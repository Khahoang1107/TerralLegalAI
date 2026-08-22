import os

file_path = r'd:\TerraLegalAI\docker-compose.yml'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace dockerfile: Dockerfile with dockerfile: Dockerfile.dev
content = content.replace('dockerfile: Dockerfile', 'dockerfile: Dockerfile.dev')

# Inject volumes if not present
if 'volumes:\n      - ./frontend:/app' not in content:
    target = '    ports:\n      - "3000:3000"\n    depends_on:'
    replacement = '    ports:\n      - "3000:3000"\n    volumes:\n      - ./frontend:/app\n      - /app/node_modules\n      - /app/.next\n    depends_on:'
    content = content.replace(target, replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated docker-compose.yml")
