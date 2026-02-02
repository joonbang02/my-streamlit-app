# app.py
import streamlit as st
import requests
from typing import Dict, List, Tuple, Optional

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="🎭 심리테스트 기반 영화 추천 (TMDB)",
    page_icon="🎬",
    layout="wide",
)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_POSTER_BASE = "https://image.tmdb.org/t/p/w500"

GENRE_IDS = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
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
# TMDB 호출 유틸
# -----------------------------
def _safe_get_json(url: str, params: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)


@st.cache_data(ttl=60 * 30)  # 30분 캐시
def fetch_popular_movies_by_genre(api_key: str, genre_id: int, n: int = 5) -> Tuple[List[Dict], Optional[str]]:
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
    data, err = _safe_get_json(url, params)
    if err:
        return [], err

    if not isinstance(data, dict) or "results" not in data:
        return [], "TMDB 응답 형식이 예상과 달라요. API Key와 호출 제한을 확인해주세요."

    results = data.get("results") or []
    return results[:n], None


# -----------------------------
# 심리테스트 분석
# -----------------------------
def analyze_answers(selected: Dict[str, str]) -> Tuple[str, Dict[str, int], str]:
    """
    selected: {question_id: option_text}
    return: (best_genre, scores, reason_summary)
    """
    scores: Dict[str, int] = {g: 0 for g in GENRE_IDS.keys()}
    matched_reasons: List[str] = []

    # 각 문항에서 선택된 옵션의 장르를 +1
    # 최종 장르에 해당하는 이유 스니펫도 모으기 위해 우선 전체를 저장
    picked: List[Tuple[str, str]] = []  # (genre, reason_snippet)
    for q in QUESTIONS:
        qid = q["id"]
        opt_text = selected.get(qid)
        if not opt_text:
            continue
        genre, snippet = q["options"][opt_text]
        picked.append((genre, snippet))
        scores[genre] += 1

    # 최고 점수 장르 결정 (동점이면 미리 정의된 순서로 결정)
    order = list(GENRE_IDS.keys())
    best_genre = max(order, key=lambda g: (scores[g], -order.index(g)))

    # 최종 장르와 일치하는 이유 스니펫을 최대 2개까지 조합
    for genre, snippet in picked:
        if genre == best_genre and snippet not in matched_reasons:
            matched_reasons.append(snippet)

    if matched_reasons:
        reason_summary = " / ".join(matched_reasons[:2])
    else:
        # 혹시라도 매칭이 비면 장르별 기본 문구
        default_reason = {
            "액션": "속도감 있는 전개와 강렬한 장면을 즐기는 성향이에요",
            "코미디": "가볍게 웃으며 스트레스를 푸는 게 잘 맞아요",
            "드라마": "인물과 감정선에 몰입하는 타입이에요",
            "SF": "새로운 설정과 아이디어에 끌리는 성향이에요",
            "로맨스": "설렘과 관계 서사가 중요한 타입이에요",
            "판타지": "현실을 벗어난 세계관에서 힐링하는 타입이에요",
        }
        reason_summary = default_reason.get(best_genre, "당신의 취향에 딱 맞는 장르예요")

    return best_genre, scores, reason_summary


def movie_recommend_reason(best_genre: str, movie: Dict, test_reason: str) -> str:
    """
    영화별 추천 이유: 테스트 결과 + 장르 성향 + 평점 요소를 섞어서 간단히
    """
    base = f"테스트 결과가 **{best_genre}** 성향이라서 추천해요. ({test_reason})"
    vote = movie.get("vote_average")
    if isinstance(vote, (int, float)) and vote >= 7.5:
        return base + f" 게다가 평점이 **{vote:.1f}**로 높은 편이에요."
    if isinstance(vote, (int, float)) and vote >= 6.8:
        return base + f" 평점도 **{vote:.1f}**로 무난하게 좋습니다."
    return base


# -----------------------------
# UI
# -----------------------------
st.title("🎭 심리테스트로 고르는 🎬 영화 추천 (TMDB)")

with st.sidebar:
    st.header("🔑 TMDB 설정")
    TMDB_API_KEY = st.text_input("TMDB API Key", type="password", placeholder="여기에 입력")
    st.caption("TMDB API Key는 저장되지 않으며, 추천 버튼을 눌렀을 때만 사용됩니다.")

st.write("간단한 심리테스트 답변을 바탕으로 **당신에게 어울리는 장르**를 고르고, TMDB에서 **해당 장르 인기 영화 5개**를 가져와 추천합니다.")

st.divider()

# 설문 폼
with st.form("psy_test_form"):
    st.subheader("🧩 심리테스트")
    selected: Dict[str, str] = {}

    for q in QUESTIONS:
        options = list(q["options"].keys())
        selected[q["id"]] = st.radio(
            q["question"],
            options=options,
            index=None,  # 선택 강제
            key=q["id"],
        )

    submitted = st.form_submit_button("결과 보기 ✅")

# 결과 처리
if submitted:
    # 1) 응답 검증
    unanswered = [q["question"] for q in QUESTIONS if not selected.get(q["id"])]
    if unanswered:
        st.error("모든 문항에 답변해 주세요!")
        for uq in unanswered:
            st.write(f"- {uq}")
        st.stop()

    # 2) 장르 결정
    best_genre, scores, test_reason = analyze_answers(selected)
    genre_id = GENRE_IDS[best_genre]

    # 3) TMDB 키 확인
    if not TMDB_API_KEY:
        st.warning("사이드바에 TMDB API Key를 입력하면 영화 추천을 가져올 수 있어요.")
        st.stop()

    # 4) TMDB에서 영화 5개 가져오기
    with st.spinner("TMDB에서 인기 영화를 가져오는 중..."):
        movies, err = fetch_popular_movies_by_genre(TMDB_API_KEY, genre_id, n=5)

    if err:
        st.error(f"TMDB 호출 중 오류가 발생했어요: {err}")
        st.stop()

    if not movies:
        st.info("해당 장르에서 가져올 영화가 없어요. (결과가 비어있습니다)")
        st.stop()

    # 5) 결과 표시
    st.success("결과가 나왔어요!")
    st.subheader("🧠 테스트 결과")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("당신의 추천 장르", best_genre)
    with c2:
        st.write(f"**추천 이유(요약):** {test_reason}")
        # 점수표(가볍게)
        score_line = " · ".join([f"{g}: {scores[g]}" for g in GENRE_IDS.keys()])
        st.caption(f"장르 점수: {score_line}")

    st.divider()
    st.subheader(f"🎥 {best_genre} 인기 영화 TOP 5")

    for idx, m in enumerate(movies, start=1):
        title = m.get("title") or m.get("name") or "제목 정보 없음"
        vote = m.get("vote_average")
        release = m.get("release_date") or "개봉일 정보 없음"
        overview = (m.get("overview") or "").strip() or "줄거리 정보가 없습니다."
        poster_path = m.get("poster_path")

        poster_url = f"{TMDB_POSTER_BASE}{poster_path}" if poster_path else None

        with st.container(border=True):
            left, right = st.columns([1, 2], vertical_alignment="top")

            with left:
                if poster_url:
                    st.image(poster_url, use_container_width=True)
                else:
                    st.info("포스터 이미지가 없습니다.")

            with right:
                st.markdown(f"### {idx}. {title}")
                # 평점 표시
                if isinstance(vote, (int, float)):
                    st.write(f"⭐ 평점: **{vote:.1f}/10**")
                else:
                    st.write("⭐ 평점: 정보 없음")

                st.write(f"📅 개봉일: **{release}**")

                # 줄거리
                st.write("📝 줄거리")
                st.write(overview)

                # 추천 이유
                st.write("💡 이 영화를 추천하는 이유")
                st.write(movie_recommend_reason(best_genre, m, test_reason))

    st.caption("데이터 제공: TMDB (The Movie Database)")

else:
    st.info("모든 문항에 답한 뒤 **결과 보기 ✅** 버튼을 눌러주세요.")
