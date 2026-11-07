#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人博客 —— 液态玻璃风格
功能：文章 CRUD / Markdown / 标签 / 评论 / 搜索 / RSS / 图片上传 / 管理后台 / 暗色模式
"""
import os, re, json, time, html, secrets, mimetypes, uuid
from datetime import datetime, timezone, timedelta
from functools import wraps

import markdown
from flask import (Flask, request, jsonify, render_template, redirect,
                   url_for, abort, send_from_directory, Response, flash,
                   session, g)
import sqlite3

# ---------------------------------------------------------------- 基础配置

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("BLOG_DATA", os.path.join(BASE_DIR, "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "blog.db")
SECRET_KEY_PATH = os.path.join(DATA_DIR, ".secret")

for d in (DATA_DIR, UPLOAD_DIR):
    os.makedirs(d, exist_ok=True)

def get_secret():
    if os.path.exists(SECRET_KEY_PATH):
        return open(SECRET_KEY_PATH).read().strip()
    key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(key)
    return key

app = Flask(__name__)
app.secret_key = get_secret()
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
app.json.ensure_ascii = False

# 时区
TZ = timezone(timedelta(hours=8))

# ---------------------------------------------------------------- 数据库

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            excerpt TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            category TEXT DEFAULT '',
            cover TEXT DEFAULT '',
            status TEXT DEFAULT 'published',
            views INTEGER DEFAULT 0,
            pinned INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            author TEXT DEFAULT '匿名',
            email TEXT DEFAULT '',
            content TEXT NOT NULL,
            ip TEXT DEFAULT '',
            created_at REAL NOT NULL,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            original TEXT DEFAULT '',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    """)
    # 默认管理员 admin / blog2026
    row = db.execute("SELECT id FROM admins WHERE username='admin'").fetchone()
    if not row:
        import hashlib
        pw = hashlib.sha256("blog2026".encode()).hexdigest()
        db.execute("INSERT INTO admins (username, password_hash) VALUES (?,?)", ("admin", pw))
    db.commit()
    db.close()

init_db()

# ---------------------------------------------------------------- 模板过滤器

@app.template_global("fmt_time")
def fmt_time(ts, fmt="%Y-%m-%d %H:%M"):
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, TZ).strftime(fmt)

@app.template_global("load_tags")
def load_tags(tags_json):
    try:
        return json.loads(tags_json or "[]")
    except Exception:
        return []

@app.template_global("now")
def now():
    return datetime.now(TZ)

# ---------------------------------------------------------------- Markdown

MD = markdown.Markdown(extensions=[
    "extra", "codehilite", "toc", "tables", "fenced_code",
], extension_configs={
    "codehilite": {"guess_lang": False, "noclasses": False},
})

def render_md(text):
    MD.reset()
    return MD.convert(text or "")

def make_excerpt(text, length=200):
    """纯文本摘要。"""
    clean = re.sub(r'[#*`>\[\]()!]|-{3,}', '', text or "")
    clean = re.sub(r'\n+', ' ', clean).strip()
    return clean[:length] + ("…" if len(clean) > length else "")

def slugify(title):
    """生成 URL slug。中文标题用 hash，英文保留。"""
    s = re.sub(r'[^\w\s-]', '', title.lower().strip())
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    if not s or len(s) < 2:
        s = uuid.uuid4().hex[:8]
    # 确保唯一
    db = get_db()
    orig = s
    i = 1
    while db.execute("SELECT id FROM posts WHERE slug=?", (s,)).fetchone():
        s = "%s-%d" % (orig, i)
        i += 1
    return s

# ---------------------------------------------------------------- 认证

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged"):
            return redirect(url_for("admin_login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def check_password(username, password):
    import hashlib
    db = get_db()
    row = db.execute("SELECT password_hash FROM admins WHERE username=?", (username,)).fetchone()
    if not row:
        return False
    return row["password_hash"] == hashlib.sha256(password.encode()).hexdigest()

# ---------------------------------------------------------------- 公开页面

@app.route("/")
def index():
    db = get_db()
    page = request.args.get("page", 1, type=int)
    tag = request.args.get("tag", "")
    category = request.args.get("category", "")
    per_page = 10

    q = "SELECT * FROM posts WHERE status='published'"
    params = []
    if tag:
        q += " AND tags LIKE ?"
        params.append('%"' + tag + '"%')
    if category:
        q += " AND category=?"
        params.append(category)

    # 置顶优先，然后按时间倒序
    q += " ORDER BY pinned DESC, created_at DESC"

    total = db.execute(q, params).fetchone()[0] if False else len(db.execute(q, params).fetchall())
    posts = db.execute(q + " LIMIT ? OFFSET ?",
                       params + [per_page, (page - 1) * per_page]).fetchall()

    # 标签和分类聚合
    all_posts = db.execute("SELECT tags, category FROM posts WHERE status='published'").fetchall()
    tag_counts = {}
    cat_counts = {}
    for p in all_posts:
        for t in json.loads(p["tags"] or "[]"):
            tag_counts[t] = tag_counts.get(t, 0) + 1
        if p["category"]:
            cat_counts[p["category"]] = cat_counts.get(p["category"], 0) + 1

    total_pages = (total + per_page - 1) // per_page
    return render_template("index.html",
                           posts=posts, page=page, total_pages=total_pages,
                           tag_counts=sorted(tag_counts.items(), key=lambda x: -x[1]),
                           cat_counts=sorted(cat_counts.items(), key=lambda x: -x[1]),
                           active_tag=tag, active_cat=category)

@app.route("/post/<slug>")
def post_detail(slug):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE slug=? AND status='published'", (slug,)).fetchone()
    if not post:
        abort(404)

    # 浏览量 +1
    db.execute("UPDATE posts SET views = views + 1 WHERE id=?", (post["id"],))
    db.commit()

    # 渲染 Markdown
    html_content = render_md(post["content"])

    # 评论
    comments = db.execute(
        "SELECT * FROM comments WHERE post_id=? ORDER BY created_at DESC",
        (post["id"],)).fetchall()

    # 上一篇 / 下一篇
    prev = db.execute(
        "SELECT slug, title FROM posts WHERE status='published' AND created_at < ? ORDER BY created_at DESC LIMIT 1",
        (post["created_at"],)).fetchone()
    next_p = db.execute(
        "SELECT slug, title FROM posts WHERE status='published' AND created_at > ? ORDER BY created_at ASC LIMIT 1",
        (post["created_at"],)).fetchone()

    # 解析标签
    tags = json.loads(post["tags"] or "[]")

    return render_template("post.html", post=post, content=html_content,
                           comments=comments, tags=tags, prev=prev, next=next_p)

@app.route("/search")
def search():
    db = get_db()
    q = request.args.get("q", "").strip()
    results = []
    if q:
        like = "%" + q + "%"
        results = db.execute(
            "SELECT * FROM posts WHERE status='published' AND (title LIKE ? OR content LIKE ? OR tags LIKE ?) ORDER BY created_at DESC",
            (like, like, like)).fetchall()
    return render_template("search.html", q=q, results=results)

@app.route("/archive")
def archive():
    db = get_db()
    posts = db.execute(
        "SELECT id, slug, title, created_at, tags FROM posts WHERE status='published' ORDER BY created_at DESC"
    ).fetchall()
    # 按年月分组
    grouped = {}
    for p in posts:
        dt = datetime.fromtimestamp(p["created_at"], TZ)
        key = dt.strftime("%Y 年 %m 月")
        grouped.setdefault(key, []).append(p)
    return render_template("archive.html", grouped=grouped)

@app.route("/tags")
def tags_page():
    db = get_db()
    all_posts = db.execute("SELECT tags FROM posts WHERE status='published'").fetchall()
    tag_counts = {}
    for p in all_posts:
        for t in json.loads(p["tags"] or "[]"):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    return render_template("tags.html", tag_counts=sorted(tag_counts.items(), key=lambda x: -x[1]))

# ---------------------------------------------------------------- RSS

@app.route("/rss")
def rss():
    db = get_db()
    posts = db.execute(
        "SELECT * FROM posts WHERE status='published' ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    items = []
    for p in posts:
        url = url_for("post_detail", slug=p["slug"], _external=True)
        pub = datetime.fromtimestamp(p["created_at"], TZ).strftime("%a, %d %b %Y %H:%M:%S +0800")
        items.append(f"""    <item>
      <title>{html.escape(p['title'])}</title>
      <link>{url}</link>
      <guid>{url}</guid>
      <pubDate>{pub}</pubDate>
      <description>{html.escape(p['excerpt'] or '')}</description>
    </item>""")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>个人博客</title>
  <link>{url_for('index', _external=True)}</link>
  <description>个人博客 RSS</description>
  <language>zh-cn</language>
{chr(10).join(items)}
</channel>
</rss>"""
    return Response(xml, mimetype="application/rss+xml")

# ---------------------------------------------------------------- 评论

@app.route("/post/<slug>/comment", methods=["POST"])
def add_comment(slug):
    db = get_db()
    post = db.execute("SELECT id FROM posts WHERE slug=? AND status='published'", (slug,)).fetchone()
    if not post:
        abort(404)

    author = (request.form.get("author") or "匿名").strip()[:50]
    email = (request.form.get("email") or "").strip()[:100]
    content = (request.form.get("content") or "").strip()
    if not content:
        return redirect(url_for("post_detail", slug=slug) + "#comments")

    ip = request.remote_addr or ""
    db.execute(
        "INSERT INTO comments (post_id, author, email, content, ip, created_at) VALUES (?,?,?,?,?,?)",
        (post["id"], author, email, content, ip, time.time()))
    db.commit()
    return redirect(url_for("post_detail", slug=slug) + "#comments")

# ---------------------------------------------------------------- 图片上传（公开 API，供编辑器用）

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if not session.get("admin_logged"):
        return jsonify({"error": "未登录"}), 401
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "没有文件"}), 400
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        return jsonify({"error": "不支持的格式"}), 400
    fname = uuid.uuid4().hex[:12] + ext
    f.save(os.path.join(UPLOAD_DIR, fname))
    db = get_db()
    db.execute("INSERT OR IGNORE INTO images (filename, original, created_at) VALUES (?,?,?)",
               (fname, f.filename or "", time.time()))
    db.commit()
    return jsonify({"url": "/uploads/" + fname})

@app.route("/uploads/<path:fname>")
def uploaded_file(fname):
    return send_from_directory(UPLOAD_DIR, fname)

# ---------------------------------------------------------------- 管理后台

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if check_password(username, password):
            session["admin_logged"] = True
            session["admin_user"] = username
            nxt = request.args.get("next") or url_for("admin")
            return redirect(nxt)
        return render_template("admin_login.html", error="用户名或密码错误")
    return render_template("admin_login.html", error=None)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin")
@login_required
def admin():
    db = get_db()
    posts = db.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    comments = db.execute(
        "SELECT c.*, p.title as post_title, p.slug as post_slug FROM comments c JOIN posts p ON c.post_id=p.id ORDER BY c.created_at DESC LIMIT 50"
    ).fetchall()
    stats = {
        "total": len(posts),
        "published": sum(1 for p in posts if p["status"] == "published"),
        "draft": sum(1 for p in posts if p["status"] == "draft"),
        "comments": db.execute("SELECT COUNT(*) FROM comments").fetchone()[0],
        "views": db.execute("SELECT COALESCE(SUM(views),0) FROM posts").fetchone()[0],
    }
    return render_template("admin.html", posts=posts, comments=comments, stats=stats)

@app.route("/admin/post/new", methods=["GET", "POST"])
@login_required
def admin_new_post():
    if request.method == "POST":
        return _save_post(None)
    return render_template("admin_edit.html", post=None)

@app.route("/admin/post/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_post(pid):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
    if not post:
        abort(404)
    if request.method == "POST":
        return _save_post(pid)
    return render_template("admin_edit.html", post=post)

def _save_post(pid):
    db = get_db()
    title = (request.form.get("title") or "").strip()
    content = request.form.get("content") or ""
    tags_raw = (request.form.get("tags") or "").strip()
    category = (request.form.get("category") or "").strip()
    cover = (request.form.get("cover") or "").strip()
    status = request.form.get("status", "published")
    pinned = 1 if request.form.get("pinned") else 0

    if not title:
        return render_template("admin_edit.html", post=None, error="标题不能为空")

    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    excerpt = make_excerpt(content)
    now = time.time()

    if pid:
        post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        slug = post["slug"]
        db.execute(
            "UPDATE posts SET title=?, content=?, excerpt=?, tags=?, category=?, cover=?, status=?, pinned=?, updated_at=? WHERE id=?",
            (title, content, excerpt, json.dumps(tags, ensure_ascii=False), category,
             cover, status, pinned, now, pid))
    else:
        slug = slugify(title)
        db.execute(
            "INSERT INTO posts (slug, title, content, excerpt, tags, category, cover, status, pinned, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (slug, title, content, excerpt, json.dumps(tags, ensure_ascii=False), category,
             cover, status, pinned, now, now))
    db.commit()
    return redirect(url_for("admin"))

@app.route("/admin/post/<int:pid>/delete", methods=["POST"])
@login_required
def admin_delete_post(pid):
    db = get_db()
    db.execute("DELETE FROM posts WHERE id=?", (pid,))
    db.commit()
    return redirect(url_for("admin"))

@app.route("/admin/comment/<int:cid>/delete", methods=["POST"])
@login_required
def admin_delete_comment(cid):
    db = get_db()
    db.execute("DELETE FROM comments WHERE id=?", (cid,))
    db.commit()
    return redirect(url_for("admin"))

@app.route("/admin/password", methods=["POST"])
@login_required
def admin_change_password():
    import hashlib
    old = request.form.get("old_password", "")
    new = request.form.get("new_password", "")
    if len(new) < 6:
        return redirect(url_for("admin") + "?err=密码至少6位")
    if not check_password(session.get("admin_user", ""), old):
        return redirect(url_for("admin") + "?err=原密码错误")
    db = get_db()
    db.execute("UPDATE admins SET password_hash=? WHERE username=?",
               (hashlib.sha256(new.encode()).hexdigest(), session.get("admin_user", "")))
    db.commit()
    return redirect(url_for("admin") + "?ok=密码已修改")

# ---------------------------------------------------------------- 健康检查

@app.route("/api/health")
def health():
    return jsonify({"ok": True})

# ---------------------------------------------------------------- 错误页

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

# ---------------------------------------------------------------- 启动

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), threaded=True)
