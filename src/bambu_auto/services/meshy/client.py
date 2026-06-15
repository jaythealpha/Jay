"""Meshy AI API 클라이언트. CreditGuard와 함께 사용.

사용 예:
    guard = CreditGuard(db, budgets)
    client = MeshyClient(api_key, config, guard)
    task_id = client.image_to_3d(job_id, image_url, with_texture=False)
    model_path = client.wait_and_download(task_id, dest_dir)

응답 진단:
    실패/대기 시 status_message, task_error.message, progress 를 함께 surface.
    4xx는 응답 body의 message/error 필드를 우선 표시 → 사용자에게 의미있는 안내.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bambu_auto.config import MeshyConfig
from bambu_auto.services.meshy.credits import BudgetExceeded, CreditGuard


class MeshyError(Exception):
    """재시도해도 의미 없는 결정적 실패 (4xx, 잘못된 입력 등)."""


class MeshyTransientError(Exception):
    """일시적 실패 (네트워크, 5xx) — 재시도 대상."""


def _extract_error_message(body_text: str) -> str:
    """응답 body에서 사람이 읽을 메시지 추출. JSON이면 message/error/detail 우선."""
    try:
        data = json.loads(body_text)
    except (json.JSONDecodeError, ValueError):
        return body_text[:300]
    if isinstance(data, dict):
        for k in ("message", "error", "detail", "errors"):
            v = data.get(k)
            if v:
                return str(v)[:300]
    return body_text[:300]


# Meshy 엔드포인트 (버전이 작업마다 다름 — 공식 docs 기준)
EP_IMAGE_TO_3D = "/openapi/v1/image-to-3d"
EP_MULTI_IMAGE_TO_3D = "/openapi/v1/multi-image-to-3d"
EP_TEXT_TO_3D = "/openapi/v2/text-to-3d"
EP_REMESH = "/openapi/v1/remesh"
EP_RETEXTURE = "/openapi/v1/retexture"
EP_BALANCE = "/openapi/v1/balance"


class MeshyClient:
    """Meshy REST API 래퍼.

    NOTE: 엔드포인트 경로·페이로드는 Meshy 공식 docs 최신 버전과 대조해서
    실제 호출 전에 검증 필요. 현재 코드는 일반적인 v2 패턴 기준 구현.
    """

    def __init__(
        self,
        api_key: str,
        config: MeshyConfig,
        guard: CreditGuard,
    ) -> None:
        if not api_key:
            raise ValueError("MESHY_API_KEY is empty. Set it in .env")
        self.api_key = api_key
        self.config = config
        self.guard = guard
        # 엔드포인트마다 버전이 다름 (image-to-3d=v1, text-to-3d=v2, balance=v1)
        # → base_url만 두고 각 메서드가 전체 경로 지정
        self._http = httpx.Client(
            base_url=config.base_url,
            timeout=config.request_timeout_sec,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def close(self) -> None:
        self._http.close()

    # ---- operations ----

    def _to_image_ref(self, image: str) -> str:
        """공개 URL이면 그대로, 로컬 경로면 base64 데이터 URI로 변환.

        Meshy image-to-3d는 image_url에 https URL 또는
        data:image/...;base64,... 형식만 허용.
        """
        if image.startswith(("http://", "https://", "data:")):
            return image
        p = Path(image)
        if not p.exists():
            raise MeshyError(f"Image not found and not a URL: {image}")
        mime = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(p.suffix.lower(), "image/png")
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def image_to_3d(
        self,
        job_id: str,
        image_url: str,
        with_texture: bool = False,
        ai_model: str | None = None,
        target_polycount: int = 30000,
    ) -> tuple[str, int]:
        """Image-to-3D 작업 제출. 크레딧 예약 → API 호출 → 예약 commit.

        image_url: 공개 URL 또는 로컬 경로(자동 base64 변환).
        ai_model: None이면 settings.yaml의 meshy.image_ai_model 사용.
        Returns: (meshy_task_id, ledger_id)
        """
        ai_model = ai_model or self.config.image_ai_model
        op = "image_to_3d_textured" if with_texture else "image_to_3d_untextured"
        ledger_id = self.guard.reserve(job_id, op, note=f"image_to_3d ai={ai_model}")
        try:
            resp = self._post(
                EP_IMAGE_TO_3D,
                {
                    "image_url": self._to_image_ref(image_url),
                    "enable_pbr": with_texture,
                    "ai_model": ai_model,
                    "topology": "triangle",
                    "target_polycount": target_polycount,
                    "target_formats": ["glb", "obj", "stl"],
                },
            )
            task_id = resp.get("result") or resp.get("id") or resp.get("task_id")
            if not task_id:
                raise MeshyError(f"Unexpected response: {resp}")
            self.guard.commit(ledger_id, meshy_task_id=task_id)
            return task_id, ledger_id
        except BudgetExceeded:
            raise
        except Exception as e:
            self.guard.refund(ledger_id, reason=f"submit_failed: {e}")
            raise

    def multi_image_to_3d(
        self,
        job_id: str,
        image_urls: list[str],
        with_texture: bool = False,
        ai_model: str | None = None,
        target_polycount: int = 30000,
    ) -> tuple[str, int]:
        """Multi-Image-to-3D (1~4장, 같은 물체 다른 각도). 품질↑.

        image_urls: 공개 URL 또는 로컬 경로(자동 base64 변환), 1~4개.
        """
        if not 1 <= len(image_urls) <= 4:
            raise MeshyError(f"multi-image는 1~4장 필요 (받음: {len(image_urls)})")
        ai_model = ai_model or self.config.image_ai_model
        op = "image_to_3d_textured" if with_texture else "image_to_3d_untextured"
        ledger_id = self.guard.reserve(job_id, op,
                                       note=f"multi_image x{len(image_urls)}")
        try:
            resp = self._post(
                EP_MULTI_IMAGE_TO_3D,
                {
                    "image_urls": [self._to_image_ref(u) for u in image_urls],
                    "should_texture": with_texture,
                    "enable_pbr": with_texture,
                    "ai_model": ai_model,
                    "target_polycount": target_polycount,
                    "target_formats": ["glb", "obj", "stl"],
                },
            )
            task_id = resp.get("result") or resp.get("id") or resp.get("task_id")
            if not task_id:
                raise MeshyError(f"Unexpected response: {resp}")
            self.guard.commit(ledger_id, meshy_task_id=task_id)
            return task_id, ledger_id
        except BudgetExceeded:
            raise
        except Exception as e:
            self.guard.refund(ledger_id, reason=f"submit_failed: {e}")
            raise

    def text_to_3d_preview(self, job_id: str, prompt: str, art_style: str = "realistic") -> tuple[str, int]:
        op = "text_to_3d_preview"
        ledger_id = self.guard.reserve(job_id, op, note=f"prompt={prompt[:60]}")
        try:
            resp = self._post(
                EP_TEXT_TO_3D,
                {"mode": "preview", "prompt": prompt, "art_style": art_style},
            )
            task_id = resp.get("result") or resp.get("id") or resp.get("task_id")
            if not task_id:
                raise MeshyError(f"Unexpected response: {resp}")
            self.guard.commit(ledger_id, meshy_task_id=task_id)
            return task_id, ledger_id
        except Exception as e:
            self.guard.refund(ledger_id, reason=f"submit_failed: {e}")
            raise

    def remesh(
        self,
        job_id: str,
        input_task_id: str,
        target_polycount: int = 30000,
        topology: str = "triangle",
    ) -> tuple[str, int]:
        """생성 완료된 task를 리메시 — 토폴로지 정리로 출력 적합성↑
        (비watertight·degenerate 감소)."""
        ledger_id = self.guard.reserve(job_id, "remesh",
                                       note=f"remesh of {input_task_id}")
        try:
            resp = self._post(
                EP_REMESH,
                {
                    "input_task_id": input_task_id,
                    "target_formats": ["glb", "obj", "stl"],
                    "topology": topology,
                    "target_polycount": target_polycount,
                },
            )
            task_id = resp.get("result") or resp.get("id") or resp.get("task_id")
            if not task_id:
                raise MeshyError(f"Unexpected response: {resp}")
            self.guard.commit(ledger_id, meshy_task_id=task_id)
            return task_id, ledger_id
        except BudgetExceeded:
            raise
        except Exception as e:
            self.guard.refund(ledger_id, reason=f"submit_failed: {e}")
            raise

    def retexture(
        self,
        job_id: str,
        input_task_id: str,
        prompt: str,
        ai_model: str | None = None,
    ) -> tuple[str, int]:
        """완료된 Meshy 작업에 새 텍스처를 입힘 (Text-to-Texture).
        input_task_id = 기존 image/text/remesh 작업 ID."""
        ai_model = ai_model or self.config.image_ai_model
        ledger_id = self.guard.reserve(job_id, "texturing",
                                       note=f"retexture of {input_task_id}")
        try:
            resp = self._post(
                EP_RETEXTURE,
                {
                    "input_task_id": input_task_id,
                    "text_style_prompt": prompt,
                    "enable_pbr": True,
                    "ai_model": ai_model,
                    "target_formats": ["glb", "obj", "stl"],
                },
            )
            task_id = resp.get("result") or resp.get("id") or resp.get("task_id")
            if not task_id:
                raise MeshyError(f"Unexpected response: {resp}")
            self.guard.commit(ledger_id, meshy_task_id=task_id)
            return task_id, ledger_id
        except BudgetExceeded:
            raise
        except Exception as e:
            self.guard.refund(ledger_id, reason=f"submit_failed: {e}")
            raise

    def balance(self) -> dict[str, Any]:
        """현재 크레딧 잔액 조회 (크레딧 소비 없음)."""
        return self._get(EP_BALANCE)

    def get_task(self, task_id: str, kind: str = "image-to-3d") -> dict[str, Any]:
        """작업 상태 조회. kind = image-to-3d | multi-image-to-3d | text-to-3d"""
        base = {
            "text-to-3d": EP_TEXT_TO_3D,
            "multi-image-to-3d": EP_MULTI_IMAGE_TO_3D,
            "remesh": EP_REMESH,
            "retexture": EP_RETEXTURE,
        }.get(kind, EP_IMAGE_TO_3D)
        return self._get(f"{base}/{task_id}")

    def wait_for_completion(
        self,
        task_id: str,
        kind: str = "image-to-3d",
        on_progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """작업 완료까지 폴링. 타임아웃·실패 시 진단 메시지 포함 예외.

        on_progress: 매 폴링마다 호출 (예: "  Meshy 35% (texturing)").
        실패 응답의 task_error.message / status_message를 surface해서
        '왜 실패했는지'를 사용자에게 노출.
        """
        deadline = time.time() + self.config.poll_max_minutes * 60
        last_progress = -1
        while time.time() < deadline:
            data = self.get_task(task_id, kind=kind)
            status = (data.get("status") or "").upper()
            progress = data.get("progress")
            if on_progress and isinstance(progress, (int, float)):
                p = int(progress)
                if p != last_progress:
                    last_progress = p
                    msg = data.get("status_message") or status.lower()
                    on_progress(f"  Meshy {p}% ({msg})")
            if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
                return data
            if status in {"FAILED", "CANCELED", "EXPIRED"}:
                err_obj = data.get("task_error") or {}
                err_msg = (
                    (isinstance(err_obj, dict) and err_obj.get("message"))
                    or data.get("status_message")
                    or "no detail"
                )
                raise MeshyError(
                    f"Meshy task {task_id} {status.lower()}: {err_msg}"
                )
            time.sleep(self.config.poll_interval_sec)
        raise MeshyError(
            f"Meshy task {task_id} timed out after "
            f"{self.config.poll_max_minutes} min (last status={last_progress}%)"
        )

    def download_model(self, task_data: dict[str, Any], dest_dir: Path, prefer: str = "glb") -> Path:
        """완료된 작업에서 모델 파일 다운로드. prefer='glb'|'obj'|'stl'|'fbx'"""
        urls = task_data.get("model_urls") or task_data.get("model_url") or {}
        if isinstance(urls, str):
            urls = {"glb": urls}
        url = urls.get(prefer) or next(iter(urls.values()), None)
        if not url:
            raise MeshyError(f"No model URL in task data: {task_data}")

        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = prefer if url.lower().endswith(prefer) else url.rsplit(".", 1)[-1].split("?")[0]
        out = dest_dir / f"{task_data.get('id', 'model')}.{ext}"
        with httpx.stream("GET", url, timeout=120) as r:
            r.raise_for_status()
            with out.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return out

    def download_all_models(
        self, task_data: dict[str, Any], dest_dir: Path,
        formats: tuple[str, ...] = ("glb", "obj", "stl", "fbx", "usdz"),
    ) -> dict[str, Path]:
        """완료된 작업의 model_urls에 있는 모든 포맷을 다운로드.
        반환: {fmt: path}. (3MF 외에 원본 모델을 여러 포맷으로 제공)"""
        urls = task_data.get("model_urls") or task_data.get("model_url") or {}
        if isinstance(urls, str):
            urls = {"glb": urls}
        dest_dir.mkdir(parents=True, exist_ok=True)
        tid = task_data.get("id", "model")
        out: dict[str, Path] = {}
        for fmt in formats:
            url = urls.get(fmt)
            if not url:
                continue
            dst = dest_dir / f"{tid}.{fmt}"
            try:
                with httpx.stream("GET", url, timeout=120) as r:
                    r.raise_for_status()
                    with dst.open("wb") as f:
                        for chunk in r.iter_bytes():
                            f.write(chunk)
                out[fmt] = dst
            except Exception:  # noqa: BLE001 — 일부 포맷 실패는 무시
                continue
        return out

    # ---- low-level ----

    @staticmethod
    def _raise_for_status(method: str, path: str, r: httpx.Response) -> None:
        if r.status_code < 400:
            return
        # JSON body면 message/error/detail 우선 — 사용자 노출용 메시지 품질↑
        readable = _extract_error_message(r.text)
        msg = f"{method} {path} -> {r.status_code}: {readable}"
        if r.status_code >= 500:
            raise MeshyTransientError(msg)   # 재시도 가치 있음
        raise MeshyError(msg)                # 4xx — 재시도 무의미

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        # 제출(POST)은 절대 자동 재시도하지 않음 — 재시도가 Meshy에 중복
        # 작업을 생성해 크레딧을 2~3배 소모할 수 있음(과금 안전). 단일 시도.
        try:
            r = self._http.post(path, json=payload)
        except httpx.TransportError as e:
            raise MeshyError(f"POST {path} network error: {e}") from e
        self._raise_for_status("POST", path, r)
        return r.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(MeshyTransientError),
        reraise=True,
    )
    def _get(self, path: str) -> dict[str, Any]:
        try:
            r = self._http.get(path)
        except httpx.TransportError as e:
            raise MeshyTransientError(f"GET {path} network error: {e}") from e
        self._raise_for_status("GET", path, r)
        return r.json()
