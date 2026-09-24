import requests

TOKEN = "rnd_H5S1jER2W162j4UEYE30N1YvB4xZ"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

BACKEND_ID = "srv-daq6nk2d0e5s739eef10"
FRONTEND_ID = "srv-daq6ng142hec738gr3rg"
BACKEND_URL = "https://crypto-bot-backend-adq6.onrender.com"

# 1. Update Frontend Env Vars
print("Updating frontend env vars...")
url_front = f"https://api.render.com/v1/services/{FRONTEND_ID}/env-vars"
payload_front = [
    {"key": "VITE_API_BASE_URL", "value": BACKEND_URL},
    {"key": "VITE_WS_BASE_URL", "value": BACKEND_URL.replace("https://", "wss://")}
]
res = requests.put(url_front, headers=HEADERS, json=payload_front)
print("Frontend update:", res.status_code)

# 2. Update Backend Build Command
print("Updating backend build command...")
url_back = f"https://api.render.com/v1/services/{BACKEND_ID}"
# To update a service, we patch it
payload_back = {
    "serviceDetails": {
        "envSpecificDetails": {
            "buildCommand": "cd app/backend && pip install --upgrade pip setuptools && pip install .",
            "startCommand": "cd app/backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
        }
    }
}
res = requests.patch(url_back, headers=HEADERS, json=payload_back)
print("Backend update:", res.status_code)

# Trigger new deploy for frontend
requests.post(f"https://api.render.com/v1/services/{FRONTEND_ID}/deploys", headers=HEADERS)

# Trigger new deploy for backend
requests.post(f"https://api.render.com/v1/services/{BACKEND_ID}/deploys", headers=HEADERS)
