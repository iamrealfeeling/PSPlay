#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PSP Downloader — ОДИН ФАЙЛ для сборки в .exe (PyInstaller).

Универсальная качалка фильмов, мультфильмов, сериалов и аниме в формат PSP.
Источники: AniLibria (API) • HDRezka (парсинг+Anubis) • KinoVibe (парсинг) • YouTube (yt-dlp).
Выход: MP4 480x272, H.264 Baseline L3.0, AAC — папка VIDEO/ на PSP.

Сборка:
    pip install -r requirements.txt
    build_exe.bat
"""
import gzip
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import urllib.parse
import urllib.request

# ============================================================
# 0. ОБЩЕЕ
# ============================================================
APP_TITLE = "PSPlay"
APP_TAGLINE = "Pocket cinema for PSP"
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if getattr(sys, "frozen", False) is False \
    else os.path.dirname(sys.executable)
DEFAULT_OUT = os.path.join(BASE_DIR, "PSP_VIDEO")
POSTER_CACHE = os.path.join(BASE_DIR, "cache_posters")
TMP_DIR = os.path.join(BASE_DIR, "tmp_dl")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return (name[:80] if len(name) > 80 else name) or "video"


def fmt_eta(sec: float) -> str:
    s = max(int(sec or 0), 0)
    return f"{s // 60}:{s % 60:02d}" if s >= 60 else f"0:{s:02d}"


def fmt_dur(sec) -> str:
    try:
        s = int(sec or 0)
    except Exception:
        return "??:??"
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_speed(bps: float) -> str:
    if bps >= 1024 * 1024:
        return f"{bps / 1024 / 1024:.1f} МБ/с"
    return f"{max(bps / 1024, 0):.0f} КБ/с"


def fmt_size(n) -> str:
    n = n or 0
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} ГБ"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} МБ"
    return f"{n // 1024} КБ"


# ============================================================
# 0b. МУЛЬТИЯЗЫК (Українська / Русский / English) + конфиг
# ============================================================
STR = {
    "Українська": {
        "tagline": "Кишенькове кіно для PSP",
        "nav_search": "🔍  Пошук", "nav_downloads": "⬇  Завантаження", "nav_settings": "⚙  Налаштування",
        "ready": "Готово", "in_queue": "У черзі",
        "src_anilibria": "Аніме • API", "src_rezka": "Усе • озвучки",
        "src_kinovibe": "Фільми • серіали", "src_anwap": "Фільми", "src_youtube": "Відео • трейлери",
        "search_ph": "Фільм, серіал, аніме — наприклад: інтерстеллар, фрірен…",
        "search_btn": "🔍 Знайти",
        "h_results": "РЕЗУЛЬТАТИ", "h_desc": "ОПИС", "h_eps": "СЕРІЇ",
        "poster_ph": "постер\nз'явиться тут", "choose_hint": "Обери результат ліворуч",
        "meta_ph": "пошук вище → клік по картці", "desc_ph": "Тут буде опис, жанри, рік, озвучки та сезони.",
        "voice": "Озвучка", "season": "Сезон",
        "sel_all": "Всі", "sel_none": "Немає",
        "queue_add": "➕ До черги завантажень", "need_sel": "Спочатку знайди і обери результат.",
        "need_eps": "Познач хоча б одну позицію.",
        "size_per": "МБ/сер.", "size_pos": "поз.",
        "dl_title": "Черга завантажень", "cancel_all": "✖ Скасувати все", "clear_done": "🗑 Прибрати готові",
        "job_cancel": "✖ Скасувати", "job_remove": "🗑 Прибрати", "job_folder": "📂 Папка",
        "st_queued": "у черзі", "st_active": "качаю", "st_converting": "конвертую",
        "st_done": "готово", "st_error": "помилка", "st_canceled": "скасовано",
        "ph_queued": "у черзі", "ph_links": "посилання", "ph_download": "завантаження",
        "ph_convert": "конвертація", "ph_done": "готово",
        "set_title": "Налаштування", "set_out": "Папка виводу", "set_preset": "Пресет PSP",
        "set_aspect": "Кадр (4:3 → 16:9)", "set_quality": "Якість джерела",
        "set_quality_hint": "480 — найшвидше, на 480x272 різниці нема",
        "set_threads": "Потоки завантаження", "set_threads_hint": "16 — оптимум (замір)",
        "set_files": "Файли", "set_thm": ".THM превʼю 160×120",
        "set_m4v": "Імена M4Vxxxxx (для старих OFW)",
        "set_lang": "Мова / Language", "set_ffmpeg": "ffmpeg",
        "set_check": "Перевірити", "set_misc": "Інше",
        "set_open_out": "📂 Відкрити папку завантажень", "set_clear_cache": "🧹 Кеш постерів",
        "ff_found": "знайдено", "ff_missing": "НЕ ЗНАЙДЕНО в PATH",
        "msg_no_ffmpeg": "ffmpeg не знайдено в PATH.\nПостав Momchil full build з gyan.dev.",
        "q_active": "активно", "q_done": "готово", "q_total": "всього",
        "cache_cleared": "Кеш постерів очищено", "cancel_queue": "Скасування всієї черги…",
        "files_word": "файлів", "added_queue": "До черги", "total_word": "всього",
        "nothing_found": "Нічого не знайдено.", "search_err": "Помилка пошуку",
        "found": "Знайдено", "dl_of": "із", "eta_word": "ETA", "ep_word": "Серія", "season_word": "Сезон", "cancel_by_user": "Скасовано користувачем", "no_link": "Немає посилання",
    },
    "Русский": {
        "tagline": "Карманное кино для PSP",
        "nav_search": "🔍  Поиск", "nav_downloads": "⬇  Загрузки", "nav_settings": "⚙  Настройки",
        "ready": "Готов", "in_queue": "В очереди",
        "src_anilibria": "Аниме • API", "src_rezka": "Всё • озвучки",
        "src_kinovibe": "Фильмы • сериалы", "src_anwap": "Фильмы", "src_youtube": "Видео • трейлеры",
        "search_ph": "Фильм, сериал, аниме — например: интерстеллар, фрирен…",
        "search_btn": "🔍 Найти",
        "h_results": "РЕЗУЛЬТАТЫ", "h_desc": "ОПИСАНИЕ", "h_eps": "СЕРИИ",
        "poster_ph": "постер\nпоявится здесь", "choose_hint": "Выбери результат слева",
        "meta_ph": "поиск выше → клик по карточке", "desc_ph": "Здесь будет описание, жанры, год, озвучки и сезоны.",
        "voice": "Озвучка", "season": "Сезон",
        "sel_all": "Все", "sel_none": "Сброс",
        "queue_add": "➕ В очередь загрузок", "need_sel": "Сначала найди и выбери результат.",
        "need_eps": "Отметь хотя бы одну позицию.",
        "size_per": "МБ/сер.", "size_pos": "поз.",
        "dl_title": "Очередь загрузок", "cancel_all": "✖ Отмена всего", "clear_done": "🗑 Очистить готовые",
        "job_cancel": "✖ Отмена", "job_remove": "🗑 Убрать", "job_folder": "📂 Папка",
        "st_queued": "в очереди", "st_active": "качаю", "st_converting": "конвертирую",
        "st_done": "готово", "st_error": "ошибка", "st_canceled": "отменено",
        "ph_queued": "в очереди", "ph_links": "ссылки", "ph_download": "скачивание",
        "ph_convert": "конвертация", "ph_done": "готово",
        "set_title": "Настройки", "set_out": "Папка вывода", "set_preset": "Пресет PSP",
        "set_aspect": "Кадр (4:3 → 16:9)", "set_quality": "Качество источника",
        "set_quality_hint": "480 — быстрее всего, на 480x272 разницы нет",
        "set_threads": "Потоки скачивания", "set_threads_hint": "16 — оптимум (замер)",
        "set_files": "Файлы", "set_thm": ".THM превью 160×120",
        "set_m4v": "Имена M4Vxxxxx (для старых OFW)",
        "set_lang": "Мова / Язык / Language", "set_ffmpeg": "ffmpeg",
        "set_check": "Проверить", "set_misc": "Прочее",
        "set_open_out": "📂 Открыть папку загрузок", "set_clear_cache": "🧹 Кэш постеров",
        "ff_found": "найден", "ff_missing": "НЕ НАЙДЕН в PATH",
        "msg_no_ffmpeg": "ffmpeg не найден в PATH.\nПоставь full build с gyan.dev.",
        "q_active": "активно", "q_done": "готово", "q_total": "всего",
        "cache_cleared": "Кэш постеров очищен", "cancel_queue": "Отмена всей очереди…",
        "files_word": "файлов", "added_queue": "В очередь", "total_word": "всего",
        "nothing_found": "Ничего не найдено.", "search_err": "Ошибка поиска",
        "found": "Найдено", "dl_of": "из", "eta_word": "ETA", "ep_word": "Серия", "season_word": "Сезон", "cancel_by_user": "Отменено пользователем", "no_link": "Нет ссылки",
    },
    "English": {
        "tagline": "Pocket cinema for PSP",
        "nav_search": "🔍  Search", "nav_downloads": "⬇  Downloads", "nav_settings": "⚙  Settings",
        "ready": "Ready", "in_queue": "Queued",
        "src_anilibria": "Anime • API", "src_rezka": "All • dubs",
        "src_kinovibe": "Movies • series", "src_anwap": "Movies", "src_youtube": "Videos • trailers",
        "search_ph": "Movie, series, anime — e.g.: interstellar, frieren…",
        "search_btn": "🔍 Search",
        "h_results": "RESULTS", "h_desc": "ABOUT", "h_eps": "EPISODES",
        "poster_ph": "poster\nshows here", "choose_hint": "Pick a result on the left",
        "meta_ph": "search above → click a card", "desc_ph": "Description, genres, year, dubs and seasons appear here.",
        "voice": "Dub", "season": "Season",
        "sel_all": "All", "sel_none": "None",
        "queue_add": "➕ Add to queue", "need_sel": "Find and pick a result first.",
        "need_eps": "Select at least one item.",
        "size_per": "MB/ep.", "size_pos": "items",
        "dl_title": "Download queue", "cancel_all": "✖ Cancel all", "clear_done": "🗑 Clear finished",
        "job_cancel": "✖ Cancel", "job_remove": "🗑 Remove", "job_folder": "📂 Folder",
        "st_queued": "queued", "st_active": "downloading", "st_converting": "converting",
        "st_done": "done", "st_error": "error", "st_canceled": "canceled",
        "ph_queued": "queued", "ph_links": "links", "ph_download": "download",
        "ph_convert": "convert", "ph_done": "done",
        "set_title": "Settings", "set_out": "Output folder", "set_preset": "PSP preset",
        "set_aspect": "Frame (4:3 → 16:9)", "set_quality": "Source quality",
        "set_quality_hint": "480 is fastest, no difference on 480x272",
        "set_threads": "Download threads", "set_threads_hint": "16 is optimal (measured)",
        "set_files": "Files", "set_thm": ".THM preview 160×120",
        "set_m4v": "M4Vxxxxx names (for old OFW)",
        "set_lang": "Language", "set_ffmpeg": "ffmpeg",
        "set_check": "Check", "set_misc": "Misc",
        "set_open_out": "📂 Open downloads folder", "set_clear_cache": "🧹 Poster cache",
        "ff_found": "found", "ff_missing": "NOT FOUND in PATH",
        "msg_no_ffmpeg": "ffmpeg not found in PATH.\nGet a full build from gyan.dev.",
        "q_active": "active", "q_done": "done", "q_total": "total",
        "cache_cleared": "Poster cache cleared", "cancel_queue": "Cancelling queue…",
        "files_word": "files", "added_queue": "Queued", "total_word": "total",
        "nothing_found": "Nothing found.", "search_err": "Search error",
        "found": "Found", "dl_of": "of", "eta_word": "ETA", "ep_word": "Episode", "season_word": "Season", "cancel_by_user": "Cancelled by user", "no_link": "No link",
    },
}
LANGS = list(STR.keys())


def detect_lang():
    import locale
    try:
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    if loc.startswith("uk"):
        return "Українська"
    if loc.startswith("en"):
        return "English"
    return "Русский"


CONFIG_PATH = os.path.join(BASE_DIR, "psplay_config.json")


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_config(d):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ============================================================
# 1. ANILIBRIA (официальный API anilibria.top v1)
# ============================================================
ANI_BASE = "https://anilibria.top"
ANI_SEARCH_URL = ANI_BASE + "/api/v1/app/search/releases"
ANI_RELEASE_URL = ANI_BASE + "/api/v1/anime/releases/{}"
ANI_HEADERS = {"User-Agent": "PSP-Downloader/2.0 (Windows)", "Accept": "application/json"}


def ani_get_json(url: str):
    last = "?"
    for a in range(3):
        try:
            req = urllib.request.Request(url, headers=ANI_HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read().decode("utf-8").strip()
            if not raw:
                last = "пустой ответ API"
                time.sleep(1 + a)
                continue
            return json.loads(raw)
        except json.JSONDecodeError as e:
            last = f"битый JSON: {e}"
            time.sleep(1 + a)
        except Exception as e:
            last = str(e)[:100]
            time.sleep(1 + a)
    raise RuntimeError(f"AniLibria API не отвечает ({last})")


def ani_search(query: str, limit: int = 20):
    q = urllib.parse.urlencode({"query": query})
    data = ani_get_json(f"{ANI_SEARCH_URL}?{q}")
    out = []
    for item in (data or [])[:limit]:
        name = item.get("name") or {}
        poster = item.get("poster") or {}
        out.append({
            "src": "anilibria",
            "id": item.get("id"),
            "alias": item.get("alias") or "",
            "title": name.get("main") or "?",
            "sub": name.get("english") or "",
            "year": item.get("year"),
            "info": (item.get("description") or "")[:120],
            "poster": poster.get("src"),
            "poster_thumb": poster.get("thumbnail") or poster.get("preview"),
            "is_ongoing": bool(item.get("is_ongoing")),
        })
    return out


def ani_poster_full(src):
    if not src:
        return None
    return src if src.startswith("http") else ANI_BASE + src


def ani_release(release_id: int):
    inc = urllib.parse.urlencode({
        "include": "id,alias,name,poster,description,year,type,season,genres,age_rating,publish_day,is_ongoing,episodes"})
    data = ani_get_json(f"{ANI_RELEASE_URL.format(release_id)}?{inc}")
    name = data.get("name") or {}
    poster = data.get("poster") or {}
    episodes = []
    for ep in data.get("episodes") or []:
        episodes.append({
            "ordinal": ep.get("ordinal"), "name": ep.get("name"),
            "duration": ep.get("duration") or 1440,
            "hls_480": ep.get("hls_480"), "hls_720": ep.get("hls_720"),
            "hls_1080": ep.get("hls_1080")})
    episodes.sort(key=lambda e: e["ordinal"] or 0)
    genres = data.get("genres") or []
    if genres and isinstance(genres[0], dict):
        genres = [g.get("name") or g.get("value") or str(g) for g in genres]
    age = data.get("age_rating") or {}
    season = data.get("season") or {}
    pub = data.get("publish_day") or {}
    typ = data.get("type") or {}
    return {
        "src": "anilibria", "id": data.get("id"), "alias": data.get("alias") or "",
        "title": name.get("main") or "?", "sub": name.get("english") or "",
        "alt": name.get("alternative") or "",
        "description": data.get("description") or "Описание отсутствует.",
        "year": data.get("year"), "season": (season.get("description") or ""),
        "kind": typ.get("description") or typ.get("value") or "",
        "genres": genres, "age": age.get("label") or "",
        "day": (pub.get("description") or ""),
        "is_ongoing": bool(data.get("is_ongoing")),
        "poster": (poster.get("src")), "poster_thumb": poster.get("thumbnail") or poster.get("preview"),
        "episodes": episodes, "is_series": True, "runtime": 0,
    }


def ani_pick_hls(episode: dict, quality: str = "480"):
    order = {"1080": ("hls_1080", "hls_720", "hls_480"),
             "720": ("hls_720", "hls_480", "hls_1080"),
             "480": ("hls_480", "hls_720", "hls_1080"),
             }.get(quality, ("hls_480", "hls_720", "hls_1080"))
    for k in order:
        if episode.get(k):
            return episode[k], k
    return None, None


def ani_refresh_hls(release_id: int):
    inc = urllib.parse.urlencode({"include": "episodes"})
    data = ani_get_json(f"{ANI_RELEASE_URL.format(release_id)}?{inc}")
    out = {}
    for ep in data.get("episodes") or []:
        out[ep.get("ordinal")] = {
            "ordinal": ep.get("ordinal"), "duration": ep.get("duration") or 1440,
            "hls_480": ep.get("hls_480"), "hls_720": ep.get("hls_720"),
            "hls_1080": ep.get("hls_1080")}
    return out

# ============================================================
# 2. HDREZKA
# ============================================================
"""HDRezka.tv — поиск, разбор страницы, CDN-потоки. Только stdlib.

Сеть: прямые IP через DoH (DNS у ряда провайдеров подменяют на заглушку),
SNI/Host под реальный домен, свой куки-джар.
Антибот Anubis (PoW sha256, difficulty считается в毫秒) решается локально:
протокол разобран из main.mjs 1.25.0 воркера sha256-purejs.mjs.
"""
import gzip
import hashlib
import http.client
import json
import re
import socket
import ssl
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

MIRRORS = ["rezka.ag", "hdrezka.ag", "hdrezka.me", "hdrezka.sh"]

_doh_cache: dict = {}


def doh_resolve(host: str) -> str:
    """Реальный IP через DNS-over-HTTPS (обход подмены DNS).

    Несколько провайдеров по очереди: если один забит/заблокирован — следующий.
    """
    if host in _doh_cache:
        return _doh_cache[host]
    providers = [
        ("https://dns.google/resolve?name=" + host + "&type=A", {}),
        ("https://cloudflare-dns.com/dns-query?name=" + host + "&type=A",
         {"Accept": "application/dns-json"}),
    ]
    last = None
    for url, extra in providers:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, **extra})
            ans = json.loads(urllib.request.urlopen(req, timeout=12).read())
            for a in ans.get("Answer", []):
                if a.get("type") == 1 and a.get("data"):
                    _doh_cache[host] = a["data"]
                    return a["data"]
            last = "empty answer"
        except Exception as e:
            last = str(e)[:80]
    # последний шанс — системный DNS
    try:
        ip = socket.gethostbyname(host)
        _doh_cache[host] = ip
        return ip
    except Exception:
        pass
    raise RuntimeError(f"DoH не резолвит {host}: {last}")


def _dechunk(body: bytes) -> bytes:
    out, rest = b"", body
    while rest:
        ln, _, rest2 = rest.partition(b"\r\n")
        try:
            n = int(ln.strip().split(b";")[0], 16)
        except Exception:
            return body
        if n == 0:
            break
        out += rest2[:n]
        rest = rest2[n + 2:]
    return out


class Session:
    """HTTPS-сессия на реальный IP с SNI=host, куками и обходом Anubis."""

    def __init__(self, host: str = None):
        self.host = host or MIRRORS[0]
        self.ip = None
        self.cookies: dict = {}
        self._ctx = ssl.create_default_context()
        self.anubis_passes = 0
        self.dead_hosts: set = set()  # CDN-ноды без маршрута — не трогаем

    def _connect(self):
        if not self.ip:
            try:
                self.ip = doh_resolve(self.host)
            except Exception:
                self.ip = socket.gethostbyname(self.host)
        s = socket.create_connection((self.ip, 443), timeout=25)
        return self._ctx.wrap_socket(s, server_hostname=self.host)

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _store_cookies(self, conn: http.client.HTTPConnection):
        for k, v in conn.getheaders():
            if k.lower() == "set-cookie":
                part = v.split(";", 1)[0]
                if "=" in part:
                    name, val = part.split("=", 1)
                    self.cookies[name.strip()] = val.strip()

    def request(self, method: str, url: str, body: bytes = None,
                extra_headers: dict = None, _anubis_retry: bool = True,
                retries: int = 3):
        """С ретраями: сервер резки периодически виснет — ждём и повторяем."""
        last = None
        for attempt in range(max(1, retries)):
            try:
                return self._request_once(method, url, body, extra_headers,
                                          _anubis_retry)
            except (TimeoutError, socket.timeout, ConnectionError,
                    ssl.SSLError, http.client.HTTPException) as e:
                last = e
                time.sleep(1 + attempt)
        raise RuntimeError(f"{method} {url}: {type(last).__name__}: {last}")

    def _request_once(self, method: str, url: str, body: bytes = None,
                      extra_headers: dict = None, _anubis_retry: bool = True):
        """url — путь (/search/...) или абсолютный URL (CDN-хосты тоже)."""
        if url.startswith("http"):
            parts = urllib.parse.urlsplit(url)
            host, path = parts.hostname, parts.path + (
                ("?" + parts.query) if parts.query else "")
            use_ssl = parts.scheme == "https"
        else:
            host, path, use_ssl = self.host, url, True
        headers = {
            "Host": host,
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip",
            "Connection": "close",
        }
        if self.cookies:
            headers["Cookie"] = self._cookie_header()
        if extra_headers:
            headers.update(extra_headers)
        # реальное соединение — на IP (обход подмены DNS), SNI/Host — на домен
        ip = doh_resolve(host) if host != self.host or not self.ip else self.ip
        if host == self.host:
            self.ip = ip
        raw = socket.create_connection((ip, 443 if use_ssl else 80), timeout=25)
        sock = self._ctx.wrap_socket(raw, server_hostname=host) if use_ssl else raw
        conn = http.client.HTTPConnection(host)
        conn.sock = sock
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        status = resp.status
        rheaders = resp.getheaders()
        data = resp.read()
        for k, v in rheaders:
            if k.lower() == "set-cookie":
                part = v.split(";", 1)[0]
                if "=" in part:
                    name, val = part.split("=", 1)
                    self.cookies[name.strip()] = val.strip()
        conn.close()
        hd = {k.lower(): v for k, v in rheaders}
        if hd.get("transfer-encoding", "").lower().startswith("chunked"):
            data = _dechunk(data)
        if hd.get("content-encoding", "").lower() == "gzip":
            try:
                data = gzip.decompress(data)
            except Exception:
                pass
        loc = hd.get("location")
        if status in (301, 302, 303, 307, 308) and loc:
            if loc.startswith("/"):
                return self.request("GET", loc, _anubis_retry=_anubis_retry)
            return status, rheaders, data  # внешний редирект — отдать как есть
        if _anubis_retry and self._is_anubis(data):
            # кука могла не взяться с первого раза — цикл с проверкой,
            # иначе страница проверки молча отдавалась как контент
            for _ in range(3):
                self._pass_anubis(data)
                status, rheaders, data = self.request(
                    method, path, body, extra_headers, _anubis_retry=False)
                if not self._is_anubis(data):
                    break
            if self._is_anubis(data):
                raise RuntimeError(
                    "Anubis не пропускает: проверка на бота осталась после 3 попыток")
        return status, rheaders, data

    def _ensure_ip(self):
        if not self.ip:
            try:
                self.ip = doh_resolve(self.host)
            except Exception:
                self.ip = socket.gethostbyname(self.host)
        return self.ip

    def get(self, path: str, extra_headers: dict = None) -> str:
        status, _, data = self.request("GET", path, extra_headers=extra_headers)
        if status != 200:
            raise RuntimeError(f"HTTP {status} на {path}")
        return data.decode("utf-8", "ignore")

    def post_ajax(self, path: str, params: dict, referer: str) -> dict:
        body = urllib.parse.urlencode(params).encode()
        status, _, data = self.request(
            "POST", path, body,
            {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
             "X-Requested-With": "XMLHttpRequest",
             "Referer": referer,
             "Accept": "application/json, text/javascript, */*; q=0.01"})
        if status != 200:
            raise RuntimeError(f"AJAX HTTP {status} на {path}")
        txt = data.decode("utf-8", "ignore").strip()
        if not txt:
            raise RuntimeError(f"AJAX пустой ответ на {path} (повторите чуть позже)")
        try:
            return json.loads(txt)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"AJAX битый JSON на {path}: {e}")

    # ---------- Anubis ----------
    @staticmethod
    def _is_anubis(data: bytes) -> bool:
        return b"anubis_challenge" in data and b"within.website" in data

    def _pass_anubis(self, challenge_page: bytes):
        html = challenge_page.decode("utf-8", "ignore")
        m = re.search(r'<script id="anubis_challenge"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            raise RuntimeError("Anubis: нет JSON челленджа")
        chal = json.loads(m.group(1))
        ch = chal["challenge"]
        difficulty = int(chal["rules"]["difficulty"])
        rnd = ch["randomData"]
        cid = ch["id"]
        t0 = time.time()
        nonce, digest = solve_pow(rnd, difficulty)
        elapsed = int((time.time() - t0) * 1000) + 50
        redir = "/"  # pass-challenge редиректит сам; дальше повторим исходный запрос
        q = urllib.parse.urlencode({
            "id": cid, "response": digest, "nonce": nonce,
            "redir": redir, "elapsedTime": elapsed})
        status, headers, _ = self.request(
            "GET", "/.within.website/x/cmd/anubis/api/pass-challenge?" + q,
            _anubis_retry=False)
        if status not in (200, 302, 303):
            raise RuntimeError(f"Anubis pass-challenge: HTTP {status}")
        self.anubis_passes += 1


def solve_pow(random_data: str, difficulty: int) -> tuple:
    """Тот же PoW, что в sha256-purejs.mjs: sha256(randomData+nonce),
    первые floor(d/2) байт нулевые, при нечётном d — старший ниббл следующего тоже 0."""
    full = difficulty // 2
    half = difficulty % 2 == 1
    nonce = 0
    while True:
        h = hashlib.sha256(f"{random_data}{nonce}".encode()).digest()
        if all(b == 0 for b in h[:full]) and (not half or (h[full] >> 4) == 0):
            return nonce, h.hex()
        nonce += 1


# ---------- разбор HTML (regex, без bs4) ----------

def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = s.replace("&quot;", '"').replace("&#039;", "'").replace("&amp;", "&")
    s = s.replace("&laquo;", "«").replace("&raquo;", "»")
    return re.sub(r"\s+", " ", s).strip()


def parse_streams(url_field: str) -> dict:
    """'[480p]https://...mp4,[720p]https://...' -> {'480p': url, ...}.

    Премиум-варианты (1080p Ultra с HTML в метке) пропускаем — они не откроются.
    """
    out = {}
    if not url_field:
        return out
    for m in re.finditer(r"\[([^\]]+)\](https?://[^,\s\"']+)", url_field):
        label = _clean(m.group(1))
        if "<" in m.group(1) or "Ultra" in label or "Premium" in label:
            continue
        q = re.search(r"(\d{3,4})p", label)
        if q:
            out[q.group(0)] = m.group(2)
    return out


def pick_mp4(streams: dict, quality: str = "480") -> tuple:
    """Ближайшее качество ≤ запрошенного, иначе минимальное доступное."""
    want = int(re.search(r"\d+", quality or "480").group(0))
    avail = sorted((int(re.search(r"\d+", k).group(0)), k) for k in streams)
    best = None
    for num, k in avail:
        if num <= want:
            best = k
    if best is None and avail:
        best = avail[0][1]
    return (streams[best], best) if best else (None, None)


def search(sess: Session, query: str, limit: int = 20):
    """Поиск через /search/. Возвращает [{page_url, post_id, title, year, poster, info}]."""
    q = urllib.parse.urlencode({"do": "search", "subaction": "search", "q": query})
    html = sess.get("/search/?" + q)
    starts = [m.start() for m in re.finditer(r'<div class="b-content__inline_item"', html)]
    out = []
    for idx, st in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else st + 3000
        chunk = html[st:end]
        pid = re.search(r'data-id="(\d+)"', chunk)
        url = re.search(r'data-url="([^"]+)"', chunk)
        img = re.search(r'<img[^>]+src="([^"]+)"', chunk)
        link = re.search(
            r'b-content__inline_item-link"[^>]*>\s*<a[^>]*>(.*?)</a>\s*<div>(.*?)</div>',
            chunk, re.S)
        if not pid or not url:
            continue
        title = _clean(link.group(1)) if link else ""
        sub = _clean(link.group(2)) if link else ""
        mm = re.search(r"(19|20)\d{2}", sub)
        poster = img.group(1) if img else ""
        if poster.startswith("//"):
            poster = "https:" + poster
        out.append({"src": "rezka", "page_url": url.group(1),
                    "post_id": pid.group(1),
                    "title": title or url.group(1).rstrip("/").split("/")[-1],
                    "year": mm.group(0) if mm else "",
                    "info": sub, "poster": poster})
        if len(out) >= limit:
            break
    return out


def page_info(sess: Session, page_url: str) -> dict:
    """Страница фильма/сериала: мета + переводы + сезоны/серии + streams по умолчанию."""
    html = sess.get("/" + page_url.split(sess.host, 1)[-1].lstrip("/")
                    if sess.host in page_url else page_url)
    if ("anubis_challenge" in html or "не бот" in html.lower()) and \
            "data-post_id" not in html:
        raise RuntimeError("HDRezka: проверка на бота не пройдена — подождите минуту и повторите")
    if "data-post_id" not in html and "translators-list" not in html \
            and "initCDN" not in html:
        raise RuntimeError("HDRezka: страница без данных релиза — повторите через минуту")
    post = re.search(r'data-post_id="(\d+)"', html)
    post_id = post.group(1) if post else ""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    orig = re.search(r'b-post__origtitle[^>]*>(.*?)</', html, re.S)
    poster = re.search(r'b-sidecover.*?<img[^>]+src="([^"]+)"', html, re.S)
    desc = re.search(r'b-post__description_text"[^>]*>(.*?)</div>', html, re.S)
    year = re.search(r"/year/(\d{4})", html)
    translators = []
    ul = re.search(r'<ul id="translators-list"(.*?)</ul>', html, re.S)
    if ul:
        seen = set()
        # два формата: <li data-translator_id="N">Имя</li> (аниме)
        # и <li><a data-translator_id="N" href="...">Имя</a></li> (сериалы)
        for m in re.finditer(
                r'data-translator_id="(\d+)"[^>]*>(.*?)</(?:a|li)>', ul.group(1), re.S):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                translators.append({"id": m.group(1), "name": _clean(m.group(2))})
    seasons = sorted({m.group(1) for m in re.finditer(r'data-season_id="(\d+)"', html)},
                     key=int) if "season_id" in html else []
    if not seasons:
        tabs = re.search(r'id="simple-seasons-tabs"(.*?)</ul>', html, re.S)
        if tabs:
            seasons = sorted({m.group(1) for m in re.finditer(r'data-tab_id="(\d+)"', tabs.group(1))},
                             key=int)
    episodes = []
    for m in re.finditer(
            r'<li[^>]*data-season_id="(\d+)"[^>]*data-episode_id="(\d+)"[^>]*>(.*?)</li>',
            html, re.S):
        episodes.append({"season": int(m.group(1)), "episode": int(m.group(2)),
                         "name": _clean(m.group(3))})
    if not episodes:  # старый формат без season_id
        for m in re.finditer(
                r'<li[^>]*data-episode_id="(\d+)"[^>]*>(.*?)</li>', html, re.S):
            episodes.append({"season": 1, "episode": int(m.group(1)),
                             "name": _clean(m.group(2))})
    is_series = bool(seasons or episodes)
    streams = {}
    dflt = {"translator_id": "", "season": 1, "episode": 1}
    m = re.search(r"initCDN\w*Events\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),.*?\"streams\":\"((?:[^\"\\]|\\.)*)\"",
                  html, re.S)
    if m:
        dflt = {"translator_id": m.group(2), "season": int(m.group(3)), "episode": int(m.group(4))}
        streams = parse_streams(m.group(5).replace("\\/", "/"))
    p = poster.group(1) if poster else ""
    if p.startswith("//"):
        p = "https:" + p
    rt = re.search(r'itemprop="duration">(\d+)', html)
    if not rt:
        rt = re.search(r"Время.*?</td>\s*<td[^>]*>(\d+)\s*мин", html, re.S)
    title_raw = _clean(h1.group(1)) if h1 else page_url
    title_raw = re.sub(r"\s*смотреть онлайн\s*$", "", title_raw, flags=re.I)
    return {"post_id": post_id or re.search(r"/(\d+)-[^/]*\.html", page_url).group(1),
            "title": title_raw,
            "orig": _clean(orig.group(1)) if orig else "",
            "poster": p,
            "description": _clean(desc.group(1)) if desc else "Описание отсутствует.",
            "year": year.group(1) if year else "",
            "runtime_min": int(rt.group(1)) if rt else 0,
            "translators": translators,
            "seasons": [int(s) for s in seasons],
            "episodes": episodes,
            "is_series": is_series,
            "default": dflt,
            "default_streams": streams}


def get_stream(sess: Session, page_url: str, post_id: str, translator_id: str,
               season: int = 1, episode: int = 1, is_series: bool = True) -> dict:
    """Прямые mp4 по качествам. Ссылки с токеном — обновлять перед скачиванием!"""
    action = "get_stream" if is_series else "get_movie"
    params = {"id": post_id, "translator_id": str(translator_id), "action": action}
    if is_series:
        params.update({"season": season, "episode": episode})
    r = sess.post_ajax("/ajax/get_cdn_series/", params, referer=page_url)
    if not r.get("success"):
        raise RuntimeError("get_stream: " + str(r.get("message") or r)[:150])
    return parse_streams(r.get("url") or "")


def fresh_session(page_url: str):
    """Новая сессия + свежий просмотр страницы (резка требует это перед
    get_stream, иначе 'Время сессии истекло'). Перебирает зеркала."""
    host = urllib.parse.urlsplit(page_url).hostname or MIRRORS[0]
    last = None
    for mirror in [host] + [m for m in MIRRORS if m != host]:
        try:
            s = Session(mirror)
            path = "/" + page_url.split(mirror, 1)[-1].lstrip("/") \
                if mirror in page_url else page_url
            s.get(path)
            s.host = host if mirror == host else mirror
            return s
        except Exception as e:
            last = e
    raise RuntimeError(f"HDRezka недоступна: {last}")


def get_episodes(sess: Session, page_url: str, post_id: str, translator_id: str,
                 season: int) -> list:
    """Серии сезона через AJAX (когда на странице их нет)."""
    r = sess.post_ajax("/ajax/get_cdn_series/",
                       {"id": post_id, "translator_id": str(translator_id),
                        "season": season, "action": "get_episodes"},
                       referer=page_url)
    eps = r.get("episodes") or ""
    # ответ содержит <ul id="simple-episodes-list-N"> на каждый сезон —
    # режем по нужному, иначе серии всех сезонов смешаются
    m = re.search(r'<ul id="simple-episodes-list-%d"(.*?)</ul>' % season, eps, re.S)
    block = m.group(1) if m else eps
    out = []
    for m in re.finditer(
            r'<li[^>]*data-season_id="(\d+)"[^>]*data-episode_id="(\d+)"[^>]*>(.*?)</li>',
            block, re.S):
        out.append({"season": int(m.group(1)), "episode": int(m.group(2)),
                    "name": _clean(m.group(3))})
    if not out:
        for m in re.finditer(r'data-episode_id="(\d+)"[^>]*>(.*?)</', block):
            out.append({"season": season, "episode": int(m.group(1)),
                        "name": _clean(m.group(2))})
    if not out:
        for m in re.finditer(r"<option[^>]*value=\"(\d+)\"", block):
            out.append({"season": season, "episode": int(m.group(1)), "name": ""})
    return out


# ---------- скачивание mp4 с CDN (обход мёртвых нод + параллельные Range) ----------

def _tcp_ok(host: str, port: int = 443, timeout: int = 6) -> bool:
    try:
        ip = doh_resolve(host)
        s = socket.create_connection((ip, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _raw_request(host: str, use_ssl: bool, path: str, headers: dict,
                 timeout: int = 20, max_head: int = 8192, port: int = None):
    """Сырой запрос, возвращает (status_line, headers_dict_lower, sock_с_остатком_тела).

    Хост резолвится через DoH, SNI — на хост. Сокет НЕ закрывается — тело читает вызывающий.
    """
    ip = doh_resolve(host)
    raw = socket.create_connection(
        (ip, port or (443 if use_ssl else 80)), timeout=timeout)
    raw.settimeout(20)  # зависший recv — в ретрай и на другую ноду, а не в вечность
    sock = ssl.create_default_context().wrap_socket(
        raw, server_hostname=host) if use_ssl else raw
    lines = [f"GET {path} HTTP/1.1", f"Host: {host}"] + \
            [f"{k}: {v}" for k, v in headers.items()] + ["Connection: close", "", ""]
    sock.sendall("\r\n".join(lines).encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        ch = sock.recv(262144)
        if not ch:
            break
        buf += ch
        if len(buf) > max_head + 262144:
            break
    head, _, rest = buf.partition(b"\r\n\r\n")
    hd = {}
    for ln in head.decode("latin1").split("\r\n")[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            hd[k.strip().lower()] = v.strip()
    return head.decode("latin1").split("\r\n", 1)[0], hd, (sock, rest)


def head_info(sess: Session, url: str, referer: str):
    """Размер и финальный URL с проходом 302-цепочки.

    Важно: HEAD редиректов НЕ даёт — шлём GET Range: bytes=0-0, в ответе 206
    с Content-Range (там и полный размер). Тело не качаем — закрываем сокет.
    Возвращает (final_url, size|None).
    """
    cur = url
    for _ in range(5):
        parts = urllib.parse.urlsplit(cur)
        host = parts.hostname
        if host in sess.dead_hosts:
            raise RuntimeError(f"нода {host} недоступна (кэш)")
        if not _tcp_ok(host):
            sess.dead_hosts.add(host)
            raise RuntimeError(f"нода {host} недоступна (нет маршрута)")
        path = parts.path + (("?" + parts.query) if parts.query else "")
        try:
            st, hd, (sock, _) = _raw_request(
                host, parts.scheme == "https", path,
                {"User-Agent": UA, "Referer": referer, "Range": "bytes=0-0"},
                port=parts.port)
        except Exception as e:
            sess.dead_hosts.add(host)
            raise RuntimeError(f"нода {host}: {str(e)[:60]}")
        try:
            code = int(st.split()[1])
        except Exception:
            raise RuntimeError(f"CDN: {st[:60]}")
        loc = hd.get("location")
        if code in (301, 302, 303, 307, 308) and loc:
            try:
                sock.close()
            except Exception:
                pass
            cur = loc if loc.startswith("http") else urllib.parse.urljoin(cur, loc)
            continue
        size = None
        cr = hd.get("content-range", "")
        m = re.search(r"/(\d+)", cr)
        if m:
            size = int(m.group(1))
        elif hd.get("content-length", "").isdigit():
            size = int(hd["content-length"])
        try:
            sock.close()
        except Exception:
            pass
        if code in (200, 206):
            return cur, size
        raise RuntimeError(f"CDN HTTP {code}")
    raise RuntimeError("слишком много редиректов CDN")


def pick_playable(sess: Session, streams: dict, quality: str, referer: str):
    """(final_mp4_url, label, size) — ближайшее качество ≤ запрошенного с живой нодой."""
    want = int(re.search(r"\d+", quality or "480").group(0))
    avail = sorted((int(re.search(r"\d+", k).group(0)), k) for k in streams)
    lower = [k for n, k in avail if n <= want]
    higher = [k for n, k in avail if n > want]
    order = lower[::-1] + higher  # сначала ближайшее снизу, потом ближайшее сверху
    if not order:
        order = [k for _, k in avail]
    errors = []
    for label in order:
        try:
            final, size = head_info(sess, streams[label].split(":hls:")[0], referer)
            return final, label, size
        except Exception as e:
            errors.append(f"{label}: {e}")
    raise RuntimeError("CDN недоступен: " + " | ".join(errors)[:250])


def download_mp4(sess: Session, url: str, referer: str, dest: str, size: int = None,
                 threads: int = 16, on_progress=None, cancel=None):
    """Параллельное скачивание кусками по 8 МБ (замер: 16 потоков ~200 КБ/с,
    8 потоков ~100 КБ/с; больше 16 — сервер режет коннекты).

    Сначала head_info: проход 302-цепочки до живой edge-ноды. Куски качаются уже
    напрямую с неё. Ошибки потоков пробрасываются, итог сверяется с размером.
    """
    import threading

    final, total = None, None
    edge = {}
    edge_lock = threading.Lock()

    def re_resolve():
        f, t = head_info(sess, url.split(":hls:")[0], referer)
        p = urllib.parse.urlsplit(f)
        edge.update(url=f, host=p.hostname, use_ssl=p.scheme == "https",
                    base=p.path + (("?" + p.query) if p.query else ""),
                    port=p.port)
        return t

    total = re_resolve()
    size = size or total

    def fetch_range(a, b):
        last = None
        # до 3 разных edge-нод: CDN ротирует их на каждый запрос,
        # дохлая/висящая нода заменяется живой
        for _edge_try in (1, 2, 3):
            h, use_ssl = edge["host"], edge["use_ssl"]
            base, port = edge["base"], edge.get("port")
            for _ in range(2):
                if cancel and cancel():
                    raise RuntimeError("cancelled")
                try:
                    st, hd, (sock, rest) = _raw_request(
                        h, use_ssl, base,
                        {"User-Agent": UA, "Referer": referer,
                         "Range": f"bytes={a}-{b}"}, timeout=20, port=port)
                    code = int(st.split()[1])
                    if code not in (200, 206):
                        try:
                            sock.close()
                        except Exception:
                            pass
                        last = st[:60]
                        continue
                    need = (b - a + 1) if code == 206 else None
                    data = rest
                    while need is None or len(data) < need:
                        ch = sock.recv(262144)
                        if not ch:
                            break
                        data += ch
                    try:
                        sock.close()
                    except Exception:
                        pass
                    if need is not None and len(data) < need:
                        # сервер молча оборвал кусок — не склеиваем огрызок, а ретраим
                        last = f"short {len(data)}/{need} @{h}"
                        continue
                    return data[:need] if need else data
                except RuntimeError:
                    raise
                except Exception as e:
                    last = f"{str(e)[:70]} @{h}"
            # кусок не дался на этой ноде — пробуем свежую
            try:
                with edge_lock:
                    re_resolve()
            except Exception as e:
                last = f"{last} | edge: {str(e)[:70]}"
        raise RuntimeError(f"Range {a}-{b}: {last} (3 ноды исчерпаны)")

    if size and size > 4 * 1024 * 1024:
        CHUNK = 8 * 1024 * 1024
        n = max(1, (size + CHUNK - 1) // CHUNK)
        bounds = [(i * CHUNK, min(size - 1, (i + 1) * CHUNK - 1))
                  for i in range(n)]
        sem = threading.Semaphore(max(1, threads))
        chunks, done, errs = [b""] * n, [0] * n, [None] * n

        def worker(i):
            try:
                with sem:
                    a, b = bounds[i]
                    chunks[i] = fetch_range(a, b)
                done[i] = len(chunks[i])
                if on_progress:
                    on_progress(sum(done) / size)
            except Exception as e:
                errs[i] = e

        ths = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(n)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
            if cancel and cancel():
                raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
        for e in errs:
            if e is not None:
                raise e
        with open(dest, "wb") as f:
            for c in chunks:
                f.write(c)
        if on_progress:
            on_progress(1.0)
        got = sum(len(c) for c in chunks)
        if size and abs(got - size) > 1024:
            raise RuntimeError(f"скачалось {got} из {size} байт")
        return dest

    # фолбэк: один поток
    data = fetch_range(0, (size - 1) if size else 10 ** 12)
    with open(dest, "wb") as f:
        f.write(data)
    if on_progress:
        on_progress(1.0)
    return dest

# ============================================================
# 3. KINOVIBE (парсинг kinovibe.cc: поиск, плеер Playerjs, плейлисты)
# ============================================================
KV_BASE = "https://kinovibe.cc"


def kv_get(url: str, referer: str = KV_BASE + "/") -> str:
    req = urllib.request.Request(url, headers={**{"User-Agent": UA}, "Referer": referer})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def kv_post(url: str, params: dict) -> str:
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA, "Referer": KV_BASE + "/",
        "Content-Type": "application/x-www-form-urlencoded"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def _kv_clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    for a, b in [("&quot;", '"'), ("&#039;", "'"), ("&amp;", "&"),
                 ("&laquo;", "«"), ("&raquo;", "»"), ("&nbsp;", " ")]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def kv_search(query: str, limit: int = 20):
    html = kv_post(KV_BASE + "/index.php?do=search&subaction=search",
                   {"do": "search", "subaction": "search", "titleonly": 3,
                    "search_start": 1, "full_search": 1, "result_from": 1,
                    "story": query})
    blocks = [m.start() for m in re.finditer(r'<a class="sres-wrap clearfix"', html)]
    out = []
    for idx, st in enumerate(blocks):
        chunk = html[st:blocks[idx + 1] if idx + 1 < len(blocks) else st + 4000]
        href = re.search(r'href="([^"]+)"', chunk)
        img = re.search(r'<img[^>]+src="([^"]+)"', chunk)
        h2 = re.search(r"<h2>(.*?)</h2>", chunk, re.S)
        desc = re.search(r'sres-desc">(.*?)</div>', chunk, re.S)
        if not href:
            continue
        title = _kv_clean(h2.group(1)) if h2 else href.group(1).rstrip("/").split("/")[-1]
        ym = re.search(r"(19|20)\d{2}", title)
        poster = img.group(1) if img else ""
        if poster.startswith("//"):
            poster = "https:" + poster
        elif poster.startswith("/"):
            poster = KV_BASE + poster
        out.append({"src": "kinovibe", "page_url": href.group(1),
                    "title": title, "sub": _kv_clean(desc.group(1))[:120] if desc else "",
                    "year": ym.group(0) if ym else "",
                    "info": _kv_clean(desc.group(1))[:80] if desc else "",
                    "poster": poster})
        if len(out) >= limit:
            break
    return out


def kv_page(page_url: str) -> dict:
    html = kv_get(page_url)
    if "не бот" in html or ("player-tab" not in html and "players-section" not in html):
        raise RuntimeError("KinoVibe: проверка на бота — подождите 30 сек и повторите")
    if "правообладател" in html or "p-closed" in html or "film is blocked" in html:
        raise RuntimeError("Удалено по требованию правообладателя (на сайте только трейлер)")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    orig = re.search(r'FullstoryTitleEng"[^>]*>.*?<span[^>]*>(.*?)</span>', html, re.S)
    p = ""
    m_og = re.search(r'meta property="og:image" content="([^"]+)"', html)
    m_item = re.search(r'<img[^>]*itemprop="image"[^>]+src="([^"]+)"', html)
    m_filt = re.search(r'<img[^>]*miniFiltereder[^>]+src="([^"]+)"', html)
    for cand in [m_og.group(1) if m_og else "", m_item.group(1) if m_item else "",
                 m_filt.group(1) if m_filt else ""]:
        if cand and "_kinovibe.jpg" not in cand and "empty.png" not in cand:
            p = cand
            break
    if not p:
        # последний шанс: первый xfieldimage не из карусели
        for m in re.finditer(r'<img[^>]+src="([^"]+)"', html):
            u = m.group(1)
            if "_kinovibe.jpg" not in u and "empty.png" not in u and \
                    ("uploads/posts/" in u or "uploads/fotos/" in u):
                p = u
                break
    desc = re.search(r'full-story[^>]*>(.*?)</div>\s*</div>', html, re.S)
    if not desc:
        desc = re.search(r'meta name="description" content="([^"]+)"', html)
    files = re.findall(r'file:"([^"]+)"', html)
    quals = re.search(r'"qualities":"([^"]+)"', html)
    main_file, playlist_url = "", ""
    for f in files:
        if f.endswith(".txt"):
            playlist_url = f if f.startswith("http") else KV_BASE + f
        elif f.endswith(".mp4") and "/trailer/" not in f and not main_file:
            main_file = f
    if not main_file and not playlist_url:
        if any("/trailer/" in f for f in files):
            raise RuntimeError("На странице только трейлер — фильм удалён")
        raise RuntimeError("KinoVibe: видеофайл не найден на странице")
    year = re.search(r"(19|20)\d{2}", h1.group(1) if h1 else "")
    if p.startswith("//"):
        p = "https:" + p
    elif p.startswith("/"):
        p = KV_BASE + p
    episodes = []
    voice = ""
    if playlist_url:
        try:
            pl = json.loads(kv_get(playlist_url, referer=page_url).lstrip("﻿"))
            for item in pl.get("playlist", []):
                comment = _kv_clean(item.get("comment", ""))
                m = re.search(r"(\d+)\s*Серия", comment)
                voice_m = re.search(r"<br>(.*)", item.get("comment", ""))
                voice = _kv_clean(voice_m.group(1)) if voice_m and not voice else voice
                if m:
                    episodes.append({"season": 1, "episode": int(m.group(1)),
                                     "name": comment, "file": item.get("file", "")})
        except Exception:
            pass
    is_series = bool(episodes)
    title = _kv_clean(h1.group(1)) if h1 else page_url
    title = re.sub(r"\s*смотреть онлайн.*$", "", title, flags=re.I)
    return {"src": "kinovibe", "page_url": page_url,
            "title": title, "sub": _kv_clean(orig.group(1)) if orig else "",
            "poster": p,
            "description": _kv_clean(desc.group(1)) if desc else "Описание отсутствует.",
            "year": year.group(0) if year else "",
            "translators": ([{"id": "0", "name": voice or "Озвучка"}] if is_series else []),
            "seasons": [1] if is_series else [],
            "episodes": episodes, "is_series": is_series,
            "file": main_file,
            "qualities": quals.group(1) if quals else "",
            "runtime": 0}


def kv_size(url: str, referer: str):
    """Размер файла через HEAD (CDN доступен напрямую)."""
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": UA, "Referer": referer})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            ln = r.headers.get("Content-Length")
            return int(ln) if ln and ln.isdigit() else None
    except Exception:
        return None


class _NoRange(Exception):
    pass


def _kv_raw(host: str, use_ssl: bool, path: str, headers: dict, timeout: int = 20):
    """Сырой сокет: (status_code, headers, sock, rest). Сокет не закрывается."""
    raw = socket.create_connection(
        (socket.gethostbyname(host), 443 if use_ssl else 80), timeout=timeout)
    raw.settimeout(30)
    sock = ssl.create_default_context().wrap_socket(
        raw, server_hostname=host) if use_ssl else raw
    lines = [f"GET {path} HTTP/1.1", f"Host: {host}"] + \
            [f"{k}: {v}" for k, v in headers.items()] + ["Connection: close", "", ""]
    sock.sendall("\r\n".join(lines).encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        ch = sock.recv(65536)
        if not ch:
            break
        buf += ch
    head, _, rest = buf.partition(b"\r\n\r\n")
    hd = {}
    for ln in head.decode("latin1").split("\r\n")[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            hd[k.strip().lower()] = v.strip()
    return int(head.decode("latin1").split()[1]), hd, sock, rest


def kv_download(url: str, referer: str, dest: str, size: int = None,
                threads: int = 16, on_progress=None, cancel=None):
    """Параллельное скачивание кусками по 8 МБ (с пробой Range + фолбэком)."""
    import threading

    if size is None:
        size = kv_size(url, referer)
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname
    use_ssl = parts.scheme == "https"
    base_path = parts.path + (("?" + parts.query) if parts.query else "")
    H = {"User-Agent": UA, "Referer": referer}

    def fetch_range(a, b):
        last = None
        for _ in range(3):
            if cancel and cancel():
                raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
            try:
                st, hd, sock, rest = _kv_raw(host, use_ssl, base_path,
                                             {**H, "Range": f"bytes={a}-{b}"})
                if st not in (200, 206):
                    try:
                        sock.close()
                    except Exception:
                        pass
                    last = f"HTTP {st}"
                    continue
                if st == 200:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    raise _NoRange()
                need = b - a + 1
                data = rest
                while len(data) < need:
                    ch = sock.recv(262144)
                    if not ch:
                        break
                    data += ch
                try:
                    sock.close()
                except Exception:
                    pass
                if len(data) < need:
                    last = f"short {len(data)}/{need}"
                    continue
                return data[:need]
            except _NoRange:
                raise
            except RuntimeError:
                raise
            except Exception as e:
                last = str(e)[:80]
        raise RuntimeError(f"Range {a}-{b}: {last}")

    def single_stream():
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            got = 0
            while True:
                if cancel and cancel():
                    raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
                ch = r.read(262144)
                if not ch:
                    break
                f.write(ch)
                got += len(ch)
                if on_progress and size:
                    on_progress(min(got / size, 1.0))
        if on_progress:
            on_progress(1.0)
        return dest

    use_parallel = False
    if size and size > 4 * 1024 * 1024:
        try:
            st, hd, sock, rest = _kv_raw(host, use_ssl, base_path,
                                         {**H, "Range": "bytes=0-0"})
            try:
                sock.close()
            except Exception:
                pass
            use_parallel = (st == 206)
        except Exception:
            use_parallel = False

    if not use_parallel:
        return single_stream()

    CHUNK = 8 * 1024 * 1024
    n = max(1, (size + CHUNK - 1) // CHUNK)
    bounds = [(i * CHUNK, min(size - 1, (i + 1) * CHUNK - 1)) for i in range(n)]
    sem = threading.Semaphore(max(1, threads))
    chunks, done, errs = [b""] * n, [0] * n, [None] * n

    def worker(i):
        try:
            with sem:
                a, b = bounds[i]
                chunks[i] = fetch_range(a, b)
            done[i] = len(chunks[i])
            if on_progress:
                on_progress(sum(done) / size)
        except Exception as e:
            errs[i] = e

    ths = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(n)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
        if cancel and cancel():
            raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
    for e in errs:
        if e is not None:
            raise e
    with open(dest, "wb") as f:
        for c in chunks:
            f.write(c)
    if on_progress:
        on_progress(1.0)
    got = sum(len(c) for c in chunks)
    if size and abs(got - size) > 1024:
        raise RuntimeError(f"скачалось {got} из {size} байт")
    return dest


# ============================================================
# 4. YOUTUBE (yt-dlp: поиск, мета, скачивание <=480p mp4)
# ============================================================
class YTCancelled(Exception):
    pass


def yt_search(query: str, limit: int = 10):
    from yt_dlp import YoutubeDL
    with YoutubeDL({"quiet": True, "no_warnings": True,
                    "socket_timeout": 20}) as ydl:
        res = ydl.extract_info(f"ytsearch{max(1, limit)}:{query}", download=False)
    out = []
    for e in (res.get("entries") or [])[:limit]:
        if not e:
            continue
        thumbs = e.get("thumbnails") or []
        out.append({"src": "youtube", "vid": e.get("id", ""),
                    "url": e.get("webpage_url") or
                    f"https://www.youtube.com/watch?v={e.get('id', '')}",
                    "title": e.get("title") or "?",
                    "sub": f"{fmt_dur(e.get('duration'))} • {e.get('channel') or ''}",
                    "year": (e.get("upload_date") or "")[:4],
                    "info": f"{e.get('view_count') or 0} просмотров",
                    "poster": (thumbs[-1].get("url") if thumbs else ""),
                    "duration": e.get("duration") or 0})
    return out


def yt_info(url: str) -> dict:
    from yt_dlp import YoutubeDL
    with YoutubeDL({"quiet": True, "no_warnings": True,
                    "socket_timeout": 20}) as ydl:
        return ydl.extract_info(url, download=False)


def yt_download(url: str, dest_tpl: str, on_progress=None, cancel=None) -> str:
    """Скачивает <=480p mp4 (мерж через ffmpeg). Возвращает путь файла."""
    from yt_dlp import YoutubeDL

    def hook(d):
        if cancel and cancel():
            raise YTCancelled("Отменено пользователем")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            if total and on_progress:
                on_progress(min(done / total, 1.0))
        elif d.get("status") == "finished" and on_progress:
            on_progress(1.0)

    opts = {"quiet": True, "no_warnings": True,
            "format": "bv*[height<=480]+ba/b[height<=480]/b",
            "merge_output_format": "mp4",
            "outtmpl": dest_tpl,
            "socket_timeout": 30,
            "progress_hooks": [hook]}
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    import glob
    base = re.sub(r"\.\%\(ext\)s$", "", dest_tpl)
    cands = sorted(glob.glob(base + ".*"),
                   key=lambda p: os.path.getsize(p), reverse=True)
    if not cands:
        raise RuntimeError("yt-dlp ничего не скачал")
    return cands[0]

# ============================================================
# 5. PSP-КОНВЕРТЕР
# ============================================================
"""Конвертация HLS -> PSP-совместимый MP4 через ffmpeg. Только stdlib + ffmpeg."""
import re
import shutil
import subprocess

TIME_RE = re.compile(r"time=(\d+):(\d+):([\d.]+)")
SPEED_RE = re.compile(r"speed=\s*([\d.]+)x")

# Пресеты под PSP: цель — ~60 МБ на 24-минутную серию (экран 480x272 это ок).
# Расчёт: МБ ≈ (v_kbit + a_kbit) * длительность_сек / 8 / 1024
# 24 мин = 1440 сек: (256+64)*1440/8/1024 ≈ 56 МБ + контейнер ≈ 58-60 МБ.
PRESETS = {
    "PSP • 60 МБ (256k+64k)": {"vbitrate": "256k", "maxrate": "384k", "bufsize": "768k", "abitrate": "64k"},
    "PSP • 85 МБ (384k+80k)": {"vbitrate": "384k", "maxrate": "512k", "bufsize": "1024k", "abitrate": "80k"},
    "PSP • 120 МБ (550k+96k)": {"vbitrate": "550k", "maxrate": "800k", "bufsize": "1536k", "abitrate": "96k"},
}


def _kbit(s: str) -> int:
    return int(str(s).lower().replace("k", ""))


def estimate_mb(preset: dict, duration_sec: int = 1440) -> float:
    total_kbit = _kbit(preset["vbitrate"]) + _kbit(preset["abitrate"])
    return round(total_kbit * duration_sec / 8 / 1024 * 1.04, 1)  # +4% контейнер

VF_480x272 = "scale=480:272:force_original_aspect_ratio=decrease,pad=480:272:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"

# Режимы кадра для PSP (экран 16:9). Для 16:9-источника все три одинаковы (во весь экран).
# Разница только для 4:3-аниме (старые сериалы вроде Naruto 2002):
ASPECT_MODES = {
    # 4:3 растягивается на весь экран без полос (лица шире — зато fullscreen)
    "16:9 во весь экран": "scale=480:272,setsar=1",
    # 4:3 увеличивается и режется сверху/снизу (без искажений, но теряются края/сабы)
    "16:9 с обрезкой краёв": "scale=480:272:force_original_aspect_ratio=increase,crop=480:272,setsar=1",
    # как в источнике: 4:3 — со столбами по бокам, без искажений и потерь
    "Как в источнике (полосы)": VF_480x272,
}
DEFAULT_ASPECT = "Как в источнике (полосы)"


def check_ffmpeg() -> str | None:
    path = shutil.which("ffmpeg")
    return path


def probe_duration(path: str) -> float | None:
    """Длительность файла в секундах через ffprobe (для точного прогресса)."""
    try:
        r = subprocess.run(
            ["ffprobe", "-hide_banner", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:
        return None


def _is_http(url: str) -> bool:
    u = (url or "").lower()
    return u.startswith("http://") or u.startswith("https://")


def build_psp_cmd(hls_url: str, out_mp4: str, preset: dict, aspect: str = DEFAULT_ASPECT,
                  referer: str = None) -> list:
    # Скорость: veryfast + threads 0 (на 8 ядрах кодирование ~17-19x realtime,
    # узкое место — скачивание HLS, поэтому источник по умолчанию 480p).
    # Надёжность: reconnect-флаги (HLS рвётся — ffmpeg переподключается, а не падает),
    # rw_timeout и nostdin (чтобы ffmpeg не ждал ввода).
    # HTTP-опции (-user_agent/-reconnect/-headers) — только для сетевого входа:
    # перед локальным файлом ffmpeg на них падает (Option not found).
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-stats_period", "0.2"]
    if _is_http(hls_url):
        cmd += ["-user_agent", "Mozilla/5.0",
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "10",
                "-rw_timeout", "15000000"]
        if referer:
            cmd += ["-headers", f"Referer: {referer}\r\n"]
    cmd += ["-i", hls_url,
            "-vf", ASPECT_MODES.get(aspect, ASPECT_MODES[DEFAULT_ASPECT]),
        "-c:v", "libx264",
        "-profile:v", "baseline",
        "-level", "3.0",
        "-preset", "veryfast",
        "-threads", "0",
        "-b:v", preset["vbitrate"],
        "-maxrate", preset["maxrate"],
        "-bufsize", preset["bufsize"],
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", preset["abitrate"],
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        "-f", "mp4",
        out_mp4,
    ]
    return cmd


def parse_ffmpeg_time(line: str) -> float | None:
    m = TIME_RE.search(line)
    if not m:
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mi * 60 + s


def download_convert(hls_url: str, out_mp4: str, preset: dict,
                     duration_sec: int = 1440,
                     on_progress=None, cancel_flag=None,
                     min_bytes: int = 1_000_000,
                     aspect: str = DEFAULT_ASPECT) -> tuple[bool, str]:
    """Качает HLS и сразу кодирует в PSP MP4.

    on_progress(frac 0..1, speed_str|None, time_sec) — живой прогресс для UI.
    При обрыве возвращает хвост лога ffmpeg, чтобы было видно причину.
    Файл меньше min_bytes считается битым.
    """
    import collections
    import os
    cmd = build_psp_cmd(hls_url, out_mp4, preset, aspect)
    tail = collections.deque(maxlen=6)
    try:
        proc = subprocess.Popen(
            cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
            universal_newlines=True, encoding="utf-8", errors="ignore",
        )
    except FileNotFoundError:
        return False, "ffmpeg не найден в PATH"
    for line in proc.stdout:
        line = line.strip()
        if line:
            tail.append(line[-220:])
        if cancel_flag is not None and cancel_flag():
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            return False, "Отменено пользователем"
        t = parse_ffmpeg_time(line)
        if t is not None and on_progress is not None:
            m = SPEED_RE.search(line)
            frac = min(max(t / max(duration_sec, 1), 0.0), 1.0)
            on_progress(frac, m.group(1) + "x" if m else None, t)
    proc.wait()
    if proc.returncode != 0:
        return False, f"ffmpeg exit={proc.returncode} :: {' | '.join(tail) or 'нет лога'}"
    if on_progress is not None:
        on_progress(1.0, None, duration_sec)
    try:
        size = os.path.getsize(out_mp4)
    except OSError:
        return False, "файл не создан (ffmpeg ничего не записал)"
    if size < min_bytes:
        return False, f"файл битый ({size // 1024} КБ < {min_bytes // 1024} КБ) :: {' | '.join(tail)}"
    return True, out_mp4


def make_thumbnail(mp4_path: str, thm_path: str, ss: int = 5) -> bool:
    """THM-превью 160x120 для старых прошивок PSP."""
    cmd = ["ffmpeg", "-y", "-ss", str(ss), "-i", mp4_path,
           "-vframes", "1", "-s", "160x120", thm_path]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
        return True
    except Exception:
        return False

class AppSearchMixin:
    def _build_search_page(self):
        pg = self._pages["search"]
        pg.grid_columnconfigure(1, weight=1)
        # ряды: 0=источник, 1=поиск, 2=заголовки, 3=контент
        pg.grid_rowconfigure(3, weight=1)
        # верх: источник + поиск
        top = ctk.CTkFrame(pg, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.src_seg = ctk.CTkSegmentedButton(
            top, values=[label for _, label, _ in SOURCES],
            command=self._on_src_change)
        self.src_seg.pack(side="left")
        self.src_seg.set("HDRezka")
        self.src_hint = ctk.CTkLabel(top, text="", text_color=MUTED,
                                     font=ctk.CTkFont(size=12))
        self.src_hint.pack(side="left", padx=10)
        self.L(self.src_hint, "src_rezka")
        srow = ctk.CTkFrame(pg, fg_color="transparent")
        srow.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            srow, textvariable=self.search_var, height=42, font=ctk.CTkFont(size=14),
            placeholder_text="Фильм, сериал, аниме — например: интерстеллар, фрирен…")
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        self.search_btn = ctk.CTkButton(srow, text="", height=42, width=120,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=ACCENT, text_color="#11111b", hover_color="#8db0ff",
                      command=self.on_search)
        self.search_btn.pack(side="left", padx=(8, 0))
        self.L(self.search_btn, "search_btn")
        self.L(self.search_entry, "search_ph", "placeholder_text")
        self.spinner = Spinner(srow, font=ctk.CTkFont(size=18), text_color=ACCENT)
        self.spinner.pack(side="left", padx=8)
        # заголовки (отдельный ряд — не поверх поиска)
        self._headers = []
        for c, k in [(0, "h_results"), (1, "h_desc"), (2, "h_eps")]:
            lb = ctk.CTkLabel(pg, text="", font=ctk.CTkFont(size=12, weight="bold"),
                              text_color=MUTED)
            lb.grid(row=2, column=c, sticky="w", padx=(0, 8) if c < 2 else 0)
            self._headers.append(lb)
            self.L(lb, k)
        # колонки контента
        self.res_scroll = ctk.CTkScrollableFrame(pg, width=260, label_text="")
        self.res_scroll.grid(row=3, column=0, sticky="nsew", padx=(0, 8))
        center = ctk.CTkFrame(pg)
        center.grid(row=3, column=1, sticky="nsew", padx=8)
        center.grid_columnconfigure(0, weight=1)
        card_top = ctk.CTkFrame(center, fg_color="transparent")
        card_top.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        card_top.grid_columnconfigure(1, weight=1)
        self.poster_lbl = ctk.CTkLabel(card_top, text="постер\nпоявится здесь",
                                       width=250, height=356, fg_color="#1f2335",
                                       corner_radius=10)
        self.poster_lbl.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 14))
        self.title_lbl = ctk.CTkLabel(card_top, text="Выбери результат слева",
                                      font=ctk.CTkFont(size=20, weight="bold"),
                                      wraplength=560, justify="left", anchor="w")
        self.title_lbl.grid(row=0, column=1, sticky="ew")
        self.meta_lbl = ctk.CTkLabel(card_top, text="поиск выше → клик по карточке",
                                     font=ctk.CTkFont(size=13), text_color=ACCENT,
                                     wraplength=560, justify="left", anchor="w")
        self.meta_lbl.grid(row=1, column=1, sticky="ew")
        self.genre_lbl = ctk.CTkLabel(center, text="", font=ctk.CTkFont(size=12),
                                      text_color="#bb9af7", wraplength=520,
                                      justify="left", anchor="w")
        self.genre_lbl.grid(row=1, column=0, sticky="ew", padx=12)
        self.desc_box = ctk.CTkTextbox(center, wrap="word", font=ctk.CTkFont(size=13))
        self.desc_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=8)
        center.grid_rowconfigure(2, weight=1)
        self.desc_box.insert("1.0", "Здесь будет описание, жанры, год, озвучки и сезоны.")
        self.desc_box.configure(state="disabled")
        self.stats_lbl = ctk.CTkLabel(center, text="", font=ctk.CTkFont(size=12, weight="bold"),
                                      text_color=GREEN, anchor="w")
        self.stats_lbl.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 10))
        # правая колонка (ряд контента 3)
        right = ctk.CTkFrame(pg, fg_color="transparent")
        right.grid(row=3, column=2, sticky="nsew")
        self.rzbar = ctk.CTkFrame(right, fg_color="transparent")
        self.rz_voice_lbl = ctk.CTkLabel(self.rzbar, text="",
                                         font=ctk.CTkFont(size=11), text_color=MUTED)
        self.rz_voice_lbl.pack(anchor="w")
        self.L(self.rz_voice_lbl, "voice")
        self.rz_trans_var = tk.StringVar(value="")
        self.rz_trans_menu = ctk.CTkOptionMenu(self.rzbar, variable=self.rz_trans_var,
                                               values=[], command=lambda _: self._on_extra_sel())
        self.rz_trans_menu.pack(fill="x", pady=(0, 4))
        self.rz_season_lbl = ctk.CTkLabel(self.rzbar, text="",
                                            font=ctk.CTkFont(size=11), text_color=MUTED)
        self.rz_season_lbl.pack(anchor="w")
        self.L(self.rz_season_lbl, "season")
        self.rz_season_var = tk.StringVar(value="1")
        self.rz_season_menu = ctk.CTkOptionMenu(self.rzbar, variable=self.rz_season_var,
                                                values=["1"], command=lambda _: self._on_extra_sel())
        self.rz_season_menu.pack(fill="x", pady=(0, 6))
        erow = ctk.CTkFrame(right, fg_color="transparent")
        erow.pack(fill="x", pady=(0, 6))
        self._erow = erow
        self.sel_all_btn = ctk.CTkButton(erow, text="", width=60, fg_color="transparent",
                                          border_width=1, command=self._sel_all)
        self.sel_all_btn.pack(side="left")
        self.L(self.sel_all_btn, "sel_all")
        self.sel_none_btn = ctk.CTkButton(erow, text="", width=60, fg_color="transparent",
                                          border_width=1, command=self._sel_none)
        self.sel_none_btn.pack(side="left", padx=6)
        self.L(self.sel_none_btn, "sel_none")
        self.size_lbl = ctk.CTkLabel(erow, text="", font=ctk.CTkFont(size=12, weight="bold"),
                                     text_color=GREEN)
        self.size_lbl.pack(side="right")
        self.ep_scroll = ctk.CTkScrollableFrame(right, width=280)
        self.ep_scroll.pack(fill="both", expand=True)
        self.queue_btn = ctk.CTkButton(right, text="",
                                       height=40, font=ctk.CTkFont(size=13, weight="bold"),
                                       fg_color=ACCENT, text_color="#11111b",
                                       hover_color="#8db0ff", command=self.add_to_queue)
        self.queue_btn.pack(fill="x", pady=(8, 0))
        self.L(self.queue_btn, "queue_add")

    # ---------- источник ----------
    def _src_key(self):
        label = self.src_seg.get()
        for k, lb, _ in SOURCES:
            if lb == label:
                return k
        return "rezka"

    def _on_src_change(self, label):
        for k, lb, _h in SOURCES:
            if lb == label:
                self.src_hint.configure(text=self.T("src_" + k))
                return

    # ---------- поиск ----------
    def on_search(self):
        q = self.search_var.get().strip()
        if not q or getattr(self, "busy", False):
            return
        self.busy = True
        src = self._src_key()
        self.set_side(f"Поиск [{src}]: {q}…")
        self.spinner.start("Ищу ")
        self.logln(f"Поиск [{src}]: {q}")

        def job():
            try:
                if src == "anilibria":
                    res = ani_search(q)
                elif src == "rezka":
                    res = search(self._rz_session(), q)
                elif src == "kinovibe":
                    res = kv_search(q)
                elif src == "anwap":
                    res = aw_search(q)
                else:
                    res = yt_search(q)
                    for r in res:
                        r["poster_cache"] = r["vid"]
                self.results = res
                self._ui(lambda: self._show_results(res))
                self._ui(lambda n=len(res): self._search_done_ui(n))
                if not res:
                    self._ui(lambda: self.logln(self.T("nothing_found")))
            except Exception as e:
                self._ui(lambda ee=e: self.logln(f"{self.T('search_err')}: {ee}"))
            finally:
                self.busy = False
                self._ui(lambda: self.spinner.stop())
        self.run_bg(job)

    def _search_done_ui(self, n):
        self.set_side(f"{self.T('found')}: {n}")
        self.logln(f"{self.T('found')}: {n}")

    def _show_results(self, res):
        for w in self.res_scroll.winfo_children():
            w.destroy()
        for i, r in enumerate(res):
            title = (r["title"][:42] + "…") if len(r["title"]) > 42 else r["title"]
            sub = (r.get("sub") or r.get("info") or "")[:46]
            year = r.get("year", "") or ""
            if year and sub.startswith(year):
                sub = sub[len(year):].lstrip(" ,-•")
            line2 = f"{year} • {sub}" if year and sub else (year or sub)
            txt = f"{title}\n{line2}" if line2 else title
            b = ctk.CTkButton(self.res_scroll, text=txt, anchor="w",
                              fg_color="transparent", border_width=1,
                              height=56, font=ctk.CTkFont(size=13),
                              command=lambda rr=r: self._pick_result(rr))
            # каскадное появление карточек
            self.after(i * 45, lambda b=b: b.pack(fill="x", pady=3) if b.winfo_exists() else None)

    def _pick_result(self, item):
        if getattr(self, "busy", False):
            return
        self.busy = True
        self.spinner.start("Гружу ")
        self.set_side(f"Загрузка: {item['title'][:40]}…")

        def job():
            try:
                src = item["src"]
                self._ui(lambda: self.set_side(f"Страница: {item['title'][:40]}…"))
                if src == "anilibria":
                    rel = self._load_retry(
                        lambda: ani_release(item["id"]), " AniLibria")
                    self.detail = self._norm_ani(rel)
                elif src == "rezka":
                    info = self._load_retry(
                        lambda: page_info(self._rz_session(), item["page_url"]), "HDRezka")
                    self.detail = self._norm_rz(info, item["page_url"])
                elif src == "kinovibe":
                    info = self._load_retry(
                        lambda: kv_page(item["page_url"]), "KinoVibe")
                    self.detail = self._norm_kv(info)
                elif src == "anwap":
                    info = self._load_retry(
                        lambda: aw_page(item["page_url"]), "Anwap")
                    self.detail = self._norm_aw(info)
                else:
                    info = self._load_retry(
                        lambda: yt_info(item["url"]), "YouTube")
                    self.detail = self._norm_yt(info, item)
                self._ui(lambda: self._show_detail_safe())
                poster = self.detail.get("poster")
                if poster:
                    self.run_bg(lambda: self._load_poster(poster, self.detail.get("cache_key", "x")))
            except Exception as e:
                self._ui(lambda ee=e: self._show_pick_error(item, ee))
            finally:
                self.busy = False
                self._ui(lambda: self.spinner.stop())
        self.run_bg(job)

    def _load_retry(self, fn, label, tries=3):
        """Загрузка страницы с видимыми попытками (сеть к резке рвётся)."""
        msg = ""
        for a in range(1, tries + 1):
            try:
                if a > 1:
                    self._ui(lambda aa=a: self.set_side(f"{label}: попытка {aa}/{tries}…"))
                return fn()
            except Exception as e:
                msg = str(e)[:150]
                self._ui(lambda m=msg: self.logln(f"{label}: попытка не удалась ({m})"))
                time.sleep(1 + a)
        raise RuntimeError(f"{label}: {msg}")

    def _show_detail_safe(self):
        try:
            self._show_detail(self.detail)
        except Exception as e:
            self._show_pick_error({"title": (self.detail or {}).get("title", "?")}, e)

    def _show_pick_error(self, item, err):
        """Ошибка — ВИДНО в панели описания, а не только в скрытом логе."""
        self.logln(f"Ошибка: {err}")
        self.set_side(f"Ошибка: {str(err)[:80]}")
        self.title_lbl.configure(text=item.get("title", "?")[:80])
        self.meta_lbl.configure(text=f"⚠ Не загрузилось: {str(err)[:120]}",
                                text_color=RED)
        try:
            self.desc_box.configure(state="normal")
            self.desc_box.delete("1.0", "end")
            self.desc_box.insert(
                "end", f"Не удалось загрузить страницу.\n\nПричина: {err}\n\n"
                       f"Что попробовать:\n"
                       f"• подождать 30 секунд и кликнуть ещё раз;\n"
                       f"• выбрать другой перевод/сезон;\n"
                       f"• полный текст ошибки — в логе на странице Загрузки.")
            self.desc_box.configure(state="disabled")
        except Exception:
            pass

    # ---------- нормализация карточек ----------
    def _norm_ani(self, rel):
        return {"src": "anilibria", "id": rel["id"], "title": rel["title"],
                "sub": rel["sub"], "year": rel["year"],
                "meta": f"{rel['year'] or '?'} • {rel['kind']} • {rel['season']} • "
                        f"{'🟡 Онгоинг' if rel['is_ongoing'] else '🟢 Завершён'} • {rel['age']}",
                "tags": " · ".join(rel["genres"][:10]),
                "desc": rel["description"], "poster": ani_poster_full(rel["poster"]),
                "cache_key": f"ani{rel['id']}",
                "stats": f"Серий: {len(rel['episodes'])}",
                "kind": "series", "seasons_n": 1, "runtime": 0,
                "translators": [], "seasons": [],
                "episodes": [{"ordinal": e["ordinal"], "name": e.get("name") or "",
                              "duration": e.get("duration") or 1440,
                              "season": 1, "episode": e["ordinal"], "hls": e}
                             for e in rel["episodes"]]}

    def _norm_rz(self, info, page_url):
        trs = info["translators"]
        if not trs and (info.get("default") or {}).get("translator_id"):
            # у части фильмов нет списка переводов — берём дефолтный из плеера
            trs = [{"id": info["default"]["translator_id"], "name": "Озвучка"}]
        rt = info.get("runtime_min") or 0
        kind = "Сериал" if info["is_series"] else "Фильм"
        if rt and not info["is_series"]:
            kind += f" • {rt} мин"
        return {"src": "rezka", "id": info["post_id"], "page_url": page_url,
                "title": info["title"], "sub": info["orig"], "year": info["year"],
                "meta": f"{info['year'] or '?'} • {kind}"
                        f" • Озвучек: {len(trs)} • Сезонов: {len(info['seasons']) or 1}",
                "tags": " · ".join(t["name"] for t in trs[:8]),
                "desc": info["description"], "poster": info["poster"],
                "cache_key": "rz" + info["post_id"],
                "stats": "", "kind": "series" if info["is_series"] else "film",
                "seasons_n": len(info["seasons"]),
                "runtime": (info.get("runtime_min") or 0) * 60,
                "translators": trs, "seasons": info["seasons"],
                "episodes": info["episodes"], "default": info.get("default", {})}

    def _norm_kv(self, info):
        eps = []
        for e in info["episodes"]:
            eps.append({"ordinal": e["episode"], "name": e.get("name", ""),
                        "duration": 1440, "season": e["season"],
                        "episode": e["episode"], "file": e.get("file", "")})
        if not info["is_series"]:
            eps = [{"ordinal": 1, "name": "Фильм", "duration": 5400,
                    "season": 1, "episode": 1, "file": info.get("file", ""),
                    "is_film": True}]
        return {"src": "kinovibe", "id": info["page_url"], "page_url": info["page_url"],
                "title": info["title"], "sub": info["sub"], "year": info["year"],
                "meta": f"{info['year'] or '?'} • {'Сериал' if info['is_series'] else 'Фильм'}"
                        f" • {info.get('qualities', '')}",
                "tags": (info["translators"][0]["name"] if info["translators"] else ""),
                "desc": info["description"], "poster": info["poster"],
                "cache_key": "kv" + str(abs(hash(info['page_url'])) % 10 ** 8),
                "stats": "", "kind": "series" if info["is_series"] else "film",
                "seasons_n": 1, "runtime": 0,
                "translators": info["translators"], "seasons": info["seasons"],
                "episodes": eps, "file": info.get("file", "")}

    def _norm_aw(self, info):
        opts = info["options"]
        best = ""
        for o in opts:
            if "426" in o["label"]:
                best = o["label"]
                break
        best = best or opts[0]["label"]
        return {"src": "anwap", "id": info["page_url"], "page_url": info["page_url"],
                "title": info["title"], "sub": info["sub"], "year": info["year"],
                "meta": f"{info['year'] or '?'} • Фильм • {len(opts)} варианта • {best}",
                "tags": "", "desc": info["description"], "poster": info["poster"],
                "cache_key": "aw" + re.sub(r"\D", "", info["page_url"])[-8:],
                "stats": "", "kind": "film", "seasons_n": 1, "runtime": info.get("runtime") or 0,
                "translators": [], "seasons": [],
                "episodes": [{"ordinal": 1, "name": "Фильм", "duration": 5400,
                              "season": 1, "episode": 1, "is_film": True}]}

    def _norm_yt(self, info, item):
        dur = info.get("duration") or item.get("duration") or 0
        thumbs = info.get("thumbnail") or item.get("poster") or ""
        desc = (info.get("description") or "")[:1500]
        return {"src": "youtube", "id": info.get("id") or item.get("vid", ""),
                "url": info.get("webpage_url") or item.get("url", ""),
                "title": info.get("title") or item.get("title", "?"),
                "sub": f"{info.get('channel') or ''}",
                "year": (info.get("upload_date") or "")[:4],
                "meta": f"{fmt_dur(dur)} • {info.get('channel') or ''} • "
                        f"{info.get('view_count') or 0} просмотров",
                "tags": "", "desc": desc or "Без описания.",
                "poster": thumbs, "cache_key": "yt" + (info.get("id") or "x"),
                "stats": "", "kind": "film", "seasons_n": 1, "runtime": dur,
                "translators": [], "seasons": [],
                "episodes": [{"ordinal": 1, "name": "Видео", "duration": dur or 600,
                              "season": 1, "episode": 1, "is_film": True}]}

    # ---------- показ карточки ----------
    def _show_detail(self, d):
        self.title_lbl.configure(text=f"{d['title']}\n{d['sub']}" if d["sub"] else d["title"])
        self.meta_lbl.configure(text=d["meta"], text_color=ACCENT)
        self.genre_lbl.configure(text=d["tags"])
        self.desc_box.configure(state="normal")
        self.desc_box.delete("1.0", "end")
        self.desc_box.insert("end", d["desc"])
        self.desc_box.configure(state="disabled")
        # строка озвучка/сезон — только для резки
        self.rzbar.pack_forget()
        if d["src"] == "rezka":
            names = [t["name"] for t in d["translators"]] or ["—"]
            prefer = next((t["name"] for t in d["translators"]
                           if "anilibria" in t["name"].lower()), names[0])
            self.rz_trans_menu.configure(values=names)
            self.rz_trans_var.set(prefer)
            seasons = [str(s) for s in d["seasons"]] or ["1"]
            self.rz_season_menu.configure(values=seasons)
            self.rz_season_var.set(seasons[0])
            self.rzbar.pack(fill="x", pady=(0, 6), before=self._erow)
        self._render_eps()

    def _rz_trans_id(self):
        d = self.detail or {}
        name = self.rz_trans_var.get()
        for t in d.get("translators", []):
            if t["name"] == name:
                return t["id"]
        return ((d.get("translators", [{}]) or [{}])[0] or {}).get("id", "")

    def _on_extra_sel(self):
        if self.detail and self.detail["src"] == "rezka":
            self._render_eps()

    def _current_eps(self):
        """Эпизоды со страницы (без сети!). Нехватка серий сезона —
        через _fetch_season_bg в фоне."""
        d = self.detail
        if not d:
            return []
        if d["src"] == "rezka" and d["kind"] == "series":
            season = int(self.rz_season_var.get() or 1)
            eps = [e for e in d["episodes"] if e["season"] == season]
            if not eps:
                self._fetch_season_bg(season)
            out = []
            for e in eps:
                out.append({"ordinal": e["episode"], "name": e.get("name") or "",
                            "duration": 1440, "season": e["season"],
                            "episode": e["episode"]})
            return out
        if d["src"] == "rezka" and d["kind"] == "film":
            rt = d.get("runtime") or 0
            return [{"ordinal": 1, "name": f"Фильм{f' • {rt // 3600}ч {(rt % 3600) // 60}м' if rt else ''}",
                     "duration": rt or 5400, "season": 1, "episode": 1,
                     "is_film": True}]
        if d["src"] == "anilibria":
            return [{"ordinal": e["ordinal"], "name": e.get("name") or "",
                     "duration": e.get("duration") or 1440, "season": 1,
                     "episode": e["ordinal"], "hls": e["hls"]} for e in d["episodes"]]
        if d["src"] == "anwap":
            return [{"ordinal": 1, "name": "Фильм", "duration": d.get("runtime") or 5400,
                     "season": 1, "episode": 1, "is_film": True}]
        # kinovibe / youtube
        return [{"ordinal": e["ordinal"], "name": e.get("name") or "",
                 "duration": e.get("duration") or 1440, "season": e.get("season", 1),
                 "episode": e.get("episode", e["ordinal"]),
                 "file": e.get("file", ""), "is_film": e.get("is_film", False)}
                for e in d["episodes"]]

    def _fetch_season_bg(self, season):
        """Догрузка серий сезона в фоне (не морозит UI)."""
        d = self.detail
        if not d or d.get("src") != "rezka":
            return
        token = (d.get("id"), self.rz_trans_var.get(), season)
        if getattr(self, "_fetch_token", None) == token:
            return
        self._fetch_token = token
        tr = self._rz_trans_id()

        def job():
            try:
                self._ui(lambda: self.stats_lbl.configure(text="Загружаю серии…"))
                eps = get_episodes(self._rz_session(), d["page_url"], d["id"], tr, season)
                # пользователь мог уйти дальше — обновляем только свой релиз
                if self.detail is d and int(self.rz_season_var.get() or 1) == season:
                    d["episodes"].extend(
                        e for e in eps
                        if not any(x["season"] == e["season"] and
                                   x["episode"] == e["episode"] for x in d["episodes"]))
                    self._ui(lambda: self._render_eps())
            except Exception as e:
                self._ui(lambda ee=e: (
                    self.stats_lbl.configure(text=f"Серии не загрузились: {ee}"),
                    self.logln(f"Серии: {ee}")))
            finally:
                if getattr(self, "_fetch_token", None) == token:
                    self._fetch_token = None
        self.run_bg(job)

    def _render_eps(self):
        for w in self.ep_scroll.winfo_children():
            w.destroy()
        self.ep_vars.clear()
        eps = self._current_eps()
        self.detail_eps = eps
        preset = PRESETS.get(self.preset_var.get(), list(PRESETS.values())[0])
        total_dur = 0
        for ep in eps:
            dur = ep.get("duration") or 1440
            total_dur += dur
            mb = estimate_mb(preset, dur)
            var = tk.BooleanVar(value=False)
            if ep.get("is_film"):
                txt = f"▶ {ep.get('name', 'Видео')} • {fmt_dur(dur)} • ~{mb} МБ"
            else:
                txt = f"EP{ep['ordinal']:02d} • {fmt_dur(dur)} • ~{mb} МБ"
                if ep.get("name"):
                    txt += f"\n{ep['name'][:32]}"
            cb = ctk.CTkCheckBox(self.ep_scroll, text=txt, variable=var,
                                 font=ctk.CTkFont(size=12),
                                 command=self._refresh_estimates)
            cb.pack(fill="x", anchor="w", pady=2, padx=2)
            self.ep_vars.append((ep, var))
        n = len(eps)
        head = ""
        if self.detail:
            if self.detail["kind"] == "film":
                head = ""
            elif self.detail["src"] == "rezka":
                head = f"Сезон {self.rz_season_var.get()} • "
        self.stats_lbl.configure(
            text=f"{head}Позиций: {n} • Хронометраж: {total_dur // 3600}ч {(total_dur % 3600) // 60}м"
            if n else "")
        self._refresh_estimates()

    # ---------- выбор ----------
    def _sel_all(self):
        for _, v in self.ep_vars:
            v.set(True)
        self._refresh_estimates()

    def _sel_none(self):
        for _, v in self.ep_vars:
            v.set(False)
        self._refresh_estimates()

    def _selected_eps(self):
        return [ep for ep, v in self.ep_vars if v.get()]

    def _refresh_estimates(self):
        if not self.detail:
            return
        preset = PRESETS.get(self.preset_var.get(), list(PRESETS.values())[0])
        sel = self._selected_eps()
        if not sel:
            if len(self.ep_vars) == 1:
                d = self.ep_vars[0][0].get("duration") or 1440
                self.size_lbl.configure(text=f"~{estimate_mb(preset, d)} МБ")
            else:
                self.size_lbl.configure(text=f"~{estimate_mb(preset, 1440)} МБ/сер.")
            return
        total = sum(estimate_mb(preset, (ep.get("duration") or 1440)) for ep in sel)
        self.size_lbl.configure(text=f"{len(sel)} поз. ≈ {total:.0f} МБ")

    # ---------- постер ----------
    def _load_poster(self, src, rid):
        if not src:
            return
        url = src if src.startswith("http") else ("https:" + src if src.startswith("//") else src)
        self._ui(lambda: self.poster_lbl.configure(text="загрузка…"))
        try:
            path = _poster_cache_path(rid)
            if not os.path.exists(path) or os.path.getsize(path) < 5000:
                # ютуб-постеры могут требовать обычный DNS — urllib ок
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r, open(path, "wb") as f:
                    f.write(r.read())
            img = Image.open(path).convert("RGB")
            img.thumbnail((500, 720), Image.LANCZOS)
            w, h = img.size
            scale = min(250 / w, 356 / h, 1.0)
            photo = ctk.CTkImage(light_image=img, dark_image=img,
                                 size=(int(w * scale), int(h * scale)))
            self.poster_photo = photo
            self._ui(lambda: self.poster_lbl.configure(image=self.poster_photo, text=""))
        except Exception:
            self._ui(lambda: self.poster_lbl.configure(text="нет постера"))

    def _rz_session(self):
        sess = getattr(self, "_rz_sess", None)
        if sess is not None:
            return sess
        last = None
        for mirror in MIRRORS:
            try:
                sess = Session(mirror)
                doh_resolve(mirror)
                self._rz_sess = sess
                return sess
            except Exception as e:
                last = e
        raise RuntimeError(f"HDRezka недоступна: {last}")

    def add_to_queue(self):
        if not self.detail:
            messagebox.showinfo(APP_TITLE, self.T("need_sel"))
            return
        sel = self._selected_eps()
        if not sel:
            messagebox.showinfo(APP_TITLE, self.T("need_eps"))
            return
        d = self.detail
        added = 0
        for ep in sel:
            self.job_seq += 1
            self.queue.append({
                "id": self.job_seq, "src": d["src"], "title": d["title"],
                "ep_label": ep.get("name") and f"EP{ep['ordinal']:02d} • {ep['name'][:30]}"
                or (f"EP{ep['ordinal']:02d}" if not ep.get("is_film") else "Фильм"),
                "ep": dict(ep), "detail": d,
                "translator": self.rz_trans_var.get() if d["src"] == "rezka" else "",
                "status": "queued", "frac": 0.0, "phase": "queued",
                "speed": "", "eta": "", "done": 0, "total": 0,
                "out": "", "msg": "", "cancel": False,
            })
            added += 1
        self.logln(f"{self.T('added_queue')}: {added} ({self.T('total_word')} {len(self.queue)})")
        self.set_side(f"{self.T('in_queue')}: {sum(1 for j in self.queue if j['status'] in ('queued', 'active'))}")
        self._sel_none()
        self.show_page("downloads")
        self.refresh_queue_ui()
        self._pump_worker()




# ============================================================
# 5b. ANWAP (mm.anwap.media: фильмы для телефона — прямые мелкие MP4)
# ============================================================
AW_BASE = "https://mm.anwap.media"
AW_REF = AW_BASE + "/"


def aw_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": AW_REF})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def _aw_clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    for a, b in [("&quot;", '"'), ("&#039;", "'"), ("&amp;", "&"),
                 ("&laquo;", "«"), ("&raquo;", "»"), ("&nbsp;", " "),
                 ("&#151;", "—")]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def aw_search(query: str, limit: int = 20):
    q = urllib.parse.urlencode({"slv": query, "vid": 1})
    html = aw_get(AW_BASE + "/films/search/?" + q)
    blocks = [m.start() for m in re.finditer(r'<div class="my_razdel film"', html)]
    out = []
    for idx, st in enumerate(blocks):
        chunk = html[st:blocks[idx + 1] if idx + 1 < len(blocks) else st + 3000]
        href = re.search(r'href="(/films/\d+[^"]*)"', chunk)
        img = re.search(r'<img[^>]+src="([^"]+)"', chunk)
        name = re.search(r'<div class="namefilm">(.*?)</div>', chunk, re.S)
        qual = re.search(r'<span class="in green">(.*?)</span>', chunk)
        year = re.search(r'<span class="in year">(.*?)</span>', chunk)
        if not href:
            continue
        title = _aw_clean(name.group(1)) if name else href.group(1)
        poster = img.group(1) if img else ""
        if poster.startswith("/"):
            poster = AW_BASE + poster
        info = " ".join(x for x in [
            _aw_clean(qual.group(1)) if qual else "",
            _aw_clean(year.group(1)) if year else ""] if x)
        ym = re.search(r"(19|20)\d{2}", info)
        out.append({"src": "anwap", "page_url": AW_BASE + href.group(1),
                    "title": title, "sub": info, "year": ym.group(0) if ym else "",
                    "info": info, "poster": poster})
        if len(out) >= limit:
            break
    return out


def aw_page(page_url: str) -> dict:
    html = aw_get(page_url)
    if "не бот" in html.lower() and "my_razdel" not in html:
        raise RuntimeError("Anwap: проверка на бота — повторите через минуту")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    title = _aw_clean(h1.group(1)) if h1 else page_url
    title = re.sub(r"\s*смотреть онлайн.*$", "", title, flags=re.I)
    og = re.search(r'og:image" content="([^"]+)"', html)
    fid = (re.search(r"/films/(\d+)", page_url) or [None, ""])[1]
    # постер: именной prew (настоящая обложка); og:image — это GIF-скрин, запасной
    poster = AW_BASE + f"/films/prew/{fid}.jpg" if fid else ""
    if not poster and og:
        poster = og.group(1)
    if poster.startswith("/"):
        poster = AW_BASE + poster
    desc = re.search(r'meta name="description" content="([^"]+)"', html)
    # инфо-таблица: Год / Качество / Жанр / Страна / Перевод / Время
    info_rows = {}
    for m in re.finditer(r"<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", html, re.S):
        lab, val = _aw_clean(m.group(1)), _aw_clean(m.group(2))
        lab = lab.rstrip(":").strip()
        if lab and len(lab) < 30 and val:
            info_rows[lab] = val
    year = re.search(r"(19|20)\d{2}", info_rows.get("Год", "") + " " + title)
    dur = 0
    tm = re.search(r"(\d+):(\d\d):(\d\d)", info_rows.get("Время", ""))
    if tm:
        dur = int(tm.group(1)) * 3600 + int(tm.group(2)) * 60 + int(tm.group(3))
    else:
        tm = re.search(r"(\d+)\s*мин", info_rows.get("Время", ""))
        if tm:
            dur = int(tm.group(1)) * 60
    options = []
    ul = re.search(r'<ul class="tl2">(.*?)</ul>', html, re.S)
    if ul:
        for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', ul.group(1), re.S):
            label = _aw_clean(m.group(2))
            href = m.group(1)
            options.append({
                "label": label,
                "load_url": href if href.startswith("http") else AW_BASE + href,
                "size_str": (re.search(r"([\d.,]+\s*[МM][БB])", label) or [""])[0],
            })
    if not options:
        raise RuntimeError("Anwap: вариантов скачивания нет (возможно, удалено)")
    genre = info_rows.get("Жанр", "")
    country = info_rows.get("Страна", "")
    quality = info_rows.get("Качество", "")
    info_line = " • ".join(x for x in [year.group(0) if year else "", quality,
                                       genre, country] if x)
    return {"src": "anwap", "page_url": page_url, "title": title or page_url,
            "sub": info_line or options[0]["label"],
            "year": year.group(0) if year else "",
            "poster": poster,
            "description": _aw_clean(desc.group(1)) if desc else "Описание отсутствует.",
            "translators": [], "seasons": [], "episodes": [], "is_series": False,
            "options": options, "runtime": dur}


def aw_pick(options: list, quality: str = "480"):
    """Самый большой вариант ≤ запрошенного (для PSP хватает 426x320)."""
    want = int(re.search(r"\d+", quality or "480").group(0))

    def wh(o):
        m = re.search(r"(\d{2,4})\s*x\s*(\d{2,4})", o["label"])
        if m:
            return int(m.group(1)), int(m.group(2))
        return (0, 0)

    ranked = sorted(options, key=lambda o: wh(o)[0] * wh(o)[1])
    best = None
    for o in ranked:
        w, h = wh(o)
        if h and h <= want:
            best = o
    if best is None:
        mp4s = [o for o in ranked if "mp4" in o["label"].lower()]
        best = mp4s[-1] if mp4s else (ranked[-1] if ranked else None)
    if best is None:
        raise RuntimeError("Anwap: нет вариантов")
    return best


def aw_resolve(load_url: str) -> str:
    """Проход 302-цепочки до прямого файла (без скачивания тела)."""
    req = urllib.request.Request(load_url, method="HEAD",
                                 headers={"User-Agent": UA, "Referer": AW_REF})

    class _NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(_NoRedir)
    try:
        r = opener.open(req, timeout=20)
        return r.url
    except urllib.request.HTTPError as e:
        loc = e.headers.get("Location", "")
        if loc and e.code in (301, 302, 303, 307, 308):
            return loc if loc.startswith("http") else urllib.parse.urljoin(load_url, loc)
        raise RuntimeError(f"Anwap resolve HTTP {e.code}")


# ============================================================
# 6. GUI: ОБОЛОЧКА, НАВИГАЦИЯ, АНИМАЦИИ
# ============================================================
import customtkinter as ctk
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT = "#7aa2f7"
GREEN = "#9ece6a"
MUTED = "#7a83a6"
RED = "#f7768e"
YELLOW = "#e0af68"

SOURCES = [
    ("anilibria", "AniLibria", "Аниме • API"),
    ("rezka", "HDRezka", "Всё • озвучки"),
    ("kinovibe", "KinoVibe", "Фильмы • сериалы"),
    ("anwap", "Anwap", "Фильмы"),
    ("youtube", "YouTube", "Видео • трейлеры"),
]


def tween(widget, key, target, ms=180, fmt=None):
    """Плавная анимация числового параметра виджета (progress)."""
    try:
        cur = float(widget.get()) if key == "progress" else 0.0
    except Exception:
        cur = 0.0
    steps, delay = max(1, ms // 16), 16

    def step(i=1):
        v = cur + (target - cur) * (i / steps)
        try:
            if key == "progress":
                widget.set(v)
        except Exception:
            return
        if i < steps:
            widget.after(delay, lambda: step(i + 1))
    step()


class Spinner(ctk.CTkLabel):
    """Анимированный спиннер загрузки."""
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, **kw):
        super().__init__(master, text="", **kw)
        self._i = 0
        self._on = False

    def start(self, prefix=""):
        self._on = True
        self._tick(prefix)

    def stop(self):
        self._on = False
        self.configure(text="")

    def _tick(self, prefix=""):
        if not self._on:
            return
        self.configure(text=f"{prefix}{self.FRAMES[self._i % len(self.FRAMES)]}")
        self._i += 1
        self.after(90, lambda: self._tick(prefix))


class _AppBase(ctk.CTk):
    def __init__(self):
        super().__init__()
        cfg = load_config()
        self.lang_var = tk.StringVar(value=cfg.get("lang") or detect_lang())
        if self.lang_var.get() not in STR:
            self.lang_var.set("Русский")
        self.title(APP_TITLE + " — кино для PSP")
        self.geometry("1520x860")
        self.minsize(1240, 720)

        self.results = []
        self.detail = None          # нормализованная карточка текущего релиза
        self.detail_eps = []        # эпизоды для чеклиста: [{label, sub, data}]
        self.ep_vars = []
        self.queue = []             # Job-очереди (раздел 8)
        self.job_seq = 0
        self.worker_on = False
        self._bars = {}             # job_id -> (bar, displayed_frac)
        self.poster_photo = None
        self._last_frac = 0.0
        self._i18n_widgets = []
        self._pulse_i = 0

        # настройки (с восстановлением из конфига)
        self.out_var = tk.StringVar(value=cfg.get("out") or DEFAULT_OUT)
        self.preset_var = tk.StringVar(value=cfg.get("preset") or "PSP • 60 МБ (256k+64k)")
        self.aspect_var = tk.StringVar(value=cfg.get("aspect") or DEFAULT_ASPECT)
        self.q_var = tk.StringVar(value=cfg.get("quality") or "480")
        self.threads_var = tk.StringVar(value=cfg.get("threads") or "16")
        self.psp_names_var = tk.BooleanVar(value=bool(cfg.get("m4v", False)))
        self.thm_var = tk.BooleanVar(value=bool(cfg.get("thm", True)))
        self.src_var = tk.StringVar(value="rezka")
        self.psp_counter = 1
        for _v in (self.out_var, self.preset_var, self.aspect_var, self.q_var,
                   self.threads_var, self.psp_names_var, self.thm_var):
            _v.trace_add("write", lambda *_: self.save_settings())
        self.lang_var.trace_add("write", lambda *_: self.save_settings())

        os.makedirs(POSTER_CACHE, exist_ok=True)
        os.makedirs(self.out_var.get(), exist_ok=True)
        self._build_shell()
        self.apply_lang()
        self.show_page("search", animate=False)
        if not check_ffmpeg():
            messagebox.showwarning("ffmpeg", self.T("msg_no_ffmpeg"))
        self._fade_in()

    def T(self, key):
        return STR.get(self.lang_var.get(), STR["Русский"]).get(key, key)

    def st_name(self, code):
        return self.T("st_" + code)

    def ph_name(self, code):
        return self.T("ph_" + code)

    def save_settings(self):
        save_config({"lang": self.lang_var.get(), "out": self.out_var.get(),
                     "preset": self.preset_var.get(), "aspect": self.aspect_var.get(),
                     "quality": self.q_var.get(), "threads": self.threads_var.get(),
                     "m4v": bool(self.psp_names_var.get()), "thm": bool(self.thm_var.get())})

    def _fade_in(self):
        """Плавное появление окна при старте."""
        try:
            self.attributes("-alpha", 0.0)
            for i in range(1, 11):
                self.after(i * 35, lambda v=i / 10: self.attributes("-alpha", v))
        except Exception:
            pass

    # ---------- оболочка ----------
    def _build_shell(self):
        self.grid_columnconfigure(0, minsize=230)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        side = ctk.CTkFrame(self, width=230, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="🎬 PSPlay", font=ctk.CTkFont(size=24, weight="bold")).pack(
            pady=(18, 0), padx=16, anchor="w")
        self.logo_sub = ctk.CTkLabel(side, text="", font=ctk.CTkFont(size=13), text_color=MUTED)
        self.logo_sub.pack(padx=16, anchor="w", pady=(0, 14))
        self._nav_buttons = {}
        nav_wrap = ctk.CTkFrame(side, fg_color="transparent")
        nav_wrap.pack(fill="x", padx=8)
        self._indicator = ctk.CTkFrame(nav_wrap, fg_color=ACCENT, width=4, height=36,
                                       corner_radius=2)
        self._indicator.place(x=0, y=0)
        for key in ("search", "downloads", "settings"):
            b = ctk.CTkButton(nav_wrap, text="", anchor="w", fg_color="transparent",
                              height=40, font=ctk.CTkFont(size=14),
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", pady=2, padx=(10, 0))
            self._nav_buttons[key] = b
        self.side_status = ctk.CTkLabel(side, text="Готов", font=ctk.CTkFont(size=12),
                                        text_color=MUTED, wraplength=200, justify="left",
                                        anchor="w")
        self.side_status.pack(side="bottom", padx=16, pady=14, fill="x", anchor="w")
        self._pages = {}
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        for key in ("search", "downloads", "settings"):
            f = ctk.CTkFrame(wrap, fg_color="transparent")
            f.grid(row=0, column=0, sticky="nsew")
            self._pages[key] = f
        self._cur_page = ""
        self._build_search_page()
        self._build_downloads_page()
        self._build_settings_page()

    def show_page(self, key, animate=True):
        if key == self._cur_page:
            return
        self._cur_page = key
        for k, f in self._pages.items():
            if k == key:
                f.tkraise()
            else:
                pass
        # индикатор навигации едет к активной кнопке
        try:
            b = self._nav_buttons[key]
            self.update_idletasks()
            y = b.winfo_y()
            cur = self._indicator.place_info().get("y", 0) or 0
            for i in range(1, 7):
                v = float(cur) + (y - float(cur)) * i / 6
                self.after(i * 25, lambda v=v: self._indicator.place_configure(y=v))
        except Exception:
            pass

    # ---------- общие хелперы GUI ----------
    def L(self, widget, key, attr="text"):
        """Текст из словаря + регистрация для переключения языка."""
        try:
            widget.configure(**{attr: self.T(key)})
        except Exception:
            pass
        self._i18n_widgets.append((widget, key, attr))
        return widget

    def apply_lang(self):
        for widget, key, attr in list(self._i18n_widgets):
            try:
                widget.configure(**{attr: self.T(key)})
            except Exception:
                pass
        try:
            self.logo_sub.configure(text=self.T("tagline"))
            for k, b in self._nav_buttons.items():
                b.configure(text=self.T("nav_" + k))
            for card in getattr(self, "_job_cards", {}).values():
                card["b_cancel"].configure(text=self.T("job_cancel"))
                card["b_rm"].configure(text=self.T("job_remove"))
                card["b_open"].configure(text=self.T("job_folder"))
            if not getattr(self, "detail", None):
                self.title_lbl.configure(text=self.T("choose_hint"))
                self.meta_lbl.configure(text=self.T("meta_ph"))
                self.poster_lbl.configure(text=self.T("poster_ph"))
                try:
                    self.desc_box.configure(state="normal")
                    self.desc_box.delete("1.0", "end")
                    self.desc_box.insert("end", self.T("desc_ph"))
                    self.desc_box.configure(state="disabled")
                except Exception:
                    pass
            self._check_ff()
            self.refresh_queue_ui()
        except Exception:
            pass
        self.save_settings()

    def logln(self, s):
        try:
            self.glog.configure(state="normal")
            self.glog.insert("end", s + "\n")
            self.glog.see("end")
            self.glog.configure(state="disabled")
        except Exception:
            pass

    def run_bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _ui(self, fn):
        self.after(0, fn)

    def set_side(self, s):
        self.side_status.configure(text=s)

# ============================================================
# 7. GUI: СТРАНИЦА ПОИСКА
# ============================================================
def _poster_cache_path(rid):
    return os.path.join(POSTER_CACHE, f"{str(rid).replace('/', '_')}_full.jpg")


# ============================================================
class App(_AppBase, AppSearchMixin):
    pass


# 8. GUI: ЗАГРУЗКИ (очередь) + НАСТРОЙКИ
# ============================================================
STATUS_COLORS = {"queued": MUTED, "active": ACCENT, "converting": "#bb9af7",
                 "done": GREEN, "error": RED, "canceled": MUTED}
STATUS_NAMES = {"queued": "в очереди", "active": "качаю", "converting": "конвертирую",
                "done": "готово", "error": "ошибка", "canceled": "отменено"}


def _build_downloads_page(self):
    pg = self._pages["downloads"]
    pg.grid_columnconfigure(0, weight=1)
    pg.grid_rowconfigure(1, weight=1)
    head = ctk.CTkFrame(pg, fg_color="transparent")
    head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    self.dl_title_lbl = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=18, weight="bold"))
    self.dl_title_lbl.pack(side="left")
    self.L(self.dl_title_lbl, "dl_title")
    self.q_count = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=12), text_color=MUTED)
    self.q_count.pack(side="left", padx=10)
    self.cancel_all_btn = ctk.CTkButton(head, text="", width=130, fg_color="transparent",
                  border_width=1, command=self.cancel_all)
    self.cancel_all_btn.pack(side="right", padx=(6, 0))
    self.L(self.cancel_all_btn, "cancel_all")
    self.clear_done_btn = ctk.CTkButton(head, text="", width=150, fg_color="transparent",
                  border_width=1, command=self.clear_done)
    self.clear_done_btn.pack(side="right")
    self.L(self.clear_done_btn, "clear_done")
    self.jobs_scroll = ctk.CTkScrollableFrame(pg, label_text="")
    self.jobs_scroll.grid(row=1, column=0, sticky="nsew")
    self.glog = ctk.CTkTextbox(pg, height=130, font=ctk.CTkFont(family="Consolas", size=12))
    self.glog.grid(row=2, column=0, sticky="ew", pady=(8, 0))
    self.glog.configure(state="disabled")
    self._job_cards = {}
    self.after(400, self._refresh_tick)


def _job_card(self, job):
    f = ctk.CTkFrame(self.jobs_scroll)
    f.pack(fill="x", pady=4, padx=2)
    top = ctk.CTkFrame(f, fg_color="transparent")
    top.pack(fill="x", padx=10, pady=(8, 0))
    title = ctk.CTkLabel(top, text=f"{job['title'][:70]}", font=ctk.CTkFont(size=13, weight="bold"),
                         anchor="w")
    title.pack(side="left", fill="x", expand=True)
    badge = ctk.CTkLabel(top, text=job["src"], font=ctk.CTkFont(size=11),
                         text_color=MUTED)
    badge.pack(side="left", padx=8)
    status = ctk.CTkLabel(top, text="в очереди", font=ctk.CTkFont(size=12, weight="bold"),
                          width=110, anchor="e")
    status.pack(side="right")
    sub = ctk.CTkLabel(f, text=job["ep_label"], font=ctk.CTkFont(size=12),
                       text_color=MUTED, anchor="w")
    sub.pack(fill="x", padx=10)
    bar = ctk.CTkProgressBar(f)
    bar.pack(fill="x", padx=10, pady=4)
    bar.set(0)
    info = ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=12), text_color=MUTED, anchor="w")
    info.pack(fill="x", padx=10)
    msg = ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=11), text_color=MUTED,
                       anchor="w", wraplength=900, justify="left")
    msg.pack(fill="x", padx=10, pady=(0, 4))
    btns = ctk.CTkFrame(f, fg_color="transparent")
    btns.pack(fill="x", padx=10, pady=(0, 8))
    b_cancel = ctk.CTkButton(btns, text="✖ Отмена", width=90, fg_color="transparent",
                             border_width=1,
                             command=lambda j=job: self.cancel_job(j))
    b_cancel.pack(side="left")
    b_rm = ctk.CTkButton(btns, text="🗑 Убрать", width=90, fg_color="transparent",
                         border_width=1, command=lambda j=job: self.remove_job(j))
    b_rm.pack(side="left", padx=6)
    b_open = ctk.CTkButton(btns, text="📂 Папка", width=90, fg_color="transparent",
                           border_width=1, command=lambda j=job: self.open_job_folder(j))
    b_open.pack(side="left")
    card = {"frame": f, "title": title, "status": status, "bar": bar,
            "info": info, "msg": msg, "shown": 0.0,
            "b_cancel": b_cancel, "b_rm": b_rm, "b_open": b_open}
    self._job_cards[job["id"]] = card
    return card


def refresh_queue_ui(self):
    for job in self.queue:
        card = self._job_cards.get(job["id"]) or self._job_card(job)
        st = job["status"]
        card["status"].configure(text=self.st_name(st),
                                 text_color=STATUS_COLORS.get(st, MUTED))
        card["b_cancel"].configure(text=self.T("job_cancel"))
        card["b_rm"].configure(text=self.T("job_remove"))
        card["b_open"].configure(text=self.T("job_folder"))
        shown = card["shown"] + (job["frac"] - card["shown"]) * 0.35
        card["shown"] = shown
        card["bar"].set(shown)
        parts = [self.ph_name(job.get("phase", ""))]
        if st in ("active", "converting"):
            parts.append(f"{job['frac'] * 100:.0f}%")
            if job.get("speed"):
                parts.append(job["speed"])
            if job.get("eta"):
                parts.append(self.T("eta_word") + " " + job["eta"])
            if job.get("total"):
                parts.append(f"{fmt_size(job.get('done', 0))} / {fmt_size(job['total'])}")
        card["info"].configure(text=" • ".join(p for p in parts if p))
        if job.get("msg"):
            card["msg"].configure(text=job["msg"][:220])
        active = st in ("queued", "active", "converting")
        card["b_cancel"].configure(state="normal" if active else "disabled")
        card["b_rm"].configure(state="disabled" if st == "active" else "normal")
    nq = sum(1 for j in self.queue if j["status"] in ("queued", "active", "converting"))
    nd = sum(1 for j in self.queue if j["status"] == "done")
    # пульс-индикатор активности в сайдбаре
    try:
        if nq:
            self._pulse_i = (self._pulse_i + 1) % 4
            dots = ("●○○", "○●○", "○○●", "○●○")[self._pulse_i]
            self.set_side(f"{dots} {self.T('in_queue')}: {nq}")
        else:
            self.set_side(self.T("ready"))
        self.q_count.configure(
            text=f"{self.T('q_active')}: {nq} • {self.T('q_done')}: {nd} • "
                 f"{self.T('q_total')}: {len(self.queue)}")
    except Exception:
        pass


def _refresh_tick(self):
    try:
        if getattr(self, "_job_cards", None) is not None and self.queue:
            self.refresh_queue_ui()
    except Exception:
        pass
    self.after(400, self._refresh_tick)


def cancel_job(self, job):
    job["cancel"] = True
    if job["status"] == "queued":
        job["status"] = "canceled"
        job["msg"] = self.T("cancel_by_user")
    self.refresh_queue_ui()


def cancel_all(self):
    for j in self.queue:
        if j["status"] in ("queued", "active", "converting"):
            j["cancel"] = True
            if j["status"] == "queued":
                j["status"] = "canceled"
    self.logln(self.T("cancel_queue"))
    self.refresh_queue_ui()


def remove_job(self, job):
    if job["status"] == "active":
        return
    card = self._job_cards.pop(job["id"], None)
    if card:
        try:
            card["frame"].destroy()
        except Exception:
            pass
    try:
        self.queue.remove(job)
    except ValueError:
        pass
    self.refresh_queue_ui()


def clear_done(self):
    for j in [x for x in self.queue if x["status"] in ("done", "error", "canceled")]:
        self.remove_job(j)


def open_job_folder(self, job):
    path = job.get("out") or self.out_var.get()
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(folder)
        else:
            subprocess.run(["xdg-open", folder])
    except Exception as e:
        self.logln(f"Не открыть папку: {e}")


# ---------- воркер очереди ----------
def _pump_worker(self):
    if self.worker_on:
        return
    if not any(j["status"] == "queued" for j in self.queue):
        return
    self.worker_on = True
    self.run_bg(self._worker_loop)


def _worker_loop(self):
    while True:
        job = next((j for j in self.queue if j["status"] == "queued"), None)
        if job is None:
            break
        job["status"] = "active"
        job["cancel"] = False
        try:
            self._do_job(job)
        except Exception as e:
            job["status"] = "error"
            job["msg"] = f"✗ {str(e)[:200]}"
            self._ui(lambda _j=job, _e=e: self.logln(f"[{_j['title'][:40]}] Ошибка: {_e}"))
    self.worker_on = False
    self._ui(lambda: self.refresh_queue_ui())


class _Prog:
    """Прогресс с живой скоростью/ETA для колбэков (потоки + ffmpeg)."""

    def __init__(self, job, ui_set, base=0.0, span=1.0, total_bytes=0):
        self.job, self.ui_set = job, ui_set
        self.base, self.span = base, span
        self.total = total_bytes
        self.t0 = time.time()
        self.last_ui = 0.0

    def dl(self, frac):
        now = time.time()
        f = self.base + frac * self.span
        self.job["frac"] = f
        if self.total:
            done = frac * self.total
            self.job["done"] = done
            avg = done / max(now - self.t0, 0.001)
            self.job["speed"] = fmt_speed(avg)
            self.job["eta"] = fmt_eta((self.total - done) / avg) if avg > 0 else ""
        if now - self.last_ui > 0.25:
            self.last_ui = now
            self.ui_set()

    def enc(self, frac, speed, t, dur):
        f = self.base + frac * self.span
        self.job["frac"] = f
        self.job["phase"] = "convert"
        try:
            spd = float((speed or "0x").rstrip("x"))
            left = (dur - t) / spd if spd > 0 else (dur - t)
        except Exception:
            left = dur - t
            spd = 0
        self.job["speed"] = f"{speed}" if speed else ""
        self.job["eta"] = fmt_eta(left)
        now = time.time()
        if now - self.last_ui > 0.25 or frac >= 1.0:
            self.last_ui = now
            self.ui_set()


def _job_out_path(self, job) -> str:
    outdir = self.out_var.get()
    os.makedirs(outdir, exist_ok=True)
    ep = job["ep"]
    base = sanitize(job["title"])
    if self.psp_names_var.get():
        name = f"M4V{self.psp_counter:05d}.MP4"
        self.psp_counter += 1
        return os.path.join(outdir, name)
    if ep.get("is_film") or job.get("detail", {}).get("kind") == "film":
        return os.path.join(outdir, f"{base}.mp4")
    folder = os.path.join(outdir, base)
    if (job.get("detail", {}).get("seasons_n") or 1) > 1:
        folder = os.path.join(folder, f"{self.T('season_word')} {ep.get('season', 1)}")
    os.makedirs(folder, exist_ok=True)
    pad = 3 if (ep.get("ordinal") or 0) >= 100 else 2
    return os.path.join(folder, f"{self.T('ep_word')} {ep.get('ordinal', 1):0{pad}d} - {base}.mp4")


def _finish_convert(self, job, tmp, out, dur, aspect):
    """Конвертация tmp -> out с прогрессом. Возвращает (ok, msg)."""
    prog = _Prog(job, lambda: self.refresh_queue_ui(), base=job.get("_enc_base", 0.55),
                 span=1.0 - job.get("_enc_base", 0.55))

    def cb(frac, speed, t, d=dur):
        if frac - getattr(cb, "last", 0.0) < 0.02 and frac < 1.0:
            return
        cb.last = frac
        prog.enc(frac, speed, t, d)
    cb.last = 0.0
    return download_convert(tmp, out, PRESETS.get(self.preset_var.get(),
                                                  list(PRESETS.values())[0]),
                            duration_sec=int(dur),
                            on_progress=cb,
                            cancel_flag=lambda: job["cancel"],
                            aspect=aspect)


def _do_job(self, job):
    src = job["src"]
    outdir = self.out_var.get()
    os.makedirs(outdir, exist_ok=True)
    out = self._job_out_path(job)
    job["out"] = out
    job["msg"] = ""
    preset = PRESETS.get(self.preset_var.get(), list(PRESETS.values())[0])
    aspect = self.aspect_var.get()
    quality = self.q_var.get()
    threads = int(self.threads_var.get() or 16)
    tmpdir = TMP_DIR
    os.makedirs(tmpdir, exist_ok=True)
    ui = lambda: self._ui(lambda: self.refresh_queue_ui())
    if src == "anilibria":
        self._do_ani(job, out, preset, aspect, quality, ui)
    elif src == "rezka":
        self._do_rezka(job, out, preset, aspect, quality, threads, tmpdir, ui)
    elif src == "kinovibe":
        self._do_kv(job, out, preset, aspect, threads, tmpdir, ui)
    elif src == "anwap":
        self._do_aw(job, out, preset, aspect, threads, tmpdir, ui)
    elif src == "youtube":
        self._do_yt(job, out, preset, aspect, tmpdir, ui)
    else:
        raise RuntimeError(f"неизвестный источник {src}")


def _do_ani(self, job, out, preset, aspect, quality, ui):
    ep = job["ep"]
    rid = job["detail"]["id"]
    job["phase"] = "links"
    ui()
    msg, hls = "", None
    for attempt in range(1, 4):
        if job["cancel"]:
            raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
        try:
            m = ani_refresh_hls(rid)
            live = m.get(ep["ordinal"], ep.get("hls") or {})
            hls, used = ani_pick_hls(live, quality)
            if not hls:
                raise RuntimeError("нет HLS-ссылки")
            break
        except Exception as e:
            msg = str(e)[:150]
            job["msg"] = f"Ссылки: попытка {attempt}/3 ({msg})"
            ui()
            time.sleep(1 + attempt)
    if not hls:
        raise RuntimeError(f"Нет потоков: {msg}")
    job["phase"] = "convert"
    for attempt in range(1, 4):
        if job["cancel"]:
            raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
        prog = _Prog(job, ui)
        ok, m = download_convert(hls, out, preset, duration_sec=ep.get("duration") or 1440,
                                 on_progress=lambda f, s, t, d=ep.get("duration") or 1440:
                                 prog.enc(f, s, t, d),
                                 cancel_flag=lambda: job["cancel"], aspect=aspect)
        if ok:
            return self._job_done(job, out)
        job["msg"] = f"Попытка {attempt}/3: {m[:150]}"
        ui()
    raise RuntimeError(job["msg"] or "ffmpeg не справился")


def _do_rezka(self, job, out, preset, aspect, quality, threads, tmpdir, ui):
    import time as _t
    ep = job["ep"]
    d = job["detail"]
    # серверу нужен translator_id, а не имя: резолвим по словарю релиза
    tr_name = job.get("translator") or ""
    tr = next((t["id"] for t in d.get("translators", []) if t["name"] == tr_name), "")
    if not tr:
        tr = ((d.get("translators", [{}]) or [{}])[0] or {}).get("id", "")
    if not tr:
        tr = (d.get("default") or {}).get("translator_id", "")
    if not tr:
        raise RuntimeError("Нет ID озвучки для get_stream")
    season = ep.get("season", 1)
    number = ep.get("episode", ep.get("ordinal", 1))
    is_series = d.get("kind") != "film"
    job["phase"] = "links"
    ui()
    final = label = size = msg = None
    for rnd in (1, 2):
        if job["cancel"]:
            raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
        # свежая сессия + просмотр страницы каждый круг: иначе резка отвечает
        # «Время сессии истекло» на get_stream
        try:
            sess = fresh_session(d["page_url"])
        except Exception as e:
            msg = str(e)[:150]
            job["msg"] = f"Сессия: {msg}"
            ui()
            continue
        streams = None
        for attempt in (1, 2, 3):
            try:
                streams = get_stream(sess, d["page_url"], d["id"], tr,
                                     season, number, is_series)
                break
            except Exception as e:
                msg = str(e)[:150]
                job["msg"] = f"Ссылки: попытка {attempt}/3 ({msg})"
                ui()
                _t.sleep(1 + attempt)
        if not streams:
            continue
        try:
            final, label, size = pick_playable(sess, streams, quality, d["page_url"])
            break
        except Exception as e:
            msg = str(e)[:200]
            job["msg"] = f"CDN круг {rnd}/2: {msg}"
            ui()
    if not final:
        raise RuntimeError(f"Нет потоков: {msg}")
    job["phase"] = "download"
    job["total"] = size or 0
    ui()
    tmp = os.path.join(tmpdir, f"rz_{d['id']}_{season}_{number}.mp4")
    prog = _Prog(job, ui, base=0.0, span=0.55, total_bytes=size or 0)
    download_mp4(sess, final, d["page_url"], tmp,
                 on_progress=prog.dl, cancel=lambda: job["cancel"])
    dur = int(probe_duration(tmp) or ep.get("duration") or 1440)
    job["_enc_base"] = 0.55
    job["phase"] = "convert"
    ok, m = self._finish_convert(job, tmp, out, dur, aspect)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    if not ok or not os.path.exists(out):
        raise RuntimeError(f"Конвертация: {m}")
    self._job_done(job, out)


def _do_kv(self, job, out, preset, aspect, threads, tmpdir, ui):
    import time as _t
    ep = job["ep"]
    d = job["detail"]
    referer = d.get("page_url", KV_BASE + "/")
    # ссылки kvb.cool протухают: перед скачиванием обновляем страницу (до 2 кругов)
    url, size, msg = "", 0, ""
    for rnd in (1, 2):
        if job["cancel"]:
            raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
        try:
            fresh = kv_page(referer)
            if ep.get("is_film") or d.get("kind") == "film":
                url = fresh.get("file", "")
            else:
                url = next((e.get("file", "") for e in fresh.get("episodes", [])
                            if e.get("episode") == ep.get("episode")), "")
            url = url or ep.get("file") or d.get("file", "")
            if not url:
                raise RuntimeError(self.T("no_link") + " KinoVibe")
            size = kv_size(url, referer)
            if size is None:
                raise RuntimeError("HTTP 404: файл удалён или ссылка протухла")
            break
        except Exception as e:
            msg = str(e)[:180]
            job["msg"] = f"Ссылки: круг {rnd}/2 ({msg})"
            ui()
            _t.sleep(1 + rnd)
    else:
        raise RuntimeError(msg or "нет ссылки")
    if not url or size is None:
        raise RuntimeError(msg or "нет ссылки")
    job["phase"] = "download"
    job["total"] = size or 0
    ui()
    tmp = os.path.join(tmpdir, f"kv_{abs(hash(url)) % 10**10}.mp4")
    prog = _Prog(job, ui, base=0.0, span=0.55, total_bytes=size or 0)
    kv_download(url, referer, tmp, size=size, threads=threads,
                on_progress=prog.dl, cancel=lambda: job["cancel"])
    dur = int(probe_duration(tmp) or ep.get("duration") or 1440)
    job["_enc_base"] = 0.55
    job["phase"] = "convert"
    ok, m = self._finish_convert(job, tmp, out, dur, aspect)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    if not ok or not os.path.exists(out):
        raise RuntimeError(f"Конвертация: {m}")
    self._job_done(job, out)


def _do_aw(self, job, out, preset, aspect, threads, tmpdir, ui):
    import time as _t
    ep = job["ep"]
    d = job["detail"]
    referer = d.get("page_url", AW_BASE + "/")
    quality = self.q_var.get()
    url, size, msg = "", 0, ""
    for rnd in (1, 2):
        if job["cancel"]:
            raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
        try:
            info = aw_page(referer)
            opt = aw_pick(info["options"], quality)
            final = aw_resolve(opt["load_url"])
            size = kv_size(final, referer)
            if size is None:
                raise RuntimeError("HTTP 404: файл удалён или ссылка протухла")
            url = final
            job["msg"] = f"{opt['label'][:60]} ({fmt_size(size)})"
            ui()
            break
        except Exception as e:
            msg = str(e)[:180]
            job["msg"] = f"Ссылки: круг {rnd}/2 ({msg})"
            ui()
            _t.sleep(1 + rnd)
    if not url or size is None:
        raise RuntimeError(msg or "нет ссылки")
    job["phase"] = "download"
    job["total"] = size or 0
    ui()
    tmp = os.path.join(tmpdir, f"aw_{abs(hash(url)) % 10**10}.mp4")
    prog = _Prog(job, ui, base=0.0, span=0.55, total_bytes=size or 0)
    kv_download(url, referer, tmp, size=size, threads=threads,
                on_progress=prog.dl, cancel=lambda: job["cancel"])
    dur = int(probe_duration(tmp) or 5400)
    job["_enc_base"] = 0.55
    job["phase"] = "convert"
    ok, m = self._finish_convert(job, tmp, out, dur, aspect)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    if not ok or not os.path.exists(out):
        raise RuntimeError(f"Конвертация: {m}")
    self._job_done(job, out)


def _do_yt(self, job, out, preset, aspect, tmpdir, ui):
    ep = job["ep"]
    url = job.get("detail", {}).get("url") or ep.get("url", "")
    if not url:
        raise RuntimeError(self.T("no_link") + " YouTube")
    job["phase"] = "download"
    ui()
    base = os.path.join(tmpdir, f"yt_{job['id']}.%(ext)s")
    prog = _Prog(job, ui, base=0.0, span=0.6,
                 total_bytes=(ep.get("duration") or 600) * 90000)
    try:
        tmp = yt_download(url, base, on_progress=prog.dl,
                          cancel=lambda: job["cancel"])
    except YTCancelled:
        raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
    dur = int(probe_duration(tmp) or ep.get("duration") or 600)
    job["_enc_base"] = 0.6
    job["phase"] = "convert"
    ok, m = self._finish_convert(job, tmp, out, dur, aspect)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    if not ok or not os.path.exists(out):
        raise RuntimeError(f"Конвертация: {m}")
    self._job_done(job, out)


def _job_done(self, job, out):
    if job["cancel"]:
        raise RuntimeError(self.T("cancel_by_user") if "self" in dir() else "cancelled")
    job["status"] = "done"
    job["frac"] = 1.0
    job["phase"] = "done"
    job["speed"] = ""
    job["eta"] = ""
    real = os.path.getsize(out) // (1024 * 1024) if os.path.exists(out) else 0
    job["msg"] = f"✓ {self.T('st_done')} ({real} МБ): {out}"
    if self.thm_var.get() or self.psp_names_var.get():
        thm = os.path.splitext(out)[0] + ".THM"
        if make_thumbnail(out, thm):
            job["msg"] += " + THM"
    self._ui(lambda: (self.logln(f"[{job['title'][:40]}] {job['msg']}"),
                      self.refresh_queue_ui()))


# ---------- настройки ----------
def _build_settings_page(self):
    pg = self._pages["settings"]
    pg.grid_columnconfigure(1, weight=1)
    self.set_title_lbl = ctk.CTkLabel(pg, text="", font=ctk.CTkFont(size=18, weight="bold"))
    self.set_title_lbl.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
    self.L(self.set_title_lbl, "set_title")
    r = 1
    self._set_rows = {}

    def row(key):
        nonlocal r
        lb = ctk.CTkLabel(pg, text="", font=ctk.CTkFont(size=13))
        lb.grid(row=r, column=0, sticky="w", pady=6, padx=(0, 12))
        self._set_rows[key] = lb
        self.L(lb, key)
        fr = ctk.CTkFrame(pg, fg_color="transparent")
        fr.grid(row=r, column=1, sticky="ew", pady=6)
        r += 1
        return fr
    fr = row("set_out")
    ctk.CTkEntry(fr, textvariable=self.out_var, width=420).pack(side="left")
    ctk.CTkButton(fr, text="…", width=40, command=self.on_browse).pack(side="left", padx=6)
    fr = row("set_preset")
    ctk.CTkOptionMenu(fr, variable=self.preset_var, values=list(PRESETS.keys()),
                      width=280).pack(side="left")
    fr = row("set_aspect")
    ctk.CTkOptionMenu(fr, variable=self.aspect_var, values=list(ASPECT_MODES.keys()),
                      width=280).pack(side="left")
    fr = row("set_lang")
    ctk.CTkOptionMenu(fr, variable=self.lang_var, values=LANGS, width=200,
                      command=lambda _: self.apply_lang()).pack(side="left")
    fr = row("set_quality")
    ctk.CTkSegmentedButton(fr, values=["480", "720", "1080"], variable=self.q_var).pack(side="left")
    self.set_quality_hint = ctk.CTkLabel(fr, text="", text_color=MUTED,
                                         font=ctk.CTkFont(size=12))
    self.set_quality_hint.pack(side="left", padx=10)
    self.L(self.set_quality_hint, "set_quality_hint")
    fr = row("set_threads")
    ctk.CTkSegmentedButton(fr, values=["8", "16", "24"], variable=self.threads_var).pack(side="left")
    self.set_threads_hint = ctk.CTkLabel(fr, text="", text_color=MUTED,
                                         font=ctk.CTkFont(size=12))
    self.set_threads_hint.pack(side="left", padx=10)
    self.L(self.set_threads_hint, "set_threads_hint")
    fr = row("set_files")
    self.thm_cb = ctk.CTkCheckBox(fr, text="", variable=self.thm_var)
    self.thm_cb.pack(side="left")
    self.L(self.thm_cb, "set_thm")
    self.m4v_cb = ctk.CTkCheckBox(fr, text="", variable=self.psp_names_var)
    self.m4v_cb.pack(side="left", padx=16)
    self.L(self.m4v_cb, "set_m4v")
    fr = row("set_ffmpeg")
    self.ff_lbl = ctk.CTkLabel(fr, text="", font=ctk.CTkFont(size=12))
    self.ff_lbl.pack(side="left")
    self.check_ff_btn = ctk.CTkButton(fr, text="", width=110, command=self._check_ff)
    self.check_ff_btn.pack(side="left", padx=10)
    self.L(self.check_ff_btn, "set_check")
    fr = row("set_misc")
    self.open_out_btn = ctk.CTkButton(fr, text="", width=210,
                  command=lambda: self.open_job_folder({"out": self.out_var.get()}))
    self.open_out_btn.pack(side="left")
    self.L(self.open_out_btn, "set_open_out")
    self.clear_cache_btn = ctk.CTkButton(fr, text="", width=150, fg_color="transparent",
                  border_width=1, command=self._clear_posters)
    self.clear_cache_btn.pack(side="left", padx=10)
    self.L(self.clear_cache_btn, "set_clear_cache")
    self._check_ff()


def on_browse(self):
    d = filedialog.askdirectory(initialdir=self.out_var.get())
    if d:
        self.out_var.set(d)


def _check_ff(self):
    p = check_ffmpeg()
    try:
        self.ff_lbl.configure(
            text=f"{self.T('ff_found')}: {p[:80]}" if p else self.T("ff_missing"),
            text_color=GREEN if p else RED)
    except Exception:
        pass


def _clear_posters(self):
    n = 0
    try:
        for f in os.listdir(POSTER_CACHE):
            os.remove(os.path.join(POSTER_CACHE, f))
            n += 1
    except Exception as e:
        self.logln(f"Cache: {e}")
    self.logln(f"{self.T('cache_cleared')} ({n} {self.T('files_word')})")


for _name in ["_build_downloads_page", "_job_card", "refresh_queue_ui", "_refresh_tick",
              "cancel_job", "cancel_all", "remove_job", "clear_done", "open_job_folder",
              "_pump_worker", "_worker_loop", "_job_out_path", "_finish_convert",
              "_do_job", "_do_ani", "_do_rezka", "_do_kv", "_do_aw", "_do_yt", "_job_done",
              "_build_settings_page", "on_browse", "_check_ff", "_clear_posters"]:
    setattr(App, _name, locals()[_name])

if __name__ == "__main__":
    App().mainloop()




