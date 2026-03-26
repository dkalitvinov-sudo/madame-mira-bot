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


def send_message(chat_id, text):
    requests.post(
        URL + "sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


def main():
    global last_update_id

    print("Bot started...")

    while True:
        updates = get_updates()

        if "result" in updates:
            for update in updates["result"]:
                last_update_id = update["update_id"] + 1

                if "message" in update:
                    chat_id = update["message"]["chat"]["id"]
                    text = update["message"].get("text", "")

                    if text == "/start":
                        send_message(
                            chat_id,
                            "Привет, я Madame Mira ✨\n\n"
                            "Я помогаю выбрать формат разбора и провести тебя по шагам.\n\n"
                            "Напиши, что тебя сейчас волнует."
                        )
                    else:
                        send_message(
                            chat_id,
                            "Я услышала тебя ✨\n\n"
                            "Скоро я стану умнее. А пока напиши /start"
                        )


if __name__ == "__main__":
    main()