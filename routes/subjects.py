"""
routes/subjects.py
CRUD endpoints for subjects.

GET    /api/subjects          → list all subjects
POST   /api/subjects          → add a new subject
DELETE /api/subjects/<id>     → delete a subject
"""

from flask import Blueprint, request, jsonify
from database import get_connection

# A Blueprint groups related routes together.
# We register it in app.py with app.register_blueprint(subjects_bp)
subjects_bp = Blueprint("subjects", __name__)


# ── GET all subjects ──────────────────────────────────────────────────────────
@subjects_bp.route("/api/subjects", methods=["GET"])
def get_subjects():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM subjects ORDER BY exam_date ASC"
    ).fetchall()
    conn.close()

    # Convert each sqlite3.Row to a plain dict so jsonify can serialise it
    subjects = [dict(row) for row in rows]
    return jsonify(subjects)


# ── POST a new subject ────────────────────────────────────────────────────────
@subjects_bp.route("/api/subjects", methods=["POST"])
def add_subject():
    data = request.get_json()

    # ── Validate required fields ──
    required = ["name", "syllabus_units", "exam_date", "priority"]
    for field in required:
        if not data or field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    name           = str(data["name"]).strip()
    syllabus_units = int(data["syllabus_units"])
    exam_date      = str(data["exam_date"])          # expected: "YYYY-MM-DD"
    priority       = int(data["priority"])           # 1, 2, or 3

    if not name:
        return jsonify({"error": "Subject name cannot be empty"}), 400
    if syllabus_units < 1:
        return jsonify({"error": "Syllabus units must be at least 1"}), 400
    if priority not in (1, 2, 3):
        return jsonify({"error": "Priority must be 1 (low), 2 (medium), or 3 (high)"}), 400

    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO subjects (name, syllabus_units, exam_date, priority)
           VALUES (?, ?, ?, ?)""",
        (name, syllabus_units, exam_date, priority)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({"message": "Subject added", "id": new_id}), 201


# ── DELETE a subject ──────────────────────────────────────────────────────────
@subjects_bp.route("/api/subjects/<int:subject_id>", methods=["DELETE"])
def delete_subject(subject_id):
    conn = get_connection()

    # Make sure it exists first
    row = conn.execute(
        "SELECT id FROM subjects WHERE id = ?", (subject_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Subject not found"}), 404

    # ON DELETE CASCADE in DB will also remove related study_sessions
    conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Subject deleted"})
