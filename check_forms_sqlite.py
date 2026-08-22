import sqlite3
import json

def check():
    conn = sqlite3.connect("backend/data/terra_legal.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, fields FROM form_schemas")
    for row in cursor.fetchall():
        print(f"ID: {row[0]}")
        print(f"Name: {row[1]}")
        print(f"Fields: {row[2]}")
        print("-" * 50)
    conn.close()

if __name__ == "__main__":
    check()
