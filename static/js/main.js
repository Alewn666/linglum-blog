/* 液态玻璃博客 — 前端交互 */
(function () {
  'use strict';

  // ---------- 主题切换 ----------
  var saved = localStorage.getItem('theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
  else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches)
    document.documentElement.setAttribute('data-theme', 'light');

  var toggle = document.getElementById('themeToggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var cur = document.documentElement.getAttribute('data-theme');
      var next = cur === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    });
  }

  // ---------- 移动端菜单（现在是悬浮面板，展开不挤内容） ----------
  var burger = document.getElementById('navBurger');
  var mobile = document.getElementById('navMobile');
  if (burger && mobile) {
    var closeMenu = function () {
      mobile.classList.add('hidden');
      burger.setAttribute('aria-expanded', 'false');
    };
    burger.addEventListener('click', function (e) {
      e.stopPropagation();
      var willOpen = mobile.classList.contains('hidden');
      mobile.classList.toggle('hidden', !willOpen);
      burger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
    // 点菜单项 → 关；点别处 → 关；Esc → 关；转回桌面宽度 → 关
    mobile.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeMenu();
    });
    document.addEventListener('click', function (e) {
      if (!mobile.classList.contains('hidden')
          && !e.target.closest('#navMobile') && !e.target.closest('#navBurger')) {
        closeMenu();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !mobile.classList.contains('hidden')) closeMenu();
    });
    // 一滚动就收起：菜单浮在内容上，别让它一直挡着
    window.addEventListener('scroll', function () {
      if (!mobile.classList.contains('hidden') && window.scrollY > 4) closeMenu();
    }, { passive: true });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 768) closeMenu();     // 断点与 CSS 里的媒体查询一致
    });
  }

  // ---------- 弹层（管理后台「修改密码」） ----------
  var pwModal = document.getElementById('pwModal');
  if (pwModal) {
    var openPw = function () {
      pwModal.classList.remove('hidden');
      var first = pwModal.querySelector('input');
      if (first) setTimeout(function () { first.focus(); }, 60);
    };
    var closePw = function () { pwModal.classList.add('hidden'); };
    var op = document.getElementById('btnPwOpen');
    if (op) op.addEventListener('click', openPw);
    var cl = document.getElementById('btnPwClose');
    if (cl) cl.addEventListener('click', closePw);
    pwModal.addEventListener('click', function (e) {
      if (e.target === pwModal) closePw();           // 点遮罩空白处关闭
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !pwModal.classList.contains('hidden')) closePw();
    });
  }

  // ---------- 导航滚动效果 ----------
  var nav = document.querySelector('.glass-nav');
  if (nav) {
    var lastY = 0;
    window.addEventListener('scroll', function () {
      var y = window.scrollY;
      if (y > 60) {
        nav.style.boxShadow = '0 4px 30px rgba(0,0,0,0.15)';
      } else {
        nav.style.boxShadow = 'none';
      }
      lastY = y;
    }, { passive: true });
  }

  // ---------- 卡片入场动画 ----------
  var cards = document.querySelectorAll('.glass-card, .post-card');
  if ('IntersectionObserver' in window && cards.length) {
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.style.opacity = '1';
          e.target.style.transform = 'translateY(0)';
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.08 });

    cards.forEach(function (c, i) {
      c.style.opacity = '0';
      c.style.transform = 'translateY(24px)';
      c.style.transition = 'opacity 0.5s ease ' + (i * 0.06) + 's, transform 0.5s ease ' + (i * 0.06) + 's';
      obs.observe(c);
    });
  }
})();
