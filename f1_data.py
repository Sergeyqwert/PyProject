import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import time
import re

WIKI_BASE = "https://en.wikipedia.org"


def get_wiki_soup(url: str) -> BeautifulSoup:
    """
    Делает GET-запрос к указанному URL и возвращает BeautifulSoup-объект страницы.
    Парсер — встроенный 'html.parser'.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/your-repo)"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_available_seasons() -> list[int]:
    """
    Возвращает все сезоны Формулы-1, начиная с 1950-го по текущий год (включительно),
    отсортированные по убыванию (чтобы самые свежие шли первыми).
    """
    current = datetime.now().year
    return list(range(current, 1949, -1))


def normalize_race_link(season: int, race_name: str, href: str) -> str:
    """
    Если href (например, "/wiki/Bahrain_Grand_Prix") не содержит "{season}_",
    то строим ссылку как "/wiki/{season}_{Race_Name}", 
    заменяя пробелы на "_" и убирая символы «’». Иначе возвращаем href 그대로.
    """
    if href.startswith("/wiki/") and f"/wiki/{season}_" not in href:
        cleaned_name = race_name.replace(" ", "_").replace("’", "")
        return f"/wiki/{season}_{cleaned_name}"
    return href


def parse_date_cell(date_text: str, season: int) -> tuple[str, date | None]:
    """
    Извлекает из строки date_text (например, "2–4 March" или "16 March 2025" или "2025-03-02")
    нормализованную строку date_norm ("YYYY-MM-DD" или оригинал) и объект date_obj, если удалось распознать.

    Алгоритм:
     1. Если в строке уже есть формат "YYYY-MM-DD", попробовать распарсить.
     2. Иначе ищем все вхождения "<день> <месяц>" с помощью regex, берём последнее и добавляем год.
     3. Если удалось распарсить как "%d %B %Y" → возвращаем date_obj.
     4. Иначе date_obj = None, date_norm = оригинальный date_text.
    """
    date_norm = date_text
    date_obj = None

    # 1. Попробуем «YYYY-MM-DD»
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_text):
        try:
            dt2 = datetime.strptime(date_text, "%Y-%m-%d")
            return date_text, dt2.date()
        except ValueError:
            pass

    # 2. Ищем все вхождения "число месяц" (например, "2 March", "4 March")
    #    с учётом того, что может быть диапазон "2–4 March"
    matches = re.findall(r"(\d{1,2}\s+[A-Za-z]+)", date_text)
    if matches:
        # Берём последнее вхождение (обычно это «конечная дата» из диапазона)
        last = matches[-1]  # e.g. "4 March"
        combo = f"{last} {season}"
        try:
            dt = datetime.strptime(combo, "%d %B %Y")
            date_obj = dt.date()
            date_norm = date_obj.strftime("%Y-%m-%d")
            return date_norm, date_obj
        except ValueError:
            date_obj = None

    # 3. Если ни одно не сработало, пытаемся «средний вариант» – просто найти «%d %B %Y» прямо
    try:
        dt = datetime.strptime(date_text, "%d %B %Y")
        date_obj = dt.date()
        date_norm = date_obj.strftime("%Y-%m-%d")
        return date_norm, date_obj
    except ValueError:
        pass

    # 4. Не удалось распознать → возвращаем оригинал и None
    return date_norm, None


def get_races(season: int) -> list[dict]:
    """
    Парсит страницу "{season}_Formula_One_World_Championship" и извлекает список гонок:
      [
        {
          "round": int,
          "race_name": str,
          "date_str": str,       # нормализованная строка "YYYY-MM-DD" или оригинал
          "link": str,           # относительный путь вроде "/wiki/2025_Bahrain_Grand_Prix"
          "date_obj": datetime.date | None
        },
        ...
      ]
    Сортирует по возрастанию round и возвращает.
    """
    url = f"{WIKI_BASE}/wiki/{season}_Formula_One_World_Championship"
    try:
        soup = get_wiki_soup(url)
    except requests.RequestException as e:
        print(f"⚠️ Не удалось загрузить страницу чемпионата {season}: {e}")
        return []

    # Ищем таблицу, где в заголовке есть "Round" и "Grand Prix"
    target_table = None
    for tbl in soup.find_all("table", class_="wikitable"):
        first_tr = tbl.find("tr")
        if not first_tr:
            continue
        headers = [th.get_text(strip=True) for th in first_tr.find_all("th")]
        if any("Round" in h for h in headers) and any("Grand Prix" in h for h in headers):
            target_table = tbl
            break

    if target_table is None:
        print(f"⚠️ Не удалось найти таблицу расписания на Википедии для сезона {season}")
        return []

    races = []
    for row in target_table.find_all("tr")[1:]:
        cols = row.find_all(["th", "td"])
        if len(cols) < 3:
            continue

        # 0-я колонка: номер этапа
        try:
            rnd = int(cols[0].get_text(strip=True))
        except ValueError:
            continue

        # 1-я колонка: Grand Prix (название и ссылка)
        link_tag = cols[1].find("a")
        if not link_tag or not link_tag.get("href"):
            continue
        race_name = link_tag.get_text(strip=True)
        raw_href = link_tag["href"]
        href = normalize_race_link(season, race_name, raw_href)

        # 2-я колонка: Date
        original_date_text = cols[2].get_text(strip=True)
        date_norm, date_obj = parse_date_cell(original_date_text, season)

        races.append({
            "round": rnd,
            "race_name": race_name,
            "date_str": date_norm,
            "link": href,
            "date_obj": date_obj
        })

    return sorted(races, key=lambda x: x["round"])


def parse_race_classification(relative_url: str) -> dict[str, float]:
    """
    По относительному URL "/wiki/2025_Bahrain_Grand_Prix" (пример) парсит таблицу результатов:
    Ищем среди всех <table class="wikitable"> ту, в шапке которой есть и "Driver", и "Points".
    Возвращаем словарь { "Имя Фамилия": очки }.
    Если таблицу не нашли или возникла ошибка → возвращаем пустой словарь.
    """
    full_url = WIKI_BASE + relative_url
    try:
        soup = get_wiki_soup(full_url)
    except requests.RequestException as e:
        print(f"⚠️ Не удалось загрузить страницу гонки {relative_url}: {e}")
        return {}

    target_table = None
    for tbl in soup.find_all("table", class_="wikitable"):
        header_cells = tbl.find_all("th")
        headers = [th.get_text(strip=True) for th in header_cells]
        if any("Driver" in h for h in headers) and any("Points" in h for h in headers):
            target_table = tbl
            break

    if target_table is None:
        print(f"⚠️ Не удалось найти таблицу с колонками Driver/Points на странице {relative_url}")
        return {}

    header_cells = target_table.find_all("th")
    headers = [th.get_text(strip=True) for th in header_cells]
    idx_driver = idx_points = None
    for idx, h in enumerate(headers):
        if "Driver" in h:
            idx_driver = idx
        if "Points" in h:
            idx_points = idx
    if idx_driver is None or idx_points is None:
        print(f"⚠️ Не удалось найти колонки Driver/Points в таблице {relative_url}")
        return {}

    results: dict[str, float] = {}
    for row in target_table.find_all("tr")[1:]:
        cols = row.find_all(["th", "td"])
        if len(cols) <= max(idx_driver, idx_points):
            continue

        name = cols[idx_driver].get_text(strip=True)
        points_text = cols[idx_points].get_text(strip=True)
        try:
            pts = float(points_text)
        except ValueError:
            pts = 0.0

        results[name] = pts

    return results


def get_all_results_up_to_race(season: int, round_limit: int) -> dict[str, float]:
    """
    Сначала вызывает get_races(season) → список всех гонок сезона.
    Для каждой гонки с round ≤ round_limit: вызываем parse_race_classification(),
    суммируем очки пилотов. В конце возвращаем словарь { "Имя Фамилия": очки }, 
    отсортированный по убыванию очков.
    """
    races = get_races(season)
    if not races:
        return {}

    totals: dict[str, float] = {}
    for race in races:
        if race["round"] > round_limit:
            break

        time.sleep(1)  # Небольшая пауза

        pts_dict = parse_race_classification(race["link"])
        if not pts_dict:
            continue

        for drv, pts in pts_dict.items():
            totals[drv] = totals.get(drv, 0.0) + pts

    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))
