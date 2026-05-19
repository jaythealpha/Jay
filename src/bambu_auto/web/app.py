"""FastAPI 웹 대시보드.

- GET  /                 : HTML 대시보드 (제출 폼 + job 목록 + 다운로드)
- POST /api/jobs          : 소스 제출 → NEW job 생성 (워커가 처리)
- GET  /api/jobs          : job 목록 JSON
- GET  /api/credits       : Meshy 크레딧 사용량
- GET  /api/download/{id} : 완료된 gcode.3mf 다운로드
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from bambu_auto.config import AppConfig
from bambu_auto.core.job import Job, SourceType
from bambu_auto.core.repository import JobRepository
from bambu_auto.services.meshy.credits import CreditGuard
from bambu_auto.storage.db import Database
from bambu_auto.web.worker import Worker

INDEX_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bambu Auto</title>
<style>
 :root{--bd:#e5e7eb;--mut:#6b7280;--ink:#111827;--bg:#f7f7f8}
 *{box-sizing:border-box}
 body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
   max-width:1000px;margin:0 auto;padding:24px 18px;color:var(--ink);
   background:var(--bg)}
 h1{font-size:19px;margin:0 0 4px} .sub{color:var(--mut);font-size:13px;
   margin:0 0 18px}
 .card{background:#fff;border:1px solid var(--bd);border-radius:12px;
   padding:18px;margin:14px 0}
 label.fld{display:block;font-size:12px;color:var(--mut);margin:10px 0 4px}
 textarea,select{width:100%;font-size:14px;padding:9px 11px;
   border:1px solid #d1d5db;border-radius:8px;background:#fff}
 textarea{resize:vertical;font-family:ui-monospace,Menlo,monospace;font-size:12px}
 .grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
 .opts{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-top:12px}
 .opts label{font-size:13px;color:var(--ink);display:flex;gap:6px;
   align-items:center}
 button{background:var(--ink);color:#fff;border:0;border-radius:8px;
   padding:11px 22px;font-size:14px;font-weight:600;cursor:pointer}
 button:disabled{opacity:.45}
 .seg{display:inline-flex;border:1px solid #d1d5db;border-radius:8px;
   overflow:hidden}
 .seg button{background:#fff;color:var(--ink);font-weight:500;border:0;
   padding:8px 14px;border-radius:0}
 .seg button.on{background:var(--ink);color:#fff}
 .bar{display:flex;justify-content:space-between;align-items:center;
   margin-top:14px;flex-wrap:wrap;gap:8px}
 .msg{font-size:13px;color:var(--mut)}
 table{width:100%;border-collapse:collapse;font-size:13px}
 th{text-align:left;color:var(--mut);font-weight:500;font-size:11px;
   text-transform:uppercase;letter-spacing:.04em;padding:8px 8px}
 td{padding:10px 8px;border-top:1px solid #f0f0f1;vertical-align:middle}
 .id{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--mut)}
 .b{font-size:11px;font-weight:600;padding:3px 9px;border-radius:99px;
   background:#eef0f2;color:#374151;white-space:nowrap}
 .b.ok{background:#dcfce7;color:#15803d}
 .b.no{background:#fee2e2;color:#b91c1c}
 .b.go{background:#fef9c3;color:#854d0e}
 .prog{max-width:340px;color:var(--mut);font-size:12px;overflow:hidden;
   text-overflow:ellipsis;white-space:nowrap}
 a{color:#1d4ed8;text-decoration:none;font-weight:600}
 a:hover{text-decoration:underline}
 .empty{color:var(--mut);text-align:center;padding:28px 0;font-size:13px}
</style></head><body>
<h1>Bambu Auto</h1>
<p class="sub">이미지 → 3D → 출력용 G-code · 내부팀 도구</p>

<div class="card">
  <div class="seg">
    <button id="mBatch" class="on" onclick="setMode('batch')">여러 물체 (배치)</button>
    <button id="mView" onclick="setMode('multiview')">한 물체 · 여러 각도</button>
  </div>
  <label class="fld" id="hint">한 줄에 이미지 URL 1개 = 물체 1개. 여러 줄이면 각각 별도 제작.</label>
  <textarea id="src" rows="5"
    placeholder="https://.../productA.jpg&#10;https://.../productB.jpg&#10;https://.../productC.jpg"></textarea>
  <div class="grid">
    <div><label class="fld">재질</label>
      <select id="mat">
        <option value="pla">PLA</option><option value="petg">PETG</option>
        <option value="abs">ABS</option><option value="silk">PLA Silk</option>
      </select></div>
    <div><label class="fld">프린터</label>
      <select id="prn"><option value="auto">자동 (기본 A1)</option></select></div>
    <div><label class="fld">옵션</label>
      <div class="opts"><label><input id="bg" type="checkbox" checked>
        배경·인물 제거</label></div></div>
  </div>
  <div class="bar">
    <span id="msg" class="msg"></span>
    <button id="go" onclick="submit()">제작 시작</button>
  </div>
  <div id="cred" class="msg" style="margin-top:6px"></div>
</div>

<div class="card">
  <table><thead><tr>
    <th>ID</th><th>상태</th><th>재질</th><th>프린터</th><th>진행</th>
    <th>생성</th><th>파일</th><th>공유</th>
  </tr></thead><tbody id="tb"></tbody></table>
  <div id="empty" class="empty" style="display:none">아직 작업이 없습니다.</div>
</div>

<script>
let MODE='batch';
function setMode(m){MODE=m;
 document.getElementById('mBatch').className=m==='batch'?'on':'';
 document.getElementById('mView').className=m==='multiview'?'on':'';
 document.getElementById('hint').textContent= m==='batch'
  ? '한 줄에 이미지 URL 1개 = 물체 1개. 여러 줄이면 각각 별도로 제작됩니다.'
  : '같은 물체를 다른 각도로 찍은 2~4장. 합쳐서 정밀한 3D 1개를 만듭니다.';}
async function loadPrinters(){
 try{const p=await (await fetch('/api/printers')).json();
  const s=document.getElementById('prn');
  for(const n of p.printers){const o=document.createElement('option');
   o.value=n;o.textContent=n.toUpperCase();s.appendChild(o);}
  if([...s.options].some(o=>o.value==='a1'))s.value='a1';
 }catch(e){}}
async function submit(){
 const raw=document.getElementById('src').value;
 const srcs=raw.split(/\n/).map(s=>s.trim()).filter(Boolean);
 if(!srcs.length){alert('이미지 URL을 한 줄 이상 입력하세요');return;}
 if(MODE==='multiview'&&srcs.length>4){alert('멀티뷰는 최대 4장');return;}
 if(MODE==='batch'&&srcs.length>20){alert('배치는 한 번에 최대 20개');return;}
 const b=document.getElementById('go');b.disabled=true;
 document.getElementById('msg').textContent='제출 중…';
 try{
  const r=await fetch('/api/jobs',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({sources:srcs,mode:MODE,
    material:document.getElementById('mat').value,
    printer:document.getElementById('prn').value,
    remove_bg:document.getElementById('bg').checked})});
  const j=await r.json();
  document.getElementById('msg').textContent= r.ok
   ? (j.ids.length+'개 작업 대기열 등록 (워커가 순차 처리)')
   : ('오류: '+(j.detail||r.status));
  if(r.ok)document.getElementById('src').value='';
 }catch(e){document.getElementById('msg').textContent='오류: '+e;}
 b.disabled=false;refresh();}
function badge(s){let c='b';if(s==='sliced'||s==='done')c+=' ok';
 else if(s.startsWith('failed'))c+=' no';else if(s!=='new')c+=' go';
 const t=s==='sliced'?'완료':s==='new'?'대기':s;
 return '<span class="'+c+'">'+t+'</span>';}
async function refresh(){
 const j=await (await fetch('/api/jobs')).json();
 const tb=document.getElementById('tb');tb.innerHTML='';
 document.getElementById('empty').style.display=j.jobs.length?'none':'block';
 for(const x of j.jobs){
  const dl=x.has_gcode?'<a href="/api/download/'+x.id+'">⬇ 3MF</a>':'<span class="msg">—</span>';
  const sh=x.has_gcode?'<a href="#" onclick="share(\''+x.id+'\');return false">🔗</a>':'<span class="msg">—</span>';
  const m=(x.message||'').replace(/"/g,'&quot;');
  const tr=document.createElement('tr');
  tr.innerHTML='<td class="id">'+x.id.slice(0,8)+'</td><td>'+badge(x.state)+
   '</td><td>'+x.material+'</td><td>'+(x.printer||'auto')+
   '</td><td class="prog" title="'+m+'">'+m+
   '</td><td class="msg">'+x.created.slice(5,16).replace('T',' ')+
   '</td><td>'+dl+'</td><td>'+sh+'</td>';
  tb.appendChild(tr);}
 const c=await (await fetch('/api/credits')).json();
 const bal=(c.meshy_balance==null)?'조회실패':c.meshy_balance.toLocaleString();
 document.getElementById('cred').innerHTML='<b>Meshy 잔액 '+bal+'</b>'+
  ' · 안전한도 일 '+c.daily_used+'/'+c.daily_cap+
  ' · 월 '+c.monthly_used+'/'+c.monthly_cap;}
function share(id){const u=location.origin+'/share/'+id;
 navigator.clipboard.writeText(u).then(
  ()=>alert('공유 링크 복사됨:\n'+u),()=>prompt('공유 링크:',u));}
loadPrinters();refresh();setInterval(refresh,3000);
</script></body></html>"""


class SubmitReq(BaseModel):
    sources: list[str]
    mode: str = "batch"          # batch=각 URL 별도 물체 / multiview=한 물체 다각도
    material: str = "pla"
    printer: str = "auto"
    remove_bg: bool = False


def create_app(cfg: AppConfig) -> FastAPI:
    db = Database(cfg.settings.storage.db_path)
    repo = JobRepository(db)
    guard = CreditGuard(db, cfg.budgets)
    worker = Worker(cfg, db)

    app = FastAPI(title="Bambu Auto")

    @app.on_event("startup")
    def _start() -> None:
        worker.start()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/printers")
    def printers() -> dict:
        return {"printers": list(cfg.printers.printers.keys())}

    @app.post("/api/jobs")
    def submit(req: SubmitReq) -> dict:
        srcs = [s.strip() for s in req.sources if s.strip()]
        if not srcs:
            raise HTTPException(400, "이미지 URL이 비어있음")
        printer = None if req.printer == "auto" else req.printer

        def mk(stype: SourceType, payload: dict) -> str:
            job = Job(source_type=stype, source_payload=payload,
                      material=req.material, target_printer=printer)
            repo.save(job)
            return job.id

        if req.mode == "multiview":
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

    @app.get("/api/jobs")
    def jobs() -> dict:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id, state, material, target_printer, gcode_path, "
                "error, created_at FROM jobs ORDER BY created_at DESC LIMIT 100"
            ).fetchall()

        def msg(r) -> str:
            st = r["state"]
            if st in ("sliced", "done"):
                return "✅ 완료"
            if st.startswith("failed"):
                return f"❌ {r['error'] or worker.last_message.get(r['id'], st)}"
            if st == "new":
                return "대기 중…"
            return worker.last_message.get(r["id"], "진행 중…")

        return {"jobs": [{
            "id": r["id"], "state": r["state"], "material": r["material"],
            "printer": r["target_printer"],
            "has_gcode": bool(r["gcode_path"]),
            "created": r["created_at"],
            "message": msg(r),
        } for r in rows]}

    # 실시간 Meshy 잔액 (60초 TTL 캐시 — 3초 폴링 API 남용 방지)
    _bal_cache: dict[str, float | int | None] = {"ts": 0.0, "value": None}

    def _live_balance() -> int | None:
        import time

        from bambu_auto.services.meshy.client import MeshyClient

        now = time.time()
        if now - float(_bal_cache["ts"] or 0) < 60 and _bal_cache["value"] is not None:
            return int(_bal_cache["value"])
        try:
            mc = MeshyClient(cfg.secrets.meshy_api_key, cfg.settings.meshy, guard)
            try:
                data = mc.balance()
            finally:
                mc.close()
            bal = data.get("balance") if isinstance(data, dict) else None
            if isinstance(bal, (int, float)):
                _bal_cache["ts"] = now
                _bal_cache["value"] = int(bal)
                return int(bal)
        except Exception:  # noqa: BLE001 — 잔액 조회 실패는 치명적 아님
            pass
        return int(_bal_cache["value"]) if _bal_cache["value"] is not None else None

    @app.get("/api/credits")
    def credits() -> dict:
        u = guard.usage()
        return {"meshy_balance": _live_balance(),
                "monthly_used": u.monthly_used, "monthly_cap": u.monthly_cap,
                "monthly_remaining": u.monthly_remaining,
                "daily_used": u.daily_used, "daily_cap": u.daily_cap}

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

    @app.get("/share/{job_id}", response_class=HTMLResponse)
    def share(job_id: str) -> str:
        with db.connect() as conn:
            r = conn.execute(
                "SELECT id, state, material, target_printer, gcode_path, "
                "created_at FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        if not r:
            raise HTTPException(404, "작업을 찾을 수 없음")
        ready = bool(r["gcode_path"]) and Path(r["gcode_path"]).exists()
        dl = (f'<a href="/api/download/{job_id}" '
              f'style="display:inline-block;background:#111;color:#fff;'
              f'padding:12px 22px;border-radius:8px;text-decoration:none;'
              f'font-weight:600">⬇ 3MF 다운로드</a>') if ready else \
             '<p style="color:#a40000">아직 준비되지 않았습니다 ' \
             f'(상태: {r["state"]})</p>'
        return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bambu Auto 공유 — {job_id[:8]}</title>
<style>body{{font-family:-apple-system,sans-serif;max-width:560px;
margin:60px auto;padding:0 16px;text-align:center;color:#1a1a1a}}
.card{{border:1px solid #e3e3e3;border-radius:12px;padding:32px}}
.m{{color:#888;font-size:13px}}</style></head><body>
<div class="card">
<h2>3D 프린트 파일 공유</h2>
<p class="m">ID {job_id[:8]} · 재질 {r['material']} ·
 프린터 {r['target_printer'] or 'auto'} ·
 {r['created_at'][:16].replace('T',' ')}</p>
<div style="margin:28px 0">{dl}</div>
<p class="m">이 파일을 Bambu Studio/Handy로 열어 출력하세요.</p>
</div></body></html>"""

    return app
