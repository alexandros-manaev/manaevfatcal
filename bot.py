import logging
import math
import json
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from config import TOKEN, GOOGLE_FORM_LINK

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
(SELECT_MODULE, GET_WEIGHT, GET_HEIGHT, GET_AGE, GET_GENDER,
 GET_NECK, GET_WAIST, GET_HIP, GET_ACTIVITY) = range(9)

USERS_FILE = "users.json"

def save_user(user):
    users = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            try:
                users = json.load(f)
            except json.JSONDecodeError:
                users = []
    if not any(u["id"] == user.id for u in users):
        users.append({"id": user.id, "username": user.username})
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)

# Функция для замены запятых на точки и преобразования в float
def parse_float(text: str) -> float:
    return float(text.strip().replace(",", "."))

# Вступительное сообщение с разъяснениями
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    save_user(user)
    intro_text = (
        "Добро пожаловать!\n\n"
        "Этот бот поможет вам рассчитать два показателя:\n\n"
        "1. ИМТ (индекс массы тела) – подходит для оценки общего состояния массы, но может быть искажен, если вы не занимаетесь силовыми тренировками.\n\n"
        "2. % жира – более точный показатель состава тела, который рекомендуется использовать, если вы активно занимаетесь силовыми тренировками. (Расчет не предназначен для детей и подростков.)\n\n"
        "Выберите, что хотите рассчитать:"
    )
    keyboard = [
        [
            InlineKeyboardButton("Расчёт ИМТ", callback_data="BMI"),
            InlineKeyboardButton("Расчёт % жира", callback_data="BF"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(intro_text, reply_markup=reply_markup)
    return SELECT_MODULE

async def select_module(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    module = query.data
    context.user_data["module"] = module
    if module == "BMI":
        await query.edit_message_text(
            "Вы выбрали расчёт ИМТ.\n\nПожалуйста, введите свой вес (в кг).\n(Измеряйте вес утром, на тощак, до завтрака.)"
        )
        return GET_WEIGHT
    else:
        await query.edit_message_text(
            "Вы выбрали расчёт % жира.\n\nПожалуйста, введите свой вес (в кг).\n(Измеряйте вес утром, на тощак, до завтрака.)"
        )
        return GET_WEIGHT

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        weight = parse_float(update.message.text)
        if weight <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите корректное число для веса.")
        return GET_WEIGHT
    context.user_data["weight"] = weight
    await update.message.reply_text(
        "Введите свой рост (в см).\n(Измеряйте рост без обуви, лучше утром.)"
    )
    return GET_HEIGHT

async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        height = parse_float(update.message.text)
        if height <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите корректное число для роста.")
        return GET_HEIGHT
    context.user_data["height"] = height
    await update.message.reply_text("Введите свой возраст (в годах).")
    return GET_AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        age = int(update.message.text.strip())
        if age <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите корректный возраст.")
        return GET_AGE
    context.user_data["age"] = age
    module = context.user_data.get("module")
    if module == "BF":
        reply_keyboard = [["М", "Ж"]]
        await update.message.reply_text(
            "Укажите свой пол: введите 'М' для мужчин или 'Ж' для женщин.",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return GET_GENDER
    else:
        return await ask_activity(update, context)

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gender = update.message.text.strip().lower()
    if gender not in ["м", "ж", "m", "f"]:
        await update.message.reply_text("Введите корректно: 'М' для мужчин или 'Ж' для женщин.")
        return GET_GENDER
    context.user_data["gender"] = "м" if gender in ["м", "m"] else "ж"
    await update.message.reply_text(
        "Введите окружность шеи (в см).\n(Измеряйте чуть ниже гортани, не сжимая кожу слишком сильно.)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GET_NECK

async def get_neck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        neck = parse_float(update.message.text)
        if neck <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите корректное число для окружности шеи (используйте точку).")
        return GET_NECK
    context.user_data["neck"] = neck
    await update.message.reply_text(
        "Введите окружность талии (в см).\n(Для мужчин: измеряйте на уровне пупка. Для женщин: в самой узкой части живота.)"
    )
    return GET_WAIST

async def get_waist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        waist = parse_float(update.message.text)
        if waist <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите корректное число для окружности талии (используйте точку).")
        return GET_WAIST
    context.user_data["waist"] = waist
    if context.user_data.get("gender") == "ж":
        await update.message.reply_text(
            "Введите окружность бедер (в см).\n(Измеряйте в самой широком месте – на уровне ягодиц.)"
        )
        return GET_HIP
    else:
        return await ask_activity(update, context)

async def get_hip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        hip = parse_float(update.message.text)
        if hip <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите корректное число для окружности бедер (используйте точку).")
        return GET_HIP
    context.user_data["hip"] = hip
    return await ask_activity(update, context)

# Запрос выбора физической активности (тексты сокращены через дефис)
async def ask_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Выберите ваш уровень физической активности:", reply_markup=ReplyKeyboardRemove())
    keyboard = [
        [InlineKeyboardButton("Офис без пер.", callback_data="1.20")],
        [InlineKeyboardButton("Офис c редк.-пер.", callback_data="1.25")],
        [InlineKeyboardButton("Офис c рег.-прог.", callback_data="1.30")],
        [InlineKeyboardButton("Офис + легк-трен", callback_data="1.35")],
        [InlineKeyboardButton("Офис + рег-трен", callback_data="1.40")],
        [InlineKeyboardButton("Работа c ход.", callback_data="1.45")],
        [InlineKeyboardButton("Работа c дви.+ период-трен", callback_data="1.50")],
        [InlineKeyboardButton("Физ-работа + легк-трен", callback_data="1.60")],
        [InlineKeyboardButton("Активн. работа + интенсив-трен", callback_data="1.70")],
        [InlineKeyboardButton("Проф. спорт", callback_data="1.80")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("Выберите ваш уровень физической активности:", reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text("Выберите ваш уровень физической активности:", reply_markup=reply_markup)
    return GET_ACTIVITY

async def get_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    try:
        activity_coeff = float(query.data)
    except ValueError:
        await query.edit_message_text("Ошибка выбора уровня активности. Попробуйте ещё раз.")
        return GET_ACTIVITY
    context.user_data["activity_coeff"] = activity_coeff
    return await process_result(update, context)

async def process_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    module = context.user_data.get("module")
    weight = context.user_data.get("weight")
    height = context.user_data.get("height")
    age = context.user_data.get("age")
    activity_coeff = context.user_data.get("activity_coeff")
    recommendations = ""
    risks = ""
    result_text = ""

    if module == "BMI":
        height_m = height / 100
        bmi = weight / (height_m ** 2)
        bmi = round(bmi, 2)
        context.user_data["bmi"] = bmi

        if bmi < 18.5:
            risks = "Низкий вес может свидетельствовать о дефиците энергии и нарушениях гормонального баланса."
            recommendations = (
                "Рацион: Увеличьте калорийность, уделяя внимание качественным белкам, сложным углеводам и полезным жирам. При необходимости обратитесь к диетологу или эндокринологу.\n\n"
                "Физическая активность: Если ваша работа преимущественно сидячая, делайте регулярные перерывы, вставайте и двигайтесь, стремясь к не менее 10 000 шагам в день. Следите за качеством сна."
            )
        elif 18.5 <= bmi <= 24.9:
            risks = "Ваш ИМТ находится в пределах нормы."
            recommendations = (
                "Рацион: Поддерживайте сбалансированное питание с упором на свежие овощи, цельнозерновые продукты и умеренные источники белка.\n\n"
                "Физическая активность: Если ваша работа связана с длительным сидением, делайте регулярные перерывы, поддерживайте активность (не менее 10 000 шагов в день) и следите за режимом сна."
            )
        elif 25 <= bmi <= 29.9:
            risks = ("Избыточный % жира повышает риск сердечно-сосудистых заболеваний, диабета, метаболического синдрома, "
                     "а также заболеваний суставов, хронического воспаления и снижения защитных функций организма.")
            recommendations = (
                "Рацион: Пересмотрите рацион, снизив энергетическую плотность за счёт увеличения потребления овощей, продуктов с высоким содержанием пищевых волокон и белка, а также уменьшив количество обработанных и ультраобработанных продуктов. Обратитесь к эндокринологу, кардиологу и специалисту по питанию. Дополнительно проконсультируйтесь с психотерапевтом или психиатром для исключения РПП.\n\n"
                "Физическая активность: Рекомендуется добавить силовые трен-ки и умеренное кардио (при отсутствии противопоказаний, проконсультируйтесь со специалистом). Если вы ощущаете усталость, временно снижайте интенсивность тренировок. Если ваша работа сидячая – делайте регулярные перерывы, вставайте и двигайтесь, стремясь к не менее 10 000 шагам в день. Следите за качеством сна."
            )
        else:
            risks = ("Ожирение существенно повышает риск диабета 2 типа, сердечно-сосудистых заболеваний, метаболического синдрома, "
                     "заболеваний суставов, хронического воспаления и снижения защитных функций организма.")
            recommendations = (
                "Рацион: Запустите комплексную программу по снижению веса – уменьшите энергетическую плотность за счёт увеличения овощей, продуктов с высоким содержанием пищевых волокон и белка, и снизьте количество обработанных и ультраобработанных продуктов. Обратитесь к эндокринологу, кардиологу, диетологу и тренеру. Дополнительно проконсультируйтесь с психотерапевтом или психиатром для исключения РПП.\n\n"
                "Физическая активность: Если вы долго сидите, делайте регулярные перерывы, стремитесь к 10 000 шагам в день, и добавьте силовые трен-ки с умеренным кардио. При ощущении усталости временно снижайте интенсивность тренировок и следите за качеством сна."
            )
        result_text = f"Ваш ИМТ: {bmi}.\n\nРиски: {risks}\n\nРекомендации:\n{recommendations}\n\n"
    
    elif module == "BF":
        height_val = height  # см
        waist = context.user_data.get("waist")
        neck = context.user_data.get("neck")
        if context.user_data.get("gender") == "м":
            try:
                bf = 495 / (1.0324 - 0.19077 * math.log10(waist - neck) + 0.15456 * math.log10(height_val)) - 450
            except ValueError:
                await update.callback_query.message.reply_text("Ошибка в измерениях. Проверьте введённые значения.")
                return ConversationHandler.END
        else:
            hip = context.user_data.get("hip")
            try:
                bf = 495 / (1.29579 - 0.35004 * math.log10(waist + hip - neck) + 0.221 * math.log10(height_val)) - 450
            except ValueError:
                await update.callback_query.message.reply_text("Ошибка в измерениях. Проверьте введённые значения.")
                return ConversationHandler.END
        bf = round(bf, 2)
        context.user_data["bf"] = bf

        if (context.user_data.get("gender") == "м" and bf < 6) or (context.user_data.get("gender") == "ж" and bf < 14):
            risks = "Низкий % жира может свидетельствовать о нарушениях гормонального баланса и снижении иммунитета."
            recommendations = (
                "Рацион: Постепенно увеличьте общую калорийность, уделяя внимание продуктам с высоким содержанием пищевых волокон, овощам и белку. Обратитесь к специалисту по питанию, эндокринологу и кардиологу.\n\n"
                "Физическая активность: Если вы чувствуете усталость, временно снижайте интенсивность тренировок и следите за качеством сна."
            )
        elif (context.user_data.get("gender") == "м" and 6 <= bf <= 24) or (context.user_data.get("gender") == "ж" and 14 <= bf <= 31):
            risks = "Ваш % жира находится в нормальном диапазоне."
            recommendations = (
                "Рацион: Поддерживайте сбалансированное питание с упором на свежие овощи, цельнозерновые продукты, белковые источники и продукты с высоким содержанием пищевых волокон.\n\n"
                "Физическая активность: Если ваша работа сидячая, регулярно делайте перерывы, вставайте и двигайтесь, стремясь к не менее 10 000 шагам в день, и следите за качеством сна."
            )
            # Дополнительное сообщение для низкого нормального диапазона
            if context.user_data.get("gender") == "м" and bf < 10:
                recommendations += "\n\nОбратите внимание: очень низкий % жира (ниже 10%) может негативно влиять на уровень половых и щитовидных гормонов, что сказывается на общем самочувствии и может привести к симптомам метаболической адаптации."
            elif context.user_data.get("gender") == "ж" and bf < 20:
                recommendations += "\n\nОбратите внимание: очень низкий % жира (ниже 20%) может негативно влиять на гормональный баланс, что может привести к нарушениям менструального цикла, однако всё индивидуально."
        else:
            risks = ("Избыточный % жира повышает риск сердечно-сосудистых заболеваний, диабета, метаболического синдрома, "
                     "а также заболеваний суставов, хронического воспаления и снижения защитных функций организма.")
            recommendations = (
                "Рацион: Пересмотрите рацион, снизив энергетическую плотность за счёт увеличения потребления овощей, продуктов с высоким содержанием пищевых волокон и белка, а также уменьшив количество обработанных и ультраобработанных продуктов. Обратитесь к эндокринологу, кардиологу и специалисту по питанию. Дополнительно проконсультируйтесь с психотерапевтом или психиатром для исключения РПП.\n\n"
                "Физическая активность: Рекомендуется добавить силовые трен-ки и умеренное кардио (при отсутствии противопоказаний, проконсультируйтесь со специалистом). Если вы ощущаете усталость, временно снижайте интенсивность тренировок. Если ваша работа предполагает длительное сидение, делайте регулярные перерывы, вставайте и двигайтесь, стремясь к не менее 10 000 шагам в день, и следите за качеством сна."
            )
        result_text = f"Ваш рассчитанный % жира: {bf}%.\n\nРиски: {risks}\n\nРекомендации:\n{recommendations}\n\n"

    # Дополнительные рекомендации в зависимости от коэффициента активности
    pa_extra = ""
    if activity_coeff <= 1.30:
        pa_extra = " Если ваша активность низкая, постарайтесь существенно увеличить её: делайте частые перерывы от сидячей работы, вставайте и двигайтесь, стремясь к не менее 10 000 шагам в день, а также добавьте легкое кардио."
    elif activity_coeff <= 1.50:
        pa_extra = " Если ваша работа предполагает длительное сидение, даже при среднем уровне активности, не забывайте регулярно делать перерывы, вставать и поддерживать активность на уровне 10 000 шагов в день, а также добавлять кардио для улучшения обмена веществ."
    else:
        pa_extra = " Даже если вы активны, если ваша работа связана с длительным сидением, регулярно делайте перерывы, вставайте и двигайтесь, стремясь к не менее 10 000 шагам в день, а также добавляйте кардио для оптимизации обмена веществ."
    
    # Добавляем дополнительное сообщение к разделу физической активности
    result_text += "\n\n" + pa_extra

    # Финальный призыв к действию
    result_text += (
        "\n\nДля разбора вашей ситуации и подробных рекомендаций по питанию, тренировкам и изменению образа жизни заполните анкету. "
        "Я свяжусь с вами для проведения индивидуальной консультации."
    )

    keyboard = [
        [InlineKeyboardButton("Записаться на консультацию", url=GOOGLE_FORM_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.message.reply_text(result_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(result_text, reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Диалог отменён. Для начала отправьте /start.")
    return ConversationHandler.END

def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_MODULE: [CallbackQueryHandler(select_module)],
            GET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            GET_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            GET_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GET_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            GET_NECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_neck)],
            GET_WAIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_waist)],
            GET_HIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hip)],
            GET_ACTIVITY: [CallbackQueryHandler(get_activity)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()