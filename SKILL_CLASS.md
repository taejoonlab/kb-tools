# PDF → Obsidian CLASS MD Workflow (수업용 노트)

## 개요
수업 참고용 논문 PDF를 읽고 Obsidian MD 노트를 생성하는 워크플로우.
ARTICLE/REVIEW 스킬과 달리 수업 맥락 중심의 상세 요약, 핵심 참고문헌 DOI 링크, 후속 연구 아이디어를 포함한다.

| 스킬 | 대상 | 파일명 형식 | 출력 위치 |
|------|------|------------|---------|
| `SKILL.md` | 원저 연구 | `Author2024_Journal.pdf` | `ko/articles/` |
| `SKILL_REVIEW.md` | 리뷰 논문 | `Author2024_Journal-review.pdf` | `ko/reviews/` |
| **`SKILL_CLASS.md`** | **수업 참고 논문** | **`Author2024_Journal_Keyword.pdf`** | **`ko/{category}/`** |

카테고리: `population` / `forward` / `reverse`

## 1회 설정
```bash
pip install pymupdf
```

## 파일명 형식

```
{FirstAuthor}{Year}_{Journal}_{Keyword1}[-{Keyword2}].pdf
```

| 예시 | 설명 |
|------|------|
| `Lewontin1972_Genetics_GeneticVariation.pdf` | 키워드 1개 |
| `Nielsen2005_NatRevGenet_NaturalSelection-Adaptation.pdf` | 키워드 2개 (하이픈 구분) |

- 키워드는 CamelCase, 하이픈으로 최대 2개 연결
- 내용의 핵심 개념을 반영 (저자/저널로 구분 안 되는 주제 식별용)

## 사용법

### Step 1: PDF 텍스트 추출 + 파일명 정리

```bash
# dry-run으로 제안 이름 확인
python3 tools/process_pdf_class.py ko/pdf/paper.pdf \
  --keywords "PopulationGenetics,GeneticDrift" \
  --category population \
  --dry-run

# 실제 실행 (파일명 변경 + 스켈레톤 생성)
python3 tools/process_pdf_class.py ko/pdf/paper.pdf \
  --keywords "PopulationGenetics,GeneticDrift" \
  --category population
```

옵션:

| 옵션 | 설명 |
|------|------|
| `--keywords "kw1,kw2"` | 파일명 키워드 지정 (쉼표 구분, 최대 2개). 생략 시 제목에서 자동 추출 시도 |
| `--category` | `population` / `forward` / `reverse` (YAML frontmatter에 반영, 기본: CATEGORY) |
| `--dry-run` | 파일 변경 없이 제안 이름만 출력 |

> **⚠️ 자동 추출은 자주 실패한다.** `--dry-run`으로 확인 후 키워드는 반드시 수동 지정 (`--keywords`)할 것.

### Step 1b: PDF 이름 직접 수정 (권장)

```bash
# dry-run 결과 확인 후 수동 rename
mv "ko/pdf/Unknown2024_Unknown_KEYWORD.pdf" "ko/pdf/Lewontin1972_Genetics_GeneticVariation.pdf"
```

### Step 2: MD 내용 생성 (LLM에 요청)

`ko/pdf/notes/{stem}_extracted.txt` 를 읽고 아래 형식으로 노트를 작성한다.

```
---
tags: [genetics, class, {category}, ko]
date: YYYY-MM-DD
type: class
---

# 논문 전체 제목

## Citation (NLM)
저자. 제목. 저널. 연도;권(호):쪽. doi:xxx

**DOI:** [https://doi.org/...](https://doi.org/...)

---

## Summary

핵심 주장, 주요 데이터, 결론을 수업 이해에 초점을 맞춰 상세하게 서술.
ARTICLE의 Background/Methods/Results를 하나의 흐름으로 통합.

---

## Significance in Introduction Context

이 논문이 해당 분야의 도입부에서 갖는 의미:
- 어떤 배경 지식/전제를 제공하는가
- 어떤 논쟁 또는 패러다임 전환에 위치하는가
- 수업에서 이 논문을 읽어야 하는 이유

---

## Key References

본문에서 인용된 핵심 참고문헌 (DOI URL 포함, 5~10개 선별):

1. **AuthorA et al. (Year)** — [https://doi.org/...](https://doi.org/...) — 한 줄 설명
2. **AuthorB et al. (Year)** — [https://doi.org/...](https://doi.org/...) — 한 줄 설명

---

## Future Research Directions

이 논문에서 제기된 미해결 질문과 향후 연구 아이디어:

- 아이디어 1
- 아이디어 2

---

*Processed by **{LLM_MODEL}** ({TOOL}) on {YYYY-MM-DD}*
```

**각 섹션 작성 지침**:

| 섹션 | ARTICLE/REVIEW와의 차이 | 작성 포인트 |
|------|----------------------|------------|
| Summary | ARTICLE보다 길고 통합적 | 배경·방법·결과를 수업 맥락에서 연결, 핵심 수치/데이터 포함 |
| Significance in Introduction Context | CLASS 전용 섹션 | 분야 도입부에서의 위치, 수업 필요성 명시 |
| Key References | REVIEW의 Key References와 동일 형식 | DOI 링크 필수, 설명 1줄 |
| Future Research Directions | CLASS 전용 섹션 | 논문이 남긴 질문, 새 실험 아이디어, 기술 적용 가능성 |

### Step 3: 파일 이동 + bilingual mirror

노트 완성 후 해당 카테고리 폴더로 이동:

```bash
# ko 노트
mv ko/pdf/notes/Author2024_Journal_Keyword.md ko/{category}/Author2024_Journal_Keyword.md

# en 노트 (영어 번역 — bilingual mirror 필수)
# → 동일 파일명으로 en/{category}/ 에 영어 버전 생성
cp ko/{category}/Author2024_Journal_Keyword.md en/{category}/Author2024_Journal_Keyword.md
# (내용을 영어로 번역 후 태그 lang 변경: ko → en)
```

### Step 4: LLM 처리 메타데이터 기록

Future Research Directions 뒤 `---` 구분선 + 처리 정보:

```
---

*Processed by **{LLM_MODEL}** ({TOOL}) on {YYYY-MM-DD}*
```

### Step 5: Commit & Push

```bash
# tools submodule (변경 있을 때)
cd tools && git add -A && git commit -m "add: SKILL_CLASS, process_pdf_class" && git push origin main && cd ..

# vault
git add ko/{category}/ en/{category}/
git commit -m "add: ko/{category} Author2024_Journal_Keyword"
git push origin main
```

commit 메시지 형식: `{action}: {lang}/{category} {Author}{Year}_{Journal}_{Keyword}`

## 파일 구조

```
ko/pdf/
└── Author2024_Journal_Keyword.pdf          # 원본 PDF (gitignored)
ko/pdf/notes/
├── Author2024_Journal_Keyword_extracted.txt  # 추출 텍스트 (gitignored)
└── 00_processing_log.md
ko/{category}/
└── Author2024_Journal_Keyword.md           # 한국어 CLASS 노트 (tracked)
en/{category}/
└── Author2024_Journal_Keyword.md           # 영어 CLASS 노트 (tracked)
```

## SKILL 비교

| 항목 | ARTICLE | REVIEW | CLASS |
|------|---------|--------|-------|
| 스크립트 | `process_pdf.py` | `process_pdf.py` | `process_pdf_class.py` |
| 파일명 | `Author2024_Journal` | `Author2024_Journal-review` | `Author2024_Journal_Keyword` |
| 출력 위치 | `ko/articles/` | `ko/reviews/` | `ko/{population\|forward\|reverse}/` |
| bilingual | 필수 | 없음 | 필수 |
| 추가 섹션 | — | Key References | Significance in Intro + Key References + Future Directions |
| YAML type | (없음) | (없음) | `type: class` |

## 주의사항

- **키워드 수동 지정 권장**: `--keywords` 없이 자동 추출하면 의미없는 단어가 들어갈 수 있음
- **카테고리 필수 지정**: `--category` 를 빠뜨리면 frontmatter에 `CATEGORY` 플레이스홀더가 남음
- **Key References DOI 링크 필수**: DOI 없는 문헌은 제외하거나 저널 홈페이지 링크 대체
- **bilingual mirror 필수**: ko/en 쌍으로 생성, en 버전 tags의 `ko` → `en` 변경 잊지 말 것
- **dry-run 먼저**: 키워드 포함 파일명 충돌 가능성 있으므로 반드시 dry-run 확인 후 실행
