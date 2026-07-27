<!--
trigger:  방법 프로토콜 논문 PDF 1개를 Obsidian MD 노트로 변환할 때
          (파일명에 -protocol 접미사, 또는 저널이 Nature Protocols / STAR Protocols /
           Methods in Molecular Biology / Current Protocols / Bio-protocol / JoVE 등 프로토콜 전문지)
input:    PDF 파일 경로 ({lang}/pdf/*-protocol.pdf 또는 프로토콜 전문지 PDF)
output:   {lang}/protocols/{Author}{Year}_{Journal}_{Keyword}.md
          {lang}/pdf/notes/{stem}_extracted.txt
script:   process_pdf.py --no-rename --output-dir {lang}/protocols/
related:  SKILL.md (원저 연구), SKILL_REVIEW.md (리뷰 논문), SKILL_CLASS.md (수업용),
          SKILL_MONTHLY.md (대량 처리), SKILL_RAWDATA.md (raw-data accession / RawDataAvailable 태그)
-->

# PDF → Obsidian Protocol MD Workflow

## 개요
**방법 프로토콜 논문** PDF를 읽고 Obsidian용 MD 노트를 생성하는 워크플로우.
원저 연구(`SKILL.md`)·리뷰(`SKILL_REVIEW.md`)와 달리, 새로운 발견이나 문헌 종합이 아니라
**재현 가능한 실험/분석 절차 자체**에 초점을 맞춘다.

- 원저 연구 노트 → `ko/articles/` (`SKILL.md`)
- 리뷰 노트 → `ko/reviews/` (`SKILL_REVIEW.md`)
- **프로토콜 노트 → `ko/protocols/`** (이 스킬)

## 프로토콜 판별 기준
- **저널**: Nature Protocols, STAR Protocols, Methods in Molecular Biology, Current Protocols,
  Bio-protocol, JoVE 등 프로토콜 전문지
- **형식**: "Protocol", "Step-by-step", "Procedure", "Timing", "Troubleshooting", "Anticipated results"
  등 절차 중심 구성
- **계산 도구 논문**(소프트웨어 튜토리얼·분석 파이프라인)도 절차(how-to) 중심이면 프로토콜로 분류
  (예: CellChat·CellPhoneDB의 Nature Protocols 논문)
- **애매할 때**: 새 발견 중심이면 `articles/`, 방법 재현(how-to) 중심이면 `protocols/`.
  프로토콜 전문지 게재본은 기본적으로 `protocols/`.

## 1회 설정
```bash
pip install pymupdf
```

## 사용법 (2단계 파이프라인)

### Phase 1 (Python): 텍스트 추출 + 파일명 정리
파일명이 이미 `(FirstAuthor)(Year)_(Journal)-protocol.pdf` 형식으로 확정돼 있다면
`--no-rename` 과 `--output-dir` 을 지정한다.

```bash
python3 tools/process_pdf.py ko/pdf/Author2024_Journal-protocol.pdf \
  --no-rename \
  --output-dir ko/protocols/
```

실행 결과:
- `ko/pdf/notes/Author2024_Journal-protocol_extracted.txt` — 추출 텍스트
- `extract/YYYY-MM-DD_pNN.txt` — 추출 텍스트 (날짜별 통합, git tracked)
- `ko/protocols/Author2024_Journal.md` — TODO 스켈레톤

> **⚠️ `process_pdf.py`는 MD 스켈레톤만 생성**한다 (TODO placeholder).
> 실제 상세 요약은 Phase 2에서 LLM이 처리한다.

### Phase 2 (LLM): 추출 텍스트 → 상세 프로토콜 노트

`ko/pdf/notes/Author2024_Journal-protocol_extracted.txt` 를 읽고
아래 형식으로 `ko/protocols/Author2024_Journal.md` 를 작성한다.

**LLM 처리 지시** (프론트매터 규칙은 `SKILL.md`의 "Tag 입력 필수 / extract_file 필수 / log 필수" 참조):

**프로토콜 노트 형식 (원저·리뷰와 다름)**:

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

# 프로토콜 전체 제목

## Citation (NLM)
저자. 제목. 저널. 연도;권(호):쪽. doi:xxx

**DOI:** [URL](URL)

---

## Overview
(프로토콜의 목적·배경·해결하는 문제·적용 범위를 2~4문단으로 상세히)

---

## Materials & Setup
(핵심 시약·세포·장비 등 준비물. 계산 프로토콜이면 필요한 입력 데이터·소프트웨어 의존성·실행 환경)

---

## Procedure
(단계별 절차를 stage 단위로 번호 매겨 정리. 각 stage의 핵심 파라미터·소요 시간(Timing)·핵심 조작을 구체적으로)

---

## Applications & Expected Results
(이 프로토콜이 적용되는 실험/분석 유형과 대표 출력·예상 결과·검증 지표)

---

## Notes & Troubleshooting
(흔한 실패 지점, 한계, 최적화 팁, 대안 방법과의 비교)

---

## Perspective
(프로토콜의 의의, 분야에서의 위치, 향후 발전 방향)

## Data Availability          # raw-data accession이 있을 때만 (SKILL_RAWDATA.md)
```

**각 섹션 작성 지침**:

| 섹션 | 작성 포인트 |
|------|------------|
| Overview | 프로토콜의 목적·적용 범위·해결하는 문제 |
| Materials & Setup | 시약/세포/장비, 또는 계산 프로토콜이면 입력 데이터·의존성·실행 환경 |
| Procedure | stage별 절차, 핵심 파라미터, 소요 시간(Timing), 핵심 조작 |
| Applications & Expected Results | 활용 사례, 대표 출력, 예상 결과, 검증 지표 |
| Notes & Troubleshooting | 흔한 실패 지점, 한계, 최적화 팁, 대안 비교 |
| Perspective | 의의, 분야에서의 위치, 향후 |

**Data Availability (선택)**: 추출 텍스트에 raw-data accession이 있으면 `## Data Availability` 섹션을
**Perspective 뒤**에 추가한다. 프로토콜이 예시 데이터를 직접 기탁했다면 self 항목과 `RawDataAvailable`
태그·`raw_data:` frontmatter를 부여하고, 인용·재사용(cited)만 있으면 섹션에만 구분해 넣는다.
형식·판정은 **`SKILL_RAWDATA.md`** 참조.

### Step 3: LLM 처리 메타데이터 기록

Perspective(또는 Data Availability) 섹션 뒤에 `---` 구분선과 함께 추가:

```
---

*Processed by **{LLM_MODEL}** ({TOOL}) on {YYYY-MM-DD}*
```

### Step 4: Commit & Push

```bash
# tools submodule (변경 있을 때)
cd tools && git add -A && git commit -m "..." && git push origin main && cd ..

# vault
git add ko/protocols/ && git commit -m "add: ko protocol Author2024_Journal_Keyword"
git push origin main
```

commit 메시지 형식: `add: ko protocol {Author}{Year}_{Journal}_{Keyword}`

## 파일 구조

```
ko/pdf/
└── Author2024_Journal-protocol.pdf        # 원본 PDF (gitignore)
ko/pdf/done/protocol/
└── Author2024_Journal_Keyword.pdf         # 노트 완료 후 이동 (노트 stem 이름, gitignore)
ko/pdf/notes/
└── Author2024_Journal-protocol_extracted.txt   # 추출 텍스트 (gitignore)
ko/protocols/
└── Author2024_Journal_Keyword.md          # 최종 프로토콜 노트 (tracked)
extract/
└── (YYYY-MM-DD)_pNN.txt                    # 통합 추출 텍스트, 앵커 ===== <note-stem> ===== (tracked)
```

- frontmatter에 `extract_file`을 기록해 노트↔추출 텍스트를 연결한다(`SKILL.md` "extract_file 필수" 참조).
- 노트 작성 후 프로토콜 PDF는 `{lang}/pdf/done/protocol/`로 옮기고 노트 stem 이름으로 rename한다.

**파일명**: MD 파일명에 `_(Keyword)` 주제 접미사는 **필수**다(여러 단어는 `+`로 연결,
예 `Jin2025_NatProtoc_CellChat+Protocol+CellCommunication`). 원저(`SKILL.md`)와 동일한 규칙을
적용하며, PDF의 `-protocol` 접미사는 MD 파일명에는 포함하지 않는다.

최종 MD 파일 구조:
```
# Title
## Citation (NLM)
...
## Overview
...
## Materials & Setup
...
## Procedure
...
## Applications & Expected Results
...
## Notes & Troubleshooting
...
## Perspective
...
## Data Availability          # raw-data accession이 있을 때만 (SKILL_RAWDATA.md)
...
---
*Processed by **{LLM}** ({Tool}) on {date}*
```

## 원저·리뷰 노트와의 비교

| 항목 | 원저 (`SKILL.md`) | 리뷰 (`SKILL_REVIEW.md`) | 프로토콜 (이 스킬) |
|------|-----------------|------------------------|------------------|
| 출력 위치 | `ko/articles/` | `ko/reviews/` | `ko/protocols/` |
| PDF 파일명 접미사 | 없음 | `-review` | `-protocol` |
| process_pdf.py 옵션 | 기본 (`--dry-run` 권장) | `--no-rename --output-dir ko/reviews/` | `--no-rename --output-dir ko/protocols/` |
| 섹션 구조 | Background / Key Experiment Methods / Results / Perspective | Overview / Key Topics / Key Findings / Perspective / Key References | Overview / Materials & Setup / Procedure / Applications & Expected Results / Notes & Troubleshooting / Perspective |
| 내용 초점 | 발견·결과 중심 | 분야 종합 + 참고 문헌 | 재현 가능한 절차(how-to) 중심 |
| bilingual mirror | (현재 vault는 `ko`만 생성) | 없음 (ko만) | 없음 (ko만) |

## 주의사항

- **판별 애매 시**: 새 발견 중심이면 article, 방법 재현(how-to) 중심이면 protocol
- **계산 프로토콜**: Materials & Setup에 소프트웨어 버전·의존성·입력 데이터·실행 환경을 명시
- **`-protocol` 접미사**: 노트 파일명에는 붙이지 않음 (PDF만 붙임)
- **bilingual mirror 불필요**: 프로토콜 노트는 `ko/protocols/`만 생성
- **파일명 자동 추출 실패 빈번**: `process_pdf.py` 결과를 PDF 파일명·DOI와 반드시 대조 후 교정
