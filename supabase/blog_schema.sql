-- =============================================================================
-- 네이버 블로그 순위 체커 — Supabase 마이그레이션
-- =============================================================================
--
-- 실행 순서 (Supabase SQL Editor에서 위에서 아래로 순서대로 실행)
--
--   [선행] supabase/schema.sql
--          members · watchlist_items 테이블이 먼저 있어야 합니다.
--          (플레이스 앱만 쓰는 경우 schema.sql 한 번 실행)
--
--   [1단계] 아래 "members 확장" 블록 실행
--   [2단계] blog_profiles 테이블 생성
--   [3단계] blog_posts 테이블 생성
--   [4단계] blog_post_keywords 테이블 생성
--   [5단계] 인덱스 생성
--
-- 재실행: IF NOT EXISTS / ADD COLUMN IF NOT EXISTS 사용 — 안전하게 재실행 가능
-- =============================================================================

-- [1단계] members 확장
alter table members add column if not exists blog_search_mode text not null default 'unified';
alter table members add column if not exists blog_max_rank int not null default 50;

-- [2단계] blog_profiles (멤버당 최대 100개)
create table if not exists blog_profiles (
  id uuid primary key default gen_random_uuid(),
  member_id uuid not null references members(id) on delete cascade,
  blog_id text not null,
  blog_url text not null,
  blog_title text not null default '',
  advertiser_name text not null default '',
  search_mode text,
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  unique (member_id, blog_id)
);

-- [3단계] blog_posts (블로그당 최근 40개)
create table if not exists blog_posts (
  id uuid primary key default gen_random_uuid(),
  blog_profile_id uuid not null references blog_profiles(id) on delete cascade,
  post_id text not null,
  post_url text not null,
  title text not null,
  published_at text,
  views int,
  comments int,
  fetched_at timestamptz,
  unique (blog_profile_id, post_id)
);

-- [4단계] blog_post_keywords (게시글당 키워드 슬롯 4개)
create table if not exists blog_post_keywords (
  id uuid primary key default gen_random_uuid(),
  blog_post_id uuid not null references blog_posts(id) on delete cascade,
  slot int not null check (slot between 1 and 4),
  keyword text not null default '',
  rank int,
  found boolean not null default false,
  updated_at timestamptz,
  unique (blog_post_id, slot)
);

-- [5단계] 인덱스
create index if not exists idx_blog_profiles_member on blog_profiles(member_id);
create index if not exists idx_blog_posts_profile on blog_posts(blog_profile_id);
create index if not exists idx_blog_keywords_post on blog_post_keywords(blog_post_id);
