import pymupdf
import sys
import os
import io

def extract_pdf_text(file_path):
    doc = pymupdf.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_pdf.py <path_to_pdf>")
        sys.exit(1)
    
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)
        
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print(extract_pdf_text(path))
