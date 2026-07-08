import os
import csv
import io
import json
import random
import requests
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
API_VERSION = "5.199"

CSV_PRICES = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=0&single=true&output=csv"
CSV_JOBS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=1300710276&single=true&output=csv"
CSV_POINTS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=722284172&single=true&output=csv"

PER_PAGE = 8  # пунктов на странице

known_users = set()

WELCOME_TEXT = "👋 Здравствуйте! Добро пожаловать!\n\nВыберите, что вас интересует:"
UNIVERSAL_TEXT = "Выберите, что вас интересует:"


# ============ Работа с гугл-таблицей ============

def load_csv(url):
    r = requests.get(url, timeout=10)
    r.encoding = "utf-8"
    reader = csv.DictReader(io.StringIO(r.text))
    return list(reader)


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


def point_label(p):
    """Короткая подпись для кнопки"""
    parts = []
    if p["district"]:
        parts.append(p["district"])
    if p["subdistrict"]:
        parts.append(p["subdistrict"])
    label = ", ".join(parts) if parts else p["address"]
    return label[:40] if label else "Пункт"


def format_point_detail(p):
    """Полная инфа по пункту"""
    title = []
    if p["district"]:
        title.append(p["district"])
    if p["subdistrict"]:
        title.append(p["subdistrict"])
    text = "📍 " + (", ".join(title) if title else "Пункт приема") + "\n"
    if p["address"]:
        text += f"\nАдрес: {p['address']}"
    if p["hours"]:
        text += f"\nРежим работы: {p['hours']}"
    return text


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


def points_keyboard(page):
    """Кнопки пунктов текущей страницы + навигация"""
    points = get_points_data()
    total = len(points)
    start = page * PER_PAGE
    end = min(start + PER_PAGE, total)

    buttons = []
    # кнопки пунктов (по одной в строке)
    for idx in range(start, end):
        p = points[idx]
        buttons.append([{
            "action": {"type": "callback", "label": point_label(p),
                       "payload": json.dumps({"cmd": "point", "i": idx})},
            "color": "secondary"
        }])

    # строка навигации
    nav = []
    if page > 0:
        nav.append({
            "action": {"type": "callback", "label": "◀️ Назад",
                       "payload": json.dumps({"cmd": "points", "p": page - 1})},
            "color": "primary"
        })
    if end < total:
        nav.append({
            "action": {"type": "callback", "label": "Вперёд ▶️",
                       "payload": json.dumps({"cmd": "points", "p": page + 1})},
            "color": "primary"
        })
    if nav:
        buttons.append(nav)

    # кнопка в главное меню
    buttons.append([{
        "action": {"type": "callback", "label": "🏠 В меню",
                   "payload": json.dumps({"cmd": "menu"})},
        "color": "negative"
    }])

    return json.dumps({"inline": True, "buttons": buttons}, ensure_ascii=False)


def points_title(page):
    points = get_points_data()
    total = len(points)
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    return f"📍 Пункты приема (стр. {page + 1}/{total_pages}):\nВыберите пункт:"


# ============ Отправка / редактирование ============

def send_message(peer_id, text, keyboard=None):
    params = {
        "access_token": VK_TOKEN, "v": API_VERSION,
        "peer_id": peer_id, "message": text,
        "random_id": random.randint(1, 2**31),
    }
    if keyboard:
        params["keyboard"] = keyboard
    requests.post("https://api.vk.com/method/messages.send", data=params)


def edit_message(peer_id, cmid, text, keyboard=None):
    params = {
        "access_token": VK_TOKEN, "v": API_VERSION,
        "peer_id": peer_id, "conversation_message_id": cmid,
        "message": text,
    }
    if keyboard:
        params["keyboard"] = keyboard
    requests.post("https://api.vk.com/method/messages.edit", data=params)


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

                    if cmd == "prices":
                        edit_message(peer_id, cmid, format_prices(), back_keyboard())

                    elif cmd == "jobs":
                        edit_message(peer_id, cmid, format_jobs(), back_keyboard())
                    elif cmd == "points":
                        try:
                            page = payload.get("p", 0)
                            points = get_points_data()
                            print(f"[DEBUG] Загружено пунктов: {len(points)}")
                            if points:
                                print(f"[DEBUG] Первый пункт: {points[0]}")
                            kb = points_keyboard(page)
                            print(f"[DEBUG] Клавиатура: {kb[:300]}")
                            edit_message(peer_id, cmid, points_title(page), kb)
                        except Exception as e:
                            print("[DEBUG] ОШИБКА в points:", repr(e))
                            send_message(peer_id, f"Ошибка пунктов: {e}", main_keyboard())

                    elif cmd == "point":
                        i = payload.get("i")
                        points = get_points_data()
                        if 0 <= i < len(points):
                            # какая страница у этого пункта — чтобы вернуться на неё
                            page = i // PER_PAGE
                            kb = {
                                "inline": True,
                                "buttons": [[{
                                    "action": {"type": "callback", "label": "⬅️ К списку",
                                               "payload": json.dumps({"cmd": "points", "p": page})},
                                    "color": "primary"
                                }]]
                            }
                            edit_message(peer_id, cmid,
                                         format_point_detail(points[i]),
                                         json.dumps(kb, ensure_ascii=False))

                    elif cmd == "menu":
                        edit_message(peer_id, cmid, UNIVERSAL_TEXT, main_keyboard())

        except Exception as e:
            print("Ошибка:", e)


if __name__ == "__main__":
    main()
