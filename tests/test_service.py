import json
import threading
import unittest
import importlib
from pathlib import Path
from unittest.mock import Mock, patch

from douyin_service import (
    DouyinServiceError,
    DouyinTaskCancelled,
    PROJECT_ROOT,
    _load_local_modules,
    _resolve_messaging_credentials,
    cookie_map,
    extract_url,
    fetch_creator_comments,
    fetch_comments_with_auth,
    normalize_comment,
    normalize_cookie,
    video_id_from_url,
)


class CookieTests(unittest.TestCase):
    def test_normalizes_cookie_and_skips_domain_fragments(self):
        raw = "douyin.com; sessionid=abc; s_v_web_id=verify_1; token=a=b"
        normalized = normalize_cookie(raw)
        self.assertEqual(
            cookie_map(normalized),
            {"sessionid": "abc", "s_v_web_id": "verify_1", "token": "a=b"},
        )


class UrlTests(unittest.TestCase):
    def test_extracts_url_from_share_text(self):
        self.assertEqual(
            extract_url("复制链接 https://www.douyin.com/video/1234567890123 试试"),
            "https://www.douyin.com/video/1234567890123",
        )

    def test_extracts_video_id(self):
        self.assertEqual(
            video_id_from_url("https://www.douyin.com/video/1234567890123?x=1"),
            "1234567890123",
        )

    def test_rejects_missing_video_id(self):
        with self.assertRaises(DouyinServiceError):
            video_id_from_url("https://www.douyin.com/")


class CommentTests(unittest.TestCase):
    def test_normalizes_comment(self):
        raw = {
            "cid": "c1",
            "text": "需要",
            "digg_count": 3,
            "user": {
                "uid": "42",
                "nickname": "测试用户",
                "signature": "签名",
                "avatar_thumb": {"url_list": ["https://example.com/a.jpg"]},
            },
        }
        result = normalize_comment(raw, video={"aweme_id": "v1", "desc": "作品"})
        self.assertEqual(result["user"]["uid"], "42")
        self.assertEqual(result["text"], "需要")
        self.assertEqual(result["video"]["id"], "v1")

    @patch("douyin_service._raise_for_api_error")
    def test_comment_pagination_honors_limit(self, _raise):
        api = Mock()
        api.get_work_out_comment.side_effect = [
            {
                "comments": [
                    {"cid": "1", "text": "a", "user": {"uid": "1"}},
                    {"cid": "2", "text": "b", "user": {"uid": "2"}},
                ],
                "cursor": 2,
                "has_more": 1,
            },
            {
                "comments": [
                    {"cid": "3", "text": "c", "user": {"uid": "3"}},
                    {"cid": "4", "text": "d", "user": {"uid": "4"}},
                ],
                "cursor": 4,
                "has_more": 0,
            },
        ]
        result = fetch_comments_with_auth(
            api, object(), "https://www.douyin.com/video/1", 3, {}
        )
        self.assertEqual([item["id"] for item in result], ["1", "2", "3"])
        self.assertEqual(api.get_work_out_comment.call_count, 2)

    def test_cancelled_comment_task_stops_before_request(self):
        event = threading.Event()
        event.set()
        api = Mock()
        with self.assertRaises(DouyinTaskCancelled):
            fetch_comments_with_auth(
                api,
                object(),
                "https://www.douyin.com/video/1",
                3,
                {},
                event,
            )
        api.get_work_out_comment.assert_not_called()

    def test_creator_video_limit_is_ten(self):
        with self.assertRaisesRegex(DouyinServiceError, "作品数量范围为 1–10"):
            fetch_creator_comments("https://www.douyin.com/user/example", 11, 100)

    def test_creator_total_comment_limit_is_bounded(self):
        with self.assertRaisesRegex(DouyinServiceError, "评论总数范围为 1–1000"):
            fetch_creator_comments("https://www.douyin.com/user/example", 10, 1001)


class MessagingCredentialTests(unittest.TestCase):
    def test_detects_swapped_credentials_and_literal_private_key_newline(self):
        web_data = {
            "ticket": "ticket",
            "ts_sign": "ts",
            "client_cert": "cert",
        }
        key_data_with_literal_newline = '{"ec_privateKey":"line1\nline2"}'
        web_raw = json.dumps({"data": json.dumps(web_data)})
        keys_raw = json.dumps({"data": key_data_with_literal_newline})

        web, keys = _resolve_messaging_credentials(keys_raw, web_raw)

        self.assertEqual(web["ticket"], "ticket")
        self.assertEqual(keys["ec_privateKey"], "line1\nline2")


class IndependentPackagingTests(unittest.TestCase):
    def test_core_modules_are_loaded_from_this_project(self):
        modules = _load_local_modules()
        objects = [
            modules["DouyinAuth"],
            modules["DouyinAPI"],
            modules["ProtoBuilder"],
        ]
        paths = [
            Path(importlib.import_module(obj.__module__).__file__).resolve()
            for obj in objects
        ]
        paths.append(Path(modules["ResponseProto"].__file__).resolve())

        for path in paths:
            self.assertTrue(path.is_relative_to(PROJECT_ROOT), str(path))


if __name__ == "__main__":
    unittest.main()
