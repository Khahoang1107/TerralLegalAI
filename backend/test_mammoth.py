import mammoth
import re
import sys

def test_convert():
    try:
        with open("../data/uploaded/test_raw.docx", "rb") as f:
            result = mammoth.convert_to_html(f)
            print("HTML OUTPUT:")
            print(result.value)
    except FileNotFoundError:
        import os
        import glob
        files = glob.glob("../data/uploaded/*.docx")
        if files:
            with open(files[0], "rb") as f:
                result = mammoth.convert_to_html(f)
                print(f"HTML OUTPUT for {files[0]}:")
                print(result.value)
        else:
            print("No docx found in data/uploaded")

if __name__ == "__main__":
    test_convert()
