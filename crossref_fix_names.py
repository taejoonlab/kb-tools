#!/usr/bin/env python3
"""CrossRef API로 추출된 PDF 메타데이터 보정: 저자명+연도+저널명 정확히 조회하여 파일명 수정
처리: _extracted.txt → DOI 추출 → CrossRef API → 올바른 이름 생성 → rename
"""
import sys, os, re, json, time
from pathlib import Path
import urllib.request
import urllib.error

_VAULT = Path(__file__).parent.parent
PDF_DIR = _VAULT / "ko/pdf"
NOTES_DIR = PDF_DIR / "notes"
LOG_FILE = NOTES_DIR / "crossref_fix_log.md"

CROSSREF_TIMEOUT = 15


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
    """CrossRef API로 저자, 연도, 저널명 조회"""
    if not doi:
        return None, None, None
    try:
        url = f"https://api.crossref.org/works/{doi}"
        req = urllib.request.Request(url, headers={"User-Agent": "kb-taejoon/1.0"})
        with urllib.request.urlopen(req, timeout=CROSSREF_TIMEOUT) as resp:
            data = json.loads(resp.read())
        msg = data.get("message", {})

        # 저자
        authors = msg.get("author", [])
        first_author = None
        if authors:
            first = authors[0].get("family", "")
            if first and len(first) > 1:
                first_author = re.sub(r'[^A-Za-zÀ-ü\-]', '', first)

        # 연도
        year = None
        date_parts = msg.get("published-online", {}).get("date-parts", [[]])[0]
        if not date_parts:
            date_parts = msg.get("issued", {}).get("date-parts", [[]])[0]
        if date_parts:
            y = date_parts[0]
            if isinstance(y, int) and 1900 <= y <= 2099:
                year = str(y)

        # 저널명 (short)
        journal = None
        short = msg.get("short-container-title", [])
        if short:
            journal = re.sub(r'[^A-Za-z0-9]', '', short[0])
        if not journal:
            full = msg.get("container-title", [])
            if full:
                # Take first word or abbreviation
                j = full[0]
                # Try to get standard abbreviation
                j_abbr = re.sub(r'[^A-Za-z0-9]', '', j.split()[0] if j.split() else j)
                if len(j_abbr) > 3:
                    journal = j_abbr

        return first_author, year, journal
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None, None  # DOI not found
        raise
    except Exception:
        return None, None, None


def generate_name(author, year, journal):
    if not author:
        author = "Unknown"
    if not year:
        year = "XXXX"
    if not journal:
        journal = "Unknown"
    return f"{author}{year}_{journal}.pdf"


def main():
    # Find ALL extracted text files (not just today's - old files might also benefit)
    extracted_files = sorted(NOTES_DIR.glob("*_extracted.txt"))

    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(hours=48)
    new_files = [f for f in extracted_files if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff]

    print(f"최근 48시간 내 생성된 파일: {len(new_files)}개")

    renamed = 0
    skipped = 0
    errors = 0
    results = []

    for i, txt_path in enumerate(new_files, 1):
        stem = txt_path.stem  # e.g., "Da2024_Unknown_extracted"
        # Remove trailing _extracted
        if stem.endswith("_extracted"):
            current_name = stem[:-len("_extracted")]
        else:
            current_name = stem

        print(f"[{i}/{len(new_files)}] {current_name} ... ", end="", flush=True)

        # Read first 3000 chars for DOI
        try:
            text = txt_path.read_text(encoding="utf-8", errors="ignore")[:3000]
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
            continue

        doi = extract_doi(text)
        if not doi:
            print(f"DOI 없음 → skip")
            skipped += 1
            continue

        # CrossRef lookup
        try:
            author, year, journal = crossref_lookup(doi)
        except Exception as e:
            print(f"API 오류: {e}")
            errors += 1
            continue

        correct_name = generate_name(author, year, journal)
        correct_stem = correct_name.replace(".pdf", "")

        if correct_name == f"{current_name}.pdf":
            print(f"이미 올바름 ✓")
            skipped += 1
            continue

        # Need to rename
        print(f"{current_name}.pdf → {correct_name}")

        # 1. Rename extracted text file
        new_txt_path = NOTES_DIR / f"{correct_stem}_extracted.txt"
        if new_txt_path.exists():
            print(f"   [WARN] 대상 _extracted.txt 존재 → skip")
            skipped += 1
            continue
        txt_path.rename(new_txt_path)

        # 2. Rename PDF
        old_pdf = PDF_DIR / f"{current_name}.pdf"
        new_pdf = PDF_DIR / correct_name
        if old_pdf.exists():
            if new_pdf.exists():
                print(f"   [WARN] 대상 PDF 존재 → skip rename")
            else:
                old_pdf.rename(new_pdf)
                print(f"   PDF 이름 변경 완료")
        else:
            print(f"   PDF 없음: {old_pdf.name}")

        results.append((current_name, correct_stem, doi))
        renamed += 1

    # Summary
    print(f"\n=== CrossRef 보정 완료 ===")
    print(f"처리: {len(new_files)}")
    print(f"이름 변경: {renamed}")
    print(f"건너뜀: {skipped}")
    print(f"오류: {errors}")

    # Log
    if results:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"# CrossRef Name Fix Log ({time.strftime('%Y-%m-%d %H:%M')})\n\n")
            f.write(f"| # | Old Name | New Name | DOI |\n|---|----------|----------|-----|\n")
            for i, (old, new, doi) in enumerate(results, 1):
                f.write(f"| {i} | {old} | {new} | {doi} |\n")

if __name__ == "__main__":
    main()
