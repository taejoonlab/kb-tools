<!--
trigger:  vault의 MD 노트를 GitHub Wiki에 게시할 때
input:    {lang}/articles/*.md, {lang}/reviews/*.md (vault 내 완성된 노트)
output:   GitHub Wiki repo에 Articles-*.md, Reviews-*.md 파일 동기화
script:   (스크립트 없음 — git 명령 수동 실행)
related:  SKILL.md (원저 노트 생성), SKILL_REVIEW.md (리뷰 노트 생성)
config:   사용 전 아래 변수를 repo에 맞게 설정
          VAULT  = vault 루트 절대경로   (예: /mnt/d/Git/taejoonlab/kb-Genetics)
          OWNER  = GitHub 사용자/조직명  (예: taejoonlab)
          REPO   = GitHub repo 이름      (예: kb-Genetics)
          WIKI_DIR = wiki 클론 경로      (예: /tmp/wiki/{REPO}.wiki)
-->

# GitHub Wiki Posting Workflow

## 개요
vault의 마크다운 노트를 GitHub Wiki에 포스팅하는 워크플로우.
사용 전 아래 변수를 현재 repo에 맞게 설정한다.

```bash
VAULT="/mnt/d/Git/taejoonlab/{REPO}"   # vault 루트
OWNER="taejoonlab"                      # GitHub owner
REPO="{REPO}"                           # GitHub repo 이름
WIKI_DIR="/tmp/wiki/${REPO}.wiki"       # wiki 클론 경로
```

## 전제 조건
- GitHub Wiki가 활성화되어 있어야 함 (repo 설정 → Features → Wikis 체크)
- SSH 키가 설정되어 있어야 함 (`git@github.com:` 접근)
- Wiki repo URL: `git@github.com:{OWNER}/{REPO}.wiki.git`

## 사용법

### Step 1: Wiki Repo 클론 또는 최신화

```bash
mkdir -p /tmp/wiki
if [ -d "$WIKI_DIR/.git" ]; then
  cd "$WIKI_DIR" && git pull
else
  git clone "git@github.com:${OWNER}/${REPO}.wiki.git" "$WIKI_DIR"
fi
```

### Step 2: 마크다운 파일 복사

GitHub Wiki는 **하위 폴더를 지원하지 않으므로** 모든 파일을 루트에 복사하고 파일명에 접두사를 붙인다.

```bash
cd "$WIKI_DIR"

# 기존 파일 정리 (Articles-, Reviews- 접두사 파일만 삭제)
rm -f Articles-*.md Reviews-*.md

# 영어 article 복사 (en/articles/ 사용)
cp "$VAULT/en/articles/"*.md .
for f in *.md; do
  [[ "$f" == Home.md ]] && continue
  [[ "$f" == Articles-* ]] && continue
  mv "$f" "Articles-${f}"
done

# 한국어 review 복사 (ko/reviews/ 사용)
cp "$VAULT/ko/reviews/"*.md .
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
| `ko/reviews/Nielsen2005_NatRevGenet.md` | `Reviews-Nielsen2005_NatRevGenet.md` |

### Step 3: Home.md 작성

Home.md는 영어로 작성하며, 주제별 섹션으로 구성한다.

```markdown
# {REPO} Wiki

Korean/English Obsidian vault for **{주제}** research literature.

## {주제 섹션 1}
(논문 요약 테이블)

## Full Article List
(전체 article 테이블)

## Full Review List
(전체 review 테이블)
```

**링크 형식**: GitHub Wiki는 하위 폴더 미지원이므로 `[Title](Articles-Filename)` 형식 사용 (`.md` 확장자 생략 가능).

```markdown
[Adam et al. (2024) PNAS](Articles-Adam2024_PNAS)
[Nielsen et al. (2005) Nat Rev Genet](Reviews-Nielsen2005_NatRevGenet)
```

### Step 4: Commit & Push

```bash
cd "$WIKI_DIR"
git add -A
git commit -m "update: sync wiki with vault $(date +%Y-%m-%d)"
git push
```

## 전체 스크립트 (한 번에 실행)

```bash
#!/bin/bash
set -e

# ── 설정 (repo마다 변경) ──────────────────────────────────
VAULT="/mnt/d/Git/taejoonlab/{REPO}"
OWNER="taejoonlab"
REPO="{REPO}"
WIKI_DIR="/tmp/wiki/${REPO}.wiki"
# ─────────────────────────────────────────────────────────

# Wiki 클론 또는 최신화
mkdir -p /tmp/wiki
if [ -d "$WIKI_DIR/.git" ]; then
  cd "$WIKI_DIR" && git pull
else
  git clone "git@github.com:${OWNER}/${REPO}.wiki.git" "$WIKI_DIR"
fi

cd "$WIKI_DIR"

# 기존 파일 정리
rm -f Articles-*.md Reviews-*.md

# 영어 article 복사
cp "$VAULT/en/articles/"*.md . 2>/dev/null || true
for f in *.md; do
  [[ "$f" == Home.md ]] && continue
  [[ "$f" == Articles-* ]] && continue
  mv "$f" "Articles-${f}"
done

# 한국어 review 복사
cp "$VAULT/ko/reviews/"*.md . 2>/dev/null || true
for f in *.md; do
  [[ "$f" == Home.md ]] && continue
  [[ "$f" == Articles-* ]] && continue
  [[ "$f" == Reviews-* ]] && continue
  mv "$f" "Reviews-${f}"
done

# Home.md는 수동으로 작성/수정 후

git add -A
git status
# 확인 후 실행:
# git commit -m "update: sync wiki $(date +%Y-%m-%d)" && git push
```

## 주의사항
- **하위 폴더 미지원**: GitHub Wiki는 `Articles/`, `Reviews/` 같은 서브디렉토리를 렌더링하지 않음 → 반드시 루트에 평탄화
- **파일명 접두사**: `Articles-`, `Reviews-` 접두사로 원본 구분
- **Home.md 링크**: `.md` 확장자 없이 `[Title](Articles-Filename)` 형식
- **영어 article만 공개**: `en/articles/`의 영어 버전 사용 권장
- **Home.md는 매번 수동**: 새 논문 추가 시 Home.md의 요약 테이블도 함께 업데이트 필요
- **VAULT 경로**: 스크립트 상단의 `VAULT`, `OWNER`, `REPO` 변수를 반드시 현재 repo에 맞게 설정
