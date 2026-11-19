# Mockstar – Interactive Interview Simulation and Evaluation Platform

Flask + SQLite + Google Gemini + OpenCV (Haar cascades). Matches the project report.

## Run in VS Code
1. Open this folder in VS Code, then open a terminal (Ctrl+`).
2. Create and activate a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv venv` then `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and paste your free Gemini key (https://aistudio.google.com/apikey).
   Without a key the app still runs, using simple offline fallbacks.
5. `python app.py` and open http://127.0.0.1:5000 (sign up first).

Use Chrome or Edge for voice input and the webcam. Camera access works on localhost.

## Structure
- `app.py` routes, auth, SQLite, REST API
- `ai.py` Gemini prompts + fallbacks (questions, feedback, report, quiz, study material, chatbot)
- `vision.py` OpenCV face / eye / posture analysis
- `templates/`, `static/` frontend (Jinja2, CSS, vanilla JS)
- `mockstar.db` is created automatically on first run
