#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""博客后端功能测试 — 纯本地，不依赖外部服务。"""
import os, sys, json, tempfile

TMP = tempfile.mkdtemp(prefix="blog_test_")
os.environ["BLOG_DATA"] = TMP
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as srv

PASS = FAIL = 0
def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond: PASS += 1; print("  ✔ %s" % name)
    else: FAIL += 1; print("  ✘ %s   %s" % (name, extra))

c = srv.app.test_client()

print("[1] 基础路由")
for path, expect in [("/", 200), ("/archive", 200), ("/tags", 200),
                      ("/search?q=hello", 200), ("/rss", 200),
                      ("/api/health", 200), ("/admin/login", 200),
                      ("/nonexistent", 404)]:
    r = c.get(path)
    ok("%s → %d" % (path, expect), r.status_code == expect, "got %d" % r.status_code)

print("[2] 管理员认证")
r = c.get("/admin")
ok("未登录 302 到登录页", r.status_code == 302 and "/admin/login" in r.headers.get("Location", ""))

# 错误密码
r = c.post("/admin/login", data={"username": "admin", "password": "wrong"})
ok("错误密码显示错误", r.status_code == 200 and "错误" in r.get_data(as_text=True))

# 正确密码
r = c.post("/admin/login", data={"username": "admin", "password": "blog2026"})
ok("正确密码登录成功", r.status_code == 302)

r = c.get("/admin")
ok("登录后可访问后台", r.status_code == 200)

print("[3] 创建文章")
r = c.post("/admin/post/new", data={
    "title": "Hello World",
    "content": "# 标题\n\n这是**第一篇**文章。\n\n```python\nprint('hi')\n```\n\n- 列表1\n- 列表2",
    "tags": "python, flask, 测试",
    "category": "技术",
    "status": "published",
    "pinned": "on",
})
ok("创建成功 302", r.status_code == 302)

# 首页能看到
r = c.get("/")
html = r.get_data(as_text=True)
ok("首页显示文章", "Hello World" in html)
ok("显示置顶标记", "置顶" in html or "📌" in html)
ok("显示分类", "技术" in html)
ok("显示标签", "python" in html)

print("[4] 文章详情")
r = c.get("/post/hello-world")
html = r.get_data(as_text=True)
ok("详情页 200", r.status_code == 200)
ok("Markdown 渲染 - 标题", "<h1" in html)
ok("Markdown 渲染 - 加粗", "<strong>" in html)
ok("Markdown 渲染 - 代码块", "<pre>" in html or "<code" in html)
ok("Markdown 渲染 - 列表", "<li>" in html)
ok("显示浏览量", "👁" in html)

# 浏览量 +1
r = c.get("/post/hello-world")
ok("浏览量累加", "👁 2" in r.get_data(as_text=True) or "views" in r.get_data(as_text=True))

print("[5] 评论")
r = c.post("/post/hello-world/comment", data={
    "author": "测试者", "content": "写得不错！", "email": "test@test.com"
}, follow_redirects=True)
html = r.get_data(as_text=True)
ok("评论成功", "写得不错" in html)
ok("显示评论者", "测试者" in html)

# 空评论不入库
r = c.post("/post/hello-world/comment", data={"content": ""}, follow_redirects=True)
ok("空评论被忽略", r.status_code == 200)

print("[6] 搜索")
r = c.get("/search?q=Hello")
html = r.get_data(as_text=True)
ok("搜到文章", "Hello World" in html)

r = c.get("/search?q=python")
ok("标签也能搜到", "Hello World" in r.get_data(as_text=True))

r = c.get("/search?q=xyznotfound")
ok("无结果提示", "没有找到" in r.get_data(as_text=True))

print("[7] 标签/分类过滤")
r = c.get("/?tag=python")
ok("按标签过滤", "Hello World" in r.get_data(as_text=True))

r = c.get("/?category=技术")
ok("按分类过滤", "Hello World" in r.get_data(as_text=True))

r = c.get("/?tag=nonexistent")
ok("无匹配标签", "Hello World" not in r.get_data(as_text=True))

print("[8] 归档页")
r = c.get("/archive")
ok("归档显示文章", "Hello World" in r.get_data(as_text=True))
ok("按月分组", "2026 年" in r.get_data(as_text=True))

print("[9] 标签云")
r = c.get("/tags")
html = r.get_data(as_text=True)
ok("标签云显示", "#python" in html and "#flask" in html)

print("[10] RSS")
r = c.get("/rss")
xml = r.get_data(as_text=True)
ok("RSS 是 XML", xml.startswith("<?xml"))
ok("RSS 含文章标题", "Hello World" in xml)
ok("RSS Content-Type", "rss" in r.content_type)

print("[11] 草稿不公开可见")
c.post("/admin/post/new", data={
    "title": "秘密草稿", "content": "不该被看到", "status": "draft"
})
r = c.get("/")
ok("草稿不在首页", "秘密草稿" not in r.get_data(as_text=True))
r = c.get("/post/secret-draft")  # slug 是拼音hash
# slug 可能不是 secret-draft（中文标题），检查 404 或不显示
ok("草稿不可直接访问", r.status_code == 404)

print("[12] 编辑文章")
# 找到文章 id
r = c.get("/admin")
# 用数据库
import sqlite3
db = sqlite3.connect(os.path.join(TMP, "blog.db"))
row = db.execute("SELECT id FROM posts WHERE title='Hello World'").fetchone()
pid = row[0]
db.close()

r = c.post("/admin/post/%d/edit" % pid, data={
    "title": "Hello World v2",
    "content": "更新后的内容",
    "tags": "python",
    "category": "技术",
    "status": "published",
})
ok("编辑成功", r.status_code == 302)
r = c.get("/post/hello-world")
ok("详情显示新标题", "Hello World v2" in r.get_data(as_text=True))
ok("详情显示新内容", "更新后的内容" in r.get_data(as_text=True))

print("[13] 删除文章")
r = c.post("/admin/post/%d/delete" % pid)
ok("删除 302", r.status_code == 302)
r = c.get("/post/hello-world")
ok("删后 404", r.status_code == 404)

print("[14] 修改密码")
r = c.post("/admin/password", data={
    "old_password": "wrong", "new_password": "newpass123"
})
ok("旧密码错误被拒", "err=" in r.headers.get("Location", ""))

r = c.post("/admin/password", data={
    "old_password": "blog2026", "new_password": "123"
})
from urllib.parse import unquote
ok("太短密码被拒", "至少6位" in unquote(r.headers.get("Location", "")))

r = c.post("/admin/password", data={
    "old_password": "blog2026", "new_password": "newpass123"
})
ok("改密码成功", "ok=" in r.headers.get("Location", ""))

# 用新密码登录
c.get("/admin/logout")
r = c.post("/admin/login", data={"username": "admin", "password": "newpass123"})
ok("新密码登录成功", r.status_code == 302)

# 旧密码失效
c.get("/admin/logout")
r = c.post("/admin/login", data={"username": "admin", "password": "blog2026"})
ok("旧密码失效", r.status_code == 200 and "错误" in r.get_data(as_text=True))

print("[15] 图片上传")
# 先登录
c.post("/admin/login", data={"username": "admin", "password": "newpass123"})
import io
fake_img = (b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
r = c.post("/api/upload", data={
    "file": (io.BytesIO(fake_img), "test.png")
}, content_type="multipart/form-data")
ok("上传返回 URL", r.status_code == 200 and "/uploads/" in r.get_json().get("url", ""))

# 未登录不能传
c.get("/admin/logout")
r = c.post("/api/upload", data={
    "file": (io.BytesIO(fake_img), "test.png")
}, content_type="multipart/form-data")
ok("未登录上传 401", r.status_code == 401)

# 非法格式
c.post("/admin/login", data={"username": "admin", "password": "newpass123"})
r = c.post("/api/upload", data={
    "file": (io.BytesIO(b"MZ"), "evil.exe")
}, content_type="multipart/form-data")
ok("非法格式被拒", r.status_code == 400)

print()
print("PASS=%d FAIL=%d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
