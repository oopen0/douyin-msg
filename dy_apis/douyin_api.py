import json
import re

import requests

from builder.header import HeaderBuilder, HeaderType
from builder.params import Params


requests.packages.urllib3.disable_warnings()
REQUEST_TIMEOUT = 25


class DouyinAPI:
    douyin_url = "https://www.douyin.com"

    @staticmethod
    def get_user_work_info(auth, user_url: str, max_cursor, **kwargs) -> dict:
        api = "/aweme/v1/web/aweme/post/"
        user_id = user_url.split("/")[-1].split("?")[0]
        headers = HeaderBuilder.build(HeaderType.GET)
        headers.set_referer(user_url)
        params = Params()
        params.add_param("device_platform", "webapp")
        params.add_param("aid", "6383")
        params.add_param("channel", "channel_pc_web")
        params.add_param("sec_user_id", user_id)
        params.add_param("max_cursor", max_cursor)
        params.add_param("locate_query", "false")
        params.add_param("show_live_replay_strategy", "1")
        params.add_param("need_time_list", "1" if max_cursor == "0" else "0")
        params.add_param("time_list_query", "0")
        params.add_param("whale_cut_token", "")
        params.add_param("cut_version", "1")
        params.add_param("count", "18")
        params.add_param("publish_video_strategy_type", "2")
        params.add_param("update_version_code", "170400")
        params.add_param("pc_client_type", "1")
        params.add_param("version_code", "290100")
        params.add_param("version_name", "29.1.0")
        params.add_param("cookie_enabled", "true")
        params.add_param("screen_width", "1707")
        params.add_param("screen_height", "960")
        params.add_param("browser_language", "zh-CN")
        params.add_param("browser_platform", "Win32")
        params.add_param("browser_name", "Edge")
        params.add_param("browser_version", "125.0.0.0")
        params.add_param("browser_online", "true")
        params.add_param("engine_name", "Blink")
        params.add_param("engine_version", "125.0.0.0")
        params.add_param("os_name", "Windows")
        params.add_param("os_version", "10")
        params.add_param("cpu_core_num", "32")
        params.add_param("device_memory", "8")
        params.add_param("platform", "PC")
        params.add_param("downlink", "10")
        params.add_param("effective_type", "4g")
        params.add_param("round_trip_time", "100")
        params.with_web_id(auth, user_url)
        params.add_param("verifyFp", auth.cookie["s_v_web_id"])
        params.add_param("fp", auth.cookie["s_v_web_id"])
        params.add_param("msToken", auth.msToken)
        params.with_a_bogus()
        response = requests.get(
            f"{DouyinAPI.douyin_url}{api}",
            headers=headers.get(),
            cookies=auth.cookie,
            params=params.get(),
            verify=False,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_work_out_comment(
        auth, url: str, cursor: str = "0", **kwargs
    ) -> dict:
        api = "/aweme/v1/web/comment/list/"
        if "video" in url:
            aweme_id = url.split("/")[-1].split("?")[0]
        else:
            matches = re.findall(r"modal_id=(\d+)", url)
            if not matches:
                raise ValueError("无法从链接中识别视频 ID")
            aweme_id = matches[0]
            url = f"https://www.douyin.com/video/{aweme_id}"
        headers = HeaderBuilder.build(HeaderType.GET)
        headers.set_referer(url)
        params = Params()
        params.add_param("device_platform", "webapp")
        params.add_param("aid", "6383")
        params.add_param("channel", "channel_pc_web")
        params.add_param("aweme_id", aweme_id)
        params.add_param("cursor", cursor)
        params.add_param("count", "5")
        params.add_param("item_type", "0")
        params.add_param("whale_cut_token", "")
        params.add_param("cut_version", "1")
        params.add_param("rcFT", "")
        params.add_param("update_version_code", "170400")
        params.add_param("pc_client_type", "1")
        params.add_param("version_code", "170400")
        params.add_param("version_name", "17.4.0")
        params.add_param("cookie_enabled", "true")
        params.add_param("screen_width", "1707")
        params.add_param("screen_height", "960")
        params.add_param("browser_language", "zh-CN")
        params.add_param("browser_platform", "Win32")
        params.add_param("browser_name", "Edge")
        params.add_param("browser_version", "125.0.0.0")
        params.add_param("browser_online", "true")
        params.add_param("engine_name", "Blink")
        params.add_param("engine_version", "125.0.0.0")
        params.add_param("os_name", "Windows")
        params.add_param("os_version", "10")
        params.add_param("cpu_core_num", "32")
        params.add_param("device_memory", "8")
        params.add_param("platform", "PC")
        params.add_param("downlink", "10")
        params.add_param("effective_type", "4g")
        params.add_param("round_trip_time", "0")
        params.with_web_id(auth, url)
        params.add_param("verifyFp", auth.cookie["s_v_web_id"])
        params.add_param("fp", auth.cookie["s_v_web_id"])
        params.add_param("msToken", auth.msToken)
        params.with_a_bogus()
        response = requests.get(
            f"{DouyinAPI.douyin_url}{api}",
            headers=headers.get(),
            cookies=auth.cookie,
            params=params.get(),
            verify=False,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_my_uid(auth, **kwargs) -> int:
        url = "https://www.douyin.com/aweme/v1/web/query/user/"
        headers = HeaderBuilder.build(HeaderType.GET)
        referer = "https://www.douyin.com/"
        headers.set_header("referer", referer)
        params = Params()
        params.with_platform()
        params.with_web_id(auth, referer)
        params.with_ms_token()
        params.add_param("verifyFp", auth.cookie["s_v_web_id"])
        params.add_param("fp", auth.cookie["s_v_web_id"])
        params.with_a_bogus()
        response = requests.get(
            url,
            params=params.get(),
            verify=False,
            headers=headers.get(),
            cookies=auth.cookie,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = json.loads(response.text)
        return int(payload["user_uid"])

