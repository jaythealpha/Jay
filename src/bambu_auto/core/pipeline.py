"""파이프라인 오케스트레이터.

흐름: source 준비 → 캐시 확인 → Meshy 생성 → mesh 리페어 →
      프린터 라우팅 → 슬라이싱 → (Phase 3: 프린터 전송)

각 단계 후 Job 상태를 DB에 기록 → 중간 실패 시 그 지점부터 재개 가능.
Meshy/슬라이서는 Protocol로 추상화 → 테스트에서 Mock 주입.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from bambu_auto.adapters.sources.base import PreparedSource, SourceAdapter
from bambu_auto.config import AppConfig
from bambu_auto.core.job import Job, JobState
from bambu_auto.core.repository import JobRepository
from bambu_auto.core.router import RouteContext, select_printer
from bambu_auto.services.mesh.repair import MeshReport, repair_mesh


class MeshyPort(Protocol):
    """파이프라인이 요구하는 Meshy 인터페이스 (테스트에서 Mock)."""

    def image_to_3d(self, job_id: str, image_url: str,
                     with_texture: bool = False) -> tuple[str, int]: ...
    def multi_image_to_3d(self, job_id: str, image_urls: list[str],
                           with_texture: bool = False) -> tuple[str, int]: ...
    def text_to_3d_preview(self, job_id: str,
                           prompt: str) -> tuple[str, int]: ...
    def remesh(self, job_id: str,
               input_task_id: str) -> tuple[str, int]: ...
    def retexture(self, job_id: str, input_task_id: str,
                  prompt: str) -> tuple[str, int]: ...
    def wait_for_completion(self, task_id: str, kind: str = "image-to-3d") -> dict: ...
    def download_model(self, task_data: dict, dest_dir: Path, prefer: str = "glb") -> Path: ...
    def download_all_models(self, task_data: dict, dest_dir: Path) -> dict: ...
    def balance(self) -> dict: ...


class SlicerPort(Protocol):
    def slice(self, model_stl: Path, profile: str, out_dir: Path): ...


class Pipeline:
    def __init__(
        self,
        cfg: AppConfig,
        repo: JobRepository,
        meshy: MeshyPort,
        slicer: SlicerPort,
        on_progress: "Callable[[str], None] | None" = None,
    ) -> None:
        self.cfg = cfg
        self.repo = repo
        self.meshy = meshy
        self.slicer = slicer
        self.assets = Path(cfg.settings.storage.data_dir) / "assets"
        self._notify = on_progress or (lambda _msg: None)

    def run(self, job: Job, adapter: SourceAdapter) -> Job:
        work = self.assets / job.id
        payload = job.source_payload or {}
        try:
            if payload.get("retexture_task_id"):
                self._notify("[1/4] Meshy 재텍스처 중…")
                model_path = self._retexture(job, work)
            else:
                self._notify("[1/5] 소스 준비 중 (이미지 다운로드)…")
                prepared = self._prepare(job, adapter, work)
                self._notify("[2/5] Meshy 3D 생성 중 (1~5분 소요, 폴링)…")
                model_path = self._generate(job, prepared, work)
            self._notify("[3/5] mesh 리페어 중…")
            report = self._repair(job, Path(model_path), work)
            self._addon(job, report, work)
            self._brand(job, report, work)
            self._export_formats(job, report, work)
            self._notify("[4/5] 프린터 라우팅 중…")
            self._route(job, report)
            self._notify(f"[5/5] 슬라이싱 중 → {job.target_printer}…")
            self._slice(job, report, work)
        except Exception as e:
            # 단계별 except에서 상태를 이미 세팅했으면 유지, 아니면 일반 실패
            if not job.state.value.startswith("failed"):
                self.repo.set_state(job, JobState.FAILED_MESHY, error=str(e))
            raise
        return job

    # ---- 단계 ----

    def _prepare(self, job: Job, adapter: SourceAdapter, work: Path) -> PreparedSource:
        try:
            prepared = adapter.prepare(work / "source")
            job.input_hash = prepared.input_hash
            self.repo.set_state(job, JobState.SOURCE_FETCHED)
            return prepared
        except Exception as e:
            self.repo.set_state(job, JobState.FAILED_SOURCE, error=str(e))
            raise

    def _generate(self, job: Job, prepared: PreparedSource, work: Path) -> str:
        payload = job.source_payload or {}

        # 2D 평면 패널 모드: Meshy 미사용, 이미지 실루엣을 로컬에서 압출 (크레딧 0)
        if payload.get("flat") and prepared.image_paths:
            from bambu_auto.services.mesh.flat_panel import make_flat_panel

            self._notify("  2D 평면 패널 생성 중 (Meshy 미사용)…")
            out = work / "model" / "flat.stl"
            out.parent.mkdir(parents=True, exist_ok=True)
            r = make_flat_panel(
                prepared.image_paths[0], out,
                size_mm=float(payload.get("flat_size_mm") or 50),
                thickness_mm=float(payload.get("flat_thickness_mm") or 3.5),
            )
            if not r.get("ok"):
                self.repo.set_state(job, JobState.FAILED_MESHY,
                                    error=f"평면 패널 실패: {r.get('method')}")
                raise ValueError(f"평면 패널 실패: {r.get('method')}")
            job.model_path = str(out)
            self.repo.set_actual_credits(job.id, 0)  # 크레딧 0
            self.repo.set_state(job, JobState.MESHY_COMPLETE)
            return str(out)

        # 캐시 히트면 크레딧 소비 없이 재사용 (모델 파일들을 현재 job 폴더로 복사)
        cached = self.repo.cache_lookup(prepared.input_hash)
        if cached:
            task_id, model_path = cached
            job.meshy_task_id = task_id
            job.model_path = self._copy_cached_models(model_path, work)
            self.repo.set_state(job, JobState.MESHY_COMPLETE)
            return job.model_path

        with_tex = bool(payload.get(
            "texture", not self.cfg.budgets.saving.skip_texture_by_default))
        poly = 100000 if payload.get("precision") == "high" else 30000
        bal_before = self._safe_balance()  # 실측 크레딧 측정용

        try:
            if prepared.kind == "text":
                if not prepared.prompt:
                    raise ValueError("프롬프트가 비어있음")
                task_id, _ = self.meshy.text_to_3d_preview(
                    job.id, prepared.prompt)
                kind = "text-to-3d"
            elif prepared.kind == "multi_image":
                if not prepared.image_paths:
                    raise ValueError("멀티이미지 경로 없음")
                refs = [str(p) for p in prepared.image_paths]
                task_id, _ = self.meshy.multi_image_to_3d(
                    job.id, refs, with_texture=with_tex, target_polycount=poly)
                kind = "multi-image-to-3d"
            else:
                if not prepared.image_paths:
                    raise ValueError("이미지 경로 없음")
                task_id, _ = self.meshy.image_to_3d(
                    job.id, str(prepared.image_paths[0]),
                    with_texture=with_tex, target_polycount=poly)
                kind = "image-to-3d"

            job.meshy_task_id = task_id
            self.repo.set_state(job, JobState.MESHY_QUEUED)

            data = self.meshy.wait_for_completion(task_id, kind=kind)

            # 리메시(옵션): 생성물 토폴로지 정리 → 비watertight 실패↓.
            # 매 작업마다 생성+리메시로 크레딧이 2배 → 작업별 토글 허용.
            # 실패해도 원본으로 진행 (enhancement, 치명적 아님).
            use_remesh = bool(payload.get(
                "remesh", self.cfg.settings.pipeline.use_remesh))
            if use_remesh:
                try:
                    self._notify("  리메시 중 (토폴로지 정리)…")
                    rm_id, _ = self.meshy.remesh(
                        job.id, task_id, target_polycount=poly)
                    data = self.meshy.wait_for_completion(rm_id, kind="remesh")
                except Exception as e:  # noqa: BLE001
                    self._notify(f"  ⚠ 리메시 건너뜀: {e}")

            # 가능한 모든 포맷 다운로드 (glb/obj/stl 등) — 사용자가 원본을
            # 여러 포맷으로 받을 수 있게. 처리는 stl>glb>첫 포맷 순으로.
            models = self.meshy.download_all_models(data, work / "model")
            if not models:
                # 폴백: 단일 다운로드
                model_path = self.meshy.download_model(
                    data, work / "model", prefer="stl")
            else:
                pick = models.get("stl") or models.get("glb") or \
                    next(iter(models.values()))
                model_path = pick
            job.model_path = str(model_path)
            self.repo.cache_store(prepared.input_hash, prepared.kind,
                                  task_id, str(model_path))

            # 실측 크레딧: 잔액 차이로 이 작업의 진짜 소비량 기록
            bal_after = self._safe_balance()
            if bal_before is not None and bal_after is not None:
                delta = max(0, bal_before - bal_after)
                self.repo.set_actual_credits(job.id, delta)
                self._notify(f"  실측 크레딧 소비: {delta} (잔액 {bal_after})")

            self.repo.set_state(job, JobState.MESHY_COMPLETE)
            return str(model_path)
        except Exception as e:
            self.repo.set_state(job, JobState.FAILED_MESHY, error=str(e))
            raise

    def _safe_balance(self) -> int | None:
        try:
            d = self.meshy.balance()
            b = d.get("balance") if isinstance(d, dict) else None
            return int(b) if isinstance(b, (int, float)) else None
        except Exception:  # noqa: BLE001
            return None

    def _retexture(self, job: Job, work: Path) -> str:
        """기존 Meshy 작업에 새 텍스처를 입혀 컬러 모델 생성."""
        payload = job.source_payload or {}
        tid = payload["retexture_task_id"]
        prompt = payload.get("texture_prompt", "")
        bal_before = self._safe_balance()
        try:
            rt_id, _ = self.meshy.retexture(job.id, tid, prompt)
            job.meshy_task_id = rt_id
            self.repo.set_state(job, JobState.MESHY_QUEUED)
            data = self.meshy.wait_for_completion(rt_id, kind="retexture")
            models = self.meshy.download_all_models(data, work / "model")
            model_path = (models.get("stl") or models.get("glb")
                          or next(iter(models.values())))
            job.model_path = str(model_path)
            bal_after = self._safe_balance()
            if bal_before is not None and bal_after is not None:
                self.repo.set_actual_credits(job.id, max(0, bal_before - bal_after))
            self.repo.set_state(job, JobState.MESHY_COMPLETE)
            return str(model_path)
        except Exception as e:
            self.repo.set_state(job, JobState.FAILED_MESHY, error=str(e))
            raise

    def _copy_cached_models(self, cached_model_path: str, work: Path) -> str:
        """캐시 히트 시 원본 job의 모델 파일(전 포맷)을 현재 job 폴더로 복사.
        → 멀티 포맷 다운로드 링크가 캐시 재사용에도 동작."""
        import shutil

        src = Path(cached_model_path)
        if not src.exists():
            return cached_model_path
        dest_dir = work / "model"
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied_main = None
        for f in src.parent.glob("*.*"):
            if f.suffix.lower() in (".glb", ".obj", ".stl", ".fbx", ".usdz"):
                dst = dest_dir / f.name
                try:
                    shutil.copy2(f, dst)
                    if f == src:
                        copied_main = dst
                except Exception:  # noqa: BLE001
                    continue
        return str(copied_main or (dest_dir / src.name))

    def _repair(self, job: Job, model_path: Path, work: Path) -> MeshReport:
        if not self.cfg.settings.pipeline.auto_repair:
            self.repo.set_state(job, JobState.REPAIRED)
            return _trivial_report(model_path)
        try:
            # 평면 패널은 이미 실제 크기로 생성됨 → 재스케일 금지
            if (job.source_payload or {}).get("flat"):
                target = None
            else:
                target = self.cfg.settings.pipeline.target_size_mm
            report = repair_mesh(model_path, work / "repaired", scale_to_mm=target)
            job.repaired_path = str(report.path)
            self._notify(f"  스케일: 최대치수 → {report.max_dimension_mm:.0f}mm "
                         f"(목표 {target}mm)")

            strict = self.cfg.settings.pipeline.strict_mesh_check
            if strict and not report.printable:
                raise ValueError(
                    f"엄격 모드: 출력 불가 (watertight={report.watertight}, "
                    f"volume={report.volume_mm3:.1f}mm3). "
                    f"settings.yaml의 pipeline.strict_mesh_check=false로 완화 가능."
                )
            if not report.has_geometry:
                raise ValueError(
                    f"형상 없음: triangles={report.triangle_count}, "
                    f"max_dim={report.max_dimension_mm:.1f}mm — Meshy 생성 실패 가능"
                )
            if not report.watertight:
                self._notify(
                    f"  ⚠ 비watertight 메쉬 (slicer 자체 복구 시도). "
                    f"hull부피≈{report.volume_mm3:.0f}mm3, "
                    f"크기={report.max_dimension_mm:.0f}mm"
                )
            self.repo.set_state(job, JobState.REPAIRED)
            return report
        except Exception as e:
            self.repo.set_state(job, JobState.FAILED_REPAIR, error=str(e))
            raise

    def _addon(self, job: Job, report: MeshReport, work: Path) -> None:
        """부착(키링/받침/키캡) 또는 공동(자석/NFC). 실패해도 원본 유지."""
        payload = job.source_payload or {}
        addon = payload.get("addon")
        if addon not in ("keychain", "stand", "magnet", "nfc", "keycap",
                         "keycap_fit", "keyring"):
            return

        # 키캡: 모델을 MX 키캡 위에 얹음 (별도 처리)
        if addon == "keycap":
            from bambu_auto.services.mesh.keycap import (
                make_keycap, make_keycap_multicolor,
            )

            self._notify("  키캡 생성 중 (MX 스템 + 토퍼)…")
            out = work / "repaired" / f"{Path(report.path).stem}_keycap.stl"
            try:
                r = make_keycap(Path(report.path), out)
            except Exception as e:  # noqa: BLE001
                r = {"ok": False, "method": f"err:{e}"}
            if r.get("ok") and out.exists():
                report.path = out
                job.repaired_path = str(out)
                self.repo.save(job)
                self._notify("  ✓ 키캡 생성 완료 (MX 호환)")
            else:
                self._notify(f"  ⚠ 키캡 실패({r.get('method')}) — 원본 진행")

            # 멀티컬러: 텍스처가 있는 원본(GLB)에서 색 추출 → Bambu 3MF.
            # 단색 STL(report.path)은 슬라이싱용으로 유지, 색 파일은 별도 산출.
            self._keycap_multicolor(job, work, make_keycap_multicolor)
            return

        # 키캡 소켓 보정: 이미 키캡 형태인 모델을 1u로 스케일 + 규격 MX 소켓 차감
        if addon == "keycap_fit":
            from bambu_auto.services.mesh.keycap import fit_mx_socket

            self._notify("  키캡 소켓 보정 중 (1u 스케일 + 규격 MX 암 소켓)…")
            out = work / "repaired" / f"{Path(report.path).stem}_mxfit.stl"
            try:
                r = fit_mx_socket(Path(report.path), out)
            except Exception as e:  # noqa: BLE001
                r = {"ok": False, "method": f"err:{e}"}
            if r.get("ok") and out.exists():
                report.path = out
                job.repaired_path = str(out)
                self.repo.save(job)
                self._notify(
                    f"  ✓ MX 소켓 보정 — 배율 {r.get('scale')}×, "
                    f"캡 {r.get('base_mm')}mm / 높이 {r.get('height_mm')}mm")
            else:
                self._notify(f"  ⚠ 소켓 보정 실패({r.get('method')}) — 원본 진행")
            return

        from bambu_auto.services.mesh import addons as A

        label_map = {"keychain": "키링 고리", "stand": "받침대",
                     "magnet": "자석 공동", "nfc": "NFC 공동",
                     "keyring": "키링 구멍"}
        label = label_map[addon]
        self._notify(f"  {label} 작업 중…")
        out = work / "repaired" / f"{Path(report.path).stem}_{addon}.stl"

        method = ""
        cavity_top_z = 0.0
        try:
            if addon in ("keychain", "stand"):
                method = A.ADDONS[addon](Path(report.path), out)
            elif addon == "magnet":
                d, h = self._parse_magnet_size(payload.get("magnet_size", "5x2"))
                r = A.add_magnet_cavity(Path(report.path), out, d, h)
                method = r["method"] if r["ok"] else ""
                cavity_top_z = r["top_z"]
            elif addon == "nfc":
                r = A.add_nfc_cavity(Path(report.path), out)
                method = r["method"] if r["ok"] else ""
                cavity_top_z = r["top_z"]
            elif addon == "keyring":
                r = A.add_keyring_tab(Path(report.path), out)
                method = r["method"] if r["ok"] else ""
        except Exception as e:  # noqa: BLE001
            self._notify(f"  ⚠ {label} 오류: {e}")

        if method and out.exists():
            report.path = out
            job.repaired_path = str(out)
            if cavity_top_z > 0:
                payload["cavity_top_z"] = cavity_top_z
                job.source_payload = payload
            self.repo.save(job)
            extra = f" (자동 일시정지 Z={cavity_top_z:.1f}mm)" if cavity_top_z else ""
            tag = {"union": "union(완전결합)", "subtract": "subtract(공동)",
                   "concat": "concat(인접배치)",
                   "keyring_tab": "고리 탭",
                   "keyring_tab(concat)": "고리 탭"}.get(method, method)
            self._notify(f"  ✓ {label} — {tag}{extra}")
        else:
            self._notify(f"  ⚠ {label} 실패 — 원본으로 진행")

    def _keycap_multicolor(self, job: Job, work: Path, fn) -> None:
        """키캡 토퍼의 텍스처 색으로 Bambu 멀티컬러 3MF 생성 (실패해도 무시).
        텍스처가 박힌 GLB가 색의 원천 — 슬라이싱용 STL은 이미 색이 없음."""
        model_dir = work / "model"
        glbs = sorted(model_dir.glob("*.glb"),
                      key=lambda p: p.stat().st_size, reverse=True)
        if not glbs:
            self._notify("  ⚠ 키캡 멀티컬러 건너뜀: 텍스처 GLB 없음 "
                         "(생성 시 '텍스처' 옵션 필요)")
            return
        ddir = work / "download"
        stem = job.id[:8]
        try:
            r = fn(glbs[0], ddir, stem)
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "method": f"err:{e}"}
        if r.get("ok"):
            cols = r.get("colors") or []
            self._notify(f"  ✓ 키캡 멀티컬러 3MF — {len(cols)}색 "
                         f"{' '.join(cols)}")
        elif r.get("method") == "no_color":
            self._notify("  ⚠ 키캡 멀티컬러 건너뜀: 토퍼에 색 없음 "
                         "(Meshy 텍스처/재텍스처 필요)")
        else:
            self._notify(f"  ⚠ 키캡 멀티컬러 실패({r.get('method')}) "
                         "— 단색으로 진행")

    @staticmethod
    def _parse_magnet_size(s: str) -> tuple[float, float]:
        try:
            a, b = s.lower().replace("×", "x").split("x")
            return float(a), float(b)
        except Exception:  # noqa: BLE001
            return 5.0, 2.0  # 안전 기본값

    def _brand(self, job: Job, report: MeshReport, work: Path) -> None:
        """바닥면 디보스(로고 텍스트/아이콘). 실패해도 원본 유지."""
        payload = job.source_payload or {}
        text = (payload.get("brand_text") or "").strip()
        icon = (payload.get("brand_icon") or "").strip()
        content = text or icon
        if not content:
            return
        size_mm = float(payload.get("brand_size_mm") or 25.0)
        depth_mm = float(payload.get("brand_depth_mm") or 0.6)
        from bambu_auto.services.mesh.branding import (
            ICON_LABELS, add_bottom_branding,
        )
        label = ICON_LABELS.get(content, content)
        self._notify(f"  바닥 로고 디보스 중: '{label}'…")
        out = work / "repaired" / f"{Path(report.path).stem}_brand.stl"
        try:
            r = add_bottom_branding(Path(report.path), out,
                                    content=content, size_mm=size_mm,
                                    depth_mm=depth_mm)
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "method": f"err:{e}"}
        if r.get("ok") and out.exists():
            report.path = out
            job.repaired_path = str(out)
            self.repo.save(job)
            self._notify(f"  ✓ 바닥 로고 — {r['method']}")
        else:
            self._notify(f"  ⚠ 바닥 로고 실패({r.get('method')}) — 원본 진행")

    def _export_formats(self, job: Job, report: MeshReport, work: Path) -> None:
        """최종 메쉬를 stl/obj/glb/ply로 직접 변환 (Meshy 포맷 의존 제거).
        다운로드는 이 폴더에서 서빙 → 항상 전 포맷 보장·안정."""
        try:
            import trimesh

            mesh = trimesh.load(report.path, force="mesh")
            ddir = work / "download"
            ddir.mkdir(parents=True, exist_ok=True)
            stem = job.id[:8]
            done = []
            for ext in ("stl", "obj", "glb", "ply"):
                try:
                    mesh.export(ddir / f"{stem}.{ext}")
                    done.append(ext)
                except Exception:  # noqa: BLE001
                    continue

            # 평면 제품: 전경 색 분석(k-means)으로 색 영역별 파트를 직접
            # 압출 → 원본에 가까운 4색 멀티컬러 (단색/뭉개짐 문제 해소).
            payload = job.source_payload or {}
            if payload.get("flat"):
                pal = self._build_flat_multicolor(job, work, ddir, stem)
                if pal:
                    done.append(f"glb(4색:{len(pal)})")
            self._notify(f"  포맷 변환: {', '.join(done) or '실패'}")
        except Exception as e:  # noqa: BLE001
            self._notify(f"  ⚠ 포맷 변환 건너뜀: {e}")

    def _build_flat_multicolor(self, job: Job, work: Path, ddir: Path,
                               stem: str) -> list:
        """평면 제품을 전경 색 분석 기반 멀티컬러로 빌드 (flat_panel.build_multicolor).
        addon에 따라 키링 구멍/자석 공동을 각 색 파트에 적용. 팔레트 반환."""
        try:
            from bambu_auto.services.mesh.flat_panel import build_multicolor

            payload = job.source_payload or {}
            src = work / "source"
            imgs = sorted(src.rglob("input*")) if src.exists() else []
            if not imgs:
                return []
            addon = payload.get("addon")
            feature = None
            if addon == "keyring":
                feature = {"kind": "hole"}
            elif addon == "magnet":
                d, h = self._parse_magnet_size(payload.get("magnet_size", "5x2"))
                feature = {"kind": "cavity", "d": d, "h": h}
            elif addon == "nfc":
                feature = {"kind": "cavity", "d": 27.0, "h": 1.0}
            return build_multicolor(
                imgs[-1], ddir, stem,
                size_mm=float(payload.get("flat_size_mm") or 50),
                thickness_mm=float(payload.get("flat_thickness_mm") or 3.5),
                n_colors=4, feature=feature)
        except Exception as e:  # noqa: BLE001
            self._notify(f"  ⚠ 멀티컬러 건너뜀: {e}")
            return []


    def _route(self, job: Job, report: MeshReport) -> None:
        ctx = RouteContext(material=job.material,
                           max_dimension_mm=report.max_dimension_mm)
        job.target_printer = select_printer(
            ctx, self.cfg.settings.routing, forced=job.target_printer
        )
        self.repo.save(job)

    def _slice(self, job: Job, report: MeshReport, work: Path) -> None:
        try:
            printer = self.cfg.printers.printers[job.target_printer]
            profile = printer.default_profile
            result = self.slicer.slice(report.path, profile, work / "gcode")
            job.gcode_path = str(result.output_3mf)

            # 일시정지 (M400 U1) 결정:
            # 1) 자석/NFC 공동 → cavity 천장 Z에 자동 (override)
            # 2) 아니면 pause_at_pct (%) → 전체 Z의 해당 비율
            from bambu_auto.services.slicer.postprocess import (
                compute_total_z, inject_pause,
            )
            p = job.source_payload or {}
            cav_z = float(p.get("cavity_top_z") or 0)
            pct = float(p.get("pause_at_pct") or 0)
            pause_z = 0.0
            reason = ""
            if cav_z > 0:
                pause_z = cav_z
                reason = "공동 자동"
            elif pct > 0:
                total_z = compute_total_z(Path(job.gcode_path))
                if total_z > 0:
                    pause_z = total_z * (pct / 100.0)
                    reason = f"{pct:.0f}% × 총높이 {total_z:.1f}mm"
            if pause_z > 0:
                res = inject_pause(Path(job.gcode_path), pause_z)
                if res.get("injected"):
                    self._notify(
                        f"  ⏸ Z={pause_z:.2f}mm에 M400 U1 삽입 ({reason})")
                else:
                    self._notify(
                        f"  ⚠ 일시정지 삽입 실패: {res.get('reason')}")

            self.repo.set_state(job, JobState.SLICED)
        except Exception as e:
            self.repo.set_state(job, JobState.FAILED_SLICE, error=str(e))
            raise


def _trivial_report(path: Path) -> MeshReport:
    return MeshReport(
        path=path, watertight=True, volume_mm3=1.0,
        bbox_mm=(50.0, 50.0, 50.0), triangle_count=0, repaired=False,
    )
