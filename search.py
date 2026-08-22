import os
def search_dir(d):
    for root, dirs, files in os.walk(d):
        if 'node_modules' in root or '.git' in root or '.next' in root:
            continue
        for file in files:
            if file.endswith(('.tsx', '.ts', '.js', '.jsx')):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        if 'Kiểm tra dữ liệu' in f.read():
                            print(f'Found in: {path}')
                except:
                    pass
search_dir(r"d:\TerraLegalAI\frontend")
