#!/usr/bin/env python3
"""
CLASS PDF → Obsidian MD 변환 (수업용 노트)

사용법:
  python3 process_pdf_class.py /path/to/paper.pdf [--keywords "kw1,kw2"] [--dry-run]

기능:
  1. PyMuPDF로 텍스트 추출 (max 30 pages)
  2. DOI → CrossRef API로 저자명/저널명 검색
  3. {FirstAuthor}{Year}_{Journal}_{Kw1}[-{Kw2}].pdf 형식으로 이름 제안
  4. CLASS 형식 MD 스켈레톤 생성:
       - Summary (상세 요약)
       - Significance in Introduction Context (Introduction에서의 의미)
       - Key References (DOI URL 포함)
       - Future Research Directions (후속 연구 아이디어)
  5. notes/에 추출 텍스트 + MD 스켈레톤 저장
  6. 00_processing_log.md 업데이트

ARTICLE/REVIEW와의 차이:
  - 파일명에 키워드 1-2개 추가: {Author}{Year}_{Journal}_{Keyword}.pdf
  - MD 섹션이 수업용으로 확장됨 (Key References with DOI, Future Directions)
  - type: class frontmatter 태그

의존성:
  pip install pymupdf
"""

import sys
import os
import re
import json
import datetime
from pathlib import Path
from typing import Optional

try:
    import fitz
except ImportError:
    print("PyMuPDF 필요: pip install pymupdf")
    sys.exit(1)

# Reuse journal map from same directory
_SCRIPT_DIR = Path(__file__).parent
_MAP_FILE = _SCRIPT_DIR / "doi_journal_map.json"


def _load_journal_map() -> tuple:
    if not _MAP_FILE.exists():
        return {}, {}
    with open(_MAP_FILE) as f:
        data = json.load(f)
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
    patterns = [
        r'(?:doi|DOI)\s*[:\s]*\s*(10\.\d{4,}/[^\s,;]+)',
        r'(10\.\d{4,}/[^\s,;\]]+)',
        r'doi\.org/(10\.\d{4,}/[^\s,;]+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).rstrip('.,)')
    return None


def extract_year(text: str) -> Optional[str]:
    lines = text.split('\n')
    for line in lines[:30]:
        m = re.search(r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+((?:19|20)\d{2}))', line)
        if m:
            year = m.group(2)
            if 1900 <= int(year) <= 2099:
                return year
        m = re.search(r'(?:©|Copyright)\s*((?:19|20)\d{2})', line)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year
    for line in lines[:30]:
        m = re.search(r'[\(（]\s*((?:19|20)\d{2})\s*[\)）]', line)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year
    for line in lines[:100]:
        m = re.search(r'(?:Published|online|publication)\s*(?:\w+\s*)*[:\s]*\s*((?:19|20)\d{2})', line, re.IGNORECASE)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2099:
                return year
    for line in lines[:200]:
        m = re.search(r'\b(20[0-2]\d)\b', line)
        if m:
            year = m.group(1)
            if 2000 <= int(year) <= 2029:
                return year
    return None


def extract_first_author(text: str, doi: Optional[str] = None) -> Optional[str]:
    if doi:
        try:
            import urllib.request
            url = f"https://api.crossref.org/works/{doi}"
            req = urllib.request.Request(url, headers={"User-Agent": "process_pdf_class/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                authors = data.get("message", {}).get("author", [])
                if authors:
                    first = authors[0].get("family", "")
                    if first and len(first) > 1:
                        return re.sub(r'[^A-Za-zÀ-ü\-]', '', first)
        except Exception:
            pass

    lines = text[:5000].split('\n')
    for line in lines[:200]:
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
            words = m.group(1).split()
            last_name = re.sub(r'[^A-Za-zÀ-ü\-]', '', words[-1] if len(words) > 1 else words[0])
            if last_name and len(last_name) > 1:
                if not re.search(r'(?:correspondence|email|abstract|introduction|summary|key\s*words)', line, re.IGNORECASE):
                    return last_name
    return None


def extract_journal(text: str) -> Optional[str]:
    doi = extract_doi(text)
    doi_lower = doi.lower() if doi else ""
    for prefix, abbr in DOI_PREFIX_MAP.items():
        if doi_lower.startswith(prefix):
            if abbr == '__HINDAWI__':
                break
            return abbr
    header_keywords = ['©', 'Copyright', 'published', 'Volume', 'Vol.', 'ISSN',
                       'journal homepage', 'www.', 'wileyonlinelibrary']
    lines = text[:3000].split('\n')
    for line in lines:
        line_lower = line.lower()
        has_header = any(kw.lower() in line_lower for kw in header_keywords)
        for name, abbr in KNOWN_JOURNALS.items():
            if name.lower() in line_lower:
                if has_header or 'journal' in line_lower:
                    return abbr
                if len(name) > 12 and name.lower() not in ('development', 'nature', 'science'):
                    return abbr
    return None


def extract_keywords_from_title(text: str, doi: Optional[str] = None) -> list[str]:
    """CrossRef title → 명사구 키워드 후보 추출 (최대 2개)."""
    title = ""

    # CrossRef에서 제목 가져오기
    if doi:
        try:
            import urllib.request
            url = f"https://api.crossref.org/works/{doi}"
            req = urllib.request.Request(url, headers={"User-Agent": "process_pdf_class/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                titles = data.get("message", {}).get("title", [])
                if titles:
                    title = titles[0]
        except Exception:
            pass

    # fallback: 첫 줄 텍스트
    if not title:
        for line in text.split('\n')[:20]:
            line = line.strip()
            if len(line) > 20 and re.search(r'[a-zA-Z]', line):
                title = line
                break

    if not title:
        return []

    # 불용어 제거 후 CamelCase 키워드 추출
    stopwords = {
        'the', 'a', 'an', 'of', 'in', 'on', 'at', 'by', 'for', 'with',
        'and', 'or', 'but', 'is', 'are', 'was', 'were', 'be', 'been',
        'to', 'from', 'that', 'this', 'their', 'its', 'as', 'role',
        'effects', 'impact', 'study', 'analysis', 'new', 'novel',
    }

    # 단어 토큰화 (특수문자 제거)
    words = re.findall(r"[A-Za-z][a-zA-Z'\-]*", title)
    content_words = [w for w in words if w.lower() not in stopwords and len(w) > 3]

    if not content_words:
        return []

    # 연속 명사구를 CamelCase로 합치기 (최대 2단어씩)
    candidates = []
    i = 0
    while i < len(content_words) and len(candidates) < 2:
        w1 = content_words[i].capitalize()
        if i + 1 < len(content_words):
            w2 = content_words[i + 1].capitalize()
            candidates.append(w1 + w2)
            i += 2
        else:
            candidates.append(w1)
            i += 1

    return candidates[:2]


def slugify_keyword(kw: str) -> str:
    """키워드를 파일명 안전한 CamelCase 슬러그로 변환."""
    parts = re.split(r'[\s\-_]+', kw)
    return ''.join(p.capitalize() for p in parts if p)


def suggest_target_name(pdf_path: str, text: str, doi: Optional[str],
                        user_keywords: Optional[list[str]] = None) -> str:
    """{FirstAuthor}{Year}_{Journal}_{Kw1}[-{Kw2}].pdf 형식 제안."""
    author = extract_first_author(text, doi)
    year = extract_year(text)
    journal = extract_journal(text)

    if not author:
        base = Path(pdf_path).stem
        m = re.match(r'^([A-Za-z]+)(20\d{2})', base)
        if m:
            author = m.group(1).capitalize()
            year = year or m.group(2)
        else:
            # 파일명에서 첫 단어 추출
            author = re.sub(r'[^A-Za-z]', '', base.split('_')[0]) or "Unknown"

    if not year:
        year = "XXXX"

    j_short = re.sub(r'[^A-Za-z0-9]', '', journal) if journal else "Unknown"

    # 키워드 결정
    if user_keywords:
        kw_slugs = [slugify_keyword(k) for k in user_keywords[:2]]
    else:
        kw_slugs = extract_keywords_from_title(text, doi)

    if kw_slugs:
        kw_part = '_' + '-'.join(kw_slugs)
    else:
        kw_part = '_KEYWORD'

    return f"{author}{year}_{j_short}{kw_part}.pdf"


def create_class_skeleton(pdf_path: str, target_basename: str, doi: Optional[str],
                          category: str = "CATEGORY") -> str:
    """CLASS 형식 MD 스켈레톤 생성."""
    today = datetime.date.today().isoformat()
    doi_str = doi if doi else "PLACEHOLDER"
    doi_url = f"https://doi.org/{doi_str}"

    md_content = f"""---
tags: [genetics, class, {category}, ko]
date: {today}
type: class
---

# TITLE_PLACEHOLDER

## Citation (NLM)
NLM_CITATION_PLACEHOLDER

**DOI:** [{doi_url}]({doi_url})

---

## Summary

TODO — 핵심 주장, 주요 데이터, 결론을 수업 이해에 초점을 맞춰 상세하게 서술.

---

## Significance in Introduction Context

TODO — 이 논문이 해당 분야의 도입부에서 갖는 의미:
- 어떤 배경 지식/전제를 제공하는가
- 어떤 논쟁 또는 패러다임 전환에 위치하는가
- 수업에서 이 논문을 읽어야 하는 이유

---

## Key References

TODO — 본문에서 인용된 핵심 참고문헌 (DOI URL 포함):

1. **AuthorA et al. (Year)** — [https://doi.org/...](https://doi.org/...) — 한 줄 설명
2. **AuthorB et al. (Year)** — [https://doi.org/...](https://doi.org/...) — 한 줄 설명

---

## Future Research Directions

TODO — 이 논문에서 제기된 미해결 질문과 향후 연구 아이디어:

-
-

---

*Processed by **LLM_MODEL_PLACEHOLDER** (TOOL_PLACEHOLDER) on {today}*
"""

    notes_dir = Path(pdf_path).parent / "notes"
    notes_dir.mkdir(exist_ok=True)

    md_path = notes_dir / f"{Path(target_basename).stem}.md"
    md_path.write_text(md_content, encoding='utf-8')
    return str(md_path)


def update_log(pdf_dir: str, entry: str):
    log_path = Path(pdf_dir) / "notes" / "00_processing_log.md"
    log_path.parent.mkdir(exist_ok=True)
    if not log_path.exists():
        log_path.write_text("# Processing Log\n\n| Type | PDF | MD | Status |\n|------|-----|----|--------|\n")
    with open(log_path, 'a') as f:
        f.write(entry + "\n")


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="CLASS PDF → Obsidian MD 변환 (수업용)"
    )
    parser.add_argument("pdf_path", help="처리할 PDF 파일 경로")
    parser.add_argument("--keywords", "-k",
                        help='파일명에 추가할 키워드 1-2개, 쉼표 구분 (예: "Population,Drift")')
    parser.add_argument("--category", "-c", default="CATEGORY",
                        help='노트 카테고리: population / forward / reverse (기본: CATEGORY)')
    parser.add_argument("--dry-run", action="store_true",
                        help="파일 변경 없이 제안 이름만 출력")
    return parser.parse_args()


def main():
    args = parse_args()
    pdf_path = args.pdf_path
    dry_run = args.dry_run

    if not os.path.exists(pdf_path):
        print(f"파일 없음: {pdf_path}")
        sys.exit(1)

    pdf_path = os.path.abspath(pdf_path)
    pdf_dir = os.path.dirname(pdf_path)
    pdf_name = os.path.basename(pdf_path)

    user_keywords = None
    if args.keywords:
        user_keywords = [k.strip() for k in args.keywords.split(',') if k.strip()]

    print(f"📄 CLASS 처리 중: {pdf_name}")

    text = extract_text(pdf_path)
    print(f"   텍스트: {len(text):,} chars")

    doi = extract_doi(text)
    print(f"   DOI: {doi if doi else 'Not found'}")

    target_name = suggest_target_name(pdf_path, text, doi, user_keywords)
    print(f"   제안 이름: {target_name}")
    print(f"   카테고리: {args.category}")

    if dry_run:
        print("   (dry-run — 파일 변경 없음)")
        return

    # 충돌 체크
    target_path = os.path.join(pdf_dir, target_name)
    if os.path.exists(target_path) and target_path != pdf_path:
        print(f"   ⚠️  충돌: {target_name} 이미 존재 → abort. 수동 확인 후 rename 하세요.")
        sys.exit(1)

    # MD 스켈레톤 생성
    md_path = create_class_skeleton(pdf_path, target_name, doi, args.category)
    print(f"   MD 파일: {md_path}")

    # PDF 이름 변경
    if pdf_name == target_name:
        print("   PDF 이름: 이미 올바른 형식")
    else:
        os.rename(pdf_path, target_path)
        print(f"   PDF 이름: {pdf_name} → {target_name}")

    # 텍스트 추출본 저장
    txt_path = Path(pdf_dir) / "notes" / f"{Path(target_name).stem}_extracted.txt"
    txt_path.write_text(text[:50000], encoding='utf-8')
    print(f"   텍스트 추출본: {txt_path}")

    # 로그 업데이트
    log_entry = f"| CLASS | {target_name} (from {pdf_name}) | {Path(md_path).name} | ✅ Done |"
    update_log(pdf_dir, log_entry)

    print(f"✅ 완료: {target_name}")
    print(f"   → notes/ 의 MD 스켈레톤을 LLM에 전달해 내용을 채우세요.")
    print(f"   → 완성 후 {args.category}/ 폴더로 이동하세요.")


if __name__ == "__main__":
    main()
