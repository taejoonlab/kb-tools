# PDF → Obsidian Review MD Workflow

## 개요
리뷰 논문 PDF를 읽고 Obsidian용 MD 노트를 생성하는 워크플로우.
원저 연구 노트(`SKILL.md`)와 달리 전반적인 내용 종합 + 핵심 참고 문헌 링크를 포함한다.

- 원저 연구 노트 → `ko/articles/` (`SKILL.md` 참조)
- **리뷰 노트 → `ko/reviews/`** (이 스킬)

## 1회 설정
```bash
pip install pymupdf
```

## 사용법

### Step 1: 텍스트 추출 (리뷰 PDF 전용 옵션)

파일명이 이미 `(FirstAuthor)(Year)_(Journal)-review.pdf` 형식으로 확정되어 있으므로
`--no-rename` 과 `--output-dir` 을 반드시 지정한다.

```bash
# 단일 파일
python3 tools/process_pdf.py ko/pdf/Author2024_Journal-review.pdf \
  --no-rename \
  --output-dir ko/reviews/

# 배치 (전체 review PDF)
for f in ko/pdf/*-review.pdf; do
  python3 tools/process_pdf.py "$f" \
    --no-rename \
    --output-dir ko/reviews/
done
```

실행 결과:
- `ko/reviews/Author2024_Journal.md` — 리뷰 전용 스켈레톤 생성 (`-review` 접미사 제거)
- `ko/pdf/notes/Author2024_Journal-review_extracted.txt` — 추출 텍스트 저장
- `ko/pdf/notes/00_processing_log.md` — 처리 이력 기록

> **⚠️ 파일명 교정 필수**: `process_pdf.py`의 저자·저널 자동 추출은 자주 실패한다.
> `ko/reviews/` 에 생성된 스켈레톤 파일명이 원본 PDF명과 다르면 수동으로 교정한다.
> ```bash
> # PDF 파일명 기준으로 교정 예시
> mv ko/reviews/Unknown2024_Unknown.md ko/reviews/Author2024_Journal.md
> mv ko/pdf/notes/Unknown2024_Unknown-review_extracted.txt \
>    ko/pdf/notes/Author2024_Journal-review_extracted.txt
> ```

### Step 2: MD 내용 생성 (LLM에 요청)

`ko/pdf/notes/Author2024_Journal-review_extracted.txt` 를 읽고
아래 형식으로 `ko/reviews/Author2024_Journal.md` 를 작성한다.

**리뷰 노트 형식 (원저와 다름)**:

```
# 논문 전체 제목

## Citation (NLM)
저자. 제목. 저널. 연도;권(호):쪽. doi:xxx

**DOI:** [URL](URL)

---

## Overview
(리뷰의 주제, 배경, 목적, 전체 범위를 2~4문단으로 상세 서술)

---

## Key Topics
(리뷰가 다루는 주요 주제를 소제목별로 정리.
 원저의 Key Experiment Methods보다 내용 위주로 서술)

---

## Key Findings
(리뷰의 핵심 결론, 중요 인사이트, 분야 현황 정리)

---

## Perspective
(의의, 한계, 향후 연구 방향)

---

## Key References
(리뷰에서 인용된 핵심 논문 목록.
 형식: - 저자 (연도) 제목. *저널* 권:쪽. [doi:xxx](URL)
 5~15개 선별, DOI 링크 필수)
```

**각 섹션 작성 지침**:

| 섹션 | 원저와의 차이 | 작성 포인트 |
|------|------------|------------|
| Overview | 원저의 Background보다 넓고 깊게 | 분야 전체 맥락, 리뷰가 다루는 범위와 목적 |
| Key Topics | 원저의 Methods 대신 | 주제별 내용 정리, 소제목 활용 |
| Key Findings | 원저의 Results보다 광범위 | 분야 현황, 대표 사례, 방법론 비교 |
| Perspective | 동일 | 의의, 한계, 향후 방향 |
| Key References | 원저에 없는 섹션 | 리뷰에서 인용한 핵심 논문, DOI 링크 필수 |

### Step 3: LLM 처리 메타데이터 기록

Key References 섹션 뒤에 `---` 구분선과 함께 추가:

```
---

*Processed by **{LLM_MODEL}** ({TOOL}) on {YYYY-MM-DD}*
```

예시:
```
---

*Processed by **Claude Sonnet 4.6** (Claude Code) on 2026-06-20*
```

### Step 4: Commit & Push

```bash
# tools submodule (변경 있을 때)
cd tools && git add -A && git commit -m "..." && git push origin main && cd ..

# vault
git add ko/reviews/ && git commit -m "add: ko review Author2024_Journal"
git push origin main
```

commit 메시지 형식: `add: ko review {Author}{Year}_{Journal}`

## 파일 구조

```
ko/pdf/
└── Author2024_Journal-review.pdf       # 원본 PDF (gitignore)
ko/pdf/notes/
└── Author2024_Journal-review_extracted.txt  # 추출 텍스트 (gitignore)
ko/reviews/
└── Author2024_Journal.md               # 최종 리뷰 노트 (tracked)
```

최종 MD 파일 구조:
```
# Title
## Citation (NLM)
...
## Overview
...
## Key Topics
...
## Key Findings
...
## Perspective
...
## Key References
...
---
*Processed by **{LLM}** ({Tool}) on {date}*
```

## 원저 노트와의 비교

| 항목 | 원저 (`SKILL.md`) | 리뷰 (`SKILL_REVIEW.md`) |
|------|-----------------|------------------------|
| 출력 위치 | `ko/articles/` | `ko/reviews/` |
| PDF 파일명 | `-review` 없음 | `-review` 접미사 |
| process_pdf.py 옵션 | 기본 (`--dry-run` 권장) | `--no-rename --output-dir ko/reviews/` |
| 섹션 구조 | Background / Key Experiment Methods / Results / Perspective | Overview / Key Topics / Key Findings / Perspective / Key References |
| 내용 깊이 | Methods·Results 중심 | 전체 내용 종합 + 참고 문헌 |
| bilingual mirror | 필수 (`en/articles/` 쌍) | 없음 (ko만) |

## 주의사항

- **파일명 자동 추출 실패 빈번**: `process_pdf.py` 결과를 PDF 파일명과 반드시 대조 후 교정
- **`-review` 접미사**: 노트 파일명에는 `-review`를 붙이지 않음 (PDF만 붙임)
- **bilingual mirror 불필요**: 리뷰 노트는 `ko/reviews/`만 생성, `en/reviews/` 없음
- **Key References DOI 링크 필수**: DOI 없는 참고 문헌은 제외하거나 저널 홈페이지 링크 대체
