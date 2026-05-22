"""백그라운드 워커: NEW 상태 job을 하나씩 파이프라인에 태움.

웹 제출은 job을 DB에 NEW로만 기록하고 즉시 반환. 이 워커 스레드가
오래된 NEW job부터 순차 처리 (단일 스레드 → SQLite 동시성 안전,
Meshy 동시 호출 폭주 방지).
"""

from __future__ import annotations

import threading
import time

from bambu_auto.config import AppConfig
from bambu_auto.core.runner import run_job
from bambu_auto.storage.db import Database


class Worker:
    def __init__(self, cfg: AppConfig, db: Database, poll_sec: float = 3.0) -> None:
        self.cfg = cfg
        self.db = db
        self.poll_sec = poll_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.current_job: str | None = None
        self.last_message: dict[str, str] = {}  # job_id -> 최근 진행 메시지
        self.job_keys: dict[str, str] = {}      # job_id -> BYO Meshy 키(메모리만)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _next_job_id(self) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE state='new' "
                "ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
        return row["id"] if row else None

    def _loop(self) -> None:
        while not self._stop.is_set():
            job_id = self._next_job_id()
            if not job_id:
                time.sleep(self.poll_sec)
                continue
            self.current_job = job_id
            try:
                run_job(
                    self.cfg, self.db, job_id,
                    on_progress=lambda m, jid=job_id: self.last_message.__setitem__(jid, m),
                    api_key=self.job_keys.get(job_id),  # BYO 키(있으면)
                )
            except Exception as e:  # noqa: BLE001 — 상태는 pipeline이 DB에 기록
                self.last_message[job_id] = f"실패: {e}"
            finally:
                self.current_job = None
                self.job_keys.pop(job_id, None)  # 키는 처리 후 메모리에서 제거
