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

# Название района, который дробится на подрайоны (как в таблице)
SARANSK_NAME = "Саранск (городской округ)"

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


# ---- Функции для пунктов приема ----

def get_points_data():
    """Возвращает список пунктов (только с адресом)"""
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
    """Список уникальных районов (в порядке появления)"""
    points = get_points_data()
    districts = []
    for p in points:
        if p["district"] and p["district"] not in districts:
            districts.append(p["district"])
    return districts


def get_subdistricts(district):
    """Список уникальных подрайонов внутри района"""
    points = get_points_data()
    subs = []
    for p in points:
        if p["district"] == district and p["subdistrict"] and p["subdistrict"] not in subs:
            subs.append(p["subdistrict"])
    return subs


def format_points_list(district, subdistrict=None):
    """Формирует текст списка пунктов для района (+ подрайон если задан)"""
    points = get_points_data()
    title = f"📍 Пункты приема — {district}"
    if subdistrict:
        title += f", {subdistrict}"
    blocks = [title + "\n"]
    for p in points:
        if p["district"] != district:
            continue
        if subdistrict and p["subdistrict"] != subdistrict:
            continue
        block = "🔹"
        if p["subdistrict"] and not subdistrict:
            block += f" {p['subdistrict']}"
        if p["address"]:
            block += f"\nАдрес: {p['address']}"
        if p["hours"]:
            block += f"\nРежим работы: {p['hours']}"
        blocks.append(block)
    return "\n\n".join(blocks) if len(blocks) > 1 else "Здесь пока нет пунктов."


# ============ Клавиатуры ============

def main_keyboard():
    keyboard = {
        "inline": True,
        "buttons": [
            [{"action": {"type": "callback", "label": "💰 Цены на металл",
                         "payload": json.dumps({"cmd": "prices"})}, "color": "primary"}],
            [{"action": {"type": "callback", "label": "📍 Пункты приема",
                         "payload": json.dumps({"cmd": "points"})}, "color": "secondary"}],
            [{"action": {"type": "callback", "label": "💼 Вакансии",
                         "payload": json.dumps({"cmd": "jobs"})}, "color": "secondary"}],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def back_keyboard(payload_cmd="menu"):
    keyboard = {
        "inline": True,
        "buttons": [
            [{"action": {"type": "callback", "label": "⬅️ Назад",
                         "payload": json.dumps({"cmd": payload_cmd})}, "color": "secondary"}],
        ],
    }
    return json.dumps(keyboard, ensure_ascii=False)


def districts_keyboard():
    """Кнопки со списком районов (по индексам)"""
    districts = get_districts()
    buttons = []
    for i, d in enumerate(districts):
        buttons.append([{
            "action": {"type": "callback", "label": d[:40],
                       "payload": json.dumps({"cmd": "district", "i": i})},
            "color": "secondary"
        }])
    buttons.append([{
        "action": {"type": "callback", "label": "⬅️ Назад",
                   "payload": json.dumps({"cmd": "menu"})},
        "color": "primary"
    }])
    return json.dumps({"inline": True, "buttons": buttons}, ensure_ascii=False)


def subdistricts_keyboard(district_index):
    """Кнопки с подрайонами выбранного района"""
    districts = get_districts()
    district = districts[district_index]
    subs = get_subdistricts(district)
    buttons = []
    for j, s in enumerate(subs):
        buttons.append([{
            "action": {"type": "callback", "label": s[:40],
                       "payload": json.dumps({"cmd": "sub", "i": district_index, "j": j})},
            "color": "secondary"
        }])
    buttons.append([{
        "action": {"type": "callback", "label": "⬅️ Назад",
                   "payload": json.dumps({"cmd": "points"})},
        "color": "primary"
    }])
    return json.dumps({"inline": True, "buttons": buttons}, ensure_ascii=False)


# ============ Отправка / редактирование сообщений ============

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
                        # Уровень 1: список районов
                        edit_message(peer_id, cmid,
                                     "📍 Выберите район:", districts_keyboard())

                    elif cmd == "district":
                        # Выбран район
                        i = payload.get("i")
                        districts = get_districts()
                        district = districts[i]
                        if district == SARANSK_NAME and get_subdistricts(district):
                            # Уровень 2: подрайоны Саранска
                            edit_message(peer_id, cmid,
                                         f"📍 {district} — выберите район:",
                                         subdistricts_keyboard(i))
                        else:
                            # Сразу список пунктов
                            edit_message(peer_id, cmid,
                                         format_points_list(district),
                                         back_keyboard("points"))

                    elif cmd == "sub":
                        # Выбран подрайон Саранска
                        i = payload.get("i")
                        j = payload.get("j")
                        districts = get_districts()
                        district = districts[i]
                        subs = get_subdistricts(district)
                        subdistrict = subs[j]
                        edit_message(peer_id, cmid,
                                     format_points_list(district, subdistrict),
                                     back_keyboard("district_back"))
                        # для возврата к подрайонам сохраняем индекс района в payload кнопки назад ниже

                    elif cmd == "menu":
                        edit_message(peer_id, cmid, UNIVERSAL_TEXT, main_keyboard())

        except Exception as e:
            print("Ошибка:", e)


if __name__ == "__main__":
    main()
