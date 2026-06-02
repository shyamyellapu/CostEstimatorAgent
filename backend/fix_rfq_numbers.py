"""Fix bad rfq_numbers while the server may be running — uses WAL timeout."""
import sqlite3, uuid, time

for attempt in range(10):
    try:
        db = sqlite3.connect(
            r'C:\Users\Bhatia\Desktop\CostEstimatorAgent\cost_estimator.db',
            timeout=30
        )
        db.execute('UPDATE rfq_records SET rfq_number=? WHERE id=?',
                   ('PR#ADI60049003', 'a76a0563-3788-4d98-a412-c84d5ba79b7d'))
        db.execute('UPDATE rfq_records SET rfq_number=? WHERE id=?',
                   ('RFQ-731-05-ADNOC', 'dbad7094-d04d-411b-bf1e-d64756541198'))
        new_num = 'RFQ-' + uuid.uuid4().hex[:6].upper()
        db.execute('UPDATE rfq_records SET rfq_number=? WHERE id=?',
                   (new_num, 'e9a33f58-0f30-420e-9a0a-2aa5a40b3da0'))
        db.commit()
        print('Updated. Verifying:')
        for r in db.execute('SELECT rfq_number, subject FROM rfq_records'):
            print(f'  {r[0]:<30} {r[1]}')
        db.close()
        break
    except sqlite3.OperationalError as e:
        print(f'Attempt {attempt+1}: {e}, retrying...')
        time.sleep(3)
