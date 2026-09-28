"""
routes/stats.py
Progress statistics endpoint used by the dashboard.

GET /api/stats   → summary of sessions total, completed, per-subject breakdown
"""

from flask import Blueprint, jsonify
from database import get_connection

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/stats", methods=["GET"])
def get_stats():
    conn = get_connection()

    # Overall counts
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM study_sessions"
    ).fetchone()["n"]

    completed = conn.execute(
        "SELECT COUNT(*) AS n FROM study_sessions WHERE completed = 1"
    ).fetchone()["n"]

    # Per-subject breakdown
    rows = conn.execute(
        """
        SELECT
            s.id,
            s.name,
            s.exam_date,
            s.priority,
            COUNT(ss.id)                        AS total_sessions,
            SUM(CASE WHEN ss.completed=1 THEN 1 ELSE 0 END) AS done_sessions
        FROM subjects s
        LEFT JOIN study_sessions ss ON ss.subject_id = s.id
        GROUP BY s.id
        ORDER BY s.exam_date ASC
        """
    ).fetchall()
    conn.close()

    subjects_stats = []
    for r in rows:
        t = r["total_sessions"] or 0
        d = r["done_sessions"]  or 0
        subjects_stats.append({
            "id":             r["id"],
            "name":           r["name"],
            "exam_date":      r["exam_date"],
            "priority":       r["priority"],
            "total_sessions": t,
            "done_sessions":  d,
            "pct":            round(d / t * 100) if t > 0 else 0,
        })

    return jsonify({
        "total_sessions":     total,
        "completed_sessions": completed,
        "pending_sessions":   total - completed,
        "overall_pct":        round(completed / total * 100) if total > 0 else 0,
        "subjects":           subjects_stats,
    })
