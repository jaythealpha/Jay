"""파이프라인 실행 진입점 (CLI·웹 공용).

cli._run_job의 로직을 typer/console 비의존으로 추출.
progress 콜백으로 진행 상황을 호출자에게 전달.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from bambu_auto.adapters.sources.image import ImageSourceAdapter
from bambu_auto.config import AppConfig
from bambu_auto.core.job import Job, SourceType
from bambu_auto.core.pipeline import Pipeline
from bambu_auto.core.repository import JobRepository
from bambu_auto.services.meshy.client import MeshyClient
from bambu_auto.services.meshy.credits import CreditGuard
from bambu_auto.services.slicer.orca import OrcaSlicer
from bambu_auto.storage.db import Database

ProgressCb = Callable[[str], None]


class JobNotFound(Exception):
    pass


def run_job(
    cfg: AppConfig,
    db: Database,
    job_id: str,
    on_progress: ProgressCb | None = None,
    api_key: str | None = None,
) -> Job:
    """job_id를 파이프라인에 태우고 완료된 Job 반환. 예외는 그대로 전파.

    api_key: BYO-key — 사용자가 입력한 Meshy 키. None이면 .env 키 사용.
    """
    notify = on_progress or (lambda _m: None)
    repo = JobRepository(db)

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise JobNotFound(job_id)

    job = Job(
        id=row["id"],
        source_type=SourceType(row["source_type"]),
        source_payload=json.loads(row["source_payload"]),
        material=row["material"],
        quality=row["quality"],
        target_printer=row["target_printer"],
    )

    remove_bg = job.source_payload.get("remove_bg", False)
    if job.source_type == SourceType.IMAGE:
        adapter = ImageSourceAdapter(
            job.source_payload["source"], remove_bg=remove_bg)
    elif job.source_type == SourceType.MULTI_IMAGE:
        from bambu_auto.adapters.sources.multi_image import MultiImageSourceAdapter
        adapter = MultiImageSourceAdapter(
            job.source_payload["sources"], remove_bg=remove_bg)
    elif job.source_type == SourceType.TEXT:
        from bambu_auto.adapters.sources.text import TextSourceAdapter
        adapter = TextSourceAdapter(job.source_payload["prompt"])
    else:
        raise ValueError("지원하지 않는 소스 타입 (web은 추후)")

    guard = CreditGuard(db, cfg.budgets)
    key = api_key or cfg.secrets.meshy_api_key
    meshy = MeshyClient(key, cfg.settings.meshy, guard)
    try:
        slicer = OrcaSlicer()
    except Exception as e:  # noqa: BLE001
        notify(f"⚠ OrcaSlicer 미준비: {e} (슬라이싱 전 단계까지)")
        slicer = None  # type: ignore
    pipe = Pipeline(cfg, repo, meshy, slicer, on_progress=notify)
    try:
        pipe.run(job, adapter)
        return job
    finally:
        meshy.close()
