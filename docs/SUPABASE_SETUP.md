# Supabase + Streamlit Cloud 배포 (블로그 순위 체커)

## 1. Supabase

1. [supabase.com](https://supabase.com) → New project
2. SQL Editor → [`supabase/schema.sql`](../supabase/schema.sql) 실행
3. API Keys: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

## 2. Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → GitHub 연결
2. Repository: `trendmarkhyun/naver-blog-rank`
3. Main file: `blog_app.py`
4. Secrets:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_SERVICE_KEY = "eyJ..."
TEAM_ACCESS_CODE = "your-team-code"
```

## 3. 로컬 개발

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run blog_app.py
```
