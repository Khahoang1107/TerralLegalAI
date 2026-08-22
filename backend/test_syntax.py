import sys
try:
    import backend.app.api.v1.forms
    print("Syntax OK")
except Exception as e:
    print("Syntax Error:", e)
