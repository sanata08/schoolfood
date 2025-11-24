import sqlite3
import os
from datetime import datetime, time
import telebot

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = os.environ.get('8549278171:AAHSCYnVBVqo-ZHVHclJpBo53bd10rsxmOs')
CHAT_ID_STOLOVAYA = None
ADMIN_ID = 1085832439  # Замени на реальный ID

bot = telebot.TeleBot(API_TOKEN)

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('food_data.db', check_same_thread=False)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            free INTEGER NOT NULL,
            paid INTEGER NOT NULL,
            date TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_report(class_name, free, paid, user_id):
    """Добавляет или обновляет отчет по классу за сегодня."""
    today = datetime.now().date().isoformat()
    
    conn = sqlite3.connect('food_data.db', check_same_thread=False)
    cur = conn.cursor()
    
    # Проверяем, есть ли уже отчет от этого класса за сегодня
    cur.execute('SELECT id FROM reports WHERE class_name = ? AND date = ?', (class_name, today))
    existing = cur.fetchone()
    
    if existing:
        # Обновляем существующую запись
        cur.execute('''
            UPDATE reports SET free = ?, paid = ?, user_id = ? 
            WHERE class_name = ? AND date = ?
        ''', (free, paid, user_id, class_name, today))
    else:
        # Добавляем новую запись
        cur.execute('''
            INSERT INTO reports (class_name, free, paid, date, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (class_name, free, paid, today, user_id))
    
    conn.commit()
    conn.close()

def get_today_report():
    """Возвращает все отчеты за сегодняшний день."""
    today = datetime.now().date().isoformat()
    conn = sqlite3.connect('food_data.db', check_same_thread=False)
    cur = conn.cursor()
    cur.execute('''
        SELECT class_name, free, paid FROM reports 
        WHERE date = ? 
        ORDER BY class_name
    ''', (today,))
    data = cur.fetchall()
    conn.close()
    return data

def is_editing_allowed():
    """Проверяет, разрешено ли редактирование данных (до 9:00)."""
    now = datetime.now().time()
    return now <= time(22, 0)  # True если время ДО 9:00 включительно

def get_time_until_deadline():
    """Возвращает строку с оставшимся временем до дедлайна."""
    now = datetime.now()
    deadline = datetime.combine(now.date(), time(9, 0))
    
    if now > deadline:
        return "⏰ Время сдачи данных истекло в 9:00"
    else:
        time_left = deadline - now
        minutes = int(time_left.total_seconds() // 60)
        return f"⏳ До окончания сбора данных: {minutes} минут"

# --- КОМАНДЫ БОТА ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Отправляет приветственное сообщение."""
    time_info = get_time_until_deadline()
    
    welcome_text = f"""
Привет! Я бот для учета питания в школьной столовой.

{time_info}

**Как передать сведения по классу:**
Напиши сообщение в формате:
`Класс Кол-воБесплатно Кол-воПлатно`

**Например:**
`5А 15 10`
`10Б 2 18`

*Внимание: редактирование данных доступно только до 9:00 утра!*
    """
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['time'])
def check_time(message):
    """Показывает оставшееся время до дедлайна."""
    time_info = get_time_until_deadline()
    bot.reply_to(message, time_info)

@bot.message_handler(commands=['report'])
def send_report(message):
    """Формирует и отправляет сводную ведомость (только для администратора)."""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
        return

    data = get_today_report()
    if not data:
        bot.send_message(message.chat.id, "На сегодня данных еще нет.")
        return

    # Формируем красивый отчет в виде таблицы
    report_text = "🍽 *СВОДНАЯ ВЕДОМОСТЬ НА ПИТАНИЕ*\n"
    report_text += f"*Дата:* {datetime.now().strftime('%d.%m.%Y')}\n"
    
    # Добавляем статус редактирования
    if is_editing_allowed():
        report_text += "*Статус:* ✅ Прием данных открыт (до 9:00)\n\n"
    else:
        report_text += "*Статус:* ❌ Прием данных закрыт (после 9:00)\n\n"
    
    report_text += "```\n"
    report_text += "Класс | Беспл. | Плат. | Всего\n"
    report_text += "------|---------|-------|-------\n"
    
    total_free = 0
    total_paid = 0
    total_all = 0

    for row in data:
        class_name, free, paid = row
        total = free + paid
        report_text += f"{class_name:5} | {free:7} | {paid:5} | {total:5}\n"
        total_free += free
        total_paid += paid
        total_all += total

    report_text += "------|---------|-------|-------\n"
    report_text += f"ИТОГО | {total_free:7} | {total_paid:5} | {total_all:5}\n"
    report_text += "```"

    bot.send_message(message.chat.id, report_text, parse_mode='Markdown')

    if CHAT_ID_STOLOVAYA:
        bot.send_message(CHAT_ID_STOLOVAYA, report_text, parse_mode='Markdown')

@bot.message_handler(commands=['getmyid'])
def get_my_id(message):
    bot.reply_to(message, f"Ваш ID: `{message.from_user.id}`", parse_mode='Markdown')

# --- ОБРАБОТКА ОСНОВНЫХ СООБЩЕНИЙ ---
@bot.message_handler(func=lambda message: True)
def handle_data(message):
    """Обрабатывает сообщения с данными о питании."""
    
    # ПРОВЕРКА ВРЕМЕНИ - ГЛАВНОЕ ИЗМЕНЕНИЕ!
    if not is_editing_allowed():
        bot.reply_to(message, "❌ *Редактирование данных закрыто!*\n\nПрием данных осуществляется только до 9:00 утра. Для внесения изменений обратитесь к дежурному администратору.", parse_mode='Markdown')
        return
    
    user_id = message.from_user.id
    text = message.text.strip()

    # Проверяем формат сообщения
    parts = text.split()
    if len(parts) != 3:
        time_info = get_time_until_deadline()
        bot.reply_to(message, f"{time_info}\n\n❌ Неверный формат. Используй: `Класс Бесплатно Платно`\nНапример: `5А 15 10`", parse_mode='Markdown')
        return

    class_name, str_free, str_paid = parts

    try:
        free = int(str_free)
        paid = int(str_paid)
        if free < 0 or paid < 0:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Количество должно быть целым положительным числом.")
        return

    # Сохраняем данные в базу
    add_report(class_name, free, paid, user_id)

    # Подтверждаем прием данных с информацией о времени
    time_info = get_time_until_deadline()
    bot.reply_to(message, f"✅ Данные для {class_name} класса приняты!\nБесплатно: {free}, Платно: {paid}\n\n{time_info}")

# --- ЗАПУСК БОТА ---
if __name__ == '__main__':
    init_db()
    print("Бот запущен...")
    bot.polling(none_stop=True)