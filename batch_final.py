#!/usr/bin/env python3
"""Final batch: process remaining raw PDFs + fix misidentified files."""
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


def extract_text(pdf_path, max_pages=15):
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
        if m: y = m.group(2); return y if 1900 <= int(y) <= 2099 else None
        m = re.search(r'(?:©|Copyright)\s*((?:19|20)\d{2})', line)
        if m: y = m.group(1); return y if 2000 <= int(y) <= 2099 else None
    for line in lines[:30]:
        m = re.search(r'[\((]\s*((?:19|20)\d{2})\s*[\))]', line)
        if m: y = m.group(1); return y if 2000 <= int(y) <= 2099 else None
    doi = extract_doi(text)
    if doi:
        m = re.search(r'\.(20\d{2})', doi)
        if m: return m.group(1)
    for line in lines[:200]:
        m = re.search(r'\b(20[0-2]\d)\b', line)
        if m: y = m.group(1); return y if 2010 <= int(y) <= 2029 else None
    return "XXXX"


def extract_first_author(text):
    lines = text[:5000].split('\n')
    for line in lines[:200]:
        line = line.strip()
        if not line or len(line) < 10: continue
        if re.search(r'\b(?:and|&)\s+[A-Z][a-zà-ü\-]+\s+[A-Z]\.?(?:$|\s*\d)', line):
            parts = line.split(',')
            words = parts[0].strip().split()
            if words:
                name = re.sub(r'[^A-Za-zÀ-ü\-]', '', words[0])
                if len(name) > 1: return name
            break
        m = re.match(r'^([A-Z][a-zà-ü\-]+(?:\s+[A-Z][a-zà-ü\-]+)*)\s*(?:[A-Z]\.?\s*)?', line)
        if m and re.search(r'[.,]\s*\d', line):
            words = m.group(1).split()
            last = words[-1] if len(words) > 1 else words[0]
            last = re.sub(r'[^A-Za-zÀ-ü\-]', '', last)
            if last and len(last) > 1 and not re.search(r'(?:correspondence|email|abstract|introduction|summary|key\s*words)', line, re.IGNORECASE):
                return last
    for line in lines[:50]:
        m = re.match(r'^([A-Z][a-zà-ü\-]+(?:\s+[A-Z]\.?){0,2})\s*(?:PhD|MD|DDS|DVM|Dr|Prof)', line)
        if m:
            name = m.group(1).split()[0]
            if len(name) > 1: return name
        m = re.match(r'^([A-Z][a-zà-ü\-]+)\s+[A-Z]\.?\s*$', line)
        if m:
            last = m.group(1)
            if last.lower() not in ('the', 'and', 'for', 'from', 'with', 'that', 'this'): return last
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
        ll = line.lower()
        ctx = any(kw in ll for kw in ['©', 'copyright', 'published', 'volume', 'vol.', 'issn', 'www.'])
        for name, abbr in KNOWN_JOURNALS.items():
            if name.lower() in ll and (ctx or 'journal' in ll or len(name) > 12):
                return abbr
    return "Unknown"


def extract_news_keyword(text):
    lines = text.split('\n')
    skip = [r'^nature\s+reviews', r'^research\s+highlights', r'^volume',
            r'^\d+\s*\|', r'^www\.', r'^©', r'^nature', r'^editorial',
            r'^advertisement', r'^advertiser']
    title = None
    for line in lines[:30]:
        s = line.strip()
        if not s or len(s) < 10: continue
        if any(re.search(p, s, re.I) for p in skip): continue
        if re.match(r'^[A-Z][a-zA-Z\s\-:,/()]+$', s) and not s.endswith('.'):
            title = s; break
    if not title:
        for line in lines[:30]:
            s = line.strip()
            if len(s) > 15 and any(c.isupper() for c in s[:5]):
                if not any(re.search(p, s, re.I) for p in skip):
                    title = s; break
    if not title: return "News"
    stopwords = {'the','a','an','of','in','on','at','by','for','with','and','or',
                 'but','is','are','was','were','be','been','to','from','that','this',
                 'their','its','as','has','not','no','we','it','do','does','can','may','will'}
    words = re.findall(r"[A-Za-z][a-zA-Z0-9\-']*", title)
    content = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    if not content: return "News"
    return ''.join(w.capitalize() for w in content[:3])


def process_file(pdf_path):
    pdf_name = pdf_path.name
    text = extract_text(pdf_path)
    if not text.strip():
        print(f"   [SKIP] empty")
        return None

    doi = extract_doi(text)
    head = text[:2000].lower()

    # Detect Nature news (d41586) by content
    if re.search(r'nature\s*\|?\s*vol', head) and re.search(r'(technology\s*&\s*tools|news\s+feature)', head):
        journal = 'NatureNews'
        year = extract_year(text)
        kw = extract_news_keyword(text)
        return f"{journal}{year}-news-{kw}.pdf"

    # Detect advertorial (d43747) by content
    if 'advertisement feature' in head or 'advertiser retains sole responsibility' in head:
        journal = 'NatureAsia'
        year = extract_year(text) or "2024"
        kw = extract_news_keyword(text)
        return f"{journal}{year}-news-{kw}.pdf"

    # Detect news by DOI
    if doi:
        doi_l = doi.lower()
        if doi_l.startswith('10.1038/d41573'):
            year = extract_year(text) or "2024"
            kw = extract_news_keyword(text)
            return f"NatRevDrugDisc{year}-news-{kw}.pdf"
        if doi_l.startswith('10.1038/d41586'):
            year = extract_year(text) or "2024"
            kw = extract_news_keyword(text)
            return f"NatureNews{year}-news-{kw}.pdf"
        if doi_l.startswith('10.1038/d43747'):
            year = extract_year(text) or "2024"
            kw = extract_news_keyword(text)
            return f"NatureAsia{year}-news-{kw}.pdf"

    # Standard article/review
    author = extract_first_author(text)
    year = extract_year(text)
    journal = extract_journal(text)
    if not year: year = "XXXX"
    j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
    if not author: author = "Unknown"
    return f"{author}{year}_{j_short}.pdf"


def main():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    processed = 0
    renamed = 0
    errors = 0

    total = len(pdf_files)
    for i, pdf_path in enumerate(pdf_files, 1):
        pdf_name = pdf_path.name

        # Skip already-named files
        if re.match(r'^[A-Z][a-zà-ü]+20\d{2}_[A-Za-z0-9]+', pdf_name):
            continue
        if re.match(r'^[A-Za-z]+20\d{2}-news-', pdf_name):
            continue
        if re.match(r'^[A-Z][a-z]+\d{4}_', pdf_name):
            continue

        print(f"[{i}/{total}] {pdf_name}")

        try:
            text = extract_text(pdf_path)
        except Exception as e:
            print(f"   [ERROR] extract: {e}")
            errors += 1
            continue

        if not text.strip():
            print(f"   [SKIP] empty")
            continue

        doi = extract_doi(text)
        head = text[:2000].lower()

        # Detect Nature news (d41586)
        if re.search(r'nature\s*\|?\s*vol', head) and re.search(r'(technology\s*&\s*tools|news\s+feature)', head):
            journal = 'NatureNews'
            year = extract_year(text)
            kw = extract_news_keyword(text)
            new_name = f"{journal}{year}-news-{kw}.pdf"
        # Advertorial
        elif 'advertisement feature' in head or 'advertiser retains sole responsibility' in head:
            journal = 'NatureAsia'
            year = extract_year(text) or "2024"
            kw = extract_news_keyword(text)
            new_name = f"{journal}{year}-news-{kw}.pdf"
        # News by DOI
        elif doi:
            doi_l = doi.lower()
            if doi_l.startswith('10.1038/d41573'):
                year = extract_year(text) or "2024"
                kw = extract_news_keyword(text)
                new_name = f"NatRevDrugDisc{year}-news-{kw}.pdf"
            elif doi_l.startswith('10.1038/d41586'):
                year = extract_year(text) or "2024"
                kw = extract_news_keyword(text)
                new_name = f"NatureNews{year}-news-{kw}.pdf"
            elif doi_l.startswith('10.1038/d43747'):
                year = extract_year(text) or "2024"
                kw = extract_news_keyword(text)
                new_name = f"NatureAsia{year}-news-{kw}.pdf"
            else:
                author = extract_first_author(text)
                year = extract_year(text) or "XXXX"
                journal = extract_journal(text)
                j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
                new_name = f"{author}{year}_{j_short}.pdf"
        else:
            author = extract_first_author(text)
            year = extract_year(text) or "XXXX"
            journal = extract_journal(text)
            j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal != "Unknown" else "Unknown"
            new_name = f"{author}{year}_{j_short}.pdf"

        target_path = PDF_DIR / new_name
        base_stem = new_name.replace(".pdf", "")

        # Save extracted text
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        notes_path = NOTES_DIR / f"{base_stem}_extracted.txt"
        if not notes_path.exists():
            notes_path.write_text(text[:50000], encoding='utf-8')

        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        extract_path = EXTRACT_DIR / f"{time.strftime('%Y-%m-%d')}.txt"
        with open(extract_path, "a", encoding="utf-8") as f:
            f.write(f"===== {base_stem}.pdf (from {pdf_name}) =====\n\n")
            f.write(text[:50000])
            f.write("\n\n=====\n\n")

        # Rename
        if pdf_path.name != new_name:
            if target_path.exists():
                alt = new_name.replace('.pdf', '_dup.pdf')
                pdf_path.rename(PDF_DIR / alt)
                print(f"   -> {alt} (dup)")
            else:
                pdf_path.rename(target_path)
                print(f"   -> {new_name}")
            renamed += 1
        else:
            print(f"   이름 동일")

        processed += 1

    print(f"\n=== Done ===")
    print(f"Processed: {processed}")
    print(f"Renamed: {renamed}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
