import os
import math
import time
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple

import requests
import streamlit as st
import pydeck as pdk

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]


try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
except Exception:
    A4 = None
    rl_canvas = None
    mm = None


APP_NAME = "Travel-Maker"

BEIGE_BG = "#F6F0E6"
CARD_BG = "#FFF9F0"
TEXT = "#2B2B2B"
MUTED = "#6B6B6B"
ACCENT = "#C07A4D"
SOFT_BORDER = "rgba(0,0,0,0.07)"

CSS = f"""
<style>
  .stApp {{
    background: {BEIGE_BG};
    color: {TEXT};
  }}
  .block-container {{
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1120px;
  }}
  .tm-title {{
    font-size: 2.45rem;
    font-weight: 950;
    letter-spacing: -0.9px;
    margin-bottom: .15rem;
  }}
  .tm-subtitle {{
    color: {MUTED};
    font-size: 1.02rem;
    margin-bottom: .9rem;
  }}
  .tm-badge {{
    display: inline-block;
    padding: .25rem .6rem;
    border-radius: 999px;
    background: rgba(192, 122, 77, 0.12);
    color: {ACCENT};
    font-weight: 900;
    font-size: .86rem;
    margin-left: .4rem;
    transform: translateY(-2px);
  }}
  .tm-card {{
    background: {CARD_BG};
    border: 1px solid {SOFT_BORDER};
    border-radius: 18px;
    padding: 1rem 1.1rem;
    box-shadow: 0 10px 26px rgba(0,0,0,0.06);
    margin: .65rem 0 1rem 0;
  }}
  .tm-card h3 {{
    margin: 0 0 .35rem 0;
    font-size: 1.12rem;
  }}
  .tm-tip {{
    color: {MUTED};
    font-size: .96rem;
    line-height: 1.45;
    margin-top: .25rem;
  }}
  .tm-section-title {{
    font-size: 1.25rem;
    font-weight: 950;
    margin-top: .35rem;
    margin-bottom: .35rem;
    letter-spacing: -0.2px;
  }}
  .tm-micro {{
    color: {MUTED};
    font-size: .85rem;
  }}

  div.stButton > button {{
    border-radius: 14px;
    padding: .58rem 1rem;
    font-weight: 950;
    border: 1px solid {SOFT_BORDER};
  }}
  div.stButton > button:hover {{
    border-color: rgba(192, 122, 77, 0.50);
    box-shadow: 0 12px 24px rgba(192, 122, 77, 0.18);
    transform: translateY(-1px);
  }}

  .stTextInput input, .stNumberInput input {{
    border-radius: 12px !important;
  }}
  .stSelectbox div[data-baseweb="select"] > div {{
    border-radius: 12px !important;
  }}
  details {{
    border-radius: 14px;
    border: 1px solid {SOFT_BORDER};
    background: {CARD_BG};
    padding: .45rem .7rem;
  }}

  section[data-testid="stSidebar"] {{
    background: rgba(255, 249, 240, 0.78);
    border-right: 1px solid {SOFT_BORDER};
  }}
</style>
"""


def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 1

    defaults = {
        "travel_month": "상관없음",
        "party_type": "친구",
        "party_count": 2,
        "destination_scope": "국내",
        "destination_text": "",
        "duration": "3일",
        "travel_style": ["힐링"],
        "budget": 1000000,
        "start_date": date.today(),
        "start_city": "서울",
        "openai_api_key": "",
        "travel_mode_sidebar": "자유여행",
        "move_mode": "자동",
        "include_return_to_center": True,
        "show_map": True,
        "show_budget": True,
        "show_checklist": True,
        "enable_edit": True,
        "poi_radius_km": 8,
        "poi_limit": 50,
        "poi_types": ["관광", "맛집", "카페", "자연", "문화"],
        "last_payload_sig": None,
        "last_bundle": None,
        "itinerary_edits": {},
        "poi_user_exclude": set(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def month_hint(month: str) -> str:
    if month == "상관없음":
        return "월이 프리면, 날씨는 그때그때 ‘유연한 인간’ 모드로 대응 ㄱㄱ"
    try:
        m = int(month.replace("월", ""))
    except Exception:
        return "월 파싱 실패… 그래도 우린 계획을 세운다."
    if m in [12, 1, 2]:
        return "겨울 감성 ON. 방한템 + 실내코스도 챙기면 완-벽"
    if m in [3, 4, 5]:
        return "봄바람 살랑. 낮밤 온도차만 조심하면 갬성샷 자동 생성"
    if m in [6, 7, 8]:
        return "여름 폭주 구간. 더위/습도/소나기 대비 필수(선크림은 생존템)"
    if m in [9, 10, 11]:
        return "가을은 진짜 반칙. 걷기/야외 코스 뽕 뽑기 좋은 시즌"
    return "날씨 힌트 로딩 실패… (하지만 우린 계획왕/퀸)"


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def geocode_place(query: str) -> Optional[Dict[str, Any]]:
    if not query or not query.strip():
        return None
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": f"{APP_NAME}/1.0 (streamlit)"}
    try:
        time.sleep(0.15)
        r = requests.get(url, params=params, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return {
            "lat": float(data[0]["lat"]),
            "lon": float(data[0]["lon"]),
            "display_name": data[0].get("display_name", query),
        }
    except Exception:
        return None


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def classify_distance(km: Optional[float]) -> str:
    if km is None:
        return "미정"
    if km < 1200:
        return "단거리 느낌(가볍게 다녀오기 가능)"
    if km < 4500:
        return "중거리(비행/이동 계획 빡세게 짜야 함)"
    return "장거리(시차/체력/동선까지 전략 필요)"


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_open_meteo_forecast(lat: float, lon: float, days: int) -> Optional[Dict[str, Any]]:
    try:
        n = max(1, min(days, 16))
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": n,
        }
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        d = r.json().get("daily", {})
        times = d.get("time", [])
        tmax = d.get("temperature_2m_max", [])
        tmin = d.get("temperature_2m_min", [])
        prcp = d.get("precipitation_sum", [])
        if not times or not tmax or not tmin:
            return None
        daily = []
        for i in range(min(len(times), len(tmax), len(tmin), len(prcp))):
            daily.append({"date": times[i], "tmax": tmax[i], "tmin": tmin[i], "prcp": prcp[i]})
        return {"daily": daily}
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_open_meteo_recent_snapshot(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": 7,
        }
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        d = r.json().get("daily", {})
        tmax = d.get("temperature_2m_max", [])
        tmin = d.get("temperature_2m_min", [])
        prcp = d.get("precipitation_sum", [])
        if not tmax or not tmin:
            return None
        return {
            "avg_max": round(sum(tmax) / len(tmax), 1),
            "avg_min": round(sum(tmin) / len(tmin), 1),
            "total_prcp": round(sum(prcp) if prcp else 0.0, 1),
        }
    except Exception:
        return None


def _radius_to_bbox(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    lat_deg = radius_km / 110.574
    lon_deg = radius_km / (111.320 * math.cos(math.radians(lat)) + 1e-9)
    return (lat - lat_deg, lon - lon_deg, lat + lat_deg, lon + lon_deg)


def _overpass_query_bbox(south, west, north, east) -> str:
    return f"""
    [out:json][timeout:25];
    (
      node["tourism"~"attraction|museum|viewpoint"]({south},{west},{north},{east});
      node["leisure"="park"]({south},{west},{north},{east});
      node["natural"~"peak|beach"]({south},{west},{north},{east});
      node["historic"~"monument|castle|memorial"]({south},{west},{north},{east});
      node["amenity"~"restaurant|cafe|bar"]({south},{west},{north},{east});
    );
    out center;
    """


def _poi_type(tags: Dict[str, Any]) -> str:
    if "amenity" in tags:
        v = tags["amenity"]
        if v == "restaurant":
            return "맛집"
        if v == "cafe":
            return "카페"
        if v == "bar":
            return "유흥"
        return "편의"
    if "tourism" in tags:
        v = tags["tourism"]
        if v == "museum":
            return "문화"
        if v in ["attraction", "viewpoint"]:
            return "관광"
        return "관광"
    if tags.get("leisure") == "park":
        return "자연"
    if "natural" in tags:
        return "자연"
    if "historic" in tags:
        return "문화"
    return "관광"


@st.cache_data(show_spinner=False, ttl=60 * 30)
def fetch_pois_overpass(lat: float, lon: float, radius_km: float, limit: int):
    south, west, north, east = _radius_to_bbox(lat, lon, radius_km)
    query = _overpass_query_bbox(south, west, north, east)

    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data=query.encode("utf-8"), timeout=35)
            r.raise_for_status()
            data = r.json()

            elements = data.get("elements", [])
            pois = []

            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue

                lat_p = el.get("lat") or el.get("center", {}).get("lat")
                lon_p = el.get("lon") or el.get("center", {}).get("lon")
                if lat_p is None or lon_p is None:
                    continue

                pois.append({
                    "name": name,
                    "lat": float(lat_p),
                    "lon": float(lon_p),
                    "type": _poi_type(tags),
                    "tags": tags,
                    "osm_id": el.get("id"),
                })

            return pois[:limit]

        except Exception:
            # 이 서버 실패 → 다음 서버 시도
            continue

    # 모든 서버 실패
    return []


        seen = set()
        deduped = []
        for p in pois:
            key = (p["name"], round(p["lat"], 5), round(p["lon"], 5))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)

        return deduped[: max(0, int(limit))]
    except Exception:
        return []


def duration_to_days(duration: str) -> int:
    return {"당일치기": 1, "3일": 3, "5일": 5, "10일 이상": 10}.get(duration, 3)


def poi_score(poi: Dict[str, Any], styles: List[str]) -> float:
    base = {
        "관광": 1.0,
        "문화": 1.0,
        "자연": 1.0,
        "맛집": 0.9,
        "카페": 0.7,
        "유흥": 0.6,
        "편의": 0.3,
    }.get(poi.get("type", "관광"), 0.8)

    s = base
    if "힐링" in styles and poi["type"] in ["자연", "카페"]:
        s += 0.35
    if "식도락" in styles and poi["type"] in ["맛집", "카페"]:
        s += 0.45
    if "유흥" in styles and poi["type"] in ["유흥"]:
        s += 0.6
    if "문화/예술" in styles and poi["type"] in ["문화"]:
        s += 0.5
    if "자연" in styles and poi["type"] in ["자연"]:
        s += 0.45
    if "로드트립" in styles and poi["type"] in ["자연", "관광"]:
        s += 0.15
    return s


def _kmeans_like(points: List[Tuple[float, float]], k: int, iters: int = 10) -> List[int]:
    if not points or k <= 1:
        return [0 for _ in points]
    k = min(k, len(points))
    step = max(1, len(points) // k)
    centroids = [points[i] for i in range(0, len(points), step)][:k]
    assign = [0] * len(points)

    for _ in range(iters):
        changed = False
        for i, (x, y) in enumerate(points):
            best_c = 0
            best_d = 1e18
            for c, (cx, cy) in enumerate(centroids):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if d < best_d:
                    best_d = d
                    best_c = c
            if assign[i] != best_c:
                assign[i] = best_c
                changed = True

        tmp = [[0.0, 0.0, 0] for _ in range(k)]
        for i, c in enumerate(assign):
            tmp[c][0] += points[i][0]
            tmp[c][1] += points[i][1]
            tmp[c][2] += 1

        new_centroids = []
        for c in range(k):
            if tmp[c][2] == 0:
                new_centroids.append(centroids[c])
            else:
                new_centroids.append((tmp[c][0] / tmp[c][2], tmp[c][1] / tmp[c][2]))
        centroids = new_centroids

        if not changed:
            break

    return assign


def _nearest_neighbor_order(pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(pois) <= 2:
        return pois
    remaining = pois[:]
    mean_lat = sum(p["lat"] for p in remaining) / len(remaining)
    mean_lon = sum(p["lon"] for p in remaining) / len(remaining)
    start_idx = min(
        range(len(remaining)),
        key=lambda i: (remaining[i]["lat"] - mean_lat) ** 2 + (remaining[i]["lon"] - mean_lon) ** 2,
    )
    route = [remaining.pop(start_idx)]
    while remaining:
        last = route[-1]
        idx = min(
            range(len(remaining)),
            key=lambda i: haversine_km(last["lat"], last["lon"], remaining[i]["lat"], remaining[i]["lon"]),
        )
        route.append(remaining.pop(idx))
    return route


def build_itinerary_from_pois(
    pois: List[Dict[str, Any]],
    styles: List[str],
    days: int,
    exclude_names: Optional[set] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    exclude_names = exclude_names or set()
    if not pois:
        return {d: [] for d in range(1, days + 1)}

    filtered = [p for p in pois if p["name"] not in exclude_names]
    scored = [(poi_score(p, styles), p) for p in filtered]
    scored.sort(key=lambda x: x[0], reverse=True)

    per_day = 5 if days >= 5 else 6
    max_pick = max(6, min(len(scored), days * per_day))
    picked = [p for _, p in scored[:max_pick]]

    points = [(p["lat"], p["lon"]) for p in picked]
    k = min(days, len(picked))
    clusters = _kmeans_like(points, k=k, iters=12)

    day_map: Dict[int, List[Dict[str, Any]]] = {d: [] for d in range(1, days + 1)}
    for p, c in zip(picked, clusters):
        day = c + 1
        if day <= days:
            day_map[day].append(p)

    for d in range(1, days + 1):
        day_map[d] = _nearest_neighbor_order(day_map[d])

    return day_map


def infer_move_mode(styles: List[str], radius_km: float) -> str:
    if "로드트립" in styles:
        return "차량"
    if radius_km <= 3:
        return "도보"
    return "대중교통"


def move_speed_kmh(mode: str) -> float:
    return {"도보": 4.5, "대중교통": 18.0, "차량": 28.0}.get(mode, 18.0)


def leg_overhead_min(mode: str) -> float:
    return {"도보": 3.0, "대중교통": 10.0, "차량": 8.0}.get(mode, 8.0)


def estimate_route_time_minutes(
    points: List[Tuple[float, float]],
    mode: str,
    return_to_center: bool = True,
) -> Dict[str, Any]:
    if not points or len(points) == 1:
        return {
            "mode": mode,
            "total_minutes": 0,
            "total_km": 0.0,
            "legs": [],
            "note": "포인트가 1개 이하라 이동시간은 0으로 처리!",
        }

    speed = move_speed_kmh(mode)
    overhead = leg_overhead_min(mode)

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))

    legs = []
    total_km = 0.0
    total_min = 0.0

    for i in range(len(points) - 1):
        a = points[i]
        b = points[i + 1]
        km = haversine_km(a[0], a[1], b[0], b[1])
        minutes = (km / speed) * 60.0 + overhead
        legs.append({"from": i, "to": i + 1, "km": round(km, 2), "minutes": int(round(minutes))})
        total_km += km
        total_min += minutes

    if return_to_center:
        last = points[-1]
        km = haversine_km(last[0], last[1], center[0], center[1])
        minutes = (km / speed) * 60.0 + overhead
        legs.append({"from": len(points) - 1, "to": "center", "km": round(km, 2), "minutes": int(round(minutes))})
        total_km += km
        total_min += minutes

    return {
        "mode": mode,
        "total_minutes": int(round(total_min)),
        "total_km": round(total_km, 2),
        "legs": legs,
        "note": "추정치(직선거리+오버헤드)라 실제 교통/경로에 따라 달라질 수 있어요.",
    }


def build_day_travel_times(
    day_map: Dict[int, List[Dict[str, Any]]],
    styles: List[str],
    radius_km: float,
    move_mode_setting: str,
    return_to_center: bool,
) -> Dict[int, Dict[str, Any]]:
    day_times = {}
    inferred = infer_move_mode(styles, radius_km)

    for d, pois in day_map.items():
        pts = [(p["lat"], p["lon"]) for p in pois]
        mode = move_mode_setting
        if mode == "자동":
            mode = inferred
        day_times[d] = estimate_route_time_minutes(pts, mode=mode, return_to_center=return_to_center)

    return day_times


def budget_tier(budget: int) -> str:
    if budget <= 0:
        return "미정(=무한 가능성…이 아니라 입력 부탁 🥲)"
    if budget < 800000:
        return "가성비"
    if budget < 2000000:
        return "밸런스"
    return "플렉스"


def base_budget_weights(mode: str) -> Dict[str, float]:
    if mode == "패키지여행":
        return {"숙소": 0.35, "식비": 0.22, "교통": 0.12, "체험/투어": 0.20, "쇼핑": 0.06, "기타": 0.05}
    return {"숙소": 0.32, "식비": 0.22, "교통": 0.16, "체험/투어": 0.16, "쇼핑": 0.08, "기타": 0.06}


def style_adjustment(style: List[str]) -> Dict[str, float]:
    adj = {"숙소": 0.0, "식비": 0.0, "교통": 0.0, "체험/투어": 0.0, "쇼핑": 0.0, "기타": 0.0}
    if "힐링" in style:
        adj["숙소"] += 0.03
        adj["기타"] += 0.01
    if "식도락" in style:
        adj["식비"] += 0.06
        adj["체험/투어"] -= 0.01
    if "유흥" in style:
        adj["기타"] += 0.05
        adj["식비"] += 0.01
    if "로드트립" in style:
        adj["교통"] += 0.06
        adj["숙소"] -= 0.02
    if "쇼핑" in style:
        adj["쇼핑"] += 0.08
        adj["기타"] -= 0.02
    if "문화/예술" in style or "액티비티" in style or "테마파크" in style:
        adj["체험/투어"] += 0.06
        adj["식비"] -= 0.01
    if "자연" in style:
        adj["교통"] += 0.02
        adj["체험/투어"] += 0.02
    return adj


def allocate_budget(total: int, mode: str, style: List[str]) -> Dict[str, int]:
    if total <= 0:
        return {"숙소": 0, "식비": 0, "교통": 0, "체험/투어": 0, "쇼핑": 0, "기타": 0}
    w = base_budget_weights(mode)
    adj = style_adjustment(style)
    for k in w:
        w[k] = max(0.01, w[k] + adj.get(k, 0.0))
    s = sum(w.values())
    w = {k: v / s for k, v in w.items()}
    alloc = {k: int(total * w[k]) for k in w}
    remainder = total - sum(alloc.values())
    alloc["기타"] += remainder
    return alloc


def build_checklist(destination_scope: str, month: str, style: List[str], party_type: str) -> Dict[str, List[str]]:
    packing = [
        "보조배터리(진짜 생존템)",
        "편한 신발(발이 편해야 인생도 편함)",
        "상비약/밴드",
        "우산 or 우비(날씨 변덕 대비)",
        "충전기/케이블(여분 있으면 인간미 +100)",
    ]
    docs = []
    money = ["카드 2장 이상(한 장은 예비)", "교통카드/현지 교통 앱"]

    if destination_scope == "해외":
        docs += ["여권(유효기간 체크)", "항공권/숙소 예약 내역(오프라인 저장)", "여행자보험(강추)", "멀티어댑터(국가별)"]
        money += ["현지 소액 현금(택시/시장용)"]

    if month != "상관없음":
        try:
            m = int(month.replace("월", ""))
        except Exception:
            m = None
        if m in [12, 1, 2]:
            packing += ["방한 외투/장갑/목도리", "핫팩(있으면 천재)"]
        if m in [6, 7, 8]:
            packing += ["선크림/모자", "벌레 퇴치제(자연코스면 특히)"]

    if "로드트립" in style:
        packing += ["면허증(렌트 시)", "차량용 거치대/충전기"]
    if "액티비티" in style:
        packing += ["운동화/활동복"]
    if "유흥" in style:
        packing += ["편한데 예쁜(?) 옷 한 벌", "숙소 위치/귀가 루트 미리 체크"]
    if "식도락" in style:
        packing += ["소화제(선제적 방어)", "맛집 후보 10개(최소 3개는 ‘대안’)"]
    if "테마파크" in style:
        packing += ["대기시간 대비 이어폰/컨텐츠"]

    if party_type in ["부모님", "가족"]:
        packing += ["너무 빡센 일정 금지(체력 배려)", "필요 시 무릎/허리 보호"]
    if party_type == "연인":
        packing += ["골든아워 체크(사진 퀄이 사랑을 함)", "서프라이즈 옵션 1개(과하면 안됨)"]

    def dedupe(seq):
        seen = set()
        out = []
        for x in seq:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    return {
        "서류/예약": dedupe(docs) if docs else ["(국내면 패스해도 OK. 그래도 예약 캡처는 안전빵)"],
        "필수 짐": dedupe(packing),
        "돈/결제": dedupe(money),
    }


def plan_from_poi_daymap(dest: str, days: int, day_map: Dict[int, List[Dict[str, Any]]], styles: List[str], party: str) -> Dict[str, Any]:
    day_blocks = []
    for d in range(1, days + 1):
        pois = day_map.get(d, [])
        am = pois[:2]
        pm = pois[2:4]
        night = pois[4:6]

        def fmt(items):
            if not items:
                return "취향 코스(여유) / 근처 산책 / 카페"
            return " → ".join([f"{p['name']}({p['type']})" for p in items])

        am_line = f"☀️ 오전: {fmt(am)}"
        pm_line = f"🌤️ 오후: {fmt(pm)}"
        night_line = f"🌙 밤: {fmt(night)}"
        if "식도락" in styles:
            night_line += " + 야식/디저트(선택인데 사실 거의 필수)"
        if "힐링" in styles:
            am_line += " + 느긋하게(마음의 평화 우선)"
        if "유흥" in styles:
            night_line += " + 바/야경 스팟 옵션"

        day_blocks.append({"day": d, "title": f"Day {d}", "plan": [am_line, pm_line, night_line]})

    headline = f"✨ {dest} {days}일 플랜 (feat. {party} 모먼트) — 동선은 효율, 감성은 과몰입"
    summary = "근처 POI를 자동 수집해서 ‘하루 동선’ 기준으로 묶고, 가까운 순으로 정렬했어. 너는 그냥 즐기기만 하면 됨 😎"
    return {"headline": headline, "summary": summary, "day_blocks": day_blocks, "tips": [], "sources": []}


def build_rule_based_plan(
    payload: Dict[str, Any],
    km: Optional[float],
    snapshot: Optional[Dict[str, Any]],
    poi_daymap: Optional[Dict[int, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    days = duration_to_days(payload["duration"])
    styles = payload.get("travel_style", [])
    party = payload.get("party_type", "친구")
    budget = int(payload.get("budget", 0))
    dest = (payload.get("destination_text") or "").strip() or "어딘가 갬성 좋은 곳"
    travel_mode = payload.get("travel_mode", "자유여행")

    tier = budget_tier(budget)
    dist_label = classify_distance(km)

    wx_line = month_hint(payload.get("travel_month", "상관없음"))
    if snapshot:
        wx_line += f" / 최근 스냅샷: 평균 {snapshot['avg_min']}~{snapshot['avg_max']}°C, 강수 {snapshot['total_prcp']}mm(7일)"

    mode_line = "자유여행이면 동선 최적화가 승부!" if travel_mode == "자유여행" else "패키지면 체력 관리가 승부!"

    if poi_daymap:
        plan = plan_from_poi_daymap(dest, days, poi_daymap, styles, party)
    else:
        day_blocks = []
        for d in range(1, days + 1):
            if d == 1:
                focus = "도착/체크인/동네 적응 + ‘첫 끼’로 분위기 잡기"
            elif d == days:
                focus = "마무리 산책 + 기념품 + 이동(체력 안배)"
            else:
                focus = "메인 스팟 + 취향 코스 + 저녁 한 방(야경/야식 옵션)"
            day_blocks.append(
                {
                    "day": d,
                    "title": f"Day {d}",
                    "plan": [
                        "☀️ 오전: 여유롭게 스타트(과속 금지, 여행은 마라톤)",
                        f"🌤️ 오후: {focus}",
                        "🌙 밤: 숙소 복귀 전 ‘오늘의 베스트 컷’ 저장 📸",
                    ],
                }
            )
        plan = {
            "headline": f"✨ {dest} {days}일 플랜 (feat. {party} 모먼트) — 계획은 깔끔, 감성은 꽉",
            "summary": f"{dest}에서 {days}일 동안 {', '.join(styles) if styles else '취향저격'}으로 즐기는 플랜! 무리하지 말고 ‘꾸준히’ 즐기자 😎",
            "day_blocks": day_blocks,
            "tips": [],
            "sources": [],
        }

    tips = [
        f"🗓️ 시즌 힌트: {wx_line}",
        f"🧭 거리 감: {dist_label} (이동시간이 일정 퀄을 좌우함)",
        f"💸 예산 무드: {tier} 코스(과소비 방지 ‘인간 실드’ ON)",
        f"🚶 이동 팁: {mode_line}",
        "✅ 안전빵: 핵심 스팟은 오전에, 변수는 오후에(‘플랜 B’가 승자)",
    ]
    plan["tips"] = tips
    return plan


def call_openai_plan(openai_api_key: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if OpenAI is None:
        return None, "openai 패키지가 없어요. `pip install openai` 해주세요."
    try:
        client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        return None, f"OpenAI 클라이언트 초기화 실패: {e}"

    model = "gpt-4o-mini"

    instructions = (
        "너는 ‘Travel-Maker’ 여행 플래너 AI야.\n"
        "톤: 한국어, MZ 유행어/위트(과하지만 않게), 구조는 깔끔.\n"
        "사용자 입력을 바탕으로 구체적인 여행 계획(일자별)을 작성해.\n"
        "가능하면 web_search로 여행지 명소/동선/맛집/이동 팁 등을 참고하고,\n"
        "Sources에 출처(title/url/note)를 bullet로 정리해.\n"
        "확실하지 않으면 ‘추정’이라고 표시.\n"
        "반드시 JSON만 출력해.\n"
        "JSON 스키마:\n"
        "{\n"
        '  "headline": "...",\n'
        '  "summary": "...",\n'
        '  "day_blocks": [{"day":1,"title":"...","plan":["...","...","..."]}, ...],\n'
        '  "tips": ["...", "..."],\n'
        '  "sources": [{"title":"...","url":"...","note":"..."}]\n'
        "}\n"
    )

    user_input = json.dumps(payload, ensure_ascii=False)

    try:
        resp = client.responses.create(
            model=model,
            instructions=instructions,
            input=user_input,
            tools=[{"type": "web_search"}],
            include=["web_search_call.action.sources"],
            max_output_tokens=1700,
        )
    except Exception as e:
        return None, f"OpenAI 호출 실패: {e}"

    text = getattr(resp, "output_text", None)
    if not text:
        try:
            text = resp.output[0].content[0].text
        except Exception:
            text = None
    if not text:
        return None, "OpenAI 응답 텍스트 추출 실패"

    plan = None
    try:
        plan = json.loads(text)
    except Exception:
        try:
            s = text.find("{")
            e = text.rfind("}")
            if s != -1 and e != -1 and e > s:
                plan = json.loads(text[s : e + 1])
        except Exception:
            plan = None

    if plan is None or not isinstance(plan, dict):
        return None, "계획 JSON 파싱 실패(모델 출력 형식 흔들림)"

    sources = plan.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    try:
        dumped = resp.model_dump() if hasattr(resp, "model_dump") else None
        if dumped and "output" in dumped:
            for item in dumped["output"]:
                if item.get("type") == "web_search_call":
                    action = item.get("action", {})
                    srcs = action.get("sources", []) or []
                    for s in srcs:
                        url = s.get("url")
                        title = s.get("title") or s.get("source") or "web"
                        if url and not any(isinstance(x, dict) and x.get("url") == url for x in sources):
                            sources.append({"title": title, "url": url, "note": "web_search"})
        plan["sources"] = sources
    except Exception:
        pass

    return plan, None


def ensure_itinerary_edits(days: int, plan: Dict[str, Any]):
    edits = st.session_state.itinerary_edits or {}
    seed = {}
    for b in plan.get("day_blocks", []):
        try:
            d = int(b.get("day"))
        except Exception:
            continue
        lines = b.get("plan", []) if isinstance(b.get("plan", []), list) else []
        seed[d] = {
            "am": lines[0] if len(lines) > 0 else "☀️ 오전: (여기에 입력)",
            "pm": lines[1] if len(lines) > 1 else "🌤️ 오후: (여기에 입력)",
            "night": lines[2] if len(lines) > 2 else "🌙 밤: (여기에 입력)",
        }
    for d in range(1, days + 1):
        if d not in edits:
            edits[d] = seed.get(d, {"am": "☀️ 오전: ", "pm": "🌤️ 오후: ", "night": "🌙 밤: "})
    st.session_state.itinerary_edits = edits


def apply_itinerary_edits(plan: Dict[str, Any]) -> Dict[str, Any]:
    edits = st.session_state.itinerary_edits or {}
    new_plan = json.loads(json.dumps(plan))
    for b in new_plan.get("day_blocks", []):
        try:
            d = int(b.get("day"))
        except Exception:
            continue
        if d in edits:
            b["plan"] = [edits[d]["am"], edits[d]["pm"], edits[d]["night"]]
    return new_plan


def make_ics(bundle: Dict[str, Any]) -> str:
    payload = bundle.get("payload", {})
    plan = bundle.get("plan", {})
    start: date = payload.get("start_date_obj") or date.today()
    day_blocks = plan.get("day_blocks", []) or []
    dest = payload.get("destination_text", "Trip")

    def dt_all_day(d: date):
        return d.strftime("%Y%m%d")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Travel-Maker//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for b in day_blocks:
        try:
            day_num = int(b.get("day"))
        except Exception:
            continue
        d = start + timedelta(days=day_num - 1)
        title = b.get("title", f"Day {day_num}")
        detail = "\\n".join([str(x).replace("\n", " ") for x in b.get("plan", [])])

        uid = f"travel-maker-{start.strftime('%Y%m%d')}-{day_num}@travelmaker"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;VALUE=DATE:{dt_all_day(d)}",
            f"DTEND;VALUE=DATE:{dt_all_day(d + timedelta(days=1))}",
            f"SUMMARY:{dest} - {title}",
            f"DESCRIPTION:{detail}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def make_pdf_bytes(bundle: Dict[str, Any]) -> Optional[bytes]:
    if rl_canvas is None or A4 is None or mm is None:
        return None

    from io import BytesIO

    buf = BytesIO()

    payload = bundle.get("payload", {})
    plan = bundle.get("plan", {})
    meta = bundle.get("meta", {})

    c = rl_canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    def draw_title(text, y):
        c.setFont("Helvetica-Bold", 18)
        c.drawString(18 * mm, y, text)

    def draw_sub(text, y):
        c.setFont("Helvetica", 10)
        c.drawString(18 * mm, y, text)

    def draw_section(title, y):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(18 * mm, y, title)

    def draw_bullets(lines_, y, leading=12):
        c.setFont("Helvetica", 10)
        for line in lines_:
            if y < 20 * mm:
                c.showPage()
                y = height - 20 * mm
                c.setFont("Helvetica", 10)
            c.drawString(22 * mm, y, f"• {line}")
            y -= leading
        return y

    y = height - 20 * mm
    draw_title(f"{APP_NAME} — Travel Plan", y)
    y -= 10 * mm
    draw_sub(f"Exported at: {bundle.get('exported_at', '')}", y)
    y -= 6 * mm

    dest = payload.get("destination_text", "")
    month = payload.get("travel_month", "")
    duration = payload.get("duration", "")
    party = f"{payload.get('party_count', '')}명 · {payload.get('party_type', '')}"
    budget = payload.get("budget", 0)
    start_date_str = payload.get("start_date", "")

    y -= 4 * mm
    draw_section("Input Summary", y)
    y -= 6 * mm
    y = draw_bullets(
        [
            f"Destination: {dest}",
            f"Month: {month}",
            f"Start date: {start_date_str}",
            f"Duration: {duration}",
            f"Party: {party}",
            f"Budget: {budget:,} KRW" if isinstance(budget, int) else f"Budget: {budget}",
            f"Distance: {meta.get('distance_comment','')}",
            f"Move mode: {meta.get('move_mode_used','')}",
        ],
        y,
    )

    y -= 4 * mm
    draw_section("Headline", y)
    y -= 6 * mm
    y = draw_bullets([plan.get("headline", "")], y)

    y -= 2 * mm
    draw_section("Summary", y)
    y -= 6 * mm
    y = draw_bullets([plan.get("summary", "")], y)

    day_times = meta.get("day_travel_times", {}) or {}
    y -= 2 * mm
    draw_section("Estimated Travel Time (per day)", y)
    y -= 6 * mm
    day_lines = []
    for d in sorted(day_times.keys()):
        info = day_times[d]
        day_lines.append(f"Day {d}: {info.get('total_minutes',0)} min, {info.get('total_km',0)} km ({info.get('mode','')})")
    y = draw_bullets(day_lines if day_lines else ["(no data)"], y)

    y -= 2 * mm
    draw_section("Day-by-Day", y)
    y -= 6 * mm
    for b in plan.get("day_blocks", []) or []:
        title = b.get("title", f"Day {b.get('day','')}")
        lines_ = b.get("plan", []) or []
        y = draw_bullets([f"{title}:"] + [f"  {ln}" for ln in lines_], y)
        y -= 2

    tips = plan.get("tips", []) or []
    if tips:
        y -= 4 * mm
        draw_section("Tips", y)
        y -= 6 * mm
        y = draw_bullets(tips, y)

    sources = plan.get("sources", []) or []
    if sources:
        y -= 4 * mm
        draw_section("Sources", y)
        y -= 6 * mm
        src_lines = []
        for s in sources:
            if isinstance(s, dict):
                t = s.get("title", "source")
                u = s.get("url", "")
                src_lines.append(f"{t} — {u}".strip())
            else:
                src_lines.append(str(s))
        y = draw_bullets(src_lines, y)

    c.showPage()
    c.save()
    return buf.getvalue()


def render_map(dest_geo: Dict[str, Any], pois: List[Dict[str, Any]]):
    if not dest_geo:
        st.info("지도는 목적지 좌표를 못 찾으면 표시가 어려워요. (도시/나라를 더 정확히 써줘봐!)")
        return

    layers = []
    dest_data = [{"lat": dest_geo["lat"], "lon": dest_geo["lon"], "name": dest_geo.get("display_name", "Destination"), "kind": "DEST"}]
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=dest_data,
            get_position=["lon", "lat"],
            get_radius=6000,
            pickable=True,
        )
    )

    if pois:
        poi_data = [{"lat": p["lat"], "lon": p["lon"], "name": p["name"], "kind": p["type"]} for p in pois]
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=poi_data,
                get_position=["lon", "lat"],
                get_radius=2500,
                pickable=True,
            )
        )

    view = pdk.ViewState(latitude=dest_geo["lat"], longitude=dest_geo["lon"], zoom=11)
    deck = pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name} ({kind})"})
    st.pydeck_chart(deck, use_container_width=True)


def render_header():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="tm-title">{APP_NAME}<span class="tm-badge">trip optimizer</span></div>
        <div class="tm-subtitle">“질문 화면”은 가볍게, 결과는 묵직하게 😎 (동선+이동시간까지 추정해줌)</div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    st.sidebar.markdown("### 🔑 OpenAI API Key")
    st.sidebar.caption("키는 세션에만 저장(서버 저장 X). 없으면 POI 최적화 룰베이스로 갑니다.")
    st.session_state.openai_api_key = st.sidebar.text_input(
        "OPENAI_API_KEY",
        type="password",
        placeholder="sk-... (optional)",
        value=st.session_state.get("openai_api_key", ""),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧳 출발지(거리 계산용)")
    st.session_state.start_city = st.sidebar.text_input("출발 도시", value=st.session_state.get("start_city", "서울"))

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗓️ 시작 날짜(예보/ICS용)")
    st.session_state.start_date = st.sidebar.date_input("여행 시작일", value=st.session_state.get("start_date", date.today()))

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 POI 자동 수집 옵션")
    st.session_state.poi_radius_km = st.sidebar.slider("반경(km)", min_value=1, max_value=20, value=int(st.session_state.get("poi_radius_km", 5)))
    st.session_state.poi_limit = st.sidebar.slider("POI 최대 개수", min_value=10, max_value=120, value=int(st.session_state.get("poi_limit", 50)), step=10)
    st.session_state.poi_types = st.sidebar.multiselect(
        "POI 타입 필터(표시/계획에 반영)",
        ["관광", "문화", "자연", "맛집", "카페", "유흥"],
        default=st.session_state.get("poi_types", ["관광", "맛집", "카페", "자연", "문화"]),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🚶 Day 이동시간 추정 설정")
    st.session_state.move_mode = st.sidebar.selectbox(
        "이동수단",
        ["자동", "도보", "대중교통", "차량"],
        index=["자동", "도보", "대중교통", "차량"].index(st.session_state.get("move_mode", "자동")),
    )
    st.session_state.include_return_to_center = st.sidebar.toggle(
        "하루 마지막에 중심(대략 숙소) 복귀 포함",
        value=st.session_state.get("include_return_to_center", True),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧳 (선택) 여행 형태(예산 분배용)")
    st.session_state.travel_mode_sidebar = st.sidebar.selectbox(
        "여행 형태",
        ["자유여행", "패키지여행"],
        index=["자유여행", "패키지여행"].index(st.session_state.get("travel_mode_sidebar", "자유여행")),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ 확장 UI 토글")
    st.session_state.show_map = st.sidebar.toggle("지도 표시", value=st.session_state.get("show_map", True))
    st.session_state.enable_edit = st.sidebar.toggle("일정 편집 모드", value=st.session_state.get("enable_edit", True))
    st.session_state.show_budget = st.sidebar.toggle("예산 분배 표시", value=st.session_state.get("show_budget", True))
    st.session_state.show_checklist = st.sidebar.toggle("체크리스트 표시", value=st.session_state.get("show_checklist", True))


def page1():
    st.markdown(
        """
        <div class="tm-card">
          <h3>1) 기본 정보부터 ‘쓱’ 수집 📝</h3>
          <div class="tm-tip">딱 필요한 것만 묻는다. 질문 많으면 피곤한 거 알지? 😌</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    months = ["상관없음"] + [f"{i}월" for i in range(1, 13)]
    c1, c2 = st.columns(2)

    with c1:
        st.session_state.travel_month = st.selectbox(
            "여행 시기(월 단위)",
            months,
            index=months.index(st.session_state.travel_month),
        )
        st.session_state.party_count = st.number_input("여행 인원", min_value=1, max_value=30, value=int(st.session_state.party_count), step=1)

    with c2:
        st.session_state.party_type = st.selectbox(
            "관계",
            ["친구", "연인", "부모님", "가족", "혼자", "직장동료", "기타"],
            index=["친구", "연인", "부모님", "가족", "혼자", "직장동료", "기타"].index(st.session_state.party_type),
        )

    st.markdown(
        """
        <div class="tm-card">
          <h3>2) 희망 여행지 🌍</h3>
          <div class="tm-tip">
              아래 칸에는 <b>국가 ❌ / 도시 ⭕</b>로 입력해줘!<br/>
              (예: ❌ 캐나다 → ⭕ 밴쿠버 / 토론토)
          </div>
        """,
        unsafe_allow_html=True,
    )

    c3, c4 = st.columns([1, 2])
    with c3:
        st.session_state.destination_scope = st.selectbox(
            "국내/해외",
            ["국내", "해외"],
            index=["국내", "해외"].index(st.session_state.destination_scope),
        )
    with c4:
        st.session_state.destination_text = st.text_input(
            "여행 도시 입력 (국가명 ❌ / 도시명 ⭕)",
            value=st.session_state.destination_text,
            placeholder="예: 밴쿠버 / 토론토 / 도쿄 / 파리",
        )        
    nav = st.columns([1, 1, 2])
    with nav[2]:
        if st.button("다음 👉 (추가 정보로)", use_container_width=True):
            st.session_state.step = 2


def page2():
    st.markdown(
        """
        <div class="tm-card">
          <h3>추가 정보는 ‘디테일의 악마’ 모드 🧠</h3>
          <div class="tm-tip">여기서부터 여행 퀄이 확 달라져. (진짜임)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.session_state.duration = st.selectbox(
            "여행 일정",
            ["당일치기", "3일", "5일", "10일 이상"],
            index=["당일치기", "3일", "5일", "10일 이상"].index(st.session_state.duration),
        )
        st.session_state.budget = st.number_input(
            "예상 예산(원)",
            min_value=0,
            max_value=20000000,
            value=int(st.session_state.budget),
            step=50000,
        )

    with c2:
        st.session_state.travel_style = st.multiselect(
            "여행 스타일(복수 선택 가능)",
            ["힐링", "식도락", "유흥", "로드트립", "액티비티", "쇼핑", "문화/예술", "자연", "테마파크"],
            default=st.session_state.travel_style,
        )

    nav = st.columns([1, 1, 2])
    with nav[0]:
        if st.button("👈 이전", use_container_width=True):
            st.session_state.step = 1
    with nav[2]:
        if st.button("여행 계획 뽑기 ✨ (이동시간까지)", use_container_width=True):
            st.session_state.step = 3


def build_payload() -> Dict[str, Any]:
    return {
        "travel_month": st.session_state.travel_month,
        "party_count": int(st.session_state.party_count),
        "party_type": st.session_state.party_type,
        "destination_scope": st.session_state.destination_scope,
        "destination_text": st.session_state.destination_text,
        "duration": st.session_state.duration,
        "travel_style": st.session_state.travel_style,
        "budget": int(st.session_state.budget),
        "start_city": st.session_state.start_city,
        "start_date": st.session_state.start_date.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date_obj": st.session_state.start_date,
        "travel_mode": st.session_state.travel_mode_sidebar,
    }


def payload_signature(payload: Dict[str, Any]) -> str:
    copy = dict(payload)
    copy.pop("start_date_obj", None)
    return json.dumps(copy, ensure_ascii=False, sort_keys=True)


def generate_bundle() -> Tuple[Dict[str, Any], Optional[str]]:
    payload = build_payload()
    sig = payload_signature(payload)

    if st.session_state.last_payload_sig == sig and st.session_state.last_bundle is not None:
        return st.session_state.last_bundle, None

    dest_text = (payload.get("destination_text") or "").strip()
    start_text = (payload.get("start_city") or "").strip()

    # 해외인데 도시 힌트가 없으면 강제로 city 힌트 추가 (국가 중심 방지)
    if payload.get("destination_scope") == "해외" and dest_text:
        if "," not in dest_text:
            dest_text = f"{dest_text}, city"
    
    dest_geo = geocode_place(dest_text) if dest_text else None
    start_geo = geocode_place(start_text) if start_text else None

    if dest_geo:
        display = (dest_geo.get("display_name") or "").lower()
        if any(k in display for k in ["canada", "united states", "japan", "australia"]):
            st.info(
                "입력한 값이 ‘국가 단위’로 인식됐어요. "
                "도시로 입력하면 POI·동선·이동시간 정확도가 훨씬 좋아져요! "
                "예: 밴쿠버 / 토론토 / 도쿄"
            )

    km = None
    distance_comment = "거리 계산 보류(도시 입력이 비었거나 검색 실패)"
    if dest_geo and start_geo:
        km = haversine_km(start_geo["lat"], start_geo["lon"], dest_geo["lat"], dest_geo["lon"])
        distance_comment = f"{km:,.0f} km · {classify_distance(km)}"

    days = duration_to_days(payload["duration"])

    snapshot = fetch_open_meteo_recent_snapshot(dest_geo["lat"], dest_geo["lon"]) if dest_geo else None
    forecast = None
    forecast_note = None

    start_d: date = payload["start_date_obj"]
    delta = (start_d - date.today()).days
    if dest_geo and -1 <= delta <= 15:
        forecast = fetch_open_meteo_forecast(dest_geo["lat"], dest_geo["lon"], days)
        forecast_note = "시작일이 가까워서(±16일) 예보 기반으로 표시했어."
    else:
        forecast_note = "시작일이 예보 범위 밖이라 ‘최근 스냅샷 + 월 힌트’로 감 잡기 모드!"

    pois_all = []
    if dest_geo:
        pois_all = fetch_pois_overpass(
            dest_geo["lat"],
            dest_geo["lon"],
            radius_km=float(st.session_state.poi_radius_km),
            limit=int(st.session_state.poi_limit),
        )

    allowed_types = set(st.session_state.poi_types or [])
    pois_filtered = [p for p in pois_all if (p.get("type") in allowed_types)] if allowed_types else pois_all
    # 필터로 전부 날아가면 전체 POI 사용
    if not pois_filtered:
        pois_filtered = pois_all

    exclude_names = set(st.session_state.poi_user_exclude or set())
    styles = payload.get("travel_style", [])
    poi_daymap = build_itinerary_from_pois(pois_filtered, styles, days=days, exclude_names=exclude_names)

    move_mode_setting = st.session_state.move_mode
    day_travel_times = build_day_travel_times(
        poi_daymap,
        styles=styles,
        radius_km=float(st.session_state.poi_radius_km),
        move_mode_setting=move_mode_setting,
        return_to_center=bool(st.session_state.include_return_to_center),
    )
    mode_used = None
    if day_travel_times:
        mode_used = day_travel_times.get(1, {}).get("mode") or None

    err = None
    openai_key = (st.session_state.get("openai_api_key") or "").strip()
    plan = None

    enriched_payload = dict(payload)
    enriched_payload.pop("start_date_obj", None)
    enriched_payload["distance_km_estimate"] = km
    enriched_payload["distance_comment"] = distance_comment
    enriched_payload["weather_snapshot"] = snapshot
    enriched_payload["weather_forecast_daily"] = forecast.get("daily") if forecast else None
    enriched_payload["poi_sample"] = [{"name": p["name"], "type": p["type"]} for p in pois_filtered[:25]]
    enriched_payload["estimated_day_travel_times"] = {
        str(d): {"mode": info.get("mode"), "total_minutes": info.get("total_minutes"), "total_km": info.get("total_km")}
        for d, info in day_travel_times.items()
    }
    enriched_payload["note"] = "이동시간은 직선거리+오버헤드 기반 추정치임(실제 경로/교통상황과 다를 수 있음)."

    if openai_key:
        plan, err = call_openai_plan(openai_key, enriched_payload)

    if not plan:
        plan = build_rule_based_plan(payload, km=km, snapshot=snapshot, poi_daymap=poi_daymap)

    totals = [v.get("total_minutes", 0) for v in day_travel_times.values() if isinstance(v, dict)]
    if totals:
        avg_min = int(round(sum(totals) / len(totals)))
        plan.setdefault("tips", [])
        plan["tips"].insert(0, f"⏱️ 이동시간(추정): Day1 {day_travel_times.get(1,{}).get('total_minutes',0)}분 / 평균 {avg_min}분 (이동수단: {mode_used or '자동'})")

    meta = {
        "dest_geo": dest_geo,
        "start_geo": start_geo,
        "distance_km": km,
        "distance_comment": distance_comment,
        "weather_snapshot": snapshot,
        "weather_forecast": forecast,
        "weather_note": forecast_note,
        "poi_total": len(pois_all),
        "poi_used": len(pois_filtered),
        "day_travel_times": day_travel_times,
        "move_mode_setting": move_mode_setting,
        "move_mode_used": mode_used
        or (infer_move_mode(styles, float(st.session_state.poi_radius_km)) if move_mode_setting == "자동" else move_mode_setting),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    bundle = {
        "payload": payload,
        "meta": meta,
        "pois": pois_filtered,
        "poi_daymap": poi_daymap,
        "plan": plan,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }

    st.session_state.last_payload_sig = sig
    st.session_state.last_bundle = bundle
    st.session_state.itinerary_edits = {}

    return bundle, err


def page3():
    st.markdown(
        """
        <div class="tm-card">
          <h3>결과 나왔다 🧾✨</h3>
          <div class="tm-tip">동선도 짰고, 이제 “이동시간(추정)”까지 깔끔하게 잡아줄게 😎</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("플랜 생성 중… (POI 수집 → 동선 최적화 → 이동시간 추정 → 일정 구성)"):
        bundle, err = generate_bundle()

    payload = bundle["payload"]
    meta = bundle["meta"]
    plan = bundle["plan"]
    pois = bundle["pois"]
    poi_daymap = bundle["poi_daymap"]
    day_times = meta.get("day_travel_times", {}) or {}

    if err:
        st.warning(f"OpenAI 쪽은 실패했지만, 플랜은 POI 최적화 룰베이스로 완주했어 🛟\n\n사유: {err}")

    dest_geo = meta.get("dest_geo")
    dest_name = dest_geo["display_name"] if dest_geo else (payload.get("destination_text") or "미입력(이러면 추천이 ‘감’이 됨)")
    styles = payload.get("travel_style", [])
    days = duration_to_days(payload["duration"])

    st.markdown(
        f"""
        <div class="tm-card">
          <div class="tm-section-title">📌 입력 요약</div>
          <div class="tm-tip">
            • 여행시기: <b>{payload["travel_month"]}</b><br/>
            • 시작일: <b>{payload["start_date"]}</b><br/>
            • 인원/관계: <b>{payload["party_count"]}명 · {payload["party_type"]}</b><br/>
            • 여행지: <b>{payload["destination_scope"]} · {dest_name}</b><br/>
            • 일정: <b>{payload["duration"]}</b><br/>
            • 스타일: <b>{", ".join(styles) if styles else "선택없음(=만능 캐릭터)"}</b><br/>
            • 예산: <b>{payload["budget"]:,}원</b><br/>
            • 출발지 기준 거리: <b>{meta.get("distance_comment","")}</b><br/>
            • 이동수단(시간추정): <b>{meta.get("move_mode_used","")}</b><br/>
            <span class="tm-micro">* 시즌 힌트: {month_hint(payload["travel_month"])}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    snapshot = meta.get("weather_snapshot")
    forecast = meta.get("weather_forecast")
    st.markdown('<div class="tm-section-title">🌦️ 날씨</div>', unsafe_allow_html=True)
    st.markdown('<div class="tm-card">', unsafe_allow_html=True)
    st.write(f"- 안내: {meta.get('weather_note','')}")
    if snapshot:
        st.write(f"- 최근 7일 스냅샷: 평균 {snapshot['avg_min']}~{snapshot['avg_max']}°C, 누적 강수 {snapshot['total_prcp']}mm")
    if forecast and forecast.get("daily"):
        st.write("- 예보(최대 16일 범위):")
        for d in forecast["daily"][: min(len(forecast["daily"]), days)]:
            st.write(f"  - {d['date']}: {d['tmin']}~{d['tmax']}°C, 강수 {d['prcp']}mm")
    st.markdown("</div>", unsafe_allow_html=True)

    tab_plan, tab_move, tab_poi, tab_budget, tab_check, tab_export = st.tabs(
        ["🧾 플랜", "⏱️ 이동시간", "🗺️ 지도+POI", "💸 예산", "✅ 체크리스트", "📤 내보내기"]
    )

    with tab_plan:
        st.markdown(
            f"""
            <div class="tm-card">
              <div class="tm-section-title">🧾 추천 여행 계획</div>
              <h3 style="margin:0;">{plan.get("headline","")}</h3>
              <div class="tm-tip" style="margin-top:.35rem;">{plan.get("summary","")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        ensure_itinerary_edits(days, plan)

        if st.session_state.get("enable_edit", True):
            st.caption("편집 모드 ON ✅ (오전/오후/밤을 바꿔서 ‘내 플랜’로 커스터마이징)")
            for d in range(1, days + 1):
                with st.expander(f"Day {d} 편집하기", expanded=(d == 1)):
                    ed = st.session_state.itinerary_edits.get(d, {"am": "", "pm": "", "night": ""})
                    ed["am"] = st.text_input(f"Day {d} - 오전", value=ed["am"], key=f"edit_am_{d}")
                    ed["pm"] = st.text_input(f"Day {d} - 오후", value=ed["pm"], key=f"edit_pm_{d}")
                    ed["night"] = st.text_input(f"Day {d} - 밤", value=ed["night"], key=f"edit_night_{d}")
                    st.session_state.itinerary_edits[d] = ed
            final_plan = apply_itinerary_edits(plan)
        else:
            final_plan = plan

        st.markdown('<div class="tm-section-title">📆 Day-by-Day</div>', unsafe_allow_html=True)
        for b in final_plan.get("day_blocks", []):
            day = b.get("day", "?")
            title = b.get("title", f"Day {day}")
            items = b.get("plan", [])
            with st.expander(f"{title} (Day {day})", expanded=(str(day) == "1")):
                try:
                    dnum = int(day)
                except Exception:
                    dnum = None
                if dnum and dnum in day_times:
                    info = day_times[dnum]
                    st.write(f"**⏱️ 이동시간 추정:** {info.get('total_minutes',0)}분 · {info.get('total_km',0)}km · {info.get('mode','')}")
                    st.caption(info.get("note", ""))
                for it in items:
                    st.write(f"- {it}")

        tips = final_plan.get("tips", []) or []
        if tips:
            st.markdown('<div class="tm-section-title">🧠 꿀팁</div>', unsafe_allow_html=True)
            st.markdown('<div class="tm-card">', unsafe_allow_html=True)
            for t in tips:
                st.write(f"- {t}")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="tm-section-title">🔎 Sources (AI가 참고한 곳)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-card">', unsafe_allow_html=True)
        sources = final_plan.get("sources", []) or []
        if sources:
            for s in sources:
                if isinstance(s, dict):
                    t = s.get("title", "source")
                    u = s.get("url", "")
                    note = s.get("note", "")
                    st.write(f"- {t} — {u}" + (f" ({note})" if note else ""))
                else:
                    st.write(f"- {s}")
        else:
            st.write("- (OpenAI 키 없이 생성했거나, 모델이 출처를 못 가져온 경우 비어있을 수 있어요.)")
        st.markdown("</div>", unsafe_allow_html=True)

        bundle["plan"] = final_plan

    with tab_move:
        st.markdown(
            """
            <div class="tm-card">
              <div class="tm-section-title">⏱️ Day별 이동시간(추정치)</div>
              <div class="tm-tip">직선거리(POI 간) + 구간별 오버헤드(대기/주차/신호)로 계산한 추정치야.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not day_times:
            st.info("이동시간을 계산할 POI가 부족해요. (목적지/POI 상태 확인 or 반경/POI 수 늘려봐!)")
        else:
            for d in range(1, days + 1):
                info = day_times.get(d, {"total_minutes": 0, "total_km": 0, "mode": "", "legs": []})
                with st.expander(
                    f"Day {d} — {info.get('total_minutes',0)}분 · {info.get('total_km',0)}km · {info.get('mode','')}",
                    expanded=(d == 1),
                ):
                    st.caption(info.get("note", ""))
                    legs = info.get("legs", [])
                    if not legs:
                        st.write("- (이동 구간 없음)")
                    else:
                        st.write("- 구간별(추정):")
                        for lg in legs:
                            to = lg["to"]
                            to_label = f"POI#{to+1}" if isinstance(to, int) else "center(대략 숙소)"
                            frm = lg["from"]
                            frm_label = f"POI#{frm+1}" if isinstance(frm, int) else str(frm)
                            st.write(f"  - {frm_label} → {to_label}: {lg['km']}km / {lg['minutes']}분")

    with tab_poi:
        st.markdown(
            f"""
            <div class="tm-card">
              <div class="tm-section-title">📍 POI 자동 수집 결과</div>
              <div class="tm-tip">
                • 전체 수집: <b>{meta.get("poi_total", 0)}</b>개 / 필터 반영: <b>{meta.get("poi_used", 0)}</b>개<br/>
                • 팁: POI가 잡음이면 “제외” 체크로 바로 정리하면 됨 😎
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.get("show_map", True):
            st.markdown('<div class="tm-section-title">🗺️ 지도</div>', unsafe_allow_html=True)
            st.markdown('<div class="tm-card">', unsafe_allow_html=True)
            render_map(dest_geo, pois)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="tm-section-title">🧹 POI 정리(원치 않는 곳 제외)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-card">', unsafe_allow_html=True)

        if not pois:
            st.info("POI를 못 가져왔어… (목적지 좌표/Overpass 상태 확인). 그래도 플랜은 계속 가능!")
        else:
            cols = st.columns([3, 1, 1, 1])
            cols[0].markdown("**이름**")
            cols[1].markdown("**타입**")
            cols[2].markdown("**제외**")
            cols[3].markdown("**대략거리(중심)**")

            exclude_set = set(st.session_state.poi_user_exclude or set())
            center_lat = dest_geo["lat"] if dest_geo else pois[0]["lat"]
            center_lon = dest_geo["lon"] if dest_geo else pois[0]["lon"]

            display_n = min(len(pois), 60)
            for i in range(display_n):
                p = pois[i]
                row = st.columns([3, 1, 1, 1])
                row[0].write(p["name"])
                row[1].write(p["type"])
                checked = row[2].checkbox("", value=(p["name"] in exclude_set), key=f"exclude_{p['osm_id']}_{i}")
                if checked:
                    exclude_set.add(p["name"])
                else:
                    exclude_set.discard(p["name"])

                dist = haversine_km(center_lat, center_lon, p["lat"], p["lon"])
                row[3].write(f"{dist:.1f}km")

            st.session_state.poi_user_exclude = exclude_set
            st.caption("제외 변경 후 아래 ‘재최적화’ 버튼을 누르면 일정/이동시간이 새로 계산돼요.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="tm-section-title">🧠 일자별 POI(자동 묶기)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-card">', unsafe_allow_html=True)
        for d in range(1, days + 1):
            day_pois = poi_daymap.get(d, [])
            if day_pois:
                st.write(f"- Day {d}: " + " → ".join([f"{p['name']}({p['type']})" for p in day_pois[:8]]))
            else:
                st.write(f"- Day {d}: (POI 부족/제외됨) — 여유코스/휴식/근처 산책 추천")
        st.markdown("</div>", unsafe_allow_html=True)

        if st.button("POI 제외 반영 + 일정/이동시간 재최적화 🔄", use_container_width=True):
            st.session_state.last_payload_sig = None
            st.rerun()

    with tab_budget:
        if st.session_state.get("show_budget", True):
            alloc = allocate_budget(int(payload["budget"]), payload.get("travel_mode", "자유여행"), styles)
            st.markdown('<div class="tm-card">', unsafe_allow_html=True)
            st.markdown('<div class="tm-section-title">💸 예산 분배(추천)</div>', unsafe_allow_html=True)
            st.write(f"- 예산 무드: **{budget_tier(int(payload['budget']))}**")
            for k, v in alloc.items():
                st.write(f"- {k}: **{v:,}원**")
            st.caption("※ 실제 비용은 여행지/시즌/환율/취향에 따라 달라요.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("사이드바에서 ‘예산 분배 표시’를 켜면 나와요.")

    with tab_check:
        if st.session_state.get("show_checklist", True):
            checklist = build_checklist(payload["destination_scope"], payload["travel_month"], styles, payload["party_type"])
            st.markdown('<div class="tm-card">', unsafe_allow_html=True)
            st.markdown('<div class="tm-section-title">✅ 체크리스트(준비물)</div>', unsafe_allow_html=True)
            cols = st.columns(3)
            keys = list(checklist.keys())
            for i, key in enumerate(keys):
                with cols[i]:
                    st.markdown(f"**{key}**")
                    for item in checklist[key]:
                        st.write(f"- {item}")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("사이드바에서 ‘체크리스트 표시’를 켜면 나와요.")

    with tab_export:
        st.markdown(
            """
            <div class="tm-card">
              <div class="tm-section-title">📤 내보내기 (JSON / ICS / PDF)</div>
              <div class="tm-tip">JSON/캘린더/리포트로 저장 가능.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        export_bundle = {
            "app": APP_NAME,
            "payload": {k: v for k, v in payload.items() if k != "start_date_obj"},
            "meta": meta,
            "plan": bundle["plan"],
            "pois": pois[:100],
            "exported_at": datetime.now().isoformat(timespec="seconds"),
        }
        json_bytes = json.dumps(export_bundle, ensure_ascii=False, indent=2).encode("utf-8")

        st.download_button(
            "📥 JSON 다운로드",
            data=json_bytes,
            file_name=f"travel-maker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

        ics_text = make_ics({"payload": payload, "plan": bundle["plan"], "meta": meta, "exported_at": export_bundle["exported_at"]})
        st.download_button(
            "🗓️ ICS(캘린더) 다운로드",
            data=ics_text.encode("utf-8"),
            file_name=f"travel-maker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ics",
            mime="text/calendar",
            use_container_width=True,
        )

        pdf_bytes = make_pdf_bytes({"payload": payload, "plan": bundle["plan"], "meta": meta, "exported_at": export_bundle["exported_at"]})
        if pdf_bytes is None:
            st.info("PDF 내보내기는 `reportlab` 설치가 필요해요: `pip install reportlab`")
        else:
            st.download_button(
                "🧾 PDF 다운로드",
                data=pdf_bytes,
                file_name=f"travel-maker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    nav = st.columns([1, 1, 2])
    with nav[0]:
        if st.button("👈 입력 수정", use_container_width=True):
            st.session_state.step = 1
    with nav[1]:
        if st.button("⬅️ 추가 정보 수정", use_container_width=True):
            st.session_state.step = 2
    with nav[2]:
        if st.button("완전 새로 뽑기(캐시 초기화) 🔄", use_container_width=True):
            st.session_state.last_payload_sig = None
            st.session_state.last_bundle = None
            st.rerun()


def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🧳", layout="wide")
    init_state()
    render_header()
    render_sidebar()

    if st.session_state.step == 1:
        page1()
    elif st.session_state.step == 2:
        page2()
    else:
        page3()


if __name__ == "__main__":
    main()



