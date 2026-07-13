# KB-Tools Skills Index

어떤 SKILL 파일을 사용할지 결정하는 진입점.
각 SKILL 파일 상단의 `<!-- trigger / input / output -->` 헤더에서 상세 조건을 확인한다.

## 태스크별 SKILL 선택

| 상황 | SKILL 파일 | 스크립트 |
|------|-----------|---------|
| 원저 연구 PDF 1개 처리 | [SKILL.md](SKILL.md) | `process_pdf.py` |
| 리뷰 논문 PDF 1개 처리 | [SKILL_REVIEW.md](SKILL_REVIEW.md) | `process_pdf.py` |
| 수업 참고 논문 PDF 1개 처리 | [SKILL_CLASS.md](SKILL_CLASS.md) | `process_pdf_class.py` |
| PDF 수십~수백 개 일괄 처리 | [SKILL_MONTHLY.md](SKILL_MONTHLY.md) | `batch_process_pdfs.py` |
| 완성된 노트를 GitHub Wiki에 게시 | [SKILL_WIKI.md](SKILL_WIKI.md) | (git 수동) |

## 노트 타입별 MD 섹션 비교

| 섹션 | ARTICLE | REVIEW | CLASS | NEWS |
|------|:-------:|:------:|:-----:|:----:|
| Background | ✅ | — | — | — |
| Key Experiment Methods | ✅ | — | — | — |
| Results | ✅ | — | — | — |
| Overview | — | ✅ | — | — |
| Key Topics | — | ✅ | — | — |
| Key Findings | — | ✅ | — | — |
| Summary | — | — | ✅ | — |
| Key Points | — | — | — | ✅ |
| Significance in Intro Context | — | — | ✅ | — |
| Perspective | ✅ | ✅ | — | — |
| Significance | — | — | — | ✅ |
| Key References (DOI 링크) | — | ✅ | ✅ | — |
| Future Research Directions | — | — | ✅ | — |
| Related Research | — | — | — | ✅ |

## 파일명 형식

| 타입 | PDF 파일명 | MD 파일명 | 출력 위치 |
|------|----------|---------|---------|
| ARTICLE | `Author2024_Journal.pdf` | `Author2024_Journal.md` | `{lang}/articles/` |
| REVIEW | `Author2024_Journal-review.pdf` | `Author2024_Journal.md` | `{lang}/reviews/` |
| CLASS | `Author2024_Journal_Keyword.pdf` | `Author2024_Journal_Keyword.md` | `{lang}/{category}/` |
| NEWS | `Journal2024-news-Keyword.pdf` | `Journal2024-news-Keyword.md` | `{lang}/news/` |
| Supplement | `Author2024_Journal-sm.pdf` | — (extract만 병합) | — |
| Companion | `Author2024_Journal-news.pdf` | — (extract만 병합) | — |

## 논문 타입 판단 기준

```
리뷰 논문 (SKILL_REVIEW.md)
  → 제목·초록에 "Review Article", "VIEWPOINT", "Minireview" 명시
  → 기존 문헌을 종합·분석하는 논문

수업 참고 논문 (SKILL_CLASS.md)
  → 수업(BME333/BIO333 등)에서 직접 읽히는 논문
  → 교과서적 중요도를 가진 seminal paper

뉴스 (news)
  → d41573/d41586/d43747 등 Nature 출판사의 독립형 뉴스
  → Research Highlights, News & Analysis, News in Brief
  → 포맷: (Journal)(Year)-news-(Keyword)

원저 연구 (SKILL.md)
  → 위 경우에 해당하지 않는 실험 연구 논문
```

## 공통 워크플로우 (2단계 파이프라인)

```
[Phase 1 - Python] 텍스트 추출 + 파일명 정리 (확정적, 빠름)
   process_pdf.py / batch_process_pdfs.py
   → PDF → _extracted.txt (ko/pdf/notes/)
   → PDF → AuthorYear_Journal.pdf (파일명 정리)

[Phase 2 - LLM] 추출된 텍스트 → 상세 MD 노트 생성 (지능적)
   Task agent가 ko/pdf/notes/*_extracted.txt 읽고
   → ko/articles/ (또는 reviews/, news/)에 MD 작성
   → tags, extract date 포함
```

## 스크립트 의존성

```bash
pip install pymupdf   # 공통 필수 (Phase 1)
```

인터넷 연결 필요: CrossRef API (저자명·저널명 자동 조회, 실패 시 regex fallback).

## `extract/` 디렉토리 관리

- `extract/YY-MM-DD.txt`는 모든 PDF의 원시 추출 텍스트가 누적되는 파일
- **git에 포함됨** (`.gitignore` 제외 대상 아님) — 이후 grep 등 검색용으로 보존
- **모니터링 기준**: 200MB 초과 시 조치 고려
  - 옵션 1: extract 파일을 날짜별로 분할 유지 (현재 방식 유지)
  - 옵션 2: `extract/`를 별도 submodule로 분리
  - 옵션 3: `git gc --aggressive`로 pack 최적화
- **체크 명령어**: `du -sh extract/ && find extract/ -name "*.txt" -exec wc -c {} + | tail -1`
