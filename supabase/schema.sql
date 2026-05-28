-- Supabase SQL Editor에서 실행 (블로그 순위 체커)

create table if not exists members (
  id uuid primary key default gen_random_uuid(),
  display_name text not null,
  team_code text not null,
  max_rank int not null default 50,
  blog_search_mode text not null default 'unified',
  blog_max_rank int not null default 50,
  created_at timestamptz not null default now(),
  unique (display_name, team_code)
);

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

create index if not exists idx_blog_profiles_member on blog_profiles(member_id);
create index if not exists idx_blog_posts_profile on blog_posts(blog_profile_id);
create index if not exists idx_blog_keywords_post on blog_post_keywords(blog_post_id);
