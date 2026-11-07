# ✨ 灵珑博客 · 液态玻璃风格

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-4B8BBE)
![Release](https://img.shields.io/github/v/release/Alewn666/linglum-blog?label=release)

> 一个 **505 行单文件**就能完整跑起来的个人博客：文章、Markdown、代码高亮、标签、评论、搜索、归档、RSS、图片上传、管理后台、暗色模式，一个都不少。界面是自写的液态玻璃（glassmorphism）风格。

写博客最常见的两种麻烦：一是装个 CMS 要配数据库、插件、主题；二是用静态生成器又要搭构建链。这个项目选了第三条路——`app.py` 一个文件包含全部路由与逻辑，数据用 Python 内置的 `sqlite3` 存在本地 `data/` 目录（不用单独部署数据库服务），Markdown 直接渲染，`docker build` 一下就能上线；想改界面就改 `templates/` 和 `static/css/glass.css`，没有构建步骤。

## 功能

| 分类 | 内容 |
| --- | --- |
| 阅读 | 首页列表、`/post/<slug>` 正文、归档、标签云、全文搜索、RSS 订阅 |
| 写作 | Markdown 正文 + `codehilite`（Pygments）代码高亮、草稿/发布、图片上传 |
| 互动 | 评论提交与后台删除 |
| 管理 | 登录 / 登出 / 改密、文章新建 / 编辑 / 删除、评论管理 |
| 外观 | 液态玻璃卡片、毛玻璃导航栏、默认深色主题（可一键切换浅色、localStorage 记忆）、404 页 |
| 运维 | `/api/health` 健康检查、gunicorn 多线程、Dockerfile 开箱即用 |

前端是 10 个 Jinja2 模板 + 一份 `glass.css` + 一份 `main.js`，没有前端框架、没有 npm、没有打包器。

## 快速开始

**Docker（推荐）**：

```bash
docker build -t linglum-blog .
docker run -d --name blog --restart unless-stopped \
  -p 8080:8080 -e TZ=Asia/Shanghai \
  -v "$PWD/data:/data" linglum-blog
```

**本地运行**：

```bash
pip install -r requirements.txt
PORT=8080 python3 app.py
curl http://127.0.0.1:8080/api/health
```

打开后先访问 `/admin/login` 设置管理口令，之后就能写第一篇文章了。

## 配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `80`（Docker 内为 `8080`） | 监听端口 |
| `BLOG_DATA` | `./data` | 文章数据、上传图片与配置的存放目录 |
| `TZ` | `Asia/Shanghai` | 容器时区 |
| `PYTHONUNBUFFERED` | `1` | 容器日志实时输出 |

## 目录结构

```
linglum-blog/
├── app.py                    # 全部后端逻辑（约 505 行）
├── requirements.txt          # flask / markdown / gunicorn / pygments
├── Dockerfile                # python:3.11-slim + gunicorn（8 线程）
├── templates/                # base / index / post / archive / tags / search
│                             # admin / admin_edit / admin_login / 404
├── static/
│   ├── css/glass.css         # 液态玻璃样式与暗色模式
│   └── js/main.js
├── test_blog.py              # 功能测试（路由 / CRUD / 搜索 / RSS …）
├── ui_test_layout.py         # 界面布局回归
└── docs/检查与修复记录.md     # 排障实录
```

## 测试

```bash
python3 test_blog.py          # 后端功能回归
python3 ui_test_layout.py     # 布局与渲染检查
```

## 架构

```
浏览器 ── Jinja2 模板（10 个） + glass.css ── Flask app.py
                                             ├─ Markdown + Pygments 渲染
                                             ├─ BLOG_DATA 本地数据目录
                                             └─ gunicorn gthread × 8
```

用 Python 内置 `sqlite3`，无需单独跑数据库服务；备份就是把 `data/` 目录打包带走，迁移到另一台机器只要挂同一个目录。

## 说明与边界

- 定位是**个人或小团队博客**，不含多用户、权限分级与评论反垃圾机制。
- 数据存本地文件系统，多实例部署需要自己处理共享存储。
- 管理后台请设在可信网络内，或自行加反向代理与 HTTPS。
- `data/`、`.env`、`*.db`、`*.log` 已在 `.gitignore` 中排除，公开仓库不含真实文章数据与凭据。

## 许可证

MIT — 见 [LICENSE](LICENSE)。本项目由 NAS 归档包整理后公开发布。
