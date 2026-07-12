<!--
trigger:  수십~수백 개의 PDF를 한 번에 일괄 처리할 때
input:    {lang}/pdf/ 아래의 PDF 파일들
output:   {lang}/articles/*.md, {lang}/reviews/*.md
          {lang}/pdf/notes/*_extracted.txt
script:   process_pdf.py (반복 실행)
related:  SKILL.md (단일 원저), SKILL_REVIEW.md (단일 리뷰)
note:     경로 예시는 {VAULT}={vault 루트 절대경로}, {lang}=ko|en 으로 치환하여 사용
-->

# Monthly Batch PDF → Obsidian MD Workflow

## 개요
많은 수(수십~수백)의 PDF를 한 번에 처리할 때의 워크플로우.
**① PDF 분류 → ② 파일명 정리 → ③ MD 내용 생성** 3단계로 구성되며, 각 단계를 소단위(chunk)로 나누어 진행한다.

## 핵심 원칙
1. **한 번에 1 chunk씩**: 전체를 동시에 처리하지 않고 15-20개씩 chunk로 나눠 순차 처리
2. **chunk 단위 검증**: 각 chunk 완료 후 파일명·분류(article/review)가 올바른지 확인
3. **subagent는 1회 1개만**: 병렬 subagent는 최대 2개로 제한 (너무 많으면 에러 추적 불가)
4. **dry-run 필수**: 실제 rename 전에 `--dry-run`으로 충돌·오류를 먼저 확인

## 작업 흐름

```
Step 0: PDF 목록 수집
Step 1: Dry-run (전체)
Step 2: Chunk 단위 rename + MD 스켈레톤 생성
Step 3: Chunk 단위 MD 내용 채우기
Step 4: 검증 및 commit
```

---

## Step 0: PDF 목록 수집

```bash
ls ko/pdf/*.pdf > /tmp/all_pdfs.txt
wc -l /tmp/all_pdfs.txt
```

이미 올바른 형식의 파일명을 가진 PDF를 식별한다:
```bash
# 이미 FirstAuthorYYYY_Journal 형식인 파일 확인
ls ko/pdf/*_[0-9][0-9][0-9][0-9]_*.pdf 2>/dev/null
# 이미 -review.pdf 형식 확인
ls ko/pdf/*-review.pdf 2>/dev/null
```

---

## Step 1: Dry-run (전체 한 번에)

`process_pdf.py`로 현재 PDF들의 제안된 이름과 문제점을 한눈에 확인:

```bash
cd {VAULT}/ko/pdf   # {VAULT}를 vault 루트 절대경로로 치환

for f in *.pdf; do
  result=$(python3 ../../tools/process_pdf.py "$f" --dry-run 2>&1)
  suggested=$(echo "$result" | grep "대상 이름" | awk '{print $NF}')
  dtype=$(echo "$result" | grep "유형" | sed 's/.*유형: //')
  doi=$(echo "$result" | grep "DOI:" | head -1 | sed 's/.*DOI: //')
  echo "$f | $dtype | $suggested | $doi"
done > /tmp/dryrun_report.txt
```

**dry-run 결과에서 다음 문제를 확인**:

| 문제 | 확인 방법 | 조치 |
|------|----------|------|
| 이름 충돌 | `awk '{print $3}' /tmp/dryrun_report.txt \| sort \| uniq -c \| sort -rn \| head` | 충돌 나는 PDF는 다른 chunk로 분리하거나 수동 처리 |
| Unknown 저자 | `grep "Unknown[0-9]" /tmp/dryrun_report.txt` | 해당 PDF는 DOI로 저자 확인 필요 |
| Unknown 저널 | `grep "Unknown.pdf" /tmp/dryrun_report.txt` | 해당 PDF는 DOI prefix로 저널 확인 필요 |
| 리뷰 오판별 | `grep "리뷰" /tmp/dryrun_report.txt` | 실제 리뷰 여부 확인 |
| 연도 오류 | `grep -E "20[0-9]{2}_" /tmp/dryrun_report.txt` | 연도가 2020-2029 범위인지 확인 |

**dry-run 결과 저장** (참고용):
```bash
cat /tmp/dryrun_report.txt
```

---

## Step 2: Chunk 단위 rename + MD 스켈레톤 생성

### chunk 분할

```bash
# 148개 → 8개 chunk (각 18-19개)
cd ko/pdf
ls *.pdf > /tmp/all.txt
split -l 19 /tmp/all.txt /tmp/chunk_
ls /tmp/chunk_*
```

또는 수동으로 chunk 리스트를 작성:

```bash
# 수동 chunk 예시 (첫 번째 chunk)
CHUNK1="
file1.pdf
file2.pdf
..."
```

### 각 chunk 처리

각 chunk를 **1개씩 순차 처리**한다:

```bash
# chunk 파일 목록 읽기
cat /tmp/chunk_aa | while read f; do
  echo "=== $f ==="
  python3 ../../tools/process_pdf.py "$f" --dry-run 2>&1 | grep -E "대상 이름|유형|DOI"
  echo ""
done
```

문제가 없으면 실제 rename 실행:

```bash
cat /tmp/chunk_aa | while read f; do
  python3 ../../tools/process_pdf.py "$f" 2>&1
done
```

### 파일명 보정

`process_pdf.py`가 자주 실패하는 항목을 수동으로 확인하고 보정:

```bash
# 동일한 target name이 추천된 경우 확인
ls ko/pdf/*Unknown* 2>/dev/null
```

**수동 보정 예시**:

```bash
# 저자명이 Unknown으로 잘못 추출된 경우
python3 -c "
import fitz, re, json
doc = fitz.open('ko/pdf/FILENAME.pdf')
text = ''
for page in doc[:3]:
  text += page.get_text()
# DOI 찾기
doi = re.search(r'(10\.\d{4,}/[^\s,;\]]+)', text)
print('DOI:', doi.group(1) if doi else 'N/A')
# 첫 페이지 텍스트 출력 (저자 정보 확인)
print(text[:1000])
"
```

**저자명 확인이 필요한 경우 CrossRef API 조회**:

```bash
# DOI가 있으면
DOI="10.1038/s41467-026-xxxxx"
curl -s "https://api.crossref.org/works/$DOI" | python3 -c "
import sys, json
data = json.load(sys.stdin)
author = data['message']['author'][0]
print('First author:', author.get('family', ''))
print('Year:', data['message'].get('published-print', {}).get('date-parts', [[None]])[0][0])
print('Journal:', data['message'].get('container-title', [''])[0])
"
```

**잘못된 파일명 수정**:

```bash
# 저자·저널·연도 수정
mv "ko/pdf/Unknown2025_Unknown.pdf" "ko/pdf/Chen2025_NatCommun.pdf"

# -review 누락
mv "ko/pdf/Loeser2012_ArthritisRheum.pdf" "ko/pdf/Loeser2012_ArthritisRheum-review.pdf"
```

### chunk 검증

각 chunk 완료 후 확인:

```bash
echo "=== PDFs ===" && ls ko/pdf/*.pdf | wc -l
echo "=== Unknown in filename ===" && ls ko/pdf/*Unknown* 2>/dev/null || echo "(none)"
echo "=== MD skeletons ===" && ls ko/pdf/notes/*.md 2>/dev/null | wc -l
```

**chunk별 확인해야 할 항목**:

| 확인 사항 | 방법 |
|----------|------|
| 파일명에 Unknown 없음 | `ls ko/pdf/*Unknown*` |
| PDF-MD 파일명 일치 | `ls ko/pdf/notes/*.md \| sed 's/.md$/.pdf/' \| xargs -I{} bash -c 'basename {} .md'` |
| 리뷰 PDF에 -review 있음 | `ls ko/pdf/*-review.pdf \| wc -l` |
| 중복 이름 없음 | `ls ko/pdf/*.pdf \| sed 's/.*\///' \| sort \| uniq -d` |
| 올바른 연도 범위 | `ls ko/pdf/ | grep -oP '[12][09]\d{2}' \| sort` |

문제가 없으면 다음 chunk로 이동. 문제가 있으면 현재 chunk를 먼저 수정.

---

## Step 3: Chunk 단위 MD 내용 채우기

### 추출 텍스트 확인

```bash
# extracted text 파일이 있는지 확인
for f in ko/pdf/notes/*_extracted.txt; do
  size=$(wc -c < "$f")
  [ "$size" -lt 100 ] && echo "⚠️  Too small: $f ($size bytes)"
done

# 없거나 너무 작은 파일은 PDF에서 직접 추출
python3 -c "
import fitz
doc = fitz.open('ko/pdf/Author2025_Journal.pdf')
text = ''
for page in doc[:10]:
  text += page.get_text()
with open('ko/pdf/notes/Author2025_Journal_extracted.txt', 'w') as f:
  f.write(text)
print(f'Saved {len(text)} chars')
"
```

### LLM 내용 생성 (subagent 사용)

MD 파일을 생성할 때는 **1회에 1개 subagent(최대 15-20개 파일)**로 제한:

```bash
# chunk당 15-20개 파일씩, subagent 1개만 실행
# chunk aa: 19 files (파일명 리스트)
# chunk ab: 19 files
# ...
```

**subagent 태스크 내용에 포함할 사항**:

```
1. 다음 19개 MD 파일의 내용을 채워주세요.
2. 각 MD 파일의 extracted text는 ko/pdf/notes/{basename}_extracted.txt 에서 읽으세요.
3. extracted text가 없으면 PDF에서 직접 텍스트를 추출하세요.
4. 모든 내용은 한국어로 작성합니다.
5. 제목은 영어 원문을 유지합니다.
6. Citation은 NLM 형식을 사용합니다.
7. 다음 형식으로 작성:
   - ko/articles/: Background → Key Experiment Methods → Results → Perspective
   - ko/reviews/: Overview → Key Topics → Key Findings → Perspective → Key References
8. footer 필수: *Processed by **{MODEL}** ({TOOL}) on {YYYY-MM-DD}*
```

**subagent 실행 전 체크리스트**:

- [ ] 대상 MD 파일의 개수가 15-20개 이내인가?
- [ ] 모든 파일에 extracted text 파일이 존재하는가?
- [ ] 리뷰 파일은 ko/reviews/로 경로가 올바른가?
- [ ] PDF 파일명과 MD 파일명의 basename이 일치하는가?

### subagent 완료 후 검증

```bash
echo "=== TODO 남은 파일 ==="
grep -rl "TODO" ko/articles/ ko/reviews/ | wc -l
grep -rl "TODO" ko/articles/ ko/reviews/

echo "=== footer 없는 파일 ==="
grep -rL "Processed by" ko/articles/ ko/reviews/
```

**에러 발생 시 대응**:

| 에러 | 원인 | 대응 |
|------|------|------|
| subagent 응답 없음 | 타임아웃 | chunk를 더 작게 나누어 재시도 (10개 이하) |
| extracted text 없음 | process_pdf 실패 | PDF에서 직접 추출 후 재시도 |
| 내용이 깔끔하지 않음 | 텍스트 추출 불량 | 해당 PDF 수동 처리 |
| 잘못된 분류 (article/review) | process_pdf 오판별 | 수동으로 MD 파일 이동 및 분류 수정 |

---

## Step 4: 최종 검증 및 commit

### 통합 검증

```bash
# 1. 모든 MD에 TODO 없음
echo "TODO remaining: $(grep -rl 'TODO' ko/articles/ ko/reviews/ | wc -l)"

# 2. 모든 MD에 footer 있음
echo "Without footer: $(grep -rL 'Processed by' ko/articles/ ko/reviews/ | wc -l)"

# 3. PDF-MD 매칭 확인
echo "=== PDF without MD ==="
for f in ko/pdf/*.pdf; do
  base=$(basename "$f" .pdf | sed 's/-review$//')
  [ ! -f "ko/articles/$base.md" ] && [ ! -f "ko/reviews/$base.md" ] && echo "  MISSING: $base"
done

echo "=== MD without PDF ==="
for f in ko/articles/*.md ko/reviews/*.md; do
  base=$(basename "$f" .md)
  pdf_base="$base"
  [ -f "ko/reviews/$base.md" ] && pdf_base="${base}-review"
  [ ! -f "ko/pdf/$pdf_base.pdf" ] && echo "  MISSING: $pdf_base"
done

# 4. 리뷰 PDF에 -review 접미사 확인
echo "Review PDFs without -review:"
for f in ko/reviews/*.md; do
  base=$(basename "$f" .md)
  [ ! -f "ko/pdf/${base}-review.pdf" ] && echo "  $base"
done

# 5. 중복 파일명 확인
echo "Duplicate filenames:"
ls ko/articles/ ko/reviews/ | sed 's/.*\///' | sort | uniq -d
```

### 최종 통계

```bash
echo "=== Final Stats ==="
echo "PDFs: $(ls ko/pdf/*.pdf | wc -l)"
echo "Articles (ko/articles/): $(ls ko/articles/*.md | wc -l)"
echo "Reviews (ko/reviews/): $(ls ko/reviews/*.md | wc -l)"
echo "Review PDFs (-review.pdf): $(ls ko/pdf/*-review.pdf | wc -l)"
```

### commit

```bash
# tools submodule 변경사항이 있으면 먼저 처리
cd tools
git add -A
git commit -m "update: monthly batch processing $(date +%Y-%m)"
git push origin main
cd ..

# main vault
git add ko/articles/ ko/reviews/ tools
git commit -m "add: monthly batch $(date +%Y-%m) — N articles, N reviews"
git push origin main
```

commit 메시지 형식: `add: monthly batch {YYYY-MM} — {N} articles, {M} reviews`

---

## Chunk 분할 템플릿

대량 처리 시 사용할 chunk 분할 템플릿:

```bash
# 파일 목록 생성
ls ko/pdf/*.pdf > /tmp/all_pdfs.txt
TOTAL=$(wc -l < /tmp/all_pdfs.txt)
CHUNK_SIZE=18

echo "Total PDFs: $TOTAL"
echo "Split across $(( (TOTAL + CHUNK_SIZE - 1) / CHUNK_SIZE )) chunks"

# split 실행
cd ko/pdf
split -l $CHUNK_SIZE /tmp/all_pdfs.txt /tmp/monthly_chunk_

# 각 chunk 상태 확인
for c in /tmp/monthly_chunk_*; do
  n=$(wc -l < "$c")
  echo "  $(basename $c): $n files"
done
```

## 알려진 오류 패턴

1. **process_pdf.py 연도 추출 실패**: 개발(Development) 저널의 `dev20xxxx.pdf` 파일명에서 연도 추출 오류 (예: `dev205125` → `Mengistu2051_Development`로 출력). 개발 저널의 경우DOI에서 연도를 직접 확인 후 보정.

2. **저자명 misidentification**: 첫 페이지에 있는 다른 정보(Name, Journal homepage 등)를 저자명으로 추출하는 경우가 있음. CrossRef API로 저자명을 직접 확인할 것.

3. **저널명 misidentification**: DOI prefix 기반 저널 매핑이 부족하여 예측 실패 (예: `s41587` → NatBiotechnol이 `doi_journal_map.json`에 없어 `Unknown` 처리됨). 이런 경우 `tools/doi_journal_map.json`에 새로운 prefix를 추가할 것.

4. **리뷰 오분류**: `process_pdf.py`의 review detection은 본문 키워드 기반이라 오류 있음. 제목에 "review"가 없어도 리뷰일 수 있고, 반대로 제목에 "review"가 있어도 원저일 수 있음. **반드시 직접 확인**.

5. **Name collision**: 서로 다른 PDF가 동일한 target name으로 추천되면 나중에 처리된 파일이 먼저 파일을 조용히 덮어씀. dry-run에서 반드시 중복 확인.

6. **extracted text 없음**: `process_pdf.py`가 텍스트 추출에 실패했지만 MD 파일은 생성한 경우. 추출 텍스트 파일이 없으면 직접 PDF에서 추출.

## Reference: 자주 사용되는 DOI prefix → 저널 매핑

| DOI prefix | 저널 약어 | `doi_journal_map.json` 등록 여부 |
|-----------|----------|-------------------------------|
| 10.1038/s41586 | Nature | ✅ |
| 10.1038/s41467 | NatCommun | ✅ |
| 10.1038/s41587 | NatBiotechnol | ❌ (추가 필요) |
| 10.1038/s41551 | NatBiomedEng | ❌ (추가 필요) |
| 10.1038/s41556 | NatCellBiol | ✅ |
| 10.1038/s41598 | SciRep | ✅ |
| 10.1038/s41584 | NatRevRheumatol | ✅ |
| 10.1038/s41572 | NatRevDisPrimers | ❌ (추가 필요) |
| 10.1038/s41574 | NatRevEndocrinol | ❌ (추가 필요) |
| 10.1038/s41593 | NatNeurosci | ❌ (추가 필요) |
| 10.1126/science | Science | ✅ |
| 10.1126/sciadv | SciAdv | ✅ |
| 10.1016/j.cub | CurrBiol | ❌ (추가 필요) |
| 10.1016/j.cell | Cell | ✅ |
| 10.1016/j.isci | iScience | ✅ |
| 10.1242/dev | Development | ✅ |
| 10.7554/eLife | eLife | ✅ |
| 10.1186/s13059 | GenomeBiol | ❌ (추가 필요) |
| 10.3389/fcell | FrontCellDevBiol | ✅ |
| 10.3389/fimmu | FrontImmunol | ❌ (추가 필요) |

새로운 매핑은 `tools/doi_journal_map.json`에 추가한 후 사용한다.
