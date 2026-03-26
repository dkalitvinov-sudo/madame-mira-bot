import os
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

URL = f"https://api.telegram.org/bot{TOKEN}/"
CRYPTO_API_URL = "https://pay.crypt.bot/api"

last_update_id = None
USER_STATE = {}


def get_updates():
    global last_update_id
    params = {"timeout": 100, "offset": last_update_id}
    response = requests.get(URL + "getUpdates", params=params, timeout=120)
    return response.json()


def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(URL + "sendMessage", json=payload, timeout=30)


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    requests.post(URL + "answerCallbackQuery", json=payload, timeout=30)


def notify_admin(text):
    if not ADMIN_CHAT_ID:
        print("ADMIN_CHAT_ID not set")
        return
    requests.post(
        URL + "sendMessage",
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
            "invoice_url": None
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
        "invoice_url": None
    }


def start_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ Мини-разбор $11", "callback_data": "basic_info"}],
            [{"text": "🔮 Глубокий разбор $29", "callback_data": "deep_info"}],
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


def choose_offer(text: str):
    t = text.lower().strip()

    deep_keywords = [
        "отнош", "парень", "муж", "бывш", "измен", "предал", "предательство",
        "ушел", "ушёл", "другая", "другой", "любов", "чувства", "больно",
        "сложно", "тяжело", "кризис", "развод", "расстав", "ревность",
        "запутал", "запуталась", "запутался", "не понимаю", "что делать",
        "будущее", "судьба", "энергия", "выбор", "подруга"
    ]

    basic_keywords = [
        "быстро", "кратко", "коротко", "мини", "один вопрос",
        "простой вопрос", "быстрый ответ"
    ]

    deep_score = 0
    basic_score = 0

    for word in deep_keywords:
        if word in t:
            deep_score += 1

    for word in basic_keywords:
        if word in t:
            basic_score += 1

    if len(t) > 80:
        deep_score += 1

    if deep_score >= 2 and deep_score > basic_score:
        return "deep"

    if basic_score >= 1 and basic_score >= deep_score:
        return "basic"

    return "unknown"


def create_crypto_invoice(user_id, offer):
    if not CRYPTO_PAY_TOKEN:
        print("CRYPTO_PAY_TOKEN not set")
        return None

    amount = "11" if offer == "basic" else "29"
    description = "Мини-разбор" if offer == "basic" else "Глубокий разбор"
    payload_value = f"user_{user_id}_{offer}"

    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    data = {
        "asset": "USDT",
        "amount": amount,
        "description": description,
        "payload": payload_value
    }

    try:
        response = requests.post(
            f"{CRYPTO_API_URL}/createInvoice",
            headers=headers,
            json=data,
            timeout=30
        )
        result = response.json()

        if not result.get("ok"):
            print("CRYPTO createInvoice error:", result)
            return None

        invoice = result["result"]
        return {
            "invoice_id": invoice["invoice_id"],
            "invoice_url": invoice["bot_invoice_url"]
        }
    except Exception as e:
        print("CRYPTO createInvoice exception:", str(e))
        return None


def get_invoice_status(invoice_id):
    if not CRYPTO_PAY_TOKEN or not invoice_id:
        return None

    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    params = {"invoice_ids": str(invoice_id)}

    try:
        response = requests.get(
            f"{CRYPTO_API_URL}/getInvoices",
            headers=headers,
            params=params,
            timeout=30
        )
        result = response.json()

        if not result.get("ok"):
            print("CRYPTO getInvoices error:", result)
            return None

        items = result["result"]["items"]
        if not items:
            return None

        return items[0].get("status")
    except Exception as e:
        print("CRYPTO getInvoices exception:", str(e))
        return None


def format_offer_text(offer):
    if offer == "basic":
        return "Мини-разбор $11"
    if offer == "deep":
        return "Глубокий разбор $29"
    return "Не выбран"


def send_offer_with_invoice(chat_id, user_id, offer, intro_text):
    user = get_user_state(user_id)
    user["offer"] = offer

    invoice = create_crypto_invoice(user_id, offer)
    if not invoice:
        send_message(
            chat_id,
            "Не получилось создать счёт 😔 Попробуй ещё раз через минуту."
        )
        return

    user["invoice_id"] = invoice["invoice_id"]
    user["invoice_url"] = invoice["invoice_url"]

    send_message(
        chat_id,
        intro_text,
        payment_keyboard(invoice["invoice_url"])
    )


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

    offer = choose_offer(text)

    if offer == "basic":
        send_offer_with_invoice(
            chat_id,
            user_id,
            "basic",
            "Я бы советовала тебе ✨ Мини-разбор за $11.\n\n"
            "Потому что здесь лучше подходит быстрый и точный ответ на один главный вопрос."
        )

    elif offer == "deep":
        send_offer_with_invoice(
            chat_id,
            user_id,
            "deep",
            "Я бы советовала тебе 🔮 Глубокий разбор за $29.\n\n"
            "Потому что ситуация выглядит эмоционально сложной и требует более глубокого разбора."
        )

    else:
        send_message(
            chat_id,
            "Я услышала тебя ✨\n\nПока здесь лучше выбрать формат вручную:",
            start_keyboard()
        )


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
                            "Привет, я Madame Mira ✨\n\n"
                            "Опиши свою ситуацию одним сообщением, и я подскажу, какой формат тебе подойдет лучше.",
                            start_keyboard()
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

                    if data == "basic_info":
                        send_offer_with_invoice(
                            chat_id,
                            user_id,
                            "basic",
                            "✨ Мини-разбор — $11\n\n"
                            "Быстрый и точный ответ на один главный вопрос."
                        )

                    elif data == "deep_info":
                        send_offer_with_invoice(
                            chat_id,
                            user_id,
                            "deep",
                            "🔮 Глубокий разбор — $29\n\n"
                            "Полный разбор ситуации с пониманием причин и дальнейшего движения."
                        )

                    elif data == "help_pick":
                        send_message(
                            chat_id,
                            "Напиши одним сообщением, что тебя сейчас больше всего волнует, и я помогу выбрать формат 💬"
                        )

                    elif data == "check_payment":
                        status = get_invoice_status(user.get("invoice_id"))

                        if status == "paid":
                            user["step"] = "waiting_name"
                            send_message(
                                chat_id,
                                "Оплату вижу ✅\n\n"
                                "Давай соберем заявку по шагам.\n\n"
                                "Сначала напиши своё имя."
                            )
                        elif status in ["active", "pending"]:
                            send_message(
                                chat_id,
                                "Я пока не вижу завершённую оплату 👀\n\n"
                                "Если ты уже оплатил(а), подожди немного и нажми «Проверить оплату» ещё раз."
                            )
                        else:
                            send_message(
                                chat_id,
                                "Не получилось подтвердить оплату.\n\n"
                                "Попробуй создать счёт заново или напиши позже."
                            )

        except Exception as e:
            print("RUNTIME ERROR:", str(e))


if __name__ == "__main__":
    main()