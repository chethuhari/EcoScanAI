"""
Smart Waste Segregation AI - Flask Backend
"""
import os
import uuid
import random
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
    send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-waste-dev-secret-key-2024")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
WASTE_TYPES = ["Plastic", "Paper", "Metal", "Glass", "Organic"]
ADMIN_EMAIL = "admin@waste.ai"

# -----------------------------------------------------------------------------
# SQLite Database (simple in-memory style, using sqlite3)
# -----------------------------------------------------------------------------
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "waste_app.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS detections (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            image_path TEXT NOT NULL,
            waste_type TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_detections_date ON detections(date);
        CREATE INDEX IF NOT EXISTS idx_detections_waste_type ON detections(waste_type);
    """)
    conn.commit()

    # Ensure default admin exists (even if users already exist).
    admin = conn.execute(
        "SELECT id, is_admin FROM users WHERE email = ?",
        (ADMIN_EMAIL,),
    ).fetchone()
    if not admin:
        admin_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, name, email, password, is_admin, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (admin_id, "Admin", ADMIN_EMAIL, generate_password_hash("admin123"), datetime.utcnow().isoformat()),
        )
        conn.commit()
    else:
        # Promote to admin + reset password for this demo admin account.
        conn.execute(
            "UPDATE users SET is_admin = 1, password = ? WHERE email = ?",
            (generate_password_hash("admin123"), ADMIN_EMAIL),
        )
        conn.commit()
    conn.close()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.headers.get("Accept", "").startswith("application/json"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        # Session-based admin auth (set at login).
        if not session.get("is_admin") or session.get("user_email") != ADMIN_EMAIL:
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


# -----------------------------------------------------------------------------
# Simulated AI prediction
# -----------------------------------------------------------------------------
def predict_waste_type():
    """Simulate AI prediction - returns random waste type and confidence."""
    waste = random.choice(WASTE_TYPES)
    confidence = round(random.uniform(0.75, 0.99), 2)
    return waste, confidence


# -----------------------------------------------------------------------------
# Auth API
# -----------------------------------------------------------------------------
@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400
    if password != confirm:
        return jsonify({"error": "Passwords do not match"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    try:
        uid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, name, email, password, is_admin, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (uid, name, email, generate_password_hash(password), datetime.utcnow().isoformat()),
        )
        conn.commit()
        return jsonify({"success": True, "message": "Account created. Please login."})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 400
    finally:
        conn.close()


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    conn = get_db()
    row = conn.execute("SELECT id, name, password, is_admin FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if not row or not check_password_hash(row["password"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = row["id"]
    session["user_name"] = row["name"]
    session["user_email"] = email
    # Required: decide admin purely by email.
    session["is_admin"] = (email == ADMIN_EMAIL)
    return jsonify({"success": True, "is_admin": bool(session["is_admin"])})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


# -----------------------------------------------------------------------------
# Predict API
# -----------------------------------------------------------------------------
@app.route("/api/predict", methods=["POST"])
@login_required
def api_predict():
    if "image" not in request.files and "file" not in request.files:
        return jsonify({"error": "No image provided"}), 400
    file = request.files.get("image") or request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No image selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Use PNG, JPG, JPEG, GIF, WEBP"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    rel_path = f"/static/uploads/{filename}"

    waste_type, confidence = predict_waste_type()
    det_id = str(uuid.uuid4())
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    conn.execute(
        "INSERT INTO detections (id, user_id, image_path, waste_type, confidence_score, date) VALUES (?, ?, ?, ?, ?, ?)",
        (det_id, session["user_id"], rel_path, waste_type, confidence, date_str),
    )
    conn.commit()
    conn.close()

    return jsonify({
        "waste_type": waste_type,
        "confidence": confidence,
        "detection_id": det_id,
        "image_path": rel_path,
        "date": date_str,
    })


# -----------------------------------------------------------------------------
# Detections API
# -----------------------------------------------------------------------------
@app.route("/api/detections", methods=["GET"])
@login_required
def api_detections():
    waste_type = request.args.get("waste_type", "").strip()
    is_admin = session.get("is_admin", False)
    user_id = session["user_id"]

    conn = get_db()
    if is_admin:
        if waste_type and waste_type in WASTE_TYPES:
            rows = conn.execute(
                "SELECT id, user_id, image_path, waste_type, confidence_score, date FROM detections WHERE waste_type = ? ORDER BY date DESC",
                (waste_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, image_path, waste_type, confidence_score, date FROM detections ORDER BY date DESC"
            ).fetchall()
    else:
        if waste_type and waste_type in WASTE_TYPES:
            rows = conn.execute(
                "SELECT id, user_id, image_path, waste_type, confidence_score, date FROM detections WHERE user_id = ? AND waste_type = ? ORDER BY date DESC",
                (user_id, waste_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, image_path, waste_type, confidence_score, date FROM detections WHERE user_id = ? ORDER BY date DESC",
                (user_id,),
            ).fetchall()
    conn.close()

    detections = [
        {
            "id": r["id"],
            "image_path": r["image_path"],
            "waste_type": r["waste_type"],
            "confidence_score": r["confidence_score"],
            "date": r["date"],
        }
        for r in rows
    ]
    return jsonify({"detections": detections})


@app.route("/api/detections/<det_id>", methods=["DELETE"])
@login_required
def api_delete_detection(det_id):
    conn = get_db()
    row = conn.execute("SELECT user_id FROM detections WHERE id = ?", (det_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Detection not found"}), 404
    if not session.get("is_admin") and row["user_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "Forbidden"}), 403
    conn.execute("DELETE FROM detections WHERE id = ?", (det_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# -----------------------------------------------------------------------------
# Analytics API
# -----------------------------------------------------------------------------
@app.route("/api/analytics", methods=["GET"])
@login_required
def api_analytics():
    is_admin = session.get("is_admin", False)
    user_id = session["user_id"]

    conn = get_db()
    if is_admin:
        rows = conn.execute(
            "SELECT waste_type, confidence_score, date FROM detections ORDER BY date ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT waste_type, confidence_score, date FROM detections WHERE user_id = ? ORDER BY date ASC",
            (user_id,),
        ).fetchall()

    # Counts by type
    counts = {t: 0 for t in WASTE_TYPES}
    confidences = []
    daily_trend = {}  # date -> count

    for r in rows:
        counts[r["waste_type"]] = counts.get(r["waste_type"], 0) + 1
        confidences.append(r["confidence_score"])
        d = r["date"][:10] if r["date"] else ""
        if d:
            daily_trend[d] = daily_trend.get(d, 0) + 1

    total = len(rows)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    # Last 60 days trend (fill missing with 0)
    end = datetime.utcnow()
    trend_60 = []
    for i in range(59, -1, -1):
        d = (end - timedelta(days=i)).strftime("%Y-%m-%d")
        trend_60.append({"date": d, "count": daily_trend.get(d, 0)})

    # Environmental impact
    co2_plastic_kg = counts.get("Plastic", 0) * 0.2  # 0.2 kg CO2 per plastic item
    trees_saved = (counts.get("Paper", 0) or 0) / 100.0  # 100 paper = 1 tree

    conn.close()

    return jsonify({
        "total_waste": total,
        "counts": counts,
        "average_confidence": round(avg_conf, 2),
        "trend_60_days": trend_60,
        "co2_saved_kg": round(co2_plastic_kg, 2),
        "trees_saved": round(trees_saved, 2),
    })


# -----------------------------------------------------------------------------
# Admin: users list
# -----------------------------------------------------------------------------
@app.route("/api/admin/users", methods=["GET"])
@login_required
@admin_required
def api_admin_users():
    conn = get_db()
    rows = conn.execute("SELECT id, name, email, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    users = [{"id": r["id"], "name": r["name"], "email": r["email"], "created_at": r["created_at"]} for r in rows]
    return jsonify({"users": users})


@app.route("/api/admin/stats", methods=["GET"])
@login_required
@admin_required
def api_admin_stats():
    return api_analytics()


# -----------------------------------------------------------------------------
# Pages (HTML)
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/detect")
@login_required
def detect():
    return render_template("detect.html")


@app.route("/history")
@login_required
def history():
    return render_template("history.html")


@app.route("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


@app.route("/admin")
@login_required
@admin_required
def admin():
    return render_template("admin.html")


@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# -----------------------------------------------------------------------------
# Init & Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
