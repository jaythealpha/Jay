#!/usr/bin/env python3
"""v2.html(한국어) → en.html(영어) 빌드 스크립트.

사용자에게 보이는 문자열을 치환 테이블로 번역해 en.html을 생성한다.
실행 후 주석을 제외한 곳에 한글이 남아 있으면 실패로 처리한다.
사용: python3 tools/build_en.py
"""
import re
import sys

SRC = "v2.html"
DST = "en.html"

R = [
    # ── 문서/DOM ──
    ("<title>직장인 러너: 출근 대작전 (16-bit)</title>",
     "<title>Office Runner: Commute Crusade (16-bit)</title>"),
    ('<html lang="ko">', '<html lang="en">'),
    ("<b>점프</b>: 스페이스/↑ (2단, 레드불 효과 중 3단) · <b>슬라이드</b>: ↓ 꾹 · <b>주말 게임</b>: ←→ · <b>P</b> 일시정지 · <b>M</b> 음소거<br>",
     "<b>Jump</b>: Space/↑ (double, triple with Red Bull) · <b>Slide</b>: hold ↓ · <b>Weekend game</b>: ←→ · <b>P</b> pause · <b>M</b> mute<br>"),
    ("하루 8시간 근무, 수입은 <b>직급별 시급</b>으로! 퇴근 전 야근 장애물에 부딪히면 <b>느려집니다</b> · <a href=\"./index.html\">📖 텍스트 버전(v1)</a>",
     "8-hour workdays, paid by <b>rank-based hourly wage</b>! Overtime obstacles before quitting time <b>slow you down</b> · <a href=\"./v2.html\">🇰🇷 한국어</a>"),
    ('<div id="btn-slide" class="touch-btn">⬇ 슬라이드</div>', '<div id="btn-slide" class="touch-btn">⬇ Slide</div>'),
    ('<div id="btn-jump" class="touch-btn">⬆ 점프</div>', '<div id="btn-jump" class="touch-btn">⬆ Jump</div>'),
    ('<button id="btn-share">📤 결과 공유</button>', '<button id="btn-share">📤 Share Result</button>'),
    ('<button id="btn-help">📖 게임 설명</button>', '<button id="btn-help">📖 How to Play</button>'),
    ('const GAME_URL = "https://jaythealpha.github.io/Jay/v2.html";',
     'const GAME_URL = "https://jaythealpha.github.io/Jay/en.html";'),
    # ── 기본 데이터 ──
    ('const DAYS = ["월", "화", "수", "목", "금"];', 'const DAYS = ["MON", "TUE", "WED", "THU", "FRI"];'),
    ('{ name: "인턴"', '{ name: "Intern"'),
    ('{ name: "사원"', '{ name: "Staff"'),
    ('{ name: "주임"', '{ name: "Sr. Staff"'),
    ('{ name: "대리"', '{ name: "Asst. Mgr"'),
    ('{ name: "과장"', '{ name: "Manager"'),
    ('{ name: "차장"', '{ name: "Deputy GM"'),
    ('{ name: "부장"', '{ name: "Gen. Mgr"'),
    ('{ name: "이사"', '{ name: "Director"'),
    ('{ name: "사장"', '{ name: "President"'),
    ('{ name: "회장"', '{ name: "Chairman"'),
    # ── 업적 ──
    ('name: "첫 출근",        desc: "기념비적인 첫 출근"', 'name: "First Day",      desc: "Your historic first commute"'),
    ('name: "칼퇴의 맛",      desc: "첫 주말 보너스 진입"', 'name: "Sweet Escape",   desc: "Reach your first weekend bonus"'),
    ('name: "카페인 중독",    desc: "누적 커피 50잔"', 'name: "Caffeine Addict", desc: "Collect 50 coffees total"'),
    ('name: "콤보 장인",      desc: "커피 콤보 x10 달성"', 'name: "Combo Artisan",  desc: "Hit a x10 coffee combo"'),
    ('name: "아찔한 인생",    desc: "한 판에 니어미스 10회"', 'name: "Living on Edge", desc: "10 near-misses in one run"'),
    ('name: "월급루팡",       desc: "한 판에 50만원 벌기"', 'name: "Salary Thief",   desc: "Earn 500,000 KRW in one run"'),
    ('name: "2주차 생존자",   desc: "2주차 월요일 도달"', 'name: "Week 2 Survivor", desc: "Reach Monday of week 2"'),
    ('name: "완벽한 주말",    desc: "주말 수익 +2만원 이상"', 'name: "Perfect Weekend", desc: "Earn 20,000+ KRW on a weekend"'),
    ('name: "퇴근 본능",      desc: "한 판에 에너지드링크 3개"', 'name: "Homing Instinct", desc: "3 energy drinks in one run"'),
    ('name: "날개를 달았다",  desc: "레드불 첫 획득"', 'name: "Gave You Wings", desc: "Grab your first Red Bull"'),
    ('name: "정시 퇴근의 꿈", desc: "야근 장애물 무피해로 하루 완주"', 'name: "On-Time Dream",  desc: "Finish a day untouched by OT obstacles"'),
    ('name: "시급 인상!",     desc: "첫 승진 달성"', 'name: "Pay Raise!",     desc: "Get your first promotion"'),
    ('name: "워커홀릭",       desc: "3주차 도달"', 'name: "Workaholic",     desc: "Reach week 3"'),
    ('name: "사장님 픽",      desc: "사장님 시찰을 무피해로 통과"', 'name: "CEO\'s Pick",     desc: "Survive a CEO inspection untouched"'),
    ('toasts.push({ txt: "🏆 업적 달성: " + a.name', 'toasts.push({ txt: "🏆 Achievement: " + a.name'),
    # ── 대사 ──
    ('dayStart: ["또 월요일이라니...", "겨우 화요일?", "수요일, 반환점!", "목요일... 거의 다 왔다", "금요일! 칼퇴 가즈아!"],',
     'dayStart: ["Monday... again...", "Only Tuesday?", "Wednesday, halfway!", "Thursday... almost there", "Friday! Freedom awaits!"],'),
    ('hit: ["죄송합니다...", "멘탈이 흔들린다", "집에 가고 싶다", "퇴사 마렵다...", "이게 회사 생활이지..."],',
     'hit: ["My apologies...", "Sanity slipping...", "I wanna go home", "Should I just quit...", "Corporate life, huh..."],'),
    ('near: ["아찔했다...", "휴, 살았다", "심장 떨어질 뻔"],',
     'near: ["That was close...", "Phew, survived", "Nearly had a heart attack"],'),
    ('rushIn: "퇴근 1시간 전... 일이 몰려온다!",', 'rushIn: "One hour till quitting time... work floods in!",'),
    ('otHit: ["야근 확정이다...", "오늘도 늦겠네...", "집은 글렀다..."],',
     'otHit: ["Overtime confirmed...", "Late again today...", "Home is a distant dream..."],'),
    ('coffee10: "카페인 수혈 완료!",', 'coffee10: "Caffeine transfusion complete!",'),
    ('pay: "월급이다!!",', 'pay: "PAYDAY!!",'),
    ('card: "...카드값 자동이체",', 'card: "...auto-pay credit card bill",'),
    ('energy: "퇴근 본능 발동!!",', 'energy: "HOMING INSTINCT ON!!",'),
    ('redbull: "날개를 달았다!!",', 'redbull: "IT GAVE ME WINGS!!",'),
    ('overtime: "야근 위기...! 버텨!!",', 'overtime: "Overtime crisis...! Hold on!!",'),
    ('escape: "칼퇴 성공!!!",', 'escape: "ESCAPED ON TIME!!!",'),
    ('monday: "다시 월요일...",', 'monday: "Monday again...",'),
    ('bonusTime: "보너스 타임! 커피가 쏟아진다!",', 'bonusTime: "Bonus time! It\'s raining coffee!",'),
    ('rush: "보고서 마감 임박!!",', 'rush: "Report deadline incoming!!",'),
    ('phoneRush: "업체 전화가 폭주한다!!",', 'phoneRush: "Vendor calls flooding in!!",'),
    ('ceo: "사장님이 보고 계신다...!",', 'ceo: "The CEO is watching...!",'),
    ('snack: "야식은 못 참지",', 'snack: "Can\'t resist a night snack",'),
    ('wkKakao: "주말에 카톡이?!",', 'wkKakao: "Work chat on a WEEKEND?!",'),
    ('wkLetter: "축의금 -10만...",', 'wkLetter: "Wedding gift money -100k...",'),
    ('wkChicken: "역시 치킨은 옳다",', 'wkChicken: "Chicken is always right",'),
    ('wkZzz: "꿀잠 충전",', 'wkZzz: "Sweet nap recharge",'),
    ('"부장님의 기에 눌려 쓰러졌다...",', '"Crushed by the boss\'s aura...",'),
    ('"카페인이 부족했다...",', '"Ran out of caffeine...",'),
    ('"멘탈이 먼저 퇴근해버렸다...",', '"My sanity clocked out first...",'),
    ('"월요병에게 패배했다...",', '"Defeated by the Monday blues...",'),
    # ── 버튼 라벨 ──
    ('btnSlide.textContent = "◀ 이동"; btnJump.textContent = "이동 ▶";',
     'btnSlide.textContent = "◀ Move"; btnJump.textContent = "Move ▶";'),
    ('btnSlide.textContent = "⬇ 슬라이드"; btnJump.textContent = "⬆ 점프";',
     'btnSlide.textContent = "⬇ Slide"; btnJump.textContent = "⬆ Jump";'),
    ('btnShare.textContent = "✅ 복사 완료!";', 'btnShare.textContent = "✅ Copied!";'),
    ('btnShare.textContent = "📤 결과 공유";', 'btnShare.textContent = "📤 Share Result";'),
    # ── 도움말 ──
    ('{ title: "🎮 기본 조작", lines: [', '{ title: "🎮 Controls", lines: ['),
    ('"⬆ 스페이스/↑ : 점프 (공중에서 한 번 더 = 2단 점프)",', '"⬆ Space/↑ : jump (press again mid-air = double jump)",'),
    ('"🪽 레드불 효과 중에는 3단 점프까지 가능",', '"🪽 Triple jump available while Red Bull wings last",'),
    ('"⬇ ↓ 꾹 : 슬라이드 — 현수막·회의 요청 아래로 통과",', '"⬇ hold ↓ : slide — pass under banners & meeting requests",'),
    ('"←→ : 주말 보너스 게임에서 좌우 이동",', '"←→ : move left/right in the weekend bonus game",'),
    ('"P : 일시정지 · M : 음소거 · H : 게임 설명",', '"P : pause · M : mute · H : how to play",'),
    ('"📱 모바일: 화면 탭 = 점프, 좌하단 버튼 = 슬라이드",', '"📱 Mobile: tap screen = jump, bottom-left button = slide",'),
    ('"    주말 게임은 화면 좌/우 터치로 이동",', '"    weekend game: touch left/right half to move",'),
    ('{ title: "☕ 아이템 & 장애물", lines: [', '{ title: "☕ Items & Obstacles", lines: ['),
    ('"☕ 커피 : +500원, 연속 획득 시 콤보 배율 상승",', '"☕ Coffee : +500 KRW, chain pickups raise the combo bonus",'),
    ('"    10잔 모으면 멘탈(하트) 1칸 회복",', '"    every 10 cups restores 1 sanity heart",'),
    ('"⚡ 에너지드링크 : 4초 무적 질주",', '"⚡ Energy drink : 4s invincible dash",'),
    ('"🪽 레드불 : 6초 날개(3단 점프) + 야근 페널티 해제",', '"🪽 Red Bull : 6s wings (triple jump) + clears OT penalty",'),
    ('"💰 보너스 봉투 : 시급 1시간치 (절반은 카드값…)",', '"💰 Bonus envelope : 1 hour of wages (half goes to card bill…)",'),
    ('"🍗 야식 치킨 : 금요일 야근 타임 한정",', '"🍗 Night chicken : Friday overtime only",'),
    ('"💥 일반 장애물(서류·의자·부장님·현수막·카톡) : 멘탈 -1",', '"💥 Normal obstacles (papers/chair/boss/banner/chat) : -1 heart",'),
    ('"🐌 야근 장애물(긴급 보고서·회의 요청·업체 전화) :",', '"🐌 OT obstacles (urgent report/meeting req/vendor call):",'),
    ('"    5초간 속도 35% 감소 + 시급 30분치 차감",', '"    35% slower for 5s + lose 30 min of wages",'),
    ('{ title: "💼 시스템", lines: [', '{ title: "💼 Systems", lines: ['),
    ('"🕐 하루 500m = 8시간 근무 (09:00 → 18:00)",', '"🕐 One day = 500m = 8 working hours (09:00 → 18:00)",'),
    ('"💰 수입 = 최저시급 10,320원 × 직급 배수",', '"💰 Income = minimum wage 10,320 KRW × rank multiplier",'),
    ('"    누적 수익으로 승진 (🐣인턴 → 👑회장, 시급 인상)",', '"    lifetime earnings promote you (🐣Intern → 👑Chairman)",'),
    ('"🌆 매일 퇴근 1시간 전 야근 러시 — 야근 장애물 등장",', '"🌆 Daily OT rush 1 hour before quitting time",'),
    ('"🌙 금요일 후반 야근 위기 타임 (화면 어두워짐)",', '"🌙 Friday late-day overtime crisis (screen darkens)",'),
    ('"🛌 금요일 돌파 시 주말 보너스 게임 + 멘탈 회복",', '"🛌 Survive Friday → weekend bonus game + heart restore",'),
    ('"😱 니어미스(아슬아슬 회피) : +300원 보너스",', '"😱 Near-miss (barely dodge) : +300 KRW bonus",'),
    ('"🎲 이벤트: 💰보너스 타임 · 📋카톡 러시 · ☎전화 폭주",', '"🎲 Events: 💰bonus time · 📋chat rush · ☎phone flood",'),
    ('"    👀사장님 시찰(10초간 점수 2배)",', '"    👀CEO inspection (2x score for 10s)",'),
    ('"🏆 업적 14종 수집 · 기록은 브라우저에 저장",', '"🏆 14 achievements · records saved in your browser",'),
    # ── 공유 텍스트 ──
    ('`🏃 직장인 러너: 출근 대작전\\n` +', '`🏃 Office Runner: Commute Crusade\\n` +'),
    ('`${r.emoji} ${r.name} 김대리(시급 ${wage.toLocaleString()}원), ${Math.floor(score).toLocaleString()}원 벌고 번아웃!\\n` +',
     '`${r.emoji} ${r.name} (wage ${wage.toLocaleString()} KRW/hr) earned ${Math.floor(score).toLocaleString()} KRW before burning out!\\n` +'),
    ('`${Math.floor(dist)}m 출근 · ☕${coffee}잔 · 니어미스 ${nearMiss}회 · 최대 콤보 x${maxCombo}\\n` +',
     '`${Math.floor(dist)}m commuted · ☕${coffee} · ${nearMiss} near-misses · best combo x${maxCombo}\\n` +'),
    ('`너도 출근해 볼래? 👉 ${GAME_URL}`;', '`Think you can survive the office? 👉 ${GAME_URL}`;'),
    ('navigator.share({ title: "직장인 러너", text })', 'navigator.share({ title: "Office Runner", text })'),
    # ── 인게임 플로팅/그리기 텍스트 ──
    ('addFloat(player.x + 8, player.y - 46, "야근 -"', 'addFloat(player.x + 8, player.y - 46, "OT -"'),
    ('"부장님: 어디야?"', '"Boss: where r u?"'),
    ('addFloat(player.x + 12, player.y - 40, "아찔! +"', 'addFloat(player.x + 12, player.y - 40, "Close! +"'),
    ('"카드값 -" + cardAmt.toLocaleString()', '"Card bill -" + cardAmt.toLocaleString()'),
    ('addFloat(it.x, it.y, "무적 질주!", "#3ee06f");', 'addFloat(it.x, it.y, "INVINCIBLE!", "#3ee06f");'),
    ('addFloat(it.x, it.y, "3단 점프!", "#4cc9f0");', 'addFloat(it.x, it.y, "Triple jump!", "#4cc9f0");'),
    ('addFloat(it.x, it.y, "야식 +"', 'addFloat(it.x, it.y, "Snack +"'),
    ('ctx.fillText("야근은 셀프", x + 237, 68);', 'ctx.fillText("UNPAID OT", x + 237, 68);'),
    ('ctx.fillText("긴급", o.x + 4, y + 10);', 'ctx.fillText("ASAP", o.x + 3, y + 10);'),
    ('ctx.fillText("회의?", o.x + 5, o.flyY + 11);', 'ctx.fillText("MTG?", o.x + 5, o.flyY + 11);'),
    ('ctx.fillText("따르릉!", o.x, GROUND - 18);', 'ctx.fillText("RING!", o.x, GROUND - 18);'),
    ('ctx.fillText("회의중", 0, 0);', 'ctx.fillText("MEETING", 0, 0);'),
    # ── HUD ──
    ('ctx.fillText(Math.floor(score).toLocaleString() + " 원", W - 10, 20);',
     'ctx.fillText(Math.floor(score).toLocaleString() + " KRW", W - 10, 20);'),
    ('ctx.fillText("시급 " + wage.toLocaleString() + "원", W - 10, 46);',
     'ctx.fillText("wage " + wage.toLocaleString() + "/hr", W - 10, 46);'),
    ('const wkTxt = week > 0 ? ` (${week + 1}주차)` : "";', 'const wkTxt = week > 0 ? ` (Week ${week + 1})` : "";'),
    ('ctx.fillText(DAYS[day] + "요일" + wkTxt, 10, 33);', 'ctx.fillText(DAYS[day] + wkTxt, 10, 33);'),
    ('ctx.fillText("콤보 x" + combo, 10, 64);', 'ctx.fillText("Combo x" + combo, 10, 64);'),
    ('ctx.fillText("🐌 야근 페널티 " + slowT.toFixed(1) + "s", 10, yExtra);', 'ctx.fillText("🐌 OT penalty " + slowT.toFixed(1) + "s", 10, yExtra);'),
    ('ctx.fillText("💰 보너스 타임 " + bonusT.toFixed(1) + "s", W / 2, 22);', 'ctx.fillText("💰 BONUS TIME " + bonusT.toFixed(1) + "s", W / 2, 22);'),
    ('ctx.fillText("👀 사장님 시찰 중 — 점수 2배! " + ceoT.toFixed(1) + "s", W / 2, 22);', 'ctx.fillText("👀 CEO INSPECTION — 2x score! " + ceoT.toFixed(1) + "s", W / 2, 22);'),
    ('ctx.fillText("⚠ 야근 위기 타임 ⚠", W / 2, 22);', 'ctx.fillText("⚠ OVERTIME CRISIS ⚠", W / 2, 22);'),
    ('ctx.fillText("🌆 퇴근 전 러시 — 야근 장애물 주의!", W / 2, 22);', 'ctx.fillText("🌆 PRE-QUITTING RUSH — beware OT obstacles!", W / 2, 22);'),
    ('const msg = day === 4 ? "금요일! 야근만 피하면 주말이다!" : (week > 0 && day === 0 ? "또 월요일..." : DAYS[day] + "요일 출근");',
     'const msg = day === 4 ? "FRIDAY! Dodge overtime, reach the weekend!" : (week > 0 && day === 0 ? "Monday... again..." : DAYS[day] + " — clock in");'),
    ('ctx.fillText("↑ 점프 (공중에서 한 번 더!)", W / 2, 143);', 'ctx.fillText("↑ Jump (press again mid-air!)", W / 2, 143);'),
    ('ctx.fillText("↓ 슬라이드", W / 2, 165);', 'ctx.fillText("↓ Slide", W / 2, 165);'),
    ('ctx.fillText((helpPage + 1) + " / " + HELP_PAGES.length + "  (← 이전)", W / 2, H - 26);',
     'ctx.fillText((helpPage + 1) + " / " + HELP_PAGES.length + "  (← prev)", W / 2, H - 26);'),
    ('ctx.fillText(helpPage < HELP_PAGES.length - 1 ? "▶ 탭 / 스페이스 : 다음 페이지" : "▶ 탭 / 스페이스 : 닫기", W / 2, H - 10);',
     'ctx.fillText(helpPage < HELP_PAGES.length - 1 ? "▶ tap / space : next page" : "▶ tap / space : close", W / 2, H - 10);'),
    # ── 주말 ──
    ('ctx.fillText("🛌 주말 보너스: 이불 밖은 위험해", W / 2, 46);', 'ctx.fillText("🛌 WEEKEND BONUS: Danger Outside the Blanket", W / 2, 46);'),
    ('ctx.fillText("치킨·꿀잠은 받고, 업무 카톡·알람·청첩장은 피하세요!", W / 2, 62);', 'ctx.fillText("Catch chicken & naps, dodge work chats, alarms & invites!", W / 2, 62);'),
    ('ctx.fillText("주말 수익 " + (wk.score >= 0 ? "+" : "") + wk.score.toLocaleString() + "원", W / 2, 100);',
     'ctx.fillText("Weekend income " + (wk.score >= 0 ? "+" : "") + wk.score.toLocaleString() + " KRW", W / 2, 100);'),
    ('ctx.fillText("칼퇴 성공! +" + wk.kal.toLocaleString() + "원", W / 2, 130);', 'ctx.fillText("ON-TIME ESCAPE! +" + wk.kal.toLocaleString() + " KRW", W / 2, 130);'),
    ('ctx.fillText("주말 보너스 스테이지!", W / 2, 156);', 'ctx.fillText("WEEKEND BONUS STAGE!", W / 2, 156);'),
    ('ctx.fillText("← → 로 움직여서 받으세요", W / 2, 176);', 'ctx.fillText("Move with ← → to catch", W / 2, 176);'),
    ('["주말 종료...", 22, "#ffd166", 110],', '["Weekend over...", 22, "#ffd166", 110],'),
    ('["주말 수익: " + (wk.score >= 0 ? "+" : "") + wk.score.toLocaleString() + "원", 14,',
     '["Weekend income: " + (wk.score >= 0 ? "+" : "") + wk.score.toLocaleString() + " KRW", 14,'),
    ('["멘탈 +1 회복! 다시 출근이다...", 12, "#c0c8e0", 164],', '["+1 heart restored! Back to work...", 12, "#c0c8e0", 164],'),
    # ── 승진 진행바 ──
    ('ctx.fillText(`${r.emoji} ${r.name}(시급 ${Math.round(MIN_WAGE * r.wage).toLocaleString()}원) → ${next.emoji} ${next.name}까지 ${(next.need - total).toLocaleString()}원`, W / 2, y);',
     'ctx.fillText(`${r.emoji} ${r.name} (${Math.round(MIN_WAGE * r.wage).toLocaleString()}/hr) → ${(next.need - total).toLocaleString()} KRW to ${next.emoji} ${next.name}`, W / 2, y);'),
    ('ctx.fillText("👑 회장 달성! 더 오를 곳이 없다", W / 2, y);', 'ctx.fillText("👑 CHAIRMAN! Nowhere higher to climb", W / 2, y);'),
    # ── 타이틀 ──
    ('["직장인 러너", 30, "#ffd166", 76],', '["OFFICE RUNNER", 30, "#ffd166", 76],'),
    ('["─ 출근 대작전 ─", 13, "#4cc9f0", 98],', '["─ Commute Crusade ─", 13, "#4cc9f0", 98],'),
    ('["하루 8시간 근무, 수입은 직급별 시급으로!", 11, "#c0c8e0", 124],', '["8-hour workdays, paid by rank-based hourly wage!", 11, "#c0c8e0", 124],'),
    ('["퇴근 전 야근 장애물(보고서·회의·전화)에 맞으면 느려짐", 11, "#c0c8e0", 141],', '["OT obstacles (reports/meetings/calls) slow you down", 11, "#c0c8e0", 141],'),
    ('["☕ 커피 콤보 · ⚡ 무적 질주 · 🪽 레드불 3단 점프", 11, "#c0c8e0", 158],', '["☕ coffee combos · ⚡ invincible dash · 🪽 Red Bull triple jump", 11, "#c0c8e0", 158],'),
    ('["금요일을 버티면 🛌 주말 보너스 게임!", 11, "#ffd166", 175],', '["Survive Friday for the 🛌 weekend bonus game!", 11, "#ffd166", 175],'),
    ('], "▶ 스페이스 / 탭하여 출근 시작");', '], "▶ space / tap to clock in");'),
    ('ctx.fillText(`${RANKS[rIdx].emoji} ${RANKS[rIdx].name} (시급 ${wageNow.toLocaleString()}원) · 누적 ${total.toLocaleString()}원 · 🏆 ${achCount}/${ACH.length}`, W / 2, 195);',
     'ctx.fillText(`${RANKS[rIdx].emoji} ${RANKS[rIdx].name} (${wageNow.toLocaleString()}/hr) · lifetime ${total.toLocaleString()} KRW · 🏆 ${achCount}/${ACH.length}`, W / 2, 195);'),
    ('ctx.fillText("최고 기록: " + Number(best).toLocaleString() + "원", W / 2, 236);',
     'ctx.fillText("Best run: " + Number(best).toLocaleString() + " KRW", W / 2, 236);'),
    # ── 게임오버 ──
    ('["🎉 승진!! 🎉", 26, "#ffd166", 78],', '["🎉 PROMOTED!! 🎉", 26, "#ffd166", 78],'),
    ('[promoRank.emoji + " " + promoRank.name + " (시급 " + Math.round(MIN_WAGE * promoRank.wage).toLocaleString() + "원)", 15, "#06d6a0", 106],',
     '[promoRank.emoji + " " + promoRank.name + " (" + Math.round(MIN_WAGE * promoRank.wage).toLocaleString() + " KRW/hr)", 15, "#06d6a0", 106],'),
    ('[Math.floor(score).toLocaleString() + "원 벌었다" + (isBest ? " ★신기록" : ""), 14, "#fff", 136],',
     '["Earned " + Math.floor(score).toLocaleString() + " KRW" + (isBest ? " ★NEW BEST" : ""), 14, "#fff", 136],'),
    ('[Math.floor(dist) + "m · ☕" + coffee + " · 아찔 " + nearMiss + "회 · 콤보 x" + maxCombo, 11, "#9aa0b5", 156],',
     '[Math.floor(dist) + "m · ☕" + coffee + " · close " + nearMiss + " · combo x" + maxCombo, 11, "#9aa0b5", 156],'),
    ('], "▶ 스페이스 / 탭하여 재출근");', '], "▶ space / tap to clock in again");'),
    ('["번아웃!", 30, "#e94560", 74],', '["BURNOUT!", 30, "#e94560", 74],'),
    ('[Math.floor(score).toLocaleString() + "원 벌었다" + (isBest ? " ★신기록!" : ""), 18, "#06d6a0", 128],',
     '["Earned " + Math.floor(score).toLocaleString() + " KRW" + (isBest ? " ★NEW BEST!" : ""), 18, "#06d6a0", 128],'),
    ('[Math.floor(dist) + "m 출근 · ☕" + coffee + "잔 · 아찔 " + nearMiss + "회 · 콤보 x" + maxCombo + " · " + (week + 1) + "주차", 10, "#9aa0b5", 148],',
     '[Math.floor(dist) + "m · ☕" + coffee + " · close " + nearMiss + " · combo x" + maxCombo + " · week " + (week + 1), 10, "#9aa0b5", 148],'),
    ('drawCenterPanel([["일시정지", 24, "#ffd166", 130], ["(몰래 쉬는 중)", 12, "#9aa0b5", 152]], "P 키로 복귀");',
     'drawCenterPanel([["PAUSED", 24, "#ffd166", 130], ["(secretly resting)", 12, "#9aa0b5", 152]], "press P to resume");'),
]


def strip_comments(js: str) -> str:
    js = re.sub(r"/\*[\s\S]*?\*/", "", js)
    js = re.sub(r"//[^\n]*", "", js)
    return js


def main():
    src = open(SRC, encoding="utf-8").read()
    out = src
    missed = []
    for ko, en in R:
        if ko not in out:
            missed.append(ko[:60])
            continue
        out = out.replace(ko, en)
    if missed:
        print("⚠ 원본에서 찾지 못한 치환 키 %d개:" % len(missed))
        for m in missed:
            print("  -", m)
        sys.exit(1)
    open(DST, "w", encoding="utf-8").write(out)
    residual = [
        (i + 1, ln.strip()[:70])
        for i, ln in enumerate(strip_comments(out).splitlines())
        if re.search(r"[가-힣]", ln) and "한국어" not in ln
    ]
    if residual:
        print("⚠ 번역 누락 %d줄:" % len(residual))
        for n, ln in residual[:30]:
            print(f"  {n}: {ln}")
        sys.exit(1)
    print(f"✅ {DST} 생성 완료 — 치환 {len(R)}건, 잔여 한글 없음")


if __name__ == "__main__":
    main()
