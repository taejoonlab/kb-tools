<!--
trigger:  원저 연구 논문 PDF 1개를 Obsidian MD 노트로 변환할 때
input:    PDF 파일 경로 ({lang}/pdf/*.pdf, -review 접미사 없는 것)
output:   {lang}/articles/{Author}{Year}_{Journal}.md
          {lang}/pdf/notes/{stem}_extracted.txt
script:   process_pdf.py
related:  SKILL_REVIEW.md (리뷰 논문), SKILL_CLASS.md (수업용), SKILL_MONTHLY.md (대량 처리),
          SKILL_RAWDATA.md (raw-data accession / RawDataAvailable 태그)
-->

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

### Companion Files: Supplement (-sm) / News (-news)

일부 PDF는 원저 연구의 **추가 자료(Supplement)** 또는 **소개 글(Brief/News/News & Views/Comment)** 이다.
이런 경우 다음 규칙으로 처리한다:

| 유형 | 접미사 | 예시 | 설명 |
|------|--------|------|------|
| Supplement | `-sm` | `Gillmore2021_NEJM_ATTR-Intellia-sm.pdf` | Supplementary Appendix, Supporting Information 등 원 논문의 부속 자료 |
| News/Comment | `-news` | `Conti2018_GenomeMedicine-news.pdf` | 특정 논문을 소개/해설하는 Brief, News & Views, Comment, Editorial |

**식별 기준**:
- `-sm`: 첫 페이지에 "Supplementary Appendix", "Supporting Information", "This appendix has been provided…" 명시
- `-news`: 첫 페이지에 "COMMENT", "News & Views", "Editorial summary" 등의 라벨

**Extract 병합 규칙**:
- Companion 파일의 추출 텍스트는 **원 논문의 extract에 추가(append)** 한다.
- 최종 extract는 원 논문을 기준으로 하나의 파일로 통합된다.
- `notes/` 내 extract 파일에서 `===== [SM] ... =====` 또는 `===== [NEWS] ... =====` 구분자로 병합 내용을 확인할 수 있다.

**파일명 규칙**:
- Supplement: 원 논문의 파일명에 `-sm`을 추가 (`{MainStem}-sm.pdf`)
- News/Comment: 원 논문의 파일명에 `-news`를 추가 (`{MainStem}-news.pdf`)
- 여러 논문을 참조하는 Comment의 경우, 가장 관련된 논문의 extract에 병합

### Step 1: PDF 텍스트 추출 + 파일명 정리 (1회 1개 PDF)
```bash
python3 process_pdf.py <pdf_path> [--dry-run]
```
- 텍스트 추출 및 DOI/저자/저널 자동 검색
- `notes/`에 추출 텍스트 파일 + MD 스켈레톤 생성
- `notes/00_processing_log.md`에 진행 기록

> **타임아웃**: `extract_text(pdf_path, max_pages=30, timeout=120)`은 **항상** SIGALRM 타임아웃
> (기본 120초)을 적용한다. `process_pdf.py`를 CLI로 쓰든, `extract_text()`를 직접 import해서
> 쓰든 손상·초대형 PDF에서 무한 대기하지 않고 `ProcessingTimeout`을 던진다. 배치 스크립트에서
> 직접 호출할 때도 별도 alarm을 걸 필요 없이 `try/except ProcessingTimeout`로 개별 PDF를 건너뛰면
> 된다. (메인 스레드가 아니면 SIGALRM 미지원이라 타임아웃은 자동 생략된다.)

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

### Tag 입력 필수
MD 파일 생성 전, **반드시 태그(읽은 년월, YYYY-MM 형식)를 입력**받는다.
- `process_pdf.py`가 자동으로 프롬프트를 띄우며, Enter 시 오늘 날짜 기준 태그가 설정된다.
- YAML frontmatter에 `tags: [YYYY-MM]` 형식으로 포함된다.

추출된 텍스트를 읽고 아래 형식으로 `ko/articles/` 에 Obsidian markdown 파일을 생성:

```
---
tags: [YYYY-MM]                          # raw data 자가 기탁 시 RawDataAvailable 추가
extract: YYYY-MM-DD
extract_file: extract/YYYY-MM-DD_pNN.txt
raw_data:                                # (선택) self-deposited accession만, 없으면 생략
  - "GEO: GSE######"
log:
  - "YYYY-MM-DD · create · <Model> (<Tool>)"
---

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

---

## Data Availability
(본문에 raw-data accession이 있을 때만. self/cited 구분해 기재 — SKILL_RAWDATA.md 참조)

참고 텍스트 파일: `extract_file` frontmatter가 가리키는 파일 (아래 "추출 텍스트 통합·분할" 참조)
```

### extract_file 필수
frontmatter에 `extract_file`을 기록하여 노트↔원문 추출 텍스트를 연결한다.
- 값은 통합 추출본(분할 시 해당 part 파일)의 경로: `extract/YYYY-MM-DD_pNN.txt`
- 해당 파일 안에서 `===== <note-stem> =====` 앵커로 이 논문 블록을 찾을 수 있다.

### log 필수 (에이전트 변경 이력)
frontmatter의 `log`는 **에이전트가 노트를 생성/수정할 때마다 한 줄씩 append**하는 변경 이력이다.
- 형식: `"<YYYY-MM-DD> · <action> · <Model> (<Tool>)[ · <변경내용>]"` (예: `create`, `edit`, `rename`, `retag`)
- 구분자는 `·` 사용(`:` 은 YAML 오파싱 유발하므로 피함), 오래된 순으로 아래에 추가, 기존 항목은 절대 수정하지 않음
- 최초 생성 시 `create` 항목 1개로 시작한다. 사람용 provenance footer(`*Processed by …*`)와 별개로, `log`는 기계 판독용 변경 이력이다.

### Raw-data accession (RawDataAvailable) — 권장
추출 텍스트에 GEO/SRA/ENA/DDBJ/PRIDE-ProteomeXchange/ArrayExpress/MassIVE accession이 있으면
노트에 기록한다. **이 논문이 직접 기탁한(self-deposited) 데이터**만 `raw_data:` frontmatter와
`RawDataAvailable` 태그로 표시하고, **인용·재사용(cited) accession**은 본문 `## Data Availability`
섹션에만 구분해 넣는다. 판정 신호구·형식·`scan_accessions.py` 사용법은 **`SKILL_RAWDATA.md`** 참조.
en/ko 미러 양쪽에 동일하게 반영하고 `log`에 edit 항목을 append한다.

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
> 2. 타임아웃: 대용량 PDF(17+ page, 고해상도 이미지)는 extract_text()에서 오래 걸릴 수 있음 —
>    `extract_text`가 기본 120초에서 `ProcessingTimeout`을 던지므로, 배치에서는 이를 잡아 개별 PDF를 건너뛴다
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
ko/pdf/                                              # 미처리 PDF (gitignore)
├── (FirstAuthor)(Year)_(Journal)_(Keyword).pdf      # 원저 연구
├── (FirstAuthor)(Year)_(Journal)-review.pdf         # 리뷰 논문
├── (FirstAuthor)(Year)_(Journal)-sm.pdf             # Supplement (부속 자료)
├── (FirstAuthor)(Year)_(Journal)-news.pdf           # News/Comment (소개 글)
├── done/                                            # 노트 완료된 PDF (노트 stem 이름으로)
│   ├── (FirstAuthor)(Year)_(Journal)_(Keyword).pdf  # 원저·뉴스
│   └── review/(FirstAuthor)(Year)_(Journal)_(Keyword).pdf  # 리뷰
└── notes/                                           # 작업 아티팩트 (gitignore)
ko/articles/
└── (FirstAuthor)(Year)_(Journal)_(Keyword).md       # 원저 연구 노트 (이 스킬)
ko/reviews/
└── (FirstAuthor)(Year)_(Journal)_(Keyword).md       # 리뷰 노트 (SKILL_REVIEW.md)
en/articles/
└── (FirstAuthor)(Year)_(Journal)_(Keyword).md       # 영어 번역 (원저만)
extract/                                             # 통합 추출 텍스트 (git tracked)
└── (YYYY-MM-DD)_pNN.txt                             # 날짜별, ~2MB 단위 분할
```

**파일명**: `_(Keyword)` 주제 접미사를 붙이는 것을 권장한다(여러 단어는 `+`로 연결, 예 `Anderson2016_Nature_SCI+Mouse+Astrocytes`). 저널은 표준 약어 사용.

**추출 텍스트 통합·분할**:
- 노트를 작성한 논문들의 추출 텍스트를 날짜별 `extract/YYYY-MM-DD.txt` 하나로 통합한다(git tracked).
- 파일이 커지면(수 MB) `extract/YYYY-MM-DD_pNN.txt`로 분할한다.
- 각 논문 블록의 앵커는 **노트 stem**으로 한다: `===== <note-stem> =====` (노트의 `extract_file`이 가리키는 part에서 이 앵커로 검색).

**PDF 정리(done)**:
- 노트를 작성한 PDF는 `{lang}/pdf/done/`으로 옮기고 노트 stem 이름으로 rename한다(리뷰는 `done/review/`).
- 프로젝트 범위 밖이라 노트를 만들지 않은 PDF는 `{lang}/pdf/`에 남겨 별도 검토한다.

**Companion 파일 처리 요약**:
- Supplement(`-sm`)와 News/Comment(`-news`)는 PDF 파일명에 접미사를 추가하여 표시
- Extract 텍스트는 원 논문의 extract 파일(`notes/{stem}_extracted.txt`)에 병합
- 독립형 뉴스(News Highlights, Market Reports 등)는 `(Journal)(Year)-news-(Keyword).pdf` 형식으로 별도 관리

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
## Data Availability          # raw-data accession이 있을 때만 (SKILL_RAWDATA.md)
...
---
*Processed by **{LLM}** ({Tool}) on {date}*
```

## 주의사항 (Batch Processing Lessons)
- **덮어쓰기 위험**: 동일 target name이 추천되면 조용히 덮어씀 → dry-run 필수
- **리뷰 구분**: 리뷰 논문은 `-review.pdf` 접미사, `ko/reviews/`에 별도 생성 (`SKILL_REVIEW.md` 참조)
- **저자 추출 한계**: PDF별 author format 편차 큼 → 반드시 DOI로 논문 조회 후 직접 확인
- **저널 매핑 한계**: `process_pdf.py`의 저널 prefix 매핑은 주요 저널 위주로만 되어 있음 (Science → Development 등 오류 발생). DOI prefix 확인 후 수동 보정 필요
- **대용량 PDF 타임아웃**: `extract_text(pdf_path, max_pages=30, timeout=120)`은 항상 SIGALRM 타임아웃(기본 120초)을 적용해 손상·초대형 PDF에서 무한 대기하지 않고 `ProcessingTimeout`을 던진다. 필요 시 `timeout`/`max_pages` 인자로 조정
- **2개 언어 디렉토리**: MD 노트는 `{lang}/articles/`에 생성 (en/ko bilingual mirror)
- `process_pdf.py`의 자동 추천 이름은 **참고용**으로만 사용하고, 최종 파일명은 사람이 직접 결정
- **bilingual mirror 필수**: 원저 연구는 항상 `ko/articles/`와 `en/articles/` 쌍으로 생성

## 품질 검증 (Metadata/Content QA) — 2026-07 kb-taejoon 감사에서 도출

파이프라인(예: GLM-5.1/opencode-go)이 생성한 노트에서 반복적으로 발견되는 메타데이터·본문 오류. 배치 처리 후 반드시 아래를 점검한다.

- **파일명 저자 = given name 오기**: citation의 `## Citation (NLM)` 제1저자 **성(surname)**이 정답. 예) "Lu Chih-Hao"인데 파일명 `Chih...`, "van de Kooij Bert"인데 `Bert...`. 복합 성은 소문자 결합(`vandeKooij`, `diLillo`, `deMenezes`).
- **placeholder 저자**: `ATCC`, `Unknown`, `Authors`, `This`, 저널명(`Nature`), 국가명 등 → citation에서 실제 저자로 rename.
- **연도 오류**: citation 연도가 정답이며 DOI 슬러그(`10.1038/s41586-026`=2026)로 교차 확인. 단 DOI가 오추출일 수 있으니 citation과 충돌 시 보류.
- **BROKEN_CIT**: citation이 `AUTHORS_PLACEHOLDER`거나 제목이 PDF 헤더 잡음("SCIE N C E A D V A NCES") → Crossref(`api.crossref.org/works/<DOI>` 또는 `?query.bibliographic=`)로 제목·citation·DOI 복구.
- **BODY_CORRUPT**: 제목/citation과 본문(Methods/Results)이 서로 다른 논문. **"citation=정답" 가정 금지** — 파일명+키워드+본문 다수결로 어느 쪽이 오염인지 판단(citation이 오염인 경우도 있음).
- **DOI가 다른 논문을 가리킴**: 중복/오염 노트에서 DOI가 실제와 다른 논문으로 연결될 수 있음 → 제목으로 Crossref 재조회해 실제 DOI 확정.
- **저널 토큰 정리(DOI 기준)**: DOI 접두사 → 표준 토큰 매핑(`doi_journal_map.json`)으로 파일명 저널 토큰 대조. 주의: coarse 접두사가 자매지를 병합함(`10.1093/nar`가 NAR Cancer=`narcan`/NAR Genom Bioinform=`nargab`까지, `10.1016/j.stem`이 Stem Cell Reports=`j.stemcr`까지). longest-prefix 우선 + 자매지 override 필요. 동일 저널 약어 변형만 자동 수정, 교차 저널은 citation로 개별 확인, 프리프린트(bioRxiv)·의도적 접미사(`Nature-Cas12a2`)는 제외.
- 참조 구현: kb-taejoon 리포의 `scripts/fix_journal_tokens.py`(+`scripts/journal_overrides.json`), `scripts/tag_needreview.py`. 자동 해결 불가 노트는 `Need4Review` 태그로 검토 큐 관리.
