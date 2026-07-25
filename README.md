# 抖音评论私信工具

本地单页工具，可按视频链接拉取评论、按博主主页批量拉取多个作品的评论，并从评论列表中选择单个用户发送私信。页面、Cookie 和抓取结果都只在本机处理。

## 环境

- Python 3.10+
- Node.js 18+
- 同级目录中已有 `DouYin_Spider` 项目，或在 `.env` 配置 `DOUYIN_SPIDER_ROOT`

```powershell
uv venv
uv pip install -r requirements.txt
npm install
```

## 启动

```powershell
uv run python app.py
```

服务会自动选择可用端口并打开浏览器。按 `Ctrl+C` 停止。

Cookie 可在页面中保存；若当前项目未配置 Cookie，程序会自动读取同级 `DouYin_Spider/.env` 中的 `DY_COOKIES`。私信功能还需要两项浏览器本地凭证，详见 [配置说明](docs/configuration.md)。

## 使用流程

1. 粘贴视频链接，设置最多评论数，点击“加载评论”。
2. 或粘贴博主主页链接，设置作品数和评论总数，点击“拉取博主评论”。默认最多 10 个作品、100 条评论。
3. 单击一条评论，在右侧确认目标用户并填写私信内容。
4. 点击“发送私信”。每次请求只允许一个接收者。

长时间拉取可点击结果栏中的“停止拉取”。接口、限制和故障排查见 [功能说明](docs/usage.md)。
