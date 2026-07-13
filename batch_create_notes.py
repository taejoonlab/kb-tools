#!/usr/bin/env python3
"""Create MD notes for all PDFs without existing notes.
Tags: 2026-07-CINDELA, Extract: 2026-07-13-CINDELA
"""
import sys, os, re, json, signal, time, urllib.request
from pathlib import Path

VAULT = Path(__file__).parent.parent
ARTICLES = VAULT / "ko/articles"
REVIEWS = VAULT / "ko/reviews"
PDF_DIR = VAULT / "ko/pdf"
NOTES_DIR = PDF_DIR / "notes"

TAG = "2026-07-CINDELA"
EXTRACT_DATE = "2026-07-13-CINDELA"

_map_file = VAULT / "tools" / "doi_journal_map.json"
with open(_map_file) as f:
    _data = json.load(f)
DOI_PREFIX_MAP = {}
for cat, prefixes in _data.get("doi_prefix_map", {}).items():
    DOI_PREFIX_MAP.update(prefixes)


def crossref_lookup(doi):
    try:
        url = f"https://api.crossref.org/works/{doi}"
        req = urllib.request.Request(url, headers={"User-Agent": "kbtools/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read())
            m = d.get("message", {})
            title = (m.get("title") or [""])[0]
            authors = m.get("author", [])
            author_list = "; ".join(
                f"{a.get('family','')} {a.get('given','')}" for a in authors[:5]
            )
            if len(authors) > 5:
                author_list += " et al."
            container = (m.get("container-title") or [""])[0]
            pub = m.get("published-print",{}).get("date-parts",[[None]])[0] or \
                  m.get("published-online",{}).get("date-parts",[[None]])[0] or \
                  m.get("issued",{}).get("date-parts",[[None]])[0]
            year = str(pub[0]) if pub and pub[0] else ""
            vol = m.get("volume", "") or ""
            issue = m.get("issue", "") or ""
            pages = m.get("page", "") or ""
            return {"title": title, "authors": author_list, "journal": container,
                    "year": year, "volume": vol, "issue": issue, "pages": pages}
    except:
        return None


def extract_doi(text):
    for pat in [r'(?:doi|DOI)\s*[:\s]*\s*(10\.\d{4,}/[^\s,;]+)', r'doi\.org/(10\.\d{4,}/[^\s,;]+)']:
        m = re.search(pat, text)
        if m:
            return m.group(1).rstrip('.,/?')
    m = re.search(r'(10\.\d{4,}/[^\s,;\]]+)', text[:3000])
    if m:
        return m.group(1).rstrip('.,/?')
    return None


def clean_text(text, max_chars=3000):
    """Clean and truncate text for summaries."""
    t = re.sub(r'\s+', ' ', text).strip()
    return t[:max_chars]


def extract_title(text):
    """Extract title from first meaningful lines."""
    lines = text.split('\n')
    for line in lines[:30]:
        s = line.strip()
        if not s or len(s) < 15:
            continue
        # Skip boilerplate
        if re.match(r'^(article|research|report|review|letter|brief|comment|editorial|resource|nature|science|cell)', s, re.I):
            continue
        if re.match(r'^[A-Z][a-zA-Z\s\-:,/()\'"]{20,}', s):
            return s[:200]
    # Fallback: first long line
    for line in lines[:30]:
        s = line.strip()
        if len(s) > 30:
            return s[:200]
    return "TITLE_PLACEHOLDER"


def get_sections(text):
    """Extract key paragraphs for sections."""
    lines = text.split('\n')
    
    background = ""
    methods = ""
    results = ""
    perspective = ""
    
    current_section = "intro"
    section_text = []
    
    section_keywords = {
        'background': r'\b(introduction|background)\b',
        'methods': r'\b(methods?|experimental|procedures?|protocol|material|assay)\b',
        'results': r'\b(results?|findings?|observation|we found|we show|we demonstrate)\b',
        'discussion': r'\b(discussion|conclusion|perspective|significance|implications?|future)\b',
    }
    
    in_abstract = False
    
    for line in lines[:500]:
        s = line.strip()
        if not s or len(s) < 10:
            continue
        
        s_lower = s.lower()
        
        # Detect abstract
        if re.match(r'^abstract\b', s_lower):
            in_abstract = True
            continue
        
        # Detect section changes
        for section, pattern in section_keywords.items():
            if re.match(pattern, s_lower) and len(s) < 80:
                current_section = section
                break
        
        if in_abstract and len(s) > 20:
            section_text.append(s)
            if re.search(r'\.\s*(keywords?|introduction|©|copyright)', s_lower):
                in_abstract = False
                current_section = "intro"
    
    # Extract background from abstract/intro
    abstract_text = " ".join(section_text[:15]) if section_text else ""
    if abstract_text:
        background = abstract_text[:2000]
    
    # If no structured sections, extract key content
    if not background:
        # Get abstract
        for i, line in enumerate(lines[:100]):
            s = line.strip()
            if re.match(r'^abstract', s.lower()) and i+1 < len(lines):
                abstract_parts = []
                for j in range(i+1, min(i+30, len(lines))):
                    ls = lines[j].strip()
                    if not ls or len(ls) < 5:
                        if len(abstract_parts) > 3:
                            break
                        continue
                    abstract_parts.append(ls)
                background = " ".join(abstract_parts[:15])[:2000]
                break
    
    # Get results from key paragraphs
    result_lines = []
    for line in lines[:200]:
        s = line.strip()
        if len(s) > 40 and re.search(r'(we|our|these|the)\s+(show|demonstrate|find|report|identify|reveal|indicate|suggest)', s, re.I):
            result_lines.append(s)
            if len(result_lines) >= 5:
                break
    
    if result_lines:
        results = " ".join(result_lines)[:2000]
    
    # Get perspective from discussion/conclusion
    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r'^(discussion|conclusion)', s.lower()) and len(s) < 30:
            discuss_parts = []
            for j in range(i+1, min(i+25, len(lines))):
                ls = lines[j].strip()
                if not ls:
                    if len(discuss_parts) > 3:
                        break
                    continue
                discuss_parts.append(ls)
            if discuss_parts:
                perspective = " ".join(discuss_parts[:10])[:2000]
            break
    
    return background, methods, results, perspective


def create_article_note(pdf_name, text):
    """Create detailed article note."""
    doi = extract_doi(text)
    cr = crossref_lookup(doi) if doi else None
    
    title = cr["title"] if cr and cr["title"] else extract_title(text)
    authors = cr["authors"] if cr and cr["authors"] else "AUTHORS_PLACEHOLDER"
    journal = cr["journal"] if cr and cr["journal"] else ""
    year = cr["year"] if cr and cr["year"] else ""
    vol = cr["volume"] if cr else ""
    iss = cr["issue"] if cr else ""
    pages = cr["pages"] if cr else ""
    
    # Build NLM citation
    citation = f"{authors}. {title}. {journal}."
    if year: citation += f" {year}"
    if vol: citation += f";{vol}"
    if iss: citation += f"({iss})"
    if pages: citation += f":{pages}"
    if doi: citation += f" doi:{doi}"
    
    bg, meth, res, persp = get_sections(text)
    
    md = f"""---
tags: [{TAG}]
extract: {EXTRACT_DATE}
---

# {title}

## Citation (NLM)
{citation}

**DOI:** [{f'https://doi.org/{doi}' if doi else '#'}]({f'https://doi.org/{doi}' if doi else '#'})

---

## Background

{bg if bg else 'TODO'}

---

## Key Experiment Methods

{meth if meth else 'TODO — 주요 실험 방법 및 접근법'}

---

## Results

{res if res else 'TODO — 핵심 결과 요약 (그림/표 포함)'}

---

## Perspective

{persp if persp else 'TODO — 의의, 한계, 향후 연구 방향'}

---

*Processed by **GLM-5.1** (opencode-go) on 2026-07-13*
"""
    return md


def create_review_note(pdf_name, text):
    """Create detailed review note."""
    doi = extract_doi(text)
    cr = crossref_lookup(doi) if doi else None
    
    title = cr["title"] if cr and cr["title"] else extract_title(text)
    authors = cr["authors"] if cr and cr["authors"] else "AUTHORS_PLACEHOLDER"
    journal = cr["journal"] if cr and cr["journal"] else ""
    year = cr["year"] if cr and cr["year"] else ""
    vol = cr["volume"] if cr else ""
    iss = cr["issue"] if cr else ""
    pages = cr["pages"] if cr else ""
    
    citation = f"{authors}. {title}. {journal}."
    if year: citation += f" {year}"
    if vol: citation += f";{vol}"
    if iss: citation += f"({iss})"
    if pages: citation += f":{pages}"
    if doi: citation += f" doi:{doi}"
    
    bg, meth, res, persp = get_sections(text)
    
    md = f"""---
tags: [{TAG}]
extract: {EXTRACT_DATE}
---

# {title}

## Citation (NLM)
{citation}

**DOI:** [{f'https://doi.org/{doi}' if doi else '#'}]({f'https://doi.org/{doi}' if doi else '#'})

---

## Overview

{bg if bg else 'TODO — 리뷰 주제 및 배경, 목적'}

---

## Key Topics

TODO — 리뷰에서 다루는 주요 주제별 정리

---

## Key Findings

{res if res else 'TODO — 핵심 내용 및 결론'}

---

## Perspective

{persp if persp else 'TODO — 의의, 한계, 향후 연구 방향'}

---

*Processed by **GLM-5.1** (opencode-go) on 2026-07-13*
"""
    return md


def main():
    # Get existing notes
    existing_articles = {f.replace('.md','') for f in os.listdir(str(ARTICLES)) if f.endswith('.md')}
    existing_reviews = {f.replace('.md','') for f in os.listdir(str(REVIEWS)) if f.endswith('.md')}
    
    pdfs = sorted([f for f in os.listdir(str(PDF_DIR)) if f.endswith('.pdf') and f != 'notes'])
    
    created = 0
    skipped = 0
    errors = 0
    
    for pdf_name in pdfs:
        stem = pdf_name.replace('.pdf', '')
        
        # Skip companion files
        if '-news-' in pdf_name or pdf_name.endswith('-news.pdf') or pdf_name.endswith('-sm.pdf') or '_dup.pdf' in pdf_name:
            skipped += 1
            continue
        
        # Determine if article or review
        is_review = '-review.pdf' in pdf_name
        note_stem = stem.replace('-review', '') if is_review else stem
        target_dir = REVIEWS if is_review else ARTICLES
        
        # Check if note already exists
        existing = existing_reviews if is_review else existing_articles
        if note_stem in existing:
            skipped += 1
            continue
        
        # Read extracted text
        extract_path = NOTES_DIR / f"{stem}_extracted.txt"
        if not extract_path.exists():
            print(f"  [SKIP] no extract: {pdf_name}")
            skipped += 1
            continue
        
        text = extract_path.read_text(encoding='utf-8')
        if not text.strip():
            print(f"  [SKIP] empty extract: {pdf_name}")
            skipped += 1
            continue
        
        # Create MD content
        try:
            if is_review:
                md_content = create_review_note(pdf_name, text)
            else:
                md_content = create_article_note(pdf_name, text)
        except Exception as e:
            print(f"  [ERROR] {pdf_name}: {e}")
            errors += 1
            continue
        
        # Write MD file
        md_path = target_dir / f"{note_stem}.md"
        md_path.write_text(md_content, encoding='utf-8')
        print(f"  [{'REVIEW' if is_review else 'ARTICLE'}] {note_stem}.md")
        created += 1
    
    print(f"\n=== Done ===")
    print(f"Created: {created}, Skipped: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    main()
