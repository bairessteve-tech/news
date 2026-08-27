"""Fetch official news lists once per day and write data/news.json."""

from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "data" / "news.json"
LOG_FILE = ROOT / "data" / "fetch.log"
LIMIT = 5
SLEEP_SECONDS = 0.5
TZ = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

SOURCES = {
    "yihuan": {
        "name": "异环",
        "list_urls": [
            "https://yh.wanmei.com/news/",
            "https://yh.wanmei.com/news/index1.html",
        ],
        "base": "https://yh.wanmei.com",
    },
    "yanyun": {
        "name": "燕云十六声",
        "list_urls": ["https://www.yysls.cn/news/"],
        "base": "https://www.yysls.cn",
    },
    "nishuihan": {
        "name": "逆水寒",
        "list_urls": ["https://n.163.com/news/"],
        "base": "https://n.163.com",
    },
}


def log(message: str) -> None:
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def fetch_html(url: str) -> str:
    time.sleep(SLEEP_SECONDS)
    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def collapse(text: str | None) -> str:
    if not text:
        return ""
    cleaned = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return cleaned


def clip(text: str, limit: int = 90) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_date(raw: str) -> str:
    text = collapse(raw)
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return f"{int(match.group(2)):02d}月{int(match.group(3)):02d}日"
    match = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):02d}月{int(match.group(2)):02d}日"
    match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if match:
        return f"{int(match.group(1)):02d}月{int(match.group(2)):02d}日"
    return text


def abs_url(href: str | None, base: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base, href)


def item(
    *,
    tag: str,
    time_text: str,
    title: str,
    excerpt: str,
    url: str,
    image: str = "",
) -> dict | None:
    title = collapse(title)
    if not title or not url:
        return None
    return {
        "tag": collapse(tag) or "资讯",
        "time": format_date(time_text) or time_text,
        "title": title,
        "excerpt": clip(collapse(excerpt)),
        "url": url,
        "image": image,
    }


def parse_yihuan(html_text: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    items: list[dict] = []
    for link in soup.select(".listNews > a"):
        parsed = item(
            tag=link.select_one(".type").get_text() if link.select_one(".type") else "资讯",
            time_text=link.select_one(".date").get_text() if link.select_one(".date") else "",
            title=link.select_one(".title").get_text() if link.select_one(".title") else "",
            excerpt=link.select_one(".des").get_text() if link.select_one(".des") else "",
            url=abs_url(link.get("href"), base),
        )
        if parsed:
            items.append(parsed)
    return items


def parse_yanyun(html_text: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    items: list[dict] = []
    for link in soup.select("ul.zh_news a.news"):
        img = link.select_one(".img img")
        parsed = item(
            tag=link.select_one(".news-label").get_text() if link.select_one(".news-label") else "资讯",
            time_text=link.select_one(".date-day").get_text() if link.select_one(".date-day") else "",
            title=link.get("title") or (link.select_one(".news-tit").get_text() if link.select_one(".news-tit") else ""),
            excerpt=link.select_one(".news-text").get_text() if link.select_one(".news-text") else "",
            url=abs_url(link.get("href"), base),
            image=abs_url(img.get("src") if img else "", base),
        )
        if parsed:
            items.append(parsed)
    return items


def parse_nishuihan(html_text: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    items: list[dict] = []
    for link in soup.select("ul.news-list > li > a"):
        day = collapse(link.select_one(".news-time strong").get_text() if link.select_one(".news-time strong") else "")
        month_year = collapse(link.select_one(".news-time span").get_text() if link.select_one(".news-time span") else "")
        month = ""
        month_match = re.search(r"\.(\d{1,2})$", month_year)
        if month_match and day.isdigit():
            month = f"{int(month_match.group(1)):02d}月{int(day):02d}日"
        parsed = item(
            tag=link.select_one(".type").get_text() if link.select_one(".type") else "资讯",
            time_text=month,
            title=link.select_one(".title").get_text() if link.select_one(".title") else link.get("title", ""),
            excerpt=link.select_one(".desc").get_text() if link.select_one(".desc") else "",
            url=abs_url(link.get("href"), base),
        )
        if parsed:
            items.append(parsed)
    return items


PARSERS = {
    "yihuan": parse_yihuan,
    "yanyun": parse_yanyun,
    "nishuihan": parse_nishuihan,
}


SKIP_IMAGE_HINTS = (
    "logo",
    "qrcode",
    "share_",
    "articleaside",
    "icon",
    "avatar",
    "thumbnail",
)


def is_usable_image(src: str) -> bool:
    lower = src.lower()
    if not src.startswith("http"):
        return False
    if lower.endswith(".svg"):
        return False
    if any(hint in lower for hint in SKIP_IMAGE_HINTS):
        return False
    return bool(
        re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", lower)
        or "/resources/" in lower
        or "/r/pic/" in lower
    )


def fetch_article_image(url: str) -> str:
    try:
        soup = BeautifulSoup(fetch_html(url), "html.parser")
        for selector, attr in (
            ('meta[property="og:image"]', "content"),
            ('meta[name="twitter:image"]', "content"),
        ):
            node = soup.select_one(selector)
            if node and node.get(attr):
                src = abs_url(node.get(attr), url)
                if is_usable_image(src):
                    return src
        for img in soup.find_all("img"):
            src = abs_url(img.get("src"), url)
            if is_usable_image(src):
                return src
    except Exception as exc:  # noqa: BLE001
        log(f"配图失败 {url}: {exc}")
    return ""


def unique(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for entry in items:
        key = entry["url"] or entry["title"]
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def collect_game(game_id: str) -> list[dict]:
    meta = SOURCES[game_id]
    parser = PARSERS[game_id]
    collected: list[dict] = []
    for list_url in meta["list_urls"]:
        log(f"读取 {meta['name']} 列表 {list_url}")
        collected.extend(parser(fetch_html(list_url), meta["base"]))
        collected = unique(collected)
        if len(collected) >= LIMIT:
            break
    collected = collected[:LIMIT]
    for entry in collected:
        if not entry.get("image"):
            entry["image"] = fetch_article_image(entry["url"])
    return collected


def load_existing() -> dict:
    if not OUT_FILE.exists():
        return {}
    try:
        return json.loads(OUT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    existing = load_existing()
    games = dict(existing.get("games") or {})
    errors: list[str] = []

    for game_id in SOURCES:
        try:
            games[game_id] = collect_game(game_id)
            log(f"{SOURCES[game_id]['name']} 抓取到 {len(games[game_id])} 条")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{game_id}: {exc}")
            log(f"{SOURCES[game_id]['name']} 失败: {exc}")
            games.setdefault(game_id, [])

    payload = {
        "updatedAt": datetime.now(TZ).isoformat(timespec="seconds"),
        "games": games,
        "errors": errors,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"已写入 {OUT_FILE}")
    return 1 if errors and not any(games.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
