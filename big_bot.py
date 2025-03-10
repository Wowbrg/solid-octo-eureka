import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import logging
import asyncio
from datetime import datetime, timedelta
import pytz, os

# Настройка логирования (только ошибки)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.ERROR)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = os.getenv('TOKEN')

# Хранилище данных пользователей
user_data = {}

# Главное меню на клавиатуре
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("📋 Главное меню"), KeyboardButton("⚙️ Настройки")]],
    resize_keyboard=True
)

# Генерация математического примера
def generate_example(user_id):
    settings = user_data[user_id].get('settings', {'difficulty': 'medium', 'operations': ['+', '-', '*', '/']})
    difficulty = settings['difficulty']
    operations = settings['operations']

    op = random.choice(operations)
    if difficulty == 'easy':
        range_max = 20
    elif difficulty == 'medium':
        range_max = 100
    else:  # hard
        range_max = 500

    if op == '+':
        a, b = random.randint(1, range_max), random.randint(1, range_max)
        answer = a + b
    elif op == '-':
        a, b = random.randint(1, range_max), random.randint(1, range_max)
        a, b = max(a, b), min(a, b)
        answer = a - b
    elif op == '*':
        a, b = random.randint(1, range_max // 10), random.randint(1, range_max // 10)
        answer = a * b
    else:  # '/'
        answer = random.randint(1, range_max // 10)
        b = random.randint(1, range_max // 10)
        a = answer * b
    return f"{a} {op} {b}", answer

# Создание изображения с примером
def create_example_image(example):
    img = Image.new('RGB', (300, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default(size=40)
    d.text((10, 30), example, font=font, fill=(0, 0, 0))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# Команда /start
async def start(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        return
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            'correct': 0, 'total': 0, 'current_example': None, 'current_answer': None,
            'settings': {'difficulty': 'medium', 'operations': ['+', '-', '*', '/'], 'time_limit': 30},
            'last_message_time': None, 'timer_task': None
        }
    await update.message.reply_text(
        "✨ Привет! Я бот для тренировки устного счета! ✨\n"
        "Нажми '📋 Главное меню' или используй /menu.",
        reply_markup=MAIN_MENU_KEYBOARD
    )

# Команда /menu
async def menu(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        return
    user_id = update.message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {
            'correct': 0, 'total': 0, 'current_example': None, 'current_answer': None,
            'settings': {'difficulty': 'medium', 'operations': ['+', '-', '*', '/'], 'time_limit': 30},
            'last_message_time': None, 'timer_task': None
        }
    keyboard = [
        [InlineKeyboardButton("🏋️ Начать тренировку", callback_data='start_training')],
        [InlineKeyboardButton("📊 Статистика", callback_data='show_stats')]
    ]
    await update.message.reply_text("🎉 Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

# Настройки
async def settings_menu(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        return
    user_id = update.message.from_user.id
    settings = user_data[user_id]['settings']
    keyboard = [
        [InlineKeyboardButton("Уровень сложности", callback_data='set_difficulty')],
        [InlineKeyboardButton("Выбрать операции", callback_data='set_operations')],
        [InlineKeyboardButton("Установить время (сек)", callback_data='set_time')],
        [InlineKeyboardButton("↩️ В меню", callback_data='back')]
    ]
    await update.message.reply_text(
        f"⚙️ Настройки:\n"
        f"Сложность: {settings['difficulty']}\n"
        f"Операции: {', '.join(settings['operations'])}\n"
        f"Время: {settings['time_limit']} сек",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Таймер
async def time_out(user_id, context):
    try:
        await asyncio.sleep(user_data[user_id]['settings']['time_limit'])
        if user_data[user_id]['current_answer'] is not None:
            user_data[user_id]['total'] += 1
            user_data[user_id]['current_example'] = None
            user_data[user_id]['current_answer'] = None
            await context.bot.send_message(
                user_id,
                "⏰ Время вышло! Попробуй новый пример.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➡️ Новый пример", callback_data='start_training')]])
            )
    except asyncio.CancelledError:
        pass

# Обновление меню операций (новая функция)
async def update_operations_menu(query, user_id):
    operations = user_data[user_id]['settings']['operations']
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if '+' in operations else '❌'} Сложение", callback_data='toggle_+'),
         InlineKeyboardButton(f"{'✅' if '-' in operations else '❌'} Вычитание", callback_data='toggle_-')],
        [InlineKeyboardButton(f"{'✅' if '*' in operations else '❌'} Умножение", callback_data='toggle_*'),
         InlineKeyboardButton(f"{'✅' if '/' in operations else '❌'} Деление", callback_data='toggle_/')],
        [InlineKeyboardButton("↩️ Назад", callback_data='settings')]
    ]
    await query.edit_message_text("Выбери операции:", reply_markup=InlineKeyboardMarkup(keyboard))

# Обработка кнопок
async def button(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == 'start_training':
        if user_data[user_id].get('timer_task'):
            user_data[user_id]['timer_task'].cancel()
        example, answer = generate_example(user_id)
        user_data[user_id]['current_example'] = example
        user_data[user_id]['current_answer'] = answer
        user_data[user_id]['last_message_time'] = datetime.now(pytz.UTC)

        img_buffer = create_example_image(example + " = ?")
        await query.message.reply_photo(
            photo=img_buffer,
            caption=f"🧠 Реши за {user_data[user_id]['settings']['time_limit']} сек:",
            reply_markup=MAIN_MENU_KEYBOARD
        )
        await query.edit_message_text("✅ Пример отправлен!")
        user_data[user_id]['timer_task'] = asyncio.create_task(time_out(user_id, context))

    elif query.data == 'show_stats':
        stats = user_data.get(user_id, {'correct': 0, 'total': 0})
        percent = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        await query.edit_message_text(
            f"📊 Статистика:\n✅ Правильно: {stats['correct']}\n📚 Всего: {stats['total']}\n🌟 Успех: {percent:.1f}%",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ В меню", callback_data='back')]])
        )

    elif query.data == 'back':
        keyboard = [
            [InlineKeyboardButton("🏋️ Начать тренировку", callback_data='start_training')],
            [InlineKeyboardButton("📊 Статистика", callback_data='show_stats')]
        ]
        await query.edit_message_text("🎉 Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'set_difficulty':
        keyboard = [
            [InlineKeyboardButton("Легко", callback_data='diff_easy'),
             InlineKeyboardButton("Средне", callback_data='diff_medium'),
             InlineKeyboardButton("Сложно", callback_data='diff_hard')],
            [InlineKeyboardButton("↩️ Назад", callback_data='settings')]
        ]
        await query.edit_message_text("Выбери уровень сложности:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith('diff_'):
        difficulty = query.data.split('_')[1]
        user_data[user_id]['settings']['difficulty'] = difficulty
        await query.edit_message_text(f"Сложность установлена: {difficulty}",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data='settings')]]))

    elif query.data == 'set_operations':
        await update_operations_menu(query, user_id)

    elif query.data.startswith('toggle_'):
        op = query.data.split('_')[1]
        operations = user_data[user_id]['settings']['operations']
        if op in operations:
            if len(operations) > 1:  # Нельзя убрать последнюю операцию
                operations.remove(op)
        else:
            operations.append(op)
        await update_operations_menu(query, user_id)

    elif query.data == 'set_time':
        await query.edit_message_text("Введи время в секундах (10-60):",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Назад", callback_data='settings')]]))
        user_data[user_id]['awaiting_time'] = True

    elif query.data == 'settings':
        settings = user_data[user_id]['settings']
        keyboard = [
            [InlineKeyboardButton("Уровень сложности", callback_data='set_difficulty')],
            [InlineKeyboardButton("Выбрать операции", callback_data='set_operations')],
            [InlineKeyboardButton("Установить время (сек)", callback_data='set_time')],
            [InlineKeyboardButton("↩️ В меню", callback_data='back')]
        ]
        await query.edit_message_text(
            f"⚙️ Настройки:\n"
            f"Сложность: {settings['difficulty']}\n"
            f"Операции: {', '.join(settings['operations'])}\n"
            f"Время: {settings['time_limit']} сек",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Проверка ответа пользователя
async def check_answer(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        return
    user_id = update.message.from_user.id
    message_time = update.message.date.replace(tzinfo=pytz.UTC)

    if user_data[user_id].get('last_message_time') and (message_time < user_data[user_id]['last_message_time'] - timedelta(minutes=1)):
        return

    message_text = update.message.text
    if message_text == "📋 Главное меню":
        await menu(update, context)
        return
    elif message_text == "⚙️ Настройки":
        await settings_menu(update, context)
        return

    if 'awaiting_time' in user_data[user_id] and user_data[user_id]['awaiting_time']:
        try:
            time_limit = int(message_text)
            if 10 <= time_limit <= 60:
                user_data[user_id]['settings']['time_limit'] = time_limit
                await update.message.reply_text(f"Время установлено: {time_limit} сек", reply_markup=MAIN_MENU_KEYBOARD)
            else:
                await update.message.reply_text("Введи число от 10 до 60!", reply_markup=MAIN_MENU_KEYBOARD)
        except ValueError:
            await update.message.reply_text("Введи число!", reply_markup=MAIN_MENU_KEYBOARD)
        user_data[user_id]['awaiting_time'] = False
        return

    if user_data[user_id]['current_answer'] is None:
        return

    try:
        user_answer = int(message_text)
        correct_answer = user_data[user_id]['current_answer']
        if user_data[user_id]['timer_task']:
            user_data[user_id]['timer_task'].cancel()
        user_data[user_id]['total'] += 1
        if user_answer == correct_answer:
            user_data[user_id]['correct'] += 1
            response = "🎉 Правильно!"
        else:
            response = f"❌ Неправильно. Правильный ответ: {correct_answer}"
        user_data[user_id]['current_example'] = None
        user_data[user_id]['current_answer'] = None

        keyboard = [
            [InlineKeyboardButton("➡️ Новый пример", callback_data='start_training')],
            [InlineKeyboardButton("📊 Статистика", callback_data='show_stats')]
        ]
        await update.message.reply_text(response, reply_markup=InlineKeyboardMarkup(keyboard))

    except ValueError:
        await update.message.reply_text("⚠️ Введи число!", reply_markup=MAIN_MENU_KEYBOARD)

# Обработка ошибок
async def error_handler(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")
    if update and update.message and update.message.chat.type == 'private':
        await update.message.reply_text("😔 Что-то пошло не так. Попробуй /menu.", reply_markup=MAIN_MENU_KEYBOARD)

# Главная функция
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^📋 Главное меню$'), menu))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^⚙️ Настройки$'), settings_menu))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    application.add_error_handler(error_handler)
    application.run_polling(poll_interval=0.5)

if __name__ == '__main__':
    main()