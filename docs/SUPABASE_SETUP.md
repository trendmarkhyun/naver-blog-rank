# Supabase + Streamlit Cloud 배포 (블로그 순위 체커)

팀원이 **URL 하나**로 접속해, **개인별** 블로그를 등록하고 키워드 순위를 확인합니다.

## 구조

```
팀원 → Streamlit Cloud (blog_app.py)
         ↕ Supabase (members + blog_profiles + blog_posts + blog_post_keywords)
GitHub Actions (30분) → Playwright 순위 수집 → Supabase 갱신
```

## 1. Supabase

1. [supabase.com](https://supabase.com) → New project
2. SQL Editor → [`supabase/schema.sql`](../supabase/schema.sql) 실행
3. API Keys: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

## 2. GitHub Secrets (Actions용)

저장소 `trendmarkhyun/naver-blog-rank` → **Settings → Secrets → Actions**

| Name | Value |
|------|-------|
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | service_role key |

## 3. GitHub Actions 실행

**Actions → Supabase Blog Rank Monitor → Run workflow**

등록된 블로그 키워드가 있으면 Supabase `blog_post_keywords`의 `rank`, `found`, `updated_at`이 채워집니다.

## 4. Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → GitHub 연결
2. Repository: `trendmarkhyun/naver-blog-rank`
3. Main file: `blog_app.py`
4. Secrets:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_SERVICE_KEY = "eyJ..."
TEAM_ACCESS_CODE = "your-team-code"
```

## 5. 팀원 사용법

1. Streamlit URL 접속
2. **이름** + **팀원코드** 로그인
3. 블로그 URL 등록 → 게시글별 키워드 입력
4. 30분 이내 순위 자동 갱신 (또는 Actions 수동 실행)

## 6. 로컬 개발

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run blog_app.py
```
