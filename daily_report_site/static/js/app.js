(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem("theme");
  if (stored === "dark" || stored === "light") {
    root.setAttribute("data-theme", stored);
  }

  document.getElementById("theme-toggle")?.addEventListener("click", function () {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });

  document.querySelectorAll("[data-modal]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const id = btn.getAttribute("data-modal");
      const modal = id && document.getElementById(id);
      if (modal) modal.hidden = false;
    });
  });

  document.querySelectorAll("[data-close-modal]").forEach(function (el) {
    el.addEventListener("click", function () {
      const modal = el.closest(".modal");
      if (modal) modal.hidden = true;
    });
  });

  const form = document.getElementById("search-form");
  const box = document.getElementById("search-result");
  if (form && box) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      const fd = new FormData(form);
      const q = (fd.get("q") || "").toString().trim();
      if (q.length < 2) {
        box.hidden = false;
        box.textContent = "请输入至少 2 个字符。";
        return;
      }
      box.hidden = false;
      box.textContent = "搜索中…";
      try {
        const res = await fetch(form.action, {
          method: "POST",
          body: fd,
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        const data = await res.json();
        if (!data.ok) {
          box.textContent = data.error || "搜索失败";
          return;
        }
        let html = "";
        if (data.answer) {
          html += "<p><strong>回答：</strong>" + escapeHtml(data.answer) + "</p>";
        }
        if (data.report_date) {
          const u = "/report/" + encodeURIComponent(data.report_date) + "/";
          let hash = "";
          if (data.anchor_slug) hash = "#" + encodeURIComponent(data.anchor_slug);
          html +=
            '<p><a href="' +
            u +
            hash +
            '">跳转到 ' +
            escapeHtml(data.report_date) +
            "</a></p>";
        }
        box.innerHTML = html || "<p>（无结构化定位）请查看历史列表。</p>";
      } catch (err) {
        box.textContent = "网络错误：" + err;
      }
    });
  }

  function escapeHtml(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
