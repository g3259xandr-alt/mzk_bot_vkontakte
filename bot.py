import os
import csv
import io
import json
import random
import time
import requests
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
API_VERSION = "5.199"

CSV_PRICES = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=0&single=true&output=csv"
CSV_JOBS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=1300710276&single=true&output=csv"
CSV_POINTS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=722284172&single=true&output=csv"

JOBS_URL = "https://lom-rm.ru/vakansii/"
PHONE_NUMBER = "+79271714364"


# VK возвращает error_code 911 "keyboard contains too much buttons", если в
# inline-клавиатуре больше 10 кнопок суммарно (независимо от числа строк).
# SAFETY_MARGIN оставляет запас в 1 кнопку ниже реального лимита.
MAX_INLINE_BUTTONS = 10
SAFETY_MARGIN = 1
POINTS_COLUMNS = 2  # кнопок в одной строке списка

# Список районов (верхний уровень): "Назад" + "Вперёд" + "В меню" = 3 кнопки резерва
RESERVED_TOP = 3
PER_PAGE = ((MAX_INLINE_BUTTONS - SAFETY_MARGIN - RESERVED_TOP) // POINTS_COLUMNS) * POINTS_COLUMNS

# Список подрайонов / адресов (уровень ниже): + кнопка "⬅️ К списку" = 4 кнопки резерва
RESERVED_NESTED = 4
PER_PAGE_NESTED = ((MAX_INLINE_BUTTONS - SAFETY_MARGIN - RESERVED_NESTED) // POINTS_COLUMNS) * POINTS_COLUMNS

OTHER_SUBDISTRICT_LABEL = "Прочие пункты"

# Обработка одного клика читает таблицу пунктов по несколько раз (районы,
# подрайоны, адреса), поэтому без кеша каждый клик — это несколько отдельных
# HTTP-запросов к Google Sheets подряд, и бот кажется "подвисшим".
CSV_CACHE_TTL = 60  # секунд

known_users = set()

WELCOME_TEXT = "👋 Здравствуйте! Добро пожаловать!\n\nВыберите, что вас интересует:"
UNIVERSAL_TEXT = "Выберите, что вас интересует:"


# ============ Работа с гугл-таблицей ============

_csv_cache = {}  # url -> (fetched_at, rows)


def load_csv(url):
    cached = _csv_cache.get(url)
    if cached and time.time() - cached[0] < CSV_CACHE_TTL:
        return cached[1]
    r = requests.get(url, timeout=10)
    r.encoding = "utf-8"
    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    _csv_cache[url] = (time.time(), rows)
    return rows


def format_prices():
    rows = load_csv(CSV_PRICES)
    lines = ["💰 Цены на металл:\n"]
    for row in rows:
        name = (row.get("Название") or "").strip()
        price = (row.get("Цена") or "").strip()
        if name:
            lines.append(f"• {name} — {price}")
    return "\n".join(lines) if len(lines) > 1 else "Данные о ценах пока не заполнены."


def format_jobs():
    rows = load_csv(CSV_JOBS)
    blocks = ["💼 Вакансии:\n"]
    for row in rows:
        pos = (row.get("Должность") or "").strip()
        salary = (row.get("Зарплата") or "").strip()
        sched = (row.get("График") or "").strip()
        desc = (row.get("Описание") or "").strip()
        if pos:
            block = f"🔹 {pos}"
            if salary:
                block += f"\nЗарплата: {salary}"
            if sched:
                block += f"\nГрафик: {sched}"
            if desc:
                block += f"\n{desc}"
            blocks.append(block)
    return "\n\n".join(blocks) if len(blocks) > 1 else "Вакансий пока нет."


def get_points_data():
    """Список всех пунктов (только с адресом/районом), в порядке таблицы"""
    rows = load_csv(CSV_POINTS)
    points = []
    for row in rows:
        district = (row.get("Район") or "").strip()
        subdistrict = (row.get("Подрайон") or "").strip()
        address = (row.get("Адрес") or "").strip()
        hours = (row.get("Режим работы") or "").strip()
        if address or district:
            points.append({
                "district": district,
                "subdistrict": subdistrict,
                "address": address,
                "hours": hours,
            })
    return points


def get_districts():
    """Уникальные районы в порядке первого появления в таблице"""
    order = []
    seen = set()
    for p in get_points_data():
        d = p["district"] or "Без района"
        if d not in seen:
            seen.add(d)
            order.append(d)
    return order


def points_in_district(district):
    return [p for p in get_points_data() if (p["district"] or "Без района") == district]


def subdistrict_groups(district):
    """Подрайоны внутри района в порядке появления. Если есть пункты без
    подрайона, они собираются в отдельную группу с ключом ''."""
    order = []
    seen = set()
    has_empty = False
    for p in points_in_district(district):
        s = p["subdistrict"]
        if s:
            if s not in seen:
                seen.add(s)
                order.append(s)
        else:
            has_empty = True
    if has_empty:
        order.append("")
    return order


def subdistrict_label(s):
    return s if s else OTHER_SUBDISTRICT_LABEL


def points_in_subdistrict(district, subdistrict):
    return [p for p in points_in_district(district) if p["subdistrict"] == subdistrict]


def truncate_label(s, fallback="Пункт"):
    s = (s or "").strip()
    return s[:40] if s else fallback


# ============ Клавиатуры ============

def main_keyboard():
    keyboard = {
        "inline": True,
        "buttons": [
            [{"action": {"type": "callback", "label": "💰 Цены на металл",
                         "payload": json.dumps({"cmd": "prices"})}, "color": "primary"}],
            [{"action": {"type": "callback", "label": "📍 Пункты приема",
                         "payload": json.dumps({"cmd": "points", "p": 0})}, "color": "secondary"}],
            [{"action": {"type": "callback", "label": "💼 Вакансии",
                         "payload": json.dumps({"cmd": "jobs"})}, "color": "secondary"}],
            [{"action": {"type": "open_link", "link": f"tel:{PHONE_NUMBER}",
                         "label": "📞 Позвонить"}}],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def back_keyboard(cmd="menu"):
    keyboard = {
        "inline": True,
        "buttons": [
            [{"action": {"type": "callback", "label": "⬅️ Назад",
                         "payload": json.dumps({"cmd": cmd})}, "color": "secondary"}],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def jobs_keyboard():
    keyboard = {
        "inline": True,
        "buttons": [
            [{"action": {"type": "open_link", "link": JOBS_URL, "label": "🔗 Подробнее"}}],
            [{"action": {"type": "callback", "label": "⬅️ Назад",
                         "payload": json.dumps({"cmd": "menu"})}, "color": "secondary"}],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def _paged_grid(items, page, per_page, label_of, payload_of):
    """Общий конструктор сетки из POINTS_COLUMNS кнопок в строке для списка items."""
    total = len(items)
    start = page * per_page
    end = min(start + per_page, total)

    buttons = []
    row = []
    for i in range(start, end):
        row.append({
            "action": {"type": "callback", "label": label_of(items[i]),
                       "payload": json.dumps(payload_of(i, items[i]))},
            "color": "secondary"
        })
        if len(row) == POINTS_COLUMNS:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return buttons, total, end


def _nav_row(page, end, total, nav_cmd, nav_extra):
    nav = []
    if page > 0:
        nav.append({
            "action": {"type": "callback", "label": "◀️ Назад",
                       "payload": json.dumps({**nav_extra, "cmd": nav_cmd, "p": page - 1})},
            "color": "primary"
        })
    if end < total:
        nav.append({
            "action": {"type": "callback", "label": "Вперёд ▶️",
                       "payload": json.dumps({**nav_extra, "cmd": nav_cmd, "p": page + 1})},
            "color": "primary"
        })
    return [nav] if nav else []


def _menu_button():
    return [{
        "action": {"type": "callback", "label": "🏠 В меню",
                   "payload": json.dumps({"cmd": "menu"})},
        "color": "negative"
    }]


def _back_button(label, payload):
    return [{
        "action": {"type": "callback", "label": label,
                   "payload": json.dumps(payload)},
        "color": "primary"
    }]


def districts_keyboard(page):
    """Верхний уровень: список районов"""
    districts = get_districts()
    buttons, total, end = _paged_grid(
        districts, page, PER_PAGE,
        label_of=lambda d: truncate_label(d, "Район"),
        payload_of=lambda i, d: {"cmd": "district", "d": i, "p": 0},
    )
    buttons += _nav_row(page, end, total, "points", {})
    buttons.append(_menu_button())
    return json.dumps({"inline": True, "buttons": buttons}, ensure_ascii=False)


def districts_title(page):
    total = len(get_districts())
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    return f"📍 Пункты приема (стр. {page + 1}/{total_pages}):\nВыберите район:"


def subdistricts_keyboard(d_idx, page):
    """Средний уровень: подрайоны внутри района (например, Саранск)"""
    district = get_districts()[d_idx]
    subs = subdistrict_groups(district)
    buttons, total, end = _paged_grid(
        subs, page, PER_PAGE_NESTED,
        label_of=lambda s: truncate_label(subdistrict_label(s), "Подрайон"),
        payload_of=lambda i, s: {"cmd": "subdistrict", "d": d_idx, "s": i},
    )
    buttons += _nav_row(page, end, total, "district", {"d": d_idx})
    buttons.append(_back_button("⬅️ К районам", {"cmd": "points", "p": d_idx // PER_PAGE}))
    buttons.append(_menu_button())
    return json.dumps({"inline": True, "buttons": buttons}, ensure_ascii=False)


def subdistricts_title(d_idx, page):
    district = get_districts()[d_idx]
    total = len(subdistrict_groups(district))
    total_pages = max(1, (total + PER_PAGE_NESTED - 1) // PER_PAGE_NESTED)
    return f"📍 {district} (стр. {page + 1}/{total_pages}):\nВыберите подрайон:"


def simple_back_keyboard(back_label, back_payload):
    """Клавиатура для конечного списка адресов: только 'Назад' и 'В меню'"""
    buttons = [_back_button(back_label, back_payload), _menu_button()]
    return json.dumps({"inline": True, "buttons": buttons}, ensure_ascii=False)


def format_points_block(header, points_group):
    """Текстом сразу все адреса с режимом работы — без промежуточных кнопок"""
    lines = [header]
    for p in points_group:
        entry = f"\n🔹 {p['address'] or 'Без адреса'}"
        if p["hours"]:
            entry += f"\nРежим работы: {p['hours']}"
        lines.append(entry)
    if len(lines) == 1:
        lines.append("\nПунктов не найдено.")
    return "\n".join(lines)


def district_points_text(d_idx):
    district = get_districts()[d_idx]
    return format_points_block(f"📍 {district}:", points_in_district(district))


def subdistrict_points_text(d_idx, s_idx):
    district = get_districts()[d_idx]
    subdistrict = subdistrict_groups(district)[s_idx]
    return format_points_block(
        f"📍 {district} — {subdistrict_label(subdistrict)}:",
        points_in_subdistrict(district, subdistrict),
    )


# ============ Отправка / редактирование ============

def send_message(peer_id, text, keyboard=None):
    params = {
        "access_token": VK_TOKEN, "v": API_VERSION,
        "peer_id": peer_id, "message": text,
        "random_id": random.randint(1, 2**31),
    }
    if keyboard:
        params["keyboard"] = keyboard
    resp = requests.post("https://api.vk.com/method/messages.send", data=params).json()
    if "error" in resp:
        print("[VK ERROR] messages.send:", resp["error"])
    return resp


def edit_message(peer_id, cmid, text, keyboard=None):
    params = {
        "access_token": VK_TOKEN, "v": API_VERSION,
        "peer_id": peer_id, "conversation_message_id": cmid,
        "message": text,
    }
    if keyboard:
        params["keyboard"] = keyboard
    resp = requests.post("https://api.vk.com/method/messages.edit", data=params).json()
    if "error" in resp:
        print("[VK ERROR] messages.edit:", resp["error"])
    return resp


def answer_callback(event_id, user_id, peer_id):
    params = {
        "access_token": VK_TOKEN, "v": API_VERSION,
        "event_id": event_id, "user_id": user_id, "peer_id": peer_id,
    }
    requests.post("https://api.vk.com/method/messages.sendMessageEventAnswer", data=params)


# ============ Long Poll ============

def get_long_poll_server():
    params = {"access_token": VK_TOKEN, "v": API_VERSION, "group_id": GROUP_ID}
    r = requests.get("https://api.vk.com/method/groups.getLongPollServer",
                     params=params).json()
    return r["response"]


def main():
    print("Бот запущен...")
    lp = get_long_poll_server()
    server, key, ts = lp["server"], lp["key"], lp["ts"]

    while True:
        try:
            r = requests.get(server, params={
                "act": "a_check", "key": key, "ts": ts, "wait": 25
            }, timeout=30).json()

            if "failed" in r:
                lp = get_long_poll_server()
                server, key, ts = lp["server"], lp["key"], lp["ts"]
                continue

            ts = r["ts"]

            for event in r.get("updates", []):
                etype = event.get("type")

                if etype == "message_new":
                    msg = event["object"]["message"]
                    peer_id = msg["peer_id"]
                    from_id = msg["from_id"]

                    if from_id not in known_users:
                        known_users.add(from_id)
                        send_message(peer_id, WELCOME_TEXT, main_keyboard())
                    else:
                        send_message(peer_id, UNIVERSAL_TEXT, main_keyboard())

                elif etype == "message_event":
                    obj = event["object"]
                    peer_id = obj["peer_id"]
                    user_id = obj["user_id"]
                    event_id = obj["event_id"]
                    cmid = obj.get("conversation_message_id")
                    payload = obj.get("payload", {})
                    cmd = payload.get("cmd")

                    answer_callback(event_id, user_id, peer_id)

                    try:
                        if cmd == "prices":
                            edit_message(peer_id, cmid, format_prices(), back_keyboard())

                        elif cmd == "jobs":
                            edit_message(peer_id, cmid, format_jobs(), jobs_keyboard())

                        elif cmd == "points":
                            page = payload.get("p", 0)
                            edit_message(peer_id, cmid, districts_title(page), districts_keyboard(page))

                        elif cmd == "district":
                            d_idx = payload.get("d")
                            page = payload.get("p", 0)
                            district = get_districts()[d_idx]
                            if len(subdistrict_groups(district)) > 1:
                                edit_message(peer_id, cmid,
                                             subdistricts_title(d_idx, page),
                                             subdistricts_keyboard(d_idx, page))
                            else:
                                kb = simple_back_keyboard(
                                    "⬅️ К районам", {"cmd": "points", "p": d_idx // PER_PAGE})
                                edit_message(peer_id, cmid, district_points_text(d_idx), kb)

                        elif cmd == "subdistrict":
                            d_idx = payload.get("d")
                            s_idx = payload.get("s")
                            back_page = s_idx // PER_PAGE_NESTED
                            kb = simple_back_keyboard(
                                "⬅️ К подрайонам", {"cmd": "district", "d": d_idx, "p": back_page})
                            edit_message(peer_id, cmid, subdistrict_points_text(d_idx, s_idx), kb)

                        elif cmd == "menu":
                            edit_message(peer_id, cmid, UNIVERSAL_TEXT, main_keyboard())
                    except Exception as e:
                        print("[VK ERROR] обработка cmd", cmd, ":", repr(e))
                        send_message(peer_id, f"Ошибка: {e}", main_keyboard())

        except Exception as e:
            print("Ошибка:", e)


if __name__ == "__main__":
    main()
