# app.py
import streamlit as st
import requests
from typing import Dict, List, Tuple, Optional

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="🎭 심리테스트 기반 영화 추천 (TMDB + Unsplash + ZenQuotes)",
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

# 분위기 이미지 검색어(장르 -> Unsplash query)
UNSPLASH_QUERY_BY_GENRE = {
    "액션": "action movie cinematic",
    "코미디": "funny happy colorful",
    "드라마": "moody film still portrait",
    "SF": "sci fi futuristic neon",
    "로맨스": "romantic couple sunset",
    "판타지": "fantasy magical forest",
}

# -----------------------------
# 심리테스트 질문 구성
# 각 선택지: (장르, 이유 한 줄)
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
# 네트워크 유틸
# -----------------------------
def safe_get_json(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Tuple[Optional[Dict], Optional[str]]:
    try:
        r = requests.get(url, params=params, headers=headers, timeout=12)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)


# -----------------------------
# TMDB
# -----------------------------
@st.cache_data(ttl=60 * 30)
def fetch_movies_tmbd_by_genre(api_key: str, genre_id: int, n: int = 3) -> Tuple[List[Dict], Optional[str]]:
    url = f"{TMDB_BASE}/discover/movie"
    params = {
        "api_key": api_key,
        "with_genres": genre_id,
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "include_video": "false",
        "page": 1,
    }
    data, err = safe_get_json(url, params=params)
    if err:
        return [], err
    if not isinstance(data, dict) or "results" not in data:
        return [], "TMDB 응답 형식이 예상과 달라요. API Key/호출 제한을 확인해주세요."
    results = data.get("results") or []
    return results[:n], None


# -----------------------------
# Unsplash
# -----------------------------
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
    if not results:
        return None, None
    return results[0], None


# -----------------------------
# ZenQuotes
# -----------------------------
@st.cache_data(ttl=60 * 60)
def fetch_zenquote_today() -> Tuple[Optional[Dict], Optional[str]]:
    data, err = safe_get_json(ZENQUOTES_URL)
    if err:
        return None, err
    # ZenQuotes는 보통 리스트로 내려옴: [{"q":"...", "a":"..."}]
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict):
            return item, None
    return None, "ZenQuotes 응답 형식이 예상과 달라요."


# -----------------------------
# 심리테스트 분석
# -----------------------------
def analyze_answers(selected: Dict[str, str]) -> Tuple[str, Dict[str, int], str]:
    scores: Dict[str, int] = {g: 0 for g in GENRE_IDS.keys()}
    picked: List[Tuple[str, str]] = []

    for q in QUESTIONS:
        opt_text = selected.get(q["id"])
        if not opt_text:
            continue
        genre, snippet = q["options"][opt_text]
        scores[genre] += 1
        picked.append((genre, snippet))

    order = list(GENRE_IDS.keys())
    best_genre = max(order, key=lambda g: (scores[g], -order.index(g)))

    matched = []
    for genre, snippet in picked:
        if genre == best_genre and snippet not in matched:
            matched.append(snippet)

    reason_summary = " / ".join(matched[:2]) if matched else f"당신의 선택이 **{best_genre}** 분위기와 잘 맞아요."
    return best_genre, scores, reason_summary


def k_movie_card(movie: Dict, best_genre: str) -> Dict[str, str]:
    title = movie.get("title") or "제목 정보 없음"
    vote = movie.get("vote_average")
    poster_path = movie.get("poster_path")
    poster_url = f"{TMDB_POSTER_BASE}{poster_path}" if poster_path else None
    vote_str = f"{vote:.1f}/10" if isinstance(vote, (int, float)) else "정보 없음"
    return {
        "title": title,
        "vote": vote_str,
        "poster_url": poster_url,
    }


# -----------------------------
# 사이드바: 키 입력
# -----------------------------
with st.sidebar:
    st.header("🔑 API Keys")
    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="TMDB 키 입력")
    unsplash_key = st.text_input("Unsplash Access Key", type="password", placeholder="Unsplash 키 입력")
    st.caption("키는 저장되지 않으며, 버튼을 누를 때만 API 호출에 사용됩니다.")

# -----------------------------
# 메인 UI
# -----------------------------
st.title("🎬 심리테스트로 영화 추천")
st.write("답변을 기반으로 장르를 결정하고, **TMDB 영화 3편 + Unsplash 분위기 이미지 1장 + 오늘의 명언**을 보여줍니다.")

st.divider()

# 설문(폼)
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

if submitted:
    # 응답 검증
    unanswered = [q["question"] for q in QUESTIONS if not selected.get(q["id"])]
    if unanswered:
        st.error("모든 문항에 답변해 주세요!")
        for uq in unanswered:
            st.write(f"- {uq}")
        st.stop()

    # 장르 분석
    best_genre, scores, reason_summary = analyze_answers(selected)
    genre_id = GENRE_IDS[best_genre]

    # 상단: 타이틀 + 장르 결과
    st.subheader("✨ 당신의 결과")
    top1, top2 = st.columns([1, 2], vertical_alignment="center")
    with top1:
        st.metric("추천 장르", best_genre)
    with top2:
        st.write(f"**요약:** {reason_summary}")
        st.caption(" · ".join([f"{g}: {scores[g]}" for g in GENRE_IDS.keys()]))

    st.divider()

    # TMDB 영화 3편
    if not tmdb_key:
        st.warning("사이드바에 **TMDB API Key**를 입력하면 영화 추천을 가져올 수 있어요.")
        st.stop()

    with st.spinner("🎥 TMDB에서 영화 추천을 가져오는 중..."):
        movies, tmdb_err = fetch_movies_tmbd_by_genre(tmdb_key, genre_id, n=3)

    if tmdb_err:
        st.error(f"TMDB 오류: {tmdb_err}")
        st.stop()

    if not movies:
        st.info("TMDB에서 영화를 가져오지 못했어요. 장르/키/호출 제한을 확인해주세요.")
        st.stop()

    st.subheader("🎞️ 추천 영화 3편")
    cols = st.columns(3, gap="large")

    for i, movie in enumerate(movies[:3]):
        card = k_movie_card(movie, best_genre)
        with cols[i]:
            with st.container(border=True):
                if card["poster_url"]:
                    st.image(card["poster_url"], use_container_width=True)
                else:
                    st.info("포스터 없음")
                st.markdown(f"#### {card['title']}")
                st.write(f"⭐ 평점: **{card['vote']}**")

    st.divider()

    # 하단: 분위기 이미지 + 명언
    bottom_left, bottom_right = st.columns([3, 2], gap="large")

    # Unsplash 분위기 이미지
    with bottom_left:
        st.subheader("🖼️ 오늘의 분위기 이미지")
        if not unsplash_key:
            st.warning("사이드바에 **Unsplash Access Key**를 입력하면 분위기 이미지를 가져올 수 있어요.")
        else:
            query = UNSPLASH_QUERY_BY_GENRE.get(best_genre, "cinematic mood")
            with st.spinner("🌄 Unsplash에서 분위기 이미지를 가져오는 중..."):
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
                    st.info("검색 결과가 없어요. 다른 키워드를 시도해볼까요?")

    # ZenQuotes 명언
    with bottom_right:
        st.subheader("💬 오늘의 명언")
        with st.spinner("📝 ZenQuotes에서 명언을 가져오는 중..."):
            quote, z_err = fetch_zenquote_today()

        if z_err:
            st.error(f"ZenQuotes 오류: {z_err}")
        else:
            if quote:
                q = quote.get("q", "명언을 가져오지 못했어요.")
                a = quote.get("a", "")
                st.markdown(
                    f"""
                    > {q}
                    >
                    > — **{a}**
                    """
                )
            else:
                st.info("명언 정보를 가져오지 못했어요.")

else:
    st.info("모든 문항에 답한 뒤 **결과 보기 ✅** 버튼을 눌러주세요.")
