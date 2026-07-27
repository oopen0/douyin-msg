import base64
import json

from dy_apis.douyin_api import DouyinAPI
from utils.dy_util import generate_msToken, trans_cookies


class DouyinAuth:
    def __init__(self):
        self.cookie = None
        self.cookie_str = None
        self.private_key = None
        self.ticket = None
        self.ts_sign = None
        self.client_cert = None
        self.ree_public_key = None
        self.uid = None
        self.msToken = None

    def perepare_auth(self, cookieStr: str, web_protect_: str = "", keys_: str = ""):
        self.cookie = trans_cookies(cookieStr)
        self.cookie_str = cookieStr
        self.msToken = self.cookie.get("msToken") or generate_msToken()
        self.cookie["msToken"] = self.msToken
        self.cookie_str = "; ".join(f"{key}={value}" for key, value in self.cookie.items())
        if web_protect_:
            web_protect = json.loads(json.loads(web_protect_)["data"])
            self.ticket = web_protect["ticket"]
            self.ts_sign = web_protect["ts_sign"]
            self.client_cert = web_protect["client_cert"]
        if keys_:
            keys = json.loads(json.loads(keys_)["data"])
            self.private_key = keys["ec_privateKey"]
            self.ree_public_key = base64.b64encode(self.private_key.encode()).decode()

    def get_uid(self):
        if self.uid is None:
            self.uid = DouyinAPI.get_my_uid(self)
        return self.uid

