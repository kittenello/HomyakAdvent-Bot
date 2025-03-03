import os
import random
import datetime
from datetime import timedelta
import telebot
import string
from telebot import apihelper, types
import logging
import json
import subprocess
import requests.exceptions
import sys
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# -*- coding: utf-8 -*-

VIDEO_FOLDER = 'files'
WELCOME = 'settings'
ADMINS = 7235730433, 7716662796
MAIN_CHAT = -1002334358016
DEBUG_TOPIC_ID = 3

LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[  
        logging.FileHandler(os.path.join(LOGS_DIR, "bot.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def process_apply_bonus(message, max_bonus_time):
    user_id = message.from_user.id
    try:
        hours_to_apply = int(message.text)
        if hours_to_apply <= 0 or hours_to_apply > max_bonus_time:
            bot.send_message(message.chat.id, f"❌ Введите корректное количество часов (от 1 до {max_bonus_time}).")
            return

        update_bonus_time(user_id, -hours_to_apply)  # Уменьшаем бонусное время
        apply_bonus_time(user_id)  # Применяем бонусное время к cooldown

        bot.send_message(message.chat.id, f"✅ Вы успешно использовали {hours_to_apply} часов!")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите число.")

def initialize_referral(user_id):
    referrals_file_path = 'settings/referrals.json'
    try:
        with open(referrals_file_path, 'r') as file:
            referrals_data = json.load(file)
    except json.JSONDecodeError:
        referrals_data = {}

    if str(user_id) not in referrals_data:
        referrals_data[str(user_id)] = {
            'referrals': [],
            'bonus_time': 0
        }
        with open(referrals_file_path, 'w') as file:
            json.dump(referrals_data, file)

def get_referral_data(user_id):
    referrals_file_path = 'settings/referrals.json'
    try:
        with open(referrals_file_path, 'r') as file:
            referrals_data = json.load(file)
    except json.JSONDecodeError:
        referrals_data = {}
    return referrals_data.get(str(user_id), {'referrals': [], 'bonus_time': 0})

def update_bonus_time(user_id, bonus_hours):
    referrals_file_path = 'settings/referrals.json'
    try:
        with open(referrals_file_path, 'r') as file:
            referrals_data = json.load(file)
    except json.JSONDecodeError:
        referrals_data = {}

    if str(user_id) in referrals_data:
        referrals_data[str(user_id)]['bonus_time'] += bonus_hours
        with open(referrals_file_path, 'w') as file:
            json.dump(referrals_data, file)

def apply_bonus_time(user_id):
    referrals_file_path = 'settings/referrals.json'
    users_file_path = 'settings/users.json'

    try:
        with open(referrals_file_path, 'r') as file:
            referrals_data = json.load(file)
    except json.JSONDecodeError:
        referrals_data = {}

    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    if str(user_id) in referrals_data and referrals_data[str(user_id)]['bonus_time'] > 0:
        bonus_hours = referrals_data[str(user_id)]['bonus_time']
        current_cooldown = users_data.get(str(user_id), {}).get('cooldown', 1440)
        new_cooldown = max(0, current_cooldown - bonus_hours * 60)
        users_data[str(user_id)]['cooldown'] = new_cooldown
        referrals_data[str(user_id)]['bonus_time'] = 0

        with open(users_file_path, 'w') as file:
            json.dump(users_data, file)
        with open(referrals_file_path, 'w') as file:
            json.dump(referrals_data, file)

        return True
    return False

def log_message(message: str):
    """Записывает сообщение в логи."""
    logging.info(message)

def load_bot_token():
    with open('settings/token.json', 'r') as file:
        data = json.load(file)
        return data['bot_token']
bot = telebot.TeleBot(load_bot_token())


def initialize_user(user_id):
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            'last_opened': None,
            'cooldown': 1440,  # Default cooldown is 24 hours (1440 minutes)
            'premium': False   # Default premium status
        }
        with open(users_file_path, 'w') as file:
            json.dump(users_data, file)

def get_current_time():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))

def is_premium(user_id):
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Если пользователя нет в базе или нет поля premium, считаем его обычным
    if str(user_id) not in users_data:
        return False

    user_data = users_data[str(user_id)]
    if not user_data.get('premium', False):
        return False

    # Проверяем, есть ли поле premium_expiration и не истекло ли время
    if 'premium_expiration' in user_data:
        expiration_time = datetime.datetime.fromisoformat(user_data['premium_expiration'])
        if get_current_time() > expiration_time:
            # Подписка истекла
            user_data['premium'] = False
            del user_data['premium_expiration']
            with open(users_file_path, 'w') as file:
                json.dump(users_data, file)
            return False

    return True

def is_day_opened(user_id):
    users_file_path = 'settings/users.json'
    if not os.path.exists(users_file_path):
        with open(users_file_path, 'w') as file:
            json.dump({}, file)

    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Если пользователя нет в данных или last_opened отсутствует/некорректен, считаем, что КД нет
    if str(user_id) not in users_data or not isinstance(users_data[str(user_id)].get('last_opened'), str):
        return False, None

    try:
        # Проверяем время последнего открытия и КД
        last_opened = datetime.datetime.fromisoformat(users_data[str(user_id)]['last_opened'])
        cooldown_minutes = users_data[str(user_id)]['cooldown']
        cooldown = datetime.timedelta(minutes=cooldown_minutes)
        next_open_time = last_opened + cooldown

        if get_current_time() < next_open_time:
            remaining_time = next_open_time - get_current_time()
            return True, remaining_time
        else:
            return False, None
    except (KeyError, ValueError):
        # Если данные повреждены, сбрасываем КД
        users_data[str(user_id)]['last_opened'] = None
        with open(users_file_path, 'w') as file:
            json.dump(users_data, file)
        return False, None

def mark_day_as_opened(user_id):
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    cooldown = 360 if users_data.get(str(user_id), {}).get('premium', False) else 1440

    users_data[str(user_id)] = {
        'last_opened': get_current_time().isoformat(),
        'cooldown': cooldown,
        'premium': is_premium(user_id)  # Обновляем статус Premium
    }
    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

@bot.message_handler(func=lambda message: message.text == "Админ-панель")
def admin_panel(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой панели.")
        return

    commands_info = (
        "/rkd [id] - Убрать КД на открытие дня для пользователя с указанным ID.\n"
        "/gtime [id] - Узнать, когда пользователь с указанным ID последний раз открывал день.\n"
        "/gkd [minutes] - Установить время КД на открытие дня (в минутах). "
        "0 - сбросить КД для всех, 1 - вернуть стандартное время (24 часа).\n"
        "/gad - Снять КД для администратора (бесконечный режим).\n"
        "/folders - Узнать какие есть хомяки\n"
        "👆 /folders [Имя] - Узнать видео хомяка по названию\n"
        "/gp [id] - Дать премиум по ID\n"
        "/gpt [id] [time] - Временная премиум [id]\n"
        "/rp [id] - Снять премиум по [ID]\n"
        "/cn [Имя] - Очистить статистику по имени хомяка\n"
        "/addvideo - homyak add\n"
        "/sth - редактирование хомяка\n"
        "/referrals [id] - Посмотреть рефералов пользователя\n"
    )
    bot.send_message(message.chat.id, f"Админ-панель: \n\n{commands_info}")

@bot.message_handler(commands=['referrals'])
def view_referrals(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /referrals [id]")
        return

    target_id = int(args[0])
    referral_data = get_referral_data(target_id)
    referrals = referral_data['referrals']
    bonus_time = referral_data['bonus_time']

    if not referrals:
        bot.send_message(message.chat.id, f"У пользователя {target_id} нет рефералов.")
    else:
        bot.send_message(
            message.chat.id,
            f"👥 Рефералы пользователя {target_id}:\n\n"
            f"{' '.join(map(str, referrals))}\n\n"
            f"⏰ Бонусное время: {bonus_time} часов"
        )

def is_admin(user_id):
    admins_file_path = 'settings/admins.json'
    try:
        with open(admins_file_path, 'r') as file:
            admins_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        admins_data = {'admins': []}  # Default to no admins if file is missing/corrupted
    return user_id in admins_data.get('admins', []) or user_id == ADMINS

@bot.message_handler(func=lambda message: message.text == "⭐️ Премиум-подписка")
def premium_sub(message):
    user_id = message.from_user.id

    if not is_premium(user_id):
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой панели.")
        return

    commands_info = (
        "КД на открытие хомяка раз в 6 часа\n"
        "Получение 2 хомяка за раз.\n\n"
        "Пока что это все, если есть идеи напишите мне в ЛС - @kittenello \n"
    )
    premium_status, remaining_time = is_premium_with_remaining_time(user_id)
    if premium_status:
        if remaining_time:
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes = remainder // 60
            premium_text = (
                f"⭐️ У вас есть Premium-подписка!\n"
                f"⏳ Осталось времени: {hours} ч. {minutes} мин."
                )
        else:
            premium_text = "⭐️ У вас есть Premium-подписка!\n⏳Осталось времени: LifeTime"
    else:
        premium_text = "💡 Не удалось определить вашу подписку, напишите владельцу!"
    bot.send_message(message.chat.id, f"Премиум способности:\n\n{commands_info}\n\n{premium_text}")

def send_admin_log(user_id, name_homyak):
    admin_chat_id = -1002334358016
    
    users_file_path = 'settings/opens.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {"counters": {"daily": {}, "weekly": {}}}

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y-%m-%d')
    week_start = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))) - datetime.timedelta(days=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).weekday())).strftime('%Y-%m-%d')

    daily_count = users_data['counters']['daily'].get(today, {}).get(name_homyak, 0)
    weekly_count = users_data['counters']['weekly'].get(week_start, {}).get(name_homyak, 0)


    user = bot.get_chat_member(user_id, user_id).user
    username = user.username or "Без имени"
    log_message = (
        f"📝 Лог выпадения хомяка:📝\n"
        f"📝 1. Никнейм: @{username} [ID: {user_id}]\n"
        f"📝 2. Выпавший хомяк: {name_homyak}\n"
        f"📝 3. Время выпадания: {get_current_time().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📝 5. Статистика выпадений:\n"
        f"   - За сегодня: {daily_count}\n"
        f"   - За неделю: {weekly_count}"
        )
    bot.send_message(
        admin_chat_id,
        f"{log_message}",
        message_thread_id=411  # Указываем ID топика
    )

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()

    # Инициализация данных пользователя
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            'last_opened': None,
            'cooldown': 1440,  # Default cooldown is 24 hours (1440 minutes)
            'premium': False   # Default premium status
        }
        with open(users_file_path, 'w') as file:
            json.dump(users_data, file)

    # Обработка реферальной ссылки
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id:  # Проверяем, чтобы пользователь не приглашал сам себя
            referrals_file_path = 'settings/referrals.json'
            try:
                with open(referrals_file_path, 'r') as file:
                    referrals_data = json.load(file)
            except json.JSONDecodeError:
                referrals_data = {}

            if str(referrer_id) in referrals_data and user_id not in referrals_data[str(referrer_id)]['referrals']:
                referrals_data[str(referrer_id)]['referrals'].append(user_id)
                update_bonus_time(referrer_id, -3)  # Уменьшаем КД на 3 часа
                with open(referrals_file_path, 'w') as file:
                    json.dump(referrals_data, file)

    premium_status, remaining_time = is_premium_with_remaining_time(user_id)
    if premium_status:
        if remaining_time:
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes = remainder // 60
            premium_text = (
                f"⭐️ У вас есть Premium-подписка!\n"
                f"⏳ Осталось времени: {hours} ч. {minutes} мин."
                )
        else:
            premium_text = "⭐️ У вас есть Premium-подписка!\n⏳Осталось времени: LifeTime"
    else:
        premium_text = "💡 Вы можете приобрести Premium-подписку. Для этого напишите @kittenello"
    #"💡 Вы можете приобрести Premium-подписку. Для этого пропишите /premium"

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = telebot.types.KeyboardButton("☀️ Открыть день")
    
    # Добавляем кнопку "⭐️ Премиум-подписка" для всех пользователей
    item2 = telebot.types.KeyboardButton("⭐️ Премиум-подписка")

    if user_id in ADMINS:
        item3 = telebot.types.KeyboardButton("Админ-панель")
        markup.add(item1, item2, item3)
    else:
        markup.add(item1, item2)

    # Формируем приветственное сообщение
    welcome_message = (
        f"⭐️ Добро пожаловать в Homyak Адвент-Календарь!\n\n"
        f"🎁 Каждый день Вас ждут любимые хомяки.\n"
        f"  └ Открывайте дни, чтобы узнать какой вы хомяк каждый день!\n\n"
        f"{premium_text}"
    )

    # Путь к видео welcome.mp4
    welcome_video_path = os.path.join(WELCOME, "welcome.mp4")

    # Проверяем наличие видео
    if os.path.exists(welcome_video_path):
        # Отправляем видео с текстом (caption)
        with open(welcome_video_path, 'rb') as video_file:
            bot.send_video(message.chat.id, video_file, caption=welcome_message, reply_markup=markup)
    else:
        # Если видео отсутствует, отправляем только текст
        msg = bot.send_message(message.chat.id, welcome_message, reply_markup=markup)
        user_states[message.from_user.id] = {'last_msg_id': msg.message_id, 'waiting_for_video': False}

def remaining_time_str(remaining_time):
    if remaining_time:
        hours, remainder = divmod(remaining_time.seconds, 3600)
        minutes = remainder // 60
        return f"{hours} ч. {minutes} мин."
    return "Навсегда"

@bot.message_handler(func=lambda message: message.text == "☀️ Открыть день")
def open_day(message):
    user_id = message.from_user.id

    # Инициализация состояния пользователя, если его нет в user_states
    if user_id not in user_states:
        user_states[user_id] = {'last_msg_id': None, 'waiting_for_video': False}

    is_opened, remaining_time = is_day_opened(user_id)
    if is_opened:
        hours, remainder = divmod(remaining_time.seconds, 3600)
        minutes = remainder // 60
        cooldown_text = f"{hours} ч. {minutes} мин."
        bot.send_message(message.chat.id, f"❌ Вы уже открывали этот день сегодня!\n✅ До следующего открытия: {cooldown_text}")
        return

    if user_states[user_id]['last_msg_id']:
        try:
            bot.delete_message(message.chat.id, user_states[user_id]['last_msg_id'])
        except Exception as e:
            print(f"Error deleting message: {e}")

    if not user_states[user_id]['waiting_for_video']:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = telebot.types.KeyboardButton("☀️ Открыть день")
        #item2 = telebot.types.KeyboardButton("🙏 Второй шанс")
        markup.add(item1)

        msg = bot.send_message(message.chat.id, "☀️ Открыть день - открывайте каждый день и узнавайте какой вы хомяк!\n🤔 Что может выпасть?\n - NONE", reply_markup=markup)
        user_states[user_id]['last_msg_id'] = msg.message_id
        user_states[user_id]['waiting_for_video'] = True
    else:
        send_video(message)

def send_video(message):
    user_id = message.from_user.id

    if 'last_msg_id' in user_states[user_id]:
        try:
            bot.delete_message(message.chat.id, user_states[user_id]['last_msg_id'])
        except Exception as e:
            print(f"Error deleting message: {e}")

    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith('.mp4')]
    if not videos:
        bot.send_message(message.chat.id, "❌ Ошибка!\nНет доступных видео для отправки. 😭")
        return

    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    is_premium = users_data.get(str(user_id), {}).get('premium', False)
    num_hamsters = 2 if is_premium else 1

    # Выбираем случайные видео
    selected_videos = random.sample(videos, min(num_hamsters, len(videos)))

    media = []
    hamster_names = []
    for video in selected_videos:
        media.append(telebot.types.InputMediaVideo(open(os.path.join(VIDEO_FOLDER, video), 'rb')))
        name_homyak = os.path.splitext(video)[0]
        hamster_names.append(name_homyak)

    # Корректное формирование сообщения
    if len(hamster_names) == 2:
        result_text = (
            f"😍 Сегодня вы: {hamster_names[0]} и {hamster_names[1]} Хомяк!\n\n"
            f"📊 Статистика:\n"
            f"- За сегодня: {update_counters(hamster_names[0])[0]} и {update_counters(hamster_names[1])[0]}\n"
            f"- За неделю: {update_counters(hamster_names[0])[1]} и {update_counters(hamster_names[1])[1]}"
        )
    else:
        result_text = (
            f"😍 Сегодня вы: {hamster_names[0]} Хомяк!\n\n"
            f"📊 Статистика:\n"
            f"- За сегодня: {update_counters(hamster_names[0])[0]}\n"
            f"- За неделю: {update_counters(hamster_names[0])[1]}"
        )

    # Отправляем видео вместе с текстом
    if media:
        bot.send_media_group(message.chat.id, media)
        bot.send_message(message.chat.id, result_text)

    # Логирование для администратора
    for name in hamster_names:
        send_admin_log(user_id, name)

    # Обновляем время последнего открытия дня
    mark_day_as_opened(user_id)

    # Сбрасываем состояние ожидания видео
    user_states[user_id]['waiting_for_video'] = False

def update_counters(name_homyak):
    users_file_path = 'settings/opens.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {"counters": {"daily": {}, "weekly": {}}}

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y-%m-%d')
    week_start = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))) - datetime.timedelta(days=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).weekday())).strftime('%Y-%m-%d')

    if 'counters' not in users_data:
        users_data['counters'] = {"daily": {}, "weekly": {}}

    if today not in users_data['counters']['daily']:
        users_data['counters']['daily'][today] = {}
    if name_homyak not in users_data['counters']['daily'][today]:
        users_data['counters']['daily'][today][name_homyak] = 0
    users_data['counters']['daily'][today][name_homyak] += 1

    if week_start not in users_data['counters']['weekly']:
        users_data['counters']['weekly'][week_start] = {}
    if name_homyak not in users_data['counters']['weekly'][week_start]:
        users_data['counters']['weekly'][week_start][name_homyak] = 0
    users_data['counters']['weekly'][week_start][name_homyak] += 1

    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

    return users_data['counters']['daily'][today][name_homyak], users_data['counters']['weekly'][week_start][name_homyak]

@bot.message_handler(commands=['addvideo'])
def add_video(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    bot.send_message(message.chat.id, "Пожалуйста, отправьте видео которое нужно добавить в бота.")
    bot.register_next_step_handler(message, handle_video_upload)

def handle_video_upload(message):
    if message.content_type != 'video':
        bot.send_message(message.chat.id, "Это не видео. Пожалуйста, отправьте видео.")
        return

    file_info = bot.get_file(message.video.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    bot.send_message(message.chat.id, "Как назвать этого хомяка?")
    bot.register_next_step_handler(message, lambda msg: handle_name_input(msg, downloaded_file))

def handle_name_input(message, video_data):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "Имя не может быть пустым. Попробуйте снова.")
        return

    file_path = os.path.join(VIDEO_FOLDER, f"{name}.mp4")
    with open(file_path, 'wb') as new_file:
        new_file.write(video_data)

    bot.send_message(message.chat.id, f"Видео успешно добавлено как '{name}'.")

@bot.message_handler(commands=['rkd'])
def reset_cooldown(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return
    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /rkd [id]")
        return
    user_id = int(args[0])
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}
    
    # Проверяем, существует ли пользователь
    if str(user_id) in users_data:
        # Сбрасываем только last_opened, сохраняя остальные данные
        users_data[str(user_id)]['last_opened'] = None
        with open(users_file_path, 'w') as file:
            json.dump(users_data, file)
        bot.send_message(message.chat.id, f"КД для пользователя {user_id} был сброшен.")
        bot.send_message(user_id, f"Вам сняли КД! Вы можете еще раз испытать удачу.")
    else:
        bot.send_message(message.chat.id, f"У пользователя {user_id} не было КД.")

@bot.message_handler(commands=['gtime'])
def get_last_opened_time(message):
    user_id = message.from_user.id
    user_id = message.from_user.id
    if user_id not in ADMINS:
        users_file_path = 'settings/users.json'
        try:
            with open(users_file_path, 'r') as file:
                users_data = json.load(file)
        except json.JSONDecodeError:
            users_data = {}
        if not users_data.get(str(user_id), {}).get('premium', False):
            bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
            return
    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /gtime [id]")
        return
    target_user_id = int(args[0])
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}
    
    # Проверяем, существует ли пользователь и есть ли поле last_opened
    if str(target_user_id) in users_data and 'last_opened' in users_data[str(target_user_id)]:
        last_opened = datetime.datetime.fromisoformat(users_data[str(target_user_id)]['last_opened'])
        bot.send_message(message.chat.id, f"Пользователь {target_user_id} последний раз открывал день в {last_opened.strftime('%H:%M:%S')}")
    else:
        bot.send_message(message.chat.id, f"У пользователя {target_user_id} нет записи о последнем открытии дня.")

@bot.message_handler(commands=['gkd'])
def set_cooldown(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return
    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /gkd [minutes]")
        return
    minutes = int(args[0])
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}
    
    if minutes == 0:
        # Сбрасываем КД для всех пользователей
        for user_id in list(users_data.keys()):
            users_data[user_id]['last_opened'] = None
        bot.send_message(message.chat.id, "КД на открытие дня сброшен для всех пользователей.")
    elif minutes == 1:
        # Возвращаем стандартное время КД
        for user_id in list(users_data.keys()):
            cooldown = 360 if users_data[user_id].get('premium', False) else 1440
            users_data[user_id]['cooldown'] = cooldown
        bot.send_message(message.chat.id, "Возвращено стандартное время открытия дня.")
    else:
        # Устанавливаем новое время КД
        for user_id in list(users_data.keys()):
            if not users_data[user_id].get('premium', False):  # Только для обычных пользователей
                users_data[user_id]['cooldown'] = minutes
        bot.send_message(message.chat.id, f"КД на открытие дня установлен на {minutes} минут для всех пользователей.")
    
    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

@bot.message_handler(commands=['rac'])
def reset_admin_cooldown(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Обновляем данные для каждого администратора
    for admin_id in ADMINS:
        users_data[str(admin_id)] = {
            'last_opened': None,  # Сбрасываем время последнего открытия
            'cooldown': 0         # Устанавливаем cooldown в 0
        }

    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

    bot.send_message(message.chat.id, "+")

@bot.message_handler(commands=['cn'])
def clear_counter(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1:
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /cn [name]")
        return

    name_homyak = args[0]
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith('.mp4')]
    video_names = [os.path.splitext(video)[0] for video in videos]

    if name_homyak not in video_names:
        bot.send_message(message.chat.id, f"Ошибка: Хомяк '{name_homyak}' не найден в списке видео.")
        return

    users_file_path = 'settings/opens.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {"counters": {"daily": {}, "weekly": {}}}
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%Y-%m-%d')
    week_start = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))) - datetime.timedelta(days=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).weekday())).strftime('%Y-%m-%d')

    if 'counters' not in users_data:
        users_data['counters'] = {"daily": {}, "weekly": {}}

    if today in users_data['counters']['daily'] and name_homyak in users_data['counters']['daily'][today]:
        del users_data['counters']['daily'][today][name_homyak]

    if week_start in users_data['counters']['weekly'] and name_homyak in users_data['counters']['weekly'][week_start]:
        del users_data['counters']['weekly'][week_start][name_homyak]

    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

    bot.send_message(message.chat.id, f"Счетчики для хомяка '{name_homyak}' успешно очищены.")

@bot.message_handler(commands=['folders'])
def list_or_send_hamsters(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith('.mp4')]

    if len(args) == 1:
        if not videos:
            bot.send_message(message.chat.id, "В папке нет видеофайлов.")
            return

        hamster_names = "\n".join([os.path.splitext(video)[0] for video in videos])
        bot.send_message(message.chat.id, f"Список доступных хомяков:\n{hamster_names}")
    elif len(args) == 2:
        name = args[1]
        matching_videos = [video for video in videos if os.path.splitext(video)[0] == name]

        if not matching_videos:
            bot.send_message(message.chat.id, f"Хомяк с именем '{name}' не найден.")
            return

        video_path = os.path.join(VIDEO_FOLDER, matching_videos[0])
        with open(video_path, 'rb') as file:
            bot.send_video(message.chat.id, file)
    else:
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /folders или /folders [name]")

@bot.message_handler(commands=['premium'])
def premium_info(message):
    user_id = message.from_user.id
    is_premium_status, remaining_time = is_premium_with_remaining_time(user_id)
    
    if is_premium_status:
        if remaining_time:
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes = remainder // 60
            premium_text = (
                f"⭐️ У вас есть Premium-подписка!\n"
                f"⏳ Осталось времени: {hours} ч. {minutes} мин.\n\n"
                "Возможности Premium:\n"
                "- Открывать хомяков можно раз в 3 часа (ранее 24 часа)\n"
                "- Доступ к команде /gtime [id] - посмотреть когда последний раз человек открывал хомяка\n"
                "- Выпадение сразу 2 хомяков за раз"
            )
        else:
            premium_text = (
                f"⭐️ У вас есть Premium-подписка!\n"
                f"⏳ Осталось времени: LifeTime\n\n"
                "Возможности Premium:\n"
                "- Открывать хомяков можно раз в 3 часа (ранее 24 часа)\n"
                "- Доступ к команде /gtime [id] - посмотреть когда последний раз человек открывал хомяка\n"
                "- Выпадение сразу 2 хомяков за раз"
            )
    else:
        premium_text = (
            "💡 У вас нет Premium-подписки.\n\n"
            "🌟 Premium-подписка 🌟\n\n"
            "Стоимость: 20 рублей\n"
            "Преимущества:\n"
            "- Открывать день можно раз в 3 часа.\n"
            "- Доступ к команде /gtime.\n"
            "- Выпадение сразу 2 хомяков за раз.\n\n"
            "Для покупки Premium вы должны связаться с @kittenello"
        )
    
    bot.send_message(message.chat.id, premium_text)


@bot.message_handler(commands=['gpt'])
def give_premium_time(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) < 3 or not args[0].isdigit() or not args[1].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /gpt [id] [hours] [reason]")
        return

    user_id = int(args[0])
    hours = int(args[1])
    reason_prem = ' '.join(args[2:])  # Объединяем все оставшиеся аргументы в строку (причина)

    expiration_time = get_current_time() + datetime.timedelta(hours=hours)
    users_file_path = 'settings/users.json'

    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Добавляем пользователя с временной подпиской
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            'last_opened': None,
            'cooldown': 360,  # Default cooldown for Premium
            'premium': True,
            'premium_expiration': expiration_time.isoformat(),
            'premium_reason': reason_prem  # Сохраняем причину
        }
    else:
        users_data[str(user_id)]['premium'] = True
        users_data[str(user_id)]['premium_expiration'] = expiration_time.isoformat()
        users_data[str(user_id)]['premium_reason'] = reason_prem  # Обновляем причину

    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

    bot.send_message(message.chat.id, f"Premium-подписка успешно выдана пользователю {user_id} на {hours} часов.")
    bot.send_message(user_id, f"❗Вам была выдана временная Premium-подписка на {hours} час(-ов)\n😎 Причина выдачи подписки: {reason_prem}]")

@bot.message_handler(commands=['rp'])
def remove_premium(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /rp [id]")
        return

    user_id = int(args[0])
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Проверяем, существует ли пользователь
    if str(user_id) not in users_data:
        bot.send_message(message.chat.id, f"Пользователь {user_id} не найден.")
        return

    # Снимаем Premium-статус
    users_data[str(user_id)]['premium'] = False
    users_data[str(user_id)]['cooldown'] = 1440  # Возвращаем стандартный КД

    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

    bot.send_message(message.chat.id, f"Premium-подписка успешно снята у пользователя {user_id}.")
    bot.send_message(user_id, f"😭 Вам сняли Premium-подписку.")

@bot.message_handler(commands=['gp'])
def give_premium(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /gp [id]")
        return

    user_id = int(args[0])
    users_file_path = 'settings/users.json'

    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Добавляем пользователя с premium = True
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            'last_opened': None,
            'cooldown': 360,  # Default cooldown for Premium
            'premium': True
        }
    else:
        users_data[str(user_id)]['premium'] = True
        # Удаляем поле premium_expiration, чтобы избежать конфликта с временной подпиской
        if 'premium_expiration' in users_data[str(user_id)]:
            del users_data[str(user_id)]['premium_expiration']

    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

    bot.send_message(message.chat.id, f"Premium-подписка успешно выдана пользователю {user_id}.")
    bot.send_message(user_id, f"🤩 Вы получили Premium-подписку сроком навсегда.")

@bot.message_handler(commands=['chp'])
def check_premium(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /chp [id]")
        return

    user_id = int(args[0])
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Проверяем, существует ли пользователь
    if str(user_id) not in users_data:
        bot.send_message(message.chat.id, f"Пользователь {user_id} не найден.")
        return

    user_data = users_data[str(user_id)]
    premium_status = user_data.get('premium', False)

    if not premium_status:
        bot.send_message(message.chat.id, f"У пользователя {user_id} нет Premium-подписки.")
        return

    # Если подписка временная, проверяем время истечения
    if 'premium_expiration' in user_data:
        expiration_time = datetime.datetime.fromisoformat(user_data['premium_expiration'])
        if get_current_time() > expiration_time:
            # Подписка истекла
            user_data['premium'] = False
            del user_data['premium_expiration']
            with open(users_file_path, 'w') as file:
                json.dump(users_data, file)
            bot.send_message(message.chat.id, f"У пользователя {user_id} больше нет Premium-подписки (истек срок действия).")
            return

        expiration_time_str = expiration_time.strftime('%Y-%m-%d %H:%M:%S')
        bot.send_message(message.chat.id, f"У пользователя {user_id} есть временная Premium-подписка до {expiration_time_str}.")
    else:
        bot.send_message(message.chat.id, f"У пользователя {user_id} есть постоянная Premium-подписка.")

def is_premium_with_remaining_time(user_id):
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Если пользователя нет в базе или нет поля premium, считаем его обычным
    if str(user_id) not in users_data:
        return False, None

    user_data = users_data[str(user_id)]
    if not user_data.get('premium', False):
        return False, None

    # Проверяем, есть ли поле premium_expiration и не истекло ли время
    if 'premium_expiration' in user_data:
        expiration_time = datetime.datetime.fromisoformat(user_data['premium_expiration'])
        if get_current_time() > expiration_time:
            # Подписка истекла
            user_data['premium'] = False
            del user_data['premium_expiration']
            with open(users_file_path, 'w') as file:
                json.dump(users_data, file)
            return False, None

        remaining_time = expiration_time - get_current_time()
        return True, remaining_time

    return True, None


@bot.message_handler(commands=['sth'])
def manage_hamsters(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith('.mp4')]
    if not videos:
        bot.send_message(message.chat.id, "❌ В папке нет видеофайлов.")
        return

    # Берем последние 5 хомяков
    last_5_videos = videos[-5:]
    last_5_names = [os.path.splitext(video)[0] for video in last_5_videos]

    # Создаем инлайн-клавиатуру
    markup = InlineKeyboardMarkup(row_width=1)
    for name in last_5_names:
        button = InlineKeyboardButton(f"Выбрать {name}", callback_data=f"select_{name}")
        markup.add(button)

    # Добавляем кнопку "Поиск"
    search_button = InlineKeyboardButton("🔍 Поиск", callback_data="search_hamster")
    markup.add(search_button)

    bot.send_message(message.chat.id, "Выберите хомяка для управления или воспользуйтесь поиском:", reply_markup=markup)

def handle_search_input(message):
    query = message.text.strip().lower()
    videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith('.mp4')]
    matching_names = [os.path.splitext(video)[0] for video in videos if query in os.path.splitext(video)[0].lower()]

    if not matching_names:
        bot.send_message(message.chat.id, "❌ Хомяки с таким именем не найдены.")
        return

    # Создаем клавиатуру с найденными хомяками
    markup = InlineKeyboardMarkup(row_width=1)
    for name in matching_names:
        button = InlineKeyboardButton(f"Это {name}?", callback_data=f"confirm_{name}")
        markup.add(button)

    bot.send_message(message.chat.id, "Найдены следующие хомяки:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "search_hamster")
def search_hamster(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Введите полное или частичное имя хомяка:")
    bot.register_next_step_handler(call.message, handle_search_input)


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
def handle_hamster_selection(call):
    hamster_name = call.data.split("_", 1)[1]

    # Создаем инлайн-клавиатуру с действиями
    markup = InlineKeyboardMarkup(row_width=1)
    button_delete = InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{hamster_name}")
    button_rename = InlineKeyboardButton("📝 Переименовать", callback_data=f"rename_{hamster_name}")
    button_test = InlineKeyboardButton("▶️ Тестовое получение", callback_data=f"test_{hamster_name}")
    markup.add(button_delete, button_rename, button_test)

    bot.edit_message_text(
        f"Выбран хомяк: {hamster_name}\nВыберите действие:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_hamster(call):
    hamster_name = call.data.split("_", 1)[1]
    file_path = os.path.join(VIDEO_FOLDER, f"{hamster_name}.mp4")

    if os.path.exists(file_path):
        os.remove(file_path)
        bot.answer_callback_query(call.id, f"Хомяк '{hamster_name}' удален.")
        bot.edit_message_text(f"Хомяк '{hamster_name}' успешно удален.", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Ошибка: файл не найден.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("rename_"))
def rename_hamster_prompt(call):
    hamster_name = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, f"Введите новое имя для хомяка '{hamster_name}':")
    bot.register_next_step_handler(call.message, lambda msg: rename_hamster(msg, hamster_name))

def rename_hamster(message, old_name):
    new_name = message.text.strip()
    if not new_name:
        bot.send_message(message.chat.id, "Имя не может быть пустым. Попробуйте снова.")
        return

    old_file_path = os.path.join(VIDEO_FOLDER, f"{old_name}.mp4")
    new_file_path = os.path.join(VIDEO_FOLDER, f"{new_name}.mp4")

    if os.path.exists(old_file_path):
        os.rename(old_file_path, new_file_path)
        bot.send_message(message.chat.id, f"Хомяк '{old_name}' успешно переименован в '{new_name}'.")
    else:
        bot.send_message(message.chat.id, "Ошибка: файл не найден.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("test_"))
def test_hamster(call):
    hamster_name = call.data.split("_", 1)[1]
    file_path = os.path.join(VIDEO_FOLDER, f"{hamster_name}.mp4")

    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            bot.send_video(call.message.chat.id, file)
            bot.answer_callback_query(call.id, f"Тестовое видео хомяка '{hamster_name}' отправлено.")
    else:
        bot.answer_callback_query(call.id, "Ошибка: файл не найден.")

@bot.message_handler(commands=['makeadmin'])
def make_admin(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return
    
    if user_id in ADMINS:
        bot.send_message(message.chat.id, f"я это временно вырезал")

@bot.message_handler(commands=['unadmin'])
def unmake_admin(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 1:
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /unadmin [id]")
        return

    target_id = int(args[0])
    admins_file_path = 'settings/admins.json'

    try:
        with open(admins_file_path, 'r') as file:
            admins_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        admins_data = {'admins': []}

    if target_id not in admins_data.get('admins', []):
        bot.send_message(message.chat.id, f"Пользователь {target_id} не является администратором.")
        return

    admins_data['admins'].remove(target_id)
    with open(admins_file_path, 'w') as file:
        json.dump(admins_data, file)

    bot.send_message(message.chat.id, f"Пользователь {target_id} больше не является администратором.")
    bot.send_message(target_id, "🔒 Ваш статус администратора был снят.")

def is_admin(user_id):
    admins_file_path = 'settings/admins.json'
    try:
        with open(admins_file_path, 'r') as file:
            admins_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        admins_data = {'admins': []}  # Если файл не существует или поврежден

    return user_id in admins_data.get('admins', []) or user_id == ADMINS

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def confirm_hamster(call):
    hamster_name = call.data.split("_", 1)[1]

    # Создаем инлайн-клавиатуру с действиями
    markup = InlineKeyboardMarkup(row_width=1)
    button_delete = InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{hamster_name}")
    button_rename = InlineKeyboardButton("📝 Переименовать", callback_data=f"rename_{hamster_name}")
    button_test = InlineKeyboardButton("▶️ Тестовое получение", callback_data=f"test_{hamster_name}")
    markup.add(button_delete, button_rename, button_test)

    bot.edit_message_text(
        f"Вы выбрали хомяка: {hamster_name}\nВыберите действие:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.message_handler(commands=['premiumtop'])
def premium_top(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    # Инициализируем списки для разных типов подписок
    permanent_premium_users = []
    temporary_premium_users = []

    # Проходим по всем пользователям
    for user_id, user_data in users_data.items():
        if user_data.get('premium', False):  # Если у пользователя есть премиум
            expiration_time = user_data.get('premium_expiration')
            if expiration_time:  # Если подписка временная
                expiration_date = datetime.datetime.fromisoformat(expiration_time)
                remaining_time = expiration_date - get_current_time()
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes = remainder // 60
                try:
                    user = bot.get_chat_member(user_id, user_id).user
                    username = f"@{user.username}" if user.username else "Без имени"
                    temporary_premium_users.append(
                        f"{username} [ID: {user_id}] — Окончание через {hours} ч. {minutes} мин."
                    )
                except Exception as e:
                    print(f"Ошибка получения данных о пользователе {user_id}: {e}")
            else:  # Если подписка постоянная
                try:
                    user = bot.get_chat_member(user_id, user_id).user
                    username = f"@{user.username}" if user.username else "Без имени"
                    permanent_premium_users.append(f"{username} [ID: {user_id}]")
                except Exception as e:
                    print(f"Ошибка получения данных о пользователе {user_id}: {e}")

    # Формируем сообщение
    premium_top_message = "🌟 Список пользователей с Premium-подпиской:\n\n"

    if permanent_premium_users:
        premium_top_message += "✨ Постоянные подписчики:\n"
        premium_top_message += "\n".join(permanent_premium_users) + "\n\n"
    else:
        premium_top_message += "✨ Постоянные подписчики: Нет\n\n"

    if temporary_premium_users:
        premium_top_message += "⏳ Временные подписчики:\n"
        premium_top_message += "\n".join(temporary_premium_users) + "\n\n"
    else:
        premium_top_message += "⏳ Временные подписчики: Нет\n\n"

    bot.send_message(message.chat.id, premium_top_message)

@bot.message_handler(commands=['s'])
def send_as_bot(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /s [сообщение]")
        return

    custom_message = args[1]
    bot.send_message(message.chat.id, custom_message)

def generate_promocode(length=8):
    chars = string.ascii_uppercase + string.digits  # Используем буквы и цифры
    while True:
        promocode = ''.join(random.choices(chars, k=length))  # Генерируем промокод
        promocodes_file_path = 'settings/promocodes.json'
        try:
            with open(promocodes_file_path, 'r') as file:
                promocodes_data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            promocodes_data = {}
        if promocode not in promocodes_data:  # Проверяем уникальность промокода
            return promocode

@bot.message_handler(commands=['usepromo'])
def use_promo(message):
    args = message.text.split()[1:]
    if len(args) != 1:
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /usepromo [promocode]")
        return

    promocode = args[0]
    user_id = message.from_user.id
    promocodes_file_path = 'settings/promocodes.json'
    users_file_path = 'settings/users.json'

    try:
        with open(promocodes_file_path, 'r') as file:
            promocodes_data = json.load(file)
    except json.JSONDecodeError:
        promocodes_data = {}

    if promocode not in promocodes_data:
        bot.send_message(message.chat.id, "Промокод не найден или уже использован.")
        return

    promo_data = promocodes_data[promocode]
    if promo_data['activations'] <= 0:
        bot.send_message(message.chat.id, "Промокод больше нельзя активировать.")
        del promocodes_data[promocode]
        with open(promocodes_file_path, 'w') as file:
            json.dump(promocodes_data, file)
        return

    # Уменьшаем количество активаций промокода
    promo_data['activations'] -= 1
    with open(promocodes_file_path, 'w') as file:
        json.dump(promocodes_data, file)

    # Инициализируем пользователя
    initialize_user(user_id)

    # Обновляем данные пользователя
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}

    if promo_data['type'] == 1:  # Premium-подписка
        if promo_data['duration'] == 0.01:  # Вечная подписка
            users_data[str(user_id)]['premium'] = True
            if 'premium_expiration' in users_data[str(user_id)]:
                del users_data[str(user_id)]['premium_expiration']
            bot.send_message(message.chat.id, "Вы получили вечную Premium-подписку!")
        else:  # Временная подписка
            expiration_time = get_current_time() + datetime.timedelta(hours=promo_data['duration'])
            users_data[str(user_id)]['premium'] = True
            users_data[str(user_id)]['premium_expiration'] = expiration_time.isoformat()
            bot.send_message(
                message.chat.id,
                f"Вы получили временную Premium-подписку!\nОна будет действовать до {expiration_time.strftime('%Y-%m-%d %H:%M:%S')}."
            )
            user = bot.get_chat_member(user_id, user_id).user
            username = user.username or "Без имени"
            bot.send_message(
                MAIN_CHAT,
                f"bro {username}[ID: {user}] used promo {promocode}"
            )

    with open(users_file_path, 'w') as file:
        json.dump(users_data, file)

def is_premium_with_remaining_time(user_id):
    users_file_path = 'settings/users.json'
    try:
        with open(users_file_path, 'r') as file:
            users_data = json.load(file)
    except json.JSONDecodeError:
        users_data = {}
    
    # Если пользователя нет в базе или нет поля premium, считаем его обычным
    if str(user_id) not in users_data:
        return False, None
    
    user_data = users_data[str(user_id)]
    if not user_data.get('premium', False):
        return False, None
    
    # Проверяем, есть ли поле premium_expiration и не истекло ли время
    if 'premium_expiration' in user_data:
        expiration_time = datetime.datetime.fromisoformat(user_data['premium_expiration'])
        if get_current_time() > expiration_time:
            # Подписка истекла
            user_data['premium'] = False
            del user_data['premium_expiration']
            with open(users_file_path, 'w') as file:
                json.dump(users_data, file)
            return False, None
        
        remaining_time = expiration_time - get_current_time()
        return True, remaining_time
    
    # Если нет premium_expiration, значит подписка вечная
    return True, None

@bot.message_handler(commands=['logs'])
def get_logs(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    log_file_path = os.path.join(LOGS_DIR, "bot.log")
    if not os.path.exists(log_file_path):
        bot.send_message(message.chat.id, "Логи пока отсутствуют.")
        return

    # Определяем время 24 часа назад
    one_day_ago = datetime.datetime.now() - timedelta(days=1)

    try:
        with open(log_file_path, 'r', encoding='utf-8') as file:
            logs = file.readlines()

        # Фильтруем логи за последние 24 часа
        filtered_logs = []
        for line in logs:
            try:
                log_time = datetime.datetime.strptime(line[:19], '%Y-%m-%d %H:%M:%S')
                if log_time > one_day_ago:
                    filtered_logs.append(line)
            except ValueError:
                continue

        # Проверяем, есть ли записи за последние 24 часа
        if not filtered_logs:
            bot.send_message(message.chat.id, "За последние 24 часа логов нет.")
            return

        # Сохраняем фильтрованные логи во временный файл
        temp_log_file = os.path.join(LOGS_DIR, "last_24_hours_logs.txt")
        with open(temp_log_file, 'w', encoding='utf-8') as temp_file:
            temp_file.writelines(filtered_logs)

        # Отправляем файл пользователю
        with open(temp_log_file, 'rb') as log_file:
            bot.send_document(message.chat.id, log_file, caption="Логи за последние 24 часа")

        # Удаляем временный файл
        os.remove(temp_log_file)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при чтении логов: {e}")

@bot.inline_handler(func=lambda query: True)
def query_text(inline_query):
    try:
        text = inline_query.query
        if not text:
            return

        # Заменяем нужные буквы
        modified_text = text.replace('в', 'V').replace('з', 'Z').replace('с', 'Z').replace('о', 'О')
        
        r = types.InlineQueryResultArticle(
            id='1',
            title=f"Введи текст для конвертации патриота",
            input_message_content=types.InputTextMessageContent(message_text=f"{modified_text}")
        )
        bot.answer_inline_query(inline_query.id, results=[r])
    except Exception as e:
        print(e)

# Создание промокода
@bot.message_handler(commands=['createpromo'])
def create_promo(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 3 or not args[0].isdigit() or not args[1].isdigit() or not args[2].replace('.', '', 1).isdigit():
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /createpromo [кол-во активаций] [тип приза(1)] [время/кол-во]")
        return

    activations = int(args[0])  # Кол-во активаций
    prize_type = int(args[1])   # Тип приза (1 или 2)
    duration = float(args[2])   # Время действия (в часах) или количество шансов

    if prize_type not in [1]:
        bot.send_message(message.chat.id, "Тип приза может быть только 1")
        return

    promocodes_file_path = 'settings/promocodes.json'
    try:
        with open(promocodes_file_path, 'r') as file:
            promocodes_data = json.load(file)
    except json.JSONDecodeError:
        promocodes_data = {}

    # Генерируем уникальный промокод
    promocode = generate_promocode()
    while promocode in promocodes_data:
        promocode = generate_promocode()

    # Сохраняем данные промокода
    promocodes_data[promocode] = {
        'activations': activations,
        'type': prize_type,
        'duration': duration
    }

    with open(promocodes_file_path, 'w') as file:
        json.dump(promocodes_data, file)

    bot.send_message(message.chat.id, f"✅ Промокод успешно создан: {promocode}\nТип приза: Premium-подписка\nКол-во активаций: {activations}\n{'Время действия (ч): ' + str(duration)}\n\n/usepromo {promocode}")

@bot.message_handler(commands=['addrf'])
def add_referrals(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 2:
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /addrf [id/@tag] [count]")
        return

    target_id = resolve_user_id(args[0])
    if target_id is None:
        bot.send_message(message.chat.id, "❌ Неверный ID или @tag пользователя.")
        return

    try:
        count = int(args[1])
        if count <= 0:
            raise ValueError()

        referrals_file_path = 'settings/referrals.json'
        try:
            with open(referrals_file_path, 'r') as file:
                referrals_data = json.load(file)
        except json.JSONDecodeError:
            referrals_data = {}

        if str(target_id) not in referrals_data:
            referrals_data[str(target_id)] = {'referrals': [], 'bonus_time': 0}

        referrals_data[str(target_id)]['referrals'].extend([f"fake_ref_{i}" for i in range(count)])
        with open(referrals_file_path, 'w') as file:
            json.dump(referrals_data, file)

        bot.send_message(message.chat.id, f"✅ Добавлено {count} рефералов для пользователя {target_id}.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Количество должно быть положительным числом.")

@bot.message_handler(commands=['addtime'])
def add_bonus_time_admin(message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()[1:]
    if len(args) != 2:
        bot.send_message(message.chat.id, "Неверный формат команды. Используйте /addtime [id/@tag] [count]")
        return

    target_id = resolve_user_id(args[0])
    if target_id is None:
        bot.send_message(message.chat.id, "❌ Неверный ID или @tag пользователя.")
        return

    try:
        hours = int(args[1])
        if hours <= 0:
            raise ValueError()

        update_bonus_time(target_id, hours)
        bot.send_message(message.chat.id, f"✅ Добавлено {hours} часов бонусного времени для пользователя {target_id}.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Количество часов должно быть положительным числом.")

def resolve_user_id(input_str):
    if input_str.startswith('@'):
        try:
            user_info = bot.get_chat(input_str)
            return user_info.id
        except Exception:
            return None
    elif input_str.isdigit():
        return int(input_str)
    return None

@bot.message_handler(commands=['storage'])
def storage(message):
    user_id = message.from_user.id

    # Получаем данные реферальной системы
    referral_data = get_referral_data(user_id)
    referrals = referral_data['referrals']
    bonus_time = referral_data['bonus_time']

    # Генерация реферальной ссылки
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    bot.send_message(
        message.chat.id,
        f"📦 Ваш склад:\n\n"
        f"👥 Приглашено рефералов: {len(referrals)}\n"
        f"⏰ Бонусное время: {bonus_time} часов\n\n"
        f"🔗 Ваша реферальная ссылка:\n{referral_link}\n\n"
        f"Пригласите друзей по вашей ссылке, и получайте -3 часа к КД за каждого!"
    )
    
@bot.message_handler(func=lambda message: message.text == "📦 Использовать")
def apply_bonus(message):
    user_id = message.from_user.id

    referral_data = get_referral_data(user_id)
    bonus_time = referral_data['bonus_time']

    if bonus_time <= 0:
        bot.send_message(message.chat.id, "❌ У вас нет доступного бонусного времени.")
        return

    msg = bot.send_message(
        message.chat.id,
        "Введите количество часов, которое вы хотите использовать (максимум: {}):".format(bonus_time)
    )
    bot.register_next_step_handler(msg, process_apply_bonus, bonus_time)

if __name__ == '__main__':
    user_states = {}
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)  # Увеличиваем таймаут до 60 секунд
        except requests.exceptions.ConnectionError as e:
            MAIN_TOPIC_LOGS = 3
            current_time = datetime.datetime.now().time()
            bot.send_message(MAIN_CHAT, f"[TIME: {current_time}] бооо, что-то с ботом ужасно происходит: \n\n{e}\n\n @kittenello", message_thread_id=MAIN_TOPIC_LOGS)
            print(f"Ошибка подключения: {e}. Повторная попытка через 5 секунд...")
            import time
            time.sleep(5)  # Ждем 5 секунд перед повторной попыткой