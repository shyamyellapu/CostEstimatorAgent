"""Reset failed/stuck tasks to pending so the worker retries them."""
import sqlite3
import datetime

db_path = r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT status, COUNT(*) FROM task_queue GROUP BY status")
print("Before reset:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

now = datetime.datetime.utcnow().isoformat()
c.execute(
    "UPDATE task_queue SET status='pending', attempts=0, error_message=NULL WHERE status IN ('failed','running','retrying')",
)
print(f"\nReset {c.rowcount} tasks to pending")

c.execute(
    "UPDATE rfq_attachments SET extraction_status='pending', extraction_error=NULL WHERE extraction_status IN ('running','failed')"
)
print(f"Reset {c.rowcount} attachments extraction status")

conn.commit()

c.execute("SELECT status, COUNT(*) FROM task_queue GROUP BY status")
print("\nAfter reset:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
