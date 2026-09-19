import subprocess

result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)
all_files = [l.strip() for l in result.stdout.splitlines() if l.strip()]

KEEP_DIRS = ['backend/', 'frontend/', 'docker/', 'scripts/']
KEEP_FILES = {
    '.gitignore', '.env.example', 'docker-compose.yml', 'docker-compose.prod.yml',
    'Dockerfile', 'README.md', 'HUONG_DAN_CHAY_DU_AN.md',
    'requirements.txt', 'patch_all_templates.py', 'start.bat',
}
KEEP_SCRIPTS = {
    'scripts/alter_conversation_table.py',
    'scripts/build_test_dataset.py',
    'scripts/ingest_documents.py',
    'scripts/ocr_documents.py',
    'scripts/run-backend-dev.cmd',
    'scripts/run_evaluation.py',
}

to_remove = []
for f in all_files:
    if any(f.startswith(d) for d in KEEP_DIRS):
        if 'exports/' in f or f.startswith('backend/data/exports/'):
            to_remove.append(f)
        continue
    if f in KEEP_FILES or f in KEEP_SCRIPTS:
        continue
    # Skip data/processed OCR files (might be needed for RAG)
    if f.startswith('data/processed/') or f.startswith('data/documents/'):
        continue
    to_remove.append(f)

print(f"Files to remove ({len(to_remove)}):")
for f in sorted(to_remove):
    print(f"  {f}")

# Remove in batches of 20 to avoid path issues
import os
removed = 0
failed = []
for i in range(0, len(to_remove), 20):
    batch = to_remove[i:i+20]
    r = subprocess.run(['git', 'rm', '--cached', '--'] + batch, capture_output=True, text=True)
    if r.returncode == 0:
        removed += len(batch)
    else:
        # Try one by one
        for f in batch:
            r2 = subprocess.run(['git', 'rm', '--cached', '--', f], capture_output=True, text=True)
            if r2.returncode == 0:
                removed += 1
            else:
                failed.append(f)

print(f"\nRemoved: {removed}, Failed: {len(failed)}")
if failed:
    print("Failed files:", failed)
