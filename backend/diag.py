import sqlite3
db = sqlite3.connect(r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db')
print('=== ROOT DB tables ===')
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    n = r[0]; c = db.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
    print(f'  {n}: {c}')
print()
print('=== RFQ Records ===')
for r in db.execute('SELECT id, rfq_number, client_name, status FROM rfq_records LIMIT 5'):
    print(r)
print()
print('=== Task Queue ===')
for r in db.execute('SELECT task_type, entity_type, status, error_message, attempts FROM task_queue ORDER BY created_at DESC LIMIT 10'):
    print(r)
print()
print('=== RFQ Attachments ===')
for r in db.execute('SELECT id, original_filename, file_category, extraction_status, storage_path FROM rfq_attachments LIMIT 5'):
    print(r)
print()
print('=== Extraction Reviews ===')
for r in db.execute('PRAGMA table_info(extraction_reviews)'):
    print(r[1])
