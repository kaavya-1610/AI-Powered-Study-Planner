"""
routes/availability.py
Endpoints for managing daily study availability.

GET    /api/availability        → list all availability entries
POST   /api/availability        → add or update a day's availability
DELETE /api/availability/<id>   → remove a day
"""

from flask import Blueprint, request, jsonify
from database import get_connection

availability_bp = Blueprint("availability", __name__)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── GET all availability ──────────────────────────────────────────────────────
@availability_bp.route("/api/availability", methods=["GET"])
def get_availability():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM availability ORDER BY day_of_week ASC"
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        entry = dict(row)
        entry["day_name"] = DAYS[entry["day_of_week"]]
        result.append(entry)

    return jsonify(result)


# ── POST / upsert availability for one day ────────────────────────────────────
@availability_bp.route("/api/availability", methods=["POST"])
def set_availability():
    data = request.get_json()

    required = ["day_of_week", "start_time", "end_time", "session_duration_minutes"]
    for field in required:
        if not data or field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    day      = int(data["day_of_week"])
    start    = str(data["start_time"])
    end      = str(data["end_time"])
    duration = int(data["session_duration_minutes"])
    # break_duration_minutes is optional; defaults to 10
    break_dur = int(data.get("break_duration_minutes", 10))

    if day not in range(7):
        return jsonify({"error": "day_of_week must be 0 (Monday) to 6 (Sunday)"}), 400
    if duration < 15:
        return jsonify({"error": "Session duration must be at least 15 minutes"}), 400
    if break_dur < 0:
        return jsonify({"error": "Break duration cannot be negative"}), 400
    if start >= end:
        return jsonify({"error": "start_time must be before end_time"}), 400

    conn = get_connection()
    conn.execute(
        """INSERT INTO availability
               (day_of_week, start_time, end_time,
                session_duration_minutes, break_duration_minutes)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(day_of_week) DO UPDATE SET
               start_time               = excluded.start_time,
               end_time                 = excluded.end_time,
               session_duration_minutes = excluded.session_duration_minutes,
               break_duration_minutes   = excluded.break_duration_minutes""",
        (day, start, end, duration, break_dur)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": f"Availability saved for {DAYS[day]}"}), 201


# ── DELETE one day's availability ─────────────────────────────────────────────
@availability_bp.route("/api/availability/<int:avail_id>", methods=["DELETE"])
def delete_availability(avail_id):
    conn = get_connection()

    row = conn.execute(
        "SELECT id FROM availability WHERE id = ?", (avail_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Entry not found"}), 404

    conn.execute("DELETE FROM availability WHERE id = ?", (avail_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Availability entry deleted"})
