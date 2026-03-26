import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

URL = f"https://api.telegram.org/bot{TOKEN}/"
CRYPTO_API_URL = "https://pay.crypt.bot/api"

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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
            "invoice_url": None,
            "initial_text": "",
            "second_reply": ""
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
        "invoice_url": None,
        "initial_text": "",
        "second_reply": ""
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


def choose_offer_local(text: str):
    t = text.lower().strip()

    deep_keywords = [
        "отнош", "парень", "муж", "бывш", "измен", "предал", "предательство",
        "ушел", "ушёл", "другая", "другой", "любов", "чувства", "больно",
        "сложно", "тяжело", "кризис", "развод", "расстав", "ревность",
        "запутал", "запуталась", "запутался", "не понимаю", "что делать",
        "будущее", "судьба", "энергия", "выбор", "подруга", "треугольник",
        "предательство", "бросил", "одиночество"
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

    return "deep"


def gpt_first_reply(user_text: str):
    if not client:
        return {
            "message": "Я чувствую, что за этими словами стоит не просто вопрос, а живая боль ✨\n\nСкажи, что сейчас ранит сильнее всего: сама потеря человека или то, что ты не понимаешь, что между вами осталось?"
        }

    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мягкий, мистический, но естественный.
Нужно ответить пользователю ПЕРВЫМ сообщением.

Правила:
1. Сначала мягко отрази его состояние.
2. Потом задай ОДИН тёплый уточняющий вопрос.
3. НЕ предлагай услуги.
4. НЕ упоминай деньги.
5. НЕ показывай варианты.
6. Коротко, красиво, по-человечески.
7. Отвечай на русском.

Верни строго JSON:
{{
  "message": "текст"
}}

Сообщение пользователя:
{user_text}
""".strip()

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )
        data = json.loads((response.output_text or "").strip())
        if data.get("message"):
            return data
    except Exception as e:
        print("GPT FIRST ERROR:", str(e))

    return {
        "message": "Я чувствую, что за этим сообщением стоит не только вопрос, но и усталость сердца ✨\n\nСкажи, тебе сейчас важнее понять чувства другого человека или разобраться, что делать дальше?"
    }


def gpt_second_reply(initial_text: str, first_answer: str):
    if not client:
        return {
            "message": "Я тебя чувствую ✨\n\nЗдесь уже видно не просто переживание, а узел, который тянется глубже.\n\nСкажи, тебе важнее понять, есть ли будущее у этой истории, или как перестать в ней терять себя?"
        }

    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мистический, мягкий, но живой.

Нужно написать ВТОРОЕ сообщение в диалоге.
У тебя уже есть:
1. первое сообщение клиента
2. ответ клиента на твой первый вопрос

Задача:
1. Мягко углубить разговор
2. Показать, что ты почувствовала суть
3. Задать ЕЩЁ ОДИН короткий вопрос
4. НЕ продавать
5. НЕ упоминать оплату
6. НЕ предлагать формат
7. Отвечать коротко и красиво
8. На русском

Верни строго JSON:
{{
  "message": "текст"
}}

Первое сообщение клиента:
{initial_text}

Ответ клиента:
{first_answer}
""".strip()

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )
        data = json.loads((response.output_text or "").strip())
        if data.get("message"):
            return data
    except Exception as e:
        print("GPT SECOND ERROR:", str(e))

    return {
        "message": "Я тебя чувствую ✨\n\nВ этом правда много непрожитого и неясного.\n\nСкажи, тебе сейчас важнее увидеть, есть ли перспектива у этой связи, или понять, как выбрать себя?"
    }


def gpt_recommend(initial_text: str, first_answer: str, second_answer: str):
    combined = (
        f"Первое сообщение клиента: {initial_text}\n"
        f"Ответ на первый вопрос: {first_answer}\n"
        f"Ответ на второй вопрос: {second_answer}"
    )

    if not client:
        offer = choose_offer_local(f"{initial_text} {first_answer} {second_answer}")
        if offer == "basic":
            return {
                "offer": "basic",
                "message": "Я бы сейчас мягко повела тебя в ✨ Мини-разбор за $11.\n\nЗдесь нужен один ясный и точный ответ, без лишнего круга."
            }
        return {
            "offer": "deep",
            "message": "Я бы сейчас повела тебя в 🔮 Глубокий разбор за $29.\n\nПотому что здесь чувствуется не один вопрос, а целая внутренняя история, которую лучше раскрывать глубже."
        }

    prompt = f"""
Ты — Madame Mira.
Стиль: женственный, мягкий, мистический, премиальный.

Сейчас нужно сделать ПЕРВУЮ продажу после короткого диалога.

У тебя есть только 2 формата:
- basic = Мини-разбор $11
- deep = Глубокий разбор $29

Правила:
1. Выбери ТОЛЬКО ОДИН формат.
2. Объясни, почему он подходит.
3. Сделай это мягко, красиво, без давления.
4. НЕ перечисляй оба варианта.
5. НЕ задавай больше вопросов.
6. Отвечай коротко и на русском.
7. Если тема про отношения, боль, путаницу, измену, сильные чувства, выбирай deep.
8. Если вопрос один, короткий, конкретный, выбирай basic.

Верни строго JSON:
{{
  "offer": "basic" или "deep",
  "message": "текст"
}}

Диалог:
{combined}
""".strip()

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )
        data = json.loads((response.output_text or "").strip())

        offer = data.get("offer", "deep")
        message = data.get("message", "").strip()

        if offer not in ["basic", "deep"]:
            offer = "deep"

        if not message:
            if offer == "basic":
                message = "Я бы сейчас мягко повела тебя в ✨ Мини-разбор за $11.\n\nЗдесь нужен один ясный и точный ответ, без лишнего круга."
            else:
                message = "Я бы сейчас повела тебя в 🔮 Глубокий разбор за $29.\n\nПотому что здесь чувствуется не один вопрос, а целая внутренняя история, которую лучше раскрывать глубже."

        return {"offer": offer, "message": message}
    except Exception as e:
        print("GPT RECOMMEND ERROR:", str(e))

    offer = choose_offer_local(f"{initial_text} {first_answer} {second_answer}")
    if offer == "basic":
        return {
            "offer": "basic",
            "message": "Я бы сейчас мягко повела тебя в ✨ Мини-разбор за $11.\n\nЗдесь нужен один ясный и точный ответ, без лишнего круга."
        }

    return {
        "offer": "deep",
        "message": "Я бы сейчас повела тебя в 🔮 Глубокий разбор за $29.\n\nПотому что здесь чувствуется не один вопрос, а целая внутренняя история, которую лучше раскрывать глубже."
    }


def create_crypto_invoice(user_id, offer):
    if not CRYPTO_PAY_TOKEN:
        print("CRYPTO_PAY_TOKEN not set")
        return None

    amount = "11" if offer == "basic" else "29"
    description = "Mini" if offer == "basic" else "Deep"
    payload_value = f"user_{user_id}_{offer}"

    try:
        response = requests.post(
            f"{CRYPTO_API_URL}/createInvoice",
            headers={
                "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
                "Content-Type": "application/json"
            },
            json={
                "asset": "USDT",
                "amount": amount,
                "description": description,
                "payload": payload_value
            },
            timeout=30
        )

        print("CRYPTO CREATE:", response.text)
        data = response.json()

        if not data.get("ok"):
            print("CRYPTO CREATE ERROR:", data)
            return None

        result = data["result"]
        return {
            "invoice_id": result["invoice_id"],
            "invoice_url": result["bot_invoice_url"]
        }
    except Exception as e:
        print("CRYPTO CREATE EXCEPTION:", str(e))
        return None


def get_invoice_status(invoice_id):
    if not CRYPTO_PAY_TOKEN or not invoice_id:
        return None

    try:
        response = requests.get(
            f"{CRYPTO_API_URL}/getInvoices",
            headers={"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN},
            params={"invoice_ids": str(invoice_id)},
            timeout=30
        )

        print("CRYPTO STATUS:", response.text)
        data = response.json()

        if not data.get("ok"):
            print("CRYPTO STATUS ERROR:", data)
            return None

        items = data["result"]["items"]
        if not items:
            return None

        return items[0].get("status")
    except Exception as e:
        print("CRYPTO STATUS EXCEPTION:", str(e))
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
            "Не получилось создать счёт 😔\n\nПопробуй ещё раз через минуту."
        )
        return

    user["invoice_id"] = invoice["invoice_id"]
    user["invoice_url"] = invoice["invoice_url"]

    send_message(chat_id, intro_text, payment_keyboard(invoice["invoice_url"]))


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
        send_message(
            chat_id,
            "Приняла 💫\n\nТеперь коротко опиши свою ситуацию."
        )
        return

    if user["step"] == "waiting_situation":
        user["situation"] = text
        user["step"] = "waiting_question"
        send_message(
            chat_id,
            "Хорошо.\n\nТеперь напиши, что именно ты хочешь понять или узнать в этом разборе."
        )
        return

    if user["step"] == "waiting_question":
        user["question"] = text
        finish_application(chat_id, user_id)
        return

    if user["step"] == "waiting_clarify_1":
        user["second_reply"] = text
        second = gpt_second_reply(user["initial_text"], text)
        user["step"] = "waiting_clarify_2"
        send_message(chat_id, second["message"])
        return

    if user["step"] == "waiting_clarify_2":
        result = gpt_recommend(
            user["initial_text"],
            user["second_reply"],
            text
        )
        offer = result["offer"]
        message = result["message"]

        user["step"] = "offer_ready"
        send_offer_with_invoice(chat_id, user_id, offer, message)
        return

    # первый вход
    user["initial_text"] = text
    first = gpt_first_reply(text)
    user["step"] = "waiting_clarify_1"
    send_message(chat_id, first["message"])


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
                            "Расскажи, что сейчас тревожит тебя сильнее всего. Я мягко проведу тебя и помогу почувствовать, какой формат подойдёт лучше.",
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
                        send_offer_with_invoice(
                            chat_id,
                            user_id,
                            "basic",
                            "✨ Мини-разбор — $11\n\n"
                            "Он подойдёт, если тебе нужен быстрый и точный ответ на один главный вопрос."
                        )

                    elif data == "deep_info":
                        user["offer"] = "deep"
                        send_offer_with_invoice(
                            chat_id,
                            user_id,
                            "deep",
                            "🔮 Глубокий разбор — $29\n\n"
                            "Он подойдёт, если в ситуации много чувств, подтекста и важно увидеть картину глубже."
                        )

                    elif data == "help_pick":
                        user["step"] = None
                        user["initial_text"] = ""
                        user["second_reply"] = ""
                        send_message(
                            chat_id,
                            "Напиши одним сообщением, что тебя сейчас больше всего волнует, и я мягко подведу тебя к нужному формату 💬"
                        )

                    elif data == "check_payment":
                        status = get_invoice_status(user.get("invoice_id"))

                        if status == "paid":
                            user["step"] = "waiting_name"
                            send_message(
                                chat_id,
                                "Оплату вижу ✅\n\n"
                                "Теперь давай спокойно соберём заявку.\n\n"
                                "Сначала напиши своё имя."
                            )
                        elif status in ["active", "pending"]:
                            send_message(
                                chat_id,
                                "Я ещё не вижу подтверждённую оплату ✨\n\n"
                                "Если ты уже оплатил(а), подожди 10–20 секунд и нажми «Проверить оплату» ещё раз."
                            )
                        else:
                            send_message(
                                chat_id,
                                "Пока не получилось подтвердить оплату.\n\n"
                                "Попробуй открыть счёт ещё раз или вернись чуть позже."
                            )

        except Exception as e:
            print("RUNTIME ERROR:", str(e))


if __name__ == "__main__":
    main()