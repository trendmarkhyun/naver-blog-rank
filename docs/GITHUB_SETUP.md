# GitHub 팀 공유 설정 가이드

직원들이 **같은 순위 데이터**를 함께 보려면 GitHub + Streamlit Cloud 조합을 권장합니다.

## 구조

```
config/team_watchlist.yaml   ← 팀이 함께 관리 (업체·키워드, 최대 20개)
        ↓
GitHub Actions (30분마다)
        ↓
data/team_rankings.json      ← 순위 결과 (자동 commit)
        ↓
Streamlit Cloud app.py       ← 직원들이 URL로 접속해 조회
```

## 1. GitHub 저장소 연결

저장소: **[github.com/trendmarkhyun/place-rank](https://github.com/trendmarkhyun/place-rank)**

```powershell
cd C:\Users\User\naver-place-rank
git init
git add .
git commit -m "Initial commit: place rank monitor"
git branch -M main
git remote add origin https://github.com/trendmarkhyun/place-rank.git
git push -u origin main
```

> 이미 remote가 있으면: `git remote set-url origin https://github.com/trendmarkhyun/place-rank.git`

## 2. 팀 watchlist 등록

[`config/team_watchlist.yaml`](config/team_watchlist.yaml) 파일을 GitHub에서 수정합니다.

```yaml
max_rank: 50
items:
  - place_url: "https://map.naver.com/p/entry/place/2051450000"
    keyword: "강남역 맛집"
    place_name: "도원반점 강남역직영점"
```

- 업체 추가/삭제: 이 파일을 PR 또는 GitHub 웹 편집으로 변경
- 최대 **20개**

## 3. GitHub Actions 활성화

저장소 → **Actions** → **Team Rank Monitor** 워크플로우

- **30분마다** 자동 실행
- 수동 실행: **Run workflow** 버튼
- 성공 시 `data/team_rankings.json`이 자동 commit 됩니다

로컬에서 테스트:

```powershell
python scripts/refresh_team_rankings.py --by manual
```

## 4. Streamlit Cloud 배포 (직원 공유 URL)

1. [share.streamlit.io](https://share.streamlit.io) 접속
2. GitHub 저장소 연결
3. Main file: `app.py`
4. **Secrets** (선택, 최신 JSON 자동 fetch):

```
TEAM_RANKINGS_URL = https://raw.githubusercontent.com/trendmarkhyun/place-rank/main/data/team_rankings.json
```

5. Deploy → 생성된 URL을 직원들과 공유

앱에서 **「팀 공유 (GitHub)」** 탭을 열면 모두 같은 순위를 봅니다.

## 5. 직원 사용 방법

1. Streamlit Cloud URL 접속
2. **팀 공유 (GitHub)** 탭 확인
3. 순위 변동 시 ✓ 표시
4. **GitHub 데이터 새로고침** 버튼으로 최신 반영

## 주의

- GitHub Actions 무료 한도: private repo는 월 2000분
- Playwright 설치로 1회 실행 **5~15분** 걸릴 수 있음 → 30분 주기 권장
- 네이버 이용약관 준수, 과도한 요청 자제
- **내 PC 모니터** 탭은 개인용(로컬 `data/watchlist.json`), 팀과 별개
