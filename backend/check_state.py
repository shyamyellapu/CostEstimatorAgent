import sqlite3
db = sqlite3.connect(r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db')

print('=== Task Queue Summary ===')
for r in db.execute("SELECT task_type, status, COUNT(*) FROM task_queue GROUP BY task_type, status"):
    print(r)

print()
print('=== Recent failures (last 5) ===')
for r in db.execute("SELECT task_type, status, error_message FROM task_queue WHERE status IN ('failed','retrying') ORDER BY created_at DESC LIMIT 5"):
    print(r)

print()
print('=== Attachment extraction status ===')
for r in db.execute("SELECT extraction_status, COUNT(*) FROM rfq_attachments GROUP BY extraction_status"):
    print(r)

print()
print('=== Sample attachments ===')
for r in db.execute("SELECT original_filename, extraction_status, storage_path FROM rfq_attachments LIMIT 5"):
    print(r)
