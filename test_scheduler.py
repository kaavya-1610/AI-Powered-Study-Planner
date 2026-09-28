"""
test_scheduler.py
Tests the scheduling algorithm end-to-end using Flask's test client.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

os.environ["DB_OVERRIDE"] = os.path.join(os.path.dirname(__file__), "test_sched.db")

from app import app
client = app.test_client()
app.config["TESTING"] = True

def jprint(label, resp):
    data = json.loads(resp.data)
    ok = "✅" if resp.status_code < 300 else "❌"
    print(f"{ok} [{resp.status_code}] {label}")
    if isinstance(data, list):
        print(f"   → {len(data)} items")
        for item in data[:3]:     # show first 3
            print(f"     {item}")
        if len(data) > 3:
            print(f"     … and {len(data)-3} more")
    else:
        print(f"   → {data}")
    return data

print("\n══ Setup: add subjects and availability ══════════════════════════")

# Add 3 subjects with different priorities and exam dates
jprint("add Math (high priority, 4 weeks)",
    client.post("/api/subjects", json={
        "name": "Mathematics", "syllabus_units": 8,
        "exam_date": "2026-10-20", "priority": 3
    }))
jprint("add Physics (medium priority, 5 weeks)",
    client.post("/api/subjects", json={
        "name": "Physics", "syllabus_units": 5,
        "exam_date": "2026-10-25", "priority": 2
    }))
jprint("add English (low priority, 6 weeks)",
    client.post("/api/subjects", json={
        "name": "English", "syllabus_units": 4,
        "exam_date": "2026-11-01", "priority": 1
    }))

# Available Mon / Wed / Fri, 2 hours per day, 60 min sessions
for day, start, end in [(0,"09:00","11:00"), (2,"14:00","16:00"), (4,"10:00","12:00")]:
    jprint(f"set day {day}",
        client.post("/api/availability", json={
            "day_of_week": day, "start_time": start,
            "end_time": end, "session_duration_minutes": 60
        }))

print("\n══ Generate schedule ══════════════════════════════════════════════")
result = jprint("generate", client.post("/api/schedule/generate"))

print("\n══ View schedule ══════════════════════════════════════════════════")
sessions = jprint("get all sessions", client.get("/api/schedule"))

# Validate: no two sessions overlap on the same day
print("\n══ Overlap check ══════════════════════════════════════════════════")
from collections import defaultdict
by_date = defaultdict(list)
for s in sessions:
    by_date[s["date"]].append(s)

overlap_found = False
for d, day_sessions in by_date.items():
    day_sessions.sort(key=lambda x: x["start_time"])
    for i in range(len(day_sessions) - 1):
        a = day_sessions[i]
        b = day_sessions[i+1]
        if a["end_time"] > b["start_time"]:
            print(f"  ❌ OVERLAP on {d}: {a['subject_name']} {a['start_time']}-{a['end_time']} vs {b['subject_name']} {b['start_time']}-{b['end_time']}")
            overlap_found = True

if not overlap_found:
    print("  ✅ No overlapping sessions found")

# Check all subjects appear in the schedule
print("\n══ Coverage check ══════════════════════════════════════════════════")
scheduled_subjects = set(s["subject_name"] for s in sessions)
for name in ["Mathematics", "Physics", "English"]:
    icon = "✅" if name in scheduled_subjects else "❌"
    count = sum(1 for s in sessions if s["subject_name"] == name)
    print(f"  {icon} {name}: {count} sessions")

# Clean up
import os as _os
_os.remove(os.environ["DB_OVERRIDE"])
print("\n✅ Scheduler tests complete – test DB removed")
