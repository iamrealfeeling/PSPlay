<div align="center">

# 🎬 PSPlay

### *Pocket cinema for PSP*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PSP](https://img.shields.io/badge/PSP-1000%20%7C%202000%20%7C%203000%20%7C%20Go-red)](https://en.wikipedia.org/wiki/PlayStation_Portable)

[🇺🇦 Українська](#-українська) • [🇷🇺 Русский](#-русский) • [en English](#-english)

</div>

---

## ru Русский

**PSPlay** — качалка кино в формате PSP с четырьмя источниками, живой очередью
загрузок и тёмным анимированным интерфейсом на трёх языках.

### ✨ Возможности

| | |
|---|---|
| 🎞 **4 источника** | AniLibria (API) • HDRezka • KinoVibe • YouTube |
| 📺 **Всё подряд** | фильмы, сериалы, мультфильмы, аниме, трейлеры |
| 📥 **Очередь загрузок** | скорость, ETA, прогресс, отмена, ретраи, лог |
| 🖥 **3 страницы** | Поиск • Загрузки • Настройки + анимации |
| 🌍 **3 языка** | Українська • Русский • English (автоопределение + конфиг) |
| 📦 **Один .exe** | весь код в `psp_downloader.py`, сборка одним батником |

### 🚀 Быстрый старт

```bat
pip install -r requirements.txt
python psp_downloader.py
```

Нужен `ffmpeg` в PATH ([gyan.dev](https://www.gyan.dev/ffmpeg/builds/)).
Для `.exe`: запусти **`build_exe.bat`** → получишь `dist\PSPlay.exe`.

> ⏳ Первый запуск exe занимает 2–3 минуты (распаковка + проверка Defender) —
> окно появится не сразу, это нормально.

### 🎯 Как пользоваться

1. Введи название → **Найти** (источник переключается сверху).
2. Кликни карточку → постер, описание, озвучки/сезоны.
3. Отметь серии → **➕ В очередь**.
4. Страница **Загрузки**: смотри скорость, ETA и прогресс. Готово? Копируй в `X:/VIDEO/` на PSP.

### ⚙ Выходной формат

`MP4 480x272 • H.264 Baseline L3.0 • AAC` — играет на PSP-1000/2000/3000/Go/Vita.

| Пресет | ~24 мин |
|---|---|
| PSP • 60 МБ *(по умолчанию)* | ~58 МБ |
| PSP • 85 МБ | ~85 МБ |
| PSP • 120 МБ | ~118 МБ |

Фильм 169 мин ≈ 410 МБ. Качество источника `480` — оптимум для экрана PSP.

### ❓ FAQ

**Качается медленно?** CDN режут скорость — качаем в 16 потоков (~200 КБ/с),
прогресс показывает живую скорость и ETA. Фильм лучше брать в 360p/480p.

**HDRezka не открывается у провайдера?** Встроены обход DNS-блокировки (DoH)
и решение Anubis-капчи — работает даже из сетей с блокировкой.

---

## ua Українська

**PSPlay** — завантажувач кіно у форматі PSP: чотири джерела, жива черга
завантажень і темний анімований інтерфейс трьома мовами.

- 🎞 **4 джерела:** AniLibria • HDRezka • KinoVibe • YouTube
- 📥 **Черга:** швидкість, ETA, прогрес, повтори, лог
- 🌍 **Мова:** Українська / Русский / English (автовизначення, зберігається)
- 📦 **Один .exe:** `build_exe.bat` → `dist\PSPlay.exe`

Запуск: `pip install -r requirements.txt` → `python psp_downloader.py`
(потрібен `ffmpeg` у PATH). Файли копіюй у `X:/VIDEO/` на PSP.

---

## en English

**PSPlay** — pocket cinema for PSP: four sources, live download queue,
dark animated UI in three languages.

- 🎞 **4 sources:** AniLibria • HDRezka • KinoVibe • YouTube
- 📥 **Queue:** speed, ETA, progress, retries, log
- 🌍 **Languages:** Українська / Русский / English (auto-detect, saved)
- 📦 **Single .exe:** `build_exe.bat` → `dist\PSPlay.exe`

Run: `pip install -r requirements.txt` → `python psp_downloader.py`
(requires `ffmpeg` in PATH). Copy files to `X:/VIDEO/` on your PSP.

---

<div align="center">

**Выход / Вихід / Output:** `MP4 480x272 • H.264 Baseline • AAC` 📼

*Сделано для тех, у кого PSP до сих пор жива.* 💜

</div>
