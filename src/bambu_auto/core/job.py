from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobState(str, enum.Enum):
    NEW = "new"
    SOURCE_FETCHED = "source_fetched"
    MESHY_QUEUED = "meshy_queued"
    MESHY_COMPLETE = "meshy_complete"
    REVIEW_PENDING = "review_pending"
    REPAIRED = "repaired"
    SLICED = "sliced"
    PRINTER_QUEUED = "printer_queued"
    PRINTING = "printing"
    DONE = "done"

    FAILED_SOURCE = "failed_source"
    FAILED_MESHY = "failed_meshy"
    FAILED_REPAIR = "failed_repair"
    FAILED_SLICE = "failed_slice"
    FAILED_PRINT = "failed_print"


TERMINAL_STATES = {
    JobState.DONE,
    JobState.FAILED_SOURCE,
    JobState.FAILED_MESHY,
    JobState.FAILED_REPAIR,
    JobState.FAILED_SLICE,
    JobState.FAILED_PRINT,
}


class SourceType(str, enum.Enum):
    IMAGE = "image"
    MULTI_IMAGE = "multi_image"
    WEB_URL = "web_url"
    TEXT = "text"


class Job(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: JobState = JobState.NEW
    source_type: SourceType
    source_payload: dict[str, Any]            # path, url, prompt, etc.
    input_hash: str | None = None             # for cache dedup
    material: str = "pla"
    quality: str = "standard"
    target_printer: str | None = None         # 'p2s' | 'a1' | None=auto
    meshy_task_id: str | None = None
    model_path: str | None = None             # downloaded .glb/.stl
    repaired_path: str | None = None
    gcode_path: str | None = None
    print_job_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
