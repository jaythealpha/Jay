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
            if prepared.kind != "image" or not prepared.image_paths:
                raise ValueError("Phase 2는 image 소스만 지원 (text/web은 Phase 3+)")

            # 로컬 경로를 Meshy가 받을 수 있는 형태로 — 실제 호출은 맥에서.
            # 여기서는 경로 문자열을 그대로 넘김 (MeshyClient가 URL/데이터 처리).
            img_ref = str(prepared.image_paths[0])
            task_id, _ = self.meshy.image_to_3d(
                job.id, img_ref,
                with_texture=not self.cfg.budgets.saving.skip_texture_by_default,
            )
            job.meshy_task_id = task_id
            self.repo.set_state(job, JobState.MESHY_QUEUED)

            data = self.meshy.wait_for_completion(task_id, kind="image-to-3d")
            model_path = self.meshy.download_model(data, work / "model", prefer="stl")
            job.model_path = str(model_path)
            self.repo.cache_store(prepared.input_hash, "image_to_3d",
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
            self.repo.set_state(job, JobState.SLICED)
        except Exception as e:
            self.repo.set_state(job, JobState.FAILED_SLICE, error=str(e))
            raise


def _trivial_report(path: Path) -> MeshReport:
    return MeshReport(
        path=path, watertight=True, volume_mm3=1.0,
        bbox_mm=(50.0, 50.0, 50.0), triangle_count=0, repaired=False,
    )
