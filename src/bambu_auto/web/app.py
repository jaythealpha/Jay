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
<title>Bambu Auto — 3D 제작 파이프라인</title>
<style>
 body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
   max-width:920px;margin:24px auto;padding:0 16px;color:#1a1a1a;background:#fafafa}
 h1{font-size:20px} h2{font-size:15px;margin-top:28px;color:#444}
 .card{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:16px;margin:12px 0}
 input,select,button{font-size:14px;padding:8px 10px;border:1px solid #ccc;
   border-radius:7px;margin:4px 0}
 input[type=text]{width:100%;box-sizing:border-box}
 button{background:#111;color:#fff;border:0;cursor:pointer;padding:9px 18px}
 button:disabled{opacity:.5}
 table{width:100%;border-collapse:collapse;font-size:13px}
 th,td{text-align:left;padding:7px 6px;border-bottom:1px solid #eee}
 .s{font-size:11px;padding:2px 8px;border-radius:20px;background:#eee}
 .s.done{background:#d8f3dc;color:#1b5e20}
 .s.fail{background:#ffd9d9;color:#a40000}
 .s.run{background:#fff3cd;color:#7a5b00}
 .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .muted{color:#888;font-size:12px} a.dl{font-weight:600}
</style></head><body>
<h1>Bambu Auto — 이미지 → 3D → G-code</h1>
<div class="card">
  <div class="row">
    <textarea id="src" rows="3" style="width:100%;box-sizing:border-box;
      font-size:14px;padding:8px;border:1px solid #ccc;border-radius:7px"
      placeholder="이미지 URL — 한 줄에 하나 (1장=단일, 2~4장=멀티뷰, 같은 물체 다른 각도면 품질↑)"></textarea>
  </div>
  <div class="row">
    <select id="mat">
      <option value="pla">PLA</option><option value="petg">PETG</option>
      <option value="abs">ABS</option><option value="silk">PLA Silk</option>
    </select>
    <select id="prn"><option value="auto">자동 (기본 A1)</option></select>
    <label class="muted"><input id="bg" type="checkbox" checked>
      배경·인물 제거</label>
    <button id="go" onclick="submit()">제작 시작</button>
  </div>
  <div id="msg" class="muted"></div>
  <div id="cred" class="muted"></div>
</div>
<h2>제작 현황 / 다운로드</h2>
<div class="card"><table id="tbl"><thead><tr>
 <th>ID</th><th>상태</th><th>재질</th><th>프린터</th><th>진행</th>
 <th>생성</th><th>파일</th><th>공유</th></tr></thead><tbody></tbody></table></div>
<script>
async function loadPrinters(){
 try{const p=await (await fetch('/api/printers')).json();
  const sel=document.getElementById('prn');
  for(const name of p.printers){
   const o=document.createElement('option');o.value=name;
   o.textContent=name.toUpperCase();sel.appendChild(o);}
  if([...sel.options].some(o=>o.value==='a1')) sel.value='a1';
 }catch(e){}
}
async function submit(){
 const raw=document.getElementById('src').value;
 const srcs=raw.split(/\\n/).map(s=>s.trim()).filter(Boolean);
 if(!srcs.length){alert('이미지 URL을 한 줄 이상 입력하세요');return;}
 if(srcs.length>4){alert('최대 4장까지 가능합니다');return;}
 const b=document.getElementById('go');b.disabled=true;
 document.getElementById('msg').textContent='제출 중…';
 try{
  const r=await fetch('/api/jobs',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({sources:srcs,
    material:document.getElementById('mat').value,
    printer:document.getElementById('prn').value,
    remove_bg:document.getElementById('bg').checked})});
  const j=await r.json();
  document.getElementById('msg').textContent= r.ok
   ? '대기열 등록: '+j.id+' ('+srcs.length+'장, 워커가 순차 처리)'
   : ('오류: '+(j.detail||r.status));
 }catch(e){document.getElementById('msg').textContent='오류: '+e;}
 b.disabled=false;refresh();
}
function badge(s){let c='s';if(s==='done')c+=' done';
 else if(s.startsWith('failed'))c+=' fail';
 else if(s!=='new')c+=' run';return '<span class="'+c+'">'+s+'</span>';}
async function refresh(){
 const j=await (await fetch('/api/jobs')).json();
 const tb=document.querySelector('#tbl tbody');tb.innerHTML='';
 for(const x of j.jobs){
  const dl=x.has_gcode
   ?'<a class="dl" href="/api/download/'+x.id+'">⬇ 3MF</a>':'—';
  const sh=x.has_gcode
   ?'<a href="#" onclick="share(\\''+x.id+'\\');return false">🔗 링크</a>':'—';
  tb.insertAdjacentHTML('beforeend',
   '<tr><td>'+x.id.slice(0,8)+'</td><td>'+badge(x.state)+'</td>'+
   '<td>'+x.material+'</td><td>'+(x.printer||'auto')+'</td>'+
   '<td class="muted">'+(x.message||'')+'</td>'+
   '<td class="muted">'+x.created.slice(5,16).replace('T',' ')+'</td>'+
   '<td>'+dl+'</td><td>'+sh+'</td></tr>');
 }
 const c=await (await fetch('/api/credits')).json();
 const bal=(c.meshy_balance==null)?'조회실패':c.meshy_balance.toLocaleString();
 document.getElementById('cred').innerHTML=
  '<b>Meshy 실시간 잔액: '+bal+'</b>'+
  ' &nbsp;·&nbsp; 안전한도 일 '+c.daily_used+'/'+c.daily_cap+
  ' · 월 '+c.monthly_used+'/'+c.monthly_cap;
}
function share(id){
 const u=location.origin+'/share/'+id;
 navigator.clipboard.writeText(u).then(
  ()=>alert('공유 링크 복사됨:\\n'+u),
  ()=>prompt('공유 링크:',u));
}
loadPrinters();refresh();setInterval(refresh,3000);
</script></body></html>"""


class SubmitReq(BaseModel):
    sources: list[str]
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
        if len(srcs) > 4:
            raise HTTPException(400, "최대 4장까지 가능")
        if len(srcs) == 1:
            payload = {"source": srcs[0], "remove_bg": req.remove_bg}
            stype = SourceType.IMAGE
        else:
            payload = {"sources": srcs, "remove_bg": req.remove_bg}
            stype = SourceType.MULTI_IMAGE
        job = Job(
            source_type=stype,
            source_payload=payload,
            material=req.material,
            target_printer=None if req.printer == "auto" else req.printer,
        )
        repo.save(job)
        return {"id": job.id, "state": job.state.value}

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
