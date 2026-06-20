# PDF → Obsidian MD Workflow

## 개요
PDF 논문을 읽고 Obsidian용 MD 노트를 생성하는 자동화 워크플로우

## 1회 설정
```bash
pip install pymupdf
```

## 사용법

### Step 0: PDF 분류 (리뷰 vs 연구)
PDF를 **리뷰 논문**과 **원저 연구**로 분류한다.

| 구분 | 파일명 접미사 | MD 노트 위치 | 스킬 |
|------|-------------|-------------|------|
| 원저 연구 | `(FirstAuthor)(Year)_(Journal).pdf` | `ko/articles/` | `SKILL.md` |
| 리뷰 논문 | `(FirstAuthor)(Year)_(Journal)**-review**.pdf` | `ko/reviews/` | `SKILL_REVIEW.md` |

**리뷰 판별 기준**: 제목·초록에 "review" 명시, "VIEWPOINT" 등 opinion 형식, 기존 문헌 종합·분석 논문

> 리뷰 논문 처리는 **`SKILL_REVIEW.md`** 참조

### Step 1: PDF 텍스트 추출 + 파일명 정리 (1회 1개 PDF)
```bash
python3 process_pdf.py <pdf_path> [--dry-run]
```
- 텍스트 추출 및 DOI/저자/저널 자동 검색
- `notes/`에 추출 텍스트 파일 + MD 스켈레톤 생성
- `notes/00_processing_log.md`에 진행 기록

> **⚠️ 주의**: `process_pdf.py`의 저자·저널 자동 추출은 **자주 실패**한다.
> - 저자 추출: PDF별 author format 편차 커서 `Unknown`으로 떨어지는 경우 많음
> - 저널 추출: 내장 저널 매핑 테이블이 매우 제한적 → mismatch 빈번
> - `--dry-run`으로 제안된 이름을 **반드시 사람이 검증**한 후 실제 rename

### Step 1b: PDF 이름 직접 수정 (권장)
`process_pdf.py`의 자동 이름 추천을 신뢰하지 말고, 추출된 텍스트에서 DOI/저자/저널을 직접 확인 후 수동 rename:

```bash
# 예시: 원저
mv "Unknown2024_Cartilage.pdf" "Zhou2024_ACSNano.pdf"
# 예시: 리뷰
mv "Unknown2015_Cartilage.pdf" "Green2015_GenesDis-review.pdf"
```

#### 이름 충돌 방지
**절대 batch rename 하지 말 것.** `process_pdf.py`는 서로 다른 PDF에 동일한 이름을 추천할 수 있어(저자/저널 추출 실패 시), 나중에 처리된 파일이 먼저 파일을 **조용히 덮어씀**.

→ **dry-run으로 충돌을 먼저 확인**하고, 충돌이 예상되면 1개씩 수동 처리

#### 기존 기사와 이름 중복 확인
새로 생성할 MD 파일명이 `ko/articles/` 또는 `en/articles/`에 이미 존재하는지 확인한다:

```bash
# dry-run 결과와 기존 파일 비교
for f in *.pdf; do
  target=$(python3 process_pdf.py "$f" --dry-run 2>&1 | grep "대상 이름" | awk '{print $NF}')
  base="${target%.pdf}"
  [[ -f "ko/articles/${base}.md" ]] && echo "⚠️  중복: $target (ko/articles/에 이미 존재)"
  [[ -f "en/articles/${base}.md" ]] && echo "⚠️  중복: $target (en/articles/에 이미 존재)"
done
```

중복이 발견되면 해당 PDF는 건너뛰거나 파일명을 수정한다.

### Step 2: MD 내용 생성 (LLM에 요청)
**원저 연구 논문만** 이 스킬로 처리한다. 리뷰 논문은 `SKILL_REVIEW.md`를 사용한다.

추출된 텍스트를 읽고 아래 형식으로 `ko/articles/` 에 Obsidian markdown 파일을 생성:

```
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

배치 처리 시 리뷰 논문을 걸러내려면:
```bash
# MD 생성 대상에서 리뷰 제외: *-review_extracted.txt 는 건너뜀
for f in notes/*_extracted.txt; do
  base=$(basename "$f" _extracted.txt)
  [[ "$base" == *-review ]] && echo "SKIP review: $base" && continue
  echo "PROCESS: $base"
done
```

### 배치 처리 (deprecated)
> **⚠️ 배치 처리 권장하지 않음.** 아래 이유로 PDF는 1개씩 수동 처리할 것:
> 1. 이름 충돌: 동일 target name → silent overwrite
> 2. 타임아웃: 대용량 PDF(17+ page, 고해상도 이미지)는 extract_text()에서 수 분 소요 가능
> 3. 저자/저널 오검출: batch로 처리하면 검증 누락 → `Unknown` 이름 그대로 남음
>
> 부득이 배치가 필요하다면 dry-run을 먼저 수행하고 로그에서 충돌 확인:
> ```bash
> for f in *.pdf; do python3 process_pdf.py "$f" --dry-run 2>&1 | grep "대상 이름"; done | sort | uniq -c
> ```

### Step 3: LLM 처리 메타데이터 기록

모든 MD 파일 하단에 LLM 처리 정보를 기록한다. Perspective 섹션 뒤에 `---`로 구분하여 추가:

```
---

*Processed by **{LLM_MODEL}** ({TOOL}) on {YYYY-MM-DD}*
```

예시:
```
---

*Processed by **Qwen3.6 Plus** (opencode-go) on 2026-06-20*
```

- `{LLM_MODEL}`: 사용한 LLM 모델명 (예: `Qwen3.6 Plus`, `Claude Sonnet 4`, `GPT-4o`) — 도구명과 구분하여 정확한 모델명 기재
- `{TOOL}`: 사용한 도구 (예: `opencode-go`, `Claude Code`)
- `{YYYY-MM-DD}`: 처리 완료일

목적: (1) 노트 생성에 사용된 LLM 추적, (2) 향후 업데이트 시 동일 모델로 일관성 유지, (3) vault의 provenance 기록.

```bash
# 개별 파일
printf '\n---\n\n*Processed by **Qwen3.6 Plus** (opencode-go) on 2026-06-20*\n' >> articles/filename.md

# 배치 추가
for f in {ko,en}/articles/*.md; do
  printf '\n---\n\n*Processed by **%s** (%s) on %s*\n' "$MODEL" "$TOOL" "$DATE" >> "$f"
done
```

### Step 4: Commit & Push

```bash
# tools submodule (변경 있을 때)
cd tools && git add -A && git commit -m "..." && git push origin main && cd ..

# vault
git add -A && git commit -m "{action}: {lang} {description}" && git push origin main
```

commit 메시지 형식: `{action}: {lang} {description}` (예: `add: en Wu2021_NatComm`, `edit: ko Haseeb2021_PNAS`)

## 파일 구조
```
ko/pdf/
├── (FirstAuthor)(Year)_(Journal).pdf        # 원저 연구
└── (FirstAuthor)(Year)_(Journal)-review.pdf # 리뷰 논문
ko/articles/
└── (FirstAuthor)(Year)_(Journal).md         # 원저 연구 노트 (이 스킬)
ko/reviews/
└── (FirstAuthor)(Year)_(Journal).md         # 리뷰 노트 (SKILL_REVIEW.md)
en/articles/
└── (FirstAuthor)(Year)_(Journal).md         # 영어 번역 (원저만)
```

각 MD 파일의 최종 구조:
```
# Title
## Citation (NLM)
...
## Background
...
## Key Experiment Methods
...
## Results
...
## Perspective
...
---
*Processed by **{LLM}** ({Tool}) on {date}*
```

## 주의사항 (Batch Processing Lessons)
- **덮어쓰기 위험**: 동일 target name이 추천되면 조용히 덮어씀 → dry-run 필수
- **리뷰 구분**: 리뷰 논문은 `-review.pdf` 접미사, `ko/reviews/`에 별도 생성 (`SKILL_REVIEW.md` 참조)
- **저자 추출 한계**: PDF별 author format 편차 큼 → 반드시 DOI로 논문 조회 후 직접 확인
- **저널 매핑 한계**: `process_pdf.py`의 저널 prefix 매핑은 주요 저널 위주로만 되어 있음 (Science → Development 등 오류 발생). DOI prefix 확인 후 수동 보정 필요
- **대용량 PDF 타임아웃**: 15+ 페이지 PDF는 텍스트 추출에 수 분 소요 → extract_text()에 페이지 제한 고려
- **2개 언어 디렉토리**: MD 노트는 `{lang}/articles/`에 생성 (en/ko bilingual mirror)
- `process_pdf.py`의 자동 추천 이름은 **참고용**으로만 사용하고, 최종 파일명은 사람이 직접 결정
- **bilingual mirror 필수**: 원저 연구는 항상 `ko/articles/`와 `en/articles/` 쌍으로 생성
