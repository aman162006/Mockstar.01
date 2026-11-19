import os, requests
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("GEMINI_API_KEY", "").strip()
r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                 params={"key": key, "pageSize": 100}, timeout=30)
print(r.status_code)
if r.status_code == 200:
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print(m["name"].replace("models/", ""))
else:
    print(r.text[:400])