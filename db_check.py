import psycopg2, json

conn = psycopg2.connect(host='localhost', port=5432, dbname='terralegal', user='terralegal_user', password='terralegal_pass_dev')
cur = conn.cursor()

# Get all forms with name, mapping info
cur.execute("SELECT id, name, mapping IS NOT NULL as has_mapping FROM form_schemas ORDER BY name")
rows = cur.fetchall()
for r in rows:
    print(f"ID: {r[0]} | has_mapping: {r[2]}")
    
# Get the specific form - Đơn đăng ký biến động
cur.execute("""
    SELECT id, name, 
           (SELECT count(*) FROM jsonb_array_elements(fields) f) as num_fields,
           mapping IS NOT NULL as has_mapping
    FROM form_schemas
""")
rows = cur.fetchall()
print("\n=== Full Form List ===")
for r in rows:
    print(f"ID: {r[0]} | Name: {r[1][:30]} | fields: {r[2]} | has_mapping: {r[3]}")

conn.close()
