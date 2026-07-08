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

# Ссылки на CSV-листы
CSV_PRICES = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=0&single=true&output=csv"
CSV_JOBS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=1300710276&single=true&output=csv"
CSV_POINTS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRRIt0VXVeQzCHNuchxHTzqeMTz67gui7OYOamrMDnq5c7XaJRe_lgZjDoX8hUYlAiVMlrmZtOb0APV/pub?gid=722284172&single=true&output=csv"

# Кто уже писал боту (сбрасывается при перезапуске)
known_users = set()

# Приветственное и универсальное сообщения
WELCOME_TEXT = "👋 Здравствуйте! Добро пожаловать!\n\nВыберите, что вас интересует:"
UNIVERSAL_TEXT = "Выберите, что вас интересует:"


# ============ Работа с гугл-таблицей ============

def load_csv(url):
    """Читает CSV по ссылке, возвращает список строк (словарей)"""
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


def format_points():
    rows = load_csv(CSV_POINTS)
    blocks = ["📍 Пункты приема:\n"]
    for row in rows:
        district = (row.get("Район") or "").strip()
        subdistrict = (row.get("Подрайон") or "").strip()
        address = (row.get("Адрес") or "").strip()
        hours = (row.get("Режим работы") or "").strip()
        if address or district:
            title = district
            if subdistrict:
                title += f", {subdistrict}"
            block = f"🔹 {title}"
            if address:
                block += f"\nАдрес: {address}"
            if hours:
                block += f"\nРежим работы: {hours}"
            blocks.append(block)
    return "\n\n".join(blocks) if len(blocks) > 1 else "Пунктов приема пока нет."


# ============ Клавиатура ============

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


# ============ Отправка сообщений ============

def send_message(peer_id, text, keyboard=None):
    params = {
        "access_token": VK_TOKEN,
        "v": API_VERSION,
        "peer_id": peer_id,
        "message": text,
        "random_id": random.randint(1, 2**31),
    }
    if keyboard:
        params["keyboard"] = keyboard
    requests.post("https://api.vk.com/method/messages.send", data=params)


def answer_callback(event_id, user_id, peer_id):
    """Убирает 'часики' на кнопке (обязательно для callback-кнопок)"""
    params = {
        "access_token": VK_TOKEN,
        "v": API_VERSION,
        "event_id": event_id,
        "user_id": user_id,
        "peer_id": peer_id,
    }
    requests.post("https://api.vk.com/method/messages.sendMessageEventAnswer", data=params)


# ============ Long Poll ============

def get_long_poll_server():
    params = {
        "access_token": VK_TOKEN,
        "v": API_VERSION,
        "group_id": GROUP_ID,
    }
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

                # Обычное сообщение
                if etype == "message_new":
                    msg = event["object"]["message"]
                    peer_id = msg["peer_id"]
                    from_id = msg["from_id"]

                    if from_id not in known_users:
                        known_users.add(from_id)
                        send_message(peer_id, WELCOME_TEXT, main_keyboard())
                    else:
                        send_message(peer_id, UNIVERSAL_TEXT, main_keyboard())

                # Нажатие callback-кнопки
                elif etype == "message_event":
                    obj = event["object"]
                    peer_id = obj["peer_id"]
                    user_id = obj["user_id"]
                    event_id = obj["event_id"]
                    payload = obj.get("payload", {})
                    cmd = payload.get("cmd")

                    answer_callback(event_id, user_id, peer_id)

                    if cmd == "prices":
                        send_message(peer_id, format_prices())
                    elif cmd == "points":
                        send_message(peer_id, format_points())
                    elif cmd == "jobs":
                        send_message(peer_id, format_jobs())

        except Exception as e:
            print("Ошибка:", e)


if __name__ == "__main__":
    main()
