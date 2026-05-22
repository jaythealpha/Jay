"""
요기보(Yogibo) 인스타그램 티징 콘텐츠 — 후킹 요소 데이터셋
yogibo.kr 기준 / 빈백 소파 전체 라인업 / 한국 시장 우선

이 파일은 1,000장 대량 이미지 생성을 위한 '조합 축'을 정의한다.
각 축을 곱하면 수십만 개 조합이 나오며, generate_prompts.py가
중복 없이 다양성을 확보해 1,000개를 샘플링한다.

법적 주의: 이미지 프롬프트는 로고/상표 없는 '프리미엄 빈백 소파'로 묘사한다.
브랜드 로고·워터마크는 후반 작업(오버레이)에서 합성하는 것을 전제로 한다.
"""

# ---------------------------------------------------------------------------
# 1) 제품 라인업 (yogibo.kr 빈백 소파 전체 + 한국 현지화 라인)
# ---------------------------------------------------------------------------
PRODUCTS = [
    {"kr": "맥스",   "en": "Max",   "form": "6피트 풀사이즈 빈백 소파, 1인이 완전히 누울 수 있는 길이"},
    {"kr": "더블",   "en": "Double", "form": "맥스 2배 폭의 초대형 빈백, 커플·가족용 침대 겸용"},
    {"kr": "프라임", "en": "Prime",  "form": "슬림한 등받이형 빈백, 의자처럼 세워 앉기 좋은 형태"},
    {"kr": "슬림",   "en": "Slim",   "form": "좁은 폭의 빈백, 1인 라운지 체어 형태"},
    {"kr": "미디",   "en": "Midi",   "form": "맥스의 컴팩트 버전, 청소년·소형 공간용 중형 빈백"},
    {"kr": "미니",   "en": "Mini",   "form": "1인용 소형 빈백, 가볍고 어디든 옮기는 컴팩트 사이즈"},
    {"kr": "팟",     "en": "Pod",    "form": "둥근 1인 의자형 빈백, 감싸는 듯한 곡선 실루엣"},
    {"kr": "팟엑스", "en": "Pod X",  "form": "확장형 듀얼 라이너 빈백, 몸 굴곡에 반응하는 분절 패널"},
    {"kr": "드롭",   "en": "Drop",   "form": "물방울 형태의 빈백 스툴, 발받침·보조 좌석용"},
    {"kr": "라운저", "en": "Lounger", "form": "등받이가 높은 1인 라운지형 빈백, 독서·휴식용"},
    {"kr": "피라미드", "en": "Pyramid", "form": "삼각 쿠션형 빈백, 등·허리 받침용 보조 쿠션"},
    {"kr": "허기보", "en": "Hugibo",  "form": "끌어안는 바디필로우형 빈백, 수면·포옹감 강조"},
    {"kr": "서포트", "en": "Support", "form": "U자형 받침 쿠션, 빈백과 결합해 리클라이너로 변신"},
    # 한국 현지화/신규 라인 (전략 문서 기반)
    {"kr": "미니 K", "en": "Mini K",  "form": "원룸·15평 이하 전용 초소형 빈백"},
    {"kr": "플로어", "en": "Floor",   "form": "좌식 문화 맞춤 초저높이 빈백"},
    {"kr": "온돌",   "en": "Ondol",   "form": "겨울 발열 커버형 빈백, 전기요 호환"},
    {"kr": "키즈",   "en": "Kids",    "form": "유아·아동 안전 인증 소형 빈백, 밝은 컬러"},
    {"kr": "펫",     "en": "Pet",     "form": "방수·항균·발톱 저항 커버의 반려동물용 빈백"},
]

# ---------------------------------------------------------------------------
# 2) 후킹 아키타입 + 아키타입별 한국어 티저 카피 풀
#    (스크롤을 멈추게 하는 '훅' 유형 — 인스타 릴스/피드 1초 승부)
# ---------------------------------------------------------------------------
HOOKS = [
    {
        "key": "curiosity_gap",
        "kr": "호기심 갭",
        "desc": "정보를 일부러 가려 '뭐지?' 궁금증으로 멈추게 함",
        "copy": [
            "이 소파, 3초만 앉으면 못 일어나는 이유",
            "왜 다들 침대를 두고 여기서 잘까?",
            "이걸 본 사람들이 소파를 버렸습니다",
            "사람을 망치는 소파가 있다는데…",
            "이게 소파라고? 끝까지 보면 놀람",
        ],
    },
    {
        "key": "asmr_sensory",
        "kr": "감각·ASMR",
        "desc": "촉감/푹 꺼지는 감각을 극대화한 정적 무드",
        "copy": [
            "푹— 몸이 그대로 녹아드는 소리",
            "이 촉감, 화면으로도 느껴지나요?",
            "무중력으로 가라앉는 30초",
            "손이 닿는 순간 멈추는 마법의 촉감",
            "오늘 밤, 여기로 사라지고 싶다",
        ],
    },
    {
        "key": "before_after",
        "kr": "비포·애프터",
        "desc": "딱딱한 일상 vs 요기보 후의 변화 대비",
        "copy": [
            "딱딱한 거실 → 3초 만에 라운지로",
            "퇴근 전 vs 퇴근 후 내 모습",
            "소파 있을 때 vs 요기보 들인 후",
            "어제의 허리 vs 오늘의 허리",
            "혼자 살기 전 → 혼자 살고 난 후의 거실",
        ],
    },
    {
        "key": "problem_agitate",
        "kr": "문제 자극",
        "desc": "공감되는 불편을 콕 찌른 뒤 해결을 암시",
        "copy": [
            "소파에서 자고 일어나면 허리 아픈 당신에게",
            "비싼 소파, 커버는 왜 못 빨까?",
            "반려견이 소파를 다 뜯어놨다면",
            "원룸이라 소파는 포기했다고요?",
            "게이밍 의자, 오래 앉으면 배기지 않나요?",
        ],
    },
    {
        "key": "fomo_scarcity",
        "kr": "FOMO·희소성",
        "desc": "한정/품절 임박으로 지금 봐야 할 이유 부여",
        "copy": [
            "이 컬러, 곧 사라집니다",
            "한정 컬러 — 재입고 없음",
            "다들 이미 거실에 하나씩 들였대요",
            "올여름 품절 1순위, 미리 보세요",
            "지금 안 보면 다음은 내년",
        ],
    },
    {
        "key": "social_proof",
        "kr": "사회적 증거",
        "desc": "다수가 선택했다는 신뢰·동조 심리",
        "copy": [
            "리뷰 10,000개가 말하는 그 소파",
            "연예인 자취방에 다 있다는 그것",
            "1인 가구가 가장 많이 산 가구 1위",
            "재구매율이 말해주는 편안함",
            "한 번 산 사람은 색깔만 늘린다",
        ],
    },
    {
        "key": "transformation",
        "kr": "변신·다용도",
        "desc": "소파→침대→의자 변신 장면으로 가치 증명",
        "copy": [
            "소파였다가, 침대였다가, 의자였다가",
            "하나로 거실 전체를 바꾸는 법",
            "접고 펴고 세우고 — 공간이 살아난다",
            "1개로 5가지 자세, 직접 보세요",
            "낮엔 소파, 밤엔 침대",
        ],
    },
    {
        "key": "pattern_interrupt",
        "kr": "패턴 인터럽트",
        "desc": "예상 밖 장면/구도로 스크롤을 끊음",
        "copy": [
            "잠깐, 저 사람 지금 소파 안으로 빨려 들어감",
            "이 자세 실화냐",
            "끝까지 안 보면 손해",
            "이런 식으로 앉는 거 처음 봄",
            "3초 뒤 반전 주의",
        ],
    },
    {
        "key": "aspiration",
        "kr": "동경·라이프스타일",
        "desc": "갖고 싶은 이상적 공간/삶을 제시",
        "copy": [
            "내가 꿈꾸던 거실은 이런 거였어",
            "이런 주말, 가져본 적 있나요",
            "햇살 + 요기보 = 완벽한 일요일",
            "퇴근하고 싶어지는 집의 비밀",
            "남의 집 같던 그 무드, 우리집에",
        ],
    },
    {
        "key": "humor_relatable",
        "kr": "유머·공감",
        "desc": "피식 웃게 만드는 일상 공감 포인트",
        "copy": [
            "주말의 나: 요기보와 한 몸",
            "약속 취소되자마자 향한 곳",
            "결국 가족 모두가 노리는 자리",
            "강아지에게 자리 뺏긴 1인",
            "‘잠깐만 누울게’ → 3시간 경과",
        ],
    },
    {
        "key": "season_hook",
        "kr": "시즌·타이밍",
        "desc": "계절/이벤트와 엮어 즉시성 부여",
        "copy": [
            "장마철, 집이 가장 좋아지는 이유",
            "올여름 에어컨 앞 명당 자리",
            "환절기 허리에게 주는 선물",
            "연말, 가족이 모이는 새 중심",
            "이사 시즌, 소파 대신 이것",
        ],
    },
    {
        "key": "price_value",
        "kr": "가치·합리화",
        "desc": "가격 저항을 가치로 전환하는 메시지",
        "copy": [
            "소파 + 침대 + 의자, 가격은 하나",
            "10년 쓰는 소파, 커버만 갈면 새것",
            "버리는 소파 vs 평생 가는 소파",
            "비싸 보이지만 1평도 안 차지",
            "한 번 사면 왜 안 바꾸는지 알게 됨",
        ],
    },
]

# ---------------------------------------------------------------------------
# 3) 장면/공간 (한국 주거·라이프스타일 맥락)
# ---------------------------------------------------------------------------
SCENES = [
    {"kr": "햇살 드는 거실 창가",   "en": "sunlit living room by a large window, soft daylight"},
    {"kr": "아늑한 원룸",          "en": "cozy compact studio apartment, minimal Korean interior"},
    {"kr": "무드등 켜진 밤 침실",   "en": "dim bedroom at night with warm mood lighting"},
    {"kr": "게이밍 셋업 방",        "en": "gaming room with RGB lights and a desk setup"},
    {"kr": "서재 책장 앞",          "en": "home library nook in front of bookshelves"},
    {"kr": "발코니·테라스",         "en": "apartment balcony with plants and city view"},
    {"kr": "캠핑·차박 텐트 안",      "en": "inside a camping tent / car-camping setup, lantern light"},
    {"kr": "키즈룸",               "en": "bright kids room with toys, playful pastel palette"},
    {"kr": "재택 홈오피스",         "en": "work-from-home office corner, laptop on a low table"},
    {"kr": "감성 카페 라운지",       "en": "trendy cafe lounge interior, warm wood tones"},
    {"kr": "펜션·풀빌라 거실",       "en": "vacation pension living room, premium resort vibe"},
    {"kr": "한강 피크닉 잔디",       "en": "Hangang river park lawn picnic, outdoor daytime"},
    {"kr": "미니멀 화이트 스튜디오", "en": "clean white photo studio, seamless backdrop"},
    {"kr": "겨울 러그 깔린 마루",    "en": "winter living room with rug, cozy ondol floor warmth"},
]

# ---------------------------------------------------------------------------
# 4) 페르소나 (등장 인물/상황) — 비워두면 제품 단독 컷
# ---------------------------------------------------------------------------
PERSONAS = [
    {"kr": "20대 1인 가구 여성",   "en": "a young woman in her 20s living alone, relaxed"},
    {"kr": "재택근무 직장인",       "en": "a remote worker taking a break"},
    {"kr": "다정한 커플",          "en": "a cozy couple lounging together"},
    {"kr": "아이와 부모 가족",       "en": "a parent and a child playing"},
    {"kr": "게이머 청년",          "en": "a young gamer with a controller"},
    {"kr": "반려견과 집사",         "en": "a person with a small dog cuddling"},
    {"kr": "책 읽는 학생",          "en": "a student reading a book"},
    {"kr": "낮잠 자는 사람",        "en": "a person napping, eyes closed, blissful"},
    {"kr": "시니어 부모님",         "en": "an elderly parent resting comfortably"},
    {"kr": "반려묘와 함께",         "en": "a person with a cat curled up nearby"},
    {"kr": "친구들 홈파티",         "en": "a few friends hanging out, casual home party"},
    {"kr": "제품 단독(인물 없음)",   "en": "no person, product hero shot only"},
]

# ---------------------------------------------------------------------------
# 5) 비주얼 스타일 / 촬영 포맷 (인스타 티저에 강한 구도)
# ---------------------------------------------------------------------------
STYLES = [
    {"kr": "초근접 텍스처 클로즈업", "en": "extreme macro close-up of plush fabric texture, shallow depth of field"},
    {"kr": "라이프스타일 와이드",     "en": "wide lifestyle editorial shot, natural light, lived-in feel"},
    {"kr": "탑다운 플랫레이",        "en": "top-down flat lay composition, neatly arranged"},
    {"kr": "푹 꺼지는 모션 블러",     "en": "motion-blur of a body sinking into the bean bag, dynamic"},
    {"kr": "스플릿 비교 컷",         "en": "split-screen before/after comparison layout"},
    {"kr": "골든아워 시네마틱",       "en": "golden hour cinematic lighting, warm glow, film look"},
    {"kr": "미니멀 제품 히어로",      "en": "minimal product hero shot, soft gradient backdrop, studio light"},
    {"kr": "다크 무드 라이팅",       "en": "dark moody lighting with a single warm light source"},
    {"kr": "오버헤드 부감",          "en": "high overhead bird's-eye angle looking down"},
    {"kr": "로우앵글 임팩트",        "en": "dramatic low angle, product looks grand and inviting"},
    {"kr": "파스텔 팝 컬러블록",      "en": "pastel pop color-block background, playful graphic style"},
    {"kr": "한 손 스케일 비교",       "en": "hand or person for scale, emphasizing size and softness"},
]

# ---------------------------------------------------------------------------
# 6) 인스타 포맷별 종횡비 가중치
# ---------------------------------------------------------------------------
ASPECT_RATIOS = [
    {"ratio": "4:5",  "size": "1080x1350", "weight": 5, "use": "피드 세로"},
    {"ratio": "9:16", "size": "1080x1920", "weight": 4, "use": "릴스/스토리"},
    {"ratio": "1:1",  "size": "1080x1080", "weight": 2, "use": "피드 정방"},
]

# 컬러 팔레트 (요기보 대표 컬러 + 시즌 컬러)
COLORS = [
    "딥 네이비", "차콜 그레이", "크림 베이지", "테라코타", "올리브 그린",
    "더스티 핑크", "머스타드 옐로", "코발트 블루", "라벤더", "오트밀 화이트",
]

# 이미지 모델 공통 네거티브 프롬프트
NEGATIVE_PROMPT = (
    "logo, brand text, watermark, deformed limbs, extra fingers, low quality, "
    "blurry text, distorted face, cluttered, oversaturated, plastic look, "
    "duplicate furniture, broken perspective"
)
