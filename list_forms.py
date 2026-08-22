import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='terralegal', user='terralegal_user', password='terralegal_pass_dev')
cur = conn.cursor()
cur.execute("SELECT id, left(name, 60) as name FROM form_schemas ORDER BY name")
rows = cur.fetchall()
for r in rows:
    print(f"{r[0]}  |  {r[1].encode('ascii','replace').decode()}")
conn.close()
