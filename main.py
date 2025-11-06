from flask import Flask, request
import requests

app = Flask(__name__)

UNIVERSE_ID = 5307187607  # your universe

@app.get("/")
def home():
    return {"status": "API online"}, 200

@app.get("/passes")
def get_passes():
    url = f"https://develop.roproxy.com/v1/universes/{UNIVERSE_ID}/game-passes?limit=100"

    try:
        r = requests.get(url, timeout=5)
        data = r.json()

        result = []
        for p in data.get("data", []):
            result.append({
                "name": p.get("name"),
                "id": p.get("id"),
                "price": p.get("price")
            })

        return {"data": result}, 200

    except Exception as e:
        return {"error": str(e)}, 500
