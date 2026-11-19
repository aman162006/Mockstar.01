"""AI layer: Google Gemini (REST) with offline fallbacks so the app still runs without a key."""
import os, re, json, random
import requests


LAST_ERROR = ""
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]


def gen(prompt, system=None):
    global LAST_ERROR
    key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
    if not key:
        LAST_ERROR = "GEMINI_API_KEY is not set."
        print(LAST_ERROR)
        return None
    first = os.getenv("GEMINI_MODEL", "").strip()
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    for model in ([first] if first else []) + [m for m in MODELS if m != first]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            r = requests.post(url, params={"key": key}, json=body, timeout=45)
        except Exception as e:
            LAST_ERROR = f"{type(e).__name__}: {e}"
            print("AI error:", LAST_ERROR)
            return None
        if r.status_code == 200:
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                LAST_ERROR = "Empty reply from model."
                return None
        LAST_ERROR = f"{model} -> Google replied {r.status_code}: {r.text[:200]}"
        print("AI error:", LAST_ERROR)
        if r.status_code not in (404, 400):
            break
    return None


def gen_json(prompt):
    t = gen(prompt + "\n\nRespond ONLY with valid JSON, no markdown fences.")
    if not t:
        return None
    m = re.search(r"\{.*\}", t, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


FALLBACK_Q = {
    "technical": ["Walk me through a technical project you are proud of.",
                  "How do you debug a problem you have never seen before?",
                  "Explain the difference between a process and a thread.",
                  "How would you design a URL shortener?",
                  "What trade-offs do you consider when choosing a database?"],
    "behavioral": ["Tell me about a time you worked in a team under pressure.",
                   "Describe a conflict with a colleague and how you resolved it.",
                   "Tell me about a failure and what you learned.",
                   "How do you prioritise when everything is urgent?",
                   "Why do you want this role?"],
}


def _ctx(iv):
    return (f"Role: {iv['role']}\nInterview type: {iv['type']}\nDifficulty: {iv['difficulty']}\n"
            f"Company: {iv['company'] or 'n/a'}\nJob description: {(iv['jd'] or '')[:1500]}\n"
            f"Resume: {(iv['resume'] or '')[:2500]}")


def _transcript(qa):
    return "\n".join(f"Q{i+1}: {x['q']}\nA{i+1}: {x['a'] or '(not answered yet)'}" for i, x in enumerate(qa))


def first_question(iv):
    t = gen(f"You are a professional interviewer.\n{_ctx(iv)}\n\nAsk the FIRST interview question only. "
            "One or two sentences, no preamble.")
    if t:
        return t.strip()
    bank = FALLBACK_Q.get(iv["type"], FALLBACK_Q["behavioral"])
    return f"Let's begin. {bank[0]}"


def evaluate_and_next(iv, qa, last):
    ask = ('{"feedback": "2-3 sentence constructive feedback on the LAST answer"}' if last else
           '{"feedback": "2-3 sentence constructive feedback on the LAST answer", '
           '"next_question": "a natural follow-up (or new topic) question"}')
    r = gen_json(f"You are a professional interviewer.\n{_ctx(iv)}\n\nTranscript:\n{_transcript(qa)}\n\nReturn JSON like {ask}")
    if r and r.get("feedback"):
        if not last and not r.get("next_question"):
            r["next_question"] = "Can you tell me more about your most relevant experience?"
        return r
    n = len(qa[-1]["a"].split())
    fb = ("Your answer was very short. Add a concrete example and the result you achieved." if n < 25 else
          "Good detail. Try structuring it as situation, action, result and quantify the impact.")
    bank = FALLBACK_Q.get(iv["type"], FALLBACK_Q["behavioral"])
    return {"feedback": fb, "next_question": bank[len(qa) % len(bank)]}


def make_report(iv, qa, cv):
    r = gen_json(f"You are an interview coach.\n{_ctx(iv)}\n\nTranscript:\n{_transcript(qa)}\n\nBehavioural camera stats: {cv}\n\n"
                 'Return JSON: {"score": integer 0-10, "summary": "paragraph", "strengths": ["..."], '
                 '"weaknesses": ["..."], "suggestions": ["..."], "suitability": integer 0-100}')
    if r and "score" in r:
        return r
    words = sum(len(x["a"].split()) for x in qa) / max(len(qa), 1)
    score = max(2, min(8, round(words / 12)))
    return {"score": score, "summary": "Offline evaluation (no AI key configured): based on answer length only.",
            "strengths": ["Completed the interview session."],
            "weaknesses": ["Answers could include more specific examples."],
            "suggestions": ["Use the STAR method.", "Add GEMINI_API_KEY to .env for full AI feedback."],
            "suitability": score * 10}


def quiz_question(role, difficulty):
    r = gen_json(f"Create ONE {difficulty} multiple-choice interview question for a {role}. Random topic seed {random.randint(1,99999)}. "
                 'JSON: {"question":"...","options":["A text","B text","C text","D text"],"answer":0-3 index,"explanation":"..."}')
    if r and len(r.get("options", [])) == 4:
        return r
    return {"question": "Which data structure uses LIFO order?", "options": ["Queue", "Stack", "Tree", "Graph"],
            "answer": 1, "explanation": "A stack removes the most recently added element first."}


def study_material(role, topic):
    t = gen(f"Write concise study material on '{topic}' for a {role} preparing for interviews. Sections: Overview, Key Concepts, "
            "Common Interview Questions, Tips. Use **bold** for headings and '* ' bullets.")
    return t or f"**{topic}**\n\nAdd GEMINI_API_KEY to .env to generate study material."


def chat(message, history):
    h = "\n".join(f"{m['role']}: {m['text']}" for m in history[-8:])
    t = gen(f"{h}\nuser: {message}", system="You are Mockstar's AI Career Coach. Give practical, concise interview and career advice.")
    return t or f"AI is unavailable. Reason: {LAST_ERROR}"
