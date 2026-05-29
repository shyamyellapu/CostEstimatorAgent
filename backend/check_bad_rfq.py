import sqlite3
db = sqlite3.connect(r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db')
bad_ids = ('PR','for','erred','RFQ-20260527-8A99AF','RFQ-20260527-B9F7E8')
print('=== Bad RFQ records emails ===')
for r in db.execute('''
    SELECT r.rfq_number, r.subject, r.client_name, e.subject as email_subject, e.sender_email
    FROM rfq_records r LEFT JOIN rfq_emails e ON e.rfq_id=r.id
'''):
    if r[0] in bad_ids:
        print(r)
