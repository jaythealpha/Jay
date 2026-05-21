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

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from bambu_auto.config import AppConfig
from bambu_auto.core.job import Job, JobState, SourceType
from bambu_auto.core.repository import JobRepository
from bambu_auto.services.meshy.credits import CreditGuard
from bambu_auto.storage.db import Database
from bambu_auto.web.worker import Worker


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

INDEX_HTML = r"""<!doctype html>
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
    <button id="mBatch" class="on" onclick="setMode('batch')">이미지 (배치)</button>
    <button id="mView" onclick="setMode('multiview')">한 물체·여러 각도</button>
    <button id="mText" onclick="setMode('text')">텍스트 → 3D</button>
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
    <div><label class="fld">추가</label>
      <select id="addon" onchange="onAddonChange()">
        <option value="">없음</option>
        <option value="keychain">열쇠고리</option>
        <option value="stand">받침대</option>
        <option value="magnet">자석 삽입(공동+자동정지)</option>
        <option value="nfc">NFC 삽입(27mm 공동+자동정지)</option>
        <option value="keycap">키캡 (기계식 키보드 MX)</option>
      </select></div>
  </div>
  <div class="opts" style="margin-top:10px">
    <label><input id="bg" type="checkbox" checked> 배경·인물 제거</label>
    <label id="magWrap" style="display:none">자석 크기:
      <select id="magsize">
        <option value="4x2">4×2</option><option value="4x3">4×3</option>
        <option value="5x2" selected>5×2</option><option value="5x3">5×3</option>
        <option value="6x2">6×2</option><option value="6x3">6×3</option>
        <option value="8x2">8×2</option><option value="10x2">10×2</option>
      </select></label>
    <span style="flex:1"></span>
    <label id="pauseWrap">수동 일시정지(%):
      <input id="pause" type="number" min="0" max="100" step="1" value="0"
        style="width:70px;padding:6px 8px;border:1px solid #d1d5db;
        border-radius:6px"></label>
    <span class="msg" id="pauseHint">0=없음. 자석/NFC면 자동.</span>
  </div>
  <div class="opts" style="margin-top:10px;flex-wrap:wrap">
    <label>바닥 로고:
      <select id="brandType" onchange="onBrandChange()">
        <option value="">없음</option>
        <option value="text">텍스트</option>
        <option value="icon">아이콘</option>
      </select></label>
    <input id="brandText" type="text" placeholder="예: YOGIBO"
      style="flex:1;min-width:160px;padding:6px 10px;border:1px solid #d1d5db;
      border-radius:6px;display:none">
    <select id="brandIcon" style="display:none">
      <option value="wifi">Wi-Fi</option>
      <option value="nfc">NFC</option>
      <option value="phone">전화 ☎</option>
      <option value="mobile">휴대폰 📱</option>
      <option value="email">이메일 ✉</option>
      <option value="bluetooth">블루투스</option>
    </select>
    <label class="msg">크기(mm)
      <input id="brandSize" type="number" min="8" max="80" step="1" value="25"
        style="width:60px;padding:5px 7px;border:1px solid #d1d5db;
        border-radius:6px"></label>
    <label class="msg">깊이(mm)
      <input id="brandDepth" type="number" min="0.2" max="2.0" step="0.1"
        value="0.6" style="width:60px;padding:5px 7px;
        border:1px solid #d1d5db;border-radius:6px"></label>
  </div>
  <div class="bar">
    <span id="msg" class="msg"></span>
    <button id="go" onclick="submit()">제작 시작</button>
  </div>
  <div id="cred" class="msg" style="margin-top:6px"></div>
</div>

<div class="card">
  <div class="bar" style="margin:0 0 12px">
    <strong style="font-size:14px">제작 현황</strong>
    <span>
      <button id="bulk" onclick="bulkDelete()" disabled
        style="background:#b91c1c;padding:7px 14px;font-size:13px;
        margin-right:8px">선택 삭제</button>
      <a href="/api/download-all" style="font-size:13px">⬇ 완료분 전체 ZIP</a>
    </span>
  </div>
  <table><thead><tr>
    <th><input type="checkbox" id="all" onclick="toggleAll(this)"></th>
    <th></th><th>ID</th><th>상태</th><th>재질</th><th>프린터</th>
    <th>옵션</th><th>진행</th><th>생성</th><th>파일</th><th>공유</th><th></th>
  </tr></thead><tbody id="tb"></tbody></table>
  <div id="empty" class="empty" style="display:none">아직 작업이 없습니다.</div>
</div>

<script>
let MODE='batch';
function setMode(m){MODE=m;
 document.getElementById('mBatch').className=m==='batch'?'on':'';
 document.getElementById('mView').className=m==='multiview'?'on':'';
 document.getElementById('mText').className=m==='text'?'on':'';
 const h={batch:'한 줄에 이미지 URL 1개 = 물체 1개. 여러 줄이면 각각 별도 제작.',
  multiview:'같은 물체를 다른 각도로 찍은 2~4장. 합쳐서 정밀한 3D 1개.',
  text:'한 줄에 설명 1개 = 굿즈 1개. 예: 요기보 캐릭터 키링, 단순한 형태'};
 document.getElementById('hint').textContent=h[m];
 document.getElementById('src').placeholder= m==='text'
  ? '요기보 캐릭터 하트 키링, 두꺼운 벽\\n요기보 캐릭터 미니 피규어'
  : 'https://.../productA.jpg';}
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
 if(!srcs.length){alert('한 줄 이상 입력하세요');return;}
 if(MODE==='multiview'&&srcs.length>4){alert('멀티뷰는 최대 4장');return;}
 if((MODE==='batch'||MODE==='text')&&srcs.length>20){
  alert('한 번에 최대 20개');return;}
 const b=document.getElementById('go');b.disabled=true;
 document.getElementById('msg').textContent='제출 중…';
 try{
  const r=await fetch('/api/jobs',{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({sources:srcs,mode:MODE,
    material:document.getElementById('mat').value,
    printer:document.getElementById('prn').value,
    addon:document.getElementById('addon').value,
    magnet_size:document.getElementById('magsize').value,
    pause_at_pct:parseFloat(document.getElementById('pause').value)||0,
    brand_type:document.getElementById('brandType').value,
    brand_text:document.getElementById('brandText').value,
    brand_icon:document.getElementById('brandIcon').value,
    brand_size_mm:parseFloat(document.getElementById('brandSize').value)||25,
    brand_depth_mm:parseFloat(document.getElementById('brandDepth').value)||0.6,
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
  let dl=x.has_gcode?'<a href="/api/download/'+x.id+'">⬇ 3MF</a>':'';
  const mf=(x.model_formats||[]).map(f=>
   ' <a href="/api/model/'+x.id+'/'+f+'" class="msg">'+f+'</a>').join('');
  dl=(dl+mf)||'<span class="msg">—</span>';
  const sh=x.has_gcode?'<a href="#" onclick="share(\''+x.id+'\');return false">🔗</a>':'<span class="msg">—</span>';
  const rt=x.can_retry?'<a href="#" onclick="retry(\''+x.id+'\');return false">↻</a> ':'';
  const m=(x.message||'').replace(/"/g,'&quot;');
  const th='<img src="/api/thumb/'+x.id+'" style="width:34px;height:34px;'+
   'object-fit:cover;border-radius:6px;background:#eee" '+
   'onerror="this.style.visibility=\'hidden\'">';
  const ck=SEL.has(x.id)?' checked':'';
  const tr=document.createElement('tr');
  const op=(x.options||[]).map(s=>'<span class="b" style="margin-right:3px">'+
   s+'</span>').join('') || '<span class="msg">—</span>';
  tr.innerHTML='<td><input type="checkbox" class="sel" data-id="'+x.id+'"'+
   ck+' onclick="onSel(this)"></td>'+
   '<td>'+th+'</td><td class="id">'+x.id.slice(0,8)+
   '</td><td>'+badge(x.state)+
   '</td><td>'+x.material+'</td><td>'+(x.printer||'auto')+
   '</td><td>'+op+
   '</td><td class="prog" title="'+m+'">'+m+
   '</td><td class="msg">'+x.created.slice(5,16).replace('T',' ')+
   '</td><td>'+dl+'</td><td>'+sh+
   '</td><td class="msg">'+rt+
   '<a href="#" onclick="del(\''+x.id+'\');return false">🗑</a></td>';
  tb.appendChild(tr);}
 syncBulk();
 const c=await (await fetch('/api/credits')).json();
 const bal=(c.meshy_balance==null)?'조회실패':c.meshy_balance.toLocaleString();
 const daily=c.daily_cap>0?(c.daily_used+'/'+c.daily_cap):(c.daily_used+' (무제한)');
 document.getElementById('cred').innerHTML='<b>Meshy 잔액 '+bal+'</b>'+
  ' · 일 '+daily+' · 월 '+c.monthly_used+'/'+c.monthly_cap;}
function share(id){const u=location.origin+'/share/'+id;
 navigator.clipboard.writeText(u).then(
  ()=>alert('공유 링크 복사됨:\n'+u),()=>prompt('공유 링크:',u));}
async function retry(id){
 await fetch('/api/jobs/'+id+'/retry',{method:'POST'});refresh();}
async function del(id){
 if(!confirm('이 작업을 삭제할까요? (파일도 함께 삭제)'))return;
 await fetch('/api/jobs/'+id,{method:'DELETE'});SEL.delete(id);refresh();}
const SEL=new Set();
function onSel(cb){cb.checked?SEL.add(cb.dataset.id):SEL.delete(cb.dataset.id);
 syncBulk();}
function toggleAll(cb){document.querySelectorAll('.sel').forEach(x=>{
 x.checked=cb.checked;x.checked?SEL.add(x.dataset.id):SEL.delete(x.dataset.id);});
 syncBulk();}
function syncBulk(){const n=SEL.size;const b=document.getElementById('bulk');
 b.disabled=!n;b.textContent=n?('선택 삭제 ('+n+')'):'선택 삭제';}
async function bulkDelete(){
 const ids=[...SEL];if(!ids.length)return;
 if(!confirm(ids.length+'개 작업을 삭제할까요? (파일도 함께 삭제)'))return;
 await fetch('/api/jobs/bulk-delete',{method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({ids:ids})});
 SEL.clear();document.getElementById('all').checked=false;refresh();}
function onBrandChange(){const t=document.getElementById('brandType').value;
 document.getElementById('brandText').style.display=t==='text'?'block':'none';
 document.getElementById('brandIcon').style.display=t==='icon'?'inline-block':'none';}
function onAddonChange(){const v=document.getElementById('addon').value;
 document.getElementById('magWrap').style.display=v==='magnet'?'flex':'none';
 const auto=(v==='magnet'||v==='nfc');
 document.getElementById('pauseHint').textContent=auto
  ?'자석/NFC: 공동 위치에서 자동 일시정지 (이 값은 무시됨)'
  :'0=없음. 50=출력 절반에서 정지';}
loadPrinters();refresh();setInterval(refresh,3000);
onAddonChange();onBrandChange();
</script></body></html>"""


class BulkIds(BaseModel):
    ids: list[str]


class SubmitReq(BaseModel):
    sources: list[str]
    mode: str = "batch"          # batch=각 URL 별도 물체 / multiview=한 물체 다각도
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
            raise HTTPException(400, "입력이 비어있음")
        printer = None if req.printer == "auto" else req.printer

        def mk(stype: SourceType, payload: dict) -> str:
            extras: dict = {}
            if req.addon in ("keychain", "stand", "magnet", "nfc"):
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
                         "nfc": "NFC", "keycap": "키캡"}.get(addon, addon)
                mark = "✓" if done and f"_{addon}" in rp else ("?" if done else "·")
                chips.append(f"{mark} {label}")
            if pl.get("brand_text") or pl.get("brand_icon"):
                what = pl.get("brand_text") or pl.get("brand_icon")
                mark = "✓" if done and "_brand" in rp else ("?" if done else "·")
                chips.append(f"{mark} 로고:{what}")
            if (pl.get("pause_at_pct") or 0) > 0:
                chips.append(f"· 정지{int(pl['pause_at_pct'])}%")
            return {"chips": chips}

        data_dir = Path(cfg.settings.storage.data_dir)

        def model_formats(job_id: str) -> list[str]:
            md = data_dir / "assets" / job_id / "model"
            if not md.exists():
                return []
            fmts = sorted({p.suffix.lstrip(".").lower()
                           for p in md.glob("*.*")
                           if p.suffix.lower() in
                           (".glb", ".obj", ".stl", ".fbx", ".usdz")})
            return fmts

        return {"jobs": [{
            "id": r["id"], "state": r["state"], "material": r["material"],
            "printer": r["target_printer"],
            "has_gcode": bool(r["gcode_path"]),
            "can_retry": r["state"].startswith("failed"),
            "created": r["created_at"],
            "message": msg(r),
            "options": opts_summary(r)["chips"],
            "model_formats": model_formats(r["id"]),
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

    assets_dir = Path(cfg.settings.storage.data_dir) / "assets"

    @app.get("/api/model/{job_id}/{fmt}")
    def model_file(job_id: str, fmt: str) -> FileResponse:
        fmt = fmt.lower()
        if fmt not in ("glb", "obj", "stl", "fbx", "usdz"):
            raise HTTPException(400, "지원하지 않는 포맷")
        md = assets_dir / job_id / "model"
        hits = sorted(md.glob(f"*.{fmt}")) if md.exists() else []
        if not hits:
            raise HTTPException(404, f"{fmt} 파일 없음")
        return FileResponse(hits[0], filename=f"{job_id[:8]}.{fmt}",
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
