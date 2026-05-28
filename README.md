# 네이버 블로그 키워드 순위 체커

블로그 홈 URL을 등록하고, 게시글별 키워드(최대 4개)의 네이버 검색 순위를 확인합니다.

## 요구 사항

- Python 3.11+
- Supabase 프로젝트
- Playwright Chromium

## 설치

```powershell
cd naver-blog-rank
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

## Supabase

SQL Editor에서 [`supabase/schema.sql`](supabase/schema.sql) 실행.

기존 `members` 테이블이 있다면 [`supabase/blog_schema.sql`](supabase/blog_schema.sql) 사용.

## 실행

```powershell
streamlit run blog_app.py
```

## Streamlit Cloud

- Repository: `trendmarkhyun/naver-blog-rank`
- Main file: `blog_app.py`
- Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `TEAM_ACCESS_CODE`

## 기능

- 블로그 URL 최대 100개 등록
- 게시글 40개 · 키워드 4열 가로 배치
- 통합검색 / 블로그탭 순위 체크 (광고 제외, 50위)
- 엑셀 저장
