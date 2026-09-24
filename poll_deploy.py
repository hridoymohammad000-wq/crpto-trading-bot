import requests
import time

TOKEN = "rnd_H5S1jER2W162j4UEYE30N1YvB4xZ"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}
SVC_ID = "srv-daq6nk2d0e5s739eef10"

for _ in range(15):
    resp = requests.get(f"https://api.render.com/v1/services/{SVC_ID}/deploys", headers=HEADERS)
    if resp.status_code == 200:
        latest = resp.json()[0]['deploy']
        status = latest['status']
        print(f"Status: {status}")
        if status not in ['created', 'build_in_progress', 'update_in_progress']:
            break
    time.sleep(5)
