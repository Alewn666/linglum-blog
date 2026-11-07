# 个人博客 · 液态玻璃风格

Flask 单文件博客：文章 CRUD、Markdown、标签、评论、搜索、RSS、图片上传、管理后台与暗色模式。

> 本仓库由 NAS 归档包整理发布。已剥离运行时数据、密钥、审计日志与大型二进制镜像；
> 文档中的真实口令与内网 IP 已脱敏。镜像请用仓库内构建脚本生成，或从 Releases 获取。

## 目录结构

```
├── Dockerfile
├── app.py
├── docs/
├── requirements.txt
├── static/
├── templates/
├── test_blog.py
├── ui_test_layout.py
├── docs/检查与修复记录.md
├── static/css/
├── static/js/
├── templates/404.html
├── templates/admin.html
├── templates/admin_edit.html
```

## 使用

请参考仓库内的说明文档与构建/部署脚本；首次运行前把示例地址、口令改成自己的值。

## 安全约定

- `data/`、`.env`、`env.*`、`*.pem`、`*.keystore`、`config.json`、`*.db`、`*.log` 均已在 `.gitignore` 中排除，切勿强制提交。
- 文档里的 `192.168.1.100` 与 `203.0.113.x` 是示例地址，`<REDACTED_PASSWORD>` 是脱敏占位符。
- 涉及管理后台的服务请只在可信局域网内使用。

## 许可证

MIT
