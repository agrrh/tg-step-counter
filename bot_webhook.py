import os
import logging

import telebot
import gspread

from tg_step_counter.i18n import Internationalization as I18n

from tg_step_counter.message_parser import MessageParser

from tg_step_counter.objects.result import Result, ResultPlot
from tg_step_counter.objects.tg_user import TGUser, TGUserSpreadsheetHandler

bot_token = os.environ.get("APP_TG_TOKEN")

chat_id = os.environ.get("APP_TG_CHAT_ID")

google_service_account_fname = os.environ.get("APP_GOOGLE_SA_PATH", "./config/google-service-account.json")
google_sheet_uri = os.environ.get("APP_GOOGLE_SHEET_URI")

bot_username = os.environ.get("APP_TG_USERNAME", "step_counter_dev_bot")

bot = telebot.TeleBot(bot_token, parse_mode="Markdown")

app_language = os.environ.get("APP_LANG", "en")

i18n = I18n(lang=app_language)


def filter_results_reply(message):
    if message.reply_to_message is None:
        return False

    if message.reply_to_message.json.get("text") is None:
        return False

    proper_user = message.reply_to_message.json.get("from", {}).get("username") == bot_username
    proper_message = i18n.lang_map.reminder_mark in message.reply_to_message.json.get("text")

    return proper_user and proper_message


def get_spreadsheet():
    gc = gspread.service_account(filename=google_service_account_fname)
    sheet = gc.open_by_url(google_sheet_uri).sheet1

    return sheet


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")


@bot.message_handler(commands=["me"])
def process_stats_request(message):
    logging.warning("Processing stats request")

    result_dummy = Result(date_notation=None)

    tg_user = TGUser(id=message.from_user.id, username=message.from_user.username)
    tg_user_handler = TGUserSpreadsheetHandler(get_spreadsheet(), tg_user)

    monthly_map = tg_user_handler.get_monthly_map(result_dummy.month)
    monthly_sum = sum(monthly_map.values())

    result_plot = ResultPlot()
    plot = result_plot.my_stat(monthly_map)
    fname = result_plot.save(plot, fname=str(message.from_user.id))

    with open(fname, "rb") as fp:
        bot.send_photo(
            chat_id=chat_id,
            photo=fp,
            caption="{webhook_results_monthly}".format(**i18n.lang_map).format(**{"monthly_sum": monthly_sum}),
            reply_to_message_id=message.id,
        )


@bot.message_handler(func=filter_results_reply)
def process_results_reply(message):
    logging.warning("Processing results reply")

    logging.debug(message)

    message_parser = MessageParser()

    try:
        value = message_parser.get_value_from_reply(message.text)
    except ValueError:
        bot.reply_to(message, "{webhook_error_parse_count}".format(**i18n.lang_map))
        return None

    date = message_parser.get_date_from_notify(message.reply_to_message.json.get("text"))

    result = Result(date_notation=date, value=value)

    tg_user = TGUser(id=message.from_user.id, username=message.from_user.username)
    tg_user_handler = TGUserSpreadsheetHandler(get_spreadsheet(), tg_user)

    tg_user_handler.touch()

    try:
        tg_user_handler.add_result(result)
    except gspread.exceptions.APIError as e:
        logging.error(f"Could not write results: {e}")
        bot.reply_to(message, "{webhook_error_write_results}".format(**i18n.lang_map))
        return None

    monthly_sum = sum(tg_user_handler.get_monthly_map(result.month).values())
    monthly_sum_human = str(max(monthly_sum // 1000, 1)) + ",000"

    bot.reply_to(
        message,
        "{webhook_results_written}".format(**i18n.lang_map).format(**{"monthly_sum_human": monthly_sum_human}),
    )


if __name__ == "__main__":
    logging.critical("Starting webhook")

    bot.infinity_polling()
