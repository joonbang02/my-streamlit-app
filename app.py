# =========================
# PART 1/3
# =========================

import os
import math
import time
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple

import requests
import streamlit as st
import pydeck as pdk

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
        "poi_radius_km": 5,
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
def fetch_pois_overpass(lat: float, lon: float, radius_km: float, limit: int) -> List[Dict[str, Any]]:
    south, west, north, east = _radius_to_bbox(lat, lon, radius_km)
    query = _overpass_query_bbox(south, west, north, east)
    url = "https://overpass-api.de/api/interpreter"
    try:
        r = requests.post(url, data=query.encode("utf-8"), timeout=35)
        r.raise_for_status()
        data = r.json()
        elements = data.get("elements", []) or []
        pois = []
        for el in elements:
            tags = el.get("tags", {}) or {}
            name = tags.get("name")
            if not name:
                continue
            plat = el.get("lat") or (el.get("center", {}) or {}).get("lat")
            plon = el.get("lon") or (el.get("center", {}) or {}).get("lon")
            if plat is None or plon is None:
                continue
            ptype = _poi_type(tags)
            pois.append(
                {
                    "name": name,
                    "lat": float(plat),
                    "lon": float(plon),
                    "type": ptype,
                    "tags": tags,
                    "osm_id": el.get("id"),
                }
            )

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
# =========================
# PART 2/3
# =========================


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
        legs.append(
            {
                "from": i,
                "to": i + 1,
                "km": round(km, 2),
                "minutes": int(round(minutes)),
            }
        )
        total_km += km
        total_min += minutes

    if return_to_center:
        last = points[-1]
        km = haversine_km(last[0], last[1], center[0], center[1])
        minutes = (km / speed) * 60.0 + overhead
        legs.append(
            {
                "from": len(points) - 1,
                "to": "center",
                "km": round(km, 2),
                "minutes": int(round(minutes)),
            }
        )
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
        day_times[d] = estimate_route_time_minutes(
            pts, mode=mode, return_to_center=return_to_center
        )

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
        return {
            "숙소": 0.35,
            "식비": 0.22,
            "교통": 0.12,
            "체험/투어": 0.20,
            "쇼핑": 0.06,
            "기타": 0.05,
        }
    return {
        "숙소": 0.32,
        "식비": 0.22,
        "교통": 0.16,
        "체험/투어": 0.16,
        "쇼핑": 0.08,
        "기타": 0.06,
    }


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
# =========================
# PART 3/3
# =========================


def build_checklist(destination_scope: str, month: str, style: List[str], party_type: str) -> Dict[str, List[str]]:
    packing = [
        "보조배터리(진짜 생존템)",
        "편한 신발",
        "상비약/밴드",
        "우산 or 우비",
        "충전기/케이블",
    ]
    docs = []
    money = ["카드 2장 이상", "교통카드/현지 교통 앱"]

    if destination_scope == "해외":
        docs += ["여권", "항공권/숙소 예약 내역", "여행자보험", "멀티어댑터"]
        money += ["현지 소액 현금"]

    if month != "상관없음":
        try:
            m = int(month.replace("월", ""))
        except Exception:
            m = None
        if m in [12, 1, 2]:
            packing += ["방한 외투", "장갑/목도리"]
        if m in [6, 7, 8]:
            packing += ["선크림", "모자", "벌레 퇴치제"]

    if "로드트립" in style:
        packing += ["면허증", "차량 충전기"]
    if "유흥" in style:
        packing += ["예쁜(?) 옷 한 벌"]
    if "식도락" in style:
        packing += ["소화제"]
    if party_type in ["부모님", "가족"]:
        packing += ["체력 무리 없는 일정"]

    def dedupe(seq):
        out, seen = [], set()
        for x in seq:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    return {
        "서류/예약": dedupe(docs) if docs else ["(국내면 생략 가능)"],
        "필수 짐": dedupe(packing),
        "돈/결제": dedupe(money),
    }


def call_openai_plan(openai_api_key: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if OpenAI is None:
        return None, "openai 패키지가 없어요."
    try:
        client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        return None, str(e)

    model = "gpt-5.2"  # ✅ 요청대로 고정

    instructions = (
        "너는 Travel-Maker 여행 플래너야.\n"
        "도시 단위 기준으로 여행 일정을 만들어.\n"
        "Day별 오전/오후/밤 구조 유지.\n"
        "가능하면 web_search 참고하고 sources에 출처 표시.\n"
        "반드시 JSON만 출력."
    )

    try:
        resp = client.responses.create(
            model=model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            tools=[{"type": "web_search"}],
            include=["web_search_call.action.sources"],
            max_output_tokens=1700,
        )
    except Exception as e:
        return None, str(e)

    text = getattr(resp, "output_text", None)
    if not text:
        return None, "응답 없음"

    try:
        plan = json.loads(text)
    except Exception:
        return None, "JSON 파싱 실패"

    return plan, None


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
        "start_date_obj": st.session_state.start_date,
        "travel_mode": st.session_state.travel_mode_sidebar,
    }


def payload_signature(payload: Dict[str, Any]) -> str:
    p = dict(payload)
    p.pop("start_date_obj", None)
    return json.dumps(p, ensure_ascii=False, sort_keys=True)


def generate_bundle() -> Tuple[Dict[str, Any], Optional[str]]:
    payload = build_payload()
    sig = payload_signature(payload)

    if st.session_state.last_payload_sig == sig and st.session_state.last_bundle:
        return st.session_state.last_bundle, None

    dest_geo = geocode_place(payload["destination_text"])
    start_geo = geocode_place(payload["start_city"])

    # ✅ 국가 단위 입력 UX 안내 (요청사항)
    if dest_geo:
        display = (dest_geo.get("display_name") or "").lower()
        if any(k in display for k in ["canada", "united states", "japan", "australia"]):
            st.info(
                "입력한 값이 국가 단위로 인식됐어요. "
                "도시로 입력하면 일정/동선/이동시간 정확도가 훨씬 좋아져요!"
            )

    km = None
    if dest_geo and start_geo:
        km = haversine_km(start_geo["lat"], start_geo["lon"], dest_geo["lat"], dest_geo["lon"])

    days = duration_to_days(payload["duration"])

    pois = []
    if dest_geo:
        pois = fetch_pois_overpass(
            dest_geo["lat"],
            dest_geo["lon"],
            st.session_state.poi_radius_km,
            st.session_state.poi_limit,
        )

    poi_daymap = build_itinerary_from_pois(pois, payload["travel_style"], days)
    day_travel_times = build_day_travel_times(
        poi_daymap,
        payload["travel_style"],
        st.session_state.poi_radius_km,
        st.session_state.move_mode,
        st.session_state.include_return_to_center,
    )

    err = None
    plan = None
    if st.session_state.openai_api_key:
        plan, err = call_openai_plan(st.session_state.openai_api_key, payload)

    if not plan:
        plan = {
            "headline": f"{payload['destination_text']} {days}일 여행 플랜",
            "summary": "도시 기준으로 하루 동선을 묶은 일정이에요.",
            "day_blocks": [],
            "tips": [],
            "sources": [],
        }
        for d in range(1, days + 1):
            plan["day_blocks"].append(
                {
                    "day": d,
                    "title": f"Day {d}",
                    "plan": [
                        "☀️ 오전: 핵심 스팟",
                        "🌤️ 오후: 취향 코스",
                        "🌙 밤: 맛집/휴식",
                    ],
                }
            )

    bundle = {
        "payload": payload,
        "plan": plan,
        "pois": pois,
        "poi_daymap": poi_daymap,
        "meta": {
            "dest_geo": dest_geo,
            "start_geo": start_geo,
            "distance_km": km,
            "day_travel_times": day_travel_times,
        },
    }

    st.session_state.last_payload_sig = sig
    st.session_state.last_bundle = bundle
    return bundle, err


def page2():
    st.session_state.duration = st.selectbox(
        "여행 일정", ["당일치기", "3일", "5일", "10일 이상"], index=1
    )
    st.session_state.budget = st.number_input(
        "예산(원)", min_value=0, max_value=20000000, value=st.session_state.budget, step=50000
    )
    st.session_state.travel_style = st.multiselect(
        "여행 스타일",
        ["힐링", "식도락", "유흥", "로드트립", "문화/예술", "자연"],
        default=st.session_state.travel_style,
    )

    if st.button("여행 계획 생성"):
        st.session_state.step = 3


def page3():
    bundle, err = generate_bundle()
    plan = bundle["plan"]

    if err:
        st.warning(err)

    st.subheader(plan.get("headline", "여행 플랜"))
    st.write(plan.get("summary", ""))

    for b in plan.get("day_blocks", []):
        with st.expander(b.get("title", "")):
            for line in b.get("plan", []):
                st.write(line)


def render_header():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="tm-title">{APP_NAME}<span class="tm-badge">trip optimizer</span></div>
        <div class="tm-subtitle">도시 기준 · 이동시간까지 계산해주는 여행 플래너 😎</div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    st.sidebar.markdown("### 🔑 OpenAI API Key")
    st.session_state.openai_api_key = st.sidebar.text_input("OPENAI_API_KEY", type="password")

    st.sidebar.markdown("---")
    st.session_state.start_city = st.sidebar.text_input("출발 도시", value=st.session_state.start_city)
    st.session_state.start_date = st.sidebar.date_input("여행 시작일", value=st.session_state.start_date)


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
