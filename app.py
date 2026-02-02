# app.py
import streamlit as st
import requests
from typing import Dict, List, Tuple, Optional

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="🎭 심리테스트 기반 영화 추천 (TMDB + Unsplash + ZenQuotes + OpenAI)",
    page_icon="🎬",
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
    "드라마": "moody film still portrait",
    "SF": "sci fi futuristic neon",
    "로맨스": "romantic couple sunset",
    "판타지": "fantasy magical forest",
}

# 사이드바 국가/언어 옵션(필요하면 더 추가 가능)
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
# CSS (카드 스타일 + 콜아웃)
# -----------------------------
st.markdown(
    """
<style>
/* 전체 폭에서 카드 간격 조금 넉넉하게 */
.block-container { padding-top: 1.2rem; }

/* 파란 콜아웃 */
.ai-callout {
  background: linear-gradient(135deg, rgba(30,144,255,0.10), rgba(30,144,255,0.05));
  border: 1px solid rgba(30,144,255,0.25);
  border-radius: 16px;
  padding: 16px 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
}

/* 영화 카드 */
.movie-card {
  border-radius: 18px;
  border: 1px solid rgba(0,0,0,0.08);
  box-shadow: 0 10px 28px rgba(0,0,0,0.08);
  padding: 14px;
  background: rgba(255,255,255,0.90);
}

.movie-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 8px 0 4px 0;
}

.small-muted {
  color: rgba(0,0,0,0.55);
  font-size: 0.90rem;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 800;
  margin: 0.2rem 0 0.6rem 0;
}

.quote-box {
  padding: 14px 14px;
  border-radius: 16px;
  border: 1px dashed rgba(0,0,0,0.18);
  background: rgba(0,0,0,0.02);
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# 심리테스트 질문
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
            "마법/전설/이세계 분위기": ("판타지", "현실 밖 세계관이 좋아요"),
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
# 유틸
# -----------------------------
def safe_get_json(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Tuple[Optional[object], Optional[str]]:
    try:
        r = requests.get(url, params=params, headers=headers, timeout=12)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)


def analyze_answers(selected: Dict[str, str]) -> Tuple[str, Dict[str, int], str, List[str]]:
    scores: Dict[str, int] = {g: 0 for g in GENRE_IDS.keys()}
    picked: List[Tuple[str, str]] = []
    picked_texts: List[str] = []

    for q in QUESTIONS:
        opt_text = selected.get(q["id"])
        if not opt_text:
            continue
        genre, snippet = q["options"][opt_text]
        scores[genre] += 1
        picked.append((genre, snippet))
        picked_texts.append(f"{q['question']} -> {opt_text}")

    order = list(GENRE_IDS.keys())
    best_genre = max(order, key=lambda g: (scores[g], -order.index(g)))

    matched = []
    for genre, snippet in picked:
        if genre == best_genre and snippet not in matched:
            matched.append(snippet)

    reason_summary = " / ".join(matched[:2]) if matched else f"당신의 선택이 **{best_genre}** 분위기와 잘 맞아요."
    return best_genre, scores, reason_summary, picked_texts


# -----------------------------
# TMDB / Unsplash / ZenQuotes
# -----------------------------
@st.cache_data(ttl=60 * 30)
def fetch_movies_tmdb_discover(
    api_key: str,
    genre_id: int,
    n: int = 3,
    min_rating: float = 0.0,
    region: str = "",
    original_lang: str = "",
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
        "vote_count.gte": 50,  # 평점 신뢰도 보정(원하면 조정)
    }
    if region:
        params["region"] = region
    if original_lang:
        params["with_original_language"] = original_lang

    data, err = safe_get_json(url, params=params)
    if err:
        return [], err
    if not isinstance(data, dict) or "results" not in data:
        return [], "TMDB 응답 형식이 예상과 달라요. API Key/호출 제한을 확인해주세요."
    results = data.get("results") or []
    return results[:n], None


@st.cache_data(ttl=60 * 30)
def fetch_unsplash_image(access_key: str, query: str) -> Tuple[Optional[Dict], Optional[str]]:
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
def fetch_zenquote_today() -> Tuple[Optional[Dict], Optional[str]]:
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
# OpenAI (스트리밍 타이핑 효과)
# -----------------------------
def stream_openai_text(openai_key: str, prompt: str, model: str = "gpt-4.1-mini"):
    """
    openai python SDK(v1) 기반 스트리밍.
    환경에 SDK가 없으면 ImportError -> 예외로 처리.
    """
    from openai import OpenAI

    client = OpenAI(api_key=openai_key)
    # Responses API 스트리밍 (SDK 버전에 따라 동작)
    with client.responses.stream(
        model=model,
        input=prompt,
    ) as stream:
        for event in stream:
            # 텍스트 델타 이벤트
            if getattr(event, "type", None) == "response.output_text.delta":
                yield event.delta
        # stream.get_final_response()  # 필요 시 사용


def typing_effect(container, text_stream):
    """
    Streamlit typing effect helper
    """
    out = container.empty()
    buf = ""
    for chunk in text_stream:
        buf += chunk
        out.markdown(buf)
    return buf


def build_user_profile_context(picked_texts: List[str], best_genre: str, reason_summary: str) -> str:
    return (
        f"[심리테스트 응답]\n" + "\n".join(picked_texts) + "\n\n"
        f"[결과 장르] {best_genre}\n"
        f"[요약 이유] {reason_summary}\n"
    )


# -----------------------------
# 세션 초기화/리셋
# -----------------------------
def reset_test():
    for q in QUESTIONS:
        if q["id"] in st.session_state:
            st.session_state[q["id"]] = None
    st.session_state["submitted_once"] = False
    st.rerun()


# -----------------------------
# 사이드바
# -----------------------------
with st.sidebar:
    st.header("🔑 API Keys")
    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="TMDB 키 입력")
    unsplash_key = st.text_input("Unsplash Access Key", type="password", placeholder="Unsplash 키 입력")
    openai_key = st.text_input("OpenAI API Key", type="password", placeholder="OpenAI 키 입력")

    st.divider()

    st.header("🎚️ 영화 필터")
    min_rating = st.slider("최소 평점 (vote_average.gte)", 0.0, 10.0, 6.5, 0.5)

    region_label = st.selectbox("국가(Region)", list(REGIONS.keys()), index=0)
    lang_label = st.selectbox("원어(Original Language)", list(LANGUAGES.keys()), index=0)

    region = REGIONS[region_label]
    original_lang = LANGUAGES[lang_label]

    st.caption("TMDB Discover 기준으로 필터링합니다. (인기순 + 최소 평점 + 국가/언어)")

    st.divider()
    ai_model = st.text_input("OpenAI 모델(선택)", value="gpt-4.1-mini")
    st.caption("모델명은 계정/환경에 따라 다를 수 있어요.")

# -----------------------------
# 메인
# -----------------------------
st.title("🎬 심리테스트로 영화 추천")
st.write("결과 보기 버튼을 누르면 **TMDB 영화 3편 + Unsplash 무드 이미지 1장 + 오늘의 명언 + AI 해석**을 보여줍니다.")

st.divider()

# 설문 폼
with st.form("psy_test_form"):
    st.subheader("🧩 심리테스트")
    selected: Dict[str, str] = {}

    for q in QUESTIONS:
        selected[q["id"]] = st.radio(
            q["question"],
            options=list(q["options"].keys()),
            index=None,
            key=q["id"],
        )

    submitted = st.form_submit_button("결과 보기 ✅")

# 상태값(공유용)
if "submitted_once" not in st.session_state:
    st.session_state["submitted_once"] = False

if submitted:
    st.session_state["submitted_once"] = True

if st.session_state["submitted_once"]:
    # 응답 검증
    unanswered = [q["question"] for q in QUESTIONS if not selected.get(q["id"])]
    if unanswered:
        st.error("모든 문항에 답변해 주세요!")
        for uq in unanswered:
            st.write(f"- {uq}")
        st.stop()

    # 장르 분석
    best_genre, scores, reason_summary, picked_texts = analyze_answers(selected)
    genre_id = GENRE_IDS[best_genre]
    icon = GENRE_ICON.get(best_genre, "🎬")

    # -----------------------------
    # 헤더: 장르 아이콘 + 타이틀
    # -----------------------------
    with st.container():
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:12px;">
              <div style="font-size:2.0rem;">{icon}</div>
              <div style="font-size:1.8rem; font-weight:900;">
                당신에게 딱인 장르는 <span style="color:#1E90FF;">{best_genre}</span>!
              </div>
            </div>
            <div class="small-muted" style="margin-top:6px;">
              {reason_summary}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # -----------------------------
    # TMDB 영화 3편
    # -----------------------------
    if not tmdb_key:
        st.warning("사이드바에 **TMDB API Key**를 입력하면 영화 추천을 가져올 수 있어요.")
        st.stop()

    with st.spinner("🎥 TMDB에서 추천 영화를 가져오는 중..."):
        movies, tmdb_err = fetch_movies_tmdb_discover(
            tmdb_key,
            genre_id,
            n=3,
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

    # -----------------------------
    # AI 분석(파란 callout)
    # -----------------------------
    st.markdown('<div class="section-title">🤖 AI 분석</div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="ai-callout">', unsafe_allow_html=True)

        ai_area = st.container()
        fallback = (
            "AI 키가 없어서 기본 문구로 표시해요. "
            "당신은 지금의 기분/취향에 맞춰 장르를 고르는 편이고, "
            "오늘은 그중에서도 이 장르의 몰입감이 잘 맞는 날이에요."
        )

        if not openai_key:
            ai_area.markdown(fallback)
        else:
            try:
                ctx = build_user_profile_context(picked_texts, best_genre, reason_summary)
                prompt_personality = f"""
너는 한국어로 짧고 따뜻하게 심리테스트 결과를 해석하는 AI야.
아래 정보를 보고, '사용자 성향 설명'을 2~3문장으로 작성해줘.
과장/단정은 피하고, 부드럽고 구체적으로.

{ctx}

출력은 문장만(불릿/번호 없이) 작성해줘.
""".strip()

                typing_effect(
                    ai_area,
                    stream_openai_text(openai_key, prompt_personality, model=ai_model),
                )
            except Exception as e:
                ai_area.markdown(fallback)
                ai_area.caption(f"(OpenAI 호출 실패: {e})")

        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # -----------------------------
    # 영화 카드 3열 그리드 + expander
    # -----------------------------
    st.markdown('<div class="section-title">🎞️ 추천 영화 3편</div>', unsafe_allow_html=True)

    cols = st.columns(3, gap="large")

    # 영화 추천 이유(1~2문장): 전체 공통 요약 + 각 영화 1문장(옵션)
    overall_reason = ""
    per_movie_reason: Dict[str, str] = {}

    if openai_key:
        try:
            ctx = build_user_profile_context(picked_texts, best_genre, reason_summary)
            movie_brief = "\n".join(
                [
                    f"- {m.get('title','')} (평점 {m.get('vote_average','?')}, 개봉 {m.get('release_date','?')})"
                    for m in movies
                ]
            )
            prompt_movie_reason = f"""
너는 한국어로 영화 추천 이유를 간단히 설명하는 AI야.
아래 사용자 성향과 추천 영화 목록을 보고,
1) 전체 추천 이유를 1~2문장으로,
2) 각 영화별로 1문장씩(총 3개) 이유를 작성해줘.

형식은 정확히 아래처럼:
[전체]
...문장...
[영화별]
영화제목: ...문장...
영화제목: ...문장...
영화제목: ...문장...

{ctx}

[추천 영화]
{movie_brief}
""".strip()

            # 스트리밍으로 받아서 파싱(가볍게)
            tmp = st.empty()
            buf = ""

            try:
                for chunk in stream_openai_text(openai_key, prompt_movie_reason, model=ai_model):
                    buf += chunk
                    tmp.markdown(buf)
            finally:
                # 화면에 남기지 않고(중복 방지) 파싱 후 지움
                tmp.empty()

            # 파싱
            # 매우 단순 파서: 섹션별 분리
            if "[전체]" in buf and "[영화별]" in buf:
                part1 = buf.split("[영화별]")[0]
                overall_reason = part1.replace("[전체]", "").strip()

                part2 = buf.split("[영화별]")[1].strip()
                for line in part2.splitlines():
                    if ":" in line:
                        title, reason = line.split(":", 1)
                        per_movie_reason[title.strip()] = reason.strip()

        except Exception:
            pass

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

            st.markdown(f'<div class="movie-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="small-muted">⭐ 평점: <b>{vote_str}</b></div>', unsafe_allow_html=True)

            with st.expander("상세 보기"):
                st.write(f"📅 개봉일: **{release}**")
                st.write("📝 줄거리")
                st.write(overview)

                st.write("💡 추천하는 이유")
                # 영화별 이유 우선, 없으면 전체 이유를 사용
                reason = per_movie_reason.get(title) or overall_reason
                if reason:
                    st.write(reason)
                else:
                    st.write("당신의 현재 성향과 장르 취향에 잘 맞는 작품이라 추천해요.")

            st.markdown("</div>", unsafe_allow_html=True)

    if overall_reason:
        st.caption(f"AI 추천 요약: {overall_reason}")

    st.divider()

    # -----------------------------
    # 분위기 섹션: 이미지 크게 + 제목
    # -----------------------------
    mood_left, mood_right = st.columns([3, 2], gap="large")

    with mood_left:
        st.markdown('<div class="section-title">🌄 오늘의 무드</div>', unsafe_allow_html=True)

        if not unsplash_key:
            st.warning("사이드바에 **Unsplash Access Key**를 입력하면 무드 이미지를 가져올 수 있어요.")
        else:
            query = UNSPLASH_QUERY_BY_GENRE.get(best_genre, "cinematic mood")
            with st.spinner("🖼️ Unsplash에서 무드 이미지를 가져오는 중..."):
                img, un_err = fetch_unsplash_image(unsplash_key, query)

            if un_err:
                st.error(f"Unsplash 오류: {un_err}")
            else:
                if img:
                    image_url = img.get("urls", {}).get("regular")
                    photographer = img.get("user", {}).get("name", "Unknown")
                    if image_url:
                        st.image(image_url, use_container_width=True)
                        st.caption(f"Photo by {photographer} (Unsplash)")
                    else:
                        st.info("이미지 URL을 찾지 못했어요.")
                else:
                    st.info("검색 결과가 없어요. (장르 무드 검색어가 너무 좁을 수 있어요)")

    # -----------------------------
    # 명언 섹션: 이탤릭 + 저자 작은 글씨 + AI 해석(1문장)
    # -----------------------------
    with mood_right:
        st.markdown('<div class="section-title">💬 오늘의 명언</div>', unsafe_allow_html=True)

        with st.spinner("📝 ZenQuotes에서 명언을 가져오는 중..."):
            quote, z_err = fetch_zenquote_today()

        if z_err or not quote:
            st.error(f"ZenQuotes 오류: {z_err or '명언을 가져오지 못했어요.'}")
            quote_text = ""
            quote_author = ""
        else:
            quote_text = quote.get("q", "")
            quote_author = quote.get("a", "")

            st.markdown(
                f"""
<div class="quote-box">
  <div style="font-style: italic; font-size: 1.02rem;">“{quote_text}”</div>
  <div class="small-muted" style="margin-top:8px; font-style: italic;">— {quote_author}</div>
</div>
""",
                unsafe_allow_html=True,
            )

        st.write("")  # 여백

        st.markdown("**🧠 명언을 당신 성향에 맞게 해석**")
        if not openai_key or not quote_text:
            st.write("오늘은 너무 무겁게 끌고 가지 말고, 지금의 흐름을 자연스럽게 이어가면 좋아요.")
        else:
            try:
                ctx = build_user_profile_context(picked_texts, best_genre, reason_summary)
                prompt_quote = f"""
너는 한국어로 명언을 '사용자 성향'에 맞게 1문장으로 해석하는 AI야.
아래 사용자 성향/결과를 참고해서, 명언을 오늘의 행동/마음가짐으로 연결해줘.
반드시 1문장, 존댓말, 너무 오글거리게 말하지 않기.

{ctx}

[오늘의 명언]
{quote_text} — {quote_author}
""".strip()

                placeholder = st.container()
                typing_effect(placeholder, stream_openai_text(openai_key, prompt_quote, model=ai_model))
            except Exception as e:
                st.write("오늘은 당신의 리듬을 지키는 게 제일 중요해요—무리하지 말고 한 걸음만 가보세요.")
                st.caption(f"(OpenAI 호출 실패: {e})")

    st.divider()

    # -----------------------------
    # 하단 버튼: 다시 테스트하기 + 결과 공유하기
    # -----------------------------
    b1, b2, b3 = st.columns([1, 1, 2], gap="medium")

    with b1:
        if st.button("🔄 다시 테스트하기", use_container_width=True):
            reset_test()

    with b2:
        share_clicked = st.button("📣 결과 공유하기", use_container_width=True)

    with b3:
        # 공유 텍스트(버튼 누르면 표시)
        if share_clicked:
            titles = [m.get("title", "") for m in movies]
            share_text = (
                f"{GENRE_ICON.get(best_genre,'🎬')} 심리테스트 결과: {best_genre}\n"
                f"추천 영화: {', '.join([t for t in titles if t])}\n"
                f"오늘의 명언: “{quote_text}” — {quote_author}\n"
            )
            st.text_area("공유용 텍스트(복사해서 사용하세요)", value=share_text, height=120)

else:
    st.info("모든 문항에 답한 뒤 **결과 보기 ✅** 버튼을 눌러주세요.")
