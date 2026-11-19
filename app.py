import os, json, sqlite3, uuid, io
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
import ai, vision

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mockstar.db")
TYPES = {"technical": ("Technical Interview", 5), "behavioral": ("Behavioral Interview", 5), "quick": ("Quick Practice", 3)}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    with sqlite3.connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE,
            password TEXT, prefs TEXT DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS interviews(id TEXT PRIMARY KEY, user_id INTEGER, role TEXT, type TEXT,
            difficulty TEXT, company TEXT, jd TEXT, resume TEXT, total INTEGER, qa TEXT DEFAULT '[]',
            cv TEXT DEFAULT '{}', report TEXT, status TEXT DEFAULT 'active', score INTEGER,
            started REAL, duration INTEGER DEFAULT 0);
        """)


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "uid" not in session:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in again."), 401
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


@app.context_processor
def inject_user():
    return {"user_name": session.get("name")}


# ---------- auth ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        n, e, p = (request.form.get(k, "").strip() for k in ("name", "email", "password"))
        if not (n and e and len(p) >= 6):
            flash("Enter a name, email and a password of at least 6 characters.")
        else:
            try:
                db().execute("INSERT INTO users(name,email,password) VALUES(?,?,?)", (n, e.lower(), generate_password_hash(p)))
                db().commit()
                flash("Account created. Log in to continue.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.")
    return render_template("auth.html", mode="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?", (request.form.get("email", "").strip().lower(),)).fetchone()
        if u and check_password_hash(u["password"], request.form.get("password", "")):
            session.update(uid=u["id"], name=u["name"])
            return redirect(url_for("home"))
        flash("Email or password is incorrect.")
    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- pages ----------
@app.route("/")
@login_required
def home():
    return render_template("index.html", types=TYPES)


@app.route("/interview")
@login_required
def interview():
    prefs = json.loads(db().execute("SELECT prefs FROM users WHERE id=?", (session["uid"],)).fetchone()["prefs"])
    return render_template("interview.html", types=TYPES, sel=request.args.get("type", "technical"), prefs=prefs)


for _p in ("quiz", "learning", "chatbot"):
    app.add_url_rule(f"/{_p}", _p, login_required(lambda _p=_p: render_template(f"{_p}.html")))


@app.route("/history")
@login_required
def history():
    rows = db().execute("SELECT * FROM interviews WHERE user_id=? ORDER BY started DESC", (session["uid"],)).fetchall()
    return render_template("history.html", rows=rows)


@app.route("/report/<iid>")
@login_required
def report(iid):
    iv = db().execute("SELECT * FROM interviews WHERE id=? AND user_id=?", (iid, session["uid"])).fetchone()
    if not iv or not iv["report"]:
        return redirect(url_for("history"))
    return render_template("report.html", iv=iv, r=json.loads(iv["report"]), qa=json.loads(iv["qa"]),
                           cv=vision.summarize(json.loads(iv["cv"])))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        prefs = {"types": request.form.getlist("types"), "difficulty": request.form.get("difficulty", "Medium"),
                 "voice": bool(request.form.get("voice")), "companies": request.form.get("companies", ""),
                 "roles": request.form.get("roles", "")}
        db().execute("UPDATE users SET prefs=? WHERE id=?", (json.dumps(prefs), session["uid"]))
        db().commit()
        flash("Settings saved.")
    p = json.loads(db().execute("SELECT prefs FROM users WHERE id=?", (session["uid"],)).fetchone()["prefs"])
    return render_template("settings.html", p=p)


# ---------- interview API ----------
def get_iv(iid):
    return db().execute("SELECT * FROM interviews WHERE id=? AND user_id=?", (iid, session["uid"])).fetchone()


def read_resume(f):
    if not f or not f.filename:
        return ""
    data = f.read()
    try:
        if f.filename.lower().endswith(".pdf"):
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)[:6000]
        return data.decode("utf-8", "ignore")[:6000]
    except Exception:
        return ""


@app.post("/api/interview/start")
@login_required
def start():
    f = request.form
    itype = f.get("type", "technical")
    role = f.get("jd", "").strip()
    if not role:
        return jsonify(error="Enter the job role or paste a job description."), 400
    iid = uuid.uuid4().hex[:5].upper()
    total = TYPES.get(itype, TYPES["technical"])[1]
    db().execute("INSERT INTO interviews(id,user_id,role,type,difficulty,company,jd,resume,total,started) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (iid, session["uid"], role[:80], itype, f.get("difficulty", "Medium"), f.get("company", ""), role,
                  read_resume(request.files.get("resume")), total, __import__("time").time()))
    db().commit()
    iv = get_iv(iid)
    q = ai.first_question(iv)
    db().execute("UPDATE interviews SET qa=?, cv=? WHERE id=?",
                 (json.dumps([{"q": q, "a": "", "feedback": ""}]), json.dumps({"n": 0, "face": 0, "eyes": 0, "good": 0}), iid))
    db().commit()
    return jsonify(id=iid, question=q, total=total)


@app.post("/api/interview/<iid>/answer")
@login_required
def answer(iid):
    iv = get_iv(iid)
    if not iv:
        return jsonify(error="Interview not found."), 404
    qa = json.loads(iv["qa"])
    qa[-1]["a"] = (request.json.get("answer") or "").strip() or "(no answer)"
    last = len(qa) >= iv["total"]
    res = ai.evaluate_and_next(iv, qa, last)
    qa[-1]["feedback"] = res["feedback"]
    nxt = None
    if not last:
        nxt = res["next_question"]
        qa.append({"q": nxt, "a": "", "feedback": ""})
    db().execute("UPDATE interviews SET qa=? WHERE id=?", (json.dumps(qa), iid))
    db().commit()
    return jsonify(feedback=res["feedback"], next_question=nxt, done=last)


@app.post("/api/interview/<iid>/frame")
@login_required
def frame(iid):
    iv = get_iv(iid)
    if not iv:
        return jsonify(error="not found"), 404
    a = vision.analyze(request.json.get("image", ""))
    s = json.loads(iv["cv"])
    s["n"] += 1; s["face"] += a["face"]; s["eyes"] += a["eyes"]; s["good"] += a["posture"] == "Good"
    db().execute("UPDATE interviews SET cv=? WHERE id=?", (json.dumps(s), iid))
    db().commit()
    return jsonify(a)


@app.post("/api/interview/<iid>/finish")
@login_required
def finish(iid):
    iv = get_iv(iid)
    if not iv:
        return jsonify(error="not found"), 404
    qa = [x for x in json.loads(iv["qa"]) if x["a"]]
    rep = ai.make_report(iv, qa, vision.summarize(json.loads(iv["cv"])))
    dur = int(__import__("time").time() - iv["started"])
    db().execute("UPDATE interviews SET report=?, score=?, status='done', duration=? WHERE id=?",
                 (json.dumps(rep), int(rep.get("score", 0)), dur, iid))
    db().commit()
    return jsonify(url=url_for("report", iid=iid))


# ---------- quiz / learning / chatbot ----------
@app.get("/api/quiz")
@login_required
def quiz_api():
    return jsonify(ai.quiz_question(request.args.get("role", "Software Engineer"), request.args.get("difficulty", "Medium")))


@app.post("/api/learn")
@login_required
def learn_api():
    d = request.json
    return jsonify(text=ai.study_material(d.get("role", "software developer"), d.get("topic", "Data Structures")))


@app.post("/api/chat")
@login_required
def chat_api():
    d = request.json
    return jsonify(reply=ai.chat(d.get("message", ""), d.get("history", [])))


init_db()
if __name__ == "__main__":
    app.run(debug=True)
