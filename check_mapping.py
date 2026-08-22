import psycopg2, json, sys

conn = psycopg2.connect(host='localhost', port=5432, dbname='terralegal', user='terralegal_user', password='terralegal_pass_dev')
cur = conn.cursor()

# Check the form "Don dang ky bien dong, mau so 18"  
cur.execute("SELECT id, mapping, fields FROM form_schemas WHERE id = '58055fb0-72cf-415b-ab24-03695c689082'")
row = cur.fetchone()
form_id = row[0]
mapping = row[1]  # Already dict from psycopg2
fields = row[2]

print("=== MAPPING (first 10) ===")
if mapping:
    for k, v in list(mapping.items())[:10]:
        print(f"  blank_{k} => '{v}'")
else:
    print("  NO MAPPING")
    
print("\n=== FIELDS (first 5) ===")
if fields:
    for f in fields[:5]:
        print(f"  key='{f.get('name', f.get('key', '?'))}' desc='{f.get('description','')[:40]}'")

conn.close()
