"""Job 영속화 + Meshy 결과 캐시."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from bambu_auto.core.job import Job, JobState
from bambu_auto.storage.db import Database


class JobRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, job: Job) -> None:
        job.updated_at = datetime.now(timezone.utc)
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO jobs (id, state, source_type, source_payload, input_hash,
                       material, quality, target_printer, meshy_task_id, model_path,
                       repaired_path, gcode_path, print_job_id, error, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       state=excluded.state, input_hash=excluded.input_hash,
                       meshy_task_id=excluded.meshy_task_id, model_path=excluded.model_path,
                       repaired_path=excluded.repaired_path, gcode_path=excluded.gcode_path,
                       print_job_id=excluded.print_job_id, error=excluded.error,
                       target_printer=excluded.target_printer, updated_at=excluded.updated_at""",
                (
                    job.id, job.state.value, job.source_type.value,
                    json.dumps(job.source_payload), job.input_hash, job.material,
                    job.quality, job.target_printer, job.meshy_task_id, job.model_path,
                    job.repaired_path, job.gcode_path, job.print_job_id, job.error,
                    job.created_at.isoformat(), job.updated_at.isoformat(),
                ),
            )

    def set_state(self, job: Job, state: JobState, error: str | None = None) -> None:
        job.state = state
        job.error = error
        self.save(job)

    def cache_lookup(self, input_hash: str) -> tuple[str, str] | None:
        """캐시 히트 시 (meshy_task_id, model_path) 반환. 크레딧 절약 핵심."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT meshy_task_id, model_path FROM meshy_cache WHERE input_hash=?",
                (input_hash,),
            ).fetchone()
        return (row["meshy_task_id"], row["model_path"]) if row else None

    def cache_store(self, input_hash: str, operation: str,
                    meshy_task_id: str, model_path: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meshy_cache "
                "(input_hash, operation, meshy_task_id, model_path, created_at) "
                "VALUES (?,?,?,?,?)",
                (input_hash, operation, meshy_task_id, model_path,
                 datetime.now(timezone.utc).isoformat()),
            )
