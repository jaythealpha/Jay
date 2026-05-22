"""Mock Meshy/슬라이서로 파이프라인 전체 흐름 검증.

실제 Meshy API/OrcaSlicer 없이 상태 전이·캐시·라우팅·크레딧 가드를 테스트.
"""

from pathlib import Path

import pytest

from bambu_auto.adapters.sources.base import PreparedSource, SourceAdapter
from bambu_auto.config import (
    AppConfig,
    Budgets,
    MeshyBudget,
    PipelineConfig,
    PrinterDef,
    Printers,
    RoutingConfig,
    Secrets,
    Settings,
    StorageConfig,
)
from bambu_auto.core.job import Job, JobState, SourceType
from bambu_auto.core.pipeline import Pipeline
from bambu_auto.core.repository import JobRepository
from bambu_auto.services.slicer.orca import SliceResult
from bambu_auto.storage.db import Database


class FakeImageAdapter(SourceAdapter):
    def __init__(self, h: str = "abc123") -> None:
        self.h = h

    def prepare(self, work_dir: Path) -> PreparedSource:
        work_dir.mkdir(parents=True, exist_ok=True)
        img = work_dir / "input.png"
        img.write_bytes(b"fake-png-bytes")
        return PreparedSource(kind="image", input_hash=self.h, image_paths=[img])


class FakeMeshy:
    def __init__(self) -> None:
        self.calls = 0

    def image_to_3d(self, job_id, image_url, with_texture=False,
                    target_polycount=30000):
        self.calls += 1
        return ("task_fake_1", 1)

    def multi_image_to_3d(self, job_id, image_urls, with_texture=False,
                          target_polycount=30000):
        self.calls += 1
        return ("task_fake_multi", 1)

    def text_to_3d_preview(self, job_id, prompt):
        self.calls += 1
        return ("task_fake_text", 1)

    def remesh(self, job_id, input_task_id, target_polycount=30000):
        self.remeshed = True
        return ("task_fake_remesh", 1)

    def wait_for_completion(self, task_id, kind="image-to-3d"):
        return {"id": task_id, "status": "SUCCEEDED",
                "model_urls": {"stl": "https://example.com/m.stl"}}

    def download_model(self, task_data, dest_dir: Path, prefer="glb"):
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / "m.stl"
        out.write_text("solid fake\nendsolid fake\n")
        return out

    def download_all_models(self, task_data, dest_dir: Path):
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / "m.stl"
        out.write_text("solid fake\nendsolid fake\n")
        return {"stl": out}

    def balance(self):
        return {"balance": 1000}


class FakeSlicer:
    def slice(self, model_stl: Path, profile: str, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "m.gcode.3mf"
        out.write_bytes(b"PK fake 3mf")
        return SliceResult(output_3mf=out, stdout="ok", profile=profile)


@pytest.fixture
def cfg(tmp_path: Path) -> AppConfig:
    settings = Settings(
        storage=StorageConfig(data_dir=str(tmp_path), db_path=str(tmp_path / "j.db")),
        pipeline=PipelineConfig(auto_repair=False),  # 샌드박스엔 trimesh 없음
        routing=RoutingConfig(rules=[
            {"if": {"material": ["abs", "petg"]}, "use": "p2s"},
            {"if": {"max_dimension_mm": 200, "material": ["pla"]}, "use": "a1"},
            {"default": "p2s"},
        ]),
    )
    budgets = Budgets(
        meshy=MeshyBudget(monthly_credit_cap=1000, daily_credit_cap=50,
                          reserve_buffer=10),
        operation_costs={"image_to_3d_untextured": 5, "image_to_3d_textured": 15},
    )
    printers = Printers(printers={
        "p2s": PrinterDef(model="P2S", host="h", serial="s", access_code="c",
                          build_volume_mm=[256, 256, 256], default_profile="p2s_pla"),
        "a1": PrinterDef(model="A1", host="h", serial="s", access_code="c",
                         build_volume_mm=[256, 256, 256], default_profile="a1_pla"),
    })
    return AppConfig(settings, budgets, printers, Secrets(), tmp_path)


def _pipeline(cfg: AppConfig):
    db = Database(cfg.settings.storage.db_path)
    repo = JobRepository(db)
    return Pipeline(cfg, repo, FakeMeshy(), FakeSlicer()), repo


def test_full_pipeline_reaches_sliced(cfg: AppConfig) -> None:
    pipe, repo = _pipeline(cfg)
    job = Job(source_type=SourceType.IMAGE, source_payload={"source": "x.png"},
              material="pla")
    pipe.run(job, FakeImageAdapter())
    assert job.state == JobState.SLICED
    assert job.gcode_path is not None
    assert job.target_printer == "a1"  # pla + small -> a1


class FakeMultiAdapter(SourceAdapter):
    def prepare(self, work_dir: Path) -> PreparedSource:
        work_dir.mkdir(parents=True, exist_ok=True)
        ps = []
        for i in range(3):
            p = work_dir / f"i{i}.png"
            p.write_bytes(b"fake")
            ps.append(p)
        return PreparedSource(kind="multi_image", input_hash="multi1",
                              image_paths=ps)


def test_multi_image_pipeline_uses_multi_endpoint(cfg: AppConfig) -> None:
    pipe, _ = _pipeline(cfg)
    job = Job(source_type=SourceType.MULTI_IMAGE,
              source_payload={"sources": ["a", "b", "c"]}, material="pla")
    pipe.run(job, FakeMultiAdapter())
    assert job.state == JobState.SLICED
    assert job.meshy_task_id == "task_fake_multi"


class FakeTextAdapter(SourceAdapter):
    def prepare(self, work_dir: Path) -> PreparedSource:
        work_dir.mkdir(parents=True, exist_ok=True)
        return PreparedSource(kind="text", input_hash="txt1",
                              prompt="요기보 캐릭터 키링")


def test_text_pipeline_uses_text_endpoint(cfg: AppConfig) -> None:
    pipe, _ = _pipeline(cfg)
    job = Job(source_type=SourceType.TEXT,
              source_payload={"prompt": "요기보 캐릭터 키링"}, material="pla")
    pipe.run(job, FakeTextAdapter())
    assert job.state == JobState.SLICED
    assert job.meshy_task_id == "task_fake_text"


def test_remesh_runs_by_default(cfg: AppConfig) -> None:
    pipe, _ = _pipeline(cfg)
    job = Job(source_type=SourceType.IMAGE, source_payload={"source": "x.png"},
              material="pla")
    pipe.run(job, FakeImageAdapter())
    assert job.state == JobState.SLICED
    assert getattr(pipe.meshy, "remeshed", False) is True  # 리메시 호출됨


def test_routing_abs_goes_to_p2s(cfg: AppConfig) -> None:
    pipe, _ = _pipeline(cfg)
    job = Job(source_type=SourceType.IMAGE, source_payload={"source": "x.png"},
              material="abs")
    pipe.run(job, FakeImageAdapter())
    assert job.target_printer == "p2s"


def test_cache_hit_skips_meshy_call(cfg: AppConfig) -> None:
    pipe, repo = _pipeline(cfg)
    job1 = Job(source_type=SourceType.IMAGE, source_payload={"source": "x.png"},
               material="pla")
    pipe.run(job1, FakeImageAdapter(h="samehash"))
    assert pipe.meshy.calls == 1

    job2 = Job(source_type=SourceType.IMAGE, source_payload={"source": "x.png"},
               material="pla")
    pipe.run(job2, FakeImageAdapter(h="samehash"))
    assert pipe.meshy.calls == 1  # 캐시 히트 → Meshy 재호출 없음
    assert job2.state == JobState.SLICED
