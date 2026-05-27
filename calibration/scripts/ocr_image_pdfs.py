"""
ocr_image_pdfs.py

OCR extraction for image-only PDFs (gc-004, gc-012, gc-013).
Pipeline: PyMuPDF -> 300 DPI PNG -> Tesseract -> turn parser -> gc-*.json

Run from repo root:
    python calibration/scripts/ocr_image_pdfs.py

Never touches annotation fields. Adds `"source": "ocr"` to each turn.
Pages below 70% Tesseract confidence are flagged with a WARNING prefix.
"""

import io
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

GOLD_DIR = Path(__file__).resolve().parents[2] / "gold_standard" / "chats"
REPORT_DIR = Path(__file__).resolve().parents[1] / "audit"
CONF_WARN_THRESHOLD = 70

TARGETS = [
    ("gc-004", "Kartikeya_ChatGPT.pdf"),
    ("gc-012", "Bharath_ChatGPT.pdf"),
    ("gc-013", "Jay_ChatGPT1.pdf"),
]


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def ocr_pdf(pdf_path: Path) -> tuple[str, list[dict]]:
    """
    Returns (full_text, page_reports).
    page_reports: [{page: int, conf: float, flagged: bool}]
    """
    doc = fitz.open(str(pdf_path))
    pages_text: list[str] = []
    page_reports: list[dict] = []

    print(f"  {pdf_path.name}: {len(doc)} pages, OCR at 300 DPI ...")

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        conf_values = [int(c) for c in data["conf"] if str(c) != "-1"]
        avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0.0

        text = pytesseract.image_to_string(img, config="--psm 1")

        flagged = avg_conf < CONF_WARN_THRESHOLD
        page_reports.append({"page": i + 1, "conf": round(avg_conf, 1), "flagged": flagged})

        if flagged:
            pages_text.append(f"[WARNING: page {i+1} OCR confidence {avg_conf:.0f}% < {CONF_WARN_THRESHOLD}%]\n{text}")
            print(f"    page {i+1}: conf={avg_conf:.0f}%  *** LOW CONFIDENCE ***")
        else:
            pages_text.append(text)
            if (i + 1) % 10 == 0:
                print(f"    page {i+1}/{len(doc)}: conf={avg_conf:.0f}%")

    return "\n".join(pages_text), page_reports


# ---------------------------------------------------------------------------
# Turn parsing (mirrors extract_turns.ts logic)
# ---------------------------------------------------------------------------

def strip_artifacts(text: str) -> str:
    text = re.sub(r"\d+/\d+/\d{2,4},?\s+\d+:\d+\s+[AP]M\s+[^\n]+\nhttps?://[^\n]+", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"Stopped thinking[^\n]*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


AI_OPENER = re.compile(
    r"^(Sure|Great|Alright|Absolutely|Of course|Here'?s|Let me|I'll|I will|"
    r"I can|I've|Happy to|Understood|Okay|Yes[,!]|Got it)",
    re.IGNORECASE,
)


def heuristic_split(text: str) -> list[dict]:
    """Alternating-paragraph heuristic, same logic as extract_turns.ts."""
    clean = strip_artifacts(text)
    raw_blocks = [b.strip() for b in re.split(r"\n{2,}", clean) if len(b.strip()) > 10]

    # Merge very short blocks into the next
    merged: list[str] = []
    buf = ""
    for block in raw_blocks:
        if buf and len(buf) < 80:
            buf += "\n\n" + block
        else:
            if buf:
                merged.append(buf)
            buf = block
    if buf:
        merged.append(buf)

    if not merged:
        return []

    # Determine first role
    first_is_ai = bool(AI_OPENER.match(merged[0])) and len(merged[0]) > 300

    turns = []
    for i, content in enumerate(merged):
        role = "assistant" if (i + (1 if first_is_ai else 0)) % 2 == 1 else "user"
        turns.append({
            "role": role,
            "content": content,
            "turn_index": i,
            "timestamp_ms": None,
            "source": "ocr",
        })

    return turns


# ---------------------------------------------------------------------------
# Write to gc-*.json
# ---------------------------------------------------------------------------

def update_json(chat_id: str, turns: list[dict]) -> None:
    json_path = GOLD_DIR / f"{chat_id}.json"
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    raw["turns"] = turns
    json_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Sanity-check printer
# ---------------------------------------------------------------------------

def print_sample(chat_id: str, turns: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(f"  {chat_id} — {len(turns)} turns  (first 5 / last 3)")
    print(f"{'='*60}")
    sample = turns[:5] + (turns[-3:] if len(turns) > 5 else [])
    shown = set()
    for t in sample:
        idx = t["turn_index"]
        if idx in shown:
            continue
        shown.add(idx)
        sep = "---" if idx >= len(turns) - 3 else "..."
        flag = " [LOW-CONF]" if "[WARNING:" in t["content"] else ""
        print(f"  [{idx:>3}] {t['role']:<9}{flag}")
        print("       " + t["content"][:120].replace("\n", " ") + ("..." if len(t["content"]) > 120 else ""))
    print()


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(results: list[dict]) -> None:
    lines = ["# OCR Extraction Report\n"]
    for r in results:
        lines.append(f"## {r['chat_id']}\n")
        lines.append(f"- PDF: {r['pdf']}")
        lines.append(f"- Pages: {r['pages']}")
        lines.append(f"- Turns extracted: {r['turns']}")
        lines.append(f"- Low-confidence pages (< {CONF_WARN_THRESHOLD}%): {r['low_conf_pages']}\n")
        if r["page_reports"]:
            lines.append("| Page | Confidence | Flag |")
            lines.append("|------|-----------|------|")
            for pr in r["page_reports"]:
                flag = "*** LOW ***" if pr["flagged"] else ""
                lines.append(f"| {pr['page']} | {pr['conf']}% | {flag} |")
        lines.append("")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "ocr_extraction_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to calibration/audit/ocr_extraction_report.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    report_results = []

    for chat_id, pdf_name in TARGETS:
        pdf_path = GOLD_DIR / pdf_name
        if not pdf_path.exists():
            print(f"{chat_id}: PDF not found at {pdf_path}")
            continue

        print(f"\n[{chat_id}] {pdf_name}")
        full_text, page_reports = ocr_pdf(pdf_path)
        turns = heuristic_split(full_text)

        low_conf = [p for p in page_reports if p["flagged"]]
        print(f"  => {len(turns)} turns extracted, {len(low_conf)} low-confidence pages")

        update_json(chat_id, turns)

        report_results.append({
            "chat_id": chat_id,
            "pdf": pdf_name,
            "pages": len(page_reports),
            "turns": len(turns),
            "low_conf_pages": len(low_conf),
            "page_reports": page_reports,
        })

        print_sample(chat_id, turns)

    write_report(report_results)


if __name__ == "__main__":
    main()
