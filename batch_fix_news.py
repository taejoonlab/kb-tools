#!/usr/bin/env python3
"""Fix news PDF naming and process remaining unprocessed PDFs."""
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

# News detection by filename pattern
NEWS_BY_FILENAME = {
    'd41573': 'NatRevDrugDisc',
    'd41586': 'NatureNews',
    'd43747': 'NatureAsia',
}

# News detection by DOI prefix  
NEWS_BY_DOI = {
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
        m = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+((?:19|20)\d{2}))', line)
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
            if last and len(last) > 1:
                if not re.search(r'(?:correspondence|email|abstract|introduction|summary|key\s*words)', line, re.IGNORECASE):
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


def detect_news_by_filename(pdf_name):
    """Detect news by filename prefix."""
    for prefix, journal in NEWS_BY_FILENAME.items():
        if pdf_name.startswith(prefix):
            return journal
    return None


def detect_news_by_doi(text):
    """Detect news by DOI prefix."""
    doi = extract_doi(text)
    if doi:
        doi_lower = doi.lower()
        for prefix, journal in NEWS_BY_DOI.items():
            if doi_lower.startswith(prefix):
                return journal
    return None


def extract_news_keyword(text):
    """Extract keyword from news article title."""
    lines = text.split('\n')
    skip_patterns = [
        r'^nature\s+reviews', r'^research\s+highlights', r'^volume',
        r'^\d+\s*\|', r'^www\.', r'^©', r'^nature', r'^editorial',
        r'^advertisement', r'^advertiser', r'^news\s+&\s+views', r'^in\s+brief',
    ]
    title = None
    for line in lines[:30]:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
            continue
        if re.match(r'^[A-Z][a-zA-Z\s\-:,/()]+$', line) and not line.endswith('.'):
            title = line
            break
    if not title:
        for line in lines[:30]:
            line = line.strip()
            if len(line) > 15 and any(c.isupper() for c in line[:5]):
                if not any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
                    title = line
                    break
    if not title:
        return "News"

    stopwords = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
                 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'be', 'been',
                 'to', 'from', 'that', 'this', 'their', 'its', 'as', 'has',
                 'not', 'no', 'we', 'it', 'do', 'does', 'can', 'may', 'will'}
    words = re.findall(r"[A-Za-z][a-zA-Z0-9\-']*", title)
    content = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    if not content:
        return "News"
    kw = ''.join(w.capitalize() for w in content[:3])
    return kw


def is_news_pdf(pdf_name):
    """Check if filename indicates a news PDF."""
    for prefix in NEWS_BY_FILENAME:
        if pdf_name.startswith(prefix):
            return True
    return False


def is_already_named(fname):
    if re.match(r'^[A-Z][a-zà-ü]+20\d{2}_[A-Za-z0-9]+', fname):
        return True
    if re.match(r'^[A-Za-z]+20\d{2}-news-', fname):
        return True
    return False


def fix_news_pdfs():
    """Find and rename wrongly-named news PDFs."""
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    fixed = 0

    for pdf_path in pdf_files:
        pdf_name = pdf_path.name

        # Check if this looks like a misnamed news article
        # e.g., Nature2024-news-* (should be NatRevDrugDisc2024-news-*)
        # We need to look at the original PDF name... but it's been renamed!
        # So we need to check the extracted text to determine the source.

        # Actually, the news articles from d41573 source won't have a DOI.
        # Let me check if a PDF has "news-*" in name but wrong journal prefix.
        news_match = re.match(r'^([A-Za-z]+)(20\d{2})-news-(.+)\.pdf$', pdf_name)
        if news_match:
            journal = news_match.group(1)
            year = news_match.group(2)
            keyword = news_match.group(3)

            # Check if this journal is one of the allowed news journals
            allowed = set(NEWS_BY_FILENAME.values())
            if journal not in allowed:
                # Misnamed! Try to determine correct journal from text
                try:
                    text = extract_text(pdf_path)
                except:
                    continue

                # Check by filename pattern in text (look for "nature reviews drug discovery" etc.)
                head = text[:2000].lower()
                if 'nature reviews drug discovery' in head:
                    new_journal = 'NatRevDrugDisc'
                elif re.search(r'nature\s+[a-z]+\s+\d{4}', head):
                    # Could be Nature news - check for "nature" header
                    new_journal = 'NatureNews'
                else:
                    # Use DOI-based detection
                    doi_journal = detect_news_by_doi(text)
                    if not doi_journal:
                        continue
                    new_journal = doi_journal

                # Try to get actual year from text
                actual_year = extract_year(text)
                year = actual_year if actual_year != "XXXX" else year

                # Clean keyword (remove _dup suffix if present)
                kw_clean = re.sub(r'_dup$', '', keyword)

                new_name = f"{new_journal}{year}-news-{kw_clean}.pdf"
                if new_name != pdf_name:
                    new_path = PDF_DIR / new_name
                    if new_path.exists():
                        alt_name = new_name.replace('.pdf', '_dup.pdf')
                        pdf_path.rename(PDF_DIR / alt_name)
                        print(f"  FIXED (dup): {pdf_name} -> {alt_name}")
                    else:
                        pdf_path.rename(new_path)
                        print(f"  FIXED: {pdf_name} -> {new_name}")
                    fixed += 1

    print(f"\nFixed {fixed} misnamed news PDFs")

    # Now also check for PDFs with "Research highlights" content
    # that were not caught as news
    for pdf_path in pdf_files:
        pdf_name = pdf_path.name
        if is_already_named(pdf_name) and '-news-' not in pdf_name:
            continue
        if '-news-' in pdf_name:
            continue  # already handled above

        try:
            text = extract_text(pdf_path, max_pages=5)
        except:
            continue
        if not text.strip():
            continue

        head = text[:2000].lower()
        # Check if it's a d41573-type news article by filename prefix?
        # No - we can't determine source from renamed file.
        # But we can check content for news indicators
        if ('research highlights' in head or 'news & analysis' in head) and 'news & views' in head:
            doi = extract_doi(text)
            if doi and any(doi.lower().startswith(p) for p in ['10.1038/d41573', '10.1038/d41586']):
                print(f"  [MISSED NEWS] {pdf_name} - check manually")

    return fixed


def process_remaining():
    """Process remaining unprocessed PDFs."""
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    processed = 0
    renamed = 0
    errors = 0

    for pdf_path in pdf_files:
        pdf_name = pdf_path.name

        # Skip already-named files
        if is_already_named(pdf_name):
            continue

        # Check if file still starts with a raw Springer/Nature pattern
        if not re.match(r'^s\d+', pdf_name) and not re.match(r'^science\.', pdf_name) and \
           not re.match(r'^srep\d+', pdf_name) and not pdf_name.startswith('spanos') and \
           not pdf_name.startswith('strum') and not pdf_name.startswith('tanaka') and \
           not pdf_name.startswith('vandenBerg') and not pdf_name.startswith('williamson'):
            continue  # not a raw file

        print(f"[PROCESS] {pdf_name}")

        try:
            text = extract_text(pdf_path)
        except Exception as e:
            print(f"   [ERROR] {e}")
            errors += 1
            continue

        if not text.strip():
            print(f"   [SKIP] empty text")
            continue

        # Generate target name
        doi = extract_doi(text)

        # Check for news by DOI
        news_journal = detect_news_by_doi(text)
        if news_journal:
            year = extract_year(text)
            keyword = extract_news_keyword(text)
            target_name = f"{news_journal}{year}-news-{keyword}.pdf"
        elif pdf_name.startswith('spanos') or pdf_name.startswith('tanaka') or \
             pdf_name.startswith('strum') or pdf_name.startswith('williamson') or \
             pdf_name.startswith('vandenBerg'):
            # These have human-readable names - use standard article detection
            author = extract_first_author(text)
            year = extract_year(text)
            journal = extract_journal(text)
            if not author:
                author = re.sub(r'[^A-Za-z]', '', pdf_name.split('et-al')[0].split('-')[0].split('_')[0].capitalize()) or "Unknown"
            if not year:
                year = "XXXX"
            j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
            target_name = f"{author}{year}_{j_short}.pdf"
        else:
            # Standard article processing
            author = extract_first_author(text)
            year = extract_year(text)
            journal = extract_journal(text)
            if not author:
                author = "Unknown"
            if not year:
                year = "XXXX"
            j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
            target_name = f"{author}{year}_{j_short}.pdf"

        target_stem = target_name.replace(".pdf", "")
        target_path = PDF_DIR / target_name

        # Save extracted text
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        notes_path = NOTES_DIR / f"{target_stem}_extracted.txt"
        if not notes_path.exists():
            notes_path.write_text(text[:50000], encoding='utf-8')

        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        extract_path = EXTRACT_DIR / f"{time.strftime('%Y-%m-%d')}.txt"
        with open(extract_path, "a", encoding="utf-8") as f:
            f.write(f"===== {target_stem}.pdf (from {pdf_name}) =====\n\n")
            f.write(text[:50000])
            f.write("\n\n=====\n\n")

        # Rename
        if pdf_path.name != target_name:
            if target_path.exists():
                alt_name = target_name.replace('.pdf', '_dup.pdf')
                pdf_path.rename(PDF_DIR / alt_name)
                print(f"   이름 변경(dup): {pdf_name} -> {alt_name}")
            else:
                pdf_path.rename(target_path)
                print(f"   이름 변경: {pdf_name} -> {target_name}")
            renamed += 1

        processed += 1
        print()

    print(f"\n=== Remaining Processing Complete ===")
    print(f"처리됨: {processed}")
    print(f"이름변경: {renamed}")
    print(f"오류: {errors}")


def main():
    print("=== Step 1: Fix misnamed news PDFs ===")
    fix_news_pdfs()

    print("\n=== Step 2: Process remaining raw PDFs ===")
    process_remaining()


if __name__ == "__main__":
    main()
