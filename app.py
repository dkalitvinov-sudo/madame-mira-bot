import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"
CRYPTO_API_URL = "https://pay.crypt.bot/api"

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

last_update_id = None
USER_STATE = {}


def get_updates():
    global last_update_id
    params = {"timeout": 100, "offset": last_update_id}
    response = requests.get(f"{TELEGRAM_API_URL}/getUpdates", params=params, timeout=120)
    return response.json()


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=30)


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json=payload, timeout=30)


def notify_admin(text):
    if not ADMIN_CHAT_ID:
        print("ADMIN_CHAT_ID not set")
        return

    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={"chat_id": ADMIN_CHAT_ID, "text": text},
        timeout=30
    )


def get_user_state(user_id):
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {
            "step": None,
            "offer": None,
            "name": "",
            "situation": "",
            "question": "",
            "invoice_id": None,
            "invoice_url": None,
            "initial_text": "",
            "reply_1": "",
            "reply_2": ""
        }
    return USER_STATE[user_id]


def reset_user_form(user_id):
    USER_STATE[user_id] = {
        "step": None,
        "offer": None,
        "name": "",
        "situation": "",
        "question": "",
        "invoice_id": None,
        "invoice_url": None,
        "initial_text": "",
        "reply_1": "",
        "reply_2": ""
    }


def formats_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ Мини-разбор $10", "callback_data": "basic_info"}],
            [{"text": "🔮 Глубокий разбор $20", "callback_data": "deep_info"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def payment_keyboard(invoice_url):
    return {
        "inline_keyboard": [
            [{"text": "💸 Оплатить", "url": invoice_url}],
            [{"text": "✅ Проверить оплату", "callback_data": "check_payment"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def choose_offer_local(text: str):
    t = text.lower().strip()

    strong_deep_keywords = [
        "измена", "предательство", "ушел к другой", "ушёл к другой",
        "развод", "любовный треугольник", "предал", "предательство",
        "бросил", "муж ушел", "муж ушёл", "другая женщина", "другой мужчина"
    ]

    medium_deep_keywords = [
        "отнош", "парень", "муж", "бывш", "ушел", "ушёл", "другая", "другой",
        "любов", "чувства", "больно", "сложно", "тяжело", "кризис",
        "расстав", "ревность", "запутал", "запуталась", "запутался",
        "не понимаю", "что делать", "будущее", "судьба", "подруга",
        "одиночество", "не складываются", "страдаю", "потеряла"
    ]

    basic_keywords = [
        "быстро", "кратко", "коротко", "мини", "один вопрос",
        "простой вопрос", "быстрый ответ", "короткий ответ", "один главный вопрос"
    ]

    deep_score = 0
    basic_score = 0

    for word in strong_deep_keywords:
        if word in t:
            deep_score += 3

    for word in medium_deep_keywords:
        if word in t:
            deep_score += 1

    for word in basic_keywords:
        if word in t:
            basic_score += 2

    if len(t) > 180:
        deep_score += 2
    elif len(t) < 60:
        basic_score += 1

    # Подталкиваем к cheaper по умолчанию
    if deep_score >= 4:
        return "deep"

    if basic_score >= 1:
        return "basic"

    if deep_score >= 2 and basic_score == 0:
        return "basic"

    return "basic"


def gpt_json(prompt, fallback):
    if not client:
        return fallback

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )
        text = (response.output_text or "").strip()
        data = json.loads(text)
        return data
    except Exception as e:
        print("GPT ERROR:", str(e))
        return fallback


def gpt_first_reply(user_text: str):
    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мягкий, мистический, дорогой, тёплый, но естественный.

Нужно написать ПЕРВОЕ сообщение после того, как человек поделился ситуацией.

Правила:
1. Покажи, что ты почувствовала его состояние.
2. Дай короткий эффект "я тебя вижу".
3. Задай ОДИН тёплый вопрос.
4. Не продавай.
5. Не упоминай оплату, цены, форматы.
6. Коротко, красиво, по-человечески.
7. На русском.
8. Не используй списки.

Верни строго JSON:
{{
  "message": "текст"
}}

Сообщение пользователя:
{user_text}
""".strip()

    fallback = {
        "message": "Я чувствую, что за этими словами стоит не просто вопрос, а усталость сердца ✨\n\nСкажи, что ранит сильнее всего: сама ситуация или то, что внутри до сих пор нет ясности?"
    }

    return gpt_json(prompt, fallback)


def gpt_second_reply(initial_text: str, reply_1: str):
    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мистический, мягкий, живой, премиальный.

Нужно написать ВТОРОЕ сообщение в диалоге.
У тебя уже есть:
1. первое сообщение клиента
2. его ответ на первый вопрос

Задача:
1. Мягко углубить разговор
2. Дать ощущение, что ты почувствовала суть
3. Добавить лёгкий эффект угадывания
4. Задать ещё один короткий вопрос
5. Не продавать
6. Не упоминать услуги, форматы, цены
7. На русском
8. Коротко и красиво

Верни строго JSON:
{{
  "message": "текст"
}}

Первое сообщение:
{initial_text}

Ответ человека:
{reply_1}
""".strip()

    fallback = {
        "message": "Я тебя чувствую ✨\n\nПохоже, здесь боль не только в самом человеке, а ещё и в том, что внутри слишком долго нет опоры.\n\nСкажи, тебе сейчас важнее понять, есть ли у этой истории будущее, или вернуть себе внутреннюю ясность?"
    }

    return gpt_json(prompt, fallback)


def gpt_pre_offer_reply(initial_text: str, reply_1: str, reply_2: str):
    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мягкий, мистический, премиальный.

Нужно написать ТРЕТЬЕ сообщение перед продажей.

Задача:
1. Дать мини-инсайт
2. Показать, что ты уловила суть
3. Создать доверие
4. Не называть цену
5. Не вставлять кнопки
6. Подвести к тому, что ты можешь помочь ясностью
7. На русском
8. Коротко и красиво

Верни строго JSON:
{{
  "message": "текст"
}}

Диалог:
Первое сообщение: {initial_text}
Ответ 1: {reply_1}
Ответ 2: {reply_2}
""".strip()

    fallback = {
        "message": "Я уже чувствую основной узел этой истории ✨\n\nЗдесь проблема не только в событиях снаружи, а в том, что внутри слишком долго не было ясности.\n\nА ясность сейчас как раз может вернуть тебе опору."
    }

    return gpt_json(prompt, fallback)


def gpt_recommend(initial_text: str, reply_1: str, reply_2: str):
    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мягкий, мистический, премиальный.

Сейчас нужно сделать мягкую продажу после короткого прогрева.

Есть только 2 формата:
- basic = Мини-разбор $10
- deep = Глубокий разбор $20

Очень важно:
1. Сначала смотри, можно ли помочь через более лёгкий вход.
2. Если ситуация не критически тяжёлая и не многослойная, предпочитай basic.
3. Deep выбирай только когда в истории реально много боли, запутанности, измены, тяжёлой динамики или большого контекста.
4. Выбери только ОДИН формат.
5. Объясни, почему он подходит.
6. Сделай это мягко и красиво, без давления.
7. Не перечисляй оба варианта.
8. На русском.

Верни строго JSON:
{{
  "offer": "basic" или "deep",
  "message": "текст"
}}

Диалог:
Первое сообщение: {initial_text}
Ответ 1: {reply_1}
Ответ 2: {reply_2}
""".strip()

    fallback_offer = choose_offer_local(f"{initial_text} {reply_1} {reply_2}")

    if fallback_offer == "basic":
        fallback = {
            "offer": "basic",
            "message": "Я бы мягко повела тебя в ✨ Мини-разбор за $10.\n\nЗдесь сейчас важнее получить один ясный и точный ответ, который снимет лишнюю неопределённость."
        }
    else:
        fallback = {
            "offer": "deep",
            "message": "Я бы повела тебя в 🔮 Глубокий разбор за $20.\n\nПотому что здесь чувствуется не один вопрос, а более глубокий внутренний узел, который лучше раскрывать шире."
        }

    data = gpt_json(prompt, fallback)

    offer = data.get("offer", fallback["offer"])
    message = data.get("message", fallback["message"])

    if offer not in ["basic", "deep"]:
        offer = fallback["offer"]

    return {
        "offer": offer,
        "message": message
    }


def create_crypto_invoice(user_id, offer):
    if not CRYPTO_PAY_TOKEN:
        print("CRYPTO_PAY_TOKEN not set")
        return None

    amount = "10" if offer == "basic" else "20"
    description = "Mini" if offer == "basic" else "Deep"
    payload_value = f"user_{user_id}_{offer}"

    try:
        response = requests.post(
            f"{CRYPTO_API_URL}/createInvoice",
            headers={
                "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
                "Content-Type": "application/json"
            },
            json={
                "asset": "USDT",
                "amount": amount,
                "description": description,
                "payload": payload_value
            },
            timeout=30
        )

        print("CRYPTO CREATE:", response.text)
        data = response.json()

        if not data.get("ok"):
            print("CRYPTO CREATE ERROR:", data)
            return None

        result = data["result"]
        return {
            "invoice_id": result["invoice_id"],
            "invoice_url": result["bot_invoice_url"]
        }
    except Exception as e:
        print("CRYPTO CREATE EXCEPTION:", str(e))
        return None


def get_invoice_status(invoice_id):
    if not CRYPTO_PAY_TOKEN or not invoice_id:
        return None

    try:
        response = requests.get(
            f"{CRYPTO_API_URL}/getInvoices",
            headers={"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN},
            params={"invoice_ids": str(invoice_id)},
            timeout=30
        )

        print("CRYPTO STATUS:", response.text)
        data = response.json()

        if not data.get("ok"):
            print("CRYPTO STATUS ERROR:", data)
            return None

        items = data["result"]["items"]
        if not items:
            return None

        return items[0].get("status")
    except Exception as e:
        print("CRYPTO STATUS EXCEPTION:", str(e))
        return None


def format_offer_text(offer):
    if offer == "basic":
        return "Мини-разбор $10"
    if offer == "deep":
        return "Глубокий разбор $20"
    return "Не выбран"


def send_offer_with_invoice(chat_id, user_id, offer, intro_text):
    user = get_user_state(user_id)
    user["offer"] = offer

    invoice = create_crypto_invoice(user_id, offer)
    if not invoice:
        send_message(
            chat_id,
            "Не получилось создать счёт 😔\n\nПопробуй ещё раз через минуту."
        )
        return

    user["invoice_id"] = invoice["invoice_id"]
    user["invoice_url"] = invoice["invoice_url"]

    send_message(chat_id, intro_text, payment_keyboard(invoice["invoice_url"]))


def finish_application(chat_id, user_id):
    user = get_user_state(user_id)
    offer_text = format_offer_text(user["offer"])

    send_message(
        chat_id,
        "Заявка принята ✨\n\n"
        f"Формат: {offer_text}\n"
        f"Имя: {user['name']}\n\n"
        "Я получила всё, что нужно для начала разбора 💫"
    )

    admin_text = (
        "Новая заявка в Madame Mira 💸\n\n"
        f"User ID: {user_id}\n"
        f"Формат: {offer_text}\n"
        f"Имя: {user['name']}\n\n"
        f"Ситуация:\n{user['situation']}\n\n"
        f"Что хочет понять:\n{user['question']}\n\n"
        f"Invoice ID: {user['invoice_id']}"
    )

    notify_admin(admin_text)
    user["step"] = "done"


def handle_user_message(chat_id, user_id, text):
    user = get_user_state(user_id)

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

    if user["step"] == "waiting_clarify_1":
        user["reply_1"] = text
        second = gpt_second_reply(user["initial_text"], text)
        user["step"] = "waiting_clarify_2"
        send_message(chat_id, second["message"])
        return

    if user["step"] == "waiting_clarify_2":
        user["reply_2"] = text
        pre_offer = gpt_pre_offer_reply(
            user["initial_text"],
            user["reply_1"],
            user["reply_2"]
        )
        send_message(chat_id, pre_offer["message"])

        result = gpt_recommend(
            user["initial_text"],
            user["reply_1"],
            user["reply_2"]
        )
        user["step"] = "offer_ready"
        send_offer_with_invoice(chat_id, user_id, result["offer"], result["message"])
        return

    user["initial_text"] = text
    first = gpt_first_reply(text)
    user["step"] = "waiting_clarify_1"
    send_message(chat_id, first["message"])


def main():
    global last_update_id

    print("Bot started...")

    while True:
        try:
            updates = get_updates()

            if "result" not in updates:
                continue

            for update in updates["result"]:
                last_update_id = update["update_id"] + 1

                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    user_id = update["message"]["from"]["id"]
                    text = update["message"].get("text", "").strip()

                    if not text:
                        continue

                    if text == "/start":
                        reset_user_form(user_id)
                        send_message(
                            chat_id,
                            "Привет, я Madame Mira ✨\n\nРасскажи, что сейчас тревожит тебя сильнее всего. Я мягко проведу тебя и помогу почувствовать, куда лучше смотреть дальше."
                        )
                    else:
                        handle_user_message(chat_id, user_id, text)

                elif "callback_query" in update:
                    query = update["callback_query"]
                    data = query["data"]
                    chat_id = query["message"]["chat"]["id"]
                    user_id = query["from"]["id"]

                    user = get_user_state(user_id)
                    answer_callback_query(query["id"])

                    if data == "show_formats":
                        send_message(
                            chat_id,
                            "Сейчас доступны два формата разбора ✨",
                            formats_keyboard()
                        )

                    elif data == "basic_info":
                        user["offer"] = "basic"
                        send_offer_with_invoice(
                            chat_id,
                            user_id,
                            "basic",
                            "✨ Мини-разбор — $10\n\nОн подойдёт, если тебе нужен быстрый и точный ответ на один главный вопрос."
                        )

                    elif data == "deep_info":
                        user["offer"] = "deep"
                        send_offer_with_invoice(
                            chat_id,
                            user_id,
                            "deep",
                            "🔮 Глубокий разбор — $20\n\nОн подойдёт, если в ситуации много чувств, подтекста и важно увидеть картину глубже."
                        )

                    elif data == "help_pick":
                        user["step"] = None
                        user["initial_text"] = ""
                        user["reply_1"] = ""
                        user["reply_2"] = ""
                        send_message(
                            chat_id,
                            "Напиши одним сообщением, что тебя сейчас больше всего волнует, и я мягко подведу тебя к нужному формату 💬"
                        )

                    elif data == "check_payment":
                        status = get_invoice_status(user.get("invoice_id"))

                        if status == "paid":
                            user["step"] = "waiting_name"
                            send_message(
                                chat_id,
                                "Оплату вижу ✅\n\nТеперь давай спокойно соберём заявку.\n\nСначала напиши своё имя."
                            )
                        elif status in ["active", "pending"]:
                            send_message(
                                chat_id,
                                "Я ещё не вижу подтверждённую оплату ✨\n\nЕсли ты уже оплатил(а), подожди 10–20 секунд и нажми «Проверить оплату» ещё раз."
                            )
                        else:
                            send_message(
                                chat_id,
                                "Пока не получилось подтвердить оплату.\n\nПопробуй открыть счёт ещё раз или вернись чуть позже."
                            )

        except Exception as e:
            print("RUNTIME ERROR:", str(e))


if __name__ == "__main__":
    main()