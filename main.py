from flask import Flask, request
import requests

app = Flask(__name__)

# ===== Helper: Fetch all universes owned by a user =====
def fetch_user_universes(userId):
    url = f"https://games.roproxy.com/v2/users/{userId}/games?limit=100&sortOrder=Asc"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        return data.get("data", [])
    except:
        return []

# ===== Helper: Fetch gamepasses for a universe =====
def fetch_universe_passes(universeId):
    url = f"https://develop.roproxy.com/v1/universes/{universeId}/game-passes?limit=100"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        return data.get("data", [])
    except:
        return []

# ===== Root route (keep Render alive) =====
@app.get("/")
def home():
    return {"status": "ok"}, 200

# ===== MAIN API: /passes?userId= #### =====
@app.get("/passes")
def get_passes():
    userId = request.args.get("userId")

    if not userId:
        return {"error": "Missing userId"}, 400

    # Step 1 → get user universes
    universes = fetch_user_universes(userId)

    all_passes = []

    # Step 2 → for each universe, fetch its gamepasses
    for game in universes:
        universeId = game.get("universeId")
        if universeId:
            passes = fetch_universe_passes(universeId)
            for p in passes:
                all_passes.append({
                    "name": p.get("name"),
                    "id": p.get("id"),
                    "price": p.get("price"),
                    "universeId": universeId
                })

    return {"data": all_passes}, 200
