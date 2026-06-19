"""FastAPI 웹 대시보드.

- GET  /                 : HTML 대시보드 (제출 폼 + job 목록 + 다운로드)
- POST /api/jobs          : 소스 제출 → NEW job 생성 (워커가 처리)
- GET  /api/jobs          : job 목록 JSON
- GET  /api/credits       : Meshy 크레딧 사용량
- GET  /api/download/{id} : 완료된 gcode.3mf 다운로드
"""

from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from pathlib import Path

import uuid

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from bambu_auto.config import AppConfig
from bambu_auto.core.job import Job, JobState, SourceType
from bambu_auto.core.repository import JobRepository
from bambu_auto.services.meshy.credits import CreditGuard
from bambu_auto.storage.db import Database
from bambu_auto.web.worker import Worker


WEB_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def _git_sha() -> str:
    """현재 실행 중인 코드의 git SHA. UI 헤더와 정적 캐시 버스팅에 사용."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=WEB_DIR, capture_output=True, text=True, timeout=2,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _slice_stats(gcode_3mf: str) -> dict:
    """슬라이싱된 .gcode.3mf에서 예상 출력시간·필라멘트량 추출.
    Bambu/Orca gcode 헤더 주석 파싱. 실패 시 빈 dict."""
    try:
        with zipfile.ZipFile(gcode_3mf) as z:
            name = next((n for n in z.namelist()
                         if n.endswith(".gcode")), None)
            if not name:
                return {}
            head = z.read(name)[:8000].decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, str] = {}
    t = re.search(r"(?:total estimated time|model printing time)\s*[:=]\s*"
                  r"([0-9hms ]+)", head, re.I)
    if t:
        out["time"] = t.group(1).strip()
    f = re.search(r"(?:total )?filament used \[g\]\s*[:=]\s*([0-9.]+)",
                  head, re.I)
    if f:
        out["filament_g"] = f.group(1)
    return out



class BulkIds(BaseModel):
    ids: list[str]


class RetextureReq(BaseModel):
    prompt: str


class SubmitReq(BaseModel):
    sources: list[str]
    track: str = "3d"            # 3d=Meshy 3D / func=기능 제품(평면) / cad=Claude CAD
    product: str = "magnet"      # func일 때: magnet | nfc | keyring
    mode: str = "batch"          # batch=각 URL 별도 물체 / multiview=한 물체 다각도
    # CAD 트랙 (track="cad")
    cad_prompt: str = ""                       # 자연어 스펙
    cad_params: dict[str, float | str] = {}    # 명시 치수 {"cap_mm": 18, ...}
    cad_model: str = "claude-sonnet-4-6"
    cad_max_attempts: int = 3
    material: str = "pla"
    printer: str = "auto"
    addon: str = ""              # "" | keychain | stand | magnet | nfc
    magnet_size: str = "5x2"     # magnet일 때 사용 (D×H mm)
    pause_at_pct: float = 0      # 0~100. 자석/NFC면 자동 override
    brand_type: str = ""         # "" | text | icon
    brand_text: str = ""
    brand_icon: str = ""         # wifi | nfc | phone | mobile | email | bluetooth
    brand_size_mm: float = 25.0
    brand_depth_mm: float = 0.6
    texture: bool = False        # 컬러/PBR 텍스처 생성 (크레딧↑)
    precision: str = "standard"  # standard | high (target_polycount)
    remesh: bool = True          # 리메시(토폴로지 정리). 끄면 크레딧 절약(생성만)
    flat: bool = False           # 2D 평면 패널 모드 (Meshy 미사용·크레딧 0)
    flat_size_mm: float = 50.0
    flat_thickness_mm: float = 3.5
    remove_bg: bool = False
    preprocess: bool = True       # 이미지 정규화 (정사각·표준 해상도·대비 보정)
    vision_assess: bool = True    # Claude vision으로 3D 적합도 평가
    meshy_key: str = ""          # BYO: 사용자 Meshy 키 (미입력 시 서버 .env)


def create_app(cfg: AppConfig) -> FastAPI:
    db = Database(cfg.settings.storage.db_path)
    repo = JobRepository(db)
    guard = CreditGuard(db, cfg.budgets)
    worker = Worker(cfg, db)

    assets_dir = Path(cfg.settings.storage.data_dir) / "assets"

    app = FastAPI(title="Bambu Auto")
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    @app.on_event("startup")
    def _start() -> None:
        worker.start()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request, "index.html", {"build": _git_sha()},
        )

    @app.get("/api/printers")
    def printers() -> dict:
        return {"printers": list(cfg.printers.printers.keys())}

    @app.get("/api/config")
    def webconfig() -> dict:
        return {"byo_required": cfg.settings.web.byo_required}

    # 실행 중인 서버의 코드 버전 — 화면 헤더에 표시해 'git pull 후 미재시작'을
    # 즉시 식별. 표시 SHA != `git rev-parse --short HEAD` 면 서버가 옛 코드.
    import datetime
    _server_version = {"version": _git_sha(),
                       "started": datetime.datetime.now().strftime("%m-%d %H:%M")}

    @app.get("/api/version")
    def version() -> dict:
        return _server_version

    upload_dir = Path(cfg.settings.storage.data_dir) / "uploads"

    @app.post("/api/upload")
    async def upload(files: list[UploadFile] = File(...)) -> dict:
        """이미지 파일 첨부 → 서버에 저장하고 절대경로 반환.
        반환된 경로를 submit의 sources로 사용 (URL 대신 로컬 파일)."""
        upload_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for f in files:
            ext = Path(f.filename or "img.png").suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".png"
            dst = upload_dir / f"{uuid.uuid4().hex}{ext}"
            with dst.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            paths.append(str(dst.resolve()))
        return {"paths": paths}

    @app.post("/api/jobs")
    def submit(req: SubmitReq) -> dict:
        printer = None if req.printer == "auto" else req.printer

        # CAD 트랙: sources 불필요 (cad_prompt만 필요)
        if req.track == "cad":
            spec = (req.cad_prompt or "").strip()
            if not spec:
                raise HTTPException(400, "CAD 스펙(자연어)이 비어있음")
            if not cfg.secrets.anthropic_api_key:
                raise HTTPException(
                    400,
                    "서버에 ANTHROPIC_API_KEY가 설정되지 않음 — CAD 트랙 불가",
                )
            payload = {
                "prompt": spec,
                "cad_params": dict(req.cad_params or {}),
                "cad_model": (req.cad_model or "claude-sonnet-4-6").strip(),
                "cad_max_attempts": int(req.cad_max_attempts or 3),
                "track": "cad",
            }
            job = Job(source_type=SourceType.CAD, source_payload=payload,
                      material=req.material, target_printer=printer)
            repo.save(job)
            return {"ids": [job.id], "count": 1}

        srcs = [s.strip() for s in req.sources if s.strip()]
        if not srcs:
            raise HTTPException(400, "입력이 비어있음")

        # 외부 배포(BYO 필수) 모드: 3D 트랙(Meshy 사용)은 키 필수
        if (req.track == "3d" and cfg.settings.web.byo_required
                and not req.meshy_key.strip()):
            raise HTTPException(400, "본인 Meshy API 키가 필요합니다 (외부 배포 모드)")

        # 기능 제품 트랙: Meshy 미사용 평면 패널 + 제품별 기능(공동/구멍)
        if req.track == "func":
            req.flat = True
            req.mode = "batch"
            req.addon = req.product   # magnet | nfc | keyring
            req.remesh = False        # 평면은 리메시 불필요

        def mk(stype: SourceType, payload: dict) -> str:
            extras: dict = {"track": req.track}
            if req.texture:
                extras["texture"] = True
            if req.precision == "high":
                extras["precision"] = "high"
            if not req.remesh:
                extras["remesh"] = False
            # 이미지 전처리·평가 토글 (기본 ON, 사용자가 끄면 명시)
            if not req.preprocess:
                extras["preprocess"] = False
            if not req.vision_assess:
                extras["vision_assess"] = False
            if req.flat:
                extras["flat"] = True
                extras["flat_size_mm"] = float(req.flat_size_mm)
                extras["flat_thickness_mm"] = float(req.flat_thickness_mm)
            if req.addon in ("keychain", "stand", "magnet", "nfc", "keycap",
                             "keycap_fit", "keyring"):
                extras["addon"] = req.addon
                if req.addon == "magnet":
                    extras["magnet_size"] = req.magnet_size
            if req.pause_at_pct and req.pause_at_pct > 0:
                extras["pause_at_pct"] = float(req.pause_at_pct)
            if req.brand_type == "text" and req.brand_text.strip():
                extras["brand_text"] = req.brand_text.strip()
                extras["brand_size_mm"] = float(req.brand_size_mm)
                extras["brand_depth_mm"] = float(req.brand_depth_mm)
            elif req.brand_type == "icon" and req.brand_icon:
                extras["brand_icon"] = req.brand_icon
                extras["brand_size_mm"] = float(req.brand_size_mm)
                extras["brand_depth_mm"] = float(req.brand_depth_mm)
            payload = {**payload, **extras}
            job = Job(source_type=stype, source_payload=payload,
                      material=req.material, target_printer=printer)
            repo.save(job)
            # BYO 키: 메모리에만 보관(DB 미저장), 워커가 사용 후 삭제
            if req.meshy_key.strip():
                worker.job_keys[job.id] = req.meshy_key.strip()
            return job.id

        if req.mode == "text":
            if len(srcs) > 20:
                raise HTTPException(400, "한 번에 최대 20개")
            ids = [mk(SourceType.TEXT, {"prompt": s}) for s in srcs]
        elif req.mode == "multiview":
            if len(srcs) > 4:
                raise HTTPException(400, "멀티뷰는 최대 4장")
            if len(srcs) == 1:
                ids = [mk(SourceType.IMAGE,
                          {"source": srcs[0], "remove_bg": req.remove_bg})]
            else:
                ids = [mk(SourceType.MULTI_IMAGE,
                          {"sources": srcs, "remove_bg": req.remove_bg})]
        else:  # batch — 각 URL이 별도 물체
            if len(srcs) > 20:
                raise HTTPException(400, "배치는 한 번에 최대 20개")
            ids = [mk(SourceType.IMAGE,
                      {"source": s, "remove_bg": req.remove_bg})
                   for s in srcs]
        return {"ids": ids, "count": len(ids)}

    _stats_cache: dict[str, dict] = {}  # gcode_path -> stats (mtime키)

    def _stats_for(gcode_path: str | None) -> dict:
        if not gcode_path or not Path(gcode_path).exists():
            return {}
        key = f"{gcode_path}:{Path(gcode_path).stat().st_mtime_ns}"
        if key not in _stats_cache:
            _stats_cache[key] = _slice_stats(gcode_path)
        return _stats_cache[key]

    @app.get("/api/jobs")
    def jobs() -> dict:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id, state, material, target_printer, gcode_path, "
                "source_payload, repaired_path, error, created_at "
                "FROM jobs ORDER BY created_at DESC LIMIT 100"
            ).fetchall()

        def msg(r) -> str:
            st = r["state"]
            if st in ("sliced", "done"):
                s = _stats_for(r["gcode_path"])
                if s:
                    bits = []
                    if s.get("time"):
                        bits.append(f"⏱ {s['time']}")
                    if s.get("filament_g"):
                        bits.append(f"🧵 {s['filament_g']}g")
                    return "✅ " + " · ".join(bits) if bits else "✅ 완료"
                return "✅ 완료"
            if st.startswith("failed"):
                return f"❌ {r['error'] or worker.last_message.get(r['id'], st)}"
            if st == "new":
                return "대기 중…"
            return worker.last_message.get(r["id"], "진행 중…")

        def opts_summary(r) -> dict:
            """요청한 옵션 요약 + 적용 여부 (repaired 파일명 기반)."""
            try:
                pl = json.loads(r["source_payload"] or "{}")
            except Exception:  # noqa: BLE001
                pl = {}
            chips: list[str] = []
            rp = (r["repaired_path"] or "").lower()
            done = r["state"] in ("sliced", "done")

            addon = pl.get("addon")
            if addon:
                label = {"keychain": "키링", "stand": "받침",
                         "magnet": f"자석{pl.get('magnet_size','')}",
                         "nfc": "NFC", "keycap": "키캡",
                         "keycap_fit": "키캡소켓"}.get(addon, addon)
                suffix = {"keycap_fit": "_mxfit"}.get(addon, f"_{addon}")
                mark = "✓" if done and suffix in rp else ("?" if done else "·")
                chips.append(f"{mark} {label}")
            if pl.get("brand_text") or pl.get("brand_icon"):
                what = pl.get("brand_text") or pl.get("brand_icon")
                mark = "✓" if done and "_brand" in rp else ("?" if done else "·")
                chips.append(f"{mark} 로고:{what}")
            if (pl.get("pause_at_pct") or 0) > 0:
                chips.append(f"· 정지{int(pl['pause_at_pct'])}%")
            # AI 적합도 평가 결과 (있을 때만)
            a = pl.get("assessment") or {}
            score = a.get("score")
            if isinstance(score, (int, float)):
                mark = ("✓" if a.get("recommend") == "proceed"
                        else "⚠" if a.get("recommend") == "warn" else "✗")
                cat = a.get("category") or ""
                chips.append(f"{mark} 평가 {score:.1f}/10 {cat}".rstrip())
            return {"chips": chips}

        data_dir = Path(cfg.settings.storage.data_dir)

        def model_formats(job_id: str) -> list[str]:
            md = data_dir / "assets" / job_id / "download"
            if not md.exists():
                return []
            fmts = sorted({p.suffix.lstrip(".").lower()
                           for p in md.glob("*.*")
                           if p.suffix.lower() in
                           (".glb", ".obj", ".stl", ".ply")})
            return fmts

        def color_info(job_id: str) -> dict:
            md = data_dir / "assets" / job_id / "download"
            if not md.exists():
                return {"palette": [], "parts": 0}
            pal: list[str] = []
            pj = list(md.glob("*.palette.json"))
            if pj:
                try:
                    pal = json.loads(pj[0].read_text()).get("colors", [])
                except Exception:  # noqa: BLE001
                    pal = []
            parts = len(list(md.glob("*_c*.stl")))
            has_3mf = bool(list(md.glob("*.color.3mf")))
            has_bambu = bool(list(md.glob("*.bambu.3mf")))
            return {"palette": pal, "parts": parts, "color3mf": has_3mf,
                    "bambu3mf": has_bambu}

        # 작업별 소비 크레딧: 실측(잔액차) 우선, 없으면 견적(committed 합)
        with db.connect() as conn:
            est = conn.execute(
                "SELECT job_id, COALESCE(SUM(credits),0) c FROM credit_ledger "
                "WHERE status='committed' GROUP BY job_id"
            ).fetchall()
            act = conn.execute(
                "SELECT job_id, credits FROM job_actual_credits"
            ).fetchall()
        est_by_job = {cr["job_id"]: cr["c"] for cr in est}
        actual_by_job = {cr["job_id"]: cr["credits"] for cr in act}

        def credit_of(jid):
            if jid in actual_by_job:
                return actual_by_job[jid], True   # (값, 실측여부)
            return est_by_job.get(jid, 0), False
        credit_by_job = credit_of

        def _has_thumb(job_id: str) -> bool:
            src = assets_dir / job_id / "source"
            if not src.exists():
                return False
            try:
                return any(src.rglob("input*"))
            except Exception:  # noqa: BLE001
                return False

        def jobrow(r):
            cval, is_actual = credit_by_job(r["id"])
            try:
                pl = json.loads(r["source_payload"] or "{}")
            except Exception:  # noqa: BLE001
                pl = {}
            ci = color_info(r["id"])
            return {
                "id": r["id"], "state": r["state"], "material": r["material"],
                "printer": r["target_printer"],
                "has_gcode": bool(r["gcode_path"]),
                "has_thumb": _has_thumb(r["id"]),
                "can_retry": r["state"].startswith("failed"),
                "created": r["created_at"],
                "message": msg(r),
                "options": opts_summary(r)["chips"],
                "model_formats": model_formats(r["id"]),
                "credits": cval,
                "credits_actual": is_actual,
                "track": pl.get("track", "3d"),  # 미태깅 기존작업 = 3D 세션
                "palette": ci["palette"],
                "color_parts": ci["parts"],
                "color3mf": ci.get("color3mf", False),
                "bambu3mf": ci.get("bambu3mf", False),
            }
        return {"jobs": [jobrow(r) for r in rows]}

    # 실시간 Meshy 잔액 (60초 TTL 캐시 — 3초 폴링 API 남용 방지)
    _bal_cache: dict[str, float | int | None] = {"ts": 0.0, "value": None}

    def _live_balance(api_key: str | None = None) -> int | None:
        import time

        from bambu_auto.services.meshy.client import MeshyClient

        # BYO 필수 모드면 .env 폴백 금지 (사용자 키만)
        fallback = "" if cfg.settings.web.byo_required else cfg.secrets.meshy_api_key
        key = (api_key or "").strip() or fallback
        if not key:
            return None
        # BYO 키는 캐시 안 함(사용자별로 다름). 서버 키만 60초 캐시.
        use_cache = not (api_key and api_key.strip())
        now = time.time()
        if use_cache and now - float(_bal_cache["ts"] or 0) < 60 \
                and _bal_cache["value"] is not None:
            return int(_bal_cache["value"])
        try:
            mc = MeshyClient(key, cfg.settings.meshy, guard)
            try:
                data = mc.balance()
            finally:
                mc.close()
            bal = data.get("balance") if isinstance(data, dict) else None
            if isinstance(bal, (int, float)):
                if use_cache:
                    _bal_cache["ts"] = now
                    _bal_cache["value"] = int(bal)
                return int(bal)
        except Exception:  # noqa: BLE001 — 잔액 조회 실패는 치명적 아님
            pass
        return int(_bal_cache["value"]) if use_cache and \
            _bal_cache["value"] is not None else None

    @app.get("/api/credits")
    def credits(x_meshy_key: str = Header(default="")) -> dict:
        u = guard.usage()
        return {"meshy_balance": _live_balance(x_meshy_key),
                "monthly_used": u.monthly_used, "monthly_cap": u.monthly_cap,
                "monthly_remaining": u.monthly_remaining,
                "daily_used": u.daily_used, "daily_cap": u.daily_cap}

    @app.get("/api/model/{job_id}/{fmt}")
    def model_file(job_id: str, fmt: str) -> FileResponse:
        fmt = fmt.lower()
        if fmt not in ("glb", "obj", "stl", "ply"):
            raise HTTPException(400, "지원하지 않는 포맷")
        md = assets_dir / job_id / "download"
        hits = sorted(md.glob(f"*.{fmt}")) if md.exists() else []
        if not hits:
            raise HTTPException(404, f"{fmt} 파일 없음")
        return FileResponse(hits[0], filename=f"{job_id[:8]}.{fmt}",
                            media_type="application/octet-stream")

    @app.get("/api/colorpart/{job_id}/{n}")
    def color_part(job_id: str, n: int) -> FileResponse:
        md = assets_dir / job_id / "download"
        hits = sorted(md.glob(f"*_c{n}.stl")) if md.exists() else []
        if not hits:
            raise HTTPException(404, "색상 파트 없음")
        return FileResponse(hits[0], filename=f"{job_id[:8]}_c{n}.stl",
                            media_type="application/octet-stream")

    @app.get("/api/color3mf/{job_id}")
    def color3mf(job_id: str) -> FileResponse:
        md = assets_dir / job_id / "download"
        hits = sorted(md.glob("*.color.3mf")) if md.exists() else []
        if not hits:
            raise HTTPException(404, "컬러 3MF 없음")
        return FileResponse(hits[0], filename=f"{job_id[:8]}_color.3mf",
                            media_type="application/octet-stream")

    @app.get("/api/bambu3mf/{job_id}")
    def bambu3mf(job_id: str) -> FileResponse:
        md = assets_dir / job_id / "download"
        hits = sorted(md.glob("*.bambu.3mf")) if md.exists() else []
        if not hits:
            raise HTTPException(404, "Bambu 3MF 없음")
        return FileResponse(hits[0], filename=f"{job_id[:8]}_bambu.3mf",
                            media_type="application/octet-stream")

    @app.get("/api/download/{job_id}")
    def download(job_id: str) -> FileResponse:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT gcode_path FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        if not row or not row["gcode_path"]:
            raise HTTPException(404, "G-code 없음 (아직 미완료)")
        p = Path(row["gcode_path"])
        if not p.exists():
            raise HTTPException(404, "파일이 디스크에 없음")
        return FileResponse(p, filename=p.name,
                            media_type="application/octet-stream")

    @app.get("/api/download-all")
    def download_all() -> StreamingResponse:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id, gcode_path FROM jobs WHERE gcode_path IS NOT NULL"
            ).fetchall()
        files = [(r["id"], Path(r["gcode_path"])) for r in rows
                 if r["gcode_path"] and Path(r["gcode_path"]).exists()]
        if not files:
            raise HTTPException(404, "완료된 파일이 없음")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for jid, p in files:
                z.write(p, arcname=f"{jid[:8]}_{p.name}")
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/zip",
            headers={"Content-Disposition":
                     'attachment; filename="bambu_auto_all.zip"'})

    @app.get("/api/thumb/{job_id}")
    def thumb(job_id: str) -> FileResponse:
        src = assets_dir / job_id / "source"
        if not src.exists():
            raise HTTPException(404, "이미지 없음")
        imgs = sorted(src.rglob("input*"))
        if not imgs:
            raise HTTPException(404, "이미지 없음")
        return FileResponse(imgs[0])

    @app.post("/api/jobs/{job_id}/retry")
    def retry(job_id: str) -> dict:
        with db.connect() as conn:
            row = conn.execute("SELECT state FROM jobs WHERE id=?",
                               (job_id,)).fetchone()
            if not row:
                raise HTTPException(404, "작업 없음")
            conn.execute(
                "UPDATE jobs SET state=?, error=NULL, model_path=NULL, "
                "repaired_path=NULL, gcode_path=NULL WHERE id=?",
                (JobState.NEW.value, job_id))
        worker.last_message.pop(job_id, None)
        return {"id": job_id, "state": "new"}

    @app.post("/api/jobs/{job_id}/retexture")
    def retexture(job_id: str, req: RetextureReq,
                  x_meshy_key: str = Header(default="")) -> dict:
        with db.connect() as conn:
            r = conn.execute(
                "SELECT meshy_task_id, material, target_printer FROM jobs "
                "WHERE id=?", (job_id,)).fetchone()
        if not r:
            raise HTTPException(404, "작업 없음")
        if not r["meshy_task_id"]:
            raise HTTPException(
                400, "Meshy 작업이 없는 항목입니다 (평면/외부파일은 Meshy 웹앱 이용)")
        if not req.prompt.strip():
            raise HTTPException(400, "텍스처 설명을 입력하세요")
        job = Job(
            source_type=SourceType.IMAGE,
            source_payload={"retexture_task_id": r["meshy_task_id"],
                            "texture_prompt": req.prompt.strip(), "track": "3d"},
            material=r["material"], target_printer=r["target_printer"])
        repo.save(job)
        key = (x_meshy_key or "").strip()
        if key:
            worker.job_keys[job.id] = key
        return {"id": job.id, "state": "new"}

    def _delete_one(job_id: str) -> None:
        with db.connect() as conn:
            conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        shutil.rmtree(assets_dir / job_id, ignore_errors=True)
        worker.last_message.pop(job_id, None)

    @app.delete("/api/jobs/{job_id}")
    def delete(job_id: str) -> dict:
        _delete_one(job_id)
        return {"deleted": job_id}

    @app.post("/api/jobs/bulk-delete")
    def bulk_delete(req: BulkIds) -> dict:
        for jid in req.ids:
            _delete_one(jid)
        return {"deleted": len(req.ids)}

    @app.get("/share/{job_id}", response_class=HTMLResponse)
    def share(request: Request, job_id: str) -> HTMLResponse:
        with db.connect() as conn:
            r = conn.execute(
                "SELECT id, state, material, target_printer, gcode_path, "
                "created_at FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        if not r:
            raise HTTPException(404, "작업을 찾을 수 없음")
        ready = bool(r["gcode_path"]) and Path(r["gcode_path"]).exists()
        return TEMPLATES.TemplateResponse(
            request, "share.html",
            {
                "job_id": job_id,
                "short_id": job_id[:8],
                "state": r["state"],
                "material": r["material"],
                "printer": r["target_printer"] or "auto",
                "created": (r["created_at"] or "")[:16].replace("T", " "),
                "ready": ready,
            },
        )

    return app
