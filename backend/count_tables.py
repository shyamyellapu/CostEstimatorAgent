import sqlite3
db = sqlite3.connect('cost_estimator.db')
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    n = r[0]
    c = db.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
    print(n, c)
