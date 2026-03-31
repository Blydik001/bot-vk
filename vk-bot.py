import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import json
import re
import requests  # Импортируем requests для загрузки фотографий

# Настройки
GROUP_ID = '237221450'
TOKEN = 'vk1.a.HiLpWlX0pY7dtxhW0TdGn3P1Rmfk1v-M_3OZj8NQG25D8Je6qiuMzppSSmo59nVtz1aqJsm4n_RFAjpjF7tzZVqZjJa04rLZLzo75a9dK7PZlFUCm8Raq_DPPv_Gtpk5sIjj9wGuon9j_TeytEMppaqTM1xuqFHflk1XrkgDZq1Y2UlbPMnRURgs8XjqcsR94i4lFHlsnF3jEO31xw2sfw'

# ID бесед — будем заполнять динамически
SERVER_CHATS = {
    'ULYANOVSK': None,
    'YAKUTSK': None,
    'TAMBOV': None,
    'BRATSK': None,
    'ASTRAKHAN': None
}

# Инициализация
vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkBotLongPoll(vk_session, GROUP_ID)
vk = vk_session.get_api()

# Состояния пользователей (для жалоб)
user_states = {}

# Набор отправленных жалоб (защита от дублей)
sent_reports = set()

# Список серверов
SERVERS = ['ULYANOVSK', 'YAKUTSK', 'TAMBOV', 'BRATSK', 'ASTRAKHAN']


# Вспомогательная функция для загрузки фотографий
def upload_photos(attachments, peer_id):
    photo_attachments = []

    # Проходим по всем прикрепленным фотографиям
    for attachment in attachments:
        if attachment['type'] != 'photo':
            continue

        # Получаем URL для загрузки фотографии
        upload_url = vk.photos.getMessagesUploadServer(peer_id=peer_id)['upload_url']

        # Загружаем фотографию
        photo_file = requests.get(attachment['photo']['sizes'][-1]['url']).content
        response = requests.post(upload_url, files={'photo': ('image.jpg', photo_file)})
        result = response.json()

        # Сохраняем фотографию
        saved_photo = vk.photos.saveMessagesPhoto(**result)[0]

        # Формируем attachment для отправки
        photo_attachment = f"photo{saved_photo['owner_id']}_{saved_photo['id']}"
        photo_attachments.append(photo_attachment)

    return photo_attachments


def find_all_chats():
    """Поиск бесед для всех серверов"""
    try:
        conversations = vk.messages.getConversations(count=200, filter='all')
        found_chats = 0

        for item in conversations['items']:
            conv_data = item['conversation']
            if conv_data['peer']['type'] == 'chat':
                title = conv_data.get('chat_settings', {}).get('title', '').upper()
                for server in SERVERS:
                    if server in title:
                        if SERVER_CHATS[server] is None:
                            SERVER_CHATS[server] = conv_data['peer']['id']
                            found_chats += 1
        print(f"Найдено бесед: {found_chats}")
        return found_chats > 0
    except Exception as e:
        print(f"❌ Ошибка поиска бесед: {e}")
        return False


def send_to_server_chat(server, user_info, report_text, user_id=None, attachments=[]):
    """Отправка наводки в беседу сервера с возможностью передачи фотографий"""
    global sent_reports  # Используем глобальную переменную

    # Генерируем уникальный идентификатор для данной жалобы
    report_hash = hash((server, user_info, report_text))

    # Проверяем, не отправляли ли мы уже эту жалобу
    if report_hash in sent_reports:
        print("❗ Жалоба уже была отправлена ранее. Пропускаем повторную отправку.")
        return False

    # Продолжаем обычную логику отправки
    if SERVER_CHATS[server] is None:
        if not find_all_chats():
            print(f"❌ Не удалось найти беседу для сервера {server}")
            return False

    chat_id = SERVER_CHATS[server]
    message = f"🔔 Новая наводка\n\nИмя пользователя: {user_info}\nСервер: {server}\nТекст: {report_text}"

    # Загружаем и прикрепляем фотографии, если они есть
    photo_attachments = []
    if attachments:
        photo_attachments = upload_photos(attachments, chat_id)

    try:
        # Отправляем сообщение с фотографиями (если они есть)
        vk.messages.send(
            peer_id=chat_id,
            message=message,
            attachment=",".join(photo_attachments),
            random_id=get_random_id()
        )
        print(f"✅ Сообщение успешно отправлено в беседу {server} (ID: {chat_id})")

        # Добавляем хэш жалобы в список отправленных
        sent_reports.add(report_hash)
        return True
    except vk_api.exceptions.ApiError as e:
        error_code = e.error['error_code']
        error_msg = e.error['error_msg']

        if error_code == 917:
            print(f"❌ Ошибка 917 для беседы {server} (ID: {chat_id}): {error_msg}")
            SERVER_CHATS[server] = None
            return send_to_server_chat(server, user_info, report_text, user_id, attachments)
        elif error_code == 901:
            print(f"❌ Ошибка 901 для беседы {server}: {error_msg}")
        else:
            print(f"❌ Другая ошибка VK API при отправке в {server}: {error_code} — {error_msg}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка при отправке в беседу {server}: {e}")
        return False


def get_servers_keyboard():
    """Создание клавиатуры с выбором серверов"""
    keyboard = {
        "one_time": True,
        "buttons": []
    }

    for i in range(0, len(SERVERS), 2):
        row = []
        for server in SERVERS[i:i + 2]:
            row.append({
                "action": {
                    "type": "text",
                    "label": server,
                    "payload": json.dumps({"server": server})
                },
                "color": "primary"
            })
        keyboard["buttons"].append(row)

    return json.dumps(keyboard, ensure_ascii=False)


def get_start_keyboard():
    """Клавиатура для команды НАЧАТЬ"""
    keyboard = {
        "one_time": True,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "НАЧАТЬ"
                    },
                    "color": "positive"
                }
            ]
        ]
    }
    return json.dumps(keyboard, ensure_ascii=False)


def handle_message(event):
    """Обработка входящих сообщений"""
    user_id = event.obj.message['from_id']
    text = event.obj.message['text'].strip()

    # peer_id нужен, чтобы ответить в ту же беседу, где происходит действие
    peer_id = event.obj.message.get('peer_id')

    # Получаем прикрепленные файлы (фотографии)
    attachments = event.obj.message.get('attachments', [])

    # Обрабатываем payload (нажатие кнопок)
    payload = None
    if 'payload' in event.obj.message:
        try:
            payload = json.loads(event.obj.message['payload'])
        except Exception as e:
            print(f"Ошибка парсинга payload: {e}")

    # --- НОВЫЙ БЛОК: Автоматический ответ по reply_message ---
    # Проверяем, что сообщение пришло из беседы и это ответ на другое сообщение
    if peer_id and peer_id > 2000000000 and event.obj.message.get('reply_message'):

        # Получаем оригинальное сообщение, на которое отвечают
        reply_message = event.obj.message['reply_message']

        # Парсим оригинальный текст, чтобы найти ID пользователя
        original_text = reply_message.get('text', '')

        # Улучшаем регулярное выражение для поиска ID пользователя
        # Ищем варианты: [id12345|...], @id12345, или просто 12345
        match = re.search(r'($$id(\d+)\||@id(\d+)|(\d+))', original_text)

        if match:
            # Пробуем найти ID среди групп регулярных выражений
            groups = match.groups()
            for group in groups:
                if group and group.isdigit():  # Проверяем, что группа не пустая и это цифра
                    target_user_id = int(group)
                    break
            else:
                # Если не нашли подходящий ID
                send_message(peer_id,
                             "⚠️ Не удалось определить пользователя для ответа. Возможно, сообщение повреждено.",
                             is_user=False)
                return

            # Отправляем ответ пользователю лично
            send_message(target_user_id,
                         f"📨 Ответ технической стороны:\n\n{text}")

            # Подтверждаем в той же беседе, откуда пришёл ответ
            send_message(peer_id, f"✅ Ваш ответ успешно отправлен [id{target_user_id}|пользователю].",
                         is_user=False)
            return

        else:
            # Если не смогли найти ID пользователя, предупреждаем администратора
            send_message(peer_id, "⚠️ Не удалось определить пользователя для ответа. Возможно, сообщение повреждено.",
                         is_user=False)
            return

    # --- СТАРЫЙ БЛОК: Логика приема жалоб от пользователей ---

    try:
        user_info_data = vk.users.get(user_ids=user_id)[0]
        user_name = f"{user_info_data['first_name']} {user_info_data['last_name']}"
        user_link = f"[id{user_id}|{user_name}]"
    except Exception:
        user_link = f"ID: {user_id}"

    if text.upper() == 'НАЧАТЬ':
        user_states[user_id] = 'waiting_server'

        send_message(
            user_id,
            "Приветствую администратор, в данном боте ты сможешь оставить свою наводку на нарушение или какую то ошибку в игре. Для нчала работы выбери сервер из списка:",
            get_servers_keyboard()
        )
        return

    elif user_states.get(user_id) == 'waiting_server' and text in SERVERS:
        user_states[user_id] = {'state': 'waiting_report', 'server': text}
        send_message(
            user_id,
            f"Вы выбрали сервер: {text}. Напишите наводку на нарушителя или напишите с какой ошибкой вы столкнулись в игре."
        )
        return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get('state') == 'waiting_report':
        server = user_states[user_id]['server']
        report_text = text

        # Передаем фотографии, если они есть
        if send_to_server_chat(server, user_link, report_text, user_id, attachments):
            send_message(user_id, "Спасибо за наводку, данная информация будет проверена.")
        else:
            send_message(user_id, "Произошла ошибка при отправке жалобы.")

        del user_states[user_id]
        return

    else:
        send_message(
            user_id,
            "Неизвестная команда. Напишите НАЧАТЬ.",
            get_start_keyboard()
        )


def send_message(to_id, message, keyboard=None, is_user=True):
    """Универсальная функция отправки сообщений"""
    params = {
        'message': message,
        'random_id': get_random_id()
    }

    if keyboard:
        params['keyboard'] = keyboard

    try:
        if is_user:
            params['user_id'] = to_id
            vk.messages.send(**params)
        else:
            params['peer_id'] = to_id
            vk.messages.send(**params)
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")


def main():
    """Основной цикл бота"""
    print("Инициализация: поиск бесед...")
    if not find_all_chats():
        print("⚠️ Не удалось найти ни одной беседы. Проверьте названия чатов и права бота.")

    print("\nБот запущен...")
    try:
        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                handle_message(event)
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")
    except Exception as e:
        print(f"Критическая ошибка: {e}")


if __name__ == '__main__':
    main()