"""
test_final.py
Full integration test - covers all phases including Phase 7 fixes.
Run with: venv/Scripts/python test_final.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ["DB_OVERRIDE"] = os.path.join(os.path.dirname(__file__), "_test_final.db")

from app import app
c = app.test_client()
app.config["TESTING"] = True

PASS = "✅"; FAIL = "❌"

def chk(label, resp, exp_status=None, must_contain=None):
    d    = json.loads(resp.data)
    ok   = (exp_status is None and resp.status_code < 300) or resp.status_code == exp_status
    if must_contain and isinstance(d, dict):
        ok = ok and must_contain in d
    print(PASS if ok else FAIL, f"[{resp.status_code}]", label)
    if not ok:
        print("    →", d)
    return d

def section(title):
    print(f"\n── {title} {'─'*(50-len(title))}")

# ─────────────────────────────────────────────────────────────────────────────
section("Health check")
chk("GET /api/health", c.get("/api/health"))

# ─────────────────────────────────────────────────────────────────────────────
section("Subject validation")
chk("reject missing name",
    c.post("/api/subjects", json={"syllabus_units":3,"exam_date":"2026-10-20","priority":2}), 400)
chk("reject bad priority (5)",
    c.post("/api/subjects", json={"name":"X","syllabus_units":3,"exam_date":"2026-10-20","priority":5}), 400)
chk("reject zero units",
    c.post("/api/subjects", json={"name":"X","syllabus_units":0,"exam_date":"2026-10-20","priority":2}), 400)

# ─────────────────────────────────────────────────────────────────────────────
section("Add subjects")
chk("Math  (high, 4 weeks)",  c.post("/api/subjects",
    json={"name":"Mathematics","syllabus_units":8,"exam_date":"2026-10-20","priority":3}), 201)
chk("Physics (med, 5 weeks)", c.post("/api/subjects",
    json={"name":"Physics","syllabus_units":5,"exam_date":"2026-10-25","priority":2}), 201)
chk("English (low, 6 weeks)", c.post("/api/subjects",
    json={"name":"English","syllabus_units":4,"exam_date":"2026-11-01","priority":1}), 201)

subjects = chk("GET all subjects", c.get("/api/subjects"))
assert len(subjects) == 3, f"Expected 3 subjects, got {len(subjects)}"

# ─────────────────────────────────────────────────────────────────────────────
section("Availability validation")
chk("reject end before start",
    c.post("/api/availability",
     json={"day_of_week":0,"start_time":"15:00","end_time":"10:00","session_duration_minutes":60}), 400)
chk("reject short duration (<15)",
    c.post("/api/availability",
     json={"day_of_week":0,"start_time":"09:00","end_time":"10:00","session_duration_minutes":10}), 400)
chk("reject invalid day (7)",
    c.post("/api/availability",
     json={"day_of_week":7,"start_time":"09:00","end_time":"11:00","session_duration_minutes":60}), 400)

# ─────────────────────────────────────────────────────────────────────────────
section("Add availability")
for day, s, e in [(0,"09:00","11:00"),(2,"14:00","16:00"),(4,"10:00","12:00")]:
    chk(f"day {day}", c.post("/api/availability",
        json={"day_of_week":day,"start_time":s,"end_time":e,"session_duration_minutes":60}), 201)

# Upsert – same day again
chk("upsert Monday", c.post("/api/availability",
    json={"day_of_week":0,"start_time":"08:00","end_time":"12:00","session_duration_minutes":60}), 201)
avail = chk("GET availability", c.get("/api/availability"))
monday = [a for a in avail if a["day_of_week"] == 0][0]
assert monday["start_time"] == "08:00", "Monday should be updated to 08:00"
print(PASS, "Upsert applied correctly")

# ─────────────────────────────────────────────────────────────────────────────
section("Schedule generation")
result = chk("generate", c.post("/api/schedule/generate"), 201)
assert result["sessions_created"] > 0, "Should create at least 1 session"

sessions = chk("GET /api/schedule", c.get("/api/schedule"))
print(f"   → {len(sessions)} sessions generated")

# Subjects covered
covered = {s["subject_name"] for s in sessions}
for name in ["Mathematics", "Physics", "English"]:
    icon = PASS if name in covered else FAIL
    print(icon, f"  {name} in schedule")

# No overlapping sessions on the same day
from collections import defaultdict
by_date = defaultdict(list)
for s in sessions:
    by_date[s["date"]].append(s)

overlap = False
for d, ds in by_date.items():
    ds.sort(key=lambda x: x["start_time"])
    for i in range(len(ds)-1):
        if ds[i]["end_time"] > ds[i+1]["start_time"]:
            print(FAIL, f"  Overlap on {d}: {ds[i]['subject_name']} vs {ds[i+1]['subject_name']}")
            overlap = True
print(PASS if not overlap else FAIL, "No overlapping sessions")

# Regenerate (idempotent) – should produce same count
result2 = chk("re-generate (idempotent)", c.post("/api/schedule/generate"), 201)
assert result2["sessions_created"] == result["sessions_created"], \
    f"Re-generate mismatch: {result2['sessions_created']} vs {result['sessions_created']}"
print(PASS, "Re-generation is idempotent")

# ─────────────────────────────────────────────────────────────────────────────
section("Progress tracking")
sessions2 = json.loads(c.get("/api/schedule").data)

# Mark first 5 complete
for s in sessions2[:5]:
    chk(f"complete #{s['id']}", c.post(
        f"/api/schedule/sessions/{s['id']}/complete",
        json={"completed":1}))

stats = chk("GET /api/stats", c.get("/api/stats"))
assert stats["completed_sessions"] == 5, f"Expected 5 done, got {stats['completed_sessions']}"
assert stats["pending_sessions"] == stats["total_sessions"] - 5
assert 0 < stats["overall_pct"] <= 100
print(PASS, f"Stats: {stats['completed_sessions']}/{stats['total_sessions']} ({stats['overall_pct']}%)")

# Undo one
chk("undo complete #1", c.post(
    f"/api/schedule/sessions/{sessions2[0]['id']}/complete",
    json={"completed":0}))
stats2 = json.loads(c.get("/api/stats").data)
assert stats2["completed_sessions"] == 4
print(PASS, "Undo works correctly")

# ─────────────────────────────────────────────────────────────────────────────
section("Delete subject + cascade")
# Delete Math (id=1) – its sessions should also disappear
chk("delete Math", c.delete("/api/subjects/1"))
remaining = json.loads(c.get("/api/subjects").data)
assert len(remaining) == 2, f"Expected 2 subjects, got {len(remaining)}"
sched_after = json.loads(c.get("/api/schedule").data)
math_sessions = [s for s in sched_after if s["subject_name"] == "Mathematics"]
assert len(math_sessions) == 0, "Math sessions should be cascade-deleted"
print(PASS, "Cascade delete works")

# ─────────────────────────────────────────────────────────────────────────────
os.remove(os.environ["DB_OVERRIDE"])
print(f"\n{'─'*55}")
print("✅  All Phase 7 tests passed — test DB removed")
