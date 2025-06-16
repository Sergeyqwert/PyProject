import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from f1_data import (
    get_available_seasons,
    get_races,
    parse_race_classification,
    get_all_results_up_to_race,
)

import time

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def parse_callback(data: str):
    """
    Ожидаемый формат callback_data:
      - "season:2025"
      - "race:2025:3"
    Возвращаем кортеж (action, year, round) или (None, None, None)
    """
    parts = data.split(":")
    if len(parts) == 2 and parts[0] == "season":
        try:
            y = int(parts[1])
            return ("season", y, None)
        except ValueError:
            return (None, None, None)
    if len(parts) == 3 and parts[0] == "race":
        try:
            y = int(parts[1])
            r = int(parts[2])
            return ("race", y, r)
        except ValueError:
            return (None, None, None)
    return (None, None, None)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — выводим меню для выбора сезона.
    """
    seasons = get_available_seasons()
    if not seasons:
        await update.message.reply_text(
            "⚠️ Не удалось получить список сезонов. Повторите позже."
        )
        return

    keyboard = []
    for y in seasons:
        btn = InlineKeyboardButton(str(y), callback_data=f"season:{y}")
        keyboard.append([btn])

    try:
        await update.message.reply_text(
            "🚥 Выберите сезон Формулы-1:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except BadRequest as e:
        logging.error(f"Failed to send seasons keyboard: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Универсальный обработчик callback_data.
    """
    query = update.callback_query
    await query.answer()

    action, year, round_number = parse_callback(query.data)
    if action == "season":
        await send_race_list(query, year)
    elif action == "race":
        await send_season_points(query, year, round_number)
    else:
        try:
            await query.edit_message_text("❌ Некорректный выбор, попробуйте /start заново.")
        except BadRequest:
            pass


async def send_race_list(query, year: int):
    """
    После выбора года: выводим кнопки **только для завершённых** Гран-при.
    Чтобы понять, завершён ли этап, пробуем парсить таблицу Race classification
    и проверяем, есть ли в ней хотя бы один гонщик с очками > 0.
    """
    races = get_races(year)
    if not races:
        try:
            await query.edit_message_text(f"⚠️ Сезон {year} недоступен или не найден.")
        except BadRequest:
            pass
        return

    keyboard = []
    for race in races:
        rnd = race["round"]
        name = race["race_name"]
        date_str = race["date_str"]

        # Попробуем распарсить классификацию этого этапа:
        # если в таблице нет никого с очками > 0 → считаем, что гонка не окончена
        # (либо результаты ещё не выгружены), и пропускаем её.
        # Для вежливости добавляем небольшую паузу между запросами.
        pts_dict = parse_race_classification(race["link"])
        time.sleep(1)  # чтобы не перегружать Википедию
        if not pts_dict:
            continue

        # Проверяем, есть ли в pts_dict хоть одно ненулевое значение
        has_points = any(pts > 0 for pts in pts_dict.values())
        if not has_points:
            continue

        btn_text = f"{rnd}. {name} ({date_str})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"race:{year}:{rnd}")])

    if not keyboard:
        try:
            await query.edit_message_text(f"ℹ️ Для сезона {year} ещё нет завершённых этапов.")
        except BadRequest:
            pass
        return

    try:
        await query.edit_message_text(
            f"🏁 Сезон {year}. Выберите завершённый Гран-при:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except BadRequest as e:
        # Игнорируем "Message is not modified"
        if "Message is not modified" not in str(e):
            logging.error(f"Failed to edit message for race list: {e}")


async def send_season_points(query, year: int, round_number: int):
    """
    После выбора конкретного Гран-при: считаем и выводим очки.
    """
    totals = get_all_results_up_to_race(year, round_number)
    if not totals:
        try:
            await query.edit_message_text(
                f"⚠️ Не удалось получить очки для сезона {year}, этап {round_number}."
            )
        except BadRequest:
            pass
        return

    text = f"📊 Итоговые очки после {round_number}-го этапа сезона {year}:\n\n"
    for i, (drv, pts) in enumerate(totals.items(), start=1):
        text += f"{i}. {drv}: {pts:.0f} очков\n"

    try:
        await query.edit_message_text(text)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logging.error(f"Failed to edit message for season points: {e}")


if __name__ == "__main__":
    TOKEN = "7602772509:AAG3owYMcqESmoM6Os_VzWuv3CziYuFQKZg"
    if not TOKEN or TOKEN.startswith("INSERT"):
        print("❌ Укажите корректный токен бота в переменной TOKEN.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("✅ Бот запущен")
    app.run_polling()
