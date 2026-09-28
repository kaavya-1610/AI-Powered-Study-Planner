"""
routes/schedule.py
Endpoints for generating and viewing the study schedule.

POST /api/schedule/generate                    → run the scheduler
GET  /api/schedule                             → list all sessions
POST /api/schedule/sessions/<id>/complete      → mark complete/incomplete
"""

from flask import Blueprint, request, jsonify
from database import get_connection
from scheduler import generate_schedule

schedule_bp = Blueprint("schedule", __name__)


# ── Generate schedule ─────────────────────────────────────────────────────────
@schedule_bp.route("/api/schedule/generate", methods=["POST"])
def generate():
    result = generate_schedule()
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


# ── Get all sessions ──────────────────────────────────────────────────────────
@schedule_bp.route("/api/schedule", methods=["GET"])
def get_schedule():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            ss.id,
            ss.date,
            ss.start_time,
            ss.end_time,
            ss.completed,
            s.name        AS subject_name,
            s.priority    AS priority,
            s.exam_date   AS exam_date
        FROM study_sessions ss
        JOIN subjects s ON ss.subject_id = s.id
        ORDER BY ss.date ASC, ss.start_time ASC
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ── Mark a session complete / incomplete ──────────────────────────────────────
@schedule_bp.route("/api/schedule/sessions/<int:session_id>/complete", methods=["POST"])
def mark_complete(session_id):
    data = request.get_json()
    completed = int(data.get("completed", 1))   # default: mark done

    if completed not in (0, 1):
        return jsonify({"error": "completed must be 0 or 1"}), 400

    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM study_sessions WHERE id = ?", (session_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Session not found"}), 404

    conn.execute(
        "UPDATE study_sessions SET completed = ? WHERE id = ?",
        (completed, session_id)
    )
    conn.commit()
    conn.close()

    status = "completed" if completed else "incomplete"
    return jsonify({"message": f"Session marked as {status}"})
