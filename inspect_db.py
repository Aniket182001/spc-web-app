import sqlite3
import os

db_path = r'D:\AIQM Work\AI Projects\SPC App\instance\spc_app.db'
if os.path.exists(db_path):
    print(f'{db_path} exists.')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print('Tables in absolute instance path:', tables)
    conn.close()
else:
    print(f'{db_path} does NOT exist.')
