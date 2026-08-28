const NEWS_FILE = "data/news.json";
const LOCAL_EXTS = [".jpg", ".jpeg", ".png"];
const IMG_VER = Date.now();

const feed = document.getElementById("feed");
const list = document.querySelector(".news-list");
const today = document.getElementById("today");
const updated = document.getElementById("updated");
const buttons = document.querySelectorAll(".nav-btn");

today.textContent = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "full",
}).format(new Date());

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatUpdatedAt(iso) {
  if (!iso) return "尚未抓取";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "尚未抓取";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function localPath(gameId, index, ext) {
  const name = String(index + 1).padStart(2, "0");
  return `images/${gameId}/${name}${ext}?v=${IMG_VER}`;
}

async function fileExists(url) {
  try {
    const head = await fetch(url, { method: "HEAD", cache: "no-store" });
    if (head.ok) return true;
    if (head.status !== 404) {
      const get = await fetch(url, { method: "GET", cache: "no-store" });
      return get.ok;
    }
  } catch {
    /* fall through to image probe */
  }
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = url;
  });
}

async function findLocalImage(gameId, index) {
  for (const ext of LOCAL_EXTS) {
    const url = localPath(gameId, index, ext);
    if (await fileExists(url)) return url;
  }
  return "";
}

function handleImageError(img) {
  img.closest(".news-thumb")?.remove();
}

window.handleImageError = handleImageError;

function articleUrl(item) {
  return item.urlMobile || item.url || "#";
}

function render(gameId, items = [], localImages = []) {
  feed.dataset.game = gameId;

  if (!items.length) {
    list.innerHTML = `
      <li class="news-item">
        <article class="news-card">
          <h2>暂无资讯</h2>
          <p class="news-excerpt">请运行 scripts/fetch_news.py，或等待每日定时抓取。</p>
        </article>
      </li>
    `;
    return;
  }

  list.innerHTML = items
    .map((item, index) => {
      const href = articleUrl(item);
      const src = localImages[index] || "";
      const imageHtml = src
        ? `
          <a class="news-thumb" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" aria-label="查看资讯配图">
            <img
              class="news-image"
              src="${escapeHtml(src)}"
              alt=""
              onerror="handleImageError(this)"
            />
          </a>
        `
        : "";

      return `
      <li class="news-item">
        <article class="news-card">
          <p class="news-meta">
            <span class="news-tag">${escapeHtml(item.tag)}</span>
            <time>${escapeHtml(item.time)}</time>
          </p>
          <h2>
            <a class="news-title" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
          </h2>
          <p class="news-excerpt">${escapeHtml(item.excerpt)}</p>
          ${imageHtml}
        </article>
      </li>
    `;
    })
    .join("");
}

async function loadNews() {
  const res = await fetch(NEWS_FILE, { cache: "no-store" });
  if (!res.ok) throw new Error("无法读取资讯数据");
  return res.json();
}

let cache = { games: {}, updatedAt: "" };
let showToken = 0;

async function showGame(gameId) {
  const token = ++showToken;
  buttons.forEach((btn) => {
    const active = btn.dataset.game === gameId;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });

  const items = cache.games[gameId] || [];
  const localImages = await Promise.all(
    items.map((_, index) => findLocalImage(gameId, index)),
  );
  if (token !== showToken) return;
  render(gameId, items, localImages);
}

buttons.forEach((btn) => {
  btn.addEventListener("click", () => {
    showGame(btn.dataset.game);
  });
});

loadNews()
  .then((data) => {
    cache = data;
    if (updated) {
      updated.textContent = `数据更新于 ${formatUpdatedAt(data.updatedAt)}`;
    }
    showGame("yihuan");
  })
  .catch((err) => {
    console.error(err);
    if (updated) updated.textContent = "数据尚未生成";
    showGame("yihuan");
  });
