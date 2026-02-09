import os
import math
import time
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable, Set

import requests
import streamlit as st
import pydeck as pdk

# =========================
# Logging
# =========================
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("travel-maker")

# =========================
# External APIs
# =========================
AMADEUS_BASE_URL = "https://test.api.amadeus.com"
@st.cache_data(show_spinner=False, ttl=1800)
def get_amadeus_token(client_id: str, client_secret: str) -> str:
    if not client_id or not client_secret:
        raise ApiError("Amadeus API 키가 비어 있어요.")

    url = f"{AMADEUS_BASE_URL}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    r = requests.post(url, data=data, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

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

# =========================
# UI Theme
# =========================
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

# =========================
# Session State (structured)
# =========================
def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 1

    if "app" not in st.session_state:
        st.session_state.app = {
            "input": {
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
                "travel_mode": "자유여행",
            },
            "ui": {
                "openai_api_key": "",
                "move_mode": "자동",
                "include_return_to_center": True,
                "show_map": True,
                "show_budget": True,
                "show_checklist": True,
                "enable_edit": True,
                "poi_radius_km": 8,
                "poi_limit": 50,
                "poi_types": ["관광", "맛집", "카페", "자연", "문화"],
                "debug_panel": False,
                "openai_api_key": "",
                "amadeus_client_id": "",
                "amadeus_client_secret": "",
                "use_amadeus_hotel": False,
            },
            "cache": {
                "last_payload_sig": None,
                "last_bundle": None,
            },
            "runtime": {
                "itinerary_edits": {},
                "poi_user_exclude_ids": set(),  # ✅ now exclude by osm_id
            },
            "hotel": {
                "stars": [3, 4],
                "max_price_per_night": 0,
                "limit": 3,
                "reorder_by_hotel": True,
            },
        }


def sget(path: str, default=None):
    cur = st.session_state.app
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def sset(path: str, value):
    cur = st.session_state.app
    keys = path.split(".")
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


# =========================
# Helpers
# =========================
STAY_MINUTES = {
    "관광": 90,
    "문화": 90,
    "자연": 75,
    "맛집": 60,
    "카페": 45,
    "유흥": 120,
    "편의": 20,
}
# =========================
# Hotel Helpers
# =========================
def amadeus_hotels_by_geocode(lat, lon, token, radius_km=5):
    url = f"{AMADEUS_BASE_URL}/v1/reference-data/locations/hotels/by-geocode"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": radius_km,
        "radiusUnit": "KM",
        "hotelSource": "ALL",
    }

    r = requests.get(url, headers=headers, params=params, timeout=12)
    r.raise_for_status()
    return r.json().get("data", [])
    
def amadeus_hotel_offers(hotel_ids, token, checkin, checkout, adults):
    url = f"{AMADEUS_BASE_URL}/v3/shopping/hotel-offers"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "hotelIds": ",".join(hotel_ids),
        "checkInDate": checkin,
        "checkOutDate": checkout,
        "adults": adults,
        "currency": "KRW",
    }

    r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("data", [])
    
def fetch_hotels_amadeus(center_lat, center_lon, payload, hotel_opts):
    token = get_amadeus_token(
        sget("ui.amadeus_client_id"),
        sget("ui.amadeus_client_secret"),
    )

    nights = duration_to_days(payload["duration"])
    checkin = payload["start_date"]
    checkout = (date.fromisoformat(checkin) + timedelta(days=nights)).isoformat()

    hotels_raw = amadeus_hotels_by_geocode(center_lat, center_lon, token)
    hotel_ids = [h["hotelId"] for h in hotels_raw[:20]]

    offers = amadeus_hotel_offers(
        hotel_ids,
        token,
        checkin,
        checkout,
        payload["party_count"],
    )

    normalized = []
    for h in offers:
        hotel = h.get("hotel", {})
        offer = h.get("offers", [{}])[0]

        total_price = int(float(offer.get("price", {}).get("total", 0)))

        normalized.append({
            "name": hotel.get("name", "Hotel"),
            "lat": hotel.get("geoCode", {}).get("latitude"),
            "lon": hotel.get("geoCode", {}).get("longitude"),
            "stars": int(hotel.get("rating", 3)),
            "price": int(total_price / max(1, nights)),  # 1박 가격
            "amenities": [],
            "source": "amadeus",
        })

    return normalized

def compute_itinerary_center(poi_daymap):
    pois = [p for day in poi_daymap.values() for p in day]
    if not pois:
        return None
    lat = sum(p["lat"] for p in pois) / len(pois)
    lon = sum(p["lon"] for p in pois) / len(pois)
    return lat, lon


def fetch_hotels_mock(center_lat, center_lon, stars, max_price, limit):
    base_prices = {1: 60000, 2: 90000, 3: 130000, 4: 190000, 5: 320000}
    hotels = []

    for i, s in enumerate(stars or [3, 4]):
        price = base_prices.get(s, 150000)
        if max_price and price > max_price:
            continue
        hotels.append(
            {
                "name": f"추천 호텔 {i+1} ({s}성)",
                "lat": center_lat + 0.002 * (i + 1),
                "lon": center_lon - 0.002 * (i + 1),
                "stars": s,
                "price": price,
                "amenities": ["wifi", "parking"] if s >= 3 else ["wifi"],
            }
        )
    return hotels[:limit]


def score_hotel(hotel, center_lat, center_lon, styles, max_price):
    score = 0.0
    dist = haversine_km(center_lat, center_lon, hotel["lat"], hotel["lon"])
    score += max(0.0, 3.5 - dist) * 0.7
    score += hotel.get("stars", 3) * 0.25

    if max_price and hotel.get("price"):
        score += 0.6 if hotel["price"] <= max_price else -0.8

    if "힐링" in styles and hotel.get("stars", 3) >= 4:
        score += 0.6
    if "로드트립" in styles and "parking" in hotel.get("amenities", []):
        score += 0.4

    return round(score, 3)

def recommend_hotels(poi_daymap, styles, hotel_opts, payload=None):
    center = compute_itinerary_center(poi_daymap)
    if not center:
        return []

    lat, lon = center

    use_amadeus = bool(sget("ui.use_amadeus_hotel"))
    hotels = []

    try:
        if use_amadeus and payload:
            hotels = fetch_hotels_amadeus(lat, lon, payload, hotel_opts)
        else:
            hotels = fetch_hotels_mock(
                lat,
                lon,
                hotel_opts.get("stars", []),
                hotel_opts.get("max_price_per_night"),
                hotel_opts.get("limit", 3),
            )
    except Exception as e:
        logger.warning("Amadeus 실패 → mock fallback: %s", e)
        hotels = fetch_hotels_mock(
            lat,
            lon,
            hotel_opts.get("stars", []),
            hotel_opts.get("max_price_per_night"),
            hotel_opts.get("limit", 3),
        )

    scored = []
    for h in hotels:
        s = score_hotel(h, lat, lon, styles, hotel_opts.get("max_price_per_night"))
        scored.append({**h, "score": s})

    return sorted(scored, key=lambda x: x["score"], reverse=True)

    center = compute_itinerary_center(poi_daymap)
    if not center:
        return []

    lat, lon = center
    hotels = fetch_hotels_mock(
        lat,
        lon,
        hotel_opts.get("stars", []),
        hotel_opts.get("max_price_per_night"),
        hotel_opts.get("limit", 3),
    )

    scored = []
    for h in hotels:
        s = score_hotel(h, lat, lon, styles, hotel_opts.get("max_price_per_night"))
        scored.append({**h, "score": s})

    return sorted(scored, key=lambda x: x["score"], reverse=True)
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


# =========================
# Robust HTTP wrapper
# =========================
class ApiError(Exception):
    pass


def _request_json(
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    data: Optional[bytes] = None,
    headers: Optional[dict] = None,
    timeout: int = 12,
    retries: int = 2,
    backoff: float = 0.5,
    name: str = "API",
) -> Any:
    last_exc = None
    for attempt in range(retries + 1):
        try:
            r = requests.request(method, url, params=params, data=data, headers=headers, timeout=timeout)
            # overpass can 429/504; treat as retryable
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{name} retryable status={r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            logger.warning("%s timeout/conn error (attempt %s/%s): %s", name, attempt + 1, retries + 1, e)
        except requests.HTTPError as e:
            last_exc = e
            code = getattr(e.response, "status_code", None)
            logger.warning("%s http error (attempt %s/%s): %s", name, attempt + 1, retries + 1, code)
        except Exception as e:
            last_exc = e
            logger.exception("%s unknown error: %s", name, e)

        if attempt < retries:
            time.sleep(backoff * (2**attempt))

    raise ApiError(f"{name} 호출 실패: {last_exc}")


# =========================
# Geocoding (Nominatim) - improved selection
# =========================
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 7)  # ✅ 7 days
def geocode_place(query: str) -> Optional[Dict[str, Any]]:
    if not query or not query.strip():
        return None

    headers = {"User-Agent": f"{APP_NAME}/1.0 (streamlit)"}
    params = {
        "q": query,
        "format": "json",
        "limit": 3,  # ✅ get a few candidates
        "addressdetails": 1,
    }

    try:
        time.sleep(0.15)  # ✅ be nice to nominatim
        data = _request_json("GET", NOMINATIM_URL, params=params, headers=headers, timeout=12, retries=1, name="Nominatim")
        if not data:
            return None

        # Prefer city/town, then administrative, then best importance
        def score(item: dict) -> float:
            t = item.get("type") or ""
            cls = item.get("class") or ""
            imp = float(item.get("importance") or 0.0)
            s = imp
            if t in ("city", "town"):
                s += 2.0
            if cls == "place":
                s += 0.4
            if t in ("administrative",):
                s += 0.6
            # Penalize country-level matches a bit
            if t == "country" or cls == "boundary":
                s -= 1.2
            return s

        best = sorted(data, key=score, reverse=True)[0]
        return {
            "lat": float(best["lat"]),
            "lon": float(best["lon"]),
            "display_name": best.get("display_name", query),
            "raw": {"type": best.get("type"), "class": best.get("class"), "importance": best.get("importance")},
        }
    except Exception:
        return None


# =========================
# Weather (Open-Meteo)
# =========================
@st.cache_data(show_spinner=False, ttl=60 * 60)  # ✅ 1 hour
def fetch_open_meteo_forecast(lat: float, lon: float, days: int) -> Optional[Dict[str, Any]]:
    try:
        n = max(1, min(days, 16))
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": n,
        }
        j = _request_json("GET", OPEN_METEO_URL, params=params, timeout=12, retries=1, name="Open-Meteo(Forecast)")
        d = (j or {}).get("daily", {}) or {}
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


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)  # ✅ 6 hours
def fetch_open_meteo_recent_snapshot(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": 7,
        }
        j = _request_json("GET", OPEN_METEO_URL, params=params, timeout=12, retries=1, name="Open-Meteo(Snapshot)")
        d = (j or {}).get("daily", {}) or {}
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


# =========================
# Overpass POI
# =========================
def _radius_to_bbox(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    lat_deg = radius_km / 110.574
    lon_deg = radius_km / (111.320 * math.cos(math.radians(lat)) + 1e-9)
    return (lat - lat_deg, lon - lon_deg, lat + lat_deg, lon + lon_deg)


def _overpass_query_bbox(south, west, north, east) -> str:
    # (keep it simple: nodes only; stable & fast)
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


def _poi_quality_score(tags: Dict[str, Any]) -> float:
    """
    강화된 POI 품질 휴리스틱:
    - 실제 방문 가치가 낮은 잡음 POI 제거
    """
    s = 0.0

    # 신뢰 신호
    if tags.get("wikidata"):
        s += 0.35
    if tags.get("wikipedia"):
        s += 0.35
    if tags.get("image"):
        s += 0.2
    if tags.get("website"):
        s += 0.1
    if tags.get("opening_hours"):
        s += 0.05
    if tags.get("tourism") == "museum":
        s += 0.12

    # ❌ 맛집 잡음 제거
    if tags.get("amenity") == "restaurant":
        if not any(tags.get(k) for k in ("opening_hours", "website", "cuisine", "wikidata")):
            s -= 0.3

    # ❌ 관광지 잡음 제거
    if tags.get("tourism") == "attraction":
        if not any(tags.get(k) for k in ("wikidata", "wikipedia", "description")):
            s -= 0.25

    # ❌ 너무 일반적인 이름
    nm = (tags.get("name") or "").strip().lower()
    if nm in ("park", "cafe", "restaurant") or len(nm) <= 2:
        s -= 0.2

    return round(s, 3)


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)  # ✅ 1 day
def fetch_pois_overpass(lat: float, lon: float, radius_km: float, limit: int):
    south, west, north, east = _radius_to_bbox(lat, lon, radius_km)
    query = _overpass_query_bbox(south, west, north, east)

    for url in OVERPASS_URLS:
        try:
            j = _request_json(
                "POST",
                url,
                data=query.encode("utf-8"),
                timeout=35,
                retries=1,
                backoff=0.8,
                name=f"Overpass({url})",
            )
            elements = (j or {}).get("elements", []) or []

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

                pid = el.get("id")
                if pid is None:
                    continue

                pois.append(
                    {
                        "name": name,
                        "lat": float(plat),
                        "lon": float(plon),
                        "type": _poi_type(tags),
                        "tags": tags,
                        "osm_id": int(pid),
                        "quality": round(_poi_quality_score(tags), 3),
                    }
                )

            # ✅ dedupe by (name, lat, lon)
            seen = set()
            deduped = []
            for p in pois:
                key = (p["name"], round(p["lat"], 5), round(p["lon"], 5))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(p)

            # ✅ Rank: type bias + quality + closeness to center
            def rank(p):
                type_boost = {"관광": 0.15, "문화": 0.15, "자연": 0.12, "맛집": 0.08, "카페": 0.05, "유흥": 0.03}.get(
                    p["type"], 0.0
                )
                dist = haversine_km(lat, lon, p["lat"], p["lon"])
                # closeness bonus (<= radius)
                closeness = max(0.0, 1.0 - dist / max(0.8, radius_km))
                return type_boost + p["quality"] + 0.25 * closeness

            deduped.sort(key=rank, reverse=True)
            return deduped[: max(0, int(limit))]
        except Exception:
            continue

    # ❗ Overpass 실패 fallback
    cached = sget("cache.last_pois")
    if cached:
        return cached[: max(0, int(limit))]

    return []


# =========================
# Itinerary engine
# =========================
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

    # ✅ incorporate “quality” (notability hints)
    quality = float(poi.get("quality") or 0.0)
    s = base + 0.45 * quality

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
    radius_km,  
    exclude_ids: Optional[Set[int]] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    exclude_ids = exclude_ids or set()
    if not pois:
        return {d: [] for d in range(1, days + 1)}

    filtered = [p for p in pois if int(p.get("osm_id") or -1) not in exclude_ids]
    scored = [(poi_score(p, styles), p) for p in filtered]
    scored.sort(key=lambda x: x[0], reverse=True)

    if radius_km <= 4:
        per_day = 6
    elif radius_km <= 8:
        per_day = 5
    else:
        per_day = 4
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
    radius_km: float = 8.0,    
) -> Dict[str, Any]:
    """
    ✅ Improved realism:
    - Short leg => less overhead
    - Dense area => slightly slower effective speed
    """
    stay_min = 0  # ✅ 추가: 모든 경로에서 stay_min이 정의되도록 기본값 세팅
    
    if not points or len(points) == 1:
    stay_min = 60 * len(points)  # POI 체류시간
    total_min = 0               # 이동시간 없음
    total_km = 0.0

    return {
        "mode": mode,
        "total_minutes": total_min,
        "total_km": total_km,
        "stay_minutes": stay_min,
        "day_total_minutes": stay_min,
        "overload": stay_min > 480,
        "legs": [],
        "note": "POI가 0~1개라 이동시간 없이 체류시간만 계산했어요.",
    }


        return {
            "mode": mode,
            "total_minutes": int(round(total_min)),
            "total_km": round(total_km, 2),
            "stay_minutes": stay_min,
            "day_total_minutes": day_total,
            "overload": day_total > 480,  # 8시간 초과
            "legs": legs,
            "note": "이동+체류 합산 추정치(8시간 초과 시 과부하)",
        }

    speed = move_speed_kmh(mode)
    overhead = leg_overhead_min(mode)

    # Density adjustment (more points in smaller radius => slower)
    density = len(points) / max(1.0, radius_km)
    speed *= max(0.72, 1.15 - 0.06 * density)

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))

    legs = []
    total_km = 0.0
    total_min = 0.0

    def leg_minutes(km: float) -> float:
        local_overhead = overhead
        if km < 0.8:
            local_overhead *= 0.6
        elif km > 8 and mode == "대중교통":
            local_overhead += 5
        return (km / max(3.0, speed)) * 60.0 + local_overhead

    for i in range(len(points) - 1):
        a = points[i]
        b = points[i + 1]
        km = haversine_km(a[0], a[1], b[0], b[1])
        minutes = leg_minutes(km)
        legs.append({"from": i, "to": i + 1, "km": round(km, 2), "minutes": int(round(minutes))})
        total_km += km
        total_min += minutes

    if return_to_center:
        last = points[-1]
        km = haversine_km(last[0], last[1], center[0], center[1])
        minutes = leg_minutes(km)
        legs.append({"from": len(points) - 1, "to": "center", "km": round(km, 2), "minutes": int(round(minutes))})
        total_km += km
        total_min += minutes

    return {
        "mode": mode,
        "total_minutes": int(round(total_min)),
        "total_km": round(total_km, 2),
        "legs": legs,
        "note": "추정치(직선거리 기반 보정)라 실제 교통/경로에 따라 달라질 수 있어요.",
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
        day_times[d] = estimate_route_time_minutes(pts, mode=mode, return_to_center=return_to_center, radius_km=radius_km)

    return day_times


# =========================
# Budget
# =========================
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


# =========================
# Checklist
# =========================
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


# =========================
# Plan builders
# =========================
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


# =========================
# OpenAI (schema validation added)
# =========================
def _validate_plan_schema(plan: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(plan, dict):
        return False, "plan is not dict"
    for k in ("headline", "summary", "day_blocks"):
        if k not in plan:
            return False, f"missing key: {k}"
    if not isinstance(plan.get("day_blocks"), list):
        return False, "day_blocks is not list"
    for b in plan["day_blocks"][:20]:
        if not isinstance(b, dict):
            return False, "day_blocks item not dict"
        if "day" not in b or "plan" not in b:
            return False, "day_blocks item missing fields"
        if not isinstance(b.get("plan"), list):
            return False, "plan field not list"
    # normalize sources
    if "sources" in plan and not isinstance(plan["sources"], list):
        plan["sources"] = []
    if "tips" in plan and not isinstance(plan["tips"], list):
        plan["tips"] = []
    plan.setdefault("tips", [])
    plan.setdefault("sources", [])
    return True, ""


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

    # merge sources from web_search_call if possible
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

    ok, msg = _validate_plan_schema(plan)
    if not ok:
        return None, f"OpenAI 플랜 스키마 검증 실패: {msg}"

    return plan, None


# =========================
# Itinerary edits
# =========================
def ensure_itinerary_edits(days: int, plan: Dict[str, Any]):
    edits = sget("runtime.itinerary_edits", {}) or {}
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
    sset("runtime.itinerary_edits", edits)


def apply_itinerary_edits(plan: Dict[str, Any]) -> Dict[str, Any]:
    edits = sget("runtime.itinerary_edits", {}) or {}
    new_plan = json.loads(json.dumps(plan))
    for b in new_plan.get("day_blocks", []):
        try:
            d = int(b.get("day"))
        except Exception:
            continue
        if d in edits:
            b["plan"] = [edits[d]["am"], edits[d]["pm"], edits[d]["night"]]
    return new_plan


# =========================
# Export: ICS / PDF
# =========================
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


# =========================
# Map
# =========================
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

            radius_units="meters",          # ✅ 추가
            get_radius=350,     # ✅ 수정

            radiusMinPixels=4,     # 🔑 최소 픽셀 크기
            radiusMaxPixels=15,    # 🔑 최대 픽셀 크기
            
            get_fill_color=[192, 122, 77, 220],  # ✅ 추가 (브랜드 색)
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

            radius_units="meters",
            get_radius=120,

            radiusMinPixels=2,     # 🔑 최소 픽셀 크기
            radiusMaxPixels=12,    # 🔑 최대 픽셀 크기

            get_fill_color=[80, 140, 200, 180],
            pickable=True,
        )

    )


    view = pdk.ViewState(latitude=dest_geo["lat"], longitude=dest_geo["lon"], zoom=11)
    deck = pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name} ({kind})"}, map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json", )
    st.pydeck_chart(deck, use_container_width=True)


# =========================
# UI
# =========================
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
    sset(
        "ui.openai_api_key",
        st.sidebar.text_input(
            "OPENAI_API_KEY",
            type="password",
            placeholder="sk-... (optional)",
            value=sget("ui.openai_api_key", ""),
        ),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏨 Amadeus API (숙소 실제 데이터)")

    sset(
        "ui.amadeus_client_id",
        st.sidebar.text_input(
            "AMADEUS CLIENT ID",
            type="password",
            placeholder="Amadeus Client ID",
            value=sget("ui.amadeus_client_id", ""),
        ),
    )

    sset(
        "ui.amadeus_client_secret",
        st.sidebar.text_input(
            "AMADEUS CLIENT SECRET",
            type="password",
            placeholder="Amadeus Client Secret",
            value=sget("ui.amadeus_client_secret", ""),
        ),
    )

    sset(
        "ui.use_amadeus_hotel",
        st.sidebar.toggle(
            "실제 숙소 데이터 사용 (Amadeus)",
            value=bool(sget("ui.use_amadeus_hotel", False)),
        ),
    )

    st.sidebar.caption("※ 키는 세션 메모리에만 저장되며 서버에 기록되지 않습니다.")


    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧳 출발지(거리 계산용)")
    sset("input.start_city", st.sidebar.text_input("출발 도시", value=sget("input.start_city", "서울")))

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗓️ 시작 날짜(예보/ICS용)")
    sset("input.start_date", st.sidebar.date_input("여행 시작일", value=sget("input.start_date", date.today())))

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 POI 자동 수집 옵션")
    sset("ui.poi_radius_km", st.sidebar.slider("반경(km)", 1, 20, int(sget("ui.poi_radius_km", 5))))
    sset("ui.poi_limit", st.sidebar.slider("POI 최대 개수", 10, 120, int(sget("ui.poi_limit", 50)), step=10))
    sset(
        "ui.poi_types",
        st.sidebar.multiselect(
            "POI 타입 필터(표시/계획에 반영)",
            ["관광", "문화", "자연", "맛집", "카페", "유흥"],
            default=sget("ui.poi_types", ["관광", "맛집", "카페", "자연", "문화"]),
        ),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🚶 Day 이동시간 추정 설정")
    sset(
        "ui.move_mode",
        st.sidebar.selectbox(
            "이동수단",
            ["자동", "도보", "대중교통", "차량"],
            index=["자동", "도보", "대중교통", "차량"].index(sget("ui.move_mode", "자동")),
        ),
    )
    sset(
        "ui.include_return_to_center",
        st.sidebar.toggle("하루 마지막에 중심(대략 숙소) 복귀 포함", value=bool(sget("ui.include_return_to_center", True))),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧳 (선택) 여행 형태(예산 분배용)")
    sset(
        "input.travel_mode",
        st.sidebar.selectbox(
            "여행 형태",
            ["자유여행", "패키지여행"],
            index=["자유여행", "패키지여행"].index(sget("input.travel_mode", "자유여행")),
        ),
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ 확장 UI 토글")
    sset("ui.show_map", st.sidebar.toggle("지도 표시", value=bool(sget("ui.show_map", True))))
    sset("ui.enable_edit", st.sidebar.toggle("일정 편집 모드", value=bool(sget("ui.enable_edit", True))))
    sset("ui.show_budget", st.sidebar.toggle("예산 분배 표시", value=bool(sget("ui.show_budget", True))))
    sset("ui.show_checklist", st.sidebar.toggle("체크리스트 표시", value=bool(sget("ui.show_checklist", True))))
    sset("ui.debug_panel", st.sidebar.toggle("디버그 패널", value=bool(sget("ui.debug_panel", False))))
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏨 숙소 추천 옵션")

    sset(
        "hotel.stars",
        st.sidebar.multiselect(
            "호텔 성급",
            [1, 2, 3, 4, 5],
            default=sget("hotel.stars", [3, 4]),
            format_func=lambda x: f"{x}성",
        ),
    )

    sset(
        "hotel.max_price_per_night",
        st.sidebar.number_input(
            "1박 최대 금액(원)",
            0, 3000000,
            value=sget("hotel.max_price_per_night", 0),
            step=50000,
        ),
    )

    sset(
        "hotel.reorder_by_hotel",
        st.sidebar.toggle(
            "숙소 기준으로 일정 재정렬",
            value=bool(sget("hotel.reorder_by_hotel", True)),
        ),
    )

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
        sset(
            "input.travel_month",
            st.selectbox("여행 시기(월 단위)", months, index=months.index(sget("input.travel_month", "상관없음"))),
        )
        sset("input.party_count", st.number_input("여행 인원", 1, 30, int(sget("input.party_count", 2)), 1))

    with c2:
        sset(
            "input.party_type",
            st.selectbox(
                "관계",
                ["친구", "연인", "부모님", "가족", "혼자", "직장동료", "기타"],
                index=["친구", "연인", "부모님", "가족", "혼자", "직장동료", "기타"].index(sget("input.party_type", "친구")),
            ),
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
        sset(
            "input.destination_scope",
            st.selectbox("국내/해외", ["국내", "해외"], index=["국내", "해외"].index(sget("input.destination_scope", "국내"))),
        )
    with c4:
        sset(
            "input.destination_text",
            st.text_input(
                "여행 도시 입력 (국가명 ❌ / 도시명 ⭕)",
                value=sget("input.destination_text", ""),
                placeholder="예: 밴쿠버 / 토론토 / 도쿄 / 파리",
            ),
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
        sset(
            "input.duration",
            st.selectbox("여행 일정", ["당일치기", "3일", "5일", "10일 이상"], index=["당일치기", "3일", "5일", "10일 이상"].index(sget("input.duration", "3일"))),
        )
        sset(
            "input.budget",
            st.number_input("예상 예산(원)", 0, 20000000, int(sget("input.budget", 1000000)), step=50000),
        )

    with c2:
        sset(
            "input.travel_style",
            st.multiselect(
                "여행 스타일(복수 선택 가능)",
                ["힐링", "식도락", "유흥", "로드트립", "액티비티", "쇼핑", "문화/예술", "자연", "테마파크"],
                default=sget("input.travel_style", ["힐링"]),
            ),
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
        "travel_month": sget("input.travel_month"),
        "party_count": int(sget("input.party_count")),
        "party_type": sget("input.party_type"),
        "destination_scope": sget("input.destination_scope"),
        "destination_text": sget("input.destination_text"),
        "duration": sget("input.duration"),
        "travel_style": sget("input.travel_style"),
        "budget": int(sget("input.budget")),
        "start_city": sget("input.start_city"),
        "start_date": sget("input.start_date").isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date_obj": sget("input.start_date"),
        "travel_mode": sget("input.travel_mode"),
    }


def payload_signature(payload: Dict[str, Any]) -> str:
    copy = dict(payload)
    copy.pop("start_date_obj", None)
    return json.dumps(copy, ensure_ascii=False, sort_keys=True)


def generate_bundle() -> Tuple[Dict[str, Any], Optional[str]]:
    payload = build_payload()
    sig = payload_signature(payload)

    if sget("cache.last_payload_sig") == sig and sget("cache.last_bundle") is not None:
        return sget("cache.last_bundle"), None

    dest_text = (payload.get("destination_text") or "").strip()
    start_text = (payload.get("start_city") or "").strip()

    # 해외인데 도시 힌트가 없으면 city 힌트 추가
    if payload.get("destination_scope") == "해외" and dest_text:
        if "," not in dest_text:
            dest_text = f"{dest_text}, city"

    dest_geo = geocode_place(dest_text) if dest_text else None
    start_geo = geocode_place(start_text) if start_text else None

    if dest_geo:
        display = (dest_geo.get("display_name") or "").lower()
        if any(k in display for k in ["canada", "united states", "japan", "australia"]):
            st.info(
                "입력한 값이 ‘국가 단위’로 인식됐을 가능성이 있어요. "
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
    overpass_err = None
    if dest_geo:
        try:
            pois_all = fetch_pois_overpass(
                dest_geo["lat"],
                dest_geo["lon"],
                radius_km=float(sget("ui.poi_radius_km")),
                limit=int(sget("ui.poi_limit")),
            )
        except Exception as e:
            overpass_err = str(e)
            pois_all = []

    allowed_types = set(sget("ui.poi_types") or [])
    pois_filtered = [p for p in pois_all if (p.get("type") in allowed_types)] if allowed_types else pois_all
    if not pois_filtered:
        pois_filtered = pois_all

    exclude_ids = set(sget("runtime.poi_user_exclude_ids") or set())
    styles = payload.get("travel_style", [])
    poi_daymap = build_itinerary_from_pois(pois_filtered, styles, days=days, radius_km=float(sget("ui.poi_radius_km")), exclude_ids=exclude_ids)

    move_mode_setting = sget("ui.move_mode")
    day_travel_times = build_day_travel_times(
        poi_daymap,
        styles=styles,
        radius_km=float(sget("ui.poi_radius_km")),
        move_mode_setting=move_mode_setting,
        return_to_center=bool(sget("ui.include_return_to_center")),
    )
    # ===== Hotel Recommendation =====
    hotel_opts = sget("hotel")
    hotels = recommend_hotels(
        poi_daymap=poi_daymap,
        styles=styles,
        hotel_opts=hotel_opts,
    )

    selected_hotel = hotels[0] if hotels else None

    if selected_hotel and hotel_opts.get("reorder_by_hotel"):
        poi_daymap = {
            d: sorted(
                ps,
                key=lambda p: haversine_km(
                    selected_hotel["lat"],
                    selected_hotel["lon"],
                    p["lat"],
                    p["lon"],
                ),
            )
            for d, ps in poi_daymap.items()
        }

        day_travel_times = build_day_travel_times(
            poi_daymap,
            styles=styles,
            radius_km=float(sget("ui.poi_radius_km")),
            move_mode_setting=move_mode_setting,
            return_to_center=bool(sget("ui.include_return_to_center")),
        )
    mode_used = None
    if day_travel_times:
        mode_used = day_travel_times.get(1, {}).get("mode") or None

    err = None
    openai_key = (sget("ui.openai_api_key") or "").strip()
    plan = None

    enriched_payload = dict(payload)
    enriched_payload.pop("start_date_obj", None)
    enriched_payload["distance_km_estimate"] = km
    enriched_payload["distance_comment"] = distance_comment
    enriched_payload["weather_snapshot"] = snapshot
    enriched_payload["weather_forecast_daily"] = forecast.get("daily") if forecast else None
    enriched_payload["poi_sample"] = [{"name": p["name"], "type": p["type"], "quality": p.get("quality", 0)} for p in pois_filtered[:25]]
    enriched_payload["estimated_day_travel_times"] = {
        str(d): {"mode": info.get("mode"), "total_minutes": info.get("total_minutes"), "total_km": info.get("total_km")}
        for d, info in day_travel_times.items()
    }
    enriched_payload["note"] = "이동시간은 직선거리 기반 보정치임(실제 경로/교통상황과 다를 수 있음)."

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
        or (infer_move_mode(styles, float(sget("ui.poi_radius_km"))) if move_mode_setting == "자동" else move_mode_setting),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "hotel_recommendations": hotels,
        "selected_hotel": selected_hotel,
        "overpass_error": overpass_err,
    }

    bundle = {
        "payload": payload,
        "meta": meta,
        "pois": pois_filtered,
        "poi_daymap": poi_daymap,
        "plan": plan,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }

    sset("cache.last_payload_sig", sig)
    sset("cache.last_bundle", bundle)
    sset("runtime.itinerary_edits", {})

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
        msg = str(err).lower()
        if "quota" in msg or "rate" in msg:
            st.warning("🤖 AI 사용량 초과 → 오늘은 자동 플랜 모드로 진행했어요.")
        elif "api key" in msg:
            st.info("🔑 OpenAI 키가 없어서 자동 플랜으로 생성했어요.")
        else:
            st.warning(f"🤖 AI 응답이 불안정해서 자동 플랜으로 전환했어요.\n\n사유: {err}")

    if meta.get("overpass_error"):
        st.info(f"POI 수집이 불안정했을 수 있어요(Overpass). 필요하면 반경/개수를 줄이거나 다시 시도해줘.\n\n사유: {meta['overpass_error']}")

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

    tab_plan, tab_move, tab_poi, tab_hotel, tab_budget, tab_check, tab_export = st.tabs(
        ["🧾 플랜", "⏱️ 이동시간", "🗺️ 지도+POI", "🏨 숙소", "💸 예산", "✅ 체크리스트", "📤 내보내기"]
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

        if sget("ui.enable_edit", True):
            st.caption("편집 모드 ON ✅ (오전/오후/밤을 바꿔서 ‘내 플랜’로 커스터마이징)")
            for d in range(1, days + 1):
                with st.expander(f"Day {d} 편집하기", expanded=(d == 1)):
                    edits = sget("runtime.itinerary_edits", {})
                    ed = edits.get(d, {"am": "", "pm": "", "night": ""})
                    ed["am"] = st.text_input(f"Day {d} - 오전", value=ed["am"], key=f"edit_am_{d}")
                    ed["pm"] = st.text_input(f"Day {d} - 오후", value=ed["pm"], key=f"edit_pm_{d}")
                    ed["night"] = st.text_input(f"Day {d} - 밤", value=ed["night"], key=f"edit_night_{d}")
                    edits[d] = ed
                    sset("runtime.itinerary_edits", edits)
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
              <div class="tm-tip">직선거리 + (짧은 구간 오버헤드↓ / 혼잡 밀도 보정)으로 계산한 추정치야.</div>
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

        if sget("ui.show_map", True):
            st.markdown('<div class="tm-section-title">🗺️ 지도</div>', unsafe_allow_html=True)
            st.markdown('<div class="tm-card">', unsafe_allow_html=True)
            render_map(dest_geo, pois)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="tm-section-title">🧹 POI 정리(원치 않는 곳 제외)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-card">', unsafe_allow_html=True)

        if not pois:
            st.info("POI를 못 가져왔어… (목적지 좌표/Overpass 상태 확인). 그래도 플랜은 계속 가능!")
        else:
            cols = st.columns([3, 1, 1, 1, 1])
            cols[0].markdown("**이름**")
            cols[1].markdown("**타입**")
            cols[2].markdown("**퀄리티**")
            cols[3].markdown("**제외**")
            cols[4].markdown("**대략거리(중심)**")

            exclude_set = set(sget("runtime.poi_user_exclude_ids") or set())
            center_lat = dest_geo["lat"] if dest_geo else pois[0]["lat"]
            center_lon = dest_geo["lon"] if dest_geo else pois[0]["lon"]

            display_n = min(len(pois), 60)
            for i in range(display_n):
                p = pois[i]
                pid = int(p["osm_id"])
                row = st.columns([3, 1, 1, 1, 1])
                row[0].write(p["name"])
                row[1].write(p["type"])
                row[2].write(f"{float(p.get('quality') or 0):.2f}")

                checked = row[3].checkbox("", value=(pid in exclude_set), key=f"exclude_{pid}_{i}")
                if checked:
                    exclude_set.add(pid)
                else:
                    exclude_set.discard(pid)

                dist = haversine_km(center_lat, center_lon, p["lat"], p["lon"])
                row[4].write(f"{dist:.1f}km")

            sset("runtime.poi_user_exclude_ids", exclude_set)
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
            sset("cache.last_payload_sig", None)
            st.rerun()
            
    with tab_hotel:
        st.markdown('<div class="tm-section-title">🏨 추천 숙소</div>', unsafe_allow_html=True)
        hotels = meta.get("hotel_recommendations", [])

        if not hotels:
            st.info("추천된 숙소가 없어요.")
        else:
            for i, h in enumerate(hotels, 1):
                st.markdown(
                    f"""
                    **{i}. {h['name']} ({h['stars']}성)**  
                    - 1박 예상: {h['price']:,}원  
                    - 추천 점수: {h['score']}  
                    """
                )
                
    with tab_budget:
        if sget("ui.show_budget", True):
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
        if sget("ui.show_checklist", True):
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

    # Debug Panel
    if sget("ui.debug_panel", False):
        with st.expander("🧪 디버그 패널", expanded=False):
            st.write("meta:")
            st.json(meta)
            st.write("payload:")
            st.json({k: v for k, v in payload.items() if k != "start_date_obj"})

    nav = st.columns([1, 1, 2])
    with nav[0]:
        if st.button("👈 입력 수정", use_container_width=True):
            st.session_state.step = 1
    with nav[1]:
        if st.button("⬅️ 추가 정보 수정", use_container_width=True):
            st.session_state.step = 2
    with nav[2]:
        if st.button("완전 새로 뽑기(캐시 초기화) 🔄", use_container_width=True):
            sset("cache.last_payload_sig", None)
            sset("cache.last_bundle", None)
            st.rerun()


# =========================
# App
# =========================
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














