# kb-tools

PDF → Obsidian MD processing toolkit for the [kb-chondro](https://github.com/taejoonlab/kb-chondro) research literature vault.

## File Structure

```
tools/
├── process_pdf.py           # PDF text extraction + DOI/author/journal auto-detection + file renaming
├── doi_journal_map.json     # DOI prefix → journal abbreviation mapping table
├── SKILL.md                 # Detailed PDF processing workflow guide
└── README.md                # This file
```

## Features

### process_pdf.py

PyMuPDF-based PDF processing script.

```bash
python3 process_pdf.py <pdf_path> [--dry-run]
```

**Capabilities:**
- Text extraction via PyMuPDF (max 30 pages)
- Automatic DOI detection
- First author lookup via CrossRef API (requires network; falls back to regex)
- Journal identification via DOI prefix mapping (`doi_journal_map.json`)
- Automatic review article detection (VIEWPOINT, Review Article, etc.) → `-review` suffix
- Target filename collision detection (aborts if file already exists)
- Generates extracted text + MD skeleton in `notes/`

**Output:**
```
ko/pdf/
├── FirstAuthor2024_Journal.pdf          # Original research
├── FirstAuthor2024_Journal-review.pdf   # Review article
└── notes/
    ├── FirstAuthor2024_Journal_extracted.txt  # Extracted text
    └── FirstAuthor2024_Journal.md             # MD skeleton
```

### doi_journal_map.json

External mapping table for DOI prefixes and full journal names to abbreviations. To add a new journal, edit this file only — no code changes required.

## Installation

```bash
pip install pymupdf
```

## Setup as a Submodule

### Add to an existing repo

```bash
git submodule add git@github.com:taejoonlab/kb-tools.git tools
```

### Clone with submodules

```bash
git clone --recurse-submodules git@github.com:taejoonlab/kb-chondro.git
```

### Initialize after cloning without submodules

```bash
git submodule update --init --recursive
```

### Update the submodule

```bash
git submodule update --remote tools
cd tools && git pull origin main
cd .. && git add tools && git commit -m "update: tools submodule"
```

## Workflow

See [SKILL.md](SKILL.md) for the full guide.

Quick summary:
1. **Classify**: Distinguish review vs. original research articles
2. **Extract**: Run `process_pdf.py` with `--dry-run` first, then process
3. **Verify**: Check that suggested filenames don't collide with existing `ko/articles/` or `en/articles/`
4. **Generate**: Use an LLM to write MD notes (original research only)
5. **Translate**: Create English versions in `en/articles/`
6. **Metadata**: Append processing info (LLM model, tool, date) to each MD file
7. **Commit**: Use `{action}: {lang} {description}` format (e.g., `add: en Wu2021_NatComm`)
