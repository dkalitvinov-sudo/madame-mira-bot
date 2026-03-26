import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

URL = f"https://api.telegram.org/bot{TOKEN}/"
client = OpenAI(api_key=OPENAI_API_KEY)

last_update_id = None
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


def get_user_state(user_id: int):
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {"previous_response_id": None}
    return USER_STATE[user_id]


def prompt_text():
    return """
Ты — Madame Mira, Telegram-консультант по продаже разборов.

У тебя есть только 2 формата:
- Мини-разбор — $11
- Глубокий разбор — $29

Твоя задача:
1. Прочитать сообщение пользователя.
2. Выбрать один формат, если уверена.
3. Коротко объяснить, почему.
4. Если уверенности мало, задать 1 уточняющий вопрос.

Когда чаще советовать $29:
- отношения, муж, парень, бывший, измена, расставание
- эмоционально тяжело
- много слоев и контекста
- пользователь запутан и хочет понять глубже

Когда чаще советовать $11:
- один короткий вопрос
- быстрый ответ
- краткий формат
- пользователь хочет попробовать

Пиши тепло, коротко, без воды.
Никогда не меняй цены.
Верни строго JSON такого вида:

{
  "type": "recommendation" or "clarify",
  "offer": "basic" or "deep" or "unknown",
  "message": "текст для пользователя"
}
""".strip()


def ask_gpt(user_id: int, user_text: str):
    state = get_user_state(user_id)

    try:
        kwargs = {
            "model": "gpt-4.1-mini",
            "instructions": prompt_text(),
            "input": user_text,
        }

        if state["previous_response_id"]:
            kwargs["previous_response_id"] = state["previous_response_id"]

        response = client.responses.create(**kwargs)
        state["previous_response_id"] = response.id

        text = (response.output_text or "").strip()

        data = json.loads(text)
        return data

    except Exception as e:
        print("GPT ERROR:", str(e))
        return {
            "type": "clarify",
            "offer": "unknown",
            "message": "Я чувствую, что тут есть важный слой ✨ Опиши чуть подробнее, что именно тебя сейчас тревожит?"
        }


def handle_user_message(chat_id, user_id, text):
    result = ask_gpt(user_id, text)

    message = result.get("message", "Опиши чуть подробнее.")
    result_type = result.get("type", "clarify")

    if result_type == "recommendation":
        send_message(chat_id, message, start_keyboard())
    else:
        send_message(chat_id, message)


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
                user_id = update["message"]["from"]["id"]
                text = update["message"].get("text", "")

                if text == "/start":
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

                answer_callback_query(query["id"])

                if data == "basic":
                    send_message(
                        chat_id,
                        "✨ Мини-разбор — $11\n\nПодходит, если тебе нужен быстрый и точный ответ на один главный вопрос."
                    )
                elif data == "deep":
                    send_message(
                        chat_id,
                        "🔮 Глубокий разбор — $29\n\nПодходит, если ситуация сложная, эмоциональная или многослойная."
                    )
                elif data == "help":
                    send_message(
                        chat_id,
                        "Напиши, что тебя сейчас больше всего волнует, и я подскажу, какой формат подойдет лучше 💬"
                    )


if __name__ == "__main__":
    main()