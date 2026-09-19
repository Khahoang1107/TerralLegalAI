import json
log_path = r'C:\Users\ADMIN\.gemini\antigravity-ide\brain\8f2251fb-2f0d-4b31-a516-b62002594008\.system_generated\logs\transcript_full.jsonl'
diffs = []
with open(log_path, encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get('type') == 'CODE_ACTION' and 'page.tsx' in data.get('content', '') and '[diff_block_start]' in data.get('content', ''):
                diffs.append(data['content'])
        except Exception as e:
            pass
with open('d:/TerraLegalAI/page_tsx_diffs.txt', 'w', encoding='utf-8') as f:
    f.write('\n\n================\n\n'.join(diffs))
