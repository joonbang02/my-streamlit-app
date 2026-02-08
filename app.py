# app.py
# Travel-Maker (Streamlit)
# 실행:
#   pip install streamlit requests openai
#   streamlit run app.py
#
# 참고:
# - OpenAI Responses API + web_search 도구를 사용 (키 없으면 룰베이스 플랜 제공)
# - 무료 날씨: Open-Meteo (no key)
# - 지오코딩: Nominatim (OpenStreetMap) (no key) - User-Agent 필수

import os
import math
import time
import json
import requests
import streamlit as st
from datetime import datetime

# OpenAI SDK (공식 예시: from openai import OpenAI; client.responses.create ...)
# - 키는 sidebar 입력값 우선, 없으면 환경변수 OPENAI_API_KEY 사용 가능
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# -----------------------------
# 스타일 (베이지 + 미니멀 + MZ 감성)
# -----------------------------
APP_NAME = "Travel-Maker"

BEIGE_BG = "#F6F0E6"
CARD_BG = "#FFF9F0"
TEXT = "#2B2B2B"
MUTED = "#6B6B6B"
ACCENT = "#C07A4D"

CSS = f"""
<style>
    .stApp {{
        background: {BEIGE_BG};
        color: {TEXT};
    }}

    /* 전체 폭 조금 더 보기 좋게 */
    .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 980px;
    }}

    /* 헤더 타이틀 느낌 */
    .tm-title {{
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin-bottom: .2rem;
    }}
    .tm-subtitle {{
        color: {MUTED};
        font-size: 1.02rem;
        margin-bottom: 1rem;
    }}
    .tm-badge {{
        display: inline-block;
        padding: .25rem .6rem;
        border-radius: 999px;
        background: rgba(192, 122, 77, 0.12);
        color: {ACCENT};
        font-weight: 700;
        font-size: .88rem;
        margin-left: .35rem;
    }}

    /* 카드 */
    .tm-card {{
        background: {CARD_BG};
        border: 1px solid rgba(0,0,0,0.06);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 8px 22px rgba(0,0,0,0.06);
        margin: .6rem 0 1rem 0;
    }}
    .tm-card h3 {{
        margin: 0 0 .35rem 0;
        font-size: 1.15rem;
    }}
    .tm-tip {{
        color: {MUTED};
        font-size: .95rem;
        line-height: 1.4;
        margin-top: .25rem;
    }}

    /* 결과 섹션 */
    .tm-section-title {{
        font-size: 1.3rem;
        font-weight: 800;
        margin-top: .35rem;
        margin-bottom: .4rem;
    }}

    /* 버튼 */
    div.stButton > button {{
        border-radius: 14px;
        padding: .55rem 1rem;
        font-weight: 800;
        border: 1px solid rgba(0,0,0,0.08);
    }}
    div.stButton > button:hover {{
        border-color: rgba(192, 122, 77, 0.45);
        box-shadow: 0 10px 22px rgba(192, 122, 77, 0.18);
        transform: translateY(-1px);
    }}

    /* 입력 요소 라운딩 */
    .stTextInput input, .stNumberInput input {{
        border-radius: 12px !important;
    }}
    .stSelectbox div[data-baseweb="select"] > div {{
        border-radius: 12px !important;
    }}

    /* expander */
    details {{
        border-radius: 14px;
        border: 1px solid rgba(0,0,0,0.06);
        background: {CARD_BG};
        padding: .4rem .7rem;
    }}

    /* 작은 메모 */
    .tm-micro {{
        color: {MUTED};
        font-size: .85rem;
    }}
</style>
"""


# -----------------------------
# 유틸: 안전한 세션 상태
# -----------------------------
def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 1

    defaults = {
        # 1페이지
        "travel_month": "상관없음",
        "party_type": "친구",
        "party_count": 2,
        "destination_scope": "국내",
        "destination_text": "",
        "travel_mode": "자유여행",

        # 2페이지
        "distance_pref": "상관없음",
        "duration": "3일",
        "travel_style": ["힐링"],
        "budget": 1000000,

        # 부가
        "start_city": "서울",  # 출발지 (거리 계산용, AI 판단용)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# -----------------------------
# 무료 API: 지오코딩 (Nominatim)
# -----------------------------
def geocode_place(query: str):
    """
    Nominatim은 User-Agent 필수.
    과도 호출 방지 위해 간단 sleep.
    """
    if not query.strip():
        return None

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": f"{APP_NAME}/1.0 (streamlit app)"}
    try:
        time.sleep(0.2)
        r = requests.get(url, params=params, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return {
            "lat": float(data[0]["lat"]),
            "lon": float(data[0]["lon"]),
            "display_name": data[0].get("display_name", query)
        }
    except Exception:
        return None


# -----------------------------
# 거리: Haversine (km)
# -----------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def classify_distance(km: float):
    if km is None:
        return "미정"
    if km < 1200:
        return "단거리 느낌(가볍게 다녀오기 가능)"
    if km < 4500:
        return "중거리(비행/이동 계획 빡세게 짜야 함)"
    return "장거리(시차/체력/동선까지 전략 필요)"


# -----------------------------
# 무료 API: 날씨(요약) - Open-Meteo
# -----------------------------
def open_meteo_month_hint(month: str):
    """
    월 단위로 대략적 '계절감'만 전달 (정확한 날짜가 없으므로).
    Open-Meteo는 일자 예보/과거도 가능하지만,
    여기서는 '월'만 받아 가벼운 힌트 + 목적지 위경도 기반 '최근 7일' 요약만.
    """
    if month == "상관없음":
        return "월이 프리면, 날씨는 그때그때 ‘유연한 인간’ 모드로 대응 ㄱㄱ"
    m = int(month.replace("월", ""))
    if m in [12, 1, 2]:
        return "겨울 감성 ON. 방한템 + 실내코스도 챙기면 완-벽"
    if m in [3, 4, 5]:
        return "봄바람 살랑. 낮밤 온도차만 조심하면 갬성샷 자동 생성"
    if m in [6, 7, 8]:
        return "여름 폭주 구간. 더위/습도/소나기 대비 필수(선크림은 생존템)"
    if m in [9, 10, 11]:
        return "가을은 진짜 반칙. 걷기/야외 코스 뽕 뽑기 좋은 시즌"
    return "날씨 힌트 로딩 실패… (하지만 우린 계획왕/퀸)"


def fetch_open_meteo_recent_summary(lat: float, lon: float):
    """
    최근 7일 기온/강수 요약(목적지 좌표 필요).
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": 7
        }
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        d = r.json().get("daily", {})
        tmax = d.get("temperature_2m_max", [])
        tmin = d.get("temperature_2m_min", [])
        prcp = d.get("precipitation_sum", [])
        if not tmax or not tmin:
            return None
        avg_max = sum(tmax) / len(tmax)
        avg_min = sum(tmin) / len(tmin)
        total_prcp = sum(prcp) if prcp else 0.0
        return {
            "avg_max": round(avg_max, 1),
            "avg_min": round(avg_min, 1),
            "total_prcp": round(total_prcp, 1),
        }
    except Exception:
        return None


# -----------------------------
# 룰베이스 플래너 (키 없을 때도 결과 나오게)
# -----------------------------
def duration_to_days(duration: str):
    if duration == "당일치기":
        return 1
    if duration == "3일":
        return 3
    if duration == "5일":
        return 5
    if duration == "10일 이상":
        return 10
    # fallback
    return 3


def build_rule_based_plan(payload: dict):
    days = duration_to_days(payload["duration"])
    style = payload.get("travel_style", [])
    mode = payload.get("travel_mode", "자유여행")
    party = payload.get("party_type", "친구")
    budget = payload.get("budget", 0)
    dest = payload.get("destination_text", "").strip() or "어딘가 갬성 좋은 곳"
    month = payload.get("travel_month", "상관없음")

    # 톤: 위트 + 깔끔
    headline = f"✨ {dest} {days}일 플랜 (feat. {party} 모먼트) — ‘계획은 섬세하게, 마음은 가볍게’"
    budget_tier = "가성비" if budget and budget < 800000 else ("밸런스" if budget < 2000000 else "플렉스")
    mode_line = "자유여행이면 동선 최적화가 승부!" if mode == "자유여행" else "패키지면 체력 관리가 진짜 중요!"

    # 기본 일자별 템플릿
    day_blocks = []
    for d in range(1, days + 1):
        if d == 1:
            focus = "입국/체크인/동네 적응 + 맛집 스타트"
        elif d == days:
            focus = "마무리 산책 + 기념품 + 이동(체력 안배)"
        else:
            focus = "메인 스팟 + 취향 코스 + 야식(선택)"
        if "힐링" in style:
            focus += " + 카페/스파/공원 힐링 한 스푼"
        if "식도락" in style:
            focus += " + 로컬 맛집 2타임 확정"
        if "유흥" in style:
            focus += " + 밤코스(바/클럽/야경) 옵션"
        if "로드트립" in style:
            focus += " + 드라이브/근교 스팟 추가"

        day_blocks.append({
            "day": d,
            "title": f"Day {d}",
            "plan": [
                "☀️ 오전: 여유 있게 시작(체력은 적금이다)",
                f"🌤️ 낮: {focus}",
                "🌙 밤: 숙소 복귀 전 ‘오늘의 베스트 컷’ 저장 📸",
            ]
        })

    tips = [
        f"🗓️ 여행 시기 힌트: {open_meteo_month_hint(month)}",
        f"💸 예산 무드: {budget_tier} 코스로 구성(과소비 방지 ‘인간 실드’ ON)",
        f"🧭 이동 팁: {mode_line}",
        "✅ 체크리스트: 보조배터리/멀티어댑터(해외)/상비약/편한 신발은 국룰",
    ]

    return {
        "headline": headline,
        "summary": f"{dest}에서 {days}일 동안 {', '.join(style) if style else '취향저격'}으로 즐기는 플랜이야. 무리하지 말고 ‘꾸준히’ 즐기는 게 승자!",
        "day_blocks": day_blocks,
        "tips": tips,
        "sources": []
    }


# -----------------------------
# OpenAI 플래너 (키 있을 때: web_search + 출처 표시)
# -----------------------------
def call_openai_plan(openai_api_key: str, payload: dict):
    """
    Responses API + web_search 도구 사용.
    include에 web_search sources 포함 요청.
    - SDK convenience: response.output_text 사용 가능 (문서에 언급)
    - sources는 output items에서 추출 시도
    """
    if OpenAI is None:
        return None, "openai 패키지를 불러오지 못했어요. `pip install openai` 해주세요."

    try:
        client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        return None, f"OpenAI 클라이언트 초기화 실패: {e}"

    # 모델은 프로젝트에 따라 사용 가능 모델명이 다를 수 있어요.
    # 일단 범용적으로 많이 쓰이는 라인으로 설정(필요시 변경).
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # 사용자 입력을 기반으로 “웹 참고 + 출처” 요구
    instructions = (
        "너는 ‘Travel-Maker’ 여행 플래너 AI야.\n"
        "톤: 한국어, MZ 세대 유행어/위트(과하지만 않게), 깔끔한 구조.\n"
        "요청: 아래 사용자 입력을 바탕으로 구체적인 여행 계획을 만들어.\n"
        "가능하면 web_search로 실제 여행지/날씨/동선/맛집/핵심 명소를 참고하고,\n"
        "출처(사이트/기관/페이지 제목 수준)를 ‘Sources’ 섹션에 bullet로 정리해.\n"
        "주의: 확실하지 않은 내용은 ‘추정’이라고 표시.\n"
        "출력 포맷(JSON):\n"
        "{\n"
        '  "headline": "...",\n'
        '  "summary": "...",\n'
        '  "day_blocks": [{"day":1,"title":"...","plan":["...","..."]}, ...],\n'
        '  "tips": ["...", "..."],\n'
        '  "sources": [{"title":"...","url":"...","note":"..."}]\n'
        "}\n"
        "JSON만 출력해."
    )

    user_input = json.dumps(payload, ensure_ascii=False)

    try:
        resp = client.responses.create(
            model=model,
            instructions=instructions,
            input=user_input,
            tools=[{"type": "web_search"}],
            include=["web_search_call.action.sources"],
            max_output_tokens=1400,
        )
    except Exception as e:
        return None, f"OpenAI 호출 실패: {e}"

    # text
    text = getattr(resp, "output_text", None)
    if not text:
        # fallback: output에서 찾아보기
        try:
            # resp.output[0].content[0].text 형태가 예시로 존재
            text = resp.output[0].content[0].text
        except Exception:
            text = None

    if not text:
        return None, "OpenAI 응답에서 텍스트를 추출하지 못했어요."

    # JSON 파싱
    try:
        plan = json.loads(text)
    except Exception:
        # 모델이 JSON 외 텍스트를 섞었을 때 대비: JSON 블록만 추출 시도
        plan = None
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                plan = json.loads(text[start:end + 1])
        except Exception:
            plan = None

    if plan is None:
        return None, "계획 JSON 파싱에 실패했어요. (모델 출력 형식이 흔들렸을 수 있어요)"

    # sources 보강: include로 들어온 web_search_call sources를 output에서 긁기(가능한 경우)
    # (SDK 버전에 따라 구조가 달라질 수 있어 방어적으로)
    sources = plan.get("sources", []) if isinstance(plan, dict) else []
    try:
        dumped = resp.model_dump() if hasattr(resp, "model_dump") else None
        if dumped and "output" in dumped:
            for item in dumped["output"]:
                if item.get("type") == "web_search_call":
                    action = item.get("action", {})
                    srcs = action.get("sources", [])
                    for s in srcs:
                        # 중복 최소화
                        url = s.get("url")
                        title = s.get("title") or s.get("source") or "web"
                        if url and all(x.get("url") != url for x in sources if isinstance(x, dict)):
                            sources.append({"title": title, "url": url, "note": "web_search"})
        plan["sources"] = sources
    except Exception:
        pass

    return plan, None


# -----------------------------
# UI: 헤더
# -----------------------------
def render_header():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="tm-title">{APP_NAME}<span class="tm-badge">trip vibe generator</span></div>
        <div class="tm-subtitle">여행 계획? 이제 ‘감’ 말고 ‘근거’로 가자 😎 (근데 말투는 좀 힙하게)</div>
        """,
        unsafe_allow_html=True
    )


def sidebar():
    st.sidebar.markdown("### 🔑 OpenAI API Key")
    st.sidebar.caption("키는 앱 안에만 저장(세션)되고, 서버에 따로 저장하지 않아요.")
    api_key = st.sidebar.text_input(
        "OPENAI_API_KEY",
        type="password",
        placeholder="sk-... (없으면 룰베이스 플랜으로 진행)",
        value=st.session_state.get("openai_api_key", "")
    )
    st.session_state.openai_api_key = api_key

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧳 출발지(거리 계산용)")
    st.sidebar.caption("대충이라도 OK. 기본은 서울로 해뒀어!")
    st.session_state.start_city = st.sidebar.text_input(
        "출발 도시",
        value=st.session_state.get("start_city", "서울")
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🪄 사용 팁")
    st.sidebar.write("• 입력은 가볍게, 결과는 디테일하게\n• 키 있으면 웹 참고 + 출처까지 꽂아줌\n• 키 없으면 ‘내장 감각’(룰베이스)로도 꽤 그럴듯하게")


# -----------------------------
# 페이지 1: 기본 정보
# -----------------------------
def page1():
    st.markdown(
        """
        <div class="tm-card">
            <h3>1) 기본 정보부터 ‘쓱’ 수집할게요 📝</h3>
            <div class="tm-tip">너의 여행 DNA를 알아야… 내가 동선을 미치게 잘 짜지 😌</div>
        </div>
        """, unsafe_allow_html=True
    )

    months = ["상관없음"] + [f"{i}월" for i in range(1, 13)]
    c1, c2 = st.columns(2)

    with c1:
        st.session_state.travel_month = st.selectbox("여행 시기(월 단위)", months, index=months.index(st.session_state.travel_month))
        st.session_state.party_count = st.number_input("여행 인원", min_value=1, max_value=30, value=int(st.session_state.party_count), step=1)

    with c2:
        st.session_state.party_type = st.selectbox("관계", ["친구", "연인", "부모님", "가족", "혼자", "직장동료", "기타"], index=["친구","연인","부모님","가족","혼자","직장동료","기타"].index(st.session_state.party_type))
        st.session_state.travel_mode = st.selectbox("희망 여행 방식", ["자유여행", "패키지여행"], index=["자유여행","패키지여행"].index(st.session_state.travel_mode))

    st.markdown(
        """
        <div class="tm-card">
            <h3>2) 희망 여행지 🌍</h3>
            <div class="tm-tip">국내/해외는 분위기 선택이고, 아래 칸에는 “정확한 도시/나라”를 적어줘! (예: 부산 / 오사카 / 파리)</div>
        </div>
        """, unsafe_allow_html=True
    )

    c3, c4 = st.columns([1, 2])
    with c3:
        st.session_state.destination_scope = st.selectbox("국내/해외", ["국내", "해외"], index=["국내","해외"].index(st.session_state.destination_scope))
    with c4:
        st.session_state.destination_text = st.text_input("정확한 나라/도시", value=st.session_state.destination_text, placeholder="예: 제주 / 도쿄 / 방콕 / 바르셀로나")

    st.markdown("")

    nav = st.columns([1, 1, 2])
    with nav[2]:
        if st.button("다음 👉 (추가 정보로)", use_container_width=True):
            st.session_state.step = 2


# -----------------------------
# 페이지 2: 추가 정보
# -----------------------------
def page2():
    st.markdown(
        """
        <div class="tm-card">
            <h3>추가 정보는 ‘디테일의 악마’ 모드로 🧠</h3>
            <div class="tm-tip">여기서부터는 여행의 퀄리티가 확 달라져. (진짜임)</div>
        </div>
        """, unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)
    with c1:
        st.session_state.distance_pref = st.selectbox("여행지와의 거리 선호", ["단거리", "장거리", "상관없음"], index=["단거리","장거리","상관없음"].index(st.session_state.distance_pref))
        st.session_state.duration = st.selectbox("여행 일정", ["당일치기", "3일", "5일", "10일 이상"], index=["당일치기","3일","5일","10일 이상"].index(st.session_state.duration))

    with c2:
        st.session_state.travel_style = st.multiselect(
            "여행 스타일(복수 선택 가능)",
            ["힐링", "식도락", "유흥", "로드트립", "액티비티", "쇼핑", "문화/예술", "자연", "테마파크"],
            default=st.session_state.travel_style
        )
        st.session_state.budget = st.number_input("예상 예산(원)", min_value=0, max_value=20000000, value=int(st.session_state.budget), step=50000)

    st.markdown("")

    nav = st.columns([1, 1, 2])
    with nav[0]:
        if st.button("👈 이전", use_container_width=True):
            st.session_state.step = 1
    with nav[2]:
        if st.button("여행 계획 뽑기 ✨", use_container_width=True):
            st.session_state.step = 3


# -----------------------------
# 결과 페이지
# -----------------------------
def build_payload():
    return {
        "travel_month": st.session_state.travel_month,
        "party_count": int(st.session_state.party_count),
        "party_type": st.session_state.party_type,
        "destination_scope": st.session_state.destination_scope,
        "destination_text": st.session_state.destination_text,
        "travel_mode": st.session_state.travel_mode,
        "distance_pref": st.session_state.distance_pref,
        "duration": st.session_state.duration,
        "travel_style": st.session_state.travel_style,
        "budget": int(st.session_state.budget),
        "start_city": st.session_state.start_city,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def page3():
    payload = build_payload()

    st.markdown(
        """
        <div class="tm-card">
            <h3>결과 나왔다 🧾✨</h3>
            <div class="tm-tip">이제 너는 “여행 계획 있는 사람”이다. (이미 반은 성공)</div>
        </div>
        """, unsafe_allow_html=True
    )

    # 목적지/출발지 지오코딩 + 거리 계산 + 날씨 요약
    dest_geo = geocode_place(payload["destination_text"]) if payload["destination_text"].strip() else None
    start_geo = geocode_place(payload["start_city"]) if payload["start_city"].strip() else None

    km = None
    distance_comment = "거리 계산은 보류! (도시 입력이 비었거나 찾기 실패)"
    if dest_geo and start_geo:
        km = haversine_km(start_geo["lat"], start_geo["lon"], dest_geo["lat"], dest_geo["lon"])
        distance_comment = f"대략 **{km:,.0f} km** · {classify_distance(km)}"

    weather_hint = open_meteo_month_hint(payload["travel_month"])
    recent_weather = None
    if dest_geo:
        recent_weather = fetch_open_meteo_recent_summary(dest_geo["lat"], dest_geo["lon"])

    # 인풋 요약 카드
    dest_name = dest_geo["display_name"] if dest_geo else (payload["destination_text"].strip() or "미입력(이러면 추천이 ‘감’이 됨)")
    st.markdown(
        f"""
        <div class="tm-card">
            <div class="tm-section-title">📌 입력 요약</div>
            <div class="tm-tip">
                • 여행시기: <b>{payload["travel_month"]}</b><br/>
                • 인원/관계: <b>{payload["party_count"]}명 · {payload["party_type"]}</b><br/>
                • 여행지: <b>{payload["destination_scope"]} · {dest_name}</b><br/>
                • 방식: <b>{payload["travel_mode"]}</b><br/>
                • 거리 선호: <b>{payload["distance_pref"]}</b> (참고: {distance_comment})<br/>
                • 일정: <b>{payload["duration"]}</b><br/>
                • 스타일: <b>{", ".join(payload["travel_style"]) if payload["travel_style"] else "선택없음(=만능 캐릭터)"}</b><br/>
                • 예산: <b>{payload["budget"]:,}원</b><br/>
                <span class="tm-micro">* 날씨(월 기준): {weather_hint}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if recent_weather:
        st.markdown(
            f"""
            <div class="tm-card">
                <div class="tm-section-title">🌦️ 목적지 최근 7일 날씨 스냅샷(참고용)</div>
                <div class="tm-tip">
                    • 평균 최고기온: <b>{recent_weather["avg_max"]}°C</b><br/>
                    • 평균 최저기온: <b>{recent_weather["avg_min"]}°C</b><br/>
                    • 누적 강수(7일): <b>{recent_weather["total_prcp"]} mm</b><br/>
                    <span class="tm-micro">* ‘월’만 받는 구조라 정확 예보가 아니라 감 잡는 용도!</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # 계획 생성 (OpenAI 키 있으면 AI + 출처, 없으면 룰베이스)
    openai_key = (st.session_state.get("openai_api_key") or "").strip()
    plan = None
    err = None

    with st.spinner("플랜 뽑는 중… (여행 감성 + 동선 최적화 + 현실 체크까지 한 번에)"):
        if openai_key:
            plan, err = call_openai_plan(openai_key, payload)
        if not plan:
            plan = build_rule_based_plan(payload)

    if err:
        st.warning(f"OpenAI 쪽은 실패했지만, 플랜은 룰베이스로라도 ‘일단’ 뽑아왔어! 🛟\n\n사유: {err}")

    # 결과 렌더링
    st.markdown(
        f"""
        <div class="tm-card">
            <div class="tm-section-title">🗺️ 추천 여행 계획</div>
            <h3 style="margin:0;">{plan.get("headline","")}</h3>
            <div class="tm-tip" style="margin-top:.35rem;">{plan.get("summary","")}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Day-by-day
    day_blocks = plan.get("day_blocks", [])
    if day_blocks:
        st.markdown('<div class="tm-section-title">📆 Day-by-Day</div>', unsafe_allow_html=True)
        for b in day_blocks:
            day = b.get("day", "?")
            title = b.get("title", f"Day {day}")
            items = b.get("plan", [])
            with st.expander(f"{title} (Day {day})", expanded=(day == 1)):
                for it in items:
                    st.write(f"- {it}")

    # 팁
    tips = plan.get("tips", [])
    if tips:
        st.markdown('<div class="tm-section-title">🧠 꿀팁(진짜 꿀임)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-card">', unsafe_allow_html=True)
        for t in tips:
            st.write(f"- {t}")
        st.markdown('</div>', unsafe_allow_html=True)

    # 출처
    sources = plan.get("sources", [])
    if sources:
        st.markdown('<div class="tm-section-title">🔎 Sources (참고한 곳)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-card">', unsafe_allow_html=True)
        for s in sources:
            if isinstance(s, dict):
                title = s.get("title", "source")
                url = s.get("url", "")
                note = s.get("note", "")
                if url:
                    st.write(f"- {title} — {url}" + (f" ({note})" if note else ""))
                else:
                    st.write(f"- {title}" + (f" ({note})" if note else ""))
            else:
                st.write(f"- {s}")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.caption("키 없이 생성했거나, 모델이 출처를 못 가져온 경우 Sources는 비어있을 수 있어요.")

    # 다시하기
    nav = st.columns([1, 1, 2])
    with nav[0]:
        if st.button("👈 입력 수정", use_container_width=True):
            st.session_state.step = 1
    with nav[2]:
        if st.button("다시 뽑기 🔄", use_container_width=True):
            # step 유지 + rerun
            st.rerun()


# -----------------------------
# 메인
# -----------------------------
def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🧳", layout="centered")
    init_state()
    render_header()
    sidebar()

    # 페이지 라우팅
    if st.session_state.step == 1:
        page1()
    elif st.session_state.step == 2:
        page2()
    else:
        page3()


if __name__ == "__main__":
    main()
