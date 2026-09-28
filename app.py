"""
Study Planner - Main Flask Application
"""

from flask import Flask, jsonify
from flask_cors import CORS
from database import init_db, get_connection
from routes.subjects import subjects_bp
from routes.availability import availability_bp
from routes.schedule import schedule_bp
from routes.stats import stats_bp

app = Flask(__name__)
CORS(app)

# Create DB tables on startup
init_db()

# Register route blueprints
app.register_blueprint(subjects_bp)
app.register_blueprint(availability_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(stats_bp)


# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    return jsonify({
        "status": "ok",
        "message": "Study Planner API is running!",
        "db_tables": [t["name"] for t in tables]
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
