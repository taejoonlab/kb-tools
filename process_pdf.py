#!/usr/bin/env python3
"""
PDF → Obsidian MD 변환 워크플로우 자동화 스크립트

사용법:
  python3 process_pdf.py /path/to/paper.pdf

기능:
  1. PyMuPDF로 텍스트 추출 (pymupdf)
  2. DOI, 제목, 저자, 저널명 자동 검색
  3. (FirstAuthor)(Year)_(Journal) 형식으로 PDF 이름 변경
  4. notes/에 MD 파일 스켈레톤 생성 (LLM이 내용 채울 준비)
  5. 00_processing_log.md 업데이트

의존성:
  pip install pymupdf

출력:
  - PDF → (FirstAuthor)(Year)_(Journal).pdf 로 이름 변경
  - notes/(FirstAuthor)(Year)_(Journal).md   ← LLM이 내용 채움
  - notes/00_processing_log.md               ← 진행 로그
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path
from typing import Optional

# pip install pymupdf
try:
    import fitz
except ImportError:
    print("PyMuPDF 필요: pip install pymupdf")
    sys.exit(1)


def extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text


def extract_doi(text: str) -> Optional[str]:
    # DOI 패턴 검색
    patterns = [
        r'(?:doi|DOI)\s*[:\s]*\s*(10\.\d{4,}/[^\s,;]+)',
        r'(10\.\d{4,}/[^\s,;\]]+)',
        r'doi\.org/(10\.\d{4,}/[^\s,;]+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            doi = m.group(1).rstrip('.,)')
            return doi
    return None


def extract_year(text: str) -> Optional[str]:
    """텍스트에서 출판년도 추출"""
    # DOI에서 연도 추출이 가장 정확
    doi = extract_doi(text)
    if doi:
        # DOI 패턴에 연도가 있는 경우
        for prefix in ['nrdp', 'sciadv']:
            pass

    # DOI가 포함된 라인에서 연도 추출
    for line in text.split('\n'):
        if 'doi' in line.lower() and re.search(r'20\d{2}', line):
            continue  # DOI 라인은 제외 (연도가 DOI에 있는 경우)

    # 권호 정보가 있는 라인에서 연도 추출 (가장 신뢰할 수 있음)
    # "Journal Name. 2024; Vol" or "Name 2024, 123-130" 패턴
    lines = text.split('\n')
    for line in lines[:100]:
        line = line.strip()
        # (2024)Vol or 2024;Vol or 2024:Vol
        m = re.search(r'\b((?:19|20)\d{2})\s*[;:,]\s*(?:Vol|Suppl|\d+)', line)
        if m:
            year = m.group(1)
            if 1900 <= int(year) <= 2099:
                return year
        # Published: 2024
        m = re.search(r'(?:Published|pub|Accepted|Received|online)\s*(?:\w+\s*)*[:\s]*\s*((?:19|20)\d{2})', line, re.IGNORECASE)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year

    # DOI에서 연도 추출 시도 (일부 DOI는 연도 포함)
    if doi:
        # e.g., 10.1002/bdrc.20124 → 연도 없음
        # 10.1096/fj.201800534R → 2018
        m = re.search(r'\.(20\d{2})', doi)
        if m:
            return m.group(1)

    # 첫 번째 나타나는 사년도 숫자 (1900-2099)
    for line in lines[:200]:
        for m in re.finditer(r'\b(20[0-2]\d)\b', line):
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year
    return None


def extract_first_author(text: str) -> Optional[str]:
    """첫 번째 저자 성(Last name) 추출.
    Author list line에서 첫 번째 저자 성을 찾음."""
    lines = text[:5000].split('\n')

    # Author list line 찾기: "Last1 F1, Last2 F2, ..." or "Last1, F1, Last2, F2,..."
    # "and Last F"로 끝나는 줄이 author list
    author_line = None
    for i, line in enumerate(lines[:200]):
        line = line.strip()
        if not line or len(line) < 10:
            continue
        # and로 끝나는 author list 패턴
        if re.search(r'\b(?:and|&)\s+[A-Z][a-zà-ü]+\s+[A-Z]\.?\s*$', line):
            author_line = line
            break
        # 여러 저자가 쉼표로 구분된 패턴 (Correspondence 제외)
        if re.match(r'^[A-Z][a-zà-ü]+ [A-Z]\.\s*,\s*[A-Z][a-zà-ü]+ [A-Z]\.', line):
            if 'correspondence' not in line.lower() and 'email' not in line.lower():
                author_line = line
                break

    if author_line:
        # 첫 번째 저자 성 추출
        first_author = author_line.split(',')[0].strip()
        # "Last F." 형식 → Last
        first_name = first_author.split()[0]
        # 특수문자 제거
        first_name = re.sub(r'[^A-Za-zÀ-ü]', '', first_name)
        if first_name and len(first_name) > 1:
            return first_name.capitalize()

    # Fallback: "Authors: Last F, ..." 패턴
    for line in lines[:200]:
        m = re.search(r'(?:Authors?|By)\s*:\s*([A-Z][a-zà-ü]+)', line)
        if m:
            return m.group(1).capitalize()

    return None


def extract_journal(text: str) -> Optional[str]:
    """저널명 약어 추출"""
    # 먼저 DOI prefix로 저널 추정
    doi = extract_doi(text)
    if doi:
        doi_prefix_map = {
            '10.1126/sciadv': 'SciAdv',
            '10.1038/s41597': 'SciData',
            '10.1038/nrdp': 'NatRevDisPrimers',
            '10.1093/nar': 'NucleicAcidsRes',
            '10.1242/dev': 'Development',
            '10.1096/fj': 'FASEB',
            '10.1016/j.biomaterials': 'Biomaterials',
            '10.3389/fcell': 'FrontCellDevBiol',
            '10.1186/s12891': 'BMCMusculoskeletDisord',
            '10.3892/mmr': 'MolMedRep',
            '10.1016/j.joca': 'OsteoarthritisCartilage',
            '10.1177/19476035': 'Cartilage',
            '10.1146/annurev-physiol': 'AnnuRevPhysiol',
            '10.1146/annurev.cellbio': 'AnnuRevCellDevBiol',
            '10.1002/bdrc': 'BirthDefectsResC',
            '10.1073/pnas': 'PNAS',
            '10.7554/eLife': 'eLife',
            '10.7554/elife': 'eLife',
        }
        for prefix, abbr in doi_prefix_map.items():
            if doi.lower().startswith(prefix):
                return abbr

    known_journals = {
        'Sci Adv': 'SciAdv',
        'Scientific Data': 'SciData',
        'Nat Rev Dis Primers': 'NatRevDisPrimers',
        'Nature Reviews Disease Primers': 'NatRevDisPrimers',
        'Nucleic Acids Res': 'NucleicAcidsRes',
        'Nucleic Acids Research': 'NucleicAcidsRes',
        'Development': 'Development',
        'FASEB J': 'FASEB',
        'Biomaterials': 'Biomaterials',
        'Front Cell Dev Biol': 'FrontCellDevBiol',
        'BMC Musculoskelet Disord': 'BMCMusculoskeletDisord',
        'Mol Med Rep': 'MolMedRep',
        'Osteoarthritis Cartilage': 'OsteoarthritisCartilage',
        'Cartilage': 'Cartilage',
        'Annu Rev Physiol': 'AnnuRevPhysiol',
        'Annu Rev Cell Dev Biol': 'AnnuRevCellDevBiol',
        'Birth Defects Res C': 'BirthDefectsResC',
        'Proc Natl Acad Sci USA': 'PNAS',
        'eLife': 'eLife',
    }

    lines = text[:5000].split('\n')
    for line in lines:
        line_lower = line.lower()
        for name, abbr in known_journals.items():
            if name.lower() in line_lower.replace(' ', ''):
                return abbr

    return None


def suggest_target_name(pdf_path: str, text: str, doi: Optional[str]) -> str:
    """FirstAuthorYear_Journal.pdf 형식 제안"""
    author = extract_first_author(text)
    year = extract_year(text)
    journal = extract_journal(text)

    if not author:
        # 파일명에서 fallback
        base = Path(pdf_path).stem
        m = re.match(r'^([A-Za-z]+)(20\d{2})', base)
        if m:
            author = m.group(1).capitalize()
            year = year or m.group(2)
        else:
            author = "Unknown"

    if not year:
        year = "XXXX"

    # 저널명 단축 (첫 단어만)
    if journal:
        j_short = journal.split()[0].rstrip('.')
        # 특수문자 제거
        j_short = re.sub(r'[^A-Za-z0-9]', '', j_short)
    else:
        j_short = "Unknown"

    return f"{author}{year}_{j_short}.pdf"


def create_md_skeleton(pdf_path: str, target_basename: str, doi: Optional[str]) -> str:
    """MD 파일 스켈레톤 생성"""
    md_content = f"""# TITLE_PLACEHOLDER

## Citation (NLM)
NLM_CITATION_PLACEHOLDER

**DOI:** [https://doi.org/{doi if doi else 'PLACEHOLDER'}](https://doi.org/{doi if doi else 'PLACEHOLDER'})

---

## Background

TODO

---

## Key Experiment Methods

TODO

---

## Results

TODO

---

## Perspective

TODO
"""
    notes_dir = Path(pdf_path).parent / "notes"
    notes_dir.mkdir(exist_ok=True)

    md_path = notes_dir / f"{Path(target_basename).stem}.md"
    md_path.write_text(md_content)

    return str(md_path)


def update_log(pdf_dir: str, entry: str):
    log_path = Path(pdf_dir) / "notes" / "00_processing_log.md"
    log_path.parent.mkdir(exist_ok=True)
    if not log_path.exists():
        log_path.write_text("# Processing Log\n\n| # | PDF | MD | Status |\n|---|-----|----|--------|\n")

    with open(log_path, 'a') as f:
        f.write(entry + "\n")


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 process_pdf.py <pdf_path> [--dry-run]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(pdf_path):
        print(f"파일 없음: {pdf_path}")
        sys.exit(1)

    pdf_path = os.path.abspath(pdf_path)
    pdf_dir = os.path.dirname(pdf_path)
    pdf_name = os.path.basename(pdf_path)

    print(f"📄 처리 중: {pdf_name}")

    # 텍스트 추출
    text = extract_text(pdf_path)
    print(f"   텍스트: {len(text):,} chars")

    # DOI 추출
    doi = extract_doi(text)
    print(f"   DOI: {doi if doi else 'Not found'}")

    # 대상 파일명 제안
    target_name = suggest_target_name(pdf_path, text, doi)
    print(f"   대상 이름: {target_name}")

    # MD 스켈레톤 생성
    md_path = create_md_skeleton(pdf_path, target_name, doi)
    print(f"   MD 파일: {md_path}")

    # PDF 이름 변경
    target_path = os.path.join(pdf_dir, target_name)
    old_name = pdf_name

    if pdf_name == target_name:
        print(f"   PDF 이름: 이미 올바른 형식")
    elif dry_run:
        print(f"   PDF 이름: {pdf_name} → {target_name} (dry-run)")
    else:
        os.rename(pdf_path, target_path)
        print(f"   PDF 이름: {pdf_name} → {target_name}")

    # Log 업데이트
    log_entry = f"|  | {target_name} (renamed from {old_name}) | {Path(md_path).name} | ✅ Done |"
    if not dry_run:
        update_log(pdf_dir, log_entry)

    # 텍스트 추출본 저장 (LLM이 MD 내용 채울 때 참고)
    txt_path = f"{Path(md_path).stem}_extracted.txt"
    txt_full = Path(pdf_dir) / "notes" / txt_path
    if not dry_run:
        txt_full.write_text(text[:50000])
        print(f"   텍스트 추출본: {txt_full}")

    print(f"✅ 완료: {target_name}")
    print(f"   → notes/ 디렉토리의 MD 파일 내용을 LLM이 채우도록 요청하세요.")


if __name__ == "__main__":
    main()
