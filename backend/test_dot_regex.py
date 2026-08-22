import re
PLACEHOLDER = "BLANKZONE_PLACEHOLDER"
texts = [
    "Kính gửi : ................................... (1)",
    "Kính gửi : . . . . . . . . . . . . . (1)",
    "Mr. A. B. C. is here.",
    "Tên: _ _ _ _ _ _ _",
    "Địa chỉ: - - - - - -"
]

for t in texts:
    # Match 3 or more dots, optionally separated by spaces
    out = re.sub(r'(?:\.(?:&nbsp;| )*){3,}', PLACEHOLDER, t)
    # Match 3 or more underscores, optionally separated by spaces
    out = re.sub(r'(?:_(?:&nbsp;| )*){3,}', PLACEHOLDER, out)
    out = re.sub(r'(?:-(?:&nbsp;| )*){5,}', PLACEHOLDER, out)
    print("IN:", t)
    print("OUT:", out)
