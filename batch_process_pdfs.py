#!/usr/bin/env python3
"""Batch process ALL unprocessed PDFs in ko/pdf/:
   - Article: AuthorYear_Journal.pdf
   - Review:  AuthorYear_Journal-review.pdf
   - News:    JournalYear-news-Keyword.pdf
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

# News-type journal DOI prefixes
NEWS_DOI_PREFIXES = {
    "10.1038/d41573": "NatRevDrugDisc",
    "10.1038/d41586": "NatureNews",
    "10.1038/d43747": "NatureAsia",
}


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


def detect_news(doi):
    """Check if DOI indicates a news-type article."""
    if doi:
        doi_lower = doi.lower()
        for prefix in NEWS_DOI_PREFIXES:
            if doi_lower.startswith(prefix):
                return NEWS_DOI_PREFIXES[prefix]
    return None


def extract_news_keyword(text):
    """Extract keyword from news article title for filename."""
    lines = text.split('\n')
    # Look for title line (short, capitalized, not header/boilerplate)
    skip_patterns = [
        r'^nature\s+reviews', r'^research\s+highlights', r'^volume',
        r'^\d+\s*\|', r'^www\.', r'^©', r'^nature', r'^editorial',
        r'^news\s+&\s+views', r'^in\s+brief', r'^an\s+editorial',
    ]
    title = None
    for line in lines[:30]:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        # Skip known non-title lines
        if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
            continue
        # Title should have mixed case, end without period typically
        if re.match(r'^[A-Z][a-zA-Z\s\-:,/()]+$', line) and not line.endswith('.'):
            title = line
            break

    if not title:
        # Fallback: first line with meaningful content
        for line in lines[:30]:
            line = line.strip()
            if len(line) > 15 and any(c.isupper() for c in line[:5]):
                if not any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
                    title = line
                    break

    if not title:
        return "News"

    # Extract meaningful keywords from title
    stopwords = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
                 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'be', 'been',
                 'to', 'from', 'that', 'this', 'their', 'its', 'as', 'has',
                 'not', 'no', 'we', 'it', 'do', 'does', 'can', 'may', 'will'}

    # Take first 2-3 meaningful words
    words = re.findall(r"[A-Za-z][a-zA-Z0-9\-']*", title)
    content = [w for w in words if w.lower() not in stopwords and len(w) > 2]

    if not content:
        return "News"

    # Combine up to 3 words into CamelCase
    kw = ''.join(w.capitalize() for w in content[:3])
    return kw


def detect_preprint(text):
    """bioRxiv/medRxiv preprint detection."""
    head = text[:3000].lower()
    doi = extract_doi(text)
    if doi:
        doi_lower = doi.lower()
        if 'biorxiv' in doi_lower:
            return 'bioRxiv'
        if 'medrxiv' in doi_lower:
            return 'medRxiv'
    if re.search(r'\b(bioRxiv|biorxiv|bioRχiv)\b', head):
        return 'bioRxiv'
    if re.search(r'\b(medRxiv|medrxiv)\b', head):
        return 'medRxiv'
    return None


def detect_review(text):
    """Detect review articles."""
    head = text[:3000]
    review_patterns = [
        r'\bREVIEW\s+ARTICLE\b', r'\bReview\s+Article\b',
        r'\bVIEWPOINT\b', r'\bViewpoint\b',
        r'\bMINIREVIEW\b', r'\bMinireview\b', r'\bMini-?Review\b',
        r'\bPERSPECTIVE\b',
    ]
    for pat in review_patterns:
        if re.search(pat, head):
            return True
    natural_patterns = [
        r'\bthis review\b', r'\bwe review\b', r'\bI review\b',
        r'\breview summarizes\b', r'\breview highlights\b',
        r'\bthis article reviews\b', r'\bhere,? we review\b',
    ]
    for pat in natural_patterns:
        if re.search(pat, head, re.IGNORECASE):
            return True
    return False


def suggested_name(text, pdf_name):
    """Generate proper filename based on document type."""
    doi = extract_doi(text)

    # Check for preprint first
    preprint = detect_preprint(text)
    if preprint:
        author = extract_first_author(text)
        year = extract_year(text)
        is_review = detect_review(text)
        suffix = "-review" if is_review else ""
        return f"{author}{year}_{preprint}{suffix}.pdf", is_review

    # Check for news
    news_journal = detect_news(doi)
    if news_journal:
        year = extract_year(text)
        keyword = extract_news_keyword(text)
        return f"{news_journal}{year}-news-{keyword}.pdf", False

    # Detect news by content keywords (for non-DOI prefixed news)
    head = text[:2000].lower()
    if re.search(r'\bresearch highlights\b', head) or re.search(r'\bnews\s+&\s+views\b', head):
        journal = extract_journal(text)
        j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
        year = extract_year(text)
        keyword = extract_news_keyword(text)
        return f"{j_short}{year}-news-{keyword}.pdf", False

    # Regular article/review
    author = extract_first_author(text)
    year = extract_year(text)
    journal = extract_journal(text)
    is_review = detect_review(text)

    if not author:
        base = Path(pdf_name).stem
        m = re.match(r'^([A-Za-z]+)(20\d{2})', base)
        if m:
            author = m.group(1).capitalize()
            year = year or m.group(2)
        else:
            author = "Unknown"
    if not year:
        year = "XXXX"
    j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
    suffix = "-review" if is_review else ""
    return f"{author}{year}_{j_short}{suffix}.pdf", is_review


def is_already_named(fname):
    """Check if PDF is already in a proper naming format."""
    # Article/review: AuthorYear_Journal.pdf or AuthorYear_Journal_Keyword.pdf
    if re.match(r'^[A-Z][a-zà-ü]+20\d{2}_[A-Za-z0-9]+', fname):
        return True
    # News: JournalYear-news-Keyword.pdf
    if re.match(r'^[A-Za-z]+20\d{2}-news-', fname):
        return True
    return False


def save_extract(pdf_name, target_stem, text, date_str=None):
    """Save extracted text to notes/ and extract/."""
    if date_str is None:
        date_str = time.strftime("%Y-%m-%d")

    # Save to notes/
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    notes_path = NOTES_DIR / f"{target_stem}_extracted.txt"
    if not notes_path.exists():
        notes_path.write_text(text[:50000], encoding='utf-8')

    # Save to extract/
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    extract_path = EXTRACT_DIR / f"{date_str}.txt"
    with open(extract_path, "a", encoding="utf-8") as f:
        f.write(f"===== {target_stem}.pdf (from {pdf_name}) =====\n\n")
        f.write(text[:50000])
        f.write("\n\n=====\n\n")


def main():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    total = len(pdf_files)
    print(f"PDF 총 {total}개\n")

    already_ok = 0
    processed = 0
    renamed = 0
    skipped = 0
    errors = 0
    news_count = 0
    review_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        pdf_name = pdf_path.name

        # Skip if already in proper format
        if is_already_named(pdf_name):
            already_ok += 1
            continue

        print(f"[{i}/{total}] {pdf_name}")

        # Extract text
        t0 = time.time()
        try:
            text = extract_text(pdf_path)
        except Exception as e:
            print(f"   [ERROR] {e}")
            errors += 1
            continue
        dt = time.time() - t0

        if not text.strip():
            print(f"   [SKIP] 빈 텍스트")
            skipped += 1
            continue

        text_preview = text[:200]
        print(f"   {len(text):,} chars ({dt:.1f}s): {text_preview[:80]}...")

        # Generate target name
        target_name, is_review = suggested_name(text, pdf_name)

        # Check if news
        doi = extract_doi(text)
        is_news = detect_news(doi) is not None
        if is_news:
            news_count += 1

        target_stem = target_name.replace(".pdf", "")

        # Save extracted text
        save_extract(pdf_name, target_stem, text)

        # Rename PDF
        target_path = PDF_DIR / target_name
        if pdf_path.name != target_name:
            if target_path.exists():
                print(f"   [WARN] 대상 존재: {target_name} → dup")
                alt_name = target_name.replace('.pdf', '_dup.pdf')
                pdf_path.rename(PDF_DIR / alt_name)
                print(f"   이름 변경: {pdf_name} -> {alt_name}")
                renamed += 1
            else:
                pdf_path.rename(target_path)
                print(f"   이름 변경: {pdf_name} -> {target_name}")
                renamed += 1
        else:
            print(f"   이름: 이미 올바름")

        # Log
        log_path = NOTES_DIR / "00_processing_log.md"
        log_path.parent.mkdir(exist_ok=True)
        if not log_path.exists():
            log_path.write_text("# Processing Log\n\n| # | PDF | Status |\n|---|-----|--------|\n")
        label = "NEWS" if is_news else ("REVIEW" if is_review else "ARTICLE")
        status = f"Extracted+Renamed [{label}]"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"| [BATCH] {target_name} (from {pdf_name}) | - | [DONE] {status} |\n")

        if is_review and not is_news:
            review_count += 1
        processed += 1
        print()

    print(f"\n=== 완료 ===")
    print(f"이미 올바름: {already_ok}")
    print(f"처리됨: {processed} (뉴스: {news_count}, 리뷰: {review_count})")
    print(f"이름변경: {renamed}")
    print(f"건너뜀: {skipped}")
    print(f"오류: {errors}")


if __name__ == "__main__":
    main()
