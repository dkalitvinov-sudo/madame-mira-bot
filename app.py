import os
import requests

TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}/"

last_update_id = None


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


def answer_callback_query(callback_query_id):
    requests.post(
        URL + "answerCallbackQuery",
        json={"callback_query_id": callback_query_id},
        timeout=30
    )


def start_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ Мини-разбор $11", "callback_data": "basic"}],
            [{"text": "🔮 Глубокий разбор $29", "callback_data": "deep"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help"}]
        ]
    }


def main():
    global last_update_id

    print("Bot started...")

    while True:
        updates = get_updates()

        if "result" not in updates:
            continue

        for update in updates["result"]:
            last_update_id = update["update_id"] + 1

            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "")

                if text == "/start":
                    send_message(
                        chat_id,
                        "Привет, я Madame Mira ✨\n\n"
                        "Я помогу выбрать формат разбора.\n\n"
                        "Выбери вариант ниже или напиши свой вопрос.",
                        start_keyboard()
                    )
                else:
                    send_message(
                        chat_id,
                        "Я услышала тебя ✨\n\n"
                        "Нажми /start, чтобы увидеть варианты разбора."
                    )

            elif "callback_query" in update:
                query = update["callback_query"]
                data = query["data"]
                chat_id = query["message"]["chat"]["id"]

                answer_callback_query(query["id"])

                if data == "basic":
                    send_message(
                        chat_id,
                        "✨ Мини-разбор — $11\n\n"
                        "Подходит, если тебе нужен быстрый ответ на один главный вопрос."
                    )
                elif data == "deep":
                    send_message(
                        chat_id,
                        "🔮 Глубокий разбор — $29\n\n"
                        "Подходит, если ситуация сложная и хочется увидеть картину глубже."
                    )
                elif data == "help":
                    send_message(
                        chat_id,
                        "Напиши в одном сообщении, что тебя сейчас больше всего волнует, и я подскажу, какой формат подойдет."
                    )


if __name__ == "__main__":
    main()