# app.py
import json
import io
import textwrap
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# =========================================================
# Config
# =========================================================
st.set_page_config(
    page_title="🎬 심리테스트 기반 영화 추천 (All-in-One)",
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

# 목표 감정(사용자 선택 -> 장르 보정 가중치)
GOAL_MOOD_WEIGHTS = {
    "힐링": {"드라마": 1, "로맨스": 1, "판타지": 1},
    "스트레스 해소": {"액션": 2, "코미디": 1},
    "집중/몰입": {"드라마": 2, "SF": 1},
    "설렘": {"로맨스": 2, "코미디": 1},
    "신선함": {"SF": 2, "판타지": 1},
    "웃고 싶어요": {"코미디": 2},
}

# 시간 모드 -> runtime 필터(분)
TIME_MODES = {
    "⏱️ 30분 내외(짧게)": (0, 45),
    "🕘 90분 내외(보통)": (70, 105),
    "🕛 2시간+(길게)": (110, 999),
}

# 보기 싫은 조건 -> TMDB discover 필터(가능한 범위 내)
# (TMDB는 키워드/장르/성인물/인증 등으로 일부만 정교하게 가능)
AVOID_PRESETS = {
    "로맨스는 빼고": {"without_genres": [GENRE_IDS["로맨스"]]},
    "폭력/잔인함은 적게": {"extra_note": "폭력/잔인함은 장르/키워드로 완벽히 차단이 어려워요. AI가 줄거리 기반으로 완화 추천을 시도합니다."},
    "공포/무서운 건 싫어": {"extra_note": "공포 장르(27)도 제외 가능하지만 현재 장르 목록에 없어서, AI가 줄거리 기반으로 피하도록 시도합니다."},
    "너무 슬픈 건 싫어": {"extra_note": "슬픔은 장르로 완전 제어 어려워요. AI가 분위기 가벼운 작품 쪽으로 유도합니다."},
    "청불(성인물) 제외": {"include_adult": False},
    "가족과 보기 좋은": {"extra_note": "가족 친화는 인증/키워드로 정교화 가능. AI가 무난한 톤으로 추천을 유도합니다."},
}

# =========================================================
# Sleek CSS
# =========================================================
st.markdown(
    """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1240px; }
div[data-testid="stSidebarContent"] { padding-top: 1.2rem; }

.hero {
  border-radius: 22px;
  padding: 18px 18px;
  border: 1px solid rgba(0,0,0,0.08);
  background: radial-gradient(1200px 220px at 10% 10%, rgba(30,144,255,0.18), transparent 55%),
              radial-gradient(900px 260px at 90% 30%, rgba(255,105,180,0.12), transparent 55%),
              rgba(255,255,255,0.72);
  box-shadow: 0 16px 50px rgba(0,0,0,0.08);
}

.glass {
  border-radius: 20px;
  padding: 16px 16px;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.78);
  box-shadow: 0 12px 36px rgba(0,0,0,0.06);
}

.ai-callout {
  border-radius: 18px;
  padding: 14px 14px;
  border: 1px solid rgba(30,144,255,0.25);
  background: linear-gradient(135deg, rgba(30,144,255,0.12), rgba(30,144,255,0.05));
  box-shadow: 0 12px 32px rgba(0,0,0,0.06);
}

.section-title {
  font-size: 1.25rem;
  font-weight: 900;
  margin: 0.2rem 0 0.6rem 0;
  letter-spacing: -0.02em;
}

.movie-card {
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.92);
  box-shadow: 0 12px 34px rgba(0,0,0,0.08);
}
.movie-pad { padding: 12px 12px 10px 12px; }
.movie-title { font-size: 1.05rem; font-weight: 900; margin: 6px 0 2px 0; letter-spacing: -0.02em; }
.muted { color: rgba(0,0,0,0.55); font-size: 0.92rem; }

.quote {
  border-radius: 18px;
  padding: 14px 14px;
  border: 1px dashed rgba(0,0,0,0.18);
  background: rgba(0,0,0,0.03);
}
.quote .q { font-style: italic; font-size: 1.02rem; line-height: 1.55; }
.quote .a { font-style: italic; font-size: 0.88rem; color: rgba(0,0,0,0.55); margin-top: 8px; }

.btnrow {
  border-radius: 18px;
  padding: 10px 10px;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.70);
}

.badge {
  display:inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.86rem;
  border: 1px solid rgba(0,0,0,0.10);
  background: rgba(255,255,255,0.75);
  margin-right: 6px;
}

.small { font-size: 0.90rem; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# Questions
# =========================================================
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

# =========================================================
# Helpers
# =========================================================
def safe_get_json(url: str, params: Optional[Dict] = None) -> Tuple[Optional[Any], Optional[str]]:
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)

def poster_url(movie: Dict) -> Optional[str]:
    p = movie.get("poster_path")
    return f"{TMDB_POSTER_BASE}{p}" if p else None

def analyze_answers(selected: Dict[str, str], goal_mood: str) -> Tuple[str, Dict[str, int], str, List[str]]:
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

    # 목표 감정 가중치 적용
    weights = GOAL_MOOD_WEIGHTS.get(goal_mood, {})
    for g, w in weights.items():
        scores[g] += w

    order = list(GENRE_IDS.keys())
    best_genre = max(order, key=lambda g: (scores[g], -order.index(g)))
    reason_summary = " / ".join(snippets[best_genre][:2]) if snippets[best_genre] else f"{best_genre} 성향이 강해요."
    return best_genre, scores, reason_summary, picked_texts

def build_context(picked_texts: List[str], best_genre: str, reason_summary: str, goal_mood: str, time_mode: str, avoid: List[str]) -> str:
    return (
        f"[심리테스트 응답]\n" + "\n".join(picked_texts) + "\n\n"
        f"[결과 장르] {best_genre}\n"
        f"[요약 이유] {reason_summary}\n"
        f"[목표 감정] {goal_mood}\n"
        f"[시간 모드] {time_mode}\n"
        f"[회피 조건] {', '.join(avoid) if avoid else '없음'}\n"
    )

# =========================================================
# APIs: TMDB / Unsplash / ZenQuotes
# =========================================================
@st.cache_data(ttl=60 * 30)
def fetch_movies_tmdb_discover(
    api_key: str,
    genre_ids: List[int],
    n: int,
    min_rating: float,
    region: str,
    original_lang: str,
    runtime_range: Tuple[int, int],
    without_genres: List[int],
    page: int = 1,
) -> Tuple[List[Dict], Optional[str]]:
    url = f"{TMDB_BASE}/discover/movie"
    g = ",".join([str(x) for x in genre_ids]) if genre_ids else ""
    wg = ",".join([str(x) for x in without_genres]) if without_genres else ""
    rt_min, rt_max = runtime_range

    params = {
        "api_key": api_key,
        "with_genres": g,
        "without_genres": wg,
        "language": "ko-KR",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "include_video": "false",
        "page": page,
        "vote_average.gte": min_rating,
        "vote_count.gte": 50,
        "with_runtime.gte": rt_min,
        "with_runtime.lte": rt_max,
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
    return data.get("results") or [], None

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

@st.cache_data(ttl=60 * 60)
def fetch_tmdb_videos(api_key: str, movie_id: int, language: str = "ko-KR") -> Tuple[List[Dict], Optional[str]]:
    url = f"{TMDB_BASE}/movie/{movie_id}/videos"
    params = {"api_key": api_key, "language": language}
    data, err = safe_get_json(url, params=params)
    if err:
        return [], err
    if not isinstance(data, dict) or "results" not in data:
        return [], "TMDB videos 응답 형식이 예상과 달라요."
    return data.get("results") or [], None

@st.cache_data(ttl=60 * 60)
def fetch_tmdb_watch_providers(api_key: str, movie_id: int) -> Tuple[Dict, Optional[str]]:
    url = f"{TMDB_BASE}/movie/{movie_id}/watch/providers"
    params = {"api_key": api_key}
    data, err = safe_get_json(url, params=params)
    if err:
        return {}, err
    if not isinstance(data, dict) or "results" not in data:
        return {}, "TMDB watch/providers 응답 형식이 예상과 달라요."
    return data.get("results") or {}, None

# =========================================================
# OpenAI streaming (typing effect)
# =========================================================
def stream_openai_text(openai_key: str, prompt: str, model: str):
    from openai import OpenAI
    client = OpenAI(api_key=openai_key)
    with client.responses.stream(model=model, input=prompt) as stream:
        for event in stream:
            if getattr(event, "type", None) == "response.output_text.delta":
                yield event.delta

def openai_text(openai_key: str, prompt: str, model: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=openai_key)
    resp = client.responses.create(model=model, input=prompt)
    # SDK 버전에 따라 output_text 속성이 있을 수 있음
    try:
        return resp.output_text
    except Exception:
        # 안전 fallback: 구조에서 텍스트 합치기
        txt = ""
        for o in getattr(resp, "output", []) or []:
            for c in getattr(o, "content", []) or []:
                if getattr(c, "type", "") == "output_text":
                    txt += getattr(c, "text", "")
        return txt.strip()

def typing_effect(container, text_stream):
    out = container.empty()
    buf = ""
    for chunk in text_stream:
        buf += chunk
        out.markdown(buf)
    return buf

# =========================================================
# Persistence: wishlist / seen (session + export/import)
# =========================================================
def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "questions"  # or "results"
    if "result_payload" not in st.session_state:
        st.session_state.result_payload = None
    if "wishlist" not in st.session_state:
        st.session_state.wishlist = {}  # movie_id -> movie dict minimal
    if "seen" not in st.session_state:
        st.session_state.seen = set()   # movie_ids
    if "last_filters" not in st.session_state:
        st.session_state.last_filters = {}  # store filters for refinement
    if "refine_note" not in st.session_state:
        st.session_state.refine_note = ""

def go_questions(reset_answers: bool = True):
    st.session_state.page = "questions"
    st.session_state.result_payload = None
    st.session_state.refine_note = ""
    if reset_answers:
        for q in QUESTIONS:
            st.session_state[q["id"]] = None
    st.rerun()

def go_results(payload: Dict):
    st.session_state.page = "results"
    st.session_state.result_payload = payload
    st.rerun()

def export_user_data() -> bytes:
    payload = {
        "wishlist": st.session_state.wishlist,
        "seen": list(st.session_state.seen),
        "exported_at": datetime.utcnow().isoformat() + "Z",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

def import_user_data(raw: bytes) -> Tuple[bool, str]:
    try:
        obj = json.loads(raw.decode("utf-8"))
        wishlist = obj.get("wishlist", {})
        seen = set(obj.get("seen", []))
        if not isinstance(wishlist, dict) or not isinstance(seen, set):
            return False, "형식이 올바르지 않아요."
        st.session_state.wishlist = wishlist
        st.session_state.seen = seen
        return True, "불러오기 완료!"
    except Exception as e:
        return False, f"불러오기 실패: {e}"

# =========================================================
# Share Image Card
# =========================================================
def fetch_image_bytes(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

def create_share_card(
    best_genre: str,
    genre_icon: str,
    movies: List[Dict],
    quote_text: str,
    quote_author: str,
    mood_image_url: Optional[str],
) -> bytes:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (245, 247, 250))
    draw = ImageDraw.Draw(img)

    # background gradient-ish blocks
    draw.rounded_rectangle((30, 30, W - 30, H - 30), radius=32, fill=(255, 255, 255))
    draw.rounded_rectangle((60, 60, W - 60, 230), radius=28, fill=(232, 242, 255))
    draw.rounded_rectangle((60, 250, W - 60, H - 60), radius=28, fill=(250, 250, 250))

    # mood image
    if mood_image_url:
        b = fetch_image_bytes(mood_image_url)
        if b:
            try:
                mood = Image.open(io.BytesIO(b)).convert("RGB")
                # crop to fit
                target = (420, 280)
                mood = mood.resize(target)
                img.paste(mood, (W - 60 - target[0], 250))
            except Exception:
                pass

    # fonts (fallback to default)
    try:
        font_title = ImageFont.truetype("DejaVuSans.ttf", 44)
        font_big = ImageFont.truetype("DejaVuSans.ttf", 34)
        font_body = ImageFont.truetype("DejaVuSans.ttf", 24)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_big = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # header
    title = f"{genre_icon} 당신에게 딱인 장르는 {best_genre}!"
    draw.text((80, 85), title, fill=(20, 60, 120), font=font_title)

    # movies
    draw.text((80, 150), "추천 영화", fill=(30, 30, 30), font=font_big)
    y = 200
    for m in movies[:3]:
        t = m.get("title", "제목 없음")
        v = m.get("vote_average", None)
        vstr = f"{float(v):.1f}/10" if isinstance(v, (int, float)) else "?"
        line = f"• {t}  (⭐ {vstr})"
        draw.text((90, y), line, fill=(40, 40, 40), font=font_body)
        y += 32

    # quote
    q = quote_text or ""
    a = quote_author or ""
    if q:
        draw.text((80, 350), "오늘의 명언", fill=(30, 30, 30), font=font_big)
        q_wrapped = "\n".join(textwrap.wrap(f"“{q}”", width=46))[:3000]
        draw.text((80, 398), q_wrapped, fill=(55, 55, 55), font=font_body)
        if a:
            draw.text((80, 560), f"— {a}", fill=(100, 100, 100), font=font_small)

    # export
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# =========================================================
# Refinement (Feature #6)
# =========================================================
def ai_refine_discover_params(
    openai_key: str,
    model: str,
    ctx: str,
    instruction: str,
) -> Dict[str, Any]:
    """
    AI에게 discover 파라미터를 JSON으로만 반환하게 하고 파싱.
    """
    prompt = f"""
너는 영화 추천 필터를 구성하는 어시스턴트야.
아래 [컨텍스트]와 [요청]을 보고, TMDB discover/movie에 쓸 수 있는 필터를 "JSON"으로만 출력해줘.
주의:
- 반드시 JSON만 출력(설명/문장 금지)
- 값은 아래 키 중 필요한 것만 포함
- with_genres / without_genres 는 숫자 배열
- min_rating 은 0~10 숫자
- runtime_min / runtime_max 는 분 단위 정수
- tone_hint 는 문자열(짧게)
- avoid_keywords / prefer_keywords 는 문자열 배열(짧게)
- 목표는 "요청을 만족하면서도 사용자 성향과 부드럽게 맞는 추천"

가능 키:
{{
  "with_genres": [..],
  "without_genres": [..],
  "min_rating": 0.0,
  "runtime_min": 0,
  "runtime_max": 999,
  "tone_hint": "",
  "prefer_keywords": ["..."],
  "avoid_keywords": ["..."]
}}

[컨텍스트]
{ctx}

[요청]
{instruction}
""".strip()

    txt = openai_text(openai_key, prompt, model=model).strip()
    # JSON만 오도록 유도하지만 혹시 모를 잡텍스트 제거(최후의 안전장치)
    first = txt.find("{")
    last = txt.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return {}
    js = txt[first:last+1]
    try:
        return json.loads(js)
    except Exception:
        return {}

# =========================================================
# Build a movie list with filtering (wishlist/seen exclusion)
# =========================================================
def build_recommendations(
    tmdb_key: str,
    best_genre: str,
    min_rating: float,
    region: str,
    original_lang: str,
    runtime_range: Tuple[int, int],
    avoid_selected: List[str],
    refine_overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict], str]:
    """
    returns (movies_3, debug_note)
    """
    debug_note = ""

    # base genres
    base_with_genres = [GENRE_IDS[best_genre]]

    # avoid presets
    without_genres = []
    include_adult = False  # always false here
    extra_notes = []
    for a in avoid_selected:
        preset = AVOID_PRESETS.get(a, {})
        if "without_genres" in preset:
            without_genres += preset["without_genres"]
        if "include_adult" in preset:
            include_adult = bool(preset["include_adult"])
        if "extra_note" in preset:
            extra_notes.append(preset["extra_note"])

    # apply overrides from AI refinement
    if refine_overrides:
        if isinstance(refine_overrides.get("with_genres"), list) and refine_overrides["with_genres"]:
            base_with_genres = [int(x) for x in refine_overrides["with_genres"] if str(x).isdigit()]
        if isinstance(refine_overrides.get("without_genres"), list):
            without_genres += [int(x) for x in refine_overrides["without_genres"] if str(x).isdigit()]
        if isinstance(refine_overrides.get("min_rating"), (int, float)):
            min_rating = float(refine_overrides["min_rating"])
        if isinstance(refine_overrides.get("runtime_min"), int) and isinstance(refine_overrides.get("runtime_max"), int):
            runtime_range = (int(refine_overrides["runtime_min"]), int(refine_overrides["runtime_max"]))

        tone_hint = refine_overrides.get("tone_hint")
        if isinstance(tone_hint, str) and tone_hint.strip():
            debug_note += f"AI 톤 힌트: {tone_hint.strip()}\n"

    # fetch multiple pages until we have 3 not-seen movies
    collected: List[Dict] = []
    for page in [1, 2, 3]:
        results, err = fetch_movies_tmdb_discover(
            api_key=tmdb_key,
            genre_ids=base_with_genres,
            n=20,
            min_rating=min_rating,
            region=region,
            original_lang=original_lang,
            runtime_range=runtime_range,
            without_genres=list(set(without_genres)),
            page=page,
        )
        if err:
            return [], f"TMDB 오류: {err}"
        for m in results:
            mid = m.get("id")
            if mid in st.session_state.seen:
                continue
            collected.append(m)
            if len(collected) >= 3:
                break
        if len(collected) >= 3:
            break

    if extra_notes:
        debug_note += " · ".join(extra_notes)

    return collected[:3], debug_note.strip()

# =========================================================
# UI State
# =========================================================
init_state()

# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.header("🔑 API Keys")
    tmdb_key = st.text_input("TMDB API Key", type="password", placeholder="TMDB 키 입력")
    unsplash_key = st.text_input("Unsplash Access Key", type="password", placeholder="Unsplash 키 입력")
    openai_key = st.text_input("OpenAI API Key", type="password", placeholder="OpenAI 키 입력")
    st.caption("키는 저장되지 않으며, 버튼 클릭 시에만 사용됩니다.")

    st.divider()

    st.header("🎚️ 추천 필터")
    min_rating = st.slider("최소 평점", 0.0, 10.0, 6.5, 0.5)

    region_label = st.selectbox("국가(Region)", list(REGIONS.keys()), index=0)
    lang_label = st.selectbox("원어(Original Language)", list(LANGUAGES.keys()), index=0)
    region = REGIONS[region_label]
    original_lang = LANGUAGES[lang_label]

    st.divider()
    st.header("🧠 추천 모드")
    time_mode = st.selectbox("시청 가능 시간", list(TIME_MODES.keys()), index=1)
    goal_mood = st.selectbox("오늘의 목표 감정", list(GOAL_MOOD_WEIGHTS.keys()), index=0)

    st.divider()
    st.header("🙅 보기 싫은 조건")
    avoid_selected = st.multiselect(
        "원치 않는 요소를 선택하세요",
        options=list(AVOID_PRESETS.keys()),
        default=[],
    )

    st.divider()
    st.header("🤖 OpenAI 설정")
    ai_model = st.text_input("모델", value="gpt-4.1-mini")
    st.caption("환경/계정에 따라 모델명이 다를 수 있어요.")

    st.divider()
    st.header("⭐ 내 목록")
    st.write(f"찜: **{len(st.session_state.wishlist)}**  ·  봤어요: **{len(st.session_state.seen)}**")

    colx1, colx2 = st.columns(2)
    with colx1:
        st.download_button(
            "⬇️ 내 데이터 저장(JSON)",
            data=export_user_data(),
            file_name="movie_test_user_data.json",
            mime="application/json",
            use_container_width=True,
        )
    with colx2:
        up = st.file_uploader("⬆️ 불러오기(JSON)", type=["json"], label_visibility="collapsed")
        if up is not None:
            ok, msg = import_user_data(up.read())
            if ok:
                st.success(msg)
            else:
                st.error(msg)

# =========================================================
# Pages
# =========================================================
# -----------------------------
# QUESTIONS PAGE
# -----------------------------
if st.session_state.page == "questions":
    st.markdown(
        """
<div class="hero">
  <div style="font-size:1.9rem; font-weight:950;">🎭 오늘의 기분으로 고르는 영화 추천</div>
  <div class="muted" style="margin-top:6px;">
    6개의 질문 + <b>시간/목표 감정</b> + <b>회피 조건</b>을 반영해 <b>영화 3편</b>, <b>무드 이미지</b>, <b>명언</b>, <b>AI 해석</b>까지 한 번에 보여드려요.
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
        unanswered = [q["question"] for q in QUESTIONS if not selected.get(q["id"])]
        if unanswered:
            st.error("모든 문항에 답변해 주세요!")
            for uq in unanswered:
                st.write(f"- {uq}")
            st.stop()

        if not tmdb_key:
            st.warning("사이드바에 **TMDB API Key**를 입력해야 영화 추천을 가져올 수 있어요.")
            st.stop()

        # analyze
        best_genre, scores, reason_summary, picked_texts = analyze_answers(selected, goal_mood)
        runtime_range = TIME_MODES[time_mode]

        # movies (exclude seen)
        with st.spinner("🎥 추천 콘텐츠를 준비 중..."):
            movies, debug_note = build_recommendations(
                tmdb_key=tmdb_key,
                best_genre=best_genre,
                min_rating=min_rating,
                region=region,
                original_lang=original_lang,
                runtime_range=runtime_range,
                avoid_selected=avoid_selected,
                refine_overrides=None,
            )
            if not movies:
                st.info("조건에 맞는 영화가 없어요. (평점/시간/국가/언어/회피 조건을 조금 완화해보세요)")
                st.stop()

            # Unsplash
            mood_img = None
            mood_err = None
            if unsplash_key:
                mood_query = UNSPLASH_QUERY_BY_GENRE.get(best_genre, "cinematic mood")
                mood_img, mood_err = fetch_unsplash_image(unsplash_key, mood_query)

            # Quote
            quote, quote_err = fetch_zenquote_today()

        payload = {
            "best_genre": best_genre,
            "scores": scores,
            "reason_summary": reason_summary,
            "picked_texts": picked_texts,
            "movies": movies,
            "debug_note": debug_note,
            "mood_img": mood_img,
            "mood_err": mood_err,
            "quote": quote,
            "quote_err": quote_err,
            "filters": {
                "min_rating": min_rating,
                "region": region,
                "original_lang": original_lang,
                "time_mode": time_mode,
                "runtime_range": runtime_range,
                "goal_mood": goal_mood,
                "avoid_selected": avoid_selected,
            },
        }
        st.session_state.last_filters = payload["filters"]
        go_results(payload)

# -----------------------------
# RESULTS PAGE
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
    debug_note = payload.get("debug_note", "")
    filters = payload.get("filters", st.session_state.last_filters or {})

    icon = GENRE_ICON.get(best_genre, "🎬")
    goal_mood = filters.get("goal_mood", "힐링")
    time_mode = filters.get("time_mode", list(TIME_MODES.keys())[1])
    avoid_selected = filters.get("avoid_selected", [])

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

  <div style="margin-top:10px;">
    <span class="badge">🎯 {goal_mood}</span>
    <span class="badge">⏱️ {time_mode}</span>
    <span class="badge">⭐ 최소평점 {filters.get("min_rating", 0):.1f}</span>
    <span class="badge">🌍 {filters.get("region") or "Region:전체"}</span>
    <span class="badge">🗣️ {filters.get("original_lang") or "언어:전체"}</span>
  </div>

  <div class="muted" style="margin-top:10px;">
    {reason_summary}
    &nbsp; · &nbsp;
    {" · ".join([f"{g}:{scores[g]}" for g in GENRE_IDS.keys()])}
    {f"<br><span class='small'>참고: {debug_note}</span>" if debug_note else ""}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")

    tab1, tab2 = st.tabs(["✨ 추천 결과", f"⭐ 내 찜/봤어요 ({len(st.session_state.wishlist)}/{len(st.session_state.seen)})"])

    # =========================================================
    # TAB 1: RESULTS
    # =========================================================
    with tab1:
        # AI analysis callout (Feature: 1 + OpenAI typing)
        st.markdown('<div class="section-title">🤖 AI 분석</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="ai-callout">', unsafe_allow_html=True)
            area = st.container()

            fallback = (
                "당신은 그날의 기분과 원하는 감정(속도감/여운/설렘 등)을 비교적 명확하게 고르는 편이에요. "
                f"오늘은 특히 **{best_genre}** 쪽에서 만족도가 올라갈 확률이 높습니다."
            )

            if not openai_key:
                area.markdown(fallback)
            else:
                try:
                    ctx = build_context(picked_texts, best_genre, reason_summary, goal_mood, time_mode, avoid_selected)
                    prompt = f"""
너는 한국어로 짧고 세련되게 심리테스트 성향을 해석하는 AI야.
아래 정보를 바탕으로 '사용자 성향 설명'을 2~3문장으로 작성해줘.
단정/진단처럼 말하지 말고, 따뜻하고 구체적으로.

{ctx}

출력은 문장만(불릿/번호 없이).
""".strip()
                    typing_effect(area, stream_openai_text(openai_key, prompt, model=ai_model))
                except Exception as e:
                    area.markdown(fallback)
                    area.caption(f"(OpenAI 호출 실패: {e})")

            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Movie cards + wishlist/seen + trailer/providers (Feature: 3, 5)
        st.markdown('<div class="section-title">🎞️ 추천 영화 3편</div>', unsafe_allow_html=True)

        cols = st.columns(3, gap="large")
        for i, m in enumerate(movies):
            movie_id = m.get("id")
            title = m.get("title") or "제목 정보 없음"
            vote = m.get("vote_average")
            vote_str = f"{vote:.1f}/10" if isinstance(vote, (int, float)) else "정보 없음"
            release = m.get("release_date") or "개봉일 정보 없음"
            overview = (m.get("overview") or "").strip() or "줄거리 정보가 없습니다."
            purl = poster_url(m)

            in_wish = str(movie_id) in st.session_state.wishlist
            is_seen = movie_id in st.session_state.seen

            with cols[i]:
                st.markdown('<div class="movie-card">', unsafe_allow_html=True)
                if purl:
                    st.image(purl, use_container_width=True)
                else:
                    st.info("포스터 없음")

                st.markdown('<div class="movie-pad">', unsafe_allow_html=True)
                st.markdown(f'<div class="movie-title">{title}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="muted">⭐ 평점: <b>{vote_str}</b></div>', unsafe_allow_html=True)

                b1, b2 = st.columns(2)
                with b1:
                    if st.button(("💛 찜됨" if in_wish else "🤍 찜하기"), key=f"wish_{movie_id}", use_container_width=True):
                        if in_wish:
                            st.session_state.wishlist.pop(str(movie_id), None)
                        else:
                            st.session_state.wishlist[str(movie_id)] = {
                                "id": movie_id,
                                "title": title,
                                "vote_average": vote,
                                "poster_path": m.get("poster_path"),
                                "release_date": release,
                            }
                        st.rerun()
                with b2:
                    if st.button(("✅ 봤어요" if is_seen else "👀 봤어요"), key=f"seen_{movie_id}", use_container_width=True):
                        if is_seen:
                            st.session_state.seen.remove(movie_id)
                        else:
                            st.session_state.seen.add(movie_id)
                        st.rerun()

                with st.expander("상세 정보 / 추천 이유 / 트레일러 / 제공처"):
                    st.write(f"📅 개봉일: **{release}**")
                    st.write("📝 줄거리")
                    st.write(overview)

                    st.write("💡 왜 추천하나요?")
                    if not openai_key:
                        st.write(f"당신의 **{best_genre}** 성향( {reason_summary} )과 목표 감정(**{goal_mood}**)에 잘 맞아서 추천해요.")
                    else:
                        try:
                            ctx = build_context(picked_texts, best_genre, reason_summary, goal_mood, time_mode, avoid_selected)
                            prompt = f"""
너는 한국어로 '추천 영화를 왜 추천하는지'를 1~2문장으로 설명하는 AI야.
사용자 성향/목표 감정/회피 조건을 고려해서, 아래 영화에 대해 짧게 말해줘.
너무 과장하지 말고 자연스럽게.

{ctx}

[영화]
제목: {title}
평점: {vote}
개봉: {release}
""".strip()
                            placeholder = st.container()
                            typing_effect(placeholder, stream_openai_text(openai_key, prompt, model=ai_model))
                        except Exception:
                            st.write(f"당신의 **{best_genre}** 무드에 맞는 템포/감정선을 가진 작품이라 추천해요.")

                    st.divider()

                    # Trailer (Feature #5)
                    if tmdb_key and movie_id:
                        vids, verr = fetch_tmdb_videos(tmdb_key, int(movie_id))
                        if verr:
                            st.caption(f"트레일러 정보를 가져오지 못했어요: {verr}")
                        else:
                            yt = [v for v in vids if (v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"])]
                            if yt:
                                # pick first trailer
                                key = yt[0].get("key")
                                if key:
                                    st.write("▶️ 트레일러")
                                    st.video(f"https://www.youtube.com/watch?v={key}")
                            else:
                                st.caption("YouTube 트레일러 정보를 찾지 못했어요.")

                        # Watch providers (Feature #5)
                        providers, perr = fetch_tmdb_watch_providers(tmdb_key, int(movie_id))
                        if perr:
                            st.caption(f"제공처 정보를 가져오지 못했어요: {perr}")
                        else:
                            region_code = filters.get("region") or "KR"
                            region_info = providers.get(region_code) or providers.get("KR") or {}
                            link = region_info.get("link")
                            flatrate = region_info.get("flatrate") or []
                            rent = region_info.get("rent") or []
                            buy = region_info.get("buy") or []

                            st.write("📺 어디서 볼 수 있나요?")
                            if link:
                                st.caption("아래 버튼/링크는 TMDB 제공처 페이지로 이동합니다.")
                                st.link_button("TMDB 제공처 보기", link)

                            def show_provider_list(label: str, items: List[Dict]):
                                if not items:
                                    return
                                names = [x.get("provider_name") for x in items if x.get("provider_name")]
                                if names:
                                    st.write(f"**{label}:** " + ", ".join(names))

                            show_provider_list("구독", flatrate)
                            show_provider_list("대여", rent)
                            show_provider_list("구매", buy)

                            if not (link or flatrate or rent or buy):
                                st.caption("해당 지역 기준 제공처 정보가 없을 수 있어요.")

                st.markdown("</div>", unsafe_allow_html=True)  # movie-pad
                st.markdown("</div>", unsafe_allow_html=True)  # movie-card

        st.divider()

        # Mood + Quote section (Feature: 1 mood image + 5 quote + AI interpret 1 sentence)
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
                st.markdown("**🧠 오늘의 해석(1문장)**")

                if not openai_key or not quote_text:
                    st.write("오늘은 마음의 리듬을 지키면서, 딱 한 가지 행동만 가볍게 실천해보면 좋아요.")
                else:
                    try:
                        ctx = build_context(picked_texts, best_genre, reason_summary, goal_mood, time_mode, avoid_selected)
                        prompt = f"""
너는 한국어로 명언을 '사용자 성향'에 맞춰 1문장으로 해석하는 AI야.
반드시 1문장, 존댓말, 자연스럽게(오글거림 금지).

{ctx}

[명언]
{quote_text} — {quote_author}
""".strip()
                        placeholder = st.container()
                        typing_effect(placeholder, stream_openai_text(openai_key, prompt, model=ai_model))
                    except Exception:
                        st.write("오늘은 무리하지 말고, 지금의 흐름을 한 번만 더 이어가보세요.")

                st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Follow-up refinement buttons (Feature #6)
        st.markdown('<div class="section-title">🧠 후속 추천(클릭 한 번으로 분위기 조절)</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="glass">', unsafe_allow_html=True)
            st.caption("버튼을 누르면 AI가 필터를 재구성해서 **새 추천 3편**으로 바꿔줍니다. (봤어요 처리한 영화는 자동 제외)")
            r1, r2, r3, r4 = st.columns(4)

            refine_instruction = None
            with r1:
                if st.button("😌 더 가볍게", use_container_width=True):
                    refine_instruction = "전체적으로 가볍고 밝은 톤으로. 슬픈 여운은 줄이고 코미디/따뜻함을 늘려줘."
            with r2:
                if st.button("🔥 더 강렬하게", use_container_width=True):
                    refine_instruction = "더 강렬한 전개/긴장감. 템포 빠르게. 액션/스릴 느낌 쪽으로."
            with r3:
                if st.button("🚫 로맨스는 빼줘", use_container_width=True):
                    refine_instruction = "로맨스 비중은 최소화하고 관계 서사보다 사건/아이디어 중심으로."
            with r4:
                if st.button("🧠 설정이 신선하게", use_container_width=True):
                    refine_instruction = "신선한 설정/아이디어 중심. SF/판타지 감각 강화."

            if refine_instruction:
                if not openai_key:
                    st.warning("AI 후속 추천은 OpenAI API Key가 필요해요. 사이드바에 키를 입력해 주세요.")
                else:
                    try:
                        ctx = build_context(picked_texts, best_genre, reason_summary, goal_mood, time_mode, avoid_selected)
                        overrides = ai_refine_discover_params(openai_key, ai_model, ctx, refine_instruction)

                        # store for display
                        st.session_state.refine_note = overrides.get("tone_hint", "")

                        # build new recommendations with overrides
                        runtime_range = filters.get("runtime_range", TIME_MODES[time_mode])
                        new_movies, dbg = build_recommendations(
                            tmdb_key=tmdb_key,
                            best_genre=best_genre,
                            min_rating=float(filters.get("min_rating", 0.0)),
                            region=filters.get("region", ""),
                            original_lang=filters.get("original_lang", ""),
                            runtime_range=runtime_range,
                            avoid_selected=avoid_selected,
                            refine_overrides=overrides,
                        )
                        if not new_movies:
                            st.info("후속 조건으로는 추천이 어려워요. (필터를 조금 완화해보세요)")
                        else:
                            payload["movies"] = new_movies
                            payload["debug_note"] = (payload.get("debug_note", "") + "\n" + dbg).strip()
                            st.session_state.result_payload = payload
                            st.success("후속 추천으로 업데이트했어요!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"AI 후속 추천 중 오류: {e}")

            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # Share (Feature #4) + bottom buttons
        st.markdown('<div class="btnrow">', unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns([1, 1, 1, 2], gap="medium")
        with b1:
            if st.button("🔄 다시 테스트하기", use_container_width=True):
                go_questions(reset_answers=True)
        with b2:
            share_text_clicked = st.button("📋 텍스트 공유", use_container_width=True)
        with b3:
            share_img_clicked = st.button("🖼️ 공유 이미지 만들기", use_container_width=True)
        with b4:
            # show share outputs
            if share_text_clicked:
                titles = [m.get("title", "") for m in movies]
                qtext = quote.get("q", "") if quote else ""
                qauth = quote.get("a", "") if quote else ""
                share_text = (
                    f"{GENRE_ICON.get(best_genre,'🎬')} 결과 장르: {best_genre}\n"
                    f"추천 영화: {', '.join([t for t in titles if t])}\n"
                    f"오늘의 명언: “{qtext}” — {qauth}\n"
                )
                st.text_area("복사해서 공유하세요", value=share_text, height=110)

            if share_img_clicked:
                mood_url = None
                if mood_img:
                    mood_url = mood_img.get("urls", {}).get("regular")
                qtext = quote.get("q", "") if quote else ""
                qauth = quote.get("a", "") if quote else ""
                card_bytes = create_share_card(best_genre, icon, movies, qtext, qauth, mood_url)
                st.download_button(
                    "⬇️ 공유 이미지 다운로드(PNG)",
                    data=card_bytes,
                    file_name="movie_result_card.png",
                    mime="image/png",
                    use_container_width=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    # =========================================================
    # TAB 2: WISHLIST / SEEN
    # =========================================================
    with tab2:
        st.markdown('<div class="section-title">⭐ 내 찜 목록</div>', unsafe_allow_html=True)
        if not st.session_state.wishlist:
            st.info("아직 찜한 영화가 없어요. 추천 카드에서 🤍 찜하기를 눌러보세요.")
        else:
            items = list(st.session_state.wishlist.values())
            for it in items:
                mid = it.get("id")
                title = it.get("title", "")
                vote = it.get("vote_average")
                vstr = f"{float(vote):.1f}/10" if isinstance(vote, (int, float)) else "?"
                p = it.get("poster_path")
                purl = f"{TMDB_POSTER_BASE}{p}" if p else None
                with st.container():
                    c1, c2, c3 = st.columns([1, 3, 1])
                    with c1:
                        if purl:
                            st.image(purl, use_container_width=True)
                    with c2:
                        st.markdown(f"**{title}**")
                        st.caption(f"⭐ {vstr}  ·  📅 {it.get('release_date','')}")
                    with c3:
                        if st.button("🗑️ 제거", key=f"del_wish_{mid}", use_container_width=True):
                            st.session_state.wishlist.pop(str(mid), None)
                            st.rerun()
            st.divider()

        st.markdown('<div class="section-title">👀 봤어요</div>', unsafe_allow_html=True)
        if not st.session_state.seen:
            st.info("‘봤어요’로 표시한 영화가 없어요.")
        else:
            st.write("다음 추천에서 자동으로 제외됩니다.")
            # 간단히 ID만 보여주고, 필요하면 TMDB 상세를 붙일 수 있음
            ids = sorted(list(st.session_state.seen))
            st.code(", ".join([str(x) for x in ids]))
            if st.button("🧹 봤어요 목록 비우기"):
                st.session_state.seen = set()
                st.rerun()
