import sqlite3
db = sqlite3.connect(r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db')

print('=== Line items per RFQ ===')
for r in db.execute("""
    SELECT r.rfq_number, COUNT(li.id) as line_items, r.status
    FROM rfq_records r
    LEFT JOIN rfq_line_items li ON li.rfq_id = r.id
    GROUP BY r.id
"""):
    print(f"  {r[0]:<30} {r[1]} line items  [{r[2]}]")

print()
print('=== Sample line items for RFQ-20260527-33389B ===')
for r in db.execute("""
    SELECT li.description, li.material, li.quantity, li.unit, li.confidence_score
    FROM rfq_line_items li
    JOIN rfq_records r ON r.id = li.rfq_id
    WHERE r.rfq_number = 'RFQ-20260527-33389B'
    LIMIT 10
"""):
    print(f"  {r}")

print()
print('=== Completed attachments with extraction ===')
for r in db.execute("SELECT original_filename, extraction_status, document_type FROM rfq_attachments WHERE extraction_status='completed'"):
    print(f"  {r[0]:<50} {r[1]}  type={r[2]}")
