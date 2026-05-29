import sqlite3
db = sqlite3.connect(r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db')

print('=== Task queue status counts ===')
for r in db.execute('SELECT status, COUNT(*) FROM task_queue GROUP BY status'):
    print(r)

print()
print('=== Failed tasks errors ===')
for r in db.execute("SELECT task_type, entity_id, error_message, attempts FROM task_queue WHERE status='failed' ORDER BY created_at DESC LIMIT 10"):
    print(r)

print()
print('=== Attachments status ===')
for r in db.execute("SELECT original_filename, extraction_status, storage_path, file_category, document_type FROM rfq_attachments LIMIT 10"):
    print(r)

db.close()
