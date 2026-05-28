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

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
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
 .b{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;
   border-radius:99px;background:#eef0f2;color:#374151;white-space:nowrap;
   margin:1px 3px 1px 0}
 .b.ok{background:#dcfce7;color:#15803d}
 .b.no{background:#fee2e2;color:#b91c1c}
 .b.go{background:#fef9c3;color:#854d0e}
 .b.coin{background:#fef3c7;color:#92400e}
 .jid{font-family:ui-monospace,Menlo,monospace;font-size:12px;
   display:flex;align-items:center;gap:6px}
 .prog{max-width:300px;color:var(--mut);font-size:12px;overflow:hidden;
   text-overflow:ellipsis;white-space:nowrap;margin:2px 0}
 .thumb{width:40px;height:40px;object-fit:cover;border-radius:8px;
   background:#eee}
 td{vertical-align:middle}
 .dlcell a{font-size:12px} .sep{color:#d1d5db;margin:0 5px}
 .acts{white-space:nowrap} .acts a{font-size:15px;margin-left:8px}
 a{color:#1d4ed8;text-decoration:none;font-weight:600}
 a:hover{text-decoration:underline}
 .empty{color:var(--mut);text-align:center;padding:28px 0;font-size:13px}
</style></head><body>
<h1>Bambu Auto <span id="ver" style="font-size:11px;font-weight:400;color:#9ca3af"></span></h1>
<p class="sub">이미지/텍스트 → 3D 모델 또는 기능 제품(마그넷·NFC·키링) · 본인 Meshy 키</p>

<div class="card" style="padding:12px 18px">
  <label class="fld">내 Meshy API 키 (이 브라우저에만 저장 · 서버 미저장)</label>
  <div class="row" style="display:flex;gap:8px">
    <input id="key" type="password" placeholder="msy_..."
      style="flex:1;padding:8px 11px;border:1px solid #d1d5db;border-radius:8px"
      oninput="saveKey()">
    <button type="button" onclick="checkBal()" style="background:#374151;padding:9px 14px">잔액 확인</button>
  </div>
  <div id="keyMsg" class="msg" style="margin-top:6px">키는 브라우저 localStorage + 처리 중 메모리에만 사용.</div>
</div>

<div class="seg" style="margin-bottom:4px">
  <button id="t3d" class="on" onclick="setTrack('3d')">① 3D 모델 (Meshy)</button>
  <button id="tfn" onclick="setTrack('func')">② 기능 제품 (마그넷·NFC·키링)</button>
</div>

<div id="form3d" class="card">
  <div class="seg">
    <button id="mBatch" class="on" onclick="setMode('batch')">이미지 (배치)</button>
    <button id="mView" onclick="setMode('multiview')">한 물체·여러 각도</button>
    <button id="mText" onclick="setMode('text')">텍스트 → 3D</button>
  </div>
  <label class="fld" id="hint">한 줄에 이미지 URL 1개 = 물체 1개.</label>
  <textarea id="src" rows="4" placeholder="https://.../productA.jpg (이미지 직접 URL)"></textarea>
  <div class="opts" style="margin-top:6px">
    <label class="msg">또는 파일 첨부:
      <input type="file" accept="image/*" multiple
        onchange="upFiles(this,'up3d','up3dMsg')"></label>
    <span id="up3dMsg" class="msg"></span>
  </div>
  <div class="grid">
    <div><label class="fld">재질</label>
      <select id="mat"><option value="pla">PLA</option><option value="petg">PETG</option>
        <option value="abs">ABS</option><option value="silk">PLA Silk</option></select></div>
    <div><label class="fld">프린터</label>
      <select id="prn"><option value="auto">자동 (기본 A1)</option></select></div>
    <div><label class="fld">3D 추가</label>
      <select id="addon">
        <option value="">없음</option>
        <option value="stand">받침대</option>
        <option value="keychain">열쇠고리(3D 입체고리)</option>
        <option value="keycap">키캡 (기계식 키보드 MX)</option>
      </select>
      <span id="addonHint" class="msg" style="display:none">색 키캡은 '텍스처(컬러)' 필요 — 자동 켜짐</span></div>
  </div>
  <div class="opts" style="margin-top:10px">
    <label><input id="bg" type="checkbox" checked> 배경·인물 제거</label>
    <label><input id="tex" type="checkbox"> 텍스처(컬러)</label>
    <label title="끄면 생성만 — 크레딧 절약(약 절반)"><input id="rem" type="checkbox" checked> 리메시</label>
    <label>정밀도: <select id="prec" style="width:auto">
      <option value="standard">표준</option><option value="high">고정밀</option></select></label>
  </div>
  <div class="opts" style="margin-top:8px">
    <label>바닥 로고:
      <select id="brandType" onchange="onBrandChange()" style="width:auto">
        <option value="">없음</option><option value="text">텍스트</option><option value="icon">아이콘</option></select></label>
    <input id="brandText" type="text" placeholder="예: YOGIBO" style="flex:1;min-width:120px;padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;display:none">
    <select id="brandIcon" style="display:none;width:auto"><option value="wifi">Wi-Fi</option><option value="nfc">NFC</option>
      <option value="phone">전화</option><option value="mobile">휴대폰</option><option value="email">이메일</option><option value="bluetooth">블루투스</option></select>
  </div>
  <div class="bar">
    <span id="msg3d" class="msg"></span>
    <button id="go3d" onclick="submit3d()">3D 제작 시작</button>
  </div>
</div>

<div id="formFunc" class="card" style="display:none">
  <p class="msg" style="margin:0 0 10px">이미지를 <b>평면 제품</b>으로 — Meshy 미사용·<b>크레딧 0</b>. 한 줄에 1개(배치).</p>
  <textarea id="fsrc" rows="4" placeholder="https://.../character.png (이미지 직접 URL)"></textarea>
  <div class="opts" style="margin-top:6px">
    <label class="msg">또는 파일 첨부:
      <input type="file" accept="image/*" multiple
        onchange="upFiles(this,'upFn','upFnMsg')"></label>
    <span id="upFnMsg" class="msg"></span>
  </div>
  <div class="grid">
    <div><label class="fld">제품</label>
      <select id="product" onchange="onProductChange()">
        <option value="magnet">마그넷 (자석 공동)</option>
        <option value="nfc">NFC 태그 (27mm 공동)</option>
        <option value="keyring">키링 (구멍)</option>
      </select></div>
    <div id="fmagWrap"><label class="fld">자석 크기 (D×H)</label>
      <select id="fmagsize"><option value="4x2">4×2</option><option value="4x3">4×3</option>
        <option value="5x2" selected>5×2</option><option value="5x3">5×3</option>
        <option value="6x2">6×2</option><option value="6x3">6×3</option><option value="8x2">8×2</option><option value="10x2">10×2</option></select></div>
    <div><label class="fld">프린터</label><select id="fprn"><option value="auto">자동 (기본 A1)</option></select></div>
  </div>
  <div class="opts" style="margin-top:10px">
    <label>크기(mm) <input id="fsize" type="number" min="20" max="120" step="1" value="50" style="width:64px;padding:6px;border:1px solid #d1d5db;border-radius:6px"></label>
    <label>두께(mm) <input id="fth" type="number" min="1.5" max="10" step="0.5" value="3.5" style="width:64px;padding:6px;border:1px solid #d1d5db;border-radius:6px"></label>
    <label>재질 <select id="fmat" style="width:auto"><option value="pla">PLA</option><option value="petg">PETG</option><option value="silk">PLA Silk</option></select></label>
    <label><input id="fbg" type="checkbox" checked> 배경·인물 제거</label>
  </div>
  <div class="bar">
    <span id="msgFn" class="msg"></span>
    <button id="goFn" onclick="submitFunc()">기능 제품 제작 (크레딧 0)</button>
  </div>
</div>
<div id="cred" class="msg" style="margin:0 4px 14px"></div>

<div class="card">
  <div class="bar" style="margin:0 0 12px">
    <strong style="font-size:14px">제작 현황</strong>
    <span>
      <button id="bulk" onclick="bulkDelete()" disabled style="background:#b91c1c;padding:7px 14px;font-size:13px;margin-right:8px">선택 삭제</button>
      <a href="/api/download-all" style="font-size:13px">⬇ 완료분 전체 ZIP</a>
    </span>
  </div>
  <table><thead><tr>
    <th style="width:24px"><input type="checkbox" id="all" onclick="toggleAll(this)"></th>
    <th style="width:44px"></th><th>작업</th><th>옵션 · 크레딧</th>
    <th>다운로드</th><th style="width:90px">관리</th>
  </tr></thead><tbody id="tb"></tbody></table>
  <div id="empty" class="empty" style="display:none">아직 작업이 없습니다.</div>
</div>

<script>
let MODE='batch', TRACK='3d';
function setTrack(t){TRACK=t;
 document.getElementById('t3d').className=t==='3d'?'on':'';
 document.getElementById('tfn').className=t==='func'?'on':'';
 document.getElementById('form3d').style.display=t==='3d'?'block':'none';
 document.getElementById('formFunc').style.display=t==='func'?'block':'none';refresh();}
function setMode(m){MODE=m;
 document.getElementById('mBatch').className=m==='batch'?'on':'';
 document.getElementById('mView').className=m==='multiview'?'on':'';
 document.getElementById('mText').className=m==='text'?'on':'';
 const h={batch:'한 줄에 이미지 URL 1개 = 물체 1개.',
  multiview:'같은 물체 2~4장 → 정밀 3D 1개.',
  text:'한 줄에 설명 1개. 예: 요기보 캐릭터 피규어'};
 document.getElementById('hint').textContent=h[m];
 document.getElementById('src').placeholder=m==='text'?'요기보 캐릭터 피규어':'https://.../productA.jpg';}
function onBrandChange(){const t=document.getElementById('brandType').value;
 document.getElementById('brandText').style.display=t==='text'?'block':'none';
 document.getElementById('brandIcon').style.display=t==='icon'?'inline-block':'none';}
function onProductChange(){
 document.getElementById('fmagWrap').style.display=
  document.getElementById('product').value==='magnet'?'block':'none';}
async function loadPrinters(){try{const p=await (await fetch('/api/printers')).json();
 for(const id of ['prn','fprn']){const s=document.getElementById(id);
  for(const n of p.printers){const o=document.createElement('option');o.value=n;o.textContent=n.toUpperCase();s.appendChild(o);}
  if([...s.options].some(o=>o.value==='a1'))s.value='a1';}}catch(e){}}
function keyHdr(){const k=document.getElementById('key').value.trim();return k?{'X-Meshy-Key':k}:{};}
function saveKey(){localStorage.setItem('meshy_key',document.getElementById('key').value.trim());}
async function checkBal(){const c=await (await fetch('/api/credits',{headers:keyHdr()})).json();
 document.getElementById('keyMsg').textContent=(c.meshy_balance==null)?'잔액 조회 실패 — 키 확인':('현재 잔액: '+c.meshy_balance);}
async function post(body,msgEl,btn){btn.disabled=true;msgEl.textContent='제출 중…';
 try{const r=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();msgEl.textContent=r.ok?(j.count+'개 대기열 등록'):('오류: '+(j.detail||r.status));
 }catch(e){msgEl.textContent='오류: '+e;}btn.disabled=false;refresh();}
function srcs(id){return document.getElementById(id).value.split(/\n/).map(s=>s.trim()).filter(Boolean);}
const UP={up3d:[],upFn:[]};
async function upFiles(input,store,msgId){
 const fs=input.files;if(!fs.length)return;
 document.getElementById(msgId).textContent='업로드 중…';
 const fd=new FormData();for(const f of fs)fd.append('files',f);
 try{const r=await fetch('/api/upload',{method:'POST',body:fd});
  const j=await r.json();UP[store]=(UP[store]||[]).concat(j.paths||[]);
  document.getElementById(msgId).textContent=UP[store].length+'개 첨부됨';
 }catch(e){document.getElementById(msgId).textContent='업로드 실패: '+e;}}
document.getElementById('addon').addEventListener('change',function(){
 const kc=this.value==='keycap';
 document.getElementById('addonHint').style.display=kc?'inline':'none';
 if(kc)document.getElementById('tex').checked=true;});
async function submit3d(){const s=srcs('src').concat(UP.up3d);
 if(!s.length){alert('URL 입력 또는 파일 첨부');return;}
 if(MODE==='multiview'&&s.length>4){alert('멀티뷰 최대 4장');return;}
 if(s.length>20){alert('최대 20개');return;}
 await post({track:'3d',sources:s,mode:MODE,
  material:document.getElementById('mat').value,printer:document.getElementById('prn').value,
  addon:document.getElementById('addon').value,
  texture:document.getElementById('tex').checked,remesh:document.getElementById('rem').checked,
  precision:document.getElementById('prec').value,remove_bg:document.getElementById('bg').checked,
  brand_type:document.getElementById('brandType').value,brand_text:document.getElementById('brandText').value,
  brand_icon:document.getElementById('brandIcon').value,
  meshy_key:document.getElementById('key').value.trim()},
  document.getElementById('msg3d'),document.getElementById('go3d'));
 UP.up3d=[];document.getElementById('up3dMsg').textContent='';}
async function submitFunc(){const s=srcs('fsrc').concat(UP.upFn);
 if(!s.length){alert('URL 입력 또는 파일 첨부');return;}
 if(s.length>20){alert('최대 20개');return;}
 await post({track:'func',sources:s,mode:'batch',product:document.getElementById('product').value,
  magnet_size:document.getElementById('fmagsize').value,
  flat_size_mm:parseFloat(document.getElementById('fsize').value)||50,
  flat_thickness_mm:parseFloat(document.getElementById('fth').value)||3.5,
  material:document.getElementById('fmat').value,printer:document.getElementById('fprn').value,
  remove_bg:document.getElementById('fbg').checked},
  document.getElementById('msgFn'),document.getElementById('goFn'));
 UP.upFn=[];document.getElementById('upFnMsg').textContent='';}
function badge(s){let c='b';if(s==='sliced'||s==='done')c+=' ok';
 else if(s.startsWith('failed'))c+=' no';else if(s!=='new')c+=' go';
 const t=s==='sliced'?'완료':s==='new'?'대기':s;return '<span class="'+c+'">'+t+'</span>';}
const SEL=new Set();
function onSel(cb){cb.checked?SEL.add(cb.dataset.id):SEL.delete(cb.dataset.id);syncBulk();}
function toggleAll(cb){document.querySelectorAll('.sel').forEach(x=>{x.checked=cb.checked;
 x.checked?SEL.add(x.dataset.id):SEL.delete(x.dataset.id);});syncBulk();}
function syncBulk(){const n=SEL.size;const b=document.getElementById('bulk');
 b.disabled=!n;b.textContent=n?('선택 삭제 ('+n+')'):'선택 삭제';}
async function bulkDelete(){const ids=[...SEL];if(!ids.length)return;
 if(!confirm(ids.length+'개 삭제할까요?'))return;
 await fetch('/api/jobs/bulk-delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids})});
 SEL.clear();document.getElementById('all').checked=false;refresh();}
async function refresh(){const j=await (await fetch('/api/jobs')).json();
 const tb=document.getElementById('tb');tb.innerHTML='';
 const rows=j.jobs.filter(x=>(x.track||'3d')===TRACK);
 document.getElementById('empty').style.display=rows.length?'none':'block';
 for(const x of rows){
  const links=[];
  if(x.bambu3mf)links.push('<a href="/api/bambu3mf/'+x.id+'" title="Bambu/Orca Studio에서 열면 색마다 필라멘트(익스트루더)가 배정됨 → AMS에 팔레트 색 끼우고 바로 출력" style="background:#16a34a;color:#fff;padding:2px 7px;border-radius:5px;font-weight:600">🎨 Bambu 멀티컬러 3MF</a>');
  if(x.color3mf)links.push('<a href="/api/color3mf/'+x.id+'" title="미리보기용 컬러 3MF(필라멘트 미배정)" style="background:#dcfce7;color:#15803d;padding:2px 7px;border-radius:5px">컬러 3MF(미리보기)</a>');
  if(x.has_gcode)links.push('<a href="/api/download/'+x.id+'">3MF(단색)</a>');
  for(const f of (x.model_formats||[]))links.push('<a href="/api/model/'+x.id+'/'+f+'">'+f+'</a>');
  for(let i=1;i<=(x.color_parts||0);i++)links.push('<a href="/api/colorpart/'+x.id+'/'+i+'" title="색상 파트 '+i+'">C'+i+'</a>');
  let dl=links.length?links.join('<span class="sep">·</span>'):'<span class="msg">—</span>';
  if((x.palette||[]).length){const sw=x.palette.map(c=>'<span style="display:inline-block;width:11px;height:11px;border-radius:2px;border:1px solid #ccc;background:'+c+'"></span>').join(' ');
   dl+='<div style="margin-top:3px">'+sw+'</div>';}
  const m=(x.message||'').replace(/"/g,'&quot;');
  const th='<img src="/api/thumb/'+x.id+'" class="thumb" onerror="this.style.visibility=\'hidden\'">';
  const ck=SEL.has(x.id)?' checked':'';
  const job='<div class="jid">'+x.id.slice(0,8)+' '+badge(x.state)+'</div>'+
   '<div class="prog" title="'+m+'">'+m+'</div>'+
   '<div class="msg">'+x.material+' · '+(x.printer||'auto')+' · '+x.created.slice(5,16).replace('T',' ')+'</div>';
  const cr=x.credits>0?'<span class="b coin" title="'+(x.credits_actual?'실측':'견적')+'">🪙'+x.credits+(x.credits_actual?'':'~')+'</span>':'';
  const op=(cr+(x.options||[]).map(s=>'<span class="b">'+s+'</span>').join(''))||'<span class="msg">—</span>';
  const rt=x.can_retry?'<a href="#" title="재시도" onclick="retry(\''+x.id+'\');return false">↻</a>':'';
  const sh=x.has_gcode?'<a href="#" title="공유" onclick="share(\''+x.id+'\');return false">🔗</a>':'';
  const tx=(TRACK==='3d'&&x.state==='sliced')?'<a href="#" title="텍스처 입히기" onclick="retexture(\''+x.id+'\');return false">🎨</a>':'';
  const tr=document.createElement('tr');
  tr.innerHTML='<td><input type="checkbox" class="sel" data-id="'+x.id+'"'+ck+' onclick="onSel(this)"></td>'+
   '<td>'+th+'</td><td>'+job+'</td><td>'+op+'</td><td class="dlcell">'+dl+'</td>'+
   '<td class="acts">'+tx+rt+sh+'<a href="#" title="삭제" onclick="del(\''+x.id+'\');return false">🗑</a></td>';
  tb.appendChild(tr);}
 syncBulk();
 const c=await (await fetch('/api/credits',{headers:keyHdr()})).json();
 const bal=(c.meshy_balance==null)?'키 입력 후 잔액 확인':c.meshy_balance.toLocaleString();
 document.getElementById('cred').innerHTML='<b>Meshy 잔액 '+bal+'</b> · 월 견적 '+c.monthly_used+'/'+c.monthly_cap;}
function share(id){const u=location.origin+'/share/'+id;
 navigator.clipboard.writeText(u).then(()=>alert('공유 링크 복사됨:\n'+u),()=>prompt('공유 링크:',u));}
async function retry(id){await fetch('/api/jobs/'+id+'/retry',{method:'POST'});refresh();}
async function retexture(id){
 const p=prompt('텍스처 설명 (예: 광택 파스텔 컬러, 만화풍):');
 if(!p)return;
 const h=Object.assign({'Content-Type':'application/json'},keyHdr());
 const r=await fetch('/api/jobs/'+id+'/retexture',{method:'POST',headers:h,body:JSON.stringify({prompt:p})});
 const j=await r.json();
 if(!r.ok)alert('오류: '+(j.detail||r.status));refresh();}
async function del(id){if(!confirm('삭제할까요?'))return;await fetch('/api/jobs/'+id,{method:'DELETE'});SEL.delete(id);refresh();}
document.getElementById('key').value=localStorage.getItem('meshy_key')||'';
fetch('/api/config').then(r=>r.json()).then(c=>{if(c.byo_required)
 document.getElementById('keyMsg').textContent='⚠ 본인 Meshy 키 입력 필수 (외부 배포 모드)';});
fetch('/api/version').then(r=>r.json()).then(v=>{
 document.getElementById('ver').textContent='build '+(v.version||'?')+' · '+(v.started||'');});
loadPrinters();refresh();setInterval(refresh,3000);onProductChange();
</script></body></html>"""


class BulkIds(BaseModel):
    ids: list[str]


class RetextureReq(BaseModel):
    prompt: str


class SubmitReq(BaseModel):
    sources: list[str]
    track: str = "3d"            # 3d=Meshy 3D / func=기능 제품(평면)
    product: str = "magnet"      # func일 때: magnet | nfc | keyring
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
    texture: bool = False        # 컬러/PBR 텍스처 생성 (크레딧↑)
    precision: str = "standard"  # standard | high (target_polycount)
    remesh: bool = True          # 리메시(토폴로지 정리). 끄면 크레딧 절약(생성만)
    flat: bool = False           # 2D 평면 패널 모드 (Meshy 미사용·크레딧 0)
    flat_size_mm: float = 50.0
    flat_thickness_mm: float = 3.5
    remove_bg: bool = False
    meshy_key: str = ""          # BYO: 사용자 Meshy 키 (미입력 시 서버 .env)


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

    @app.get("/api/config")
    def webconfig() -> dict:
        return {"byo_required": cfg.settings.web.byo_required}

    # 실행 중인 서버의 코드 버전 — 화면 헤더에 표시해 'git pull 후 미재시작'을
    # 즉시 식별. 표시 SHA != `git rev-parse --short HEAD` 면 서버가 옛 코드.
    import datetime
    import subprocess

    def _git_sha() -> str:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).resolve().parent, capture_output=True,
                text=True, timeout=2)
            return out.stdout.strip() or "unknown"
        except Exception:  # noqa: BLE001
            return "unknown"

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
        srcs = [s.strip() for s in req.sources if s.strip()]
        if not srcs:
            raise HTTPException(400, "입력이 비어있음")
        printer = None if req.printer == "auto" else req.printer

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
            if req.flat:
                extras["flat"] = True
                extras["flat_size_mm"] = float(req.flat_size_mm)
                extras["flat_thickness_mm"] = float(req.flat_thickness_mm)
            if req.addon in ("keychain", "stand", "magnet", "nfc", "keycap", "keyring"):
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

    assets_dir = Path(cfg.settings.storage.data_dir) / "assets"

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
