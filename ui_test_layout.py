#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""博客「展开栏不再把内容挤下去」——真浏览器验证（自带服务、全新数据目录）。

    python3 ui_test_layout.py

覆盖：
  1. 手机菜单展开：**首屏卡片位置不许动**（改前会被推下 281px）、菜单位置是 absolute 悬浮
  2. 菜单能关：点别处 / Esc / 点菜单项
  3. 管理后台「修改密码」：变成弹层，展开时「文章管理」卡片位置不动
  4. 弹层能关：✕ / Esc / 点遮罩
  5. 三种屏幕不横向溢出、零 JS 报错
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 5195
BASE = "http://127.0.0.1:%d/" % PORT
PASS = FAIL = 0
ERRS = []


def ck(cond, name, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✔ %s" % name)
    else:
        FAIL += 1
        print("  ✘ %s   %s" % (name, extra))


def wait_port(port, timeout=30):
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/health" % port, timeout=2) as r:
                if json.load(r).get("ok"):
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def main():
    data = tempfile.mkdtemp(prefix="blog_ui_")
    env = dict(os.environ)
    env.update({"PORT": str(PORT), "BLOG_DATA": data})
    # 服务端日志留下来（排查用），别丢进 DEVNULL
    logf = open("/tmp/blog_ui_server.log", "w")
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=HERE, env=env,
                            stdout=logf, stderr=subprocess.STDOUT)
    try:
        if not wait_port(PORT):
            ck(False, "服务起来了")
            return 1
        ck(True, "服务起来了")

        import asyncio
        from playwright.async_api import async_playwright

        async def run():
            async with async_playwright() as p:
                b = await p.chromium.launch(args=["--no-sandbox"])
                pg = await b.new_page(viewport={"width": 390, "height": 844})
                pg.on("pageerror", lambda e: ERRS.append(str(e)[:200]))
                pg.on("console", lambda m: ERRS.append(m.text[:200]) if m.type == "error" else None)

                await pg.goto(BASE, wait_until="domcontentloaded")
                await pg.wait_for_timeout(900)

                print("== 1. 手机菜单：展开不许挤内容 ==")
                before = await pg.evaluate("""() => {
                  const c = document.querySelector('.post-card, .empty-state, .container');
                  return {top: Math.round(c.getBoundingClientRect().top),
                          navH: Math.round(document.querySelector('.glass-nav').getBoundingClientRect().height)};
                }""")
                await pg.eval_on_selector("#navBurger", "el => el.click()")
                await pg.wait_for_timeout(400)
                after = await pg.evaluate("""() => {
                  const c = document.querySelector('.post-card, .empty-state, .container');
                  const menu = document.getElementById('navMobile');
                  return {top: Math.round(c.getBoundingClientRect().top),
                          navH: Math.round(document.querySelector('.glass-nav').getBoundingClientRect().height),
                          menuPos: getComputedStyle(menu).position,
                          menuVisible: !menu.classList.contains('hidden'),
                          menuTop: Math.round(menu.getBoundingClientRect().top)};
                }""")
                ck(after["menuVisible"], "点 ☰ 菜单展开了")
                ck(after["menuPos"] == "absolute", "菜单是悬浮定位（absolute）", after["menuPos"])
                # 面板要"小"：别盖住大半屏（第一版是全宽面板，挡住内容太多）
                geo = await pg.evaluate("""() => {
                  const m = document.getElementById('navMobile').getBoundingClientRect();
                  return {w: Math.round(m.width), h: Math.round(m.height),
                          vw: window.innerWidth, vh: window.innerHeight,
                          cover: (m.width * m.height) / (window.innerWidth * window.innerHeight)};
                }""")
                # 关键：菜单底必须**不透明**——否则后面的正文透上来，和菜单上的字叠在一起
                alpha = await pg.eval_on_selector(
                    "#navMobile",
                    "el => { const c = getComputedStyle(el).backgroundColor;"
                    " const m = c.match(/rgba?\\(([^)]+)\\)/);"
                    " const p = m[1].split(',').map(s => s.trim());"
                    " return p.length > 3 ? parseFloat(p[3]) : 1; }")
                ck(alpha >= 0.98, "菜单底色不透明（alpha=%.2f，改前半透明会让后面的字透上来）" % alpha)
                ck(geo["w"] >= geo["vw"] * 0.8, "菜单是整条面板（%d/%d）" % (geo["w"], geo["vw"]))
                ck(after["top"] == before["top"],
                   "首屏内容**没有被推下去**（改前 +281px）",
                   "改前 %d → 现在 %d" % (before["top"], after["top"]))
                ck(after["navH"] == before["navH"],
                   "导航栏高度不变（改前 63 → 344）",
                   "%d → %d" % (before["navH"], after["navH"]))
                await pg.screenshot(path="/tmp/blog_menu_fixed.png")

                print("== 2. 菜单能关 ==")
                await pg.eval_on_selector("body", "el => el.click()")     # 点别处
                await pg.wait_for_timeout(250)
                ck(await pg.eval_on_selector("#navMobile", "el => el.classList.contains('hidden')"),
                   "点别处 → 关闭")
                await pg.eval_on_selector("#navBurger", "el => el.click()")
                await pg.wait_for_timeout(200)
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(250)
                ck(await pg.eval_on_selector("#navMobile", "el => el.classList.contains('hidden')"),
                   "Esc → 关闭")
                await pg.eval_on_selector("#navBurger", "el => el.click()")
                await pg.wait_for_timeout(200)
                # 测试实例是空博客（页面不够高、滚不动）→ 先把页面撑高再滚，才测得到这个行为
                await pg.evaluate("document.body.style.minHeight = '3000px'")
                await pg.evaluate("window.scrollTo(0, 300)")
                await pg.wait_for_timeout(500)
                ck(await pg.eval_on_selector("#navMobile", "el => el.classList.contains('hidden')"),
                   "一滚动 → 自动收起（不挡着看内容）")
                await pg.evaluate("window.scrollTo(0, 0)")
                await pg.wait_for_timeout(300)

                print("== 3. 管理后台：修改密码 = 弹层 ==")
                await pg.goto(BASE + "admin/login", wait_until="domcontentloaded")
                await pg.fill("input[name='username']", "admin")
                await pg.fill("input[name='password']", "blog2026")
                await pg.eval_on_selector("button[type='submit'], input[type='submit']", "el => el.click()")
                await pg.wait_for_url("**/admin", timeout=8000)
                await pg.wait_for_timeout(700)
                ck(await pg.eval_on_selector("#pwModal", "el => el.classList.contains('hidden')"),
                   "弹层默认是收起的")
                t1 = await pg.eval_on_selector(".admin-table", "el => Math.round(el.getBoundingClientRect().top)")
                await pg.eval_on_selector("#btnPwOpen", "el => el.click()")
                await pg.wait_for_timeout(350)
                vis = await pg.eval_on_selector("#pwModal", "el => !el.classList.contains('hidden')")
                fixed = await pg.eval_on_selector("#pwModal", "el => getComputedStyle(el).position")
                t2 = await pg.eval_on_selector(".admin-table", "el => Math.round(el.getBoundingClientRect().top)")
                ck(vis, "点「修改管理员密码」弹出弹层")
                ck(fixed == "fixed", "弹层是 fixed 覆盖层", fixed)
                ck(t2 == t1, "「文章管理」表格**没被挤动**（改前会被推下去）",
                   "%d → %d" % (t1, t2))
                ck(await pg.eval_on_selector("#pwModal input[name='old_password']", "el => !!el"),
                   "弹层里还是原来的表单（后端接口没变）")
                await pg.screenshot(path="/tmp/blog_admin_modal.png")

                print("== 4. 弹层能关 ==")
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(250)
                ck(await pg.eval_on_selector("#pwModal", "el => el.classList.contains('hidden')"), "Esc → 关闭")
                await pg.eval_on_selector("#btnPwOpen", "el => el.click()")
                await pg.wait_for_timeout(250)
                await pg.eval_on_selector("#btnPwClose", "el => el.click()")
                await pg.wait_for_timeout(250)
                ck(await pg.eval_on_selector("#pwModal", "el => el.classList.contains('hidden')"), "✕ → 关闭")
                await pg.eval_on_selector("#btnPwOpen", "el => el.click()")
                await pg.wait_for_timeout(250)
                await pg.mouse.click(10, 10)                     # 点遮罩空白
                await pg.wait_for_timeout(250)
                ck(await pg.eval_on_selector("#pwModal", "el => el.classList.contains('hidden')"),
                   "点遮罩 → 关闭")

                print("== 5. 多屏幕不溢出 + 零 JS 报错 ==")
                for w, h in ((390, 844), (768, 1024), (1280, 800)):
                    await pg.set_viewport_size({"width": w, "height": h})
                    await pg.goto(BASE, wait_until="domcontentloaded")
                    await pg.wait_for_timeout(500)
                    over = await pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                    ck(not over, "%dx%d 没有横向溢出" % (w, h))
                ck(not ERRS, "没有 JS 报错", str(ERRS[:3]))
                await b.close()

        asyncio.run(run())
    finally:
        proc.terminate()
        try:
            logf.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(data, ignore_errors=True)

    print("\n结果：%d 通过 / %d 失败" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
