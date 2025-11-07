# main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, time

app = FastAPI(title="Roblox Universe Finder", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

HEADERS = {"User-Agent": "roblox-universe-proxy/1.0"}
CACHE = {}
TTL = 120  # seconds

def cache_get(key):
    v = CACHE.get(key)
    if not v: return None
    if time.time() - v["t"] > TTL:
        CACHE.pop(key, None)
        return None
    return v["d"]

def cache_set(key, data):
    CACHE[key] = {"t": time.time(), "d": data}

def get_json(url, timeout=8):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()

# Candidate endpoints to find games owned by a user.
# Order: primary first, then fallbacks/mirrors.
GAME_LIST_ENDPOINTS = [
    "https://games.roproxy.com/v2/users/{userId}/games?limit=100&sortOrder=Asc",
    # older mirror (may or may not return results)
    "https://games.roproxy.com/v1/users/{userId}/games?limit=100",
    # dev endpoint (sometimes different shape)
    "https://games.roproxy.com/v2/users/{userId}/games?limit=100",
    # keep as placeholder for any other public mirror you trust
]

# Some content may live under "experiences" pages via creator API
CREATIONS_ENDPOINTS = [
    # this is a commonly used one for user profile metadata (not always listing games)
    "https://users.roproxy.com/v1/users/{userId}",
]

@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

@app.get("/universes")
def get_universes(userId: int = Query(..., description="Numeric Roblox userId")):
    """
    Return list of universes (universeId + optional placeId/title) for a given userId.
    Tries several endpoints; some will return empty due to Roblox server-side restrictions.
    """
    key = f"universes:{userId}"
    cached = cache_get(key)
    if cached:
        return {"count": len(cached), "data": cached, "cached": True}

    found = {}
    any_ok = False
    errors = []

    for ep in GAME_LIST_ENDPOINTS:
        url = ep.format(userId=userId)
        try:
            data = get_json(url)
        except requests.HTTPError as e:
            errors.append({"url": url, "error": f"HTTP {e.response.status_code}"})
            continue
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
            continue

        # different endpoints have different shapes — try to normalize
        # common shape for games.roproxy v2: {"data":[{ "universeId":..., "rootPlaceId":..., "name":...}, ...]}
        items = data.get("data") or data.get("games") or data.get("Games") or []
        if not items:
            # nothing returned from this endpoint for that user
            continue

        any_ok = True
        for g in items:
            # try a few keys
            uid = g.get("universeId") or g.get("id") or g.get("rootPlaceId") or g.get("universe_id")
            place = g.get("rootPlaceId") or g.get("placeId") or g.get("place_id")
            name = g.get("name") or g.get("title") or g.get("universeName")
            if uid:
                uid = int(uid)
                if uid not in found:
                    found[uid] = {"universeId": uid, "placeId": place, "name": name, "source": url}

    # As a last-resort attempt, try to fetch user's public info (sometimes includes creator shortcuts)
    if not any_ok:
        for ep in CREATIONS_ENDPOINTS:
            url = ep.format(userId=userId)
            try:
                data = get_json(url)
            except Exception:
                continue
            # not usually helpful for universes, but we keep it for additional data
            username = data.get("name") or data.get("displayName")
            if username:
                # store the username so the client can try other flows (like UGC search)
                found[f"username:{username}"] = {"note": "username discovered", "username": username, "source": url}

    result = list(found.values())
    cache_set(key, result)
    return {"count": len(result), "data": result, "cached": False, "errors_sample": errors[:3]}
