import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

URL = f"https://api.telegram.org/bot{TOKEN}/"
client = OpenAI(api_key=OPENAI_API_KEY)

last_update_id = None

CRYPTO_11 = "https://t.me/send?start=IVhQvvzpJ7nd"
CRYPTO_29 = "https://t.me/send?start=IVlbsVdZNwQK"


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
            [{"text": "✨ Мини-разбор $11", "callback_data": "basic_info"}],
            [{"text": "🔮 Глубокий разбор $29", "callback_data": "deep_info"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def payment_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💰 Оплатить $11 криптой", "url": CRYPTO_11}],
            [{"text": "🔮 Оплатить $29 криптой", "url": CRYPTO_29}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def payment_keyboard_for_offer(offer: str):
    if offer == "basic":
        return {
            "inline_keyboard": [
                [{"text": "💰 Оплатить $11 криптой", "url": CRYPTO_11}],
                [{"text": "🔮 Выбрать глубокий $29", "callback_data": "deep_info"}],
                [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
            ]
        }
    return {
        "inline_keyboard": [
            [{"text": "🔮 Оплатить $29 криптой", "url": CRYPTO_29}],
            [{"text": "✨ Выбрать мини $11", "callback_data": "basic_info"}],
            [{"text": "💬 Помоги выбрать", "callback_data": "help_pick"}]
        ]
    }


def prompt_text():
    return """
Ты — Madame Mira, уверенный Telegram-продажник разборов.

У тебя есть только 2 варианта:
- Мини-разбор — $11
- Глубокий разбор — $29

Задача:
1. Прочитать сообщение пользователя.
2. Выбрать ОДИН формат.
3. Очень коротко объяснить, почему.
4. Говорить тепло, по делу, без воды.
5. Не задавать уточняющих вопросов.
6. Не предлагать оба варианта.

Как выбирать:
- Выбирай "deep", если тема про отношения, мужа, парня, бывшего, измену, предательство, сильные эмоции, боль, запутанность, сложную ситуацию.
- Выбирай "basic", если вопрос короткий, простой, быстрый, один конкретный, без глубокого контекста.

Правила:
- Нельзя менять цены.
- Нельзя придумывать другие продукты.
- Нельзя задавать уточнения.
- Нельзя отвечать длинно.
- Всегда выбери один вариант.

Верни строго JSON такого вида:
{
  "offer": "basic" or "deep",
  "message": "готовый текст для пользователя"
}

Пример для deep:
{
  "offer": "deep",
  "message": "Я бы советовала тебе 🔮 Глубокий разбор за $29. Потому что ситуация выглядит эмоционально сложной и здесь важно увидеть картину глубже."
}

Пример для basic:
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

        offer = data.get("offer", "deep")
        if offer not in ["basic", "deep"]:
            offer = "deep"

        message = data.get("message", "").strip()
        if not message:
            if offer == "basic":
                message = "Я бы советовала тебе ✨ Мини-разбор за $11. Потому что здесь лучше подходит быстрый и точный ответ."
            else:
                message = "Я бы советовала тебе 🔮 Глубокий разбор за $29. Потому что ситуация выглядит эмоционально сложной и требует более глубокого разбора."

        return {
            "offer": offer,
            "message": message
        }

    except Exception as e