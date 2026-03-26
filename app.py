import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

URL = f"https://api.telegram.org/bot{TOKEN}/"
client = OpenAI(api_key=OPENAI_API_KEY)

last_update_id = None

# простая память в процессе
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
        USER_STATE[user_id] = {
            "previous_response_id": None,
            "last_offer": None
        }
    return USER_STATE[user_id]


def madame_mira_prompt():
    return """
Ты — Madame Mira, мягкий и умный Telegram-продажник разборов.

Твоя задача:
1. Понять, что беспокоит человека.
2. Порекомендовать один из двух форматов:
   - Мини-разбор за $11
   - Глубокий разбор за $29
3. Коротко объяснить, почему советуешь именно его.
4. Говорить тепло, уверенно, женственно, без кринжа и без лишней воды.
5. Не показывать сразу оба варианта, если можешь уверенно выбрать один.
6. Если данных мало, задай 1 уточняющий вопрос.

Когда советовать $29:
- отношения, муж, парень, бывший, измена, расставание
- эмоционально тяжелая или многослойная ситуация
- много контекста
- человек запутан и хочет понять глубже

Когда советовать $11:
- один короткий вопрос
- запрос на быстрый, краткий ответ
- низкий порог входа
- человек хочет попробовать формат

Правила:
- Никогда не меняй цены.
- Не придумывай другие тарифы.
- Не давай медицинских, юридических или финансовых гарантий.
- Отвечай коротко.
- Не пиши длинные простыни.
- Не повторяй одно и то же в каждом сообщении.

Верни только JSON в таком формате:
{
  "type": "recommendation" | "clarify",
  "offer": "basic" | "deep" | "unknown",
  "message": "текст ответа пользователю"
}
""".strip()


def ask_gpt(user_id: int, user_text: str):
    state = get_user_state(user_id)

    kwargs = {
        "model": "gpt-5.4",
        "instructions": madame_mira_prompt(),
        "input": user_text
    }

    if state["previous_response_id"]:
        kwargs["previous_response_id"] = state["previous_response_id"]

    response = client.responses.create(**kwargs)
    state["previous_response_id"] = response.id

    text = getattr(response, "output_text", "").strip()

    try:
        data = json.loads(text)
        return data
    except Exception:
        return {
            "type": "clarify",
            "offer": "unknown",
            "message": "Я чувствую, что здесь есть важный слой ✨ Расскажи чуть подробнее, что именно болит в этой ситуации?"
        }


def handle_user_message(chat_id, user_id, text):
    result = ask_gpt(user_id, text)

    message = result.get("message", "Расскажи чуть подробнее.")
    offer = result.get("offer", "unknown")
    result_type = result.get("type", "clarify")

    state = get_user_state(user_id)
    state["last_offer"] = offer

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
                        "Опиши свою ситуацию одним сообщением, и я подскажу, какой формат разбора тебе подойдет лучше.",
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
                        "✨ Мини-разбор — $11\n\n"
                        "Подходит, если тебе нужен быстрый и точный ответ на один главный вопрос."
                    )
                elif data == "deep":
                    send_message(
                        chat_id,
                        "🔮 Глубокий разбор — $29\n\n"
                        "Подходит, если ситуация сложная, эмоциональная или многослойная и хочется увидеть её глубже."
                    )
                elif data == "help":
                    send_message(
                        chat_id,
                        "Напиши одним сообщением, что тебя сейчас больше всего волнует. Я не просто покажу вариант, а объясню, почему советую именно его 💬"
                    )


if __name__ == "__main__":
    main()