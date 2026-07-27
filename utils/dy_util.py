import base64
import hashlib
import json
import random
import re
import subprocess
import time
import urllib.parse
from functools import partial
from pathlib import Path

import requests


requests.packages.urllib3.disable_warnings()
subprocess.Popen = partial(subprocess.Popen, encoding="utf-8")
import execjs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "static"
NODE_MODULES = PROJECT_ROOT / "node_modules"

try:
    dy_js = execjs.compile(
        (STATIC_ROOT / "dy_ab.js").read_text(encoding="utf-8"),
        cwd=str(NODE_MODULES),
    )
except Exception as exc:
    raise RuntimeError(
        "加载本地抖音签名脚本失败，请确认已执行 npm install"
    ) from exc


def trans_cookies(cookies_str):
    cookies = {}
    for item in cookies_str.split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key:
            cookies[key] = value
    return cookies


def generate_req_sign(data, private_key):
    return dy_js.call("get_req_sign", data, private_key)


def generate_a_bogus(query, data=""):
    return dy_js.call("get_ab", query, data)


def generate_ree_key(private_key):
    return dy_js.call("get_ree_key", private_key)


def generate_bd_ticket_client_data(api, ticket, ts_sign, private_key):
    timestamp = int(time.time())
    sign_data = f"ticket={ticket}&path={api}&timestamp={timestamp}"
    payload = {
        "ts_sign": ts_sign,
        "req_content": "ticket,path,timestamp",
        "req_sign": generate_req_sign(sign_data, private_key),
        "timestamp": timestamp,
    }
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(compact.encode("utf-8")).decode("utf-8")


def generate_msToken(randomlength=107):
    alphabet = (
        "ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789="
    )
    return "".join(random.choice(alphabet) for _ in range(randomlength))


def generate_fake_webid(random_length=19):
    return "".join(random.choice("0123456789") for _ in range(random_length))


def generate_webid(auth=None, url=""):
    if not url:
        url = "https://www.douyin.com/discover?modal_id=7376449060384935209"
    try:
        from builder.header import HeaderBuilder, HeaderType

        headers = HeaderBuilder.build(HeaderType.DOC)
        headers.set_header("cookie", auth.cookie_str if auth else "")
        headers.set_header("upgrade-insecure-requests", "1")
        response = requests.get(
            url, headers=headers.get(), verify=False, timeout=20
        )
        return re.findall(
            r'\\"user_unique_id\\":\\"(.*?)\\"', response.text
        )[0]
    except Exception:
        return generate_fake_webid()


def generate_csrf_token(cookies_str):
    try:
        headers = {
            "accept": "*/*",
            "accept-language": (
                "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
            ),
            "cache-control": "no-cache",
            "cookie": cookies_str,
            "pragma": "no-cache",
            "referer": "https://www.douyin.com/?recommend=1",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "x-secsdk-csrf-request": "1",
            "x-secsdk-csrf-version": "1.2.22",
        }
        response = requests.head(
            "https://www.douyin.com/service/2/abtest_config/",
            headers=headers,
            verify=False,
            timeout=20,
        )
        tokens = response.headers["X-Ware-Csrf-Token"].split(",")
        return tokens[1], tokens[4]
    except Exception:
        return None, None


def generate_millisecond():
    return int(round(time.time() * 1000))


def splice_url(params):
    return "&".join(
        f"{key}={urllib.parse.quote(str(value if value is not None else ''))}"
        for key, value in params.items()
    )
