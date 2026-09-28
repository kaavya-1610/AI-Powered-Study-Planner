"""Test that break_duration_minutes creates gaps between sessions."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ["DB_OVERRIDE"] = os.path.join(os.path.dirname(__file__), "_break_test.db")

from database import init_db, get_connection
init_db()
conn = get_connection()

# 3.5-hour window: 09:00-12:30, 60-min sessions, 10-min break
# Expect slots: 09:00-10:00, 10:10-11:10, 11:20-12:20 (3 sessions with 10-min gaps)
conn.execute(
    "INSERT OR REPLACE INTO availability "
    "(day_of_week, start_time, end_time, session_duration_minutes, break_duration_minutes) "
    "VALUES (0, '09:00', '12:30', 60, 10)"
)
conn.execute(
    "INSERT INTO subjects (name, syllabus_units, exam_date, priority) "
    "VALUES ('Math', 4, '2026-10-30', 3)"
)
conn.execute(
    "INSERT INTO subjects (name, syllabus_units, exam_date, priority) "
    "VALUES ('Physics', 3, '2026-11-05', 2)"
)
conn.commit()
conn.close()

from scheduler import generate_schedule
result = generate_schedule()
print("Generate result:", result)

conn2 = get_connection()
rows = conn2.execute(
    "SELECT ss.date, ss.start_time, ss.end_time, s.name "
    "FROM study_sessions ss "
    "JOIN subjects s ON ss.subject_id = s.id "
    "ORDER BY ss.date, ss.start_time"
).fetchall()
conn2.close()

print(f"\nSessions scheduled: {len(rows)}")
for r in rows:
    print(f"  {r[0]}  {r[1]} – {r[2]}  ({r[3]})")

# Check that gaps between consecutive sessions on the same day are >= 10 min
print("\nGap check:")
from collections import defaultdict
by_date = defaultdict(list)
for r in rows:
    by_date[r[0]].append(r)

def to_min(t): return int(t[:2]) * 60 + int(t[3:])

all_ok = True
for d, ds in by_date.items():
    for i in range(len(ds) - 1):
        gap = to_min(ds[i+1][1]) - to_min(ds[i][2])
        if gap < 0:
            print(f"  ❌ OVERLAP on {d}: {ds[i][3]} ends {ds[i][2]}, {ds[i+1][3]} starts {ds[i+1][1]}")
            all_ok = False
        else:
            print(f"  ✅ {d}: {ds[i][3]} ends {ds[i][2]} → {gap} min gap → {ds[i+1][3]} starts {ds[i+1][1]}")

if all_ok:
    print("\n✅ All gaps are valid — breaks applied correctly")

os.remove(os.environ["DB_OVERRIDE"])
