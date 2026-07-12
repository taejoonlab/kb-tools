# KB-Tools Skills Index

어떤 SKILL 파일을 사용할지 결정하는 진입점.
각 SKILL 파일 상단의 `<!-- trigger / input / output -->` 헤더에서 상세 조건을 확인한다.

## 태스크별 SKILL 선택

| 상황 | SKILL 파일 | 스크립트 |
|------|-----------|---------|
| 원저 연구 PDF 1개 처리 | [SKILL.md](SKILL.md) | `process_pdf.py` |
| 리뷰 논문 PDF 1개 처리 | [SKILL_REVIEW.md](SKILL_REVIEW.md) | `process_pdf.py` |
| 수업 참고 논문 PDF 1개 처리 | [SKILL_CLASS.md](SKILL_CLASS.md) | `process_pdf_class.py` |
| PDF 수십~수백 개 일괄 처리 | [SKILL_MONTHLY.md](SKILL_MONTHLY.md) | `process_pdf.py` (반복) |
| 완성된 노트를 GitHub Wiki에 게시 | [SKILL_WIKI.md](SKILL_WIKI.md) | (git 수동) |

## 노트 타입별 MD 섹션 비교

| 섹션 | ARTICLE | REVIEW | CLASS |
|------|:-------:|:------:|:-----:|
| Background | ✅ | — | — |
| Key Experiment Methods | ✅ | — | — |
| Results | ✅ | — | — |
| Overview | — | ✅ | — |
| Key Topics | — | ✅ | — |
| Key Findings | — | ✅ | — |
| Summary | — | — | ✅ |
| Significance in Intro Context | — | — | ✅ |
| Perspective | ✅ | ✅ | — |
| Key References (DOI 링크) | — | ✅ | ✅ |
| Future Research Directions | — | — | ✅ |

## 파일명 형식

| 타입 | PDF 파일명 | MD 파일명 | 출력 위치 |
|------|----------|---------|---------|
| ARTICLE | `Author2024_Journal.pdf` | `Author2024_Journal.md` | `{lang}/articles/` |
| REVIEW | `Author2024_Journal-review.pdf` | `Author2024_Journal.md` | `{lang}/reviews/` |
| CLASS | `Author2024_Journal_Keyword.pdf` | `Author2024_Journal_Keyword.md` | `{lang}/others/` → `{lang}/{category}/` |

## 논문 타입 판단 기준

```
리뷰 논문 (SKILL_REVIEW.md)
  → 제목·초록에 "Review Article", "VIEWPOINT", "Minireview" 명시
  → 기존 문헌을 종합·분석하는 논문

수업 참고 논문 (SKILL_CLASS.md)
  → 수업(BME333/BIO333 등)에서 직접 읽히는 논문
  → 교과서적 중요도를 가진 seminal paper

원저 연구 (SKILL.md)
  → 위 두 경우에 해당하지 않는 실험 연구 논문
```

## 공통 워크플로우

```
1. PDF 분류: 원저 / 리뷰 / 수업용  →  SKILL 선택
2. dry-run: python3 tools/process_pdf[_class].py <pdf> --dry-run
3. 파일명 검증 후 실제 실행
4. LLM에 추출 텍스트 전달 → MD 내용 생성
5. 노트를 올바른 {lang}/{category}/ 폴더로 이동
6. bilingual mirror: ko ↔ en 쌍 생성
7. commit & push
```

## 스크립트 의존성

```bash
pip install pymupdf   # 공통 필수
```

인터넷 연결 필요: CrossRef API (저자명·저널명 자동 조회, 실패 시 regex fallback).
