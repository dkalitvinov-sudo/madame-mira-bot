import os
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
URL = f"https://api.telegram.org/bot{TOKEN}/"

last_update_id = None

CRYPTO_11 = "https://t.me/send?start=IVhQvvzpJ7nd"
CRYPTO_29 = "https://t.me/send?start=IVlbsVdZNwQK"

USER_STATE = {}


def get_updates():
    global last_update_id
    params = {"timeout": 100, "offset": last_update_id}
    response = requests.get(URL + "getUpdates", params=params, timeout=120)
    return response.json()


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    requests.post(URL + "sendMessage", json=payload, timeout=30)


def notify_admin(text):
    if not ADMIN_CHAT_ID:
        print("ADMIN_CHAT_ID not set")
        return

    requests.post(
        URL + "sendMessage",
        json={
            "chat_id": ADMIN_CHAT_ID,
            "text": text
        },
        timeout=30
    )


def answer_callback_query(callback_query_id):
    requests.post(
        URL + "answerCallbackQuery",
        json={"callback_query_id": callback_query_id},
        timeout=30
    )


def start_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ Мини-разбор $11", "callback_data": "basic_info"}],
            [{"text": "🔮 Глубокий разбор $29", "callback_data": "deep_info"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def payment_keyboard_for_offer(offer: str):
    if offer == "basic":
        return {
            "inline_keyboard": [
                [{"text": "💰 Оплатить $11 криптой", "url": CRYPTO_11}],
                [{"text": "✅ Я оплатил(а)", "callback_data": "paid"}],
                [{"text": "🔮 Выбрать глубокий $29", "callback_data": "deep_info"}],
                [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
            ]
        }

    return {
        "inline_keyboard": [
            [{"text": "🔮 Оплатить $29 криптой", "url": CRYPTO_29}],
            [{"text": "✅ Я оплатил(а)", "callback_data": "paid"}],
            [{"text": "✨ Выбрать мини $11", "callback_data": "basic_info"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def get_user_state(user_id):
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {
            "step": None,
            "offer": None,
            "name": "",
            "situation": "",
            "question": ""
        }
    return USER_STATE[user_id]


def reset_user_form(user_id):
    USER_STATE[user_id] = {
        "step": None,
        "offer": None,
        "name": "",
        "situation": "",
        "question": ""
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


def finish_application(chat_id, user_id):
    user = get_user_state(user_id)

    if user["offer"] == "basic":
        offer_text = "Мини-разбор $11"
    elif user["offer"] == "deep":
        offer_text = "Глубокий разбор $29"
    else:
        offer_text = "Не указан"

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
        f"Что хочет понять:\n{user['question']}"
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
        user["offer"] = "basic"
        send_message(
            chat_id,
            "Я бы советовала тебе ✨ Мини-разбор за $11.\n\n"
            "Потому что здесь лучше подходит быстрый и точный ответ на один главный вопрос.",
            payment_keyboard_for_offer("basic")
        )

    elif offer == "deep":
        user["offer"] = "deep"
        send_message(
            chat_id,
            "Я бы советовала тебе 🔮 Глубокий разбор за $29.\n\n"
            "Потому что ситуация выглядит эмоционально сложной и требует более глубокого разбора.",
            payment_keyboard_for_offer("deep")
        )

    else:
        send_message(
            chat_id,
            "Я услышала тебя ✨\n\n"
            "Пока здесь лучше выбрать формат вручную:",
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
                        user["offer"] = "basic"
                        send_message(
                            chat_id,
                            "✨ Мини-разбор — $11\n\n"
                            "Быстрый и точный ответ на один главный вопрос.",
                            payment_keyboard_for_offer("basic")
                        )

                    elif data == "deep_info":
                        user["offer"] = "deep"
                        send_message(
                            chat_id,
                            "🔮 Глубокий разбор — $29\n\n"
                            "Полный разбор ситуации с пониманием причин и дальнейшего движения.",
                            payment_keyboard_for_offer("deep")
                        )

                    elif data == "help_pick":
                        send_message(
                            chat_id,
                            "Напиши одним сообщением, что тебя сейчас больше всего волнует, и я помогу выбрать формат 💬"
                        )

                    elif data == "paid":
                        user["step"] = "waiting_name"
                        send_message(
                            chat_id,
                            "Приняла оплату ✨\n\n"
                            "Давай соберем заявку по шагам.\n\n"
                            "Сначала напиши своё имя."
                        )

        except Exception as e:
            print("RUNTIME ERROR:", str(e))


if __name__ == "__main__":
    main()