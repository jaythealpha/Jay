#!/usr/bin/env python3
"""인사팀장 미팅용 PDF 생성"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

FONT_DIR = "/usr/share/fonts/truetype/nanum"
pdfmetrics.registerFont(TTFont("Nanum", f"{FONT_DIR}/NanumGothic.ttf"))
pdfmetrics.registerFont(TTFont("NanumB", f"{FONT_DIR}/NanumGothicBold.ttf"))

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="NanumB",
                    fontSize=18, leading=24, spaceAfter=10, textColor=colors.HexColor("#1F3A5F"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="NanumB",
                    fontSize=14, leading=20, spaceBefore=12, spaceAfter=8,
                    textColor=colors.HexColor("#1F3A5F"))
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="NanumB",
                    fontSize=12, leading=16, spaceBefore=8, spaceAfter=4,
                    textColor=colors.HexColor("#2E5C8A"))
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Nanum",
                      fontSize=10, leading=15, spaceAfter=4)
BODY_S = ParagraphStyle("BodyS", parent=BODY, fontSize=9, leading=13)
CALL = ParagraphStyle("Call", parent=BODY, fontName="NanumB",
                      backColor=colors.HexColor("#FFF8E1"),
                      borderColor=colors.HexColor("#FBC02D"),
                      borderWidth=1, borderPadding=6, leftIndent=0, rightIndent=0)
COVER_T = ParagraphStyle("CoverT", parent=H1, fontSize=24, leading=32, alignment=TA_CENTER)
COVER_S = ParagraphStyle("CoverS", parent=BODY, fontSize=12, alignment=TA_CENTER)


def p(text, style=BODY):
    return Paragraph(text.replace("\n", "<br/>"), style)


def make_table(data, col_widths=None, header=True, font_size=9):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    base = [
        ("FONTNAME", (0, 0), (-1, -1), "Nanum"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        base += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "NanumB"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ]
    t.setStyle(TableStyle(base))
    return t


def cell(text):
    return Paragraph(text, BODY_S)


story = []

# ───────────────── COVER ─────────────────
story.append(Spacer(1, 60 * mm))
story.append(p("팀 업무 프로세스 개선안", COVER_T))
story.append(Spacer(1, 8 * mm))
story.append(p("팀장 부재 · 주니어 중심 조직을 위한 운영체계 설계", COVER_S))
story.append(Spacer(1, 40 * mm))
cover_info = [
    ["문서명", "팀 업무 프로세스 개선안 및 조직 운영 진단"],
    ["수신", "인사팀장"],
    ["목적", "업무 가시화 · 업무량 객관화 · 책임 분산 체계 도입 협의"],
    ["작성일", "2026-05-11"],
    ["페이지", "본 문서 14p + 양식세트(엑셀) 별첨"],
]
t = Table(cover_info, colWidths=[35 * mm, 110 * mm])
t.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "Nanum"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("FONTNAME", (0, 0), (0, -1), "NanumB"),
    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0F4F8")),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(t)
story.append(PageBreak())

# ───────────────── 1. 배경 / 문제 정의 ─────────────────
story.append(p("1. 배경 및 문제 정의", H1))
story.append(p(
    "현재 조직은 팀장 부재 상태에서 경력이 짧은 직원들이 다수를 차지하고 있어, "
    "다음과 같은 구조적 문제가 반복적으로 발생하고 있습니다.", BODY))

problem_tbl = [
    ["구분", "현상", "근본 원인"],
    [cell("가시성"), cell("누가 어떤 업무를 진행 중인지 파악 어려움"), cell("업무가 구두/메신저로 분산 지시되며 단일 저장소 부재")],
    [cell("효율성"), cell("같은 업무에 소요되는 시간이 사람마다 다르고 측정 불가"), cell("표준 소요시간(공수) 기준 미정의")],
    [cell("형평성"), cell("업무가 늘면 즉시 \"일이 많다\" 불평이 발생"), cell("개인별 업무량을 객관적으로 비교할 데이터 없음")],
    [cell("책임성"), cell("업무가 미뤄지거나 마감을 놓침"), cell("우선순위·마감을 공식적으로 합의하는 절차 없음")],
    [cell("권한"), cell("판단이 필요한 순간 의사결정자가 없음"), cell("팀장 부재 + 권한 위임 룰 미정")],
]
story.append(make_table(problem_tbl, col_widths=[20 * mm, 65 * mm, 80 * mm]))
story.append(Spacer(1, 6))
story.append(p(
    "<b>본 문서의 목적:</b> 팀장(사람) 대신 시스템이 통제하도록 5가지 운영 메커니즘을 설계하고, "
    "노동법 준수 범위 내에서 즉시 적용 가능한 프로세스와 양식을 제시합니다.", CALL))

# ───────────────── 2. 개선 원칙 ─────────────────
story.append(p("2. 개선 원칙 — 5가지 운영 메커니즘", H1))
mech_tbl = [
    ["No.", "메커니즘", "대체하는 팀장 기능", "산출물"],
    [cell("①"), cell("업무 보드(가시화)"), cell("업무 현황 파악"), cell("통합 업무 보드 / 일일 업데이트")],
    [cell("②"), cell("데일리 스탠드업(싱크)"), cell("진행 점검·코칭"), cell("15분 정례 회의 / 회의록")],
    [cell("③"), cell("표준 공수표 + 80% 룰(객관화)"), cell("업무량 분배 판단"), cell("업무 분류표 / 가용 시간 산식")],
    [cell("④"), cell("역할 로테이션(분산)"), cell("코디네이션·외부 창구"), cell("4개 역할 순환 매트릭스")],
    [cell("⑤"), cell("우선순위 룰(판단)"), cell("우선순위·거절 결정"), cell("P1~P4 분류 기준 / 요청서 양식")],
]
story.append(make_table(mech_tbl, col_widths=[12 * mm, 45 * mm, 45 * mm, 63 * mm]))

# ───────────────── 3. 세부 프로세스 ─────────────────
story.append(PageBreak())
story.append(p("3. 세부 업무 프로세스", H1))

story.append(p("3.1 업무 등록 프로세스 (모든 업무의 진입점)", H2))
flow1 = [
    ["단계", "행위자", "행동", "사용 양식"],
    [cell("1"), cell("요청자"), cell("업무 요청서 작성 (P등급·기대 산출물·희망 마감 명시)"), cell("[양식 A] 업무 요청서")],
    [cell("2"), cell("업무조정자"), cell("요청 접수 → 담당자 적합도·가용시간 확인"), cell("[양식 B] 통합 업무 보드")],
    [cell("3"), cell("담당자"), cell("예상 소요시간 산정 → 보드에 등록 → 마감일 합의"), cell("[양식 B] 통합 업무 보드")],
    [cell("4"), cell("담당자"), cell("일일 진행 상태 업데이트 (시작 전/진행 중/완료/보류)"), cell("[양식 B] 통합 업무 보드")],
    [cell("5"), cell("요청자"), cell("완료 확인 및 산출물 수령 → 보드 상태 \"종료\" 처리"), cell("[양식 B] 통합 업무 보드")],
]
story.append(make_table(flow1, col_widths=[12 * mm, 30 * mm, 78 * mm, 45 * mm]))
story.append(p(
    "원칙: <b>보드에 등록되지 않은 업무는 \"존재하지 않는 업무\"로 간주.</b> "
    "구두·메신저 지시도 수령자가 직접 등록하여 가시화한다.", CALL))

story.append(p("3.2 데일리 스탠드업 운영", H2))
flow2 = [
    ["항목", "내용"],
    [cell("시간"), cell("매일 업무 시작 직후 15분 (예: 09:00~09:15)")],
    [cell("형식"), cell("기립 또는 영상회의 / 토론 금지, 공유만")],
    [cell("진행자"), cell("주간 로테이션 (퍼실리테이터 역할)")],
    [cell("발표 내용"), cell("① 어제 한 일  ② 오늘 할 일  ③ 막힌 점 / 도움 필요")],
    [cell("기록"), cell("스크라이브가 회의록 작성 → 보드에 첨부 [양식 C]")],
    [cell("후속"), cell("막힌 이슈는 스탠드업 종료 후 관련자만 별도 30분 이내 해결")],
]
story.append(make_table(flow2, col_widths=[30 * mm, 135 * mm]))

story.append(p("3.3 업무량 객관화 (80% 룰)", H2))
story.append(p(
    "<b>가용 시간 산식</b>: 주 40h × 80% = <b>32h</b>가 신규 업무 배정 가능 상한. "
    "나머지 8h(20%)는 돌발 업무·회의·휴게·이동을 위한 버퍼.", BODY))
flow3 = [
    ["단계", "행동"],
    [cell("1"), cell("[양식 D] 표준 업무 공수표에서 해당 업무의 단위 시간 조회")],
    [cell("2"), cell("담당자의 이번 주 누적 예상 시간 = 기존 등록분 + 신규 업무")],
    [cell("3"), cell("32h 초과 시 → 자동 \"보류\" 표시 + 재분배 또는 마감 연기 협의")],
    [cell("4"), cell("초과 합의 시 연장근로 → 사전 동의서 + 1.5배 가산 수당 지급 절차")],
]
story.append(make_table(flow3, col_widths=[12 * mm, 153 * mm]))

story.append(PageBreak())
story.append(p("3.4 역할 로테이션 매트릭스", H2))
flow4 = [
    ["역할", "책임 범위", "임기"],
    [cell("업무조정자 (Coordinator)"), cell("신규 업무 접수·배정, 보드 정합성 점검, 80% 룰 모니터링"), cell("2주 ~ 1개월")],
    [cell("진행자 (Facilitator)"), cell("데일리/위클리 회의 진행, 시간 관리"), cell("1주")],
    [cell("기록자 (Scribe)"), cell("회의록 작성, 결정사항 보드 반영"), cell("1주")],
    [cell("외부 창구 (Liaison)"), cell("타 부서·상위 보고 단일 채널, 외부 요청 1차 수신"), cell("1개월")],
]
story.append(make_table(flow4, col_widths=[45 * mm, 90 * mm, 30 * mm]))
story.append(p(
    "운영 효과: 주니어들의 리더십 실습 + 권한 집중 방지 + 백업 인력 자연 양성. "
    "[양식 E] 역할 로테이션 표에 분기 단위로 사전 공시.", BODY))

story.append(p("3.5 우선순위 판정 룰", H2))
prio_tbl = [
    ["P등급", "기준", "처리 원칙"],
    [cell("P1"), cell("24시간 내 마감 + 외부/상위 요청 + 중단 시 영업·법적 리스크"), cell("최우선, 진행 중 업무 일시 보류 가능")],
    [cell("P2"), cell("1주 내 마감 또는 정기 업무"), cell("일반 일정 내 처리")],
    [cell("P3"), cell("개선·기획·학습성 업무"), cell("여유 시간에 처리, 마감 유연")],
    [cell("P4"), cell("필수성 낮음, 자동화·위임·거절 검토 대상"), cell("월 1회 일괄 검토")],
]
story.append(make_table(prio_tbl, col_widths=[15 * mm, 80 * mm, 70 * mm]))
story.append(p(
    "요청자는 [양식 A]에 본인이 판단한 P등급을 표기. "
    "P등급 충돌 시 업무조정자가 룰북에 따라 재판정, 최종 미합의 시 경영지원팀장 에스컬레이션.", BODY))

story.append(p("3.6 회고 (주간 30분, 매주 금요일)", H2))
flow6 = [
    ["섹션", "내용", "양식"],
    [cell("실적 리뷰"), cell("이번 주 완료/미완료 목록, 미완료 사유 분류(양·역량·프로세스)"), cell("[양식 F] 주간 회고록")],
    [cell("프로세스 개선"), cell("반복 병목 식별 → 체크리스트/템플릿화 안건 등록"), cell("[양식 F] 주간 회고록")],
    [cell("다음 주 계획"), cell("우선순위 Top 3 합의, 역할 로테이션 인수인계"), cell("[양식 B] 통합 업무 보드")],
]
story.append(make_table(flow6, col_widths=[28 * mm, 100 * mm, 37 * mm]))

# ───────────────── 4. 노동법 체크리스트 ─────────────────
story.append(PageBreak())
story.append(p("4. 노동법 준수 체크리스트", H1))
law_tbl = [
    ["항목", "법적 기준", "본 프로세스 대응"],
    [cell("주 근로시간"), cell("주 40h + 연장 12h ≤ 52h (근기법 §50, §53)"), cell("80% 룰로 32h 상한, 초과 시 사전 동의 절차")],
    [cell("연장근로 수당"), cell("통상임금 1.5배 가산 (근기법 §56)"), cell("[양식 G] 연장근로 사전동의서 + 회계 연동")],
    [cell("휴게시간"), cell("4h당 30분, 8h당 1h 이상 (근기법 §54)"), cell("보드에 점심 12:00–13:00 고정 차단")],
    [cell("야간·휴일 지시"), cell("연장근로 인정 가능 (대법 판례)"), cell("퇴근 후 메신저 업무 지시 금지 룰 명문화")],
    [cell("업무 모니터링"), cell("개인정보보호법 §15, §59 — 동의 없는 PC감시 위법 소지"), cell("보드 자율 기록만 사용, 키로깅·화면감시 미도입")],
    [cell("안전배려 의무"), cell("산안법 §5 — 사용자의 건강 보호 의무"), cell("80% 룰로 과로 사전 차단")],
    [cell("성과·근태 기록"), cell("3년 보존 의무 (근기법 §42)"), cell("보드 데이터 월별 백업·아카이브")],
]
story.append(make_table(law_tbl, col_widths=[28 * mm, 65 * mm, 72 * mm]))

# ───────────────── 5. 도입 로드맵 ─────────────────
story.append(p("5. 4주 도입 로드맵", H1))
road_tbl = [
    ["주차", "활동", "산출물 / KPI"],
    [cell("1주차"),
     cell("보드 세팅 · 기존 업무 전수 등록 · 양식 A~G 배포"),
     cell("등록률 100%, 양식 7종 비치")],
    [cell("2주차"),
     cell("데일리 스탠드업 시작 · 표준 공수표(양식 D) 초안 작성"),
     cell("스탠드업 출석률 ≥ 95%, 공수표 80% 완성")],
    [cell("3주차"),
     cell("80% 룰 적용 · 역할 로테이션 시작 · 우선순위 룰 가동"),
     cell("주간 평균 가용시간 활용률 측정 시작")],
    [cell("4주차"),
     cell("첫 주간 회고 · 룰 보정 · 반복 업무 체크리스트화"),
     cell("회고록 1건, 표준화 안건 ≥ 3건")],
    [cell("5주차+"),
     cell("월간 점검 정착 · 분기 단위 역할 재편성"),
     cell("미완료율 < 10%, 불평 발생 건수 추적")],
]
story.append(make_table(road_tbl, col_widths=[18 * mm, 75 * mm, 72 * mm]))

# ───────────────── 6. 조직 진단 ─────────────────
story.append(PageBreak())
story.append(p("6. 조직 진단 — 매출 50억대 회사 적정 인력 검토", H1))

story.append(p("6.1 현 구성 (총 13명)", H2))
org_tbl = [
    ["부문", "포지션", "인원"],
    [cell("마케팅"), cell("마케팅 팀장 / 컨텐츠 마케터 / 퍼포먼스 마케터(B2B 병행)"), cell("3")],
    [cell("개발"), cell("프론트엔드 개발자"), cell("1")],
    [cell("상품·브랜드"), cell("MD / VMD / 디자이너"), cell("3")],
    [cell("고객"), cell("CS"), cell("1")],
    [cell("경영지원"), cell("경영지원팀장 / 인사 / 회계 / 총무"), cell("4")],
    [cell("영업"), cell("영업"), cell("1")],
    [cell("합계"), cell(""), cell("13")],
]
story.append(make_table(org_tbl, col_widths=[30 * mm, 110 * mm, 25 * mm]))

story.append(p("6.2 산업 벤치마크와의 비교", H2))
bench_tbl = [
    ["지표", "현 수치", "리테일·이커머스 벤치마크", "판정"],
    [cell("인당 매출"), cell("3.85억"), cell("3.0 ~ 5.0억"), cell("적정")],
    [cell("관리간접 비중"), cell("38% (5/13: 팀장2 + 지원3)"), cell("25 ~ 30%"), cell("높음")],
    [cell("개발자 비중"), cell("7.7% (1명)"), cell("10 ~ 15%"), cell("부족, 단일점 리스크")],
    [cell("CS 비중"), cell("7.7% (1명)"), cell("8 ~ 12%"), cell("성장 시 병목 우려")],
    [cell("영업 직무 명확성"), cell("B2B를 퍼포먼스 마케터가 병행"), cell("B2B 영업은 별도 직무로 분리"), cell("개선 필요")],
]
story.append(make_table(bench_tbl, col_widths=[28 * mm, 35 * mm, 60 * mm, 30 * mm]))

story.append(p("6.3 식별된 핵심 이슈", H2))
issues = [
    ("① 직무 충돌 (가장 시급)",
     "퍼포먼스 마케터가 B2C 광고운영 + B2B 영업을 병행. KPI 충돌(광고 ROAS vs 영업 파이프라인), "
     "근무시간 분배 불투명. <b>업무가 많다는 불평의 주된 원인일 가능성 높음.</b>"),
    ("② 단일 의존 리스크",
     "프론트엔드 개발자 1명·CS 1명·영업 1명 → 휴직/퇴사 시 대체 인력 없음. 백업 또는 외주 계약 필요."),
    ("③ 관리 통제폭(span of control) 과다",
     "경영지원팀장 1인이 인사·회계·총무·영업 4개 기능 + 영업 1명 직속 = 사실상 5명 직접관리. "
     "주니어 멘토링 시간 확보 어려움."),
    ("④ 마케팅 vs 영업 인력 비대칭",
     "마케팅 3명 vs 영업 1명. B2C 전용 모델이면 적정, B2B 매출 비중이 20% 이상이면 영업 보강 필요."),
    ("⑤ 백엔드·데이터 부재",
     "프론트엔드만 있고 백엔드·인프라·데이터 분석 인력 없음. 외주·SaaS 의존 전제 시 운영 리스크 점검 필요."),
]
for title, body in issues:
    story.append(p(f"<b>{title}</b>", H3))
    story.append(p(body, BODY))

story.append(PageBreak())
story.append(p("6.4 권고안 — 신규 채용 없이 효율을 끌어올리는 3단계", H2))

story.append(p("<b>STEP 1. 직무 재정의 (즉시, 0원)</b>", H3))
step1 = [
    ["기존", "변경 후", "기대효과"],
    [cell("퍼포먼스 마케터 (B2B 영업 병행)"),
     cell("퍼포먼스 마케터 (B2C 광고 운영 전담)"),
     cell("KPI 명확화, 불평 원인 1차 해소")],
    [cell("영업 (B2C·B2B 혼재)"),
     cell("영업 (B2B 전담 + 기존 B2C 일부 인계)"),
     cell("B2B 파이프라인 단일 책임자")],
    [cell("마케팅 팀장"),
     cell("마케팅 팀장 (퍼포먼스 마케터 코칭·KPI 관리 명시)"),
     cell("팀장 역할 구체화")],
]
story.append(make_table(step1, col_widths=[55 * mm, 55 * mm, 55 * mm]))

story.append(p("<b>STEP 2. 백업·이중화 (1개월 내, 저비용)</b>", H3))
step2 = [
    ["대상", "조치"],
    [cell("프론트엔드 개발자"), cell("외주 개발사 SLA 계약 (긴급 대응 8h 이내) + 코드 문서화 의무")],
    [cell("CS"), cell("MD·VMD가 CS 응대 2차 백업 (피크 시간만 보조), FAQ·챗봇 1차 자동화")],
    [cell("회계·총무"), cell("상호 업무 매뉴얼화 → 1주 이상 부재 시 상대가 대체 가능하도록")],
    [cell("디자이너"), cell("외주 디자이너 풀(3~5명) 사전 등록, 단가표 보유")],
]
story.append(make_table(step2, col_widths=[35 * mm, 130 * mm]))

story.append(p("<b>STEP 3. 통제폭 재설계 (분기 내)</b>", H3))
step3 = [
    ["현재", "권고", "비고"],
    [cell("경영지원팀장 → 인사/회계/총무/영업 4개 기능"),
     cell("경영지원팀장 → 인사·회계·총무 3개 기능"),
     cell("영업은 마케팅 팀장 또는 대표 직속으로 이관 검토")],
    [cell("팀장 부재 팀(마케팅 외 기타)"),
     cell("업무조정자 로테이션으로 임시 대체"),
     cell("본 문서 §3.4 적용")],
]
story.append(make_table(step3, col_widths=[55 * mm, 55 * mm, 55 * mm]))

story.append(p("<b>채용 우선순위 (매출 70억 도달 또는 B2B 비중 30% 초과 시)</b>", H3))
hire_tbl = [
    ["순위", "포지션", "트리거"],
    [cell("1순위"), cell("B2B 영업 전담 1명"), cell("B2B 매출 비중 ≥ 20% 또는 인바운드 미응대 사례 발생")],
    [cell("2순위"), cell("CS 1명 또는 CS 매니저"), cell("월 응대 건수가 1인 처리량 초과 시점")],
    [cell("3순위"), cell("백엔드/풀스택 개발자"), cell("외주 비용 > 정규직 인건비 도달 또는 운영 장애 발생 시")],
    [cell("4순위"), cell("데이터·퍼포먼스 분석 인력"), cell("매출 100억 도달 시점")],
]
story.append(make_table(hire_tbl, col_widths=[15 * mm, 50 * mm, 100 * mm]))

# ───────────────── 7. 양식 안내 ─────────────────
story.append(PageBreak())
story.append(p("7. 별첨 — 운영 양식 세트 (엑셀)", H1))
story.append(p(
    "본 문서와 함께 배포되는 「업무관리_양식세트.xlsx」 파일에 다음 7종 시트가 포함됩니다. "
    "각 시트는 그대로 사용 가능하며, 도구(Notion·Jira 등) 이전 시에도 동일한 컬럼 구조를 유지합니다.", BODY))
forms_tbl = [
    ["코드", "양식명", "용도", "작성자"],
    [cell("A"), cell("업무 요청서"), cell("신규 업무 진입점, P등급·기대산출물 명시"), cell("요청자")],
    [cell("B"), cell("통합 업무 보드"), cell("전사 모든 업무의 단일 저장소"), cell("담당자")],
    [cell("C"), cell("데일리 스탠드업 회의록"), cell("매일 15분 회의 기록"), cell("기록자")],
    [cell("D"), cell("표준 업무 공수표"), cell("업무 유형별 단위 소요시간 정의"), cell("팀 공동")],
    [cell("E"), cell("역할 로테이션 표"), cell("4개 역할의 분기별 순환 배정"), cell("업무조정자")],
    [cell("F"), cell("주간 회고록"), cell("매주 금요일 30분 회고"), cell("기록자")],
    [cell("G"), cell("연장근로 사전동의서"), cell("80% 룰 초과 시 동의·수당 산정"), cell("담당자·인사")],
]
story.append(make_table(forms_tbl, col_widths=[12 * mm, 40 * mm, 70 * mm, 35 * mm]))

# ───────────────── 8. 협의 안건 ─────────────────
story.append(p("8. 인사팀장 협의 안건", H1))
agenda_tbl = [
    ["No.", "안건", "결정 필요 사항"],
    [cell("1"), cell("도입 시점 및 시범 운영 범위"), cell("전사 동시 / 1개 팀 파일럿 중 선택")],
    [cell("2"), cell("연장근로 사전동의 절차"), cell("취업규칙 개정 필요 여부 검토")],
    [cell("3"), cell("퍼포먼스 마케터 직무 재정의"), cell("KPI·평가지표 수정과 본인 동의 절차")],
    [cell("4"), cell("외주 SLA 계약 예산"), cell("개발·디자인 외주 풀 구성 예산 승인")],
    [cell("5"), cell("도구 선정"), cell("Notion / Jira / 스프레드시트 중 선택 (예산 연동)")],
    [cell("6"), cell("성과 측정·평가 반영"), cell("보드 데이터의 인사평가 활용 범위 (감시 이슈 회피)")],
]
story.append(make_table(agenda_tbl, col_widths=[12 * mm, 60 * mm, 93 * mm]))

story.append(Spacer(1, 10))
story.append(p(
    "<b>결론:</b> 본 개선안의 핵심은 \"팀장 1명을 새로 뽑는 비용 없이도 팀장의 5가지 기능을 시스템으로 분산\"하는 것이며, "
    "동시에 매출 50억대 조직의 직무 충돌(B2B/B2C 마케터 병행)과 단일점 리스크를 해소하는 직무 재설계를 병행 제안합니다. "
    "노동법 준수 체크리스트는 모든 프로세스 단계에 내장되어 있습니다.", CALL))

# Build
doc = SimpleDocTemplate(
    "/home/user/Jay/인사팀장_미팅자료_업무프로세스개선안.pdf",
    pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
    topMargin=18 * mm, bottomMargin=18 * mm,
    title="팀 업무 프로세스 개선안", author="조직개선 TF",
)


def footer(canvas, doc_):
    canvas.saveState()
    canvas.setFont("Nanum", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(18 * mm, 10 * mm, "팀 업무 프로세스 개선안")
    canvas.drawRightString(192 * mm, 10 * mm, f"- {doc_.page} -")
    canvas.restoreState()


doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("PDF generated successfully")
