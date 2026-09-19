with open('backend/app/api/v1/forms.py', 'r', encoding='utf-8') as f:
    text = f.read()
    print('Total triple quotes:', text.count('"""'))
