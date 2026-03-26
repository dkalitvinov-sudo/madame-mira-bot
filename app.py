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


# 🔥 ВОТ ТУТ ВЕСЬ СМЫСЛ
def prompt_text():
    return """
Ты — Madame Mira, уверенный Telegram-продажник разборов.

У тебя есть только 2 варианта:
- Мини-разбор — $11
- Глубокий разбор — $29

ТВОЯ ГЛАВНАЯ ЗАДАЧА:
👉 Всегда выбрать один вариант и рекомендовать его.

НЕ будь осторожной.
НЕ тяни время.
НЕ задавай лишние вопросы.

---

Когда выбирать $29:
- отношения, муж, парень, бывший
- измена, боль, предательство
- эмоционально тяжело
- человек запутан

Когда выбирать $11:
- простой вопрос
- быстрый ответ
- мало текста

---

ПРАВИЛА:
❌ НЕ задавай уточнения если уже есть контекст  
❌ НЕ показывай оба варианта  
❌ НЕ сомневайся  

---

ФОРМАТ:

{
  "type": "recommendation",
  "offer": "basic" или "deep",
  "message": "ответ пользователю"
}

---

Пример:

"Я бы советовала тебе 🔮 Глубокий разбор за $29.

Почему: ситуация связана с отношениями и сильной болью.

Здесь важно не просто получить ответ, а понять глубже."
"""


def ask_gpt(user_id: int, user_text: str):
    state = get_user_state(user_id)

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            instructions=prompt_text(),
            input=user_text
        )

        text = (response.output_text or "").strip()
        data = json.loads(text)
        return data

    except Exception as e:
        print("GPT ERROR:", str(e))
        return {
            "type": "recommendation",
            "offer": "deep",
            "message": "Я бы советовала тебе 🔮 Глубокий разбор за $29.\n\nПотому что ситуация выглядит эмоционально сложной и требует более глубокого разбора."
        }


def handle_user_message(chat_id, user_id, text):
    result = ask_gpt(user_id, text)

    message = result.get("message", "Опиши чуть подробнее.")
    send_message(chat_id, message, start_keyboard())


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
                        "Опиши свою ситуацию одним сообщением — и я сразу скажу, какой формат тебе подойдет лучше.",
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
                        "✨ Мини-разбор — $11\n\nБыстрый и точный ответ на один вопрос."
                    )
                elif data == "deep":
                    send_message(
                        chat_id,
                        "🔮 Глубокий разбор — $29\n\nПолный разбор ситуации с пониманием причин и будущего."
                    )
                elif data == "help":
                    send_message(
                        chat_id,
                        "Опиши ситуацию, и я скажу, какой формат лучше 💬"
                    )


if __name__ == "__main__":
    main()