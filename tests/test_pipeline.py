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

    def retexture(self, job_id, input_task_id, prompt):
        self.retextured = True
        return ("task_fake_retex", 1)

    def wait_for_completion(self, task_id, kind="image-to-3d", on_progress=None):
        if on_progress:
            on_progress("  Meshy 100% (succeeded)")
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


def test_retexture_uses_existing_task(cfg: AppConfig) -> None:
    pipe, _ = _pipeline(cfg)
    job = Job(source_type=SourceType.IMAGE,
              source_payload={"retexture_task_id": "orig_task",
                              "texture_prompt": "광택 파스텔"}, material="pla")
    pipe.run(job, FakeImageAdapter())  # adapter 미사용(재텍스처 분기)
    assert job.state == JobState.SLICED
    assert getattr(pipe.meshy, "retextured", False) is True
    assert job.meshy_task_id == "task_fake_retex"


def test_routing_abs_goes_to_p2s(cfg: AppConfig) -> None:
    pipe, _ = _pipeline(cfg)
    job = Job(source_type=SourceType.IMAGE, source_payload={"source": "x.png"},
              material="abs")
    pipe.run(job, FakeImageAdapter())
    assert job.target_printer == "p2s"


def test_cad_track_bypasses_meshy(
    cfg: AppConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CAD 트랙: Meshy 호출 없이 Claude→build123d 경로로 STL을 만들고 슬라이싱까지."""
    from bambu_auto.adapters.sources.cad_spec import CadSpecAdapter
    from bambu_auto.services.cad import claude_cad

    pipe, _ = _pipeline(cfg)

    # Anthropic 키 강제 (실제 호출은 generate_part 모킹으로 막음)
    cfg.secrets.anthropic_api_key = "sk-ant-fake"

    def fake_generate_part(prompt, out_stl, api_key, **kw):
        # 진짜 build123d로 실제 STL을 만든다 (mock의 효과 = Claude만 우회)
        out_stl.parent.mkdir(parents=True, exist_ok=True)
        code = ("from build123d import *\n"
                "with BuildPart() as p:\n    Box(12, 12, 12)\n"
                "result = p.part\n")
        ok, err = claude_cad._execute_code(code, out_stl, timeout_sec=30)
        return claude_cad.CadResult(
            ok=ok, stl_path=out_stl if ok else None,
            code=code, attempts=1, error=None if ok else err,
            model="mocked",
        )

    monkeypatch.setattr(claude_cad, "generate_part", fake_generate_part)

    job = Job(source_type=SourceType.CAD,
              source_payload={"prompt": "box 12x12x12", "cad_model": "mocked"},
              material="pla")
    pipe.run(job, CadSpecAdapter("box 12x12x12"))
    assert job.state == JobState.SLICED
    assert pipe.meshy.calls == 0  # Meshy 호출 없음
    assert job.model_path and Path(job.model_path).exists()


def test_preprocess_runs_on_image_track(
    cfg: AppConfig, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """이미지 트랙: _preprocess가 호출되고 source_payload.assessment에 결과가 저장됨."""
    from bambu_auto.services.preprocess import vision_assess

    # 평가는 mock, 정규화는 진짜 PIL로 동작
    fake_anth = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    msg = fake_anth.return_value.messages.create.return_value
    block = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    block.type = "text"
    block.text = (
        '{"score":7.5,"category":"character",'
        '"issues":[],"enhanced_prompt":"front-facing figure"}'
    )
    msg.content = [block]
    fake_module = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    fake_module.Anthropic.return_value = fake_anth.return_value
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_module)
    cfg.secrets.anthropic_api_key = "sk-ant-fake"

    # FakeImageAdapter는 'fake-png-bytes'만 쓰는데, PIL이 못 읽음 → 실제 PNG로 교체
    class RealPngAdapter:
        def prepare(self, work_dir):
            from PIL import Image
            work_dir.mkdir(parents=True, exist_ok=True)
            p = work_dir / "input.png"
            Image.new("RGB", (200, 200), (200, 100, 50)).save(p)
            return PreparedSource(kind="image", input_hash="rp1",
                                  image_paths=[p])

    pipe, _ = _pipeline(cfg)
    job = Job(source_type=SourceType.IMAGE,
              source_payload={"source": "x.png", "preprocess": True,
                              "vision_assess": True},
              material="pla")
    pipe.run(job, RealPngAdapter())

    # 정규화 결과 파일 존재 + 평가 결과가 payload에 저장됨
    work = pipe.assets / job.id
    norm = work / "preprocessed"
    assert norm.exists() and any(norm.glob("input*.png"))
    a = (job.source_payload or {}).get("assessment") or {}
    assert a.get("score") == 7.5
    assert a.get("category") == "character"
    assert job.state == JobState.SLICED


def test_preprocess_disabled_when_payload_off(
    cfg: AppConfig, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payload에 preprocess=false, vision_assess=false면 전처리 스킵."""

    class RealPngAdapter:
        def prepare(self, work_dir):
            from PIL import Image
            work_dir.mkdir(parents=True, exist_ok=True)
            p = work_dir / "input.png"
            Image.new("RGB", (200, 200), (200, 100, 50)).save(p)
            return PreparedSource(kind="image", input_hash="rp2",
                                  image_paths=[p])

    pipe, _ = _pipeline(cfg)
    job = Job(
        source_type=SourceType.IMAGE,
        source_payload={"source": "x.png", "preprocess": False,
                        "vision_assess": False},
        material="pla",
    )
    pipe.run(job, RealPngAdapter())
    # preprocessed 폴더가 만들어지지 않음 + assessment 결과 없음
    assert not (pipe.assets / job.id / "preprocessed").exists()
    assert "assessment" not in (job.source_payload or {})


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
