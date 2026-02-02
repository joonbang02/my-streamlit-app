# app.py
import streamlit as st
import requests
from typing import Dict, List, Tuple, Optional

# -----------------------------
# Page / Theme
# -----------------------------
st.set_page_config(
    page_title="🎬 심리테스트 기반 영화 추천",
    page_icon="🎭",
    layout="wide",
)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_POSTER_BASE = "https://image.tmdb.org/t/p/w500"
UNSPLASH_BASE = "https://api.unsplash.com"
ZENQUOTES_URL = "https://zenquotes.io/api/today"

GENRE_IDS = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
}

GENRE_ICON = {
    "액션": "💥",
    "코미디": "😂",
    "드라마": "🎭",
    "SF": "🛸",
    "로맨스": "💘",
    "판타지": "🪄",
}

UNSPLASH_QUERY_BY_GENRE = {
    "액션": "action movie cinematic",
    "코미디": "funny happy colorful",
    "드라마": "moody cinematic portrait",
    "SF": "sci fi futuristic neon",
    "로맨스": "romantic sunset couple",
    "판타지": "fantasy magical forest",
}

REGIONS = {
    "전체(미지정)": "",
    "한국 (KR)": "KR",
    "미국 (US)": "US",
    "일본 (JP)": "JP",
    "영국 (GB)": "GB",
    "프랑스 (FR)": "FR",
    "독일 (DE)": "DE",
    "인도 (IN)": "IN",
    "스페인 (ES)": "ES",
}

LANGUAGES = {
    "전체(미지정)": "",
    "한국어 (ko)": "ko",
    "영어 (en)": "en",
    "일본어 (ja)": "ja",
    "중국어 (zh)": "zh",
    "프랑스어 (fr)": "fr",
    "스페인어 (es)": "es",
    "독일어 (de)": "de",
    "이탈리아어 (it)": "it",
}

# -----------------------------
# Sleek CSS
# -----------------------------
st.markdown(
    """
<style>
/* Layout tweaks */
.block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1200px; }
div[data-testid="stSidebarContent"] { padding-top: 1.2rem; }

/* Typography */
h1, h2, h3 { letter-spacing: -0.02em; }

/* Top gradient hero */
.hero {
  border-radius: 22px;
  padding: 18px 18px;
  border: 1px solid rgba(0,0,0,0.08);
  background: radial-gradient(1200px 220px at 10% 10%, rgba(30,144,255,0.18), transparent 55%),
              radial-gradient(900px 260px at 90% 30%, rgba(255,105,180,0.12), transparent 55%),
              rgba(255,255,255,0.70);
  box-shadow: 0 16px 50px rgba(0,0,0,0.08);
}

/* Glass section */
.glass {
  border-radius: 20px;
  padding: 16px 16px;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.75);
  box-shadow: 0 12px 36px rgba(0,0,0,0.06);
}

/* AI callout */
.ai-callout {
  border-radius: 18px;
  padding: 14px 14px;
  border: 1px solid rgba(30,144,255,0.25);
  background: linear-gradient(135deg, rgba(30,144,255,0.12), rgba(30,144,255,0.05));
  box-shadow: 0 12px 32px rgba(0,0,0,0.06);
}

/* Movie card */
.movie-card {
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.92);
  box-shadow: 0 12px 34px rgba(0,0,0,0.08);
}
.movie-pad { padding: 12px 12px 10px 12px; }
.movie-title { font-size: 1.05rem; font-weight: 800; margin: 6px 0 2px 0; letter-spacing: -0.02em; }
.muted { color: rgba(0,0,0,0.55); font-size: 0.92rem; }

/* Quote */
.quote {
  border-radius: 18px;
  padding: 14px 14px;
  border: 1px dashed rgba(0,0,0,0.18);
  background: rgba(0,0,0,0.03);
}
.quote .q { font-style: italic; font-size: 1.02rem; line-height: 1.55; }
.quote .a { font-style: italic; font-size: 0.88rem; color: rgba(0,0,0,0.55); margin-top: 8px; }

/* Buttons row */
.btnrow {
  border-radius: 18px;
  padding: 10px 10px;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.68);
}

/* Hide Streamlit default anchors spacing */
[data-testid="stHeader"] { background: rgba(255,255,255,0.0); }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Questions
# -----------------------------
QUESTIONS = [
    {
        "id": "q1",
        "question": "1) 오늘 당신의 에너지 상태는?",
        "options": {
            "🔥 에너지가 넘친다! 뭔가 터뜨리고 싶다": ("액션", "강한 자극과 속도감이 필요해요"),
            "😄 가볍게 웃고 싶다": ("코미디", "부담 없이 즐길 무드가 좋아요"),
            "😌 조용히 몰입하고 싶다": ("드라마", "감정선과 이야기에 집중하고 싶어요"),
            "🧠 새로운 상상/설정이 끌린다": ("SF", "신선한 아이디어와 세계관이 잘 맞아요"),
            "💓 설레는 감정이 필요하다": ("로맨스", "두근거림과 관계 서사가 당겨요"),
            "🪄 현실을 잠깐 잊고 싶다": ("판타지", "마법 같은 탈출감이 필요해요"),
        },
    },
    {
        "id": "q2",
        "question": "2) 영화에서 가장 중요하게 보는 요소는?",
        "options": {
            "폭발/추격/액션 시퀀스": ("액션", "시각적 쾌감과 긴장감이 중요해요"),
            "대사 센스, 웃긴 포인트": ("코미디", "유머 코드가 만족도를 좌우해요"),
            "인물의 성장, 현실적인 이야기": ("드라마", "캐릭터와 서사가 핵심이에요"),
            "미래/우주/기술 같은 설정": ("SF", "설정의 신선함이 가장 끌려요"),
            "케미, 감정선, 관계의 진전": ("로맨스", "감정의 흐름이 중요해요"),
            "마법/전설/이세계 분위기": ("판타지", "현실 밖 세계관이 좋아해요"),
        },
    },
    {
        "id": "q3",
        "question": "3) 당신은 문제를 마주하면 보통?",
        "options": {
            "일단 몸이 먼저 움직인다": ("액션", "결단력과 추진력이 강해요"),
            "분위기부터 풀고 시작한다": ("코미디", "유연함과 낙천성이 장점이에요"),
            "원인과 감정을 천천히 정리한다": ("드라마", "깊이 있는 공감이 강점이에요"),
            "새로운 관점/가설을 세운다": ("SF", "호기심과 사고 실험을 즐겨요"),
            "사람과의 관계를 먼저 챙긴다": ("로맨스", "관계 중심의 감수성이 있어요"),
            "‘만약에’ 시나리오를 상상한다": ("판타지", "상상력이 풍부한 편이에요"),
        },
    },
    {
        "id": "q4",
        "question": "4) 지금 가장 가고 싶은 곳은?",
        "options": {
            "도심 한복판, 화려한 밤거리": ("액션", "강렬한 분위기가 끌려요"),
            "친구들과 북적이는 축제": ("코미디", "사람들과 웃고 떠드는 게 좋아요"),
            "조용한 카페/서점": ("드라마", "잔잔한 공간이 편해요"),
            "우주정거장/미지의 행성": ("SF", "미지 탐험이 로망이에요"),
            "바닷가 노을/야경 산책": ("로맨스", "감정이 올라오는 풍경이 좋아요"),
            "고성/마법 숲/전설의 마을": ("판타지", "동화 같은 장소가 좋아요"),
        },
    },
    {
        "id": "q5",
        "question": "5) 선호하는 전개는?",
        "options": {
            "빠르고 시원한 전개": ("액션", "템포가 빠를수록 몰입돼요"),
            "가볍게 웃기다가 감동 한 스푼": ("코미디", "편안함 속 반전이 좋아요"),
            "천천히 쌓여가는 감정": ("드라마", "축적되는 서사가 좋아요"),
            "‘와 이런 설정이?’ 싶은 반전": ("SF", "아이디어로 승부하는 전개가 좋아요"),
            "설렘→갈등→해소": ("로맨스", "관계의 파도가 재미예요"),
            "모험과 퀘스트, 신비의 단서": ("판타지", "여정형 서사가 잘 맞아요"),
        },
    },
    {
        "id": "q6",
        "question": "6) 보고 나서 남았으면 하는 감정은?",
        "options": {
            "짜릿함/카타르시스": ("액션", "스트레스가 확 풀리는 느낌이 좋아요"),
            "기분전환/상쾌함": ("코미디", "웃고 나면 컨디션이 올라가요"),
            "여운/생각할 거리": ("드라마", "긴 여운이 오래 남는 걸 좋아해요"),
            "호기심/상상력 자극": ("SF", "끝나도 계속 생각나면 좋아요"),
            "따뜻함/두근거림": ("로맨스", "마음이 몽글몽글해지면 좋아요"),
            "경이로움/동심": ("판타지", "현실을 잊게 만드는 감정이 좋아요"),
        },
    },
]

# -----------------------------
# Network helpers
# -----------------------------
def safe_get_json(url: str, params: Optional[Dict] = None) -> Tuple[Optional[object], Optional[str]]:
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)


# -----------------------------
# Analysis
# -----------------------------
def analyze_answers(selected: Dict[str, str]) -> Tuple[str, Dict[str, int], str, List[str]]:
    scores: Dict[str, int] = {g: 0 for g in GENRE_IDS.keys()}
    picked_texts: List[str] = []
    snippets: Dict[str, List[str]] = {g: [] for g in GENRE_IDS.keys()}

    for q in QUESTIONS:
        opt_text = selected.get(q["id"])
        genre, snippet = q["options"][opt_text]
        scores[genre] += 1
        picked_texts.append(f"{q['question']} -> {opt_text}")
        if snippet not in snippets[genre]:
            snippets[genre].append(snippet)

    order = list(GENRE_IDS.keys())
    best_genre = max(order, key=lambda g: (scores[g], -order.index(g)))
    reason_summary = " / ".join(snippets[best_genre][:2]) if snippets[best_genre] else f"{best_genre} 성향이 강해요."
    return best_genre, scores, reason_summary, picked_texts


# -----------------------------
# APIs
# -----------------------------
@st.cache_data(ttl=60 * 30)
def fetch_movies_tmdb(
    api_key: str,
    genre_id: int,
    n: int,
    min_rating: float,
    region: str,
    original_lang: str,
) -> Tuple[List[Dict], Optional[str]]:
    url = f"{TMDB_BASE}/discover/movie"
    params = {
        "api_key": api_key,
        "with_genres": genre_id,
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "include_video": "false",
        "page": 1,
        "vote_average.gte": min_rating,
        "vote_count.gte": 50,
    }
    if region:
        params["region"] = region
    if original_lang:
        params["with_original_language"] = original_lang

    data, err = safe_get_json(url, params=params)
    if err:
        return [], err
    if not isinstance(data, dict) or "results" not in data:
        return [], "TMDB 응답 형식이 예상과 달라요."
    return (data.get("results") or [])[:n], None


@st.cache_data(ttl=60 * 30)
def fetch_unsplash(access_key: str, query: str) -> Tuple[Optional[Dict], Optional[str]]:
    url = f"{UNSPLASH_BASE}/search/photos"
    params = {
        "query": query,
        "client_id": access_key,
        "per_page": 1,
        "orientation": "landscape",
    }
    data, err = safe_get_json(url, params=params)
    if err:
        return None, err
    if not isinstance(data, dict) or "results" not in data:
        return None, "Unsplash 응답 형식이 예상과 달라요."
    results = data.get("results") or []
    return (results[0] if results else None), None


@st.cache_data(ttl=60 * 60)
def fetch_quote_today() -> Tuple[Optional[Dict], Optional[str]]:
    data, err = safe_get_json(ZENQUOTES_URL)
    if err:
        return None, err
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0], None
    return None, "ZenQuotes 응답 형식이 예상과 달라요."


def poster_url(movie: Dict) -> Optional[str]:
    p = movie.get("poster_path")
    return f"{TMDB_POSTER_BASE}{p}" if p else None


# -----------------------------
# OpenAI streaming (typing)
# -----------------------------
def stream_openai_text(openai_key: str, prompt: str, model: str):
    from openai import OpenAI
    client = OpenAI(api_key=openai_key)
    with client.responses.stream(model=model, input=prompt) as stream:
        for event in stream:
            if getattr(event, "type", None) == "response.output_text.delta":
                yield event.delta


def typing_effect(container, text_stream):
    out = container.empty()
    buf = ""
    for chunk in text_stream:
        buf += chunk
        out.markdown(buf)
    return buf


def build_context(picked_texts: List[str], best_genre: str, reason_summary: str) -> str:
    return (
        f"[심리테스트 응답]\n" + "\n".join(picked_texts) + "\n\n"
        f"[결과 장르] {best_genre}\n"
        f"[요약 이유] {reason_summary}\n"
    )


# -----------------------------
# State & Navigation (Question / Result split)
# -----------------------------
if "page" not in st.session_state:
    st.session_state.page = "questions"  # "results"

if "result_payload" not in st.session_state:
    st.session_state.result_payload = None

def go_questions():
    st.session_state.page = "questions"
    st.session_state.result_payload = None
    # 선택값 리셋
    for q in QUESTIONS:
        st.session_state[q["id"]] = None
    st.rerun()

def go_results(payload: Dict):
    st.session_state.page = "results"
    st.session_state.result_payload = payload
    st.rerun()

# -----------------------------
# Sidebar (keys + filters)
# -----------------------------
with st.sidebar:
    st.header("🔑 API Keys")
    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="TMDB 키 입력")
    unsplash_key = st.text_input("Unsplash Access Key", type="password", placeholder="Unsplash 키 입력")
    openai_key = st.text_input("OpenAI API Key", type="password", placeholder="OpenAI 키 입력")
    st.caption("키는 저장되지 않으며, 버튼 클릭 시에만 사용됩니다.")

    st.divider()

    st.header("🎚️ 영화 필터")
    min_rating = st.slider("최소 평점", 0.0, 10.0, 6.5, 0.5)

    region_label = st.selectbox("국가(Region)", list(REGIONS.keys()), index=0)
    lang_label = st.selectbox("원어(Original Language)", list(LANGUAGES.keys()), index=0)
    region = REGIONS[region_label]
    original_lang = LANGUAGES[lang_label]

    st.divider()
    ai_model = st.text_input("OpenAI 모델(선택)", value="gpt-4.1-mini")

# -----------------------------
# Page: Questions
# -----------------------------
if st.session_state.page == "questions":
    st.markdown(
        """
<div class="hero">
  <div style="font-size:1.9rem; font-weight:900;">🎭 오늘의 기분으로 고르는 영화 추천</div>
  <div class="muted" style="margin-top:6px;">
    6개의 질문에 답하면, <b>장르</b>를 분석해 <b>영화 3편</b>과 <b>무드 이미지</b>, <b>오늘의 명언</b>을 보여드려요.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")
    with st.container():
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.subheader("🧩 심리테스트")
        with st.form("psy_test_form"):
            selected: Dict[str, str] = {}
            for q in QUESTIONS:
                selected[q["id"]] = st.radio(
                    q["question"],
                    options=list(q["options"].keys()),
                    index=None,
                    key=q["id"],
                )

            submitted = st.form_submit_button("결과 보기 ✅")

        st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        # validation
        unanswered = [q["question"] for q in QUESTIONS if not selected.get(q["id"])]
        if unanswered:
            st.error("모든 문항에 답변해 주세요!")
            for uq in unanswered:
                st.write(f"- {uq}")
            st.stop()

        # analyze
        best_genre, scores, reason_summary, picked_texts = analyze_answers(selected)
        genre_id = GENRE_IDS[best_genre]

        # fetch movies
        if not tmdb_key:
            st.warning("사이드바에 **TMDB API Key**를 입력하면 영화 추천을 가져올 수 있어요.")
            st.stop()

        with st.spinner("🎥 추천 콘텐츠를 준비 중..."):
            movies, tmdb_err = fetch_movies_tmdb(
                tmdb_key, genre_id, n=3,
                min_rating=min_rating,
                region=region,
                original_lang=original_lang,
            )
            if tmdb_err:
                st.error(f"TMDB 오류: {tmdb_err}")
                st.stop()
            if not movies:
                st.info("조건에 맞는 영화가 없어요. (평점/국가/언어 필터를 낮춰보세요)")
                st.stop()

            # unsplash
            mood_img = None
            mood_err = None
            if unsplash_key:
                mood_query = UNSPLASH_QUERY_BY_GENRE.get(best_genre, "cinematic mood")
                mood_img, mood_err = fetch_unsplash(unsplash_key, mood_query)

            # quote
            quote, quote_err = fetch_quote_today()

        payload = {
            "best_genre": best_genre,
            "scores": scores,
            "reason_summary": reason_summary,
            "picked_texts": picked_texts,
            "movies": movies,
            "mood_img": mood_img,
            "mood_err": mood_err,
            "quote": quote,
            "quote_err": quote_err,
        }
        go_results(payload)

# -----------------------------
# Page: Results
# -----------------------------
else:
    payload = st.session_state.result_payload
    if not payload:
        st.info("결과가 없어요. 테스트 페이지로 이동합니다.")
        go_questions()

    best_genre = payload["best_genre"]
    scores = payload["scores"]
    reason_summary = payload["reason_summary"]
    picked_texts = payload["picked_texts"]
    movies = payload["movies"]
    mood_img = payload["mood_img"]
    mood_err = payload["mood_err"]
    quote = payload["quote"]
    quote_err = payload["quote_err"]

    icon = GENRE_ICON.get(best_genre, "🎬")

    # Header
    st.markdown(
        f"""
<div class="hero">
  <div style="display:flex; align-items:center; gap:12px;">
    <div style="font-size:2.2rem;">{icon}</div>
    <div style="font-size:2.0rem; font-weight:950;">
      당신에게 딱인 장르는 <span style="color:#1E90FF;">{best_genre}</span>!
    </div>
  </div>
  <div class="muted" style="margin-top:8px;">
    {reason_summary} &nbsp; · &nbsp; {" · ".join([f"{g}:{scores[g]}" for g in GENRE_IDS.keys()])}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")

    # AI Analysis
    st.markdown('<div class="section-title">🤖 AI 분석</div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="ai-callout">', unsafe_allow_html=True)
        area = st.container()

        fallback = (
            "당신은 그날의 기분과 원하는 감정(속도감/여운/설렘 등)을 비교적 명확하게 고르는 편이에요. "
            f"오늘은 특히 **{best_genre}**의 몰입감이 스트레스나 공허함을 잘 메워줄 가능성이 높습니다."
        )

        if not openai_key:
            area.markdown(fallback)
        else:
            try:
                ctx = build_context(picked_texts, best_genre, reason_summary)
                prompt = f"""
너는 한국어로 짧고 세련되게 심리테스트 성향을 해석하는 AI야.
아래 정보를 바탕으로 '성향 설명'을 2~3문장으로 작성해줘.
단정/진단처럼 말하지 말고, 부드럽고 구체적으로.

{ctx}

출력은 문장만(불릿/번호 없이).
""".strip()
                typing_effect(area, stream_openai_text(openai_key, prompt, model=ai_model))
            except Exception as e:
                area.markdown(fallback)
                area.caption(f"(OpenAI 호출 실패: {e})")

        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # Movies grid
    st.markdown('<div class="section-title">🎞️ 추천 영화 3편</div>', unsafe_allow_html=True)
    cols = st.columns(3, gap="large")
    for i, m in enumerate(movies):
        title = m.get("title") or "제목 정보 없음"
        vote = m.get("vote_average")
        vote_str = f"{vote:.1f}/10" if isinstance(vote, (int, float)) else "정보 없음"
        release = m.get("release_date") or "개봉일 정보 없음"
        overview = (m.get("overview") or "").strip() or "줄거리 정보가 없습니다."
        purl = poster_url(m)

        with cols[i]:
            st.markdown('<div class="movie-card">', unsafe_allow_html=True)
            if purl:
                st.image(purl, use_container_width=True)
            else:
                st.info("포스터 없음")

            st.markdown('<div class="movie-pad">', unsafe_allow_html=True)
            st.markdown(f'<div class="movie-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="muted">⭐ 평점: <b>{vote_str}</b></div>', unsafe_allow_html=True)

            with st.expander("상세 정보 / 추천 이유"):
                st.write(f"📅 개봉일: **{release}**")
                st.write("📝 줄거리")
                st.write(overview)

                st.write("💡 추천 이유")
                if not openai_key:
                    st.write(f"당신의 **{best_genre}** 성향( {reason_summary} )과 잘 맞아서 추천해요.")
                else:
                    try:
                        ctx = build_context(picked_texts, best_genre, reason_summary)
                        prompt = f"""
너는 한국어로 '왜 이 영화를 추천하는지'를 1~2문장으로 설명하는 AI야.
사용자 성향과 장르 결과를 고려해, 아래 영화에 대해 짧게 말해줘.
너무 과장하지 말고, 자연스럽게.

{ctx}

[영화]
제목: {title}
평점: {vote}
개봉: {release}
""".strip()
                        typing_effect(st, stream_openai_text(openai_key, prompt, model=ai_model))
                    except Exception:
                        st.write(f"당신의 **{best_genre}** 무드에 맞는 템포/감정선을 가진 작품이라 추천해요.")

            st.markdown("</div>", unsafe_allow_html=True)  # movie-pad
            st.markdown("</div>", unsafe_allow_html=True)  # movie-card

    st.divider()

    # Mood + Quote
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown('<div class="section-title">🌄 오늘의 무드</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="glass">', unsafe_allow_html=True)
            if mood_err:
                st.error(f"Unsplash 오류: {mood_err}")
            elif not mood_img:
                st.info("Unsplash 키가 없거나 검색 결과가 없어요.")
            else:
                image_url = mood_img.get("urls", {}).get("regular")
                photographer = mood_img.get("user", {}).get("name", "Unknown")
                if image_url:
                    st.image(image_url, use_container_width=True)
                    st.caption(f"Photo by {photographer} (Unsplash)")
                else:
                    st.info("이미지 URL을 찾지 못했어요.")
            st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-title">💬 오늘의 명언</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="glass">', unsafe_allow_html=True)

            quote_text = ""
            quote_author = ""
            if quote_err or not quote:
                st.error(f"ZenQuotes 오류: {quote_err or '명언을 가져오지 못했어요.'}")
            else:
                quote_text = quote.get("q", "")
                quote_author = quote.get("a", "")
                st.markdown(
                    f"""
<div class="quote">
  <div class="q">“{quote_text}”</div>
  <div class="a">— {quote_author}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

            st.write("")
            st.markdown("**🧠 오늘의 해석**")

            if not openai_key or not quote_text:
                st.write("오늘은 마음의 리듬을 지키면서, 딱 한 가지 행동만 가볍게 실천해보면 좋아요.")
            else:
                try:
                    ctx = build_context(picked_texts, best_genre, reason_summary)
                    prompt = f"""
너는 한국어로 명언을 '사용자 성향'에 맞춰 1문장으로 해석하는 AI야.
반드시 1문장, 존댓말, 자연스럽게(오글거림 금지).

{ctx}

[명언]
{quote_text} — {quote_author}
""".strip()
                    typing_effect(st, stream_openai_text(openai_key, prompt, model=ai_model))
                except Exception:
                    st.write("오늘은 무리하지 말고, 지금의 흐름을 한 번만 더 이어가보세요.")

            st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # Bottom buttons
    st.markdown('<div class="btnrow">', unsafe_allow_html=True)
    b1, b2, b3 = st.columns([1, 1, 2], gap="medium")
    with b1:
        if st.button("🔄 다시 테스트하기", use_container_width=True):
            go_questions()
    with b2:
        share_clicked = st.button("📣 결과 공유하기", use_container_width=True)
    with b3:
        if share_clicked:
            titles = [m.get("title", "") for m in movies]
            qtext = quote.get("q", "") if quote else ""
            qauth = quote.get("a", "") if quote else ""
            share_text = (
                f"{GENRE_ICON.get(best_genre,'🎬')} 결과 장르: {best_genre}\n"
                f"추천 영화: {', '.join([t for t in titles if t])}\n"
                f"오늘의 명언: “{qtext}” — {qauth}\n"
            )
            st.text_area("공유용 텍스트(복사해서 사용)", value=share_text, height=110)
    st.markdown("</div>", unsafe_allow_html=True)
