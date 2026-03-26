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


def normalize_text(text: str) -> str:
    return text.lower().strip()


def analyze_offer(user_text: str):
    text = normalize_text(user_text)

    relationship_keywords = [
        "отнош", "люб", "парень", "парнем", "девушка", "девушкой",
        "муж", "жена", "бывш", "расстав", "развод", "измена",
        "предательство", "чувства", "влюб", "ревность", "ссора"
    ]

    deep_keywords = [
        "сложно", "тяжело", "больно", "страшно", "кризис",
        "не понимаю", "запутал", "запуталась", "запутался",
        "что делать", "помоги выбрать", "помоги разобраться",
        "будущее", "судьба", "предназначение", "энергия",
        "деньги", "работа", "карьера", "путь", "выбор", "проблем"
    ]

    basic_keywords = [
        "быстро", "кратко", "коротко", "мини",
        "один вопрос", "простой вопрос", "быстрый ответ"
    ]

    deep_score = 0
    basic_score = 0
    reasons = []

    for word in relationship_keywords:
        if word in text:
            deep_score += 2
            if "отношения или чувства" not in reasons:
                reasons.append("я вижу, что вопрос связан с отношениями или чувствами")

    for word in deep_keywords:
        if word in text:
            deep_score += 1
            if word in ["сложно", "тяжело", "больно", "страшно", "кризис", "проблем"]:
                if "ситуация звучит непросто и эмоционально" not in reasons:
                    reasons.append("ситуация звучит непросто и эмоционально")
            elif word in ["не понимаю", "запутал", "запуталась", "запутался", "что делать", "помоги выбрать", "помоги разобраться", "выбор"]:
                if "тебе нужна не просто подсказка, а ясность" not in reasons:
                    reasons.append("тебе нужна не просто подсказка, а ясность")
            else:
                if "здесь есть глубина и несколько слоев" not in reasons:
                    reasons.append("здесь есть глубина и несколько слоев")

    for word in basic_keywords:
        if word in text:
            basic_score += 2
            if "ты хочешь быстрый и точный ответ" not in reasons:
                reasons.append("ты хочешь быстрый и точный ответ")

    if len(text) > 80:
        deep_score += 1
        if "в запросе уже много контекста" not in reasons:
            reasons.append("в запросе уже много контекста")

    if len(text) > 160:
        deep_score += 1
        if "вопрос выглядит многослойным" not in reasons:
            reasons.append("вопрос выглядит многослойным")

    if "?" in text and len(text) < 50:
        basic_score += 1
        if "это похоже на один конкретный вопрос" not in reasons:
            reasons.append("это похоже на один конкретный вопрос")

    if deep_score >= 2 and deep_score > basic_score:
        return {
            "offer": "deep",
            "reasons": reasons[:2]
        }

    if basic_score >= 2 and basic_score >= deep_score:
        return {
            "offer": "basic",
            "reasons": reasons[:2]
        }

    return {
        "offer": "unknown",
        "reasons": reasons[:2]
    }


def build_reason_text(reasons):
    if not reasons:
        return ""

    if len(reasons) == 1:
        return f"Почему я советую это: {reasons[0]}."
    return f"Почему я советую это: {reasons[0]}, и ещё {reasons[1]}."


def handle_user_message(chat_id, text):
    analysis = analyze_offer(text)
    offer = analysis["offer"]
    reason_text = build_reason_text(analysis["reasons"])

    if offer == "deep":
        message = (
            "Я бы советовала тебе 🔮 Глубокий разбор за $29.\n\n"
            f"{reason_text}\n\n"
            "Он подходит, когда важно не просто получить ответ, а увидеть ситуацию шире и глубже."
        )
        send_message(chat_id, message, start_keyboard())

    elif offer == "basic":
        message = (
            "Я бы советовала тебе ✨ Мини-разбор за $11.\n\n"
            f"{reason_text}\n\n"
            "Он подходит, когда нужен быстрый и точный ответ на один главный вопрос."
        )
        send_message(chat_id, message, start_keyboard())

    else:
        send_message(
            chat_id,
            "Я пока не хочу гадать наугад ✨\n\n"
            "Пока здесь вижу два возможных варианта. Выбери, что тебе ближе:",
            start_keyboard()
        )


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
                        "Выбери вариант ниже или сразу опиши свою ситуацию одним сообщением.",
                        start_keyboard()
                    )
                else:
                    handle_user_message(chat_id, text)

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
                        "Подходит, если ситуация сложная, эмоциональная или многослойная и хочется увидеть её глубже."
                    )
                elif data == "help":
                    send_message(
                        chat_id,
                        "Опиши свою ситуацию одним сообщением. Например:\n\n"
                        "«У меня проблемы с парнем, не понимаю, есть ли будущее»\n\n"
                        "И я подскажу не только формат, но и почему советую именно его 💬"
                    )


if __name__ == "__main__":
    main()