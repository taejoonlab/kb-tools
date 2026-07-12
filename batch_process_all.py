#!/usr/bin/env python3
"""401개 PDF 전체 일괄 처리: 텍스트 추출 + 자동 이름 생성 + 이름 변경 + extract 저장
CrossRef API 없이 DOI prefix map + regex 로컬 처리 (빠름)
"""
import sys, os, re, json, time
from pathlib import Path
try:
    import fitz
except ImportError:
    print("pip install pymupdf")
    sys.exit(1)

_VAULT = Path(__file__).parent.parent
PDF_DIR = _VAULT / "ko/pdf"
NOTES_DIR = PDF_DIR / "notes"
EXTRACT_DIR = _VAULT / "extract"

# Load DOI prefix journal map
_map_file = _VAULT / "tools" / "doi_journal_map.json"
if _map_file.exists():
    with open(_map_file) as f:
        _map_data = json.load(f)
    DOI_PREFIX_MAP = {}
    for cat, prefixes in _map_data.get("doi_prefix_map", {}).items():
        DOI_PREFIX_MAP.update(prefixes)
    KNOWN_JOURNALS = _map_data.get("known_journals", {})
else:
    DOI_PREFIX_MAP = {}
    KNOWN_JOURNALS = {}


def extract_text(pdf_path, max_pages=30):
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc[:max_pages]:
        text += page.get_text()
    doc.close()
    return text


def extract_doi(text):
    patterns = [
        r'(?:doi|DOI)\s*[:\s]*\s*(10\.\d{4,}/[^\s,;]+)',
        r'doi\.org/(10\.\d{4,}/[^\s,;]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).rstrip('.,/?')
    # bare DOI
    m = re.search(r'(10\.\d{4,}/[^\s,;\]]+)', text[:3000])
    if m:
        return m.group(1).rstrip('.,/?')
    return None


def extract_year(text):
    lines = text.split('\n')
    for line in lines[:30]:
        m = re.search(r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+((?:19|20)\d{2}))', line)
        if m:
            y = m.group(2)
            if 1900 <= int(y) <= 2099:
                return y
        m = re.search(r'(?:©|Copyright)\s*((?:19|20)\d{2})', line)
        if m:
            y = m.group(1)
            if 2000 <= int(y) <= 2099:
                return y
    for line in lines[:30]:
        m = re.search(r'[\((]\s*((?:19|20)\d{2})\s*[\))]', line)
        if m:
            y = m.group(1)
            if 2000 <= int(y) <= 2099:
                return y
    doi = extract_doi(text)
    if doi:
        m = re.search(r'\.(20\d{2})', doi)
        if m:
            return m.group(1)
    for line in lines[:200]:
        m = re.search(r'\b(20[0-2]\d)\b', line)
        if m:
            y = m.group(1)
            if 2010 <= int(y) <= 2029:
                return y
    return "XXXX"


def extract_first_author(text):
    lines = text[:5000].split('\n')
    for i, line in enumerate(lines[:200]):
        line = line.strip()
        if not line or len(line) < 10:
            continue
        # "and Last F., ..." 형태
        if re.search(r'\b(?:and|&)\s+[A-Z][a-zà-ü\-]+\s+[A-Z]\.?(?:$|\s*\d)', line):
            parts = line.split(',')
            raw = parts[0].strip()
            words = raw.split()
            if words:
                name = re.sub(r'[^A-Za-zÀ-ü\-]', '', words[0])
                if len(name) > 1:
                    return name
            break
        m = re.match(r'^([A-Z][a-zà-ü\-]+(?:\s+[A-Z][a-zà-ü\-]+)*)\s*(?:[A-Z]\.?\s*)?', line)
        if m and re.search(r'[.,]\s*\d', line):
            candidate = m.group(1)
            words = candidate.split()
            last = words[-1] if len(words) > 1 else words[0]
            last = re.sub(r'[^A-Za-zÀ-ü\-]', '', last)
            if last and len(last) > 1 and not re.search(r'(?:correspondence|email|abstract|introduction|summary|key\s*words)', line, re.IGNORECASE):
                return last
    for line in lines[:50]:
        m = re.match(r'^([A-Z][a-zà-ü\-]+(?:\s+[A-Z]\.?){0,2})\s*(?:PhD|MD|DDS|DVM|Dr|Prof)', line)
        if m:
            name = m.group(1).split()[0]
            if len(name) > 1:
                return name
        m = re.match(r'^([A-Z][a-zà-ü\-]+)\s+[A-Z]\.?\s*$', line)
        if m:
            last = m.group(1)
            if last.lower() not in ('the', 'and', 'for', 'from', 'with', 'that', 'this'):
                return last
    return "Unknown"


def extract_journal(text):
    doi = extract_doi(text)
    if doi:
        doi_lower = doi.lower()
        for prefix, abbr in DOI_PREFIX_MAP.items():
            if doi_lower.startswith(prefix) and abbr != '__HINDAWI__':
                return abbr
    lines = text[:3000].split('\n')
    for line in lines:
        line_lower = line.lower()
        has_context = any(kw in line_lower for kw in ['©', 'copyright', 'published', 'volume', 'vol.', 'issn', 'journal homepage', 'www.'])
        for name, abbr in KNOWN_JOURNALS.items():
            if name.lower() in line:
                if has_context or 'journal' in line_lower:
                    return abbr
                if len(name) > 12 and name.lower() not in ('development', 'nature', 'science'):
                    return abbr
    return "Unknown"


def detect_preprint(text):
    """bioRxiv/medRxiv preprint 여부 감지 (journal lookup 전에 실행)"""
    head = text[:3000].lower()
    # DOI 체크 (biorxiv/medrxiv prefix)
    doi = extract_doi(text)
    if doi:
        doi_lower = doi.lower()
        if 'biorxiv' in doi_lower:
            return 'bioRxiv'
        if 'medrxiv' in doi_lower:
            return 'medRxiv'
    # 텍스트 키워드 체크
    if re.search(r'\b(bioRxiv|biorxiv|bioRχiv)\b', head):
        return 'bioRxiv'
    if re.search(r'\b(medRxiv|medrxiv)\b', head):
        return 'medRxiv'
    if re.search(r'\bPREPRINT\b', head[:500]):
        if re.search(r'\b(bioRxiv|biorxiv)\b', head):
            return 'bioRxiv'
        if re.search(r'\b(medRxiv|medrxiv)\b', head):
            return 'medRxiv'
    return None


def suggested_name(text):
    # Preprint detection first (before journal lookup)
    preprint = detect_preprint(text)
    if preprint:
        author = extract_first_author(text)
        year = extract_year(text)
        return f"{author}{year}_{preprint}.pdf"
    
    author = extract_first_author(text)
    year = extract_year(text)
    journal = extract_journal(text)
    j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
    return f"{author}{year}_{j_short}.pdf"


def main():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    total = len(pdf_files)
    print(f"처리할 PDF: {total}개\n")

    skipped = 0
    processed = 0
    renamed = 0
    errors = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        pdf_name = pdf_path.name
        print(f"[{i}/{total}] {pdf_name}")

        # Extract text
        t0 = time.time()
        try:
            text = extract_text(pdf_path)
        except Exception as e:
            print(f"   [ERROR] 추출 실패: {e}")
            errors += 1
            continue
        t1 = time.time()
        print(f"   텍스트: {len(text):,} chars ({t1-t0:.1f}s)")

        if not text.strip():
            print(f"   [SKIP] 텍스트 없음")
            skipped += 1
            continue

        # Determine target name
        doi = extract_doi(text)
        target = suggested_name(text)
        target_stem = target.replace(".pdf", "")

        # Check if extracted text already exists
        notes_path = NOTES_DIR / f"{target_stem}_extracted.txt"
        already_done = notes_path.exists()

        if already_done:
            print(f"   [NOTE] 이미 추출됨: {target_stem}")
        else:
            NOTES_DIR.mkdir(parents=True, exist_ok=True)
            with open(notes_path, "w", encoding="utf-8") as f:
                f.write(text[:50000])
            print(f"   추출 저장: {notes_path.name}")

        # Save to extract/
        date_str = time.strftime("%Y-%m-%d")
        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        extract_path = EXTRACT_DIR / f"{date_str}.txt"
        with open(extract_path, "a", encoding="utf-8") as f:
            f.write(f"===== {target_stem}.pdf (from {pdf_name}) =====\n\n")
            f.write(text[:50000])
            f.write("\n\n=====\n\n")

        # Rename PDF
        target_path = PDF_DIR / target
        if pdf_path.name != target:
            if target_path.exists():
                print(f"   [WARN] 대상 존재: {target} → 건너뜀")
            else:
                pdf_path.rename(target_path)
                print(f"   이름 변경: {target}")
                renamed += 1
        else:
            print(f"   이름: 이미 올바름")

        # Update processing log
        log_path = NOTES_DIR / "00_processing_log.md"
        log_path.parent.mkdir(exist_ok=True)
        if not log_path.exists():
            log_path.write_text("# Processing Log\n\n| # | PDF | Status |\n|---|-----|--------|\n")
        with open(log_path, "a", encoding="utf-8") as f:
            status = "Extracted+Renamed" if not already_done else "NamedOnly(knew text)"
            f.write(f"| [BATCH] {target} (from {pdf_name}) | - | [DONE] {status} |\n")

        processed += 1
        print()

    print(f"\n=== 완료 ===")
    print(f"처리됨: {processed}")
    print(f"이름변경: {renamed}")
    print(f"건너뜀: {skipped}")
    print(f"오류: {errors}")


if __name__ == "__main__":
    main()
