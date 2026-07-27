# 配置说明

## Cookie

登录抖音网页版后，在浏览器开发者工具的 Network 面板中选择任意 `www.douyin.com` 请求，复制 Request Headers 中的完整 `Cookie`。可粘贴到页面右侧保存，也可写入：

```dotenv
DY_COOKIES='sessionid=...; s_v_web_id=...; ...'
```

评论抓取至少需要有效的 `sessionid` 和 `s_v_web_id`。Cookie 只保存在项目根目录 `.env`，该文件已加入 `.gitignore`。

## 主动私信凭证

主动私信协议使用浏览器安全 SDK 的签名私钥和 Web Protect 会话凭证。这两项位于抖音页面的 `localStorage`，不包含在 Cookie 中。

在已登录的 `https://www.douyin.com/` 页面按 F12 打开 Console，分别执行：

```javascript
copy(localStorage.getItem('security-sdk/s_sdk_crypt_sdk'))
```

```javascript
copy(localStorage.getItem('security-sdk/s_sdk_sign_data_key/web_protect'))
```

将两次复制的完整值原样写入 `.env`：

```dotenv
DY_SECURITY_KEYS='粘贴第一项'
DY_WEB_PROTECT='粘贴第二项'
```

保存后重启本地服务。程序会根据 `ec_privateKey`、`ticket` 等实际字段自动识别两份数据，因此即使变量顺序放反也能兼容；仍建议按上面的变量名保存，方便后续维护。页面右侧显示“私信凭证就绪”即可发送。凭证可能随登录状态更新而失效，失效后重新复制。

## 可选项

```dotenv
APP_HOST=127.0.0.1
APP_PORT=8765
```

只建议监听 `127.0.0.1`，避免把带有登录态的本地接口暴露给局域网。
