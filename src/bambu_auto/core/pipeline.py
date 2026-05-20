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
    def wait_for_completion(self, task_id: str, kind: str = "image-to-3d") -> dict: ...
    def download_model(self, task_data: dict, dest_dir: Path, prefer: str = "glb") -> Path: ...


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
        try:
            self._notify("[1/5] 소스 준비 중 (이미지 다운로드)…")
            prepared = self._prepare(job, adapter, work)
            self._notify("[2/5] Meshy 3D 생성 중 (1~5분 소요, 폴링)…")
            model_path = self._generate(job, prepared, work)
            self._notify("[3/5] mesh 리페어 중…")
            report = self._repair(job, Path(model_path), work)
            self._addon(job, report, work)
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
        # 캐시 히트면 크레딧 소비 없이 재사용
        cached = self.repo.cache_lookup(prepared.input_hash)
        if cached:
            task_id, model_path = cached
            job.meshy_task_id = task_id
            job.model_path = model_path
            self.repo.set_state(job, JobState.MESHY_COMPLETE)
            return model_path

        try:
            with_tex = not self.cfg.budgets.saving.skip_texture_by_default

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
                    job.id, refs, with_texture=with_tex)
                kind = "multi-image-to-3d"
            else:
                if not prepared.image_paths:
                    raise ValueError("이미지 경로 없음")
                task_id, _ = self.meshy.image_to_3d(
                    job.id, str(prepared.image_paths[0]), with_texture=with_tex)
                kind = "image-to-3d"

            job.meshy_task_id = task_id
            self.repo.set_state(job, JobState.MESHY_QUEUED)

            data = self.meshy.wait_for_completion(task_id, kind=kind)

            # 리메시(옵션): 생성물 토폴로지 정리 → 비watertight 실패↓.
            # 실패해도 원본으로 진행 (enhancement, 치명적 아님).
            if self.cfg.settings.pipeline.use_remesh:
                try:
                    self._notify("  리메시 중 (토폴로지 정리)…")
                    rm_id, _ = self.meshy.remesh(job.id, task_id)
                    data = self.meshy.wait_for_completion(rm_id, kind="remesh")
                except Exception as e:  # noqa: BLE001
                    self._notify(f"  ⚠ 리메시 건너뜀: {e}")

            model_path = self.meshy.download_model(data, work / "model", prefer="stl")
            job.model_path = str(model_path)
            self.repo.cache_store(prepared.input_hash, prepared.kind,
                                  task_id, str(model_path))
            self.repo.set_state(job, JobState.MESHY_COMPLETE)
            return str(model_path)
        except Exception as e:
            self.repo.set_state(job, JobState.FAILED_MESHY, error=str(e))
            raise

    def _repair(self, job: Job, model_path: Path, work: Path) -> MeshReport:
        if not self.cfg.settings.pipeline.auto_repair:
            self.repo.set_state(job, JobState.REPAIRED)
            return _trivial_report(model_path)
        try:
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
        """키링/받침 부착 (옵션). 실패해도 원본 유지 — 비치명적."""
        addon = (job.source_payload or {}).get("addon")
        if addon not in ("keychain", "stand"):
            return
        from bambu_auto.services.mesh.addons import ADDONS

        label = "키링 고리" if addon == "keychain" else "받침대"
        self._notify(f"  {label} 부착 중…")
        out = work / "repaired" / f"{Path(report.path).stem}_{addon}.stl"
        method = ""
        try:
            method = ADDONS[addon](Path(report.path), out)
        except Exception as e:  # noqa: BLE001
            self._notify(f"  ⚠ {label} 부착 오류: {e}")
        if method and out.exists():
            report.path = out
            job.repaired_path = str(out)
            self.repo.save(job)
            tag = "union(완전 결합)" if method == "union" else "concat(인접 배치)"
            self._notify(f"  ✓ {label} 부착 — {tag}")
        else:
            self._notify(f"  ⚠ {label} 부착 실패 — 원본으로 진행")

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

            # 자석/NFC 삽입용 일시정지 (M400 U1) 후처리
            pause_z = float((job.source_payload or {}).get("pause_at_mm") or 0)
            if pause_z > 0:
                from bambu_auto.services.slicer.postprocess import inject_pause

                res = inject_pause(Path(job.gcode_path), pause_z)
                if res.get("injected"):
                    self._notify(f"  ⏸ Z={pause_z}mm에 M400 U1 삽입 완료")
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
