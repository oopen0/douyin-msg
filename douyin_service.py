from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import requests
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REFERENCE_ROOT = PROJECT_ROOT.parent / "DouYin_Spider"
MAX_COMMENTS = 200
MAX_CREATOR_COMMENTS = 1000
MAX_VIDEOS = 10
REQUEST_TIMEOUT = 25


class DouyinServiceError(RuntimeError):
    """A user-facing failure from the Douyin integration."""


class DouyinTaskCancelled(DouyinServiceError):
    """Raised when the user stops an active collection task."""


@dataclass(frozen=True)
class AppConfig:
    cookie: str
    cookie_source: str
    web_protect: str
    security_keys: str
    reference_root: Path

    @property
    def messaging_ready(self) -> bool:
        try:
            _resolve_messaging_credentials(self.web_protect, self.security_keys)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return True


def _non_empty(value: Any) -> str:
    return str(value or "").strip()


def _decode_security_storage(raw: str) -> dict[str, Any]:
    outer = json.loads(raw, strict=False)
    data = outer["data"]
    if isinstance(data, str):
        # The SDK sometimes stores a PEM private key with literal line breaks
        # inside the nested JSON string. strict=False accepts that browser value.
        data = json.loads(data, strict=False)
    if not isinstance(data, dict):
        raise TypeError("localStorage data must be an object")
    return data


def _resolve_messaging_credentials(*raw_values: str) -> tuple[dict[str, Any], dict[str, Any]]:
    web_protect: dict[str, Any] | None = None
    security_keys: dict[str, Any] | None = None
    for raw in raw_values:
        if not _non_empty(raw):
            continue
        data = _decode_security_storage(raw)
        if data.get("ec_privateKey"):
            security_keys = data
        if all(data.get(key) for key in ("ticket", "ts_sign", "client_cert")):
            web_protect = data
    if web_protect is None or security_keys is None:
        raise ValueError("missing messaging credential fields")
    return web_protect, security_keys


def _check_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DouyinTaskCancelled("拉取已停止")


def load_config() -> AppConfig:
    local_values = dotenv_values(PROJECT_ROOT / ".env")
    reference_hint = (
        _non_empty(os.getenv("DOUYIN_SPIDER_ROOT"))
        or _non_empty(local_values.get("DOUYIN_SPIDER_ROOT"))
    )
    reference_root = Path(reference_hint).expanduser() if reference_hint else DEFAULT_REFERENCE_ROOT
    reference_values = dotenv_values(reference_root / ".env")

    env_cookie = _non_empty(os.getenv("DY_COOKIES"))
    local_cookie = _non_empty(local_values.get("DY_COOKIES"))
    reference_cookie = _non_empty(reference_values.get("DY_COOKIES"))
    if env_cookie:
        cookie, source = env_cookie, "系统环境变量"
    elif local_cookie:
        cookie, source = local_cookie, str(PROJECT_ROOT / ".env")
    elif reference_cookie:
        cookie, source = reference_cookie, str(reference_root / ".env")
    else:
        cookie, source = "", str(PROJECT_ROOT / ".env")

    return AppConfig(
        cookie=normalize_cookie(cookie),
        cookie_source=source,
        web_protect=(
            _non_empty(os.getenv("DY_WEB_PROTECT"))
            or _non_empty(local_values.get("DY_WEB_PROTECT"))
            or _non_empty(reference_values.get("DY_WEB_PROTECT"))
        ),
        security_keys=(
            _non_empty(os.getenv("DY_SECURITY_KEYS"))
            or _non_empty(local_values.get("DY_SECURITY_KEYS"))
            or _non_empty(reference_values.get("DY_SECURITY_KEYS"))
        ),
        reference_root=reference_root.resolve(),
    )


def normalize_cookie(raw_cookie: str) -> str:
    raw_cookie = raw_cookie.strip().strip("\"'")
    parts: list[str] = []
    seen: set[str] = set()
    for part in raw_cookie.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        parts.append(f"{key}={value.strip()}")
    return "; ".join(parts)


def cookie_map(cookie: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in normalize_cookie(cookie).split("; "):
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result


def validate_cookie(cookie: str) -> None:
    values = cookie_map(cookie)
    missing = [key for key in ("sessionid", "s_v_web_id") if not values.get(key)]
    if missing:
        raise DouyinServiceError(f"Cookie 缺少 {', '.join(missing)}，请复制登录后的完整 Cookie")


def _load_reference_modules(config: AppConfig):
    if not config.reference_root.is_dir():
        raise DouyinServiceError(
            f"找不到 DouYin_Spider：{config.reference_root}。请配置 DOUYIN_SPIDER_ROOT"
        )
    if str(config.reference_root) not in sys.path:
        sys.path.insert(0, str(config.reference_root))
    try:
        from builder.auth import DouyinAuth
        from builder.header import HeaderBuilder, HeaderType
        from builder.params import Params
        from builder.proto import ProtoBuilder
        from dy_apis.douyin_api import DouyinAPI
        from static import Response_pb2 as ResponseProto
        from utils.dy_util import generate_a_bogus, generate_msToken, splice_url
        from protobuf_to_dict import protobuf_to_dict
    except Exception as exc:
        raise DouyinServiceError(f"加载 DouYin_Spider 失败：{exc}") from exc
    return {
        "DouyinAuth": DouyinAuth,
        "HeaderBuilder": HeaderBuilder,
        "HeaderType": HeaderType,
        "Params": Params,
        "ProtoBuilder": ProtoBuilder,
        "DouyinAPI": DouyinAPI,
        "ResponseProto": ResponseProto,
        "generate_a_bogus": generate_a_bogus,
        "generate_msToken": generate_msToken,
        "splice_url": splice_url,
        "protobuf_to_dict": protobuf_to_dict,
    }


def _make_auth(config: AppConfig, *, require_messaging: bool = False):
    validate_cookie(config.cookie)
    if require_messaging and not config.messaging_ready:
        raise DouyinServiceError(
            "私信凭证未配置或格式无效。请按 docs/configuration.md 配置 "
            "DY_SECURITY_KEYS 和 DY_WEB_PROTECT 后重启"
        )
    modules = _load_reference_modules(config)
    auth = modules["DouyinAuth"]()
    try:
        auth.perepare_auth(config.cookie, "", "")
        if require_messaging:
            web_protect, security_keys = _resolve_messaging_credentials(
                config.web_protect, config.security_keys
            )
            auth.ticket = web_protect["ticket"]
            auth.ts_sign = web_protect["ts_sign"]
            auth.client_cert = web_protect["client_cert"]
            auth.private_key = security_keys["ec_privateKey"]
            auth.ree_public_key = base64.b64encode(
                auth.private_key.encode("utf-8")
            ).decode("ascii")
    except Exception as exc:
        raise DouyinServiceError(f"解析抖音安全凭证失败，请重新复制完整值：{exc}") from exc
    return modules, auth


URL_RE = re.compile(r"https?://[^\s<>\"']+")
VIDEO_ID_RE = re.compile(r"(?:video/|modal_id=)(\d{10,})")


def extract_url(text: str) -> str:
    match = URL_RE.search(text.strip())
    if not match:
        raise DouyinServiceError("没有找到有效的抖音链接")
    return match.group(0).rstrip("，。,.!！)）]")


def resolve_share_url(text: str) -> str:
    url = extract_url(text)
    host = urlparse(url).netloc.lower()
    if host in {"v.douyin.com", "iesdouyin.com"} or "douyin.com" not in host:
        try:
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            url = response.url
        except requests.RequestException as exc:
            raise DouyinServiceError(f"解析分享链接失败：{exc}") from exc
    if "douyin.com" not in urlparse(url).netloc.lower():
        raise DouyinServiceError("链接不是抖音网页链接")
    return unquote(url)


def video_id_from_url(url: str) -> str:
    match = VIDEO_ID_RE.search(url)
    if not match:
        raise DouyinServiceError("无法从链接中识别视频 ID")
    return match.group(1)


def _avatar_url(user: dict[str, Any]) -> str:
    for key in ("avatar_thumb", "avatar_medium", "avatar_larger"):
        urls = (user.get(key) or {}).get("url_list") or []
        if urls:
            return str(urls[0])
    return ""


def normalize_comment(raw: dict[str, Any], *, video: dict[str, Any] | None = None) -> dict[str, Any]:
    user = raw.get("user") or {}
    uid = str(user.get("uid") or user.get("short_id") or "")
    return {
        "id": str(raw.get("cid") or ""),
        "text": str(raw.get("text") or ""),
        "digg_count": int(raw.get("digg_count") or 0),
        "create_time": int(raw.get("create_time") or 0),
        "ip_label": str(raw.get("ip_label") or ""),
        "reply_count": int(raw.get("reply_comment_total") or 0),
        "user": {
            "uid": uid,
            "sec_uid": str(user.get("sec_uid") or ""),
            "nickname": str(user.get("nickname") or "抖音用户"),
            "signature": str(user.get("signature") or ""),
            "avatar": _avatar_url(user),
        },
        "video": {
            "id": str((video or {}).get("aweme_id") or raw.get("aweme_id") or ""),
            "desc": str((video or {}).get("desc") or ""),
        },
    }


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise DouyinServiceError(f"{label}必须是整数") from exc
    if number < minimum or number > maximum:
        raise DouyinServiceError(f"{label}范围为 {minimum}–{maximum}")
    return number


def fetch_video_comments(
    url_text: str,
    limit: Any = 50,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    limit_value = _bounded_int(
        limit, default=50, minimum=1, maximum=MAX_COMMENTS, label="评论数量"
    )
    resolved_url = resolve_share_url(url_text)
    video_id = video_id_from_url(resolved_url)
    canonical_url = f"https://www.douyin.com/video/{video_id}"
    modules, auth = _make_auth(load_config())
    api = modules["DouyinAPI"]

    cursor = "0"
    result: list[dict[str, Any]] = []
    seen_cursors: set[str] = set()
    while len(result) < limit_value:
        _check_cancelled(cancel_event)
        try:
            payload = api.get_work_out_comment(auth, canonical_url, cursor)
        except Exception as exc:
            raise DouyinServiceError(f"拉取评论失败：{exc}") from exc
        _check_cancelled(cancel_event)
        _raise_for_api_error(payload, "拉取评论")
        comments = payload.get("comments") or []
        result.extend(normalize_comment(item) for item in comments)
        next_cursor = str(payload.get("cursor") or "")
        if (
            not comments
            or payload.get("has_more") != 1
            or not next_cursor
            or next_cursor in seen_cursors
        ):
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return {
        "comments": result[:limit_value],
        "comment_count": min(len(result), limit_value),
        "video_count": 1,
        "video_id": video_id,
        "resolved_url": canonical_url,
    }


def _sec_uid_from_user_url(url: str) -> str:
    match = re.search(r"/user/([^/?#]+)", url)
    if not match:
        raise DouyinServiceError("无法从主页链接中识别博主")
    return match.group(1)


def fetch_creator_comments(
    url_text: str,
    video_limit: Any = 10,
    total_comment_limit: Any = 100,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    video_limit_value = _bounded_int(
        video_limit, default=10, minimum=1, maximum=MAX_VIDEOS, label="作品数量"
    )
    total_comment_limit_value = _bounded_int(
        total_comment_limit,
        default=100,
        minimum=1,
        maximum=MAX_CREATOR_COMMENTS,
        label="评论总数",
    )
    resolved_url = resolve_share_url(url_text)
    sec_uid = _sec_uid_from_user_url(resolved_url)
    canonical_user_url = f"https://www.douyin.com/user/{sec_uid}"
    modules, auth = _make_auth(load_config())
    api = modules["DouyinAPI"]

    videos: list[dict[str, Any]] = []
    max_cursor = "0"
    seen_cursors: set[str] = set()
    while len(videos) < video_limit_value:
        _check_cancelled(cancel_event)
        try:
            payload = api.get_user_work_info(auth, canonical_user_url, max_cursor)
        except Exception as exc:
            raise DouyinServiceError(f"拉取博主作品失败：{exc}") from exc
        _check_cancelled(cancel_event)
        _raise_for_api_error(payload, "拉取博主作品")
        page_items = payload.get("aweme_list") or []
        videos.extend(page_items)
        next_cursor = str(payload.get("max_cursor") or "")
        if (
            not page_items
            or payload.get("has_more") != 1
            or not next_cursor
            or next_cursor in seen_cursors
        ):
            break
        seen_cursors.add(next_cursor)
        max_cursor = next_cursor
    videos = videos[:video_limit_value]

    comments: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    processed_videos = 0
    for video in videos:
        _check_cancelled(cancel_event)
        if len(comments) >= total_comment_limit_value:
            break
        video_id = str(video.get("aweme_id") or "")
        if not video_id:
            continue
        processed_videos += 1
        try:
            page = fetch_comments_with_auth(
                api,
                auth,
                f"https://www.douyin.com/video/{video_id}",
                total_comment_limit_value - len(comments),
                video,
                cancel_event,
            )
            comments.extend(page)
        except DouyinTaskCancelled:
            raise
        except DouyinServiceError as exc:
            failures.append({"video_id": video_id, "message": str(exc)})

    return {
        "comments": comments[:total_comment_limit_value],
        "comment_count": len(comments),
        "video_count": processed_videos,
        "video_discovered_count": len(videos),
        "failed_videos": failures,
        "resolved_url": canonical_user_url,
    }


def fetch_comments_with_auth(
    api,
    auth,
    url: str,
    limit: int,
    video: dict[str, Any],
    cancel_event: threading.Event | None = None,
) -> list[dict[str, Any]]:
    cursor = "0"
    items: list[dict[str, Any]] = []
    seen_cursors: set[str] = set()
    while len(items) < limit:
        _check_cancelled(cancel_event)
        try:
            payload = api.get_work_out_comment(auth, url, cursor)
        except Exception as exc:
            raise DouyinServiceError(str(exc)) from exc
        _check_cancelled(cancel_event)
        _raise_for_api_error(payload, "拉取评论")
        comments = payload.get("comments") or []
        items.extend(normalize_comment(item, video=video) for item in comments)
        next_cursor = str(payload.get("cursor") or "")
        if (
            not comments
            or payload.get("has_more") != 1
            or not next_cursor
            or next_cursor in seen_cursors
        ):
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    return items[:limit]


def _raise_for_api_error(payload: Any, action: str) -> None:
    if not isinstance(payload, dict):
        raise DouyinServiceError(f"{action}失败：接口返回格式异常")
    status_code = payload.get("status_code")
    if status_code not in (None, 0):
        message = (
            payload.get("status_msg")
            or payload.get("message")
            or payload.get("extra", {}).get("logid")
            or f"状态码 {status_code}"
        )
        raise DouyinServiceError(f"{action}失败：{message}")


def send_private_message(user_id: Any, content: Any) -> dict[str, Any]:
    uid = _bounded_int(
        user_id,
        default=0,
        minimum=1,
        maximum=9_223_372_036_854_775_807,
        label="用户 UID",
    )
    text = str(content or "").strip()
    if not text:
        raise DouyinServiceError("私信内容不能为空")
    if len(text) > 500:
        raise DouyinServiceError("私信内容不能超过 500 个字符")

    config = load_config()
    modules, auth = _make_auth(config, require_messaging=True)
    response_proto = modules["ResponseProto"]
    protobuf_to_dict = modules["protobuf_to_dict"]

    try:
        conversation_id, short_id, ticket = _create_conversation(
            modules, auth, uid, response_proto, protobuf_to_dict
        )
        response = _send_message(
            modules,
            auth,
            conversation_id,
            short_id,
            ticket,
            text,
            response_proto,
            protobuf_to_dict,
        )
    except DouyinServiceError:
        raise
    except Exception as exc:
        raise DouyinServiceError(f"发送私信失败：{exc}") from exc

    return {
        "conversation_id": conversation_id,
        "conversation_short_id": str(short_id),
        "response": response,
    }


def _create_conversation(modules, auth, uid, response_proto, protobuf_to_dict):
    request_proto = modules["ProtoBuilder"].build_create_conversation_request(
        auth, uid, auth.get_uid()
    )
    headers = modules["HeaderBuilder"].build(modules["HeaderType"].PROTOBUF)
    headers.set_header("referer", "https://www.douyin.com/")
    response = requests.post(
        "https://imapi.douyin.com/v2/conversation/create",
        headers=headers.get(),
        cookies=auth.cookie,
        data=request_proto.SerializeToString(),
        verify=False,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise DouyinServiceError(f"创建私信会话失败：HTTP {response.status_code}")
    parsed = response_proto.Response()
    try:
        parsed.ParseFromString(response.content)
        payload = protobuf_to_dict(parsed)
        _raise_for_im_error(payload, "创建私信会话")
        conversations = (
            payload.get("body", {})
            .get("create_conversation_v2_body", {})
            .get("conversation_info_list", [])
        )
        conversation = conversations[0]
        return (
            conversation["conversation_id"],
            conversation["conversation_short_id"],
            conversation["ticket"],
        )
    except (IndexError, KeyError, ValueError) as exc:
        raise DouyinServiceError("创建私信会话失败：接口未返回有效会话") from exc


def _send_message(
    modules,
    auth,
    conversation_id,
    short_id,
    ticket,
    text,
    response_proto,
    protobuf_to_dict,
):
    request_proto = modules["ProtoBuilder"].build_send_message_request(
        auth, conversation_id, short_id, ticket, text
    )
    headers = modules["HeaderBuilder"].build(modules["HeaderType"].PROTOBUF)
    headers.set_header("referer", "https://www.douyin.com/")
    params = {
        "verifyFp": auth.cookie["s_v_web_id"],
        "fp": auth.cookie["s_v_web_id"],
        "msToken": modules["generate_msToken"](),
    }
    params["a_bogus"] = modules["generate_a_bogus"](
        modules["splice_url"](params)
    )
    response = requests.post(
        "https://imapi.douyin.com/v1/message/send",
        params=params,
        headers=headers.get(),
        cookies=auth.cookie,
        data=request_proto.SerializeToString(),
        verify=False,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise DouyinServiceError(f"发送私信失败：HTTP {response.status_code}")
    parsed = response_proto.Response()
    try:
        parsed.ParseFromString(response.content)
        payload = protobuf_to_dict(parsed)
    except Exception as exc:
        raise DouyinServiceError("发送私信失败：接口响应无法解析") from exc
    _raise_for_im_error(payload, "发送私信")
    return {
        "cmd": payload.get("cmd"),
        "sequence_id": str(payload.get("sequence_id") or ""),
        "message": payload.get("message") or "",
    }


def _raise_for_im_error(payload: dict[str, Any], action: str) -> None:
    error_desc = str(payload.get("error_desc") or "").strip()
    message = str(payload.get("message") or "").strip()
    if error_desc or (message and message.lower() not in {"success", "ok"}):
        raise DouyinServiceError(f"{action}失败：{error_desc or message}")
