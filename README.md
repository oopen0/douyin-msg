# 抖音评论私信工具

> 一个在本地运行的单页工具：按视频链接或博主主页批量拉取抖音评论，并支持从评论列表中选择单个用户发送一条私信。页面、Cookie 和抓取结果仅在本机处理，不向第三方上传任何数据。

## 功能特性

- 📥 **拉取视频评论**：粘贴视频链接（支持完整链接、`modal_id` 分享链接和 `v.douyin.com` 短链接），单次最多返回 200 条一级评论。
- 👤 **拉取博主评论**：粘贴博主主页链接，按发布时间读取作品并逐个抓取评论，默认最多 10 个作品、合计 100 条评论，可在页面调整。
- ✉️ **发送单人私信**：从评论列表选择一个用户，向其发送一条文本私信。
- ⏹️ **可随时停止**：长时间拉取时可在页面点击「停止拉取」，后端在当前请求结束后退出。
- 🔒 **纯本地运行**：内置评论接口、私信协议和本地签名实现，仅监听 `127.0.0.1`，Cookie 只保存在本机 `.env`。

## 运行环境

- Python 3.10 及以上
- Node.js 18 及以上

## 安装

```bash
# 1. 克隆仓库
git clone https://github.com/oopen0/douyin-msg.git
cd douyin-msg

# 2. 创建并激活 Python 虚拟环境，安装依赖
uv venv
uv pip install -r requirements.txt

# 3. 安装 JavaScript 签名依赖
npm install
```

> 也可使用 `pip` 代替 `uv pip`，按你习惯的方式管理 Python 环境即可。

## 启动

```bash
uv run python app.py
```

服务会自动选择可用端口（默认 8765）并打开浏览器。按 `Ctrl+C` 停止。

首次使用前请按 [配置说明](docs/configuration.md) 准备 Cookie；如需发送私信，还需额外配置两项浏览器本地凭证。

## 使用流程

1. 粘贴视频链接，设置最多评论数，点击「加载评论」。
2. 或粘贴博主主页链接，设置作品数和评论总数，点击「拉取博主评论」。
3. 单击一条评论，在右侧确认目标用户并填写私信内容。
4. 点击「发送私信」。每次请求只允许一个接收者。

详细的接口、限制和故障排查见 [功能说明](docs/usage.md)，内置模块说明见 [代码结构](docs/code-structure.md)。

## 目录结构

```
douyin-msg/
├── app.py                  # 本地 HTTP 服务、配置保存与任务停止接口
├── douyin_service.py       # 链接解析、评论聚合、凭证识别与私信流程
├── dy_apis/                # 项目使用的最小抖音 Web API 封装
├── builder/                # 请求头、参数、认证对象与私信 Protobuf 请求构造
├── utils/                  # a-bogus、Web Protect 签名及网页参数工具
├── static/
│   ├── index.html          # 单页操作界面
│   ├── dy_ab.js            # 本地 JavaScript 签名实现
│   ├── Request_pb2.py      # 私信请求协议模型
│   └── Response_pb2.py     # 私信响应协议模型
├── tests/                  # 单元测试
├── docs/                   # 文档
├── requirements.txt        # Python 依赖
└── package.json            # JavaScript 签名依赖
```

## 测试

```bash
uv run python -m unittest discover -s tests
```

## 开源协议

本项目基于 [GPL-3.0 License](LICENSE) 协议开源。任何人都可以自由使用、修改和再分发，但基于本项目的衍生作品必须同样以 GPL-3.0 协议开源。

## 免责声明

本项目仅供学习和研究使用，使用者需自行承担使用风险。使用本工具时应严格遵守抖音平台的相关用户协议以及所在地区的法律法规，**不得用于高频营销、骚扰、侵犯他人隐私或其他违法违规场景**。作者不对因使用本工具而产生的任何直接或间接后果承担责任。
