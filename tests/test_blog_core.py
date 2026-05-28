"""블로그 순위 체커 핵심 단위 테스트."""

from __future__ import annotations

import unittest

from src.blog_models import (
    BLOG_MAX_RANK,
    MAX_BLOGS,
    SEARCH_MODE_BLOG_TAB,
    SEARCH_MODE_UNIFIED,
    BlogKeyword,
    BlogPost,
    BlogProfile,
    effective_search_mode,
    format_rank_label,
    rank_badge_class,
    summarize_keyword_ranks,
    summarize_profile_ranks,
)
from src.blog_url import BlogUrlError, build_blog_home_url, parse_blog_url, post_urls_match


class BlogUrlTests(unittest.TestCase):
    def test_parse_home_url(self) -> None:
        parsed = parse_blog_url("https://blog.naver.com/example_blog01")
        self.assertEqual(parsed.blog_id, "example_blog01")
        self.assertIsNone(parsed.post_id)
        self.assertEqual(build_blog_home_url("example_blog01"), "https://blog.naver.com/example_blog01")

    def test_parse_post_url(self) -> None:
        parsed = parse_blog_url("https://blog.naver.com/myblog/123456789")
        self.assertEqual(parsed.blog_id, "myblog")
        self.assertEqual(parsed.post_id, "123456789")

    def test_parse_query_url(self) -> None:
        parsed = parse_blog_url(
            "https://blog.naver.com/PostView.naver?blogId=mvno_review&logNo=987654321"
        )
        self.assertEqual(parsed.blog_id, "mvno_review")
        self.assertEqual(parsed.post_id, "987654321")

    def test_invalid_url(self) -> None:
        with self.assertRaises(BlogUrlError):
            parse_blog_url("https://example.com/blog")

    def test_post_urls_match(self) -> None:
        a = "https://blog.naver.com/myblog/123"
        b = "https://blog.naver.com/myblog/123?trackingCode=xxx"
        self.assertTrue(post_urls_match(a, b))


class BlogModelTests(unittest.TestCase):
    def test_effective_search_mode(self) -> None:
        profile = BlogProfile(
            id="1",
            member_id="m1",
            blog_id="blog",
            blog_url="https://blog.naver.com/blog",
            blog_title="t",
            advertiser_name="a",
            search_mode=None,
        )
        self.assertEqual(effective_search_mode(profile, SEARCH_MODE_UNIFIED), SEARCH_MODE_UNIFIED)

        profile.search_mode = SEARCH_MODE_BLOG_TAB
        self.assertEqual(
            effective_search_mode(profile, SEARCH_MODE_UNIFIED),
            SEARCH_MODE_BLOG_TAB,
        )

    def test_rank_badge_class(self) -> None:
        self.assertEqual(rank_badge_class(1, True, "키워드"), "r1")
        self.assertEqual(rank_badge_class(7, True, "키워드"), "rt")
        self.assertEqual(rank_badge_class(23, True, "키워드"), "rm")
        self.assertEqual(rank_badge_class(None, False, "키워드"), "rn")
        self.assertEqual(rank_badge_class(None, False, ""), "rn")

    def test_format_rank_label(self) -> None:
        self.assertEqual(format_rank_label(3, True, "키워드"), "3위")
        self.assertEqual(format_rank_label(None, False, "키워드"), "50위 밖")
        self.assertEqual(format_rank_label(None, False, ""), "-")

    def test_summarize_keyword_ranks(self) -> None:
        keywords = [
            BlogKeyword(id="1", blog_post_id="p", slot=1, keyword="a", rank=1, found=True),
            BlogKeyword(id="2", blog_post_id="p", slot=2, keyword="b", rank=5, found=True),
            BlogKeyword(id="3", blog_post_id="p", slot=3, keyword="", found=False),
        ]
        summary = summarize_keyword_ranks(keywords)
        self.assertEqual(summary.first_place, 1)
        self.assertEqual(summary.top_ten, 1)
        self.assertEqual(summary.empty, 1)
        labels = summary.to_labels()
        self.assertEqual(labels[0], ("py", "1위 ×1"))
        self.assertEqual(labels[1], ("pg", "10위내 ×1"))
        self.assertEqual(labels[2], ("pn", "미입력 ×1"))

    def test_summarize_profile_empty(self) -> None:
        profile = BlogProfile(
            id="1",
            member_id="m1",
            blog_id="blog",
            blog_url="https://blog.naver.com/blog",
            blog_title="t",
            advertiser_name="a",
            posts=[],
        )
        labels = summarize_profile_ranks(profile.posts).to_labels()
        self.assertEqual(labels, [("pn", "키워드 미입력")])

    def test_max_constants(self) -> None:
        self.assertEqual(MAX_BLOGS, 100)
        self.assertEqual(BLOG_MAX_RANK, 50)

    def test_format_stat(self) -> None:
        from src.blog_posts import format_stat

        self.assertEqual(format_stat(None), "-")
        self.assertEqual(format_stat(4821), "4,821")

    def test_decode_post_title(self) -> None:
        from src.blog_posts import decode_post_title, is_generic_title, posts_from_api_payload

        title = decode_post_title(
            "%EC%97%98%EC%A7%80+%EC%95%8C%EB%9C%B0%ED%8F%B0+%EB%A1%9C%EB%B0%8D%EC%9C%BC%EB%A1%9C"
        )
        self.assertIn("알뜰폰", title)
        self.assertTrue(is_generic_title("동영상..."))
        self.assertFalse(is_generic_title("광주 알뜰폰 LG 편의점 유심칩으로 10분 만에 개통!"))

        posts = posts_from_api_payload(
            "58qjijwjwf",
            {
                "resultCode": "S",
                "postList": [
                    {
                        "logNo": "224297630157",
                        "title": "%EA%B4%91%EC%A3%BC+%EC%95%8C%EB%9C%B0%ED%8F%B0",
                        "addDate": "2026. 5. 27.",
                    }
                ],
            },
        )
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].post_id, "224297630157")
        self.assertIn("광주", posts[0].title)
        self.assertEqual(posts[0].published_at, "2026. 5. 27.")

    def test_parse_post_list_response_fallback(self) -> None:
        from src.blog_posts import parse_post_list_response, posts_need_refresh

        raw = (
            '{"resultCode":"S","postList":[{"sellerServiceStatus":"N","logNo":"123",'
            '"title":"%EA%B4%91%EC%A3%BC","addDate":"2026. 5. 27.","broken":"bad\\escape"}]}'
        )
        items = parse_post_list_response(raw)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["logNo"], "123")

        class _Post:
            title = "동영상..."

        self.assertTrue(posts_need_refresh([_Post()]))
        self.assertFalse(posts_need_refresh([type("P", (), {"title": "실제 제목"})()]))


class BlogDateTests(unittest.TestCase):
    def test_parse_relative_and_absolute_dates(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from src.blog_dates import parse_published_at, sort_posts_newest_first

        now = datetime(2026, 5, 28, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        recent = parse_published_at("9시간 전", now=now)
        absolute = parse_published_at("2026. 5. 27.", now=now)
        older = parse_published_at("2026. 5. 8.", now=now)

        self.assertIsNotNone(recent)
        self.assertIsNotNone(absolute)
        self.assertIsNotNone(older)
        self.assertGreater(recent, absolute)
        self.assertGreater(absolute, older)

        class _Post:
            def __init__(self, published_at: str, post_id: str) -> None:
                self.published_at = published_at
                self.post_id = post_id

        ordered = sort_posts_newest_first(
            [
                _Post("2026. 5. 8.", "100"),
                _Post("9시간 전", "99"),
                _Post("2026. 5. 27.", "101"),
            ]
        )
        self.assertEqual([post.published_at for post in ordered], ["9시간 전", "2026. 5. 27.", "2026. 5. 8."])


class BlogSearchFilterTests(unittest.TestCase):
    def test_ad_filter_ignores_loading_substrings(self) -> None:
        from src.blog_search import BlogSearchResultItem, _is_ad_item

        item = BlogSearchResultItem(
            rank=1,
            url="https://blog.naver.com/example/1234567890",
            title="엘지 알뜰폰 로밍",
            blog_id="example",
            post_id="1234567890",
            is_ad=False,
        )
        self.assertFalse(_is_ad_item(item))


class BlogSearchMatchTests(unittest.TestCase):
    def test_find_post_rank(self) -> None:
        from src.blog_search import BlogSearchResultItem, find_post_rank

        results = [
            BlogSearchResultItem(
                rank=1,
                url="https://blog.naver.com/a/111",
                title="t1",
                blog_id="a",
                post_id="111",
            ),
            BlogSearchResultItem(
                rank=2,
                url="https://blog.naver.com/b/222",
                title="t2",
                blog_id="b",
                post_id="222",
            ),
        ]
        rank, found = find_post_rank("https://blog.naver.com/b/222", results, max_rank=50)
        self.assertTrue(found)
        self.assertEqual(rank, 2)


if __name__ == "__main__":
    unittest.main()
