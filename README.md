# kb-tools

PDF → Obsidian MD 변환 도구 모음. [kb-chondro](https://github.com/taejoonlab/kb-chondro) Obsidian vault 용 논문 처리 워크플로우를 제공한다.

## 파일 구조

```
tools/
├── process_pdf.py           # PDF 텍스트 추출 + DOI/저자/저널 자동 검색 + 파일명 정리
├── doi_journal_map.json     # DOI prefix → 저널 약어 매핑 테이블
├── WORKFLOW.md              # PDF 처리 워크플로우 상세 가이드
└── README.md                # 이 파일
```

## 주요 기능

### process_pdf.py

PyMuPDF 기반 PDF 처리 스크립트.

```bash
python3 process_pdf.py <pdf_path> [--dry-run]
```

**기능:**
- PyMuPDF로 텍스트 추출 (최대 30 페이지)
- DOI 자동 검색
- CrossRef API 조회로 저자명 추출 (네트워크 필요, 실패 시 regex fallback)
- DOI prefix 매핑으로 저널명 자동 식별 (`doi_journal_map.json`)
- 리뷰 논문 자동 판별 (VIEWPOINT, Review Article 등) → `-review` 접미사
- 대상 파일명 충돌 감지 (기존 파일 존재 시 abort)
- `notes/`에 추출 텍스트 + MD 스켈레톤 생성

**출력:**
```
ko/pdf/
├── FirstAuthor2024_Journal.pdf          # 원저 연구
├── FirstAuthor2024_Journal-review.pdf   # 리뷰 논문
└── notes/
    ├── FirstAuthor2024_Journal_extracted.txt  # 추출 텍스트
    └── FirstAuthor2024_Journal.md             # MD 스켈레톤
```

### doi_journal_map.json

DOI prefix와 전체 저널명에서 약어로의 매핑 테이블. 새 저널 추가 시 이 파일만 수정하면 된다.

## 설치

```bash
pip install pymupdf
```

## kb-chondro 에서 사용하기

### 1. Submodule로 추가

```bash
git submodule add git@github.com:taejoonlab/kb-tools.git tools
```

### 2. Clone 시 함께 가져오기

```bash
git clone --recurse-submodules git@github.com:taejoonlab/kb-chondro.git
```

### 3. 이미 clone한 경우

```bash
git submodule update --init --recursive
```

### 4. Submodule 업데이트

```bash
git submodule update --remote tools
cd tools && git pull origin main
cd .. && git add tools && git commit -m "update: tools submodule"
```

## 워크플로우

상세한 사용법은 [WORKFLOW.md](WORKFLOW.md) 참조.

간략 요약:
1. **분류**: 리뷰 vs 원저 판별
2. **추출**: `process_pdf.py`로 텍스트 추출 + 파일명 정리 (dry-run 먼저)
3. **검증**: 제안된 이름이 기존 `ko/articles/`, `en/articles/`와 중복되지 않는지 확인
4. **생성**: LLM으로 MD 노트 작성 (원저만)
5. **번역**: ko → en 영어 번역
6. **메타데이터**: 각 MD 파일 하단에 LLM 처리 정보 기록
7. **커밋**: `{action}: {lang} {description}` 형식
