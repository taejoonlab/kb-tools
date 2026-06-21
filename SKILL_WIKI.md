# GitHub Wiki Posting Workflow

## 개요
kb-AutoBio vault의 마크다운 노트를 GitHub Wiki에 포스팅하는 자동화 워크플로우

## 전제 조건
- GitHub Wiki가 활성화되어 있어야 함 (repo 설정 → Features → Wikis 체크)
- SSH 키가 설정되어 있어야 함 (`git@github.com:` 접근)
- Wiki repo URL: `git@github.com:{owner}/{repo}.wiki.git`

## 사용법

### Step 1: Wiki Repo 클론
```bash
cd /tmp/opencode
git clone git@github.com:taejoonlab/kb-AutoBio.wiki.git
```
이미 클론되어 있다면 pull로 최신화:
```bash
cd /tmp/opencode/kb-AutoBio.wiki && git pull
```

### Step 2: 마크다운 파일 복사
GitHub Wiki는 **하위 폴더를 지원하지 않으므로** 모든 파일을 루트에 복사하고 파일명에 접두사를 붙인다.

```bash
# 기존 파일 정리 (Articles-, Reviews- 접두사 파일만 삭제)
cd /tmp/opencode/kb-AutoBio.wiki
rm -f Articles-*.md Reviews-*.md

# 영어 article 복사 (en/articles/ 사용)
cp /mnt/d/Git/taejoonlab/kb-AutoBio/en/articles/*.md .
for f in *.md; do
  [[ "$f" == Home.md ]] && continue
  [[ "$f" == Articles-* ]] && continue
  mv "$f" "Articles-${f}"
done

# 한국어 review 복사 (ko/reviews/ 사용)
cp /mnt/d/Git/taejoonlab/kb-AutoBio/ko/reviews/*.md .
for f in *.md; do
  [[ "$f" == Home.md ]] && continue
  [[ "$f" == Articles-* ]] && continue
  [[ "$f" == Reviews-* ]] && continue
  mv "$f" "Reviews-${f}"
done
```

**파일명 규칙**:
| 원본 위치 | Wiki 파일명 |
|-----------|------------|
| `en/articles/Adam2024_PNAS.md` | `Articles-Adam2024_PNAS.md` |
| `ko/reviews/Abolhasani2023_NatSynth.md` | `Reviews-Abolhasani2023_NatSynth.md` |

### Step 3: Home.md 작성
Home.md는 영어로 작성하며, 주제별 섹션으로 구성한다.

```markdown
# kb-AutoBio Wiki

Korean Obsidian vault for **AutoBio** research literature.

## Self-Driving Labs & Autonomous Research
(Self-driving lab 관련 논문 요약 테이블)

## Automated Cell Culture & hiPSC Manufacturing
(hiPSC 배양 자동화 관련 논문 요약 테이블)

## Organoid & 3D Cell Culture Platforms
(오가노이드 플랫폼 관련 논문 요약 테이블)

## Extracellular Vesicles (EVs) & Liquid Biopsy
(EV 분리·분석 관련 논문 요약 테이블)

## Protein Engineering & Design
(단백질 엔지니어링 관련 논문 요약 테이블)

## Quality Control & Measurement Assurance
(QC·측정 보증 관련 논문 요약 테이블)

## Full Article List
(전체 article 테이블)

## Full Review List
(전체 review 테이블)
```

**링크 형식**: GitHub Wiki는 하위 폴더 미지원이므로 `[Title](Articles-Filename)` 형식 사용 (`.md` 확장자 생략 가능).

```markdown
[Adam et al. (2024) PNAS](Articles-Adam2024_PNAS)
[Abolhasani et al. (2023) Nat Synth](Reviews-Abolhasani2023_NatSynth)
```

### Step 4: Commit & Push
```bash
cd /tmp/opencode/kb-AutoBio.wiki
git add -A
git commit -m "update: sync wiki with vault articles and reviews"
git push
```

## 전체 스크립트 (한 번에 실행)
```bash
#!/bin/bash
set -e

WIKI_DIR="/tmp/opencode/kb-AutoBio.wiki"
VAULT="/mnt/d/Git/taejoonlab/kb-AutoBio"

# Wiki 클론 또는 pull
if [ -d "$WIKI_DIR/.git" ]; then
  cd "$WIKI_DIR" && git pull
else
  cd /tmp/opencode && git clone git@github.com:taejoonlab/kb-AutoBio.wiki.git
  cd "$WIKI_DIR"
fi

# 기존 article/review 파일 정리
rm -f Articles-*.md Reviews-*.md

# 영어 article 복사
cp "$VAULT/en/articles/"*.md .
for f in *.md; do
  [[ "$f" == Home.md ]] && continue
  [[ "$f" == Articles-* ]] && continue
  mv "$f" "Articles-${f}"
done

# 한국어 review 복사
cp "$VAULT/ko/reviews/"*.md .
for f in *.md; do
  [[ "$f" == Home.md ]] && continue
  [[ "$f" == Articles-* ]] && continue
  [[ "$f" == Reviews-* ]] && continue
  mv "$f" "Reviews-${f}"
done

# Home.md는 수동으로 작성/수정 후

# Commit & Push
git add -A
git status
# git commit -m "..." && git push  # 확인 후 실행
```

## 주의사항
- **하위 폴더 미지원**: GitHub Wiki는 `Articles/`, `Reviews/` 같은 서브디렉토리를 렌더링하지 않음 → 반드시 루트에扁平化
- **파일명 접두사**: `Articles-`, `Reviews-` 접두사로 원본 구분
- **Home.md 링크**: `.md` 확장자 없이 `[Title](Articles-Filename)` 형식
- **영어 article만**: 공개 위키는 `en/articles/`의 영어 버전 사용, `ko/articles/`는 사용 안 함
- **리뷰는 한국어 유지**: `ko/reviews/`는 영어 버전 없으므로 한국어 그대로 사용
- **Home.md는 매번 수동**: 새 논문 추가 시 Home.md의 요약 테이블도 함께 업데이트 필요
