# main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests, time

app = FastAPI(title="Roblox Pass Proxy", version="1.0")

# Allow Roblox HttpService and your browser to call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# --- Simple in-memory cache (per key) ---
CACHE = {}
TTL_SECONDS = 120  # 2 minutes cache

def cache_get(key):
    v = CACHE.get(key)
    if not v: return None
    if time.time() - v["t"] > TTL_SECONDS:
        CACHE.pop(key, None)
        return None
    return v["d"]

def cache_set(key, data):
    CACHE[key] = {"t": time.time(), "d": data}

# --- HTTP helper ---
HEADERS = {"User-Agent": "roblox-proxy/1.0"}
def get_json(url, timeout=8):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()

# --- Endpoints we’ll use (roproxy mirrors) ---
USERS_API = "https://users.roproxy.com/v1/users/{userId}"
INVENTORY_PASSES = "https://www.roproxy.com/users/inventory/list-json?assetTypeId=34&cursor=&itemsPerPage=100&pageNumber={page}&userId={userId}"
CATALOG_SHIRTS = "https://catalog.roproxy.com/v1/search/items/details?Category=3&CreatorName={username}"
UNIVERSE_PASSES = "https://develop.roproxy.com/v1/universes/{universeId}/game-passes?limit=100"

# --- fetchers ---
def fetch_username(user_id: int) -> str:
    data = get_json(USERS_API.format(userId=user_id))
    return data.get("name") or data.get("displayName") or ""

def fetch_gamepasses_for_user(user_id: int) -> list:
    all_items, page = [], 1
    # paginate until empty
    while True:
        url = INVENTORY_PASSES.format(page=page, userId=user_id)
        data = get_json(url)
        items = (data.get("Data") or {}).get("Items") or []
        if not items: break
        for gp in items:
            try:
                if gp.get("Creator", {}).get("Id") == user_id:
                    all_items.append({
                        "id": gp["Item"]["AssetId"],
                        "price": gp["Product"]["PriceInRobux"],
                        "name": gp["Item"]["Name"],
                        "type": "Gamepass"
                    })
            except Exception:
                continue
        page += 1
        if page > 10: break  # hard stop guard
    return all_items

def fetch_shirts_for_username(username: str) -> list:
    if not username: return []
    data = get_json(CATALOG_SHIRTS.format(username=username))
    rows = data.get("data") or []
    out = []
    for r in rows:
        price = r.get("price")
        rid = r.get("id")
        name = r.get("name") or "UGC"
        if price is not None and rid is not None:
            out.append({"id": rid, "price": price, "name": name, "type": "UGC"})
    return out

def fetch_passes_for_universe(universe_id: int) -> list:
    data = get_json(UNIVERSE_PASSES.format(universeId=universe_id))
    rows = data.get("data") or []
    return [{"id": r.get("id"), "price": r.get("price"), "name": r.get("name"), "type": "Gamepass"} for r in rows if r.get("id")]

# --- routes ---
@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

@app.get("/passes")
def passes(
    userId: int | None = Query(default=None),
    universeId: int | None = Query(default=None),
    include: str = Query(default="gamepass,ugc"),  # comma list
    limit: int = Query(default=50)
):
    """
    Two modes:
      1) /passes?userId=123         -> gamepasses (and shirts if include=ugc)
      2) /passes?universeId=999999  -> passes in that universe
    """
    key = f"{userId}-{universeId}-{include}-{limit}"
    cached = cache_get(key)
    if cached: return cached

    items = []

    try:
        if universeId:
            items = fetch_passes_for_universe(universeId)
        elif userId:
            inc = {x.strip().lower() for x in include.split(",")}
            if "gamepass" in inc:
                items += fetch_gamepasses_for_user(userId)
            if "ugc" in inc:
                username = fetch_username(userId)
                items += fetch_shirts_for_username(username)
        else:
            raise HTTPException(400, "Provide userId or universeId")
    except requests.HTTPError as e:
        raise HTTPException(502, f"Upstream error: {e}")
    except Exception as e:
        raise HTTPException(500, f"Server error: {e}")

    # sort low → high and trim
    items = sorted(items, key=lambda x: (x.get("price") or 0, x.get("id") or 0))[:max(1, min(limit, 200))]
    payload = {"count": len(items), "data": items}
    cache_set(key, payload)
    return payload
