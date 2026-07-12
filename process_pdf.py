#!/usr/bin/env python3
"""
PDF -> Obsidian MD 변환 워크플로우 자동화 스크립트

사용법:
  python3 process_pdf.py /path/to/paper.pdf [--dry-run] [--no-rename] [--output-dir DIR] [--force-review]

기능:
  1. PyMuPDF로 텍스트 추출 (pymupdf, max 30 pages)
  2. DOI -> CrossRef API로 저자명, DOI prefix map으로 저널명 검색
  3. 리뷰 논문 자동 판별 (파일명 -review 접미사 또는 본문 키워드)
  4. (FirstAuthor)(Year)_(Journal)[-review].pdf 형식으로 이름 변경
  5. 대상 파일명 충돌 체크 (존재 시 abort)
  6. notes/에 추출 텍스트 저장, --output-dir 위치에 MD 스켈레톤 생성
  7. 00_processing_log.md 업데이트

옵션:
  --dry-run       실제 파일 변경 없이 제안 내용만 출력
  --no-rename     PDF 파일명 변경 생략 (이미 올바른 형식인 경우)
  --output-dir    MD 스켈레톤 생성 위치 (기본: pdf 디렉토리의 notes/ 하위)
  --force-review  리뷰 논문으로 강제 지정 (파일명에 -review 포함 시 자동 적용)

주의:
  - CrossRef API 접근을 위해 인터넷 연결 필요 (실패 시 regex fallback)
  - 저널명은 DOI prefix map 우선, 텍스트 기반 검색은 차선으로만 사용
  - 이름 충돌 시 abort 후 수동 확인 필요
  - dry-run으로 제안된 이름을 반드시 검증한 후 실제 rename

의존성:
  pip install pymupdf
"""

import sys
import os
import re
import json
import signal
import subprocess
from pathlib import Path
from typing import Optional


class ProcessingTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise ProcessingTimeout("PDF 처리 시간 초과 (timeout)")

# pip install pymupdf
try:
    import fitz
except ImportError:
    print("PyMuPDF 필요: pip install pymupdf")
    sys.exit(1)

# DOI prefix / journal name mapping (external JSON)
_SCRIPT_DIR = Path(__file__).parent
_MAP_FILE = _SCRIPT_DIR / "doi_journal_map.json"

def _load_journal_map() -> tuple:
    """Load DOI prefix map and known journals from JSON file."""
    if not _MAP_FILE.exists():
        return {}, {}
    with open(_MAP_FILE, encoding='utf-8') as f:
        data = json.load(f)
    # Flatten nested doi_prefix_map
    doi_map = {}
    for category, prefixes in data.get("doi_prefix_map", {}).items():
        doi_map.update(prefixes)
    known = data.get("known_journals", {})
    return doi_map, known

DOI_PREFIX_MAP, KNOWN_JOURNALS = _load_journal_map()


def extract_text(pdf_path: str, max_pages: int = 30) -> str:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc[:max_pages]:
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
    """텍스트에서 출판년도 추출 (publication date 우선)"""
    lines = text.split('\n')

    # Priority 1: 저널 헤더 라인 (e.g. "iScience 27, 109585, April 19, 2024")
    for line in lines[:30]:
        m = re.search(r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+((?:19|20)\d{2}))', line)
        if m:
            year = m.group(2)
            if 1900 <= int(year) <= 2099:
                return year
        # "© 2022" or "Copyright 2019"
        m = re.search(r'(?:©|Copyright)\s*((?:19|20)\d{2})', line)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year

    # Priority 2: 권호 + 연도 (e.g. "Nature 635, 657 (2024)")
    for line in lines[:30]:
        m = re.search(r'[\((]\s*((?:19|20)\d{2})\s*[\))]', line)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year

    # Priority 3: Published / online date (출판일 우선)
    for line in lines[:100]:
        m = re.search(r'(?:Published|online|publication)\s*(?:\w+\s*)*[:\s]*\s*((?:19|20)\d{2})', line, re.IGNORECASE)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year

    # Priority 4: 권호 정보 (e.g. "2024;Vol" "2023; Vol")
    for line in lines[:100]:
        m = re.search(r'\b((?:19|20)\d{2})\s*[;:,]\s*(?:Vol|Suppl|\d+\s*[;:,])', line)
        if m:
            year = m.group(1)
            if 1900 <= int(year) <= 2099:
                return year

    # Priority 5: Accepted date (Accepted 뒤에 published year가 옴)
    for line in lines[:100]:
        m = re.search(r'(?:Accepted|accepted)\s*(?:\w+\s*)*[:\s]*\s*((?:19|20)\d{2})', line)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year

    # Priority 6: Received date (마지막 수단)
    for line in lines[:100]:
        m = re.search(r'(?:Received|revised)\s*(?:\w+\s*)*[:\s]*\s*((?:19|20)\d{2})', line, re.IGNORECASE)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year

    # Priority 7: DOI에서 연도 추출
    doi = extract_doi(text)
    if doi:
        m = re.search(r'\.(20\d{2})', doi)
        if m:
            return m.group(1)

    # Priority 8: 첫 200줄 내 4자리 연도 (general fallback)
    for line in lines[:200]:
        m = re.search(r'\b(20[0-2]\d)\b', line)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2029:
                return year

    return None


def extract_first_author(text: str, doi: Optional[str] = None) -> Optional[str]:
    """첫 번째 저자 성(Last name) 추출.
    DOI가 있으면 CrossRef API 조회, 실패 시 regex fallback."""
    # CrossRef API 조회 (가장 정확)
    if doi:
        try:
            import urllib.request
            import urllib.error
            url = f"https://api.crossref.org/works/{doi}"
            req = urllib.request.Request(url, headers={"User-Agent": "process_pdf/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                authors = data.get("message", {}).get("author", [])
                if authors:
                    first = authors[0].get("family", "")
                    if first and len(first) > 1:
                        return re.sub(r'[^A-Za-zÀ-ü\-]', '', first)
        except Exception:
            pass  # 네트워크 오류 등 -> regex fallback

    # Regex fallback
    lines = text[:5000].split('\n')
    # 패턴 1: "Last1 F1, Last2 F2, ..., and LastN FN" 형태
    for i, line in enumerate(lines[:200]):
        line = line.strip()
        if not line or len(line) < 10:
            continue
        # and/& + Last Initial. 로 끝나는 저자 리스트
        if re.search(r'\b(?:and|&)\s+[A-Z][a-zà-ü\-]+\s+[A-Z]\.?(?:$|\s*\d)', line):
            # 저자 리스트 전체를 쉼표로 분리
            parts = line.split(',')
            raw = parts[0].strip()
            words = raw.split()
            if words:
                name = words[0]
                name = re.sub(r'[^A-Za-zÀ-ü\-]', '', name)
                if len(name) > 1:
                    return name
            break
        # 여러 저자가 쉼표 또는 번호+쉼표로 구분된 패턴
        # e.g. "Kangkang Zha,1,2,3 Zhiqiang Sun,1,2,3 ..."
        # extract first name before the first number/comma break
        m = re.match(r'^([A-Z][a-zà-ü\-]+(?:\s+[A-Z][a-zà-ü\-]+)*)\s*(?:[A-Z]\.?\s*)?', line)
        if m and re.search(r'[.,]\s*\d', line):
            author_candidate = m.group(1)
            words = author_candidate.split()
            last_name = words[-1] if len(words) > 1 else words[0]
            last_name = re.sub(r'[^A-Za-zÀ-ü\-]', '', last_name)
            if last_name and len(last_name) > 1:
                if not re.search(r'(?:correspondence|email|abstract|introduction|summary|key\s*words)', line, re.IGNORECASE):
                    return last_name

    # 패턴 2: 단독 저자 "Last Name" or "First Last" on title page
    for line in lines[:50]:
        line = line.strip()
        # "David B. Burr PhD*" -> Burr
        # 여러 단어였는데 뒤에 PhD, MD, title 등이 붙은 경우
        m = re.match(r'^([A-Z][a-zà-ü\-]+(?:\s+[A-Z]\.?){0,2})\s*(?:PhD|MD|DDS|DVM|Dr|Prof)', line)
        if m:
            name = m.group(1).split()[0]
            if len(name) > 1:
                return name
        # 제목 직후 저자명 단독 라인 (e.g. Title line 다음에 "Author Name"만)
        m = re.match(r'^([A-Z][a-zà-ü\-]+)\s+[A-Z]\.?\s*$', line)
        if m:
            last = m.group(1)
            if last.lower() not in ('the', 'and', 'for', 'from', 'with', 'that', 'this'):
                return last

    return None


def extract_journal(text: str) -> Optional[str]:
    """저널명 약어 추출 (DOI prefix 우선 -> 텍스트 헤더 정보 차선)"""
    doi = extract_doi(text)
    doi_lower = doi.lower() if doi else ""

    # DOI prefix lookup (loaded from doi_journal_map.json)
    for prefix, abbr in DOI_PREFIX_MAP.items():
        if doi_lower.startswith(prefix):
            if abbr == '__HINDAWI__':
                break  # fall through to text search
            return abbr

    # 텍스트 기반 저널명 검색 (DOI 실패 시에만, 헤더 정보에 한정)
    header_keywords = ['©', 'Copyright', 'published', 'Volume', 'Vol.', 'ISSN',
                       'journal homepage', 'www.', 'wileyonlinelibrary', 'onlinelibrary']

    lines = text[:3000].split('\n')
    for line in lines:
        line_lower = line.lower()
        has_header_context = any(kw.lower() in line_lower for kw in header_keywords)
        for name, abbr in KNOWN_JOURNALS.items():
            if name.lower() in line:
                if has_header_context or 'journal' in line_lower:
                    return abbr
                if len(name) > 12 and name.lower() not in ('development', 'nature', 'science'):
                    return abbr

    return None


def detect_review(text: str) -> bool:
    """리뷰 논문 여부 판별"""
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
    # 자연어 패턴 (case-insensitive)
    natural_patterns = [
        r'\bthis review\b', r'\bwe review\b', r'\bI review\b',
        r'\breview summarizes\b', r'\breview highlights\b',
        r'\bthis article reviews\b', r'\bhere,? we review\b',
    ]
    for pat in natural_patterns:
        if re.search(pat, head, re.IGNORECASE):
            return True
    return False


def detect_preprint(text: str) -> Optional[str]:
    """bioRxiv/medRxiv preprint 여부 감지 (journal lookup 전에 실행)"""
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


def suggest_target_name(pdf_path: str, text: str, doi: Optional[str]) -> str:
    """FirstAuthorYear_Journal[-review].pdf 형식 제안"""
    # Preprint detection first (before journal lookup)
    preprint = detect_preprint(text)
    if preprint:
        author = extract_first_author(text, doi)
        year = extract_year(text)
        if not author:
            base = Path(pdf_path).stem
            m = re.match(r'^([A-Za-z]+)(20\d{2})', base)
            if m:
                author = m.group(1).capitalize()
                year = year or m.group(2)
            else:
                author = "Unknown"
        if not year:
            year = "XXXX"
        suffix = "-review" if detect_review(text) else ""
        return f"{author}{year}_{preprint}{suffix}.pdf"

    author = extract_first_author(text, doi)
    year = extract_year(text)
    journal = extract_journal(text)
    is_review = detect_review(text)

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

    if journal:
        j_short = re.sub(r'[^A-Za-z0-9]', '', journal)
    else:
        j_short = "Unknown"

    suffix = "-review" if is_review else ""
    return f"{author}{year}_{j_short}{suffix}.pdf"


_VAULT_ROOT = _SCRIPT_DIR.parent

def prompt_tag() -> str:
    """태그(YYYY-MM) 입력 프롬프트"""
    import sys
    print("\n태그를 입력하세요 (예: 2026-06, Enter=2026-07): ", end="", flush=True)
    try:
        tag = sys.stdin.readline().strip()
    except:
        tag = ""
    if not tag:
        from datetime import datetime
        tag = datetime.now().strftime("%Y-%m")
    return tag


def _extract_date() -> str:
    """오늘 날짜 (extract 파일명용 YYYY-MM-DD)"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def save_extract(pdf_name: str, text: str, dry_run: bool = False):
    """추출 텍스트를 /extract/YYYY-MM-DD.txt 에 추가"""
    date_str = _extract_date()
    extract_dir = _VAULT_ROOT / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    out_path = extract_dir / f"{date_str}.txt"
    if dry_run:
        print(f"   추출 저장: {out_path} ({len(text)} chars)")
        return
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(f"===== {pdf_name} =====\n\n")
        f.write(text)
        f.write("\n\n=====\n\n")
    print(f"   추출 저장: {out_path}")


def create_md_skeleton(pdf_path: str, pdf_name: str, target_basename: str, doi: Optional[str],
                        output_dir: Optional[str] = None) -> str:
    """원저 논문 MD 파일 스켈레톤 생성"""
    tag = prompt_tag()
    extract_d = _extract_date()
    md_content = f"""---
tags: [{tag}]
extract: {extract_d}
---

# TITLE_PLACEHOLDER

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
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = Path(pdf_path).parent / "notes"
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / f"{Path(target_basename).stem}.md"
    md_path.write_text(md_content, encoding='utf-8')

    return str(md_path)


def create_review_md_skeleton(pdf_path: str, pdf_name: str, target_basename: str, doi: Optional[str],
                               output_dir: Optional[str] = None) -> str:
    """리뷰 논문 MD 파일 스켈레톤 생성 (리뷰 전용 섹션)"""
    tag = prompt_tag()
    extract_d = _extract_date()
    md_content = f"""---
tags: [{tag}]
extract: {extract_d}
---

# TITLE_PLACEHOLDER

## Citation (NLM)
NLM_CITATION_PLACEHOLDER

**DOI:** [https://doi.org/{doi if doi else 'PLACEHOLDER'}](https://doi.org/{doi if doi else 'PLACEHOLDER'})

---

## Overview

TODO — 리뷰의 주제, 배경, 목적 및 전체 범위

---

## Key Topics

TODO — 리뷰에서 다루는 주요 주제별 정리

---

## Key Findings

TODO — 핵심 내용, 결론, 중요한 인사이트

---

## Perspective

TODO — 의의, 한계, 향후 연구 방향

---

## Key References

TODO — 핵심 참고 문헌 목록 (저자 연도, 저널, DOI 링크)
"""
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = Path(pdf_path).parent / "notes"
    out_dir.mkdir(parents=True, exist_ok=True)

    # -review 접미사 제거하여 MD 파일명 생성
    stem = Path(target_basename).stem
    if stem.endswith('-review'):
        stem = stem[:-len('-review')]
    md_path = out_dir / f"{stem}.md"
    md_path.write_text(md_content, encoding='utf-8')

    return str(md_path)


def update_log(pdf_dir: str, entry: str):
    log_path = Path(pdf_dir) / "notes" / "00_processing_log.md"
    log_path.parent.mkdir(exist_ok=True)
    if not log_path.exists():
        log_path.write_text("# Processing Log\n\n| # | PDF | MD | Status |\n|---|-----|----|--------|\n", encoding='utf-8')

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry + "\n")


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 process_pdf.py <pdf_path> [--dry-run] [--no-rename] [--output-dir DIR] [--force-review] [--timeout SECS]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    no_rename = "--no-rename" in sys.argv
    force_review = "--force-review" in sys.argv

    timeout_secs = 10
    if "--timeout" in sys.argv:
        idx = sys.argv.index("--timeout")
        if idx + 1 < len(sys.argv):
            timeout_secs = int(sys.argv[idx + 1])

    output_dir = None
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_secs)

    try:
      _main_body(pdf_path, dry_run, no_rename, force_review, output_dir)
    except ProcessingTimeout:
        print(f"[SKIP] {pdf_path}: 처리 시간 초과 ({timeout_secs}초)")
        sys.exit(2)
    finally:
        signal.alarm(0)


def _main_body(pdf_path, dry_run, no_rename, force_review, output_dir):
    if not os.path.exists(pdf_path):
        print(f"파일 없음: {pdf_path}")
        sys.exit(1)

    pdf_path = os.path.abspath(pdf_path)
    pdf_dir = os.path.dirname(pdf_path)
    pdf_name = os.path.basename(pdf_path)

    print(f"[PROCESS] {pdf_name}")

    # 텍스트 추출
    text = extract_text(pdf_path)
    print(f"   텍스트: {len(text):,} chars")

    # DOI 추출
    doi = extract_doi(text)
    print(f"   DOI: {doi if doi else 'Not found'}")

    # 리뷰/원저 판별: 파일명 -review 접미사 우선, 그 다음 본문 키워드, 마지막으로 --force-review
    stem = Path(pdf_path).stem
    if stem.endswith('-review') or force_review:
        is_review = True
        print(f"   유형: 리뷰 논문 (파일명 기반)")
    else:
        is_review = detect_review(text)
        if is_review:
            print(f"   유형: 리뷰 논문 (본문 키워드 기반)")

    # 대상 파일명 제안
    target_name = suggest_target_name(pdf_path, text, doi)
    print(f"   대상 이름: {target_name}")

    # 충돌 체크
    target_path = os.path.join(pdf_dir, target_name)
    if os.path.exists(target_path) and target_path != pdf_path:
        print(f"   [WARN]  충돌: 대상 파일이 이미 존재함!")
        print(f"      기존: {target_name}")
        alt_name = target_name.replace('.pdf', '_dup.pdf')
        print(f"      제안: {alt_name}")
        if not dry_run:
            print(f"      -> abort. 수동으로 확인 후 rename 하세요.")
            sys.exit(1)
        else:
            print(f"      (dry-run - 계속 진행)")

    # MD 스켈레톤 생성
    if is_review:
        md_path = create_review_md_skeleton(pdf_path, pdf_name, target_name, doi, output_dir)
    else:
        md_path = create_md_skeleton(pdf_path, pdf_name, target_name, doi, output_dir)
    print(f"   MD 파일: {md_path}")

    # PDF 이름 변경
    old_name = pdf_name

    if no_rename or pdf_name == target_name:
        print(f"   PDF 이름: 변경 생략 ({pdf_name})")
    elif dry_run:
        print(f"   PDF 이름: {pdf_name} -> {target_name} (dry-run)")
    else:
        os.rename(pdf_path, target_path)
        print(f"   PDF 이름: {pdf_name} -> {target_name}")

    # Log 업데이트
    review_tag = "[REVIEW] " if is_review else ""
    log_entry = f"| {review_tag}{target_name} (from {old_name}) | {Path(md_path).name} | [DONE] Done |"
    if not dry_run:
        update_log(pdf_dir, log_entry)

    # 텍스트 추출본 저장 (extract/ 에 추가)
    save_extract(pdf_name, text[:50000], dry_run)

    print(f"[DONE] 완료: {target_name}")
    if is_review:
        print(f"   -> {md_path} 의 내용을 LLM이 채우도록 요청하세요. (리뷰 전용 섹션)")
    else:
        print(f"   -> notes/ 디렉토리의 MD 파일 내용을 LLM이 채우도록 요청하세요.")


if __name__ == "__main__":
    main()
