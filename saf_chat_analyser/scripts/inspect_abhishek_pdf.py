"""Inspect Abhishek_1.pdf: page count, format, and block x0 layout."""
import fitz, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

doc = fitz.open('d:/StartitUP/Sangillence/Synergy/gold_standard/chats/Abhishek_1.pdf')
print(f"Pages: {len(doc)}")

# Check pages 0,1,2 for role-marker patterns
for page_idx in range(min(5, len(doc))):
    page = doc[page_idx]
    print(f"\n=== PAGE {page_idx+1} ===")
    blocks = page.get_text("dict")["blocks"]
    for b in blocks[:20]:
        if "lines" not in b:
            continue
        x0, y0, x1, y1 = b["bbox"]
        first_text = ""
        for line in b["lines"]:
            for span in line["spans"]:
                bold = bool('Bold' in span['font'] or (span['flags'] & 16))
                if span["text"].strip():
                    first_text = span["text"][:80]
                    sz = span["size"]
                    break
            if first_text:
                break
        if first_text:
            print(f"  x0={x0:5.1f} y0={y0:5.1f} sz={sz:.1f} bold={bold} | {first_text}")
