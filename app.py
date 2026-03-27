import os
import json
import requests
from openai import OpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CARD_NUMBER = os.getenv("CARD_NUMBER", "1111 2222 3333 4444")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"
CRYPTO_API_URL = "https://pay.crypt.bot/api"

client = OpenAI(api_key=OPENAI_API_KEY)

last_update_id = None
USER_STATE = {}

BASIC_USD = "10"
DEEP_USD = "20"

BASIC_UAH = "440"
DEEP_UAH = "880"


def get_user(user_id):
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {
            "step": None,
            "offer": None,
            "name": "",
            "situation": "",
            "question": "",
            "initial_text": "",
            "reply_1": "",
            "invoice_id": None,
            "invoice_url": None,
            "payment_method": None,
            "status": "new",
            "followups_left": 0
        }
    return USER_STATE[user_id]


def send(chat_id, text, markup=None):
    data = {"chat_id": chat_id, "text": text}
    if markup:
        data["reply_markup"] = markup
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=data)


def gpt(text):
    try:
        r = client.responses.create(
            model="gpt-4.1-mini",
            input=text
        )
        return r.output_text.strip()
    except:
        return "Я чувствую, что здесь есть важный внутренний момент ✨"


# -------- GPT БЛОКИ --------

def first_reply(user_text):
    return gpt(f"""
Ты — Madame Mira. Ответь мягко, тепло.

Сообщение:
{user_text}

Сделай:
- эмпатия
- 1 вопрос
- без продажи
""")


def recommend(user_text, reply):
    return gpt(f"""
Ты — Madame Mira.

Нужно мягко предложить формат.

Если не супер сложная ситуация → предложи мини.

Сообщения:
{user_text}
{reply}

Ответ:
""")


def reading(user):
    return gpt(f"""
Ты — Madame Mira.

Сделай разбор.

Имя: {user['name']}
Ситуация: {user['situation']}
Вопрос: {user['question']}

Стиль:
- глубокий
- мягкий
- эмоциональный
""")


# -------- ОСНОВА --------

def handle_text(chat_id, user_id, text):
    user = get_user(user_id)

    # FOLLOW-UP
    if user["step"] == "followup":
        if user["followups_left"] <= 0:
            send(chat_id, "Мы уже завершили этот разбор ✨")
            return

        answer = gpt(f"""
Ты продолжаешь разбор.

Вопрос клиента:
{text}
""")

        send(chat_id, answer)

        user["followups_left"] -= 1

        if user["followups_left"] == 0:
            send(chat_id, "На этом завершаем ✨")

        return

    # анкета
    if user["step"] == "name":
        user["name"] = text
        user["step"] = "situation"
        send(chat_id, "Опиши ситуацию ✨")
        return

    if user["step"] == "situation":
        user["situation"] = text
        user["step"] = "question"
        send(chat_id, "Что хочешь понять?")
        return

    if user["step"] == "question":
        user["question"] = text
        user["status"] = "submitted"

        send(chat_id, "Заявка принята ✨")

        # отправка в админку
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": ADMIN_CHAT_ID,
            "text": f"Заявка\nID:{user_id}\n{user['situation']}",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "🪄 Сделать разбор", "callback_data": f"read_{user_id}"}
                ]]
            }
        })

        return

    # диалог
    if user["step"] == "wait_reply":
        user["reply_1"] = text

        msg = recommend(user["initial_text"], text)

        user["offer"] = "basic"
        user["step"] = "pay"

        send(chat_id, msg)
        send(chat_id, "Оплатить:", {
            "inline_keyboard": [
                [{"text": "💸 Крипта", "callback_data": "pay_crypto"}],
                [{"text": "💳 Карта", "callback_data": "pay_card"}]
            ]
        })
        return

    # старт
    user["initial_text"] = text
    user["step"] = "wait_reply"

    send(chat_id, first_reply(text))


# -------- CALLBACK --------

def handle_callback(q):
    data = q["data"]
    user_id = q["from"]["id"]
    chat_id = q["message"]["chat"]["id"]

    user = get_user(user_id)

    if data == "pay_crypto":
        user["payment_method"] = "crypto"
        user["step"] = "name"
        send(chat_id, "Оплата принята ✨\n\nНапиши имя")
        return

    if data == "pay_card":
        user["payment_method"] = "card"
        user["step"] = "waiting_receipt"
        send(chat_id, f"Переведи {BASIC_UAH} грн\nКарта:\n{CARD_NUMBER}")
        return

    if data.startswith("read_"):
        uid = int(data.split("_")[1])
        u = get_user(uid)

        send(uid, "Сейчас сделаю разбор ✨")

        text = reading(u)
        send(uid, text)

        # FOLLOW-UP включаем
        if u["offer"] == "basic":
            u["followups_left"] = 1
        else:
            u["followups_left"] = 2

        u["step"] = "followup"
        u["status"] = "reading_sent"

        send(uid, "Можешь задать уточняющий вопрос ✨")
        return


# -------- LOOP --------

def run():
    global last_update_id

    while True:
        r = requests.get(f"{TELEGRAM_API_URL}/getUpdates", params={
            "offset": last_update_id,
            "timeout": 100
        }).json()

        for u in r["result"]:
            last_update_id = u["update_id"] + 1

            if "message" in u:
                m = u["message"]
                if m["chat"]["id"] == ADMIN_CHAT_ID:
                    continue

                text = m.get("text")
                if text:
                    if text == "/start":
                        send(m["chat"]["id"], "Привет ✨ Напиши свою ситуацию")
                    else:
                        handle_text(m["chat"]["id"], m["from"]["id"], text)

            if "callback_query" in u:
                handle_callback(u["callback_query"])


if __name__ == "__main__":
    run()