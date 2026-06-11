"""Inspect Vaibhav ChatGPT PDF formatting to find turn markers."""
import fitz, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

doc = fitz.open('d:/StartitUP/Sangillence/Synergy/gold_standard/chats/Vaibhav_ChatGPT.pdf')
print(f"Pages: {len(doc)}")

# Check pages 0,4,9 for formatting structure
for page_idx in [0, 4, 9, 20]:
    if page_idx >= len(doc):
        continue
    page = doc[page_idx]
    print(f"\n=== PAGE {page_idx+1} ===")
    blocks = page.get_text('dict')['blocks']
    for b in blocks[:15]:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            for span in line['spans']:
                size = round(span['size'], 1)
                bold = 'Bold' in span['font'] or (span['flags'] & 16)
                italic = 'Italic' in span['font'] or (span['flags'] & 2)
                txt = span['text'][:90]
                if txt.strip():
                    print(f"  sz={size:4.1f} bold={bold} ital={italic} | {txt}")
