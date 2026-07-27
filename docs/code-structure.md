# 代码结构

本项目可独立运行，不会读取或导入其他项目目录。

## 核心目录

- `app.py`：本地 HTTP 服务、配置保存和任务停止接口。
- `douyin_service.py`：链接解析、评论聚合、凭证识别与私信流程。
- `dy_apis/`：本项目使用的最小抖音 Web API 封装。
- `builder/`：请求头、参数、认证对象和私信 Protobuf 请求构造。
- `utils/dy_util.py`：a-bogus、Web Protect 签名及网页参数工具。
- `static/dy_ab.js`：本地 JavaScript 签名实现。
- `static/Request_pb2.py`、`static/Response_pb2.py`：私信请求与响应协议模型。
- `static/index.html`：单页操作界面。

## 运行时依赖

Python 依赖由 `requirements.txt` 管理，JavaScript 签名依赖由 `package.json` 管理。发布源码时应包含 `builder/`、`dy_apis/`、`utils/` 和 `static/`；不需要包含 `.venv/` 或 `node_modules/`，使用者安装依赖后即可运行。

内置接口与签名代码基于原参考实现裁剪，仅保留本工具实际调用的评论、用户 UID 和单人私信链路。后续维护应直接修改本项目内的模块，不再同步读取任何外部源码仓库。
