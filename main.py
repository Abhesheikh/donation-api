from flask import Flask, request
import requests

app = Flask(__name__)

@app.get("/passes")
def get_passes():
    userId = request.args.get("userId")
    if not userId:
        return {"error": "Missing userId"}, 400

    url = (
        "https://catalog.roproxy.com/v1/search/items"
        f"?creatorTargetId={userId}&creatorType=User"
        "&sortOrder=Asc&limit=50&filter=1"
    )

    try:
        r = requests.get(url, timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}, 500
