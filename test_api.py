"""
Quick API test – run while Flask is NOT running.
Starts Flask in-process and fires requests directly.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Point to the test DB so we don't pollute the real one
os.environ["DB_OVERRIDE"] = os.path.join(os.path.dirname(__file__), "test.db")

from app import app

client = app.test_client()
app.config["TESTING"] = True

def ok(label, resp, expected_status=200):
    data = json.loads(resp.data)
    status = "✅" if resp.status_code == expected_status else "❌"
    print(f"{status} [{resp.status_code}] {label}: {data}")
    return data

print("\n── Health ───────────────────────────────────")
ok("health", client.get("/api/health"))

print("\n── Subjects ─────────────────────────────────")
ok("add Math",    client.post("/api/subjects",
    json={"name":"Mathematics","syllabus_units":8,"exam_date":"2026-10-20","priority":3}), 201)
ok("add Physics", client.post("/api/subjects",
    json={"name":"Physics","syllabus_units":5,"exam_date":"2026-10-25","priority":2}), 201)
ok("add English", client.post("/api/subjects",
    json={"name":"English","syllabus_units":4,"exam_date":"2026-11-01","priority":1}), 201)
ok("list all",    client.get("/api/subjects"))
ok("delete id=1", client.delete("/api/subjects/1"))
ok("list after delete", client.get("/api/subjects"))

print("\n── Availability ─────────────────────────────")
ok("set Monday",    client.post("/api/availability",
    json={"day_of_week":0,"start_time":"09:00","end_time":"13:00","session_duration_minutes":60}), 201)
ok("set Wednesday", client.post("/api/availability",
    json={"day_of_week":2,"start_time":"14:00","end_time":"17:00","session_duration_minutes":60}), 201)
ok("set Friday",    client.post("/api/availability",
    json={"day_of_week":4,"start_time":"10:00","end_time":"14:00","session_duration_minutes":90}), 201)
ok("list all",      client.get("/api/availability"))

# Update Monday (same day_of_week → should upsert)
ok("update Monday", client.post("/api/availability",
    json={"day_of_week":0,"start_time":"08:00","end_time":"12:00","session_duration_minutes":60}), 201)
ok("list after update", client.get("/api/availability"))

print("\n── Validation errors ────────────────────────")
ok("missing name",      client.post("/api/subjects",
    json={"syllabus_units":3,"exam_date":"2026-10-20","priority":2}), 400)
ok("bad priority",      client.post("/api/subjects",
    json={"name":"Bio","syllabus_units":3,"exam_date":"2026-10-20","priority":5}), 400)
ok("end before start",  client.post("/api/availability",
    json={"day_of_week":1,"start_time":"15:00","end_time":"10:00","session_duration_minutes":60}), 400)

# Clean up test DB
import os as _os
_os.remove(os.environ["DB_OVERRIDE"])
print("\n✅ All tests completed – test DB removed")
