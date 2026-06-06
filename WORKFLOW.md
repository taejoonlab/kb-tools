# PDF → Obsidian MD Workflow

## 개요
PDF 논문을 읽고 Obsidian용 MD 노트를 생성하는 자동화 워크플로우

## 1회 설정
```bash
pip install pymupdf
```

## 사용법

### Step 1: PDF 텍스트 추출 + 파일명 정리
```bash
python3 process_pdf.py <pdf_path> [--dry-run]
```
- 텍스트 추출 및 DOI/저자/저널 자동 검색
- `(FirstAuthor)(Year)_(Journal).pdf` 형식으로 PDF 이름 변경
- `notes/`에 MD 스켈레톤 + 추출 텍스트 파일 생성
- `notes/00_processing_log.md`에 진행 기록

### Step 2: MD 내용 생성 (LLM에 요청)
모든 PDF 처리 후 아래 프롬프트로 LLM에 요청:

```
다음 추출된 텍스트를 읽고 Obsidian markdown 파일을 생성해줘.
형식은 아래 예시를 따라줘:

# 논문 제목

## Citation (NLM)
저자. 제목. 저널. 연도;권(호):쪽. doi:xxx

**DOI:** [URL](URL)

---

## Background
(연구 배경, 문제 제기)

---

## Key Experiment Methods
(주요 실험 방법)

---

## Results
(주요 결과)

---

## Perspective
(의의, 한계, 향후 과제)

참고 텍스트 파일: notes/<paper>_extracted.txt
```

### 배치 처리
```bash
# 모든 PDF 처리 (dry-run)
for f in *.pdf; do python3 process_pdf.py "$f" --dry-run; done

# 실제 처리
for f in *.pdf; do python3 process_pdf.py "$f"; done
```

## 파일 구조
```
obsidian-pdf/
├── process_pdf.py            # 자동화 스크립트
├── rename_pdfs.sh            # 이름 변경 bash 스크립트
├── (FirstAuthor)(Year)_(Journal).pdf   # 정리된 PDF
├── notes/
│   ├── 00_processing_log.md  # 처리 현황
│   ├── (FirstAuthor)(Year)_(Journal).md          # MD 노트
│   └── (FirstAuthor)(Year)_(Journal)_extracted.txt  # 추출 텍스트
```

## 기존 예시
- `notes/Haseeb2021_PNAS.md`
- `notes/Kozhemyakina2015_Development.md`
