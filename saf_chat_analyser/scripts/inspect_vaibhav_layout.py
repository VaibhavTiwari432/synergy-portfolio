"""Check x/y layout of blocks to find ChatGPT turn boundary markers."""
import fitz, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

doc = fitz.open('d:/StartitUP/Sangillence/Synergy/gold_standard/chats/Vaibhav_ChatGPT.pdf')

# Dump first 3 pages with full block bboxes
for page_idx in range(min(6, len(doc))):
    page = doc[page_idx]
    print(f"\n=== PAGE {page_idx+1} (w={page.rect.width:.0f} h={page.rect.height:.0f}) ===")
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" not in b:
            continue
        x0, y0, x1, y1 = b["bbox"]
        first_text = ""
        for line in b["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    first_text = span["text"][:70]
                    break
            if first_text:
                break
        print(f"  x0={x0:5.1f} y0={y0:5.1f} x1={x1:5.1f} w={x1-x0:5.1f} | {first_text}")

# Also: check page 5 which starts with a human turn (known from earlier)
print("\n\n=== PAGE 5 BLOCK DETAIL ===")
page = doc[4]
blocks = page.get_text("dict")["blocks"]
for b in blocks[:8]:
    if "lines" not in b:
        continue
    x0, y0, x1, y1 = b["bbox"]
    text = " ".join(
        sp["text"] for line in b["lines"] for sp in line["spans"]
    ).strip()[:100]
    print(f"  bbox=({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}) | {text}")
