import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

URL = f"https://api.telegram.org/bot{TOKEN}/"
client = OpenAI(api_key=OPENAI_API_KEY)

last_update_id = None
WAITING_FOR_DESCRIPTION = {}


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


def prompt_text():
    return """
Ты — Madame Mira, уверенный Telegram-продажник разборов.

У тебя есть только 2 варианта:
- Мини-разбор — $11
- Глубокий разбор — $29

Твоя задача:
1. Прочитать сообщение пользователя.
2. Сразу выбрать ОДИН формат.
3. Коротко объяснить, почему.
4. Отвечать тепло, уверенно и по делу.

Правила выбора:
- Выбирай $29, если тема про отношения, мужа, парня, бывшего, измену, боль, предательство, сильные эмоции, путаницу, сложную ситуацию.
- Выбирай $11, если вопрос короткий, простой, быстрый, один конкретный.
- Не задавай уточняющих вопросов.
- Не предлагай оба варианта.
- Не меняй цены.
- Не пиши длинно.

Верни строго JSON:

{
  "offer": "basic" or "deep",
  "message": "готовый текст для пользователя"
}

Пример для сложной ситуации:
{
  "offer": "deep",
  "message": "Я бы советовала тебе 🔮 Глубокий разбор за $29. Потому что ситуация выглядит эмоционально сложной и требует более глубокого разбора."
}

Пример для простого вопроса:
{
  "offer": "basic",
  "message": "Я бы советовала тебе ✨ Мини-разбор за $11. Потому что здесь лучше подходит быстрый и точный ответ на один главный вопрос."
}
""".strip()


def ask_gpt(user_text: str):
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
            "offer": "deep",
            "message": "Я бы советовала тебе 🔮 Глубокий разбор за $29. Потому что ситуация выглядит эмоционально сложной и требует более глубокого разбора."
        }


def handle_user_message(chat_id, text):
    result = ask_gpt(text)
    message = result.get("message", "Я бы советовала тебе 🔮 Глубокий разбор за $29.")
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
                text = update["message"].get("text", "").strip()

                if not text:
                    continue

                if text == "/start":
                    WAITING_FOR_DESCRIPTION[user_id] = False
                    send_message(
                        chat_id,
                        "Привет, я Madame Mira ✨\n\nОпиши свою ситуацию одним сообщением, и я сразу скажу, какой формат тебе подойдет лучше.",
                        start_keyboard()
                    )
                else:
                    handle_user_message(chat_id, text)
                    WAITING_FOR_DESCRIPTION[user_id] = False

            elif "callback_query" in update:
                query = update["callback_query"]
                data = query["data"]
                chat_id = query["message"]["chat"]["id"]
                user_id = query["from"]["id"]

                answer_callback_query(query["id"])

                if data == "basic":
                    WAITING_FOR_DESCRIPTION[user_id] = False
                    send_message(
                        chat_id,
                        "✨ Мини-разбор — $11\n\nБыстрый и точный ответ на один главный вопрос."
                    )

                elif data == "deep":
                    WAITING_FOR_DESCRIPTION[user_id] = False
                    send_message(
                        chat_id,
                        "🔮 Глубокий разбор — $29\n\nПолный разбор ситуации с пониманием причин и дальнейшего движения."
                    )

                elif data == "help":
                    WAITING_FOR_DESCRIPTION[user_id] = True
                    send_message(
                        chat_id,
                        "Опиши ситуацию одним сообщением, и я скажу, какой формат подойдет лучше 💬"
                    )


if __name__ == "__main__":
    main()