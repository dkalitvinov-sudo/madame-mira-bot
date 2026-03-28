import os
import json
import time
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
CARD_NUMBER = os.getenv("CARD_NUMBER", "1111 2222 3333 4444")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"
CRYPTO_API_URL = "https://pay.crypt.bot/api"

client = OpenAI(api_key=OPENAI_API_KEY)

last_update_id = None
USER_STATE = {}
ANALYTICS = {
    "total_users": set(),
    "sources": {},
    "paid_basic": 0,
    "paid_deep": 0,
    "paid_vip": 0,
    "readings_sent": 0,
    "receipts_sent": 0
}

BASIC_USD = "5"
DEEP_USD = "12"
VIP_USD = "25"

BASIC_UAH = "200"
DEEP_UAH = "500"
VIP_UAH = "1000"

WARMUP_1_DELAY = 45 * 60
WARMUP_2_DELAY = 24 * 60 * 60
UPSELL_DELAY = 2 * 60 * 60


def now_ts():
    return int(time.time())


def tg_post(method, payload=None, data=None):
    url = f"{TELEGRAM_API_URL}/{method}"
    if payload is not None:
        return requests.post(url, json=payload, timeout=30)
    return requests.post(url, data=data, timeout=30)


def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    tg_post("sendMessage", payload=payload)


def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    tg_post("editMessageText", payload=payload)


def edit_message_caption(chat_id, message_id, caption, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": caption
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    tg_post("editMessageCaption", payload=payload)


def send_photo(chat_id, file_id, caption=None, reply_markup=None):
    data = {"chat_id": chat_id, "photo": file_id}
    if caption:
        data["caption"] = caption
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    tg_post("sendPhoto", data=data)


def send_document(chat_id, file_id, caption=None, reply_markup=None):
    data = {"chat_id": chat_id, "document": file_id}
    if caption:
        data["caption"] = caption
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    tg_post("sendDocument", data=data)


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    tg_post("answerCallbackQuery", payload=payload)


def get_updates():
    global last_update_id
    params = {"timeout": 50, "offset": last_update_id}
    response = requests.get(f"{TELEGRAM_API_URL}/getUpdates", params=params, timeout=60)
    return response.json()


def log_source(source):
    if not source:
        source = "direct"
    ANALYTICS["sources"][source] = ANALYTICS["sources"].get(source, 0) + 1


def get_user(user_id):
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {
            "step": None,
            "offer": None,
            "name": "",
            "situation": "",
            "question": "",
            "initial_text": "",
            "reply_1": "",
            "focus": None,
            "topic_class": None,
            "invoice_id": None,
            "invoice_url": None,
            "payment_method": None,
            "status": "new",
            "followups_left": 0,
            "last_activity": now_ts(),
            "warmup_stage": 0,
            "last_offer_shown": None,
            "reading_sent_at": None,
            "upsell_sent": False,
            "vip_offer_sent": False,
            "source": "direct"
        }
    return USER_STATE[user_id]


def reset_user(user_id, source="direct"):
    USER_STATE[user_id] = {
        "step": None,
        "offer": None,
        "name": "",
        "situation": "",
        "question": "",
        "initial_text": "",
        "reply_1": "",
        "focus": None,
        "topic_class": None,
        "invoice_id": None,
        "invoice_url": None,
        "payment_method": None,
        "status": "new",
        "followups_left": 0,
        "last_activity": now_ts(),
        "warmup_stage": 0,
        "last_offer_shown": None,
        "reading_sent_at": None,
        "upsell_sent": False,
        "vip_offer_sent": False,
        "source": source or "direct"
    }


def touch_user(user_id):
    user = get_user(user_id)
    user["last_activity"] = now_ts()


def formats_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ Мини-разбор $10", "callback_data": "basic_info"}],
            [{"text": "🔮 Глубокий разбор $20", "callback_data": "deep_info"}],
            [{"text": "💎 VIP-разбор $50", "callback_data": "vip_info"}],
            [{"text": "📖 Что входит в форматы", "callback_data": "show_format_details"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def focus_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "❤️ Понять чувства человека", "callback_data": "focus_feelings"}],
            [{"text": "🔮 Увидеть будущее ситуации", "callback_data": "focus_future"}],
            [{"text": "🪞 Разобраться в себе", "callback_data": "focus_self"}],
            [{"text": "🧭 Понять, что делать дальше", "callback_data": "focus_action"}]
        ]
    }


def payment_keyboard(invoice_url, offer):
    return {
        "inline_keyboard": [
            [{"text": "💸 Оплатить криптой", "url": invoice_url}],
            [{"text": "✅ Проверить оплату", "callback_data": "check_payment"}],
            [{"text": "💳 Перевод на карту", "callback_data": f"card_{offer}"}],
            [{"text": "📖 Что входит в формат", "callback_data": f"details_{offer}"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def admin_receipt_keyboard(user_id):
    return {
        "inline_keyboard": [[
            {"text": "✅ Подтвердить", "callback_data": f"admin_accept_{user_id}"},
            {"text": "❌ Отклонить", "callback_data": f"admin_reject_{user_id}"}
        ]]
    }


def admin_application_keyboard(user_id):
    return {
        "inline_keyboard": [[
            {"text": "🪄 Сделать разбор", "callback_data": f"admin_reading_{user_id}"}
        ]]
    }


def upsell_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🔮 Углубить до $20", "callback_data": "deep_info"}],
            [{"text": "💎 Взять VIP $50", "callback_data": "vip_info"}]
        ]
    }


def vip_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💎 Взять VIP $50", "callback_data": "vip_info"}]
        ]
    }


def format_offer_text(offer):
    return {
        "basic": "Мини-разбор $10",
        "deep": "Глубокий разбор $20",
        "vip": "VIP-разбор $50"
    }.get(offer, "Не выбран")


def format_card_amount_uah(offer):
    return {
        "basic": BASIC_UAH,
        "deep": DEEP_UAH,
        "vip": VIP_UAH
    }.get(offer, BASIC_UAH)


def format_status_label(status):
    return {
        "new": "⚪ новая",
        "receipt_sent": "🟡 чек получен",
        "receipt_rejected": "🔴 чек отклонён",
        "paid": "🟢 оплата подтверждена",
        "submitted": "🟣 заявка собрана",
        "reading_sent": "✨ разбор отправлен"
    }.get(status, "⚪ новая")


def send_admin_status_note(user_id):
    user = get_user(user_id)
    send_message(
        ADMIN_CHAT_ID,
        f"Статус заявки {user_id}: {format_status_label(user.get('status'))}"
    )


def format_details_text():
    return (
        "Форматы Madame Mira ✨\n\n"
        "✨ Мини-разбор $10\n"
        "Подойдёт, если тебе нужен быстрый и точный ответ на главный вопрос.\n"
        "Внутри: сам разбор + 1 уточняющий вопрос после.\n\n"
        "🔮 Глубокий разбор $20\n"
        "Подойдёт, если ситуация эмоциональная, сложная или запутанная.\n"
        "Внутри: более глубокий разбор + 2 уточняющих вопроса.\n\n"
        "💎 VIP-разбор $50\n"
        "Подойдёт, если тебе нужен не просто ответ, а более внимательное сопровождение.\n"
        "Внутри: самый глубокий формат + 3 уточняющих вопроса + более тонкое ведение."
    )


def single_format_details(offer):
    if offer == "basic":
        return (
            "✨ Мини-разбор $10\n\n"
            "Что ты получишь:\n"
            "• быстрый и точный ответ на главный вопрос\n"
            "• личный разбор по твоей ситуации\n"
            "• 1 уточняющий вопрос после разбора\n\n"
            "Подойдёт, если тебе нужна ясность без долгого погружения."
        )
    if offer == "deep":
        return (
            "🔮 Глубокий разбор $20\n\n"
            "Что ты получишь:\n"
            "• более глубокое чтение ситуации\n"
            "• раскрытие внутреннего узла истории\n"
            "• 2 уточняющих вопроса после разбора\n\n"
            "Подойдёт, если ситуация сложная, эмоциональная или многослойная."
        )
    return (
        "💎 VIP-разбор $50\n\n"
        "Что ты получишь:\n"
        "• самый глубокий формат разбора\n"
        "• более внимательное сопровождение\n"
        "• 3 уточняющих вопроса после разбора\n\n"
        "Подойдёт, если тебе нужен не просто ответ, а более тонкая и глубокая работа."
    )


def choose_offer_local(text: str, focus: str = None):
    t = text.lower().strip()

    strong_deep = [
        "измена", "предательство", "ушел к другой", "ушёл к другой",
        "развод", "любовный треугольник", "предал", "бросил", "другая женщина"
    ]
    medium_deep = [
        "отнош", "парень", "муж", "бывш", "ушел", "ушёл", "другая", "другой",
        "любов", "чувства", "больно", "сложно", "тяжело", "кризис",
        "расстав", "ревность", "запутал", "запуталась", "запутался",
        "не понимаю", "что делать", "будущее", "подруга", "одиночество",
        "не складываются", "страдаю", "потеряла"
    ]
    vip_keywords = [
        "очень плохо", "совсем тяжело", "не вывожу", "разрушен", "разрушена",
        "хочу сопровождение", "поддержка", "несколько дней", "очень глубокий"
    ]
    basic_keywords = [
        "быстро", "кратко", "коротко", "мини", "один вопрос",
        "простой вопрос", "быстрый ответ", "короткий ответ"
    ]

    deep_score = 0
    basic_score = 0
    vip_score = 0

    for word in strong_deep:
        if word in t:
            deep_score += 3
    for word in medium_deep:
        if word in t:
            deep_score += 1
    for word in vip_keywords:
        if word in t:
            vip_score += 2
    for word in basic_keywords:
        if word in t:
            basic_score += 2

    if focus == "future":
        deep_score += 1
    elif focus == "feelings":
        deep_score += 1
    elif focus == "action":
        basic_score += 1
    elif focus == "self":
        deep_score += 1

    if len(t) > 250:
        vip_score += 1
        deep_score += 1
    elif len(t) > 180:
        deep_score += 2
    elif len(t) < 60:
        basic_score += 1

    if vip_score >= 3:
        return "vip"
    if deep_score >= 4:
        return "deep"
    if basic_score >= 1:
        return "basic"
    if deep_score >= 2 and basic_score == 0:
        return "basic"
    return "basic"


def gpt_text(prompt, fallback):
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )
        text = (response.output_text or "").strip()
        return text or fallback
    except Exception:
        return fallback


def gpt_json(prompt, fallback):
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )
        text = (response.output_text or "").strip()
        return json.loads(text)
    except Exception:
        return fallback


def classify_topic(user_text: str):
    fallback = {"topic": "relationship", "supported": True}

    medical_words = ["живот", "болит", "температура", "врач", "тошнит", "таблет", "здоров", "болезн"]
    if any(w in user_text.lower() for w in medical_words):
        return {"topic": "medical", "supported": False}

    prompt = f"""
Определи тему сообщения пользователя.

Варианты topic:
- relationship
- emotional
- medical
- legal
- finance
- technical
- other

supported:
- true, если бот Madame Mira может уместно помочь как бот про отношения, чувства, внутреннюю ясность, эмоциональные ситуации
- false, если тема не его компетенция

Верни строго JSON:
{{
  "topic": "...",
  "supported": true
}}

Сообщение:
{user_text}
"""
    data = gpt_json(prompt, fallback)
    topic = data.get("topic", "relationship")
    supported = bool(data.get("supported", True))

    if topic in ["medical", "legal", "finance", "technical", "other"] and topic != "emotional":
        supported = False

    return {"topic": topic, "supported": supported}


def unsupported_reply(user_text: str, topic: str):
    if topic == "medical":
        return (
            "Я честно скажу: я не лучший помощник в медицинских вопросах ✨\n\n"
            "Если у тебя болит живот или есть симптомы по здоровью, лучше обратиться к врачу.\n\n"
            "Я больше про отношения, чувства, внутреннюю ясность и эмоциональные ситуации. Если хочешь, я могу помочь тебе именно с этим."
        )
    if topic == "legal":
        return (
            "Я честно скажу: юридические вопросы не моя сильная сторона ✨\n\n"
            "С такими темами лучше идти к профильному специалисту.\n\n"
            "Я больше помогаю там, где речь про отношения, чувства, внутренние переживания и сложные эмоциональные истории."
        )
    if topic == "finance":
        return (
            "Я честно скажу: финансовые вопросы не моя зона экспертности ✨\n\n"
            "Я больше про отношения, эмоциональную ясность и внутренние состояния.\n\n"
            "Если хочешь, можешь рассказать о своей истории именно с этой стороны."
        )
    if topic == "technical":
        return (
            "С техническими вопросами я не самый точный проводник ✨\n\n"
            "Моя сила больше в отношениях, чувствах, внутренней ясности и сложных эмоциональных ситуациях.\n\n"
            "Если хочешь, расскажи, что у тебя сейчас происходит именно на этом уровне."
        )
    return (
        "Я честно скажу: это не совсем моя зона глубины ✨\n\n"
        "Я больше про отношения, чувства, внутреннюю ясность и эмоциональные истории.\n\n"
        "Если хочешь, можешь рассказать свою ситуацию именно с этой стороны."
    )


def first_reply(user_text: str):
    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мягкий, мистический, тёплый.

Нужно написать первое сообщение после того, как человек поделился ситуацией.

Правила:
- покажи, что ты почувствовала состояние
- задай один мягкий вопрос
- не продавай
- не упоминай оплату
- коротко
- на русском

Сообщение:
{user_text}
"""
    fallback = (
        "Я чувствую, что за этими словами стоит усталость сердца ✨\n\n"
        "Скажи, что ранит сильнее: сама ситуация или то, что внутри до сих пор нет ясности?"
    )
    return gpt_text(prompt, fallback)


def recommend_offer(initial_text: str, reply_1: str, focus: str):
    fallback_offer = choose_offer_local(f"{initial_text} {reply_1}", focus=focus)
    fallback_map = {
        "basic": {
            "offer": "basic",
            "message": "Я бы мягко повела тебя в ✨ Мини-разбор за $10.\n\nЗдесь сейчас важнее получить один ясный и точный ответ, который снимет лишнюю неопределённость."
        },
        "deep": {
            "offer": "deep",
            "message": "Я бы повела тебя в 🔮 Глубокий разбор за $20.\n\nПотому что здесь чувствуется более глубокий внутренний узел, который лучше раскрывать шире."
        },
        "vip": {
            "offer": "vip",
            "message": "Я бы сейчас повела тебя в 💎 VIP-разбор за $50.\n\nЗдесь история ощущается очень глубокой, и тебе подойдёт не только сам разбор, а ещё более внимательное сопровождение."
        }
    }
    fallback = fallback_map[fallback_offer]

    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мягкий, мистический, премиальный.

Есть 3 формата:
- basic = Мини-разбор $10
- deep = Глубокий разбор $20
- vip = VIP-разбор $50

Фокус пользователя:
{focus}

Правила:
- basic выбирай чаще по умолчанию
- deep выбирай, если история многослойная
- vip только если очень тяжёлая, глубокая ситуация или явно нужна поддержка и сопровождение
- выбери только один формат
- объясни мягко и красиво
- не перечисляй все варианты

Верни строго JSON:
{{
  "offer": "basic|deep|vip",
  "message": "..."
}}

Первое сообщение:
{initial_text}

Ответ:
{reply_1}
"""
    data = gpt_json(prompt, fallback)
    offer = data.get("offer", fallback["offer"])
    if offer not in ["basic", "deep", "vip"]:
        offer = fallback["offer"]
    message = data.get("message", fallback["message"])
    return {"offer": offer, "message": message}


def make_reading(user):
    offer_text = format_offer_text(user.get("offer"))
    prompt = f"""
Ты — Madame Mira.
Сделай готовый персональный разбор для клиента на русском.

Стиль:
- женственный
- мистический
- мягкий
- уверенный
- премиальный

Правила:
- не говори, что ты ИИ
- не упоминай модель
- дай ощущение личного ответа
- basic короче
- deep подробнее
- vip глубже и с поддержкой
- не используй списки цифрами

Имя: {user.get("name")}
Формат: {offer_text}
Фокус: {user.get("focus")}
Ситуация: {user.get("situation")}
Что хочет понять: {user.get("question")}
"""
    fallback = (
        f"{user.get('name')}, я вошла в твою ситуацию глубже ✨\n\n"
        "Сейчас я вижу, что тебе особенно важно перестать смотреть на эту историю только через тревогу. Там, где нет ясности, сердце начинает додумывать и уставать сильнее, чем от самих событий.\n\n"
        "Твоя опора сейчас не в том, чтобы заставить всё сложиться любой ценой, а в том, чтобы услышать себя яснее и увидеть правду без внутреннего тумана.\n\n"
        "Именно из этой ясности и начнёт собираться твоё движение дальше 💫"
    )
    return gpt_text(prompt, fallback)


def make_followup_answer(user, followup_question):
    prompt = f"""
Ты — Madame Mira.
Продолжи уже начатый разбор.

Стиль:
- мягкий
- женственный
- мистический
- по делу
- тёплый

Формат клиента: {format_offer_text(user.get("offer"))}
Имя: {user.get("name")}
Фокус: {user.get("focus")}
Ситуация: {user.get("situation")}
Главный вопрос: {user.get("question")}
Уточняющий вопрос: {followup_question}

Ответь как продолжение уже сделанного разбора.
"""
    fallback = (
        "Я чувствую, что в этом уточнении для тебя важен не только сам ответ, а опора ✨\n\n"
        "Сейчас тебе важно смотреть не на страх потери, а на то, где в этой истории остаётся живая взаимность. Именно она показывает, есть ли здесь настоящее движение вперёд 💫"
    )
    return gpt_text(prompt, fallback)


def create_crypto_invoice(user_id, offer):
    amount_map = {
        "basic": BASIC_USD,
        "deep": DEEP_USD,
        "vip": VIP_USD
    }
    description_map = {
        "basic": "Mini",
        "deep": "Deep",
        "vip": "VIP"
    }

    try:
        response = requests.post(
            f"{CRYPTO_API_URL}/createInvoice",
            headers={
                "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
                "Content-Type": "application/json"
            },
            json={
                "asset": "USDT",
                "amount": amount_map[offer],
                "description": description_map[offer],
                "payload": f"user_{user_id}_{offer}"
            },
            timeout=30
        )
        data = response.json()
        if not data.get("ok"):
            return None
        result = data["result"]
        return {
            "invoice_id": result["invoice_id"],
            "invoice_url": result["bot_invoice_url"]
        }
    except Exception:
        return None


def get_invoice_status(invoice_id):
    try:
        response = requests.get(
            f"{CRYPTO_API_URL}/getInvoices",
            headers={"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN},
            params={"invoice_ids": str(invoice_id)},
            timeout=30
        )
        data = response.json()
        if not data.get("ok"):
            return None
        items = data["result"]["items"]
        if not items:
            return None
        return items[0].get("status")
    except Exception:
        return None


def send_offer_with_invoice(chat_id, user_id, offer, intro_text):
    user = get_user(user_id)
    user["offer"] = offer
    user["last_offer_shown"] = offer

    invoice = create_crypto_invoice(user_id, offer)
    if not invoice:
        send_message(chat_id, "Не получилось создать счёт 😔\n\nПопробуй ещё раз через минуту.")
        return

    user["invoice_id"] = invoice["invoice_id"]
    user["invoice_url"] = invoice["invoice_url"]

    send_message(chat_id, intro_text, payment_keyboard(invoice["invoice_url"], offer))


def finish_application(chat_id, user_id):
    user = get_user(user_id)

    send_message(
        chat_id,
        "Заявка принята ✨\n\n"
        f"Формат: {format_offer_text(user['offer'])}\n"
        f"Имя: {user['name']}\n\n"
        "Я получила всё, что нужно для начала разбора 💫"
    )

    admin_text = (
        "Новая заявка в Madame Mira 💸\n\n"
        f"Статус: {format_status_label('submitted')}\n"
        f"User ID: {user_id}\n"
        f"Формат: {format_offer_text(user['offer'])}\n"
        f"Оплата: {user.get('payment_method', 'не указан')}\n"
        f"Источник: {user.get('source', 'direct')}\n"
        f"Фокус: {user.get('focus', 'не выбран')}\n"
        f"Имя: {user['name']}\n\n"
        f"Ситуация:\n{user['situation']}\n\n"
        f"Что хочет понять:\n{user['question']}\n\n"
        f"Invoice ID: {user['invoice_id']}"
    )

    tg_post("sendMessage", payload={
        "chat_id": ADMIN_CHAT_ID,
        "text": admin_text,
        "reply_markup": admin_application_keyboard(user_id)
    })

    user["status"] = "submitted"


def stats_text():
    total_users = len(ANALYTICS["total_users"])
    sources = ANALYTICS["sources"]
    source_lines = []
    for key, value in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        source_lines.append(f"{key}: {value}")
    source_block = "\n".join(source_lines) if source_lines else "нет данных"

    return (
        "Статистика Madame Mira 📊\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Оплат mini: {ANALYTICS['paid_basic']}\n"
        f"Оплат deep: {ANALYTICS['paid_deep']}\n"
        f"Оплат VIP: {ANALYTICS['paid_vip']}\n"
        f"Чеков на карту: {ANALYTICS['receipts_sent']}\n"
        f"Разборов отправлено: {ANALYTICS['readings_sent']}\n\n"
        "Источники:\n"
        f"{source_block}"
    )


def process_warmups():
    current = now_ts()

    for user_id, user in USER_STATE.items():
        step = user.get("step")
        status = user.get("status")
        last_activity = user.get("last_activity", current)

        if status == "new" and step in ["waiting_clarify_1", "waiting_focus", "offer_ready", None]:
            if user["warmup_stage"] == 0 and current - last_activity >= WARMUP_1_DELAY:
                send_message(
                    user_id,
                    "Я всё ещё чувствую незавершённость в твоей истории ✨\n\n"
                    "Там есть важный внутренний момент, который мы пока не раскрыли."
                )
                user["warmup_stage"] = 1

            elif user["warmup_stage"] == 1 and current - last_activity >= WARMUP_2_DELAY:
                send_message(
                    user_id,
                    "Иногда сердце не отпускает тему просто так 💫\n\n"
                    "Если ты всё ещё в этой истории, я рядом."
                )
                user["warmup_stage"] = 2

        if user.get("status") == "reading_sent" and user.get("offer") == "basic":
            sent_at = user.get("reading_sent_at")
            if sent_at and not user.get("upsell_sent") and current - sent_at >= UPSELL_DELAY:
                send_message(
                    user_id,
                    "Я чувствую, что в твоей истории есть ещё слой глубже ✨\n\n"
                    "Если хочешь, я могу раскрыть ситуацию шире и показать больше, чем вошло в мини-разбор.",
                    upsell_keyboard()
                )
                user["upsell_sent"] = True

        if user.get("status") == "reading_sent" and user.get("offer") == "deep":
            sent_at = user.get("reading_sent_at")
            if sent_at and not user.get("vip_offer_sent") and current - sent_at >= UPSELL_DELAY:
                send_message(
                    user_id,
                    "Иногда после глубокого разбора становится видно, что нужна не только ясность, но и более тонкое сопровождение 💎\n\n"
                    "Если захочешь, я могу взять тебя в VIP-формат.",
                    vip_keyboard()
                )
                user["vip_offer_sent"] = True


def handle_user_message(chat_id, user_id, text):
    user = get_user(user_id)
    touch_user(user_id)

    if user["step"] == "followup":
        if user["followups_left"] <= 0:
            send_message(
                chat_id,
                "В рамках этого разбора я уже дала тебе максимум ✨\n\n"
                "Если захочешь пойти глубже, я рядом 💫"
            )
            return

        answer = make_followup_answer(user, text)
        send_message(chat_id, answer)

        user["followups_left"] -= 1

        if user["followups_left"] == 0:
            if user["offer"] == "basic":
                send_message(
                    chat_id,
                    "На этом мини-разбор завершается ✨\n\n"
                    "Если хочешь, я могу пойти глубже и раскрыть ситуацию шире.",
                    upsell_keyboard()
                )
            elif user["offer"] == "deep":
                send_message(
                    chat_id,
                    "На этом мы завершаем этот разбор ✨\n\n"
                    "Если почувствуешь, что тебе нужно более тонкое сопровождение, я рядом 💎",
                    vip_keyboard()
                )
            else:
                send_message(
                    chat_id,
                    "На этом мы завершаем этот этап ✨\n\n"
                    "Если захочешь вернуться ко мне позже, я рядом 💫"
                )
        return

    if user["step"] == "waiting_name":
        user["name"] = text
        user["step"] = "waiting_situation"
        send_message(chat_id, "Приняла 💫\n\nТеперь коротко опиши свою ситуацию.")
        return

    if user["step"] == "waiting_situation":
        user["situation"] = text
        user["step"] = "waiting_question"
        send_message(chat_id, "Хорошо.\n\nТеперь напиши, что именно ты хочешь понять или узнать в этом разборе.")
        return

    if user["step"] == "waiting_question":
        user["question"] = text
        finish_application(chat_id, user_id)
        return

    if user["step"] == "waiting_card_receipt":
        send_message(chat_id, "Жду фото или скрин чека ✨\n\nПросто отправь изображение сюда, и я передам его на проверку.")
        return

    if user["step"] == "waiting_clarify_1":
        user["reply_1"] = text
        user["step"] = "waiting_focus"
        send_message(
            chat_id,
            "Скажи, что тебе сейчас важнее всего ✨",
            focus_keyboard()
        )
        return

    topic_data = classify_topic(text)
    user["topic_class"] = topic_data["topic"]

    if not topic_data["supported"]:
        send_message(chat_id, unsupported_reply(text, topic_data["topic"]))
        user["step"] = None
        return

    user["initial_text"] = text
    user["warmup_stage"] = 0
    send_message(chat_id, first_reply(text))
    user["step"] = "waiting_clarify_1"


def handle_photo_or_document(chat_id, user_id, file_id, media_type):
    user = get_user(user_id)
    touch_user(user_id)

    if user["step"] != "waiting_card_receipt":
        send_message(chat_id, "Я увидела файл ✨\n\nЕсли это не чек по оплате, просто продолжай диалог.")
        return

    user["payment_method"] = "перевод на карту"
    user["status"] = "receipt_sent"
    ANALYTICS["receipts_sent"] += 1

    caption = (
        "Чек на ручную проверку 💳\n\n"
        f"Статус: {format_status_label(user['status'])}\n"
        f"User ID: {user_id}\n"
        f"Формат: {format_offer_text(user.get('offer'))}\n"
        f"Оплата: перевод на карту\n"
        f"Сумма: {format_card_amount_uah(user.get('offer'))} грн"
    )

    if media_type == "photo":
        send_photo(ADMIN_CHAT_ID, file_id, caption=caption, reply_markup=admin_receipt_keyboard(user_id))
    else:
        send_document(ADMIN_CHAT_ID, file_id, caption=caption, reply_markup=admin_receipt_keyboard(user_id))

    send_message(
        chat_id,
        "Чек получила ✨\n\n"
        "Я отправила его на ручную проверку. После подтверждения оплаты напишу тебе."
    )

    user["step"] = "waiting_manual_approval"


def main():
    global last_update_id

    while True:
        try:
            process_warmups()

            updates = get_updates()
            if "result" not in updates:
                time.sleep(1)
                continue

            for update in updates["result"]:
                last_update_id = update["update_id"] + 1

                if "message" in update:
                    message = update["message"]
                    chat_id = message["chat"]["id"]
                    user_id = message["from"]["id"]

                    if chat_id == ADMIN_CHAT_ID:
                        text = message.get("text", "").strip()
                        if text == "/stats":
                            send_message(ADMIN_CHAT_ID, stats_text())
                        continue

                    ANALYTICS["total_users"].add(user_id)

                    if "photo" in message:
                        file_id = message["photo"][-1]["file_id"]
                        handle_photo_or_document(chat_id, user_id, file_id, "photo")
                        continue

                    if "document" in message:
                        file_id = message["document"]["file_id"]
                        handle_photo_or_document(chat_id, user_id, file_id, "document")
                        continue

                    text = message.get("text", "").strip()
                    if not text:
                        continue

                    if text.startswith("/start"):
                        parts = text.split(maxsplit=1)
                        source = parts[1].strip() if len(parts) > 1 else "direct"
                        reset_user(user_id, source=source)
                        log_source(source)
                        send_message(
                            chat_id,
                            "Привет, я Madame Mira ✨\n\n"
                            "Расскажи, что сейчас тревожит тебя сильнее всего. Я мягко проведу тебя и помогу почувствовать, куда лучше смотреть дальше."
                        )
                    else:
                        handle_user_message(chat_id, user_id, text)

                elif "callback_query" in update:
                    query = update["callback_query"]
                    data = query["data"]
                    callback_chat_id = query["message"]["chat"]["id"]
                    callback_from_id = query["from"]["id"]
                    callback_message_id = query["message"]["message_id"]

                    answer_callback_query(query["id"])

                    if data == "show_formats":
                        send_message(callback_chat_id, "Сейчас доступны три формата ✨", formats_keyboard())

                    elif data == "show_format_details":
                        send_message(callback_chat_id, format_details_text())

                    elif data.startswith("details_"):
                        offer = data.split("_")[1]
                        send_message(callback_chat_id, single_format_details(offer))

                    elif data in ["focus_feelings", "focus_future", "focus_self", "focus_action"]:
                        user = get_user(callback_from_id)
                        focus_map = {
                            "focus_feelings": ("feelings", "понять чувства человека"),
                            "focus_future": ("future", "увидеть будущее ситуации"),
                            "focus_self": ("self", "разобраться в себе"),
                            "focus_action": ("action", "понять, что делать дальше")
                        }
                        focus_code, focus_label = focus_map[data]
                        user["focus"] = focus_code

                        result = recommend_offer(user["initial_text"], user["reply_1"], focus_code)
                        user["step"] = "offer_ready"

                        send_message(
                            callback_chat_id,
                            f"Я услышала: тебе сейчас важнее {focus_label} ✨\n\n{result['message']}"
                        )
                        send_offer_with_invoice(callback_chat_id, callback_from_id, result["offer"], "Вот формат, который я бы сейчас тебе предложила:")

                    elif data in ["basic_info", "deep_info", "vip_info"]:
                        user = get_user(callback_from_id)
                        offer = {
                            "basic_info": "basic",
                            "deep_info": "deep",
                            "vip_info": "vip"
                        }[data]
                        user["offer"] = offer
                        intro = {
                            "basic": "✨ Мини-разбор — $10.\n\nОн подойдёт, если тебе нужен быстрый и точный ответ на один главный вопрос.",
                            "deep": "🔮 Глубокий разбор — $20.\n\nОн подойдёт, если в ситуации много чувств, подтекста и важно увидеть картину глубже.",
                            "vip": "💎 VIP-разбор — $50.\n\nОн подойдёт, если тебе нужен не только разбор, но и более тонкое сопровождение и глубина."
                        }[offer]
                        send_offer_with_invoice(callback_chat_id, callback_from_id, offer, intro)

                    elif data == "help_pick":
                        user = get_user(callback_from_id)
                        send_message(
                            callback_chat_id,
                            "Давай выберем точнее ✨\n\nЧто тебе сейчас важнее всего?",
                            focus_keyboard()
                        )

                    elif data == "check_payment":
                        user = get_user(callback_from_id)
                        status = get_invoice_status(user.get("invoice_id"))

                        if status == "paid":
                            user["payment_method"] = "крипта"
                            user["step"] = "waiting_name"
                            user["status"] = "paid"

                            if user["offer"] == "basic":
                                ANALYTICS["paid_basic"] += 1
                            elif user["offer"] == "deep":
                                ANALYTICS["paid_deep"] += 1
                            elif user["offer"] == "vip":
                                ANALYTICS["paid_vip"] += 1

                            send_message(
                                callback_chat_id,
                                "Оплату вижу ✅\n\n"
                                "Теперь давай спокойно соберём заявку.\n\n"
                                "Сначала напиши своё имя."
                            )
                            send_admin_status_note(callback_from_id)
                        elif status in ["active", "pending"]:
                            send_message(
                                callback_chat_id,
                                "Я ещё не вижу подтверждённую оплату ✨\n\n"
                                "Если ты уже оплатил(а), подожди 10–20 секунд и нажми «Проверить оплату» ещё раз."
                            )
                        else:
                            send_message(
                                callback_chat_id,
                                "Пока не получилось подтвердить оплату.\n\n"
                                "Попробуй открыть счёт ещё раз или вернись чуть позже."
                            )

                    elif data.startswith("card_"):
                        user = get_user(callback_from_id)
                        offer = data.split("_")[1]
                        user["offer"] = offer
                        user["payment_method"] = "перевод на карту"
                        user["step"] = "waiting_card_receipt"
                        send_message(
                            callback_chat_id,
                            "💳 Перевод на карту\n\n"
                            f"Сумма: {format_card_amount_uah(offer)} грн\n"
                            f"Карта: {CARD_NUMBER}\n\n"
                            "После перевода пришли сюда фото или скрин чека. Я отправлю его на ручную проверку ✨"
                        )

                    elif data.startswith("admin_accept_"):
                        target_user_id = int(data.split("_")[2])
                        user = get_user(target_user_id)
                        user["payment_method"] = "перевод на карту"
                        user["step"] = "waiting_name"
                        user["status"] = "paid"

                        if user["offer"] == "basic":
                            ANALYTICS["paid_basic"] += 1
                        elif user["offer"] == "deep":
                            ANALYTICS["paid_deep"] += 1
                        elif user["offer"] == "vip":
                            ANALYTICS["paid_vip"] += 1

                        send_message(
                            target_user_id,
                            "Оплата подтверждена ✅\n\n"
                            "Теперь давай спокойно соберём заявку.\n\n"
                            "Сначала напиши своё имя."
                        )

                        try:
                            if "caption" in query["message"]:
                                new_caption = query["message"]["caption"] + "\n\nСтатус: 🟢 оплата подтверждена"
                                edit_message_caption(ADMIN_CHAT_ID, callback_message_id, new_caption, reply_markup=None)
                            else:
                                send_admin_status_note(target_user_id)
                        except Exception:
                            send_admin_status_note(target_user_id)

                    elif data.startswith("admin_reject_"):
                        target_user_id = int(data.split("_")[2])
                        user = get_user(target_user_id)
                        user["step"] = "waiting_card_receipt"
                        user["status"] = "receipt_rejected"

                        send_message(
                            target_user_id,
                            "Я пока не смогла подтвердить оплату ❗\n\n"
                            "Пожалуйста, проверь перевод и отправь чек ещё раз."
                        )

                        try:
                            if "caption" in query["message"]:
                                new_caption = query["message"]["caption"] + "\n\nСтатус: 🔴 чек отклонён"
                                edit_message_caption(ADMIN_CHAT_ID, callback_message_id, new_caption, reply_markup=None)
                            else:
                                send_admin_status_note(target_user_id)
                        except Exception:
                            send_admin_status_note(target_user_id)

                    elif data.startswith("admin_reading_"):
                        target_user_id = int(data.split("_")[2])
                        user = get_user(target_user_id)

                        if user.get("status") == "reading_sent":
                            send_message(ADMIN_CHAT_ID, f"Разбор для {target_user_id} уже был отправлен ✨")
                            continue

                        send_message(
                            target_user_id,
                            "Я вхожу в твою ситуацию глубже ✨\n\n"
                            "Сейчас соберу для тебя сам разбор."
                        )

                        text = make_reading(user)
                        send_message(target_user_id, text)
                        ANALYTICS["readings_sent"] += 1

                        if user["offer"] == "basic":
                            user["followups_left"] = 1
                            send_message(
                                target_user_id,
                                "По этому мини-разбору ты можешь задать мне ещё один уточняющий вопрос ✨"
                            )
                        elif user["offer"] == "deep":
                            user["followups_left"] = 2
                            send_message(
                                target_user_id,
                                "По этому глубокому разбору ты можешь задать мне ещё два уточняющих вопроса 💫"
                            )
                        else:
                            user["followups_left"] = 3
                            send_message(
                                target_user_id,
                                "В рамках VIP-разбора ты можешь задать мне ещё три уточняющих вопроса, и я буду рядом глубже 💎"
                            )

                        user["status"] = "reading_sent"
                        user["step"] = "followup"
                        user["reading_sent_at"] = now_ts()

                        try:
                            new_text = query["message"]["text"] + "\n\nСтатус: ✨ разбор отправлен"
                            edit_message(ADMIN_CHAT_ID, callback_message_id, new_text, reply_markup=None)
                        except Exception:
                            send_admin_status_note(target_user_id)

            time.sleep(1)

        except Exception:
            time.sleep(2)


if __name__ == "__main__":
    main()