import sys, psycopg2
sys.stdout.reconfigure(encoding='utf-8')
conn = psycopg2.connect(host='localhost', port=5432, dbname='terralegal', user='terralegal_user', password='terralegal_pass_dev')
cur = conn.cursor()
cur.execute("SELECT fields FROM form_schemas WHERE id = 'b7413cfd-1b21-4a18-a524-f5206ba9726b'")
fields = cur.fetchone()[0]
conn.close()

if fields:
    for f in fields[:10]:
        print(f.get('key'), f.get('name'))
    print("...")
    for f in fields[-10:]:
        print(f.get('key'), f.get('name'))
else:
    print("NO FIELDS")
