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


def choose_offer(user_text: str):
    text = user_text.lower().strip()

    deep_keywords = [
        "отнош", "люб", "бывш", "муж", "жена", "развод", "предательство",
        "измена", "чувства", "страх", "кризис", "сложно", "тяжело",
        "не понимаю", "запуталась", "запутался", "выбор", "будущее",
        "предназначение", "деньги", "работа", "путь", "энергия"
    ]

    basic_keywords = [
        "быстро", "кратко", "один вопрос", "простой вопрос", "коротко", "мини"
    ]

    deep_score = 0
    basic_score = 0

    for word in deep_keywords:
        if word in text:
            deep_score += 1

    for word in basic_keywords:
        if word in text:
            basic_score += 1

    if len(text) > 120:
        deep_score += 1

    if deep_score >= 2:
        return "deep"
    if basic_score >= 1:
        return "basic"
    return "unknown"


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
                    offer = choose_offer(text)

                    if offer == "deep":
                        send_message(
                            chat_id,
                            "Я чувствую, что здесь вопрос не поверхностный ✨\n\n"
                            "Тебе больше подойдет 🔮 Глубокий разбор за $29.\n\n"
                            "Он нужен, когда важно увидеть ситуацию шире и глубже.",
                            start_keyboard()
                        )
                    elif offer == "basic":
                        send_message(
                            chat_id,
                            "Здесь лучше подойдет ✨ Мини-разбор за $11.\n\n"
                            "Он хорош, когда нужен быстрый и точный ответ на один главный вопрос.",
                            start_keyboard()
                        )
                    else:
                        send_message(
                            chat_id,
                            "Я услышала тебя ✨\n\n"
                            "Могу предложить оба варианта, а ты почувствуешь, что тебе ближе:",
                            start_keyboard()
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
                        "Подходит, если ситуация сложная и хочется глубины, ясности и большего объема."
                    )
                elif data == "help":
                    send_message(
                        chat_id,
                        "Напиши одним сообщением, что тебя сейчас больше всего волнует, и я подскажу, какой формат подойдет лучше 💬"
                    )


if __name__ == "__main__":
    main()