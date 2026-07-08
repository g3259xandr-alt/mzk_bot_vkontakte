import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import os
from dotenv import load_dotenv

load_dotenv()

vk_session = vk_api.VkApi(token=os.getenv('VK_TOKEN'))
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

def create_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('Кнопка 1', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('Кнопка 2', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('Кнопка 3', color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()

def send_message(user_id, message, keyboard=None):
    vk.messages.send(
        user_id=user_id,
        message=message,
        random_id=0,
        keyboard=keyboard
    )

print("Бот запущен...")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.lower()

        if text == 'начать' or text == 'привет':
            send_message(user_id, "Выберите действие:", create_keyboard())
        elif text == 'кнопка 1':
            send_message(user_id, "Вы выбрали кнопку 1!")
        elif text == 'кнопка 2':
            send_message(user_id, "Вы выбрали кнопку 2!")
        elif text == 'кнопка 3':
            send_message(user_id, "Вы выбрали кнопку 3!")
        else:
            send_message(user_id, "Не понял команду. Напишите 'начать'", create_keyboard())
