import sqlite3
db = sqlite3.connect(r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db')

# Reset ALL extract/classify tasks that are not completed — start fresh
cur = db.execute(
    "UPDATE task_queue SET status='pending', attempts=0, error_message=NULL "
    "WHERE task_type IN ('extract_attachment','classify_attachment') "
    "AND status IN ('failed','retrying','running')"
)
print(f"Reset {cur.rowcount} failed/retrying/running extract tasks")

# Reset attachments stuck in 'running' back to 'pending'
cur2 = db.execute(
    "UPDATE rfq_attachments SET extraction_status='pending' "
    "WHERE extraction_status='running'"
)
print(f"Reset {cur2.rowcount} stuck 'running' attachments to 'pending'")

print()
print("=== Task queue after reset ===")
for r in db.execute("SELECT task_type, status, COUNT(*) FROM task_queue GROUP BY task_type, status ORDER BY task_type, status"):
    print(f"  {r[0]:<25} {r[1]:<12} {r[2]}")

print()
print("=== Attachment status after reset ===")
for r in db.execute("SELECT extraction_status, COUNT(*) FROM rfq_attachments GROUP BY extraction_status"):
    print(f"  {r[0]}: {r[1]}")

db.commit()
db.close()
print("\nDone.")
