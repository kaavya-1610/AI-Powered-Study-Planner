"""
scheduler.py
Rule-based study schedule generator.

Algorithm overview
──────────────────
1. Load all subjects and the student's weekly availability.
2. For each subject calculate sessions_needed = syllabus_units (1 unit = 1 session).
3. Walk forward day-by-day from today until the latest exam (max 90 days).
4. On each available day, rank subjects by weight:
       weight = priority_multiplier × urgency_factor × remaining_ratio
5. Fill the day's time window with sessions, rotating through ranked
   subjects one slot at a time so no subject dominates a single day.
6. Stop allocating a subject once its sessions_left reaches 0.
7. Persist sessions to DB (previous schedule is cleared first).
"""

import math
from datetime import date, datetime, timedelta
from database import get_connection

SESSIONS_PER_UNIT = 1.0      # sessions needed per syllabus unit
MAX_DAYS_AHEAD    = 90       # never plan beyond this many days from today

PRIORITY_MULTIPLIER = {1: 1.0, 2: 1.5, 3: 2.0}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minutes_between(start_str: str, end_str: str) -> int:
    fmt = "%H:%M"
    s = datetime.strptime(start_str, fmt)
    e = datetime.strptime(end_str,   fmt)
    return max(0, int((e - s).total_seconds() // 60))


def _add_minutes(time_str: str, minutes: int) -> str:
    t = datetime.strptime(time_str, "%H:%M") + timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def _urgency(exam_date: date, today: date) -> float:
    """1.0 (≥30 days away) → 3.0 (exam today or past)."""
    days_left = (exam_date - today).days
    if days_left <= 0:  return 3.0
    if days_left >= 30: return 1.0
    return round(1.0 + (30 - days_left) / 29.0 * 2.0, 3)


def _score(subject: dict, ref_day: date) -> float:
    """
    Higher score → subject gets earlier/more slots.
    ref_day is passed explicitly so there is no loop-closure capture.
    """
    urgency   = _urgency(subject["exam_date"], ref_day)
    priority  = PRIORITY_MULTIPLIER.get(subject["priority"], 1.0)
    remaining = subject["sessions_left"] / subject["sessions_needed"]
    return urgency * priority * remaining


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_schedule() -> dict:
    conn  = get_connection()
    today = date.today()

    # ── Load data ─────────────────────────────────────────────────────
    subject_rows = conn.execute(
        "SELECT * FROM subjects ORDER BY exam_date ASC"
    ).fetchall()
    if not subject_rows:
        conn.close()
        return {"error": "No subjects found. Please add subjects first."}

    avail_rows = conn.execute(
        "SELECT * FROM availability ORDER BY day_of_week"
    ).fetchall()
    if not avail_rows:
        conn.close()
        return {"error": "No availability set. Please add your available study days first."}

    # day_of_week → {start, end, duration, break}
    avail = {}
    for row in avail_rows:
        avail[row["day_of_week"]] = {
            "start":    row["start_time"],
            "end":      row["end_time"],
            "duration": row["session_duration_minutes"],
            "break":    row["break_duration_minutes"],   # gap between sessions
        }

    # ── Build subject working list ────────────────────────────────────
    subjects = []
    for row in subject_rows:
        exam_dt = datetime.strptime(row["exam_date"], "%Y-%m-%d").date()
        needed  = max(1, math.ceil(row["syllabus_units"] * SESSIONS_PER_UNIT))
        subjects.append({
            "id":              row["id"],
            "name":            row["name"],
            "exam_date":       exam_dt,
            "priority":        row["priority"],
            "syllabus_units":  row["syllabus_units"],
            "sessions_needed": needed,
            "sessions_left":   needed,
        })

    latest_exam = max(s["exam_date"] for s in subjects)
    end_date    = min(latest_exam, today + timedelta(days=MAX_DAYS_AHEAD))

    # ── Clear old schedule ────────────────────────────────────────────
    conn.execute("DELETE FROM study_sessions")
    conn.commit()

    # ── Walk day by day ───────────────────────────────────────────────
    sessions_created = 0
    current_day      = today

    while current_day <= end_date:

        dow = current_day.weekday()   # 0=Mon … 6=Sun

        # Skip unavailable days
        if dow not in avail:
            current_day += timedelta(days=1)
            continue

        # Subjects still needing sessions before their exam
        active = [
            s for s in subjects
            if s["sessions_left"] > 0 and s["exam_date"] >= current_day
        ]

        if not active:
            break   # nothing left to schedule

        slot     = avail[dow]
        cursor   = slot["start"]
        dur      = slot["duration"]
        brk      = slot["break"]       # minutes of rest between sessions
        slot_end = slot["end"]

        # Rank subjects for this specific day (no closure over current_day)
        ranked = sorted(active, key=lambda s: _score(s, current_day), reverse=True)

        # Round-robin through ranked list, one session per iteration
        robin_idx    = 0
        first_slot   = True   # no break before the very first session of the day

        while _minutes_between(cursor, slot_end) >= dur:
            # Find the next subject in the ranked list that still has sessions
            placed = False
            for attempt in range(len(ranked)):
                idx  = (robin_idx + attempt) % len(ranked)
                subj = ranked[idx]
                if subj["sessions_left"] <= 0:
                    continue

                sess_end = _add_minutes(cursor, dur)
                conn.execute(
                    "INSERT INTO study_sessions "
                    "(subject_id, date, start_time, end_time, completed) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (subj["id"], current_day.isoformat(), cursor, sess_end)
                )
                subj["sessions_left"] -= 1
                sessions_created      += 1

                # Advance cursor: after session + break (no break after last slot)
                cursor    = _add_minutes(sess_end, brk) if brk > 0 else sess_end
                robin_idx = (idx + 1) % len(ranked)
                placed    = True
                first_slot = False
                break   # one session placed; go back to outer while

            if not placed:
                break   # no subject has sessions left for today

        current_day += timedelta(days=1)

    conn.commit()
    conn.close()

    covered = sum(1 for s in subjects if s["sessions_left"] < s["sessions_needed"])
    total   = sessions_created
    return {
        "sessions_created": total,
        "subjects_covered": covered,
        "message": (
            f"Schedule generated: {total} session"
            f"{'s' if total != 1 else ''} across "
            f"{covered} subject{'s' if covered != 1 else ''}."
        ),
    }
