import os
import sys
import time
import logging

from datetime import date

import schedule
import telebot


bot_token = os.environ.get("APP_TG_TOKEN")

bot = telebot.TeleBot(bot_token, parse_mode="Markdown")

chat_id = os.environ.get("APP_TG_CHAT_ID")
app_dev_mode = os.environ.get("APP_DEV_MODE")
challenge_tag = os.environ.get("APP_TG_CHALLENGE_TAG")


def send_notify():
    logging.info("Sending notify")

    current_date_humanized = date.today().strftime("%d.%m")

    notify_text = f"⏰ Чтобы внести свои результаты по {challenge_tag} за {current_date_humanized}, отправьте число шагов ответом на это сообщение."  # noqa

    bot.send_message(chat_id, notify_text)

    return None


if __name__ == "__main__":
    logging.critical("Starting")

    if app_dev_mode:
        logging.warning("Running single dev run")

        schedule.every(1).seconds.do(send_notify)
        time.sleep(1)
        schedule.run_pending()
        sys.exit()

    schedule.every().day.at("23:59").do(send_notify)

    while True:
        schedule.run_pending()
        time.sleep(5)
