import requests
import time

# Токен группы и версия API
token = 'ВАШ_ТОКЕН_ГРУППЫ'
api_version = '5.131'
group_id = 'ID_ВАШЕЙ_ГРУППЫ'

# Получаем Long Poll сервер
def get_long_poll_server():
    url = f'https://api.vk.com/method/groups.getLongPollServer?group_id={group_id}&v={api_version}&access_token={token}'
    response = requests.get(url).json()
    return response['response']

# Отправка сообщения
def send_message(user_id, message):
    url = 'https://api.vk.com/method/messages.send'
    params = {
        'user_id': user_id,
        'message': message,
        'random_id': int(time.time()),
        'v': api_version,
        'access_token': token
    }
    requests.post(url, params=params)

# Основной цикл бота
def main():
    lp_server = get_long_poll_server()
    server, key, ts = lp_server['server'], lp_server['key'], lp_server['ts']
    print('Бот запущен!')

    while True:
        try:
            # Запрос к Long Poll серверу
            url = f'{server}?act=a_check&key={key}&ts={ts}&wait=25'
            response = requests.get(url).json()
            
            if 'updates' in response and response['updates']:
                for update in response['updates']:
                    if update['type'] == 'message_new':
                        user_id = update['object']['message']['from_id']
                        message_text = update['object']['message']['text'].lower()
                        
                        if message_text == 'привет':
                            send_message(user_id, 'Привет! Как настроение?')
                        elif message_text == 'пока':
                            send_message(user_id, 'До встречи!')
                        else:
                            send_message(user_id, 'Я пока не знаю, что ответить. Напиши "привет" или "пока".')
                
                ts = response['ts']  # обновляем ts

        except Exception as e:
            print('Ошибка:', e)
            time.sleep(5)
            lp_server = get_long_poll_server()
            server, key, ts = lp_server['server'], lp_server['key'], lp_server['ts']

if __name__ == '__main__':
    main()
