"""Probe post fetch count for a blog."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.blog_posts import fetch_posts_via_http

for blog_id in ("58qjijwjwf",):
    posts = fetch_posts_via_http(blog_id)
    print(f"blog={blog_id} count={len(posts)}")
    for p in posts[:10]:
        print(f"  {p.post_id} | {p.published_at} | {p.title[:50]}")
