import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CARD_NUMBER = os.getenv("CARD_NUMBER", "1111 2222 3333 4444")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"
CRYPTO_API_URL = "https://pay.crypt.bot/api"

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

last_update_id = None
USER_STATE = {}

BASIC_USD = "10"
DEEP_USD = "20"

BASIC_UAH = "440"
DEEP_UAH = "880"


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


def send_photo(chat_id, file_id, caption=None, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "photo": file_id
    }
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API_URL}/sendPhoto", data=payload, timeout=30)


def send_document(chat_id, file_id, caption=None, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "document": file_id
    }
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API_URL}/sendDocument", data=payload, timeout=30)


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


def notify_admin_with_buttons(text, user_id):
    if not ADMIN_CHAT_ID:
        print("ADMIN_CHAT_ID not set")
        return

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Подтвердить", "callback_data": f"admin_accept_{user_id}"},
                {"text": "❌ Отклонить", "callback_data": f"admin_reject_{user_id}"}
            ]
        ]
    }

    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={
            "chat_id": ADMIN_CHAT_ID,
            "text": text,
            "reply_markup": keyboard
        },
        timeout=30
    )


def admin_receipt_keyboard(user_id):
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Подтвердить", "callback_data": f"admin_accept_{user_id}"},
                {"text": "❌ Отклонить", "callback_data": f"admin_reject_{user_id}"}
            ]
        ]
    }


def get_user_state(user_id):
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {
            "step": None,
            "offer": None,
            "payment_method": None,
            "name": "",
            "situation": "",
            "question": "",
            "invoice_id": None,
            "invoice_url": None,
            "initial_text": "",
            "reply_1": ""
        }
    return USER_STATE[user_id]


def reset_user_form(user_id):
    USER_STATE[user_id] = {
        "step": None,
        "offer": None,
        "payment_method": None,
        "name": "",
        "situation": "",
        "question": "",
        "invoice_id": None,
        "invoice_url": None,
        "initial_text": "",
        "reply_1": ""
    }


def formats_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ Мини-разбор $10", "callback_data": "basic_info"}],
            [{"text": "🔮 Глубокий разбор $20", "callback_data": "deep_info"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def payment_keyboard(invoice_url, offer):
    return {
        "inline_keyboard": [
            [{"text": "💸 Оплатить криптой", "url": invoice_url}],
            [{"text": "✅ Проверить оплату", "callback_data": "check_payment"}],
            [{"text": "💳 Перевод на карту", "callback_data": f"card_{offer}"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def choose_offer_local(text: str):
    t = text.lower().strip()

    strong_deep_keywords = [
        "измена", "предательство", "ушел к другой", "ушёл к другой",
        "развод", "любовный треугольник", "предал", "бросил", "другая женщина"
    ]

    medium_deep_keywords = [
        "отнош", "парень", "муж", "бывш", "ушел", "ушёл", "другая", "другой",
        "любов", "чувства", "больно", "сложно", "тяжело", "кризис",
        "расстав", "ревность", "запутал", "запуталась", "запутался",
        "не понимаю", "что делать", "будущее", "подруга", "одиночество",
        "не складываются", "страдаю", "потеряла"
    ]

    basic_keywords = [
        "быстро", "кратко", "коротко", "мини", "один вопрос",
        "простой вопрос", "быстрый ответ", "короткий ответ"
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
Стиль: женственный, мягкий, мистический, тёплый.

Нужно написать ПЕРВОЕ сообщение после того, как человек поделился ситуацией.

Правила:
1. Покажи, что ты почувствовала его состояние.
2. Дай короткий эффект "я тебя вижу".
3. Задай ОДИН тёплый вопрос.
4. Не продавай.
5. Не упоминай оплату, цены, форматы.
6. На русском.
7. Коротко и красиво.

Верни строго JSON:
{{
  "message": "текст"
}}

Сообщение пользователя:
{user_text}
""".strip()

    fallback = {
        "message": "Я чувствую, что за этими словами стоит усталость сердца ✨\n\nСкажи, что ранит сильнее: сама ситуация или то, что внутри до сих пор нет ясности?"
    }

    return gpt_json(prompt, fallback)


def gpt_recommend(initial_text: str, reply_1: str):
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
Ответ человека: {reply_1}
""".strip()

    fallback_offer = choose_offer_local(f"{initial_text} {reply_1}")

    if fallback_offer == "basic":
        fallback = {
            "offer": "basic",
            "message": "Я бы мягко повела тебя в ✨ Мини-разбор за $10.\n\nЗдесь сейчас важнее получить один ясный и точный ответ, который снимет лишнюю неопределённость."
        }
    else:
        fallback = {
            "offer": "deep",
            "message": "Я бы повела тебя в 🔮 Глубокий разбор за $20.\n\nПотому что здесь чувствуется более глубокий внутренний узел, который лучше раскрывать шире."
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

    amount = BASIC_USD if offer == "basic" else DEEP_USD
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


def format_card_amount_uah(offer):
    return BASIC_UAH if offer == "basic" else DEEP_UAH


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

    send_message(chat_id, intro_text, payment_keyboard(invoice["invoice_url"], offer))


def finish_application(chat_id, user_id):
    user = get_user_state(user_id)
    offer_text = format_offer_text(user["offer"])
    payment_method = user.get("payment_method", "не указан")

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
        f"Оплата: {payment_method}\n"
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

    if user["step"] == "waiting_card_receipt":
        send_message(
            chat_id,
            "Жду фото или скрин чека ✨\n\nПросто отправь изображение сюда, и я передам его на проверку."
        )
        return

    if user["step"] == "waiting_card_receipt_text":
        notify_admin_with_buttons(
            "Запрос на ручную проверку оплаты 💳\n\n"
            f"User ID: {user_id}\n"
            f"Формат: {format_offer_text(user.get('offer'))}\n"
            f"Оплата: перевод на карту\n"
            f"Сумма: {format_card_amount_uah(user.get('offer'))} грн\n\n"
            f"Сообщение клиента:\n{text}",
            user_id
        )

        send_message(
            chat_id,
            "Я передала сообщение на ручную проверку ✨\n\n"
            "Как только оплата будет проверена, я напишу тебе."
        )
        user["step"] = "waiting_manual_approval"
        return

    if user["step"] == "waiting_clarify_1":
        user["reply_1"] = text
        result = gpt_recommend(user["initial_text"], text)
        user["step"] = "offer_ready"
        send_offer_with_invoice(chat_id, user_id, result["offer"], result["message"])
        return

    user["initial_text"] = text
    first = gpt_first_reply(text)
    user["step"] = "waiting_clarify_1"
    send_message(chat_id, first["message"])


def handle_photo_or_document(chat_id, user_id, file_id, media_type):
    user = get_user_state(user_id)

    if user["step"] != "waiting_card_receipt":
        send_message(
            chat_id,
            "Я увидела файл ✨\n\nЕсли это не чек по оплате, просто продолжай диалог."
        )
        return

    caption = (
        "Чек на ручную проверку 💳\n\n"
        f"User ID: {user_id}\n"
        f"Формат: {format_offer_text(user.get('offer'))}\n"
        f"Оплата: перевод на карту\n"
        f"Сумма: {format_card_amount_uah(user.get('offer'))} грн"
    )

    if ADMIN_CHAT_ID:
        if media_type == "photo":
            send_photo(
                ADMIN_CHAT_ID,
                file_id,
                caption=caption,
                reply_markup=admin_receipt_keyboard(user_id)
            )
        else:
            send_document(
                ADMIN_CHAT_ID,
                file_id,
                caption=caption,
                reply_markup=admin_receipt_keyboard(user_id)
            )

    send_message(
        chat_id,
        "Чек получила ✨\n\n"
        "Я отправила его на ручную проверку. После подтверждения оплаты напишу тебе."
    )

    user["payment_method"] = "перевод на карту"
    user["step"] = "waiting_manual_approval"


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
                    message = update["message"]
                    chat_id = message["chat"]["id"]
                    user_id = message["from"]["id"]

                    # Игнорируем обычные сообщения из админ-группы
                    if chat_id == ADMIN_CHAT_ID:
                        continue

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

                    if text == "/start":
                        reset_user_form(user_id)
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

                    answer_callback_query(query["id"])

                    if data == "show_formats":
                        send_message(
                            callback_chat_id,
                            "Сейчас доступны два формата разбора ✨",
                            formats_keyboard()
                        )

                    elif data == "basic_info":
                        user = get_user_state(callback_from_id)
                        user["offer"] = "basic"
                        send_offer_with_invoice(
                            callback_chat_id,
                            callback_from_id,
                            "basic",
                            "✨ Мини-разбор — $10.\n\n"
                            "Он подойдёт, если тебе нужен быстрый и точный ответ на один главный вопрос."
                        )

                    elif data == "deep_info":
                        user = get_user_state(callback_from_id)
                        user["offer"] = "deep"
                        send_offer_with_invoice(
                            callback_chat_id,
                            callback_from_id,
                            "deep",
                            "🔮 Глубокий разбор — $20.\n\n"
                            "Он подойдёт, если в ситуации много чувств, подтекста и важно увидеть картину глубже."
                        )

                    elif data == "help_pick":
                        user = get_user_state(callback_from_id)
                        user["step"] = None
                        user["initial_text"] = ""
                        user["reply_1"] = ""
                        send_message(
                            callback_chat_id,
                            "Напиши одним сообщением, что тебя сейчас больше всего волнует, и я мягко подведу тебя к нужному формату 💬"
                        )

                    elif data == "check_payment":
                        user = get_user_state(callback_from_id)
                        status = get_invoice_status(user.get("invoice_id"))

                        if status == "paid":
                            user["payment_method"] = "крипта"
                            user["step"] = "waiting_name"
                            send_message(
                                callback_chat_id,
                                "Оплату вижу ✅\n\n"
                                "Теперь давай спокойно соберём заявку.\n\n"
                                "Сначала напиши своё имя."
                            )
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

                    elif data == "card_basic":
                        user = get_user_state(callback_from_id)
                        user["offer"] = "basic"
                        user["payment_method"] = "перевод на карту"
                        user["step"] = "waiting_card_receipt"
                        send_message(
                            callback_chat_id,
                            "💳 Перевод на карту\n\n"
                            f"Сумма: {BASIC_UAH} грн\n"
                            f"Карта: {CARD_NUMBER}\n\n"
                            "После перевода пришли сюда фото или скрин чека. Я отправлю его на ручную проверку ✨"
                        )

                    elif data == "card_deep":
                        user = get_user_state(callback_from_id)
                        user["offer"] = "deep"
                        user["payment_method"] = "перевод на карту"
                        user["step"] = "waiting_card_receipt"
                        send_message(
                            callback_chat_id,
                            "💳 Перевод на карту\n\n"
                            f"Сумма: {DEEP_UAH} грн\n"
                            f"Карта: {CARD_NUMBER}\n\n"
                            "После перевода пришли сюда фото или скрин чека. Я отправлю его на ручную проверку ✨"
                        )

                    elif data.startswith("admin_accept_"):
                        target_user_id = int(data.split("_")[2])
                        user = get_user_state(target_user_id)
                        user["payment_method"] = "перевод на карту"
                        user["step"] = "waiting_name"

                        send_message(
                            target_user_id,
                            "Оплата подтверждена ✅\n\n"
                            "Теперь давай спокойно соберём заявку.\n\n"
                            "Сначала напиши своё имя."
                        )

                        send_message(
                            ADMIN_CHAT_ID,
                            f"Заявка {target_user_id} подтверждена ✅"
                        )

                    elif data.startswith("admin_reject_"):
                        target_user_id = int(data.split("_")[2])
                        user = get_user_state(target_user_id)
                        user["step"] = "waiting_card_receipt"

                        send_message(
                            target_user_id,
                            "Я пока не смогла подтвердить оплату ❗\n\n"
                            "Пожалуйста, проверь перевод и отправь чек ещё раз."
                        )

                        send_message(
                            ADMIN_CHAT_ID,
                            f"Заявка {target_user_id} отклонена ❌"
                        )

        except Exception as e:
            print("RUNTIME ERROR:", str(e))


if __name__ == "__main__":
    main()