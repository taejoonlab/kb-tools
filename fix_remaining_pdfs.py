#!/usr/bin/env python3
"""36개 충돌 PDF 재처리: 추출 + CrossRef API + preprint 감지 → 올바른 이름으로 rename"""
import sys, os, re, json, time, urllib.request, urllib.error
from pathlib import Path

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

try:
    import fitz
except ImportError:
    print("pip install pymupdf")
    sys.exit(1)


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
            return m.group(1).rstrip('.,/? ')
    m = re.search(r'(10\.\d{4,}/[^\s,;\]]+)', text[:3000])
    if m:
        return m.group(1).rstrip('.,/? ')
    return None


def crossref_lookup(doi):
    if not doi:
        return None, None, None
    try:
        url = f"https://api.crossref.org/works/{doi}"
        req = urllib.request.Request(url, headers={"User-Agent": "kb-taejoon/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        msg = data.get("message", {})
        authors = msg.get("author", [])
        first_author = None
        if authors:
            first = authors[0].get("family", "")
            if first and len(first) > 1:
                first_author = re.sub(r'[^A-Za-zÀ-ü\-]', '', first)
        year = None
        date_parts = msg.get("published-online", {}).get("date-parts", [[]])[0]
        if not date_parts:
            date_parts = msg.get("issued", {}).get("date-parts", [[]])[0]
        if date_parts:
            y = date_parts[0]
            if isinstance(y, int) and 1900 <= y <= 2099:
                year = str(y)
        journal = None
        short = msg.get("short-container-title", [])
        if short:
            journal = re.sub(r'[^A-Za-z0-9]', '', short[0])
        if not journal:
            full = msg.get("container-title", [])
            if full:
                j = full[0]
                j_abbr = re.sub(r'[^A-Za-z0-9]', '', j.split()[0] if j.split() else j)
                if len(j_abbr) > 3:
                    journal = j_abbr
        return first_author, year, journal
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None, None
        return None, None, None
    except Exception:
        return None, None, None


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


def detect_preprint(text):
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
    if re.search(r'\bPREPRINT\b', head[:500]):
        if re.search(r'\b(bioRxiv|biorxiv)\b', head):
            return 'bioRxiv'
        if re.search(r'\b(medRxiv|medrxiv)\b', head):
            return 'medRxiv'
    return None


def main():
    pdfs_to_process = [
        "2024.04.24.590951.full.pdf", "2026.02.01.703169.full.pdf", "2026.02.04.703868v1.full.pdf",
        "978-1-0716-4623-6.pdf", "978-1-0716-4985-5.pdf",
        "PIIS2666979X2500268X.pdf", "gkaf105.pdf", "journal.pgen.1011992.pdf",
        "plug-and-play-photo-initiated-crispr-cas12a-one-pot-nucleic-acid-detection-via-universal-repeat-rna-acylation-strategy.pdf",
        "proximity-labeling-reveals-rna-binding-proteins-associating-with-the-human-mitochondrial-import-receptor-tomm20.pdf",
        "s12943-025-02273-2.pdf", "s13059-026-03967-6_reference.pdf",
        "s41467-025-66896-1.pdf", "s41531-022-00278-y.pdf",
        "s41576-025-00869-4.pdf", "s41576-025-00872-9.pdf", "s41576-025-00889-0.pdf",
        "s41576-025-00893-4.pdf", "s41576-025-00898-z.pdf",
        "s41587-023-01685-z.pdf", "s41587-026-03002-w.pdf",
        "s41588-025-02168-4.pdf", "s41588-025-02420-x.pdf", "s41588-025-02424-7.pdf",
        "s41588-025-02443-4.pdf", "s41588-026-02506-0.pdf",
        "s41592-025-02845-6.pdf", "s41592-025-02976-w.pdf",
        "s42003-025-08443-8.pdf", "s42003-025-09157-7.pdf", "s42003-026-09722-8_reference.pdf",
        "s43018-022-00471-1.pdf", "s44319-025-00671-7.pdf",
        "sciadv.adu6505.pdf", "science.adt2760.pdf", "science.aea1272.pdf",
        "single-tube-dual-gene-detection-of-methicillin-resistant-staphylococcus-aureus-via-selective-trans-cleavage-preferences.pdf",
        "2026.01.06.697137.full.pdf", "2026.01.08.698354.full.pdf", "2026.01.08.698406.full.pdf",
    ]
    
    for i, pdf_name in enumerate(pdfs_to_process, 1):
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            print(f"[{i}/{len(pdfs_to_process)}] {pdf_name}: NOT FOUND")
            continue
        
        size = pdf_path.stat().st_size
        if size < 1000:
            print(f"[{i}/{len(pdfs_to_process)}] {pdf_name}: EMPTY ({size} bytes) → SKIP")
            continue
        
        print(f"[{i}/{len(pdfs_to_process)}] {pdf_name} ({size//1024}KB) ... ", end="", flush=True)
        
        # Extract text
        try:
            text = extract_text(pdf_path)
        except Exception as e:
            print(f"EXTRACT ERROR: {e}")
            continue
        
        if not text.strip():
            print("NO TEXT → SKIP")
            continue
        
        print(f"{len(text):,} chars", end="", flush=True)
        
        # Determine target name
        doi = extract_doi(text)
        
        # Preprint detection first
        preprint = detect_preprint(text)
        if preprint:
            author = extract_first_author(text)
            year = extract_year(text)
            target_stem = f"{author}{year}_{preprint}"
        elif doi:
            # Try CrossRef
            try:
                cr_author, cr_year, cr_journal = crossref_lookup(doi)
            except Exception:
                cr_author, cr_year, cr_journal = None, None, None
            
            if cr_author and cr_journal:
                author = cr_author
                year = cr_year or extract_year(text)
                journal = cr_journal
                target_stem = f"{author}{year}_{journal}"
            else:
                # Fall back to local extraction
                author = extract_first_author(text)
                year = extract_year(text)
                journal = None
                for prefix, abbr in DOI_PREFIX_MAP.items():
                    if doi.lower().startswith(prefix):
                        journal = abbr
                        break
                j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal else "Unknown"
                target_stem = f"{author}{year}_{j_short}"
        else:
            author = extract_first_author(text)
            year = extract_year(text)
            target_stem = f"{author}{year}_Unknown"
        
        # Check for conflicts
        txt_path = NOTES_DIR / f"{target_stem}_extracted.txt"
        if txt_path.exists():
            print(f" → {target_stem} (EXISTS)")
            # Still rename the PDF if target PDF doesn't exist
            target_pdf = PDF_DIR / f"{target_stem}.pdf"
            if not target_pdf.exists():
                pdf_path.rename(target_pdf)
                print(f"   PDF renamed: {target_stem}.pdf")
            continue
        
        # Save extracted text
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(text[:50000], encoding='utf-8')
        
        # Rename PDF
        target_pdf = PDF_DIR / f"{target_stem}.pdf"
        if target_pdf.exists():
            print(f" → {target_stem} (PDF conflict)")
        else:
            pdf_path.rename(target_pdf)
            print(f" → {target_stem}")
        
        # Save to combined extract
        date_str = time.strftime("%Y-%m-%d")
        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        with open(EXTRACT_DIR / f"{date_str}.txt", "a", encoding="utf-8") as f:
            f.write(f"===== {target_stem}.pdf (from {pdf_name}) =====\n\n{text[:50000]}\n\n=====\n\n")

    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
