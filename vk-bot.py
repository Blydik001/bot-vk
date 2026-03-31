import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import json

# --- НАСТРОЙКИ ---
TOKEN = 'vk1.a.HiLpWlX0pY7dtxhW0TdGn3P1Rmfk1v-M_3OZj8NQG25D8Je6qiuMzppSSmo59nVtz1aqJsm4n_RFAjpjF7tzZVqZjJa04rLZLzo75a9dK7PZlFUCm8Raq_DPPv_Gtpk5sIjj9wGuon9j_TeytEMppaqTM1xuqFHflk1XrkgDZq1Y2UlbPMnRURgs8XjqcsR94i4lFHlsnF3jEO31xw2sfw'
GROUP_ID = 237221450

# ID ГЛАВНОГО АДМИНА (видит всё)
MAIN_ADMIN_ID = 99999999

# Администраторы по серверам
ADMINS = {
    'ULYANOVSK': [111111, 222222],
    'YAKUTSK': [333333],
    'TAMBOV': [444444],
    'BRATSK': [555555],
    'ASTRAKHAN': [666666]
}

# База данных (в памяти для примера)
users = {}
reports = {}  # {user_id: {'server': 'ULYANOVSK', 'text': '...', 'answered_by': None}}

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)


def send_message(peer_id, message, keyboard=None):
    vk.messages.send(
        peer_id=peer_id,
        message=message,
        random_id=0,
        keyboard=keyboard
    )


def get_server_keyboard():
    keyboard = {
        "one_time": True,
        "buttons": [
            [{"action": {"type": "text", "label": "ULYANOVSK", "payload": "{}"}}],
            [{"action": {"type": "text", "label": "YAKUTSK", "payload": "{}"}}],
            [{"action": {"type": "text", "label": "TAMBOV", "payload": "{}"}}],
            [{"action": {"type": "text", "label": "BRATSK", "payload": "{}"}}],
            [{"action": {"type": "text", "label": "ASTRAKHAN", "payload": "{}"}}]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)


# Список всех админов (для проверки прав)
ALL_ADMIN_IDS = list({id for sublist in ADMINS.values() for id in sublist})

for event in longpoll.listen():
    if event.type != VkBotEventType.MESSAGE_NEW:
        continue

    user_id = event.object.message['from_id']
    text = event.object.message['text'].upper()

    # --- НАЧАЛО РАБОТЫ ---
    if text == 'НАЧАТЬ' or text == 'START':
        send_message(user_id,
                     "Приветствую! В данном боте ты сможешь оставить свою наводку на нарушение или какую-то ошибку в игре.\n\nДля начала работы выбери сервер:",
                     get_server_keyboard())
        users[user_id] = {'server': None}
        continue

    # --- ВЫБОР СЕРВЕРА ---
    if users.get(user_id, {}).get('server') is None:
        if text in ADMINS.keys():
            users[user_id]['server'] = text
            send_message(user_id,
                         f"Вы выбрали сервер: {text}\n\nНапишите вашу наводку на нарушение или какую-то ошибку в игре.")
        else:
            send_message(user_id, "Пожалуйста, выберите сервер из предложенных кнопок.", get_server_keyboard())
        continue

    # --- ОТПРАВКА СООБЩЕНИЯ АДМИНИСТРАТОРАМ ---
    if text not in ['ВЫДАТЬ АДМИН', '/ADMIN']:
        server = users[user_id]['server']

        # Сохраняем отчет
        reports[user_id] = {
            'server': server,
            'text': event.object.message['text'],
            'answered_by': None
        }

        # Формируем сообщение для админов
        report_msg = (f"[НОВОЕ СООБЩЕНИЕ]\n"
                      f"Сервер: {server}\n"
                      f"Пользователь: {user_id}\n"
                      f"Текст: {event.object.message['text']}")

        # Отправляем ГЛАВНОМУ АДМИНУ
        send_message(MAIN_ADMIN_ID, report_msg)

        # Отправляем АДМИНАМ выбранного сервера
        for admin in ADMINS[server]:
            send_message(admin, report_msg)

        send_message(user_id, "Ваша наводка отправлена администраторам. Ожидайте ответа.")

    else:
        # --- ВЫДАЧА АДМИНКИ ---
        if user_id == MAIN_ADMIN_ID or user_id in ALL_ADMIN_IDS:
            send_message(user_id, "Введите ID пользователя, которому хотите выдать права администратора:")
            users[user_id] = {'step': 'give_admin'}
        else:
            send_message(user_id, "У вас нет прав на выдачу администраторских прав.")

    # --- ОБРАБОТКА ВЫДАЧИ АДМИНКИ ---
    if users.get(user_id, {}).get('step') == 'give_admin':
        try:
            target_id = int(text)

            # Добавляем во все группы админов (или только в одну — по вашему выбору)
            for server in ADMINS:
                if target_id not in ADMINS[server]:
                    ADMINS[server].append(target_id)

            send_message(user_id, f"Администраторские права выданы пользователю {target_id}.")

            # Обновляем список всех админов
            ALL_ADMIN_IDS = list({id for sublist in ADMINS.values() for id in sublist})

        except:
            send_message(user_id, "Неверный формат ID. Попробуйте ещё раз.")

        users[user_id]['step'] = None

    # --- ОТВЕТ АДМИНИСТРАТОРА ---
    # Проверяем, что это ответ (reply) на сообщение пользователя
    reply_msg = event.object.message.get('reply_message')
    if reply_msg and user_id in ALL_ADMIN_IDS + [MAIN_ADMIN_ID]:

        # Находим ID пользователя, которому отвечаем
        replied_user_id = reply_msg['from_id']

        if replied_user_id in reports:
            # Отправляем ответ пользователю
            send_message(replied_user_id, f"Ответ администратора:\n{text}")

            # Уведомляем ГЛАВНОГО АДМИНА об ответе
            answer_notification = (
                f"[ОТВЕТ АДМИНА]\n"
                f"Пользователь: {replied_user_id} (Сервер: {reports[replied_user_id]['server']})\n"
                f"Ответил админ: {user_id}\n"
                f"Ответ: {text}"
            )
            send_message(MAIN_ADMIN_ID, answer_notification)

            # Отмечаем в базе, что ответили
            reports[replied_user_id]['answered_by'] = user_id