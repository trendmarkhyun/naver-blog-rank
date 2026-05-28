"""단위 테스트."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.config_loader import ConfigError, load_config
from src.config_loader import Business
from src.matcher import SearchResultItem, find_business_rank
from src.parser import (
    infer_list_category,
    list_url_for_keyword,
    parse_places_from_apollo_payload,
    parse_places_from_dom_links,
    to_search_results,
)
from src.place_url import PlaceUrlError, parse_place_url
from src.storage import Storage
from src.team_config import load_team_watchlist, stable_item_id
from src.team_rankings import load_team_rankings, save_team_rankings, snapshot_from_watchlist
from src.watchlist import (
    WatchlistData,
    WatchlistError,
    WatchlistItem,
    add_item,
    apply_rank_refresh,
    load_watchlist,
    rank_changed,
    remove_item,
    save_watchlist,
)


class ConfigLoaderTests(unittest.TestCase):
    def test_load_valid_config(self) -> None:
        config_path = Path(__file__).resolve().parent.parent / "config" / "test_targets.yaml"
        config = load_config(config_path)
        self.assertEqual(len(config.businesses), 2)
        self.assertEqual(len(config.targets), 2)

    def test_duplicate_business_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(
                """
businesses:
  - id: a
    name: A
    place_id: "1"
  - id: a
    name: B
    place_id: "2"
keywords:
  - test
""",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_config(path)


class MatcherTests(unittest.TestCase):
    def test_match_by_place_id(self) -> None:
        business = Business(id="x", name="테스트", place_id="123")
        results = [
            SearchResultItem(rank=1, place_id="999", name="다른 업체"),
            SearchResultItem(rank=2, place_id="123", name="테스트"),
        ]
        match = find_business_rank(business, results)
        self.assertTrue(match.found)
        self.assertEqual(match.rank, 2)
        self.assertEqual(match.matched_by, "place_id")

    def test_empty_name_does_not_match_first_result(self) -> None:
        business = Business(id="x", name="", place_id="1934883905")
        results = [
            SearchResultItem(rank=1, place_id="1100344328", name="아낙네의밀가 공주본점"),
            SearchResultItem(rank=2, place_id="31992305", name="피탕김탕"),
        ]
        match = find_business_rank(business, results)
        self.assertFalse(match.found)
        self.assertIsNone(match.rank)


class ParserTests(unittest.TestCase):
    def test_parse_apollo_payload(self) -> None:
        payload = {
            "error": None,
            "total": 7049,
            "places": [
                {"place_id": "2051450000", "name": "도원반점 강남역직영점"},
                {"place_id": "1698724177", "name": "뚜레쥬르 강남직영점"},
            ],
        }
        places, total = parse_places_from_apollo_payload(payload)
        self.assertEqual(total, 7049)
        self.assertEqual(places[0][0], "2051450000")
        results = to_search_results(places)
        self.assertEqual(results[0].rank, 1)

    def test_list_url_for_food_keyword(self) -> None:
        url = list_url_for_keyword("공주시 맛집", 50)
        self.assertIn("/restaurant/list", url)
        self.assertIn("display=50", url)

    def test_list_url_for_general_keyword(self) -> None:
        url = list_url_for_keyword("강남 미용실", 30)
        self.assertIn("/place/list", url)

    def test_list_url_for_medical_keyword(self) -> None:
        url = list_url_for_keyword("강남역 한의원", 50)
        self.assertIn("/hospital/list", url)

    def test_list_url_from_hospital_place_url(self) -> None:
        url = list_url_for_keyword(
            "강남역",
            50,
            place_url="https://m.place.naver.com/hospital/1316635415/home",
        )
        self.assertIn("/hospital/list", url)

    def test_infer_list_category(self) -> None:
        self.assertEqual(infer_list_category("강남역 한의원"), "hospital")
        self.assertEqual(infer_list_category("공주시 맛집"), "restaurant")
        self.assertEqual(
            infer_list_category("강남", "https://m.place.naver.com/hospital/1/home"),
            "hospital",
        )

    def test_parse_hospital_dom_links(self) -> None:
        links = [
            {
                "href": "https://pcmap.place.naver.com/hospital/1316635415/home",
                "text": "테스트한의원",
            }
        ]
        places = parse_places_from_dom_links(links)
        self.assertEqual(places, [("1316635415", "테스트한의원")])


class PlaceUrlTests(unittest.TestCase):
    def test_parse_map_entry_url(self) -> None:
        place_id = parse_place_url("https://map.naver.com/p/entry/place/2051450000")
        self.assertEqual(place_id, "2051450000")

    def test_parse_pcmap_url(self) -> None:
        place_id = parse_place_url(
            "https://pcmap.place.naver.com/restaurant/1476560900/home"
        )
        self.assertEqual(place_id, "1476560900")

    def test_parse_hospital_url(self) -> None:
        place_id = parse_place_url(
            "https://m.place.naver.com/hospital/1316635415/home"
        )
        self.assertEqual(place_id, "1316635415")

    def test_parse_map_search_place_url(self) -> None:
        place_id = parse_place_url(
            "https://map.naver.com/p/search/%EC%B2%9C%EC%95%88%20%EC%A0%9C%EC%8A%A4%ED%8A%B8"
            "/place/1693055805?entry=pll&searchText=test"
        )
        self.assertEqual(place_id, "1693055805")

    def test_invalid_url_raises(self) -> None:
        with self.assertRaises(PlaceUrlError):
            parse_place_url("https://www.naver.com")


class WatchlistTests(unittest.TestCase):
    def test_add_remove_and_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.json"
            data = WatchlistData()
            add_item(
                data,
                place_url="https://map.naver.com/p/entry/place/111",
                keyword="강남역 맛집",
                place_name="테스트 업체",
                place_id="111",
                rank=3,
                found=True,
                updated_at="2026-05-27T09:00:00+09:00",
            )
            save_watchlist(data, path)
            loaded = load_watchlist(path)
            self.assertEqual(len(loaded.items), 1)
            item_id = loaded.items[0].id
            remove_item(loaded, item_id)
            self.assertEqual(len(loaded.items), 0)

    def test_max_items_limit(self) -> None:
        data = WatchlistData()
        for i in range(20):
            add_item(
                data,
                place_url=f"https://map.naver.com/p/entry/place/{1000 + i}",
                keyword=f"키워드{i}",
                place_name=f"업체{i}",
                place_id=str(1000 + i),
                rank=1,
                found=True,
                updated_at="2026-05-27T09:00:00+09:00",
            )
        with self.assertRaises(WatchlistError):
            add_item(
                data,
                place_url="https://map.naver.com/p/entry/place/9999",
                keyword="추가",
                place_name="초과",
                place_id="9999",
                rank=1,
                found=True,
                updated_at="2026-05-27T09:00:00+09:00",
            )

    def test_rank_refresh_detects_change(self) -> None:
        item = WatchlistItem(
            id="1",
            place_id="111",
            place_url="https://map.naver.com/p/entry/place/111",
            place_name="테스트",
            keyword="강남역 맛집",
            rank=5,
            found=True,
            updated_at="2026-05-27T09:00:00+09:00",
        )
        apply_rank_refresh(
            item,
            rank=3,
            found=True,
            place_name="테스트",
            updated_at="2026-05-27T09:05:00+09:00",
        )
        self.assertTrue(item.changed)
        self.assertEqual(item.prev_rank, 5)
        self.assertEqual(item.rank, 3)
        self.assertTrue(rank_changed(5, 3, True, True))


class TeamConfigTests(unittest.TestCase):
    def test_load_team_watchlist(self) -> None:
        path = Path(__file__).resolve().parent.parent / "config" / "team_watchlist.yaml"
        config = load_team_watchlist(path)
        self.assertGreaterEqual(len(config.items), 1)
        self.assertEqual(stable_item_id("2051450000", "강남역 맛집"), stable_item_id("2051450000", "강남역 맛집"))

    def test_team_rankings_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "team_rankings.json"
            data = WatchlistData(
                items=[
                    WatchlistItem(
                        id="abc",
                        place_id="111",
                        place_url="https://map.naver.com/p/entry/place/111",
                        place_name="테스트",
                        keyword="키워드",
                        rank=2,
                        found=True,
                    )
                ],
                max_rank=50,
            )
            snapshot = snapshot_from_watchlist(
                data,
                refreshed_at="2026-05-27T10:00:00+09:00",
                refreshed_by="test",
            )
            save_team_rankings(snapshot, path)
            loaded = load_team_rankings(path)
            assert loaded is not None
            self.assertEqual(len(loaded.items), 1)
            self.assertEqual(loaded.refreshed_by, "test")


class StorageTests(unittest.TestCase):
    def test_save_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            storage = Storage(db_path)
            storage.sync_businesses(
                [Business(id="biz", name="테스트 업체", place_id="111")]
            )
            storage.save_ranking(
                collected_at="2026-05-27T09:00:00+09:00",
                business_id="biz",
                keyword="강남역 맛집",
                rank=3,
                found=True,
                result_count=20,
            )
            rows = storage.export_rankings()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].rank, 3)


if __name__ == "__main__":
    unittest.main()
