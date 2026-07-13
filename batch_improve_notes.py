#!/usr/bin/env python3
"""Second pass: Fill in TODO sections with better content extraction."""
import re, os
from pathlib import Path

VAULT = Path(__file__).parent.parent
ARTICLES = VAULT / "ko/articles"
REVIEWS = VAULT / "ko/reviews"
PDF_DIR = VAULT / "ko/pdf"
NOTES_DIR = PDF_DIR / "notes"


def extract_text_from_pdf(stem):
    """Read extracted text for given stem."""
    # Try exact stem first
    p = NOTES_DIR / f"{stem}_extracted.txt"
    if p.exists():
        return p.read_text(encoding='utf-8')
    # Try with -review
    p = NOTES_DIR / f"{stem}-review_extracted.txt"
    if p.exists():
        return p.read_text(encoding='utf-8')
    return ""


def get_sections(text):
    """Extract text sections by analyzing document structure."""
    lines = text.split('\n')
    
    abstract = ""
    in_abstract = False
    abstract_lines = []
    
    methods = ""
    in_methods = False
    methods_lines = []
    
    results = ""
    in_results = False
    results_lines = []
    
    discussion = ""
    in_discussion = False
    discussion_lines = []
    
    intro_lines = []
    all_content = []
    
    for i, line in enumerate(lines[:600]):
        s = line.strip()
        if not s: continue
        sl = s.lower()
        
        # Detect ABSTRACT
        if re.match(r'^abstract\b', sl) and len(s) < 30:
            in_abstract = True; in_methods = False; in_results = False; in_discussion = False
            continue
        
        # Detect INTRODUCTION
        if re.match(r'^introduction\b', sl) and len(s) < 30:
            in_abstract = False; in_methods = False; in_results = False; in_discussion = False
            continue
        
        # Detect METHODS
        if re.match(r'^(methods?|materials?\s+(and|&)\s+methods?|experimental\s+procedures?|experimental\s+design)', sl) and len(s) < 35:
            in_methods = True; in_abstract = False; in_results = False; in_discussion = False
            continue
        
        # Detect RESULTS
        if re.match(r'^(results?|findings?|outcomes?)\b', sl) and len(s) < 25:
            in_results = True; in_abstract = False; in_methods = False; in_discussion = False
            continue
        
        # Detect DISCUSSION / CONCLUSION
        if re.match(r'^(discussion|conclusion|perspective|summary|closing\s+remarks)', sl) and len(s) < 30:
            in_discussion = True; in_abstract = False; in_methods = False; in_results = False
            continue
        
        # Collect content based on current section
        if in_abstract and len(s) > 15:
            abstract_lines.append(s)
        elif in_methods and len(s) > 15:
            methods_lines.append(s)
        elif in_results and len(s) > 15:
            results_lines.append(s)
        elif in_discussion and len(s) > 15:
            discussion_lines.append(s)
        elif not in_abstract and not in_methods and not in_results and not in_discussion and len(s) > 20:
            # Early intro text
            if not any(kw in s for kw in ['©', 'copyright', 'www.', 'http', 'correspondence', 'email', '@']):
                intro_lines.append(s)
    
    # If no abstract found, look for text before first section header
    if not abstract_lines:
        for line in lines[:80]:
            s = line.strip()
            if len(s) > 40 and not any(kw in s.lower() for kw in ['received', 'accepted', 'published', 'copyright', '©', 'doi:', 'correspondence', 'email']):
                abstract_lines.append(s)
                if len(abstract_lines) >= 8:
                    break
    
    if abstract_lines: abstract = " ".join(abstract_lines[:12])
    if methods_lines: methods = " ".join(methods_lines[:10])
    if results_lines: results = " ".join(results_lines[:10])
    if discussion_lines: discussion = " ".join(discussion_lines[:10])
    
    return abstract, methods, results, discussion


def improve_note(md_path, text):
    """Improve an MD note by filling in TODOs."""
    if not md_path.exists():
        return False
    
    content = md_path.read_text(encoding='utf-8')
    if 'TODO' not in content:
        return False  # Already complete
    
    abstract, methods, results, discussion = get_sections(text)
    
    changed = False
    
    # Replace TODO in Background
    if 'TODO' in content.split('## Background')[1].split('---')[0] if '## Background' in content else '':
        if abstract:
            content = content.replace(
                '## Background\n\nTODO\n\n---',
                f'## Background\n\n{abstract}\n\n---', 1
            )
            changed = True
        elif '## Background\n\nTODO' in content:
            content = content.replace('## Background\n\nTODO', '## Background\n\n' + (abstract or 'TODO'))
            changed = True
    
    # Replace TODO in Methods
    if methods and '## Key Experiment Methods' in content:
        old = content.split('## Key Experiment Methods')[1].split('---')[0] if '## Key Experiment Methods' in content else ''
        if 'TODO' in old:
            content = content.replace(
                '## Key Experiment Methods\n\nTODO — 주요 실험 방법 및 접근법\n\n---',
                f'## Key Experiment Methods\n\n{methods}\n\n---', 1
            )
            changed = True
    
    # Replace TODO in Results
    if results and '## Results' in content:
        old = content.split('## Results')[1].split('---')[0] if '## Results' in content else ''
        if 'TODO' in old:
            content = content.replace(
                '## Results\n\nTODO — 핵심 결과 요약 (그림/표 포함)\n\n---',
                f'## Results\n\n{results}\n\n---', 1
            )
            changed = True
    
    # Replace TODO in Perspective
    if discussion and '## Perspective' in content:
        old = content.split('## Perspective')[1].split('---')[-2] if '## Perspective' in content else ''
        if 'TODO' in old:
            # Find and replace the Perspective section
            content = re.sub(
                r'## Perspective\n\nTODO[^#]*',
                f'## Perspective\n\n{discussion}\n\n',
                content
            )
            changed = True
    
    # For reviews: fill Overview with abstract
    if abstract and '## Overview' in content:
        if 'TODO' in content.split('## Overview')[1].split('---')[0] if '## Overview' in content else '':
            content = content.replace(
                '## Overview\n\nTODO — 리뷰 주제 및 배경, 목적\n\n---',
                f'## Overview\n\n{abstract}\n\n---', 1
            )
            changed = True
    
    # For reviews: fill Key Findings with results+discussion
    if (results or discussion) and '## Key Findings' in content:
        if 'TODO' in content.split('## Key Findings')[1].split('---')[0] if '## Key Findings' in content else '':
            kf = (results + ' ' + discussion)[:2000]
            content = content.replace(
                '## Key Findings\n\nTODO — 핵심 내용 및 결론\n\n---',
                f'## Key Findings\n\n{kf}\n\n---', 1
            )
            changed = True
    
    if changed:
        md_path.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    improved = 0
    no_text = 0
    unchanged = 0
    
    # Process articles
    for f in sorted(os.listdir(str(ARTICLES))):
        if not f.endswith('.md') or f == '.gitkeep': continue
        md_path = ARTICLES / f
        stem = f.replace('.md', '')
        text = extract_text_from_pdf(stem)
        if not text:
            no_text += 1
            continue
        if improve_note(md_path, text):
            improved += 1
        else:
            unchanged += 1
    
    # Process reviews
    for f in sorted(os.listdir(str(REVIEWS))):
        if not f.endswith('.md') or f == '.gitkeep': continue
        md_path = REVIEWS / f
        stem = f.replace('.md', '')
        text = extract_text_from_pdf(stem)
        if not text:
            no_text += 1
            continue
        if improve_note(md_path, text):
            improved += 1
        else:
            unchanged += 1
    
    print(f"Improved: {improved}")
    print(f"Unchanged (no TODOs or no extract): {unchanged}")
    print(f"No matching extract found: {no_text}")


if __name__ == "__main__":
    main()
