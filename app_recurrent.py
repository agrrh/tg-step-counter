import aiofiles
import aioschedule as schedule
import asyncio
import gspread
import logging
import nats
import os
import pickle
import redis
import sys
import time

from datetime import date, timedelta

from tg_step_counter.i18n import Internationalization as I18n

from tg_step_counter.objects.result import Result
from tg_step_counter.objects.leaderboard import LeaderboardPlot
from tg_step_counter.objects.tg_user import TGUser, TGUserSpreadsheetHandler


bot_token = os.environ.get("APP_TG_TOKEN")

nats_address = os.environ.get("APP_NATS_ADDRESS", "nats://nats.nats.svc:4222")
nats_subject = os.environ.get("APP_NATS_SUBJECT", "response")

chat_id = os.environ.get("APP_TG_CHAT_ID")
app_dev_mode = os.environ.get("APP_DEV_MODE") or False  # Would be True on non-empty string
challenge_tag = os.environ.get("APP_TG_CHALLENGE_TAG")

time_notify = os.environ.get("APP_TG_NOTIFY_TIME", "10:00")
time_result = os.environ.get("APP_TG_RESULT_TIME", "20:00")

google_service_account_fname = os.environ.get("APP_GOOGLE_SA_PATH", "./config/google-service-account.json")
google_sheet_uri = os.environ.get("APP_GOOGLE_SHEET_URI")

redis_host = os.environ.get("APP_REDIS_HOST", "redis")
redis_handler = redis.StrictRedis(host=redis_host)

app_language = os.environ.get("APP_LANG", "en")
i18n = I18n(lang=app_language)

REDIS_TTL = int(os.environ.get("APP_REDIS_TTL", "86400"))


def get_yesterday_notation():
    date_current = date.today()
    date_one_day_before = timedelta(days=-1)

    date_notify = date_current + date_one_day_before

    return date_notify


async def send_reminder(nats_handler=None):
    date_human = get_yesterday_notation().strftime("%d.%m")

    text = "{reminder_mark} {reminder_notify}".format(**i18n.lang_map).format(
        **{
            "challenge_tag": challenge_tag,
            "current_date_human": date_human,
        }
    )

    message = {
        "type": "generic",
        "chat_id": chat_id,
        "text": text,
    }
    data = pickle.dumps(message)

    nats_subject_ = f"{nats_subject}.{chat_id}"

    logging.warning(f"Sending response message to bus: {nats_subject_}")
    await nats_handler.publish(nats_subject_, data)


async def send_leaderboards_if_new_month_starts(nats_handler=None):
    logging.warning(f"Getting Google Spreadsheet: {google_sheet_uri}")
    gc = gspread.service_account(filename=google_service_account_fname)
    sheet = gc.open_by_url(google_sheet_uri).sheet1

    date_human = get_yesterday_notation().strftime("%d.%m")

    result_dummy = Result(date_notation=date_human)

    tg_user = TGUser(id=1)
    tg_user_handler = TGUserSpreadsheetHandler(sheet, tg_user)

    logging.debug("Form users leaderboard map")

    monthly_sum_by_user = {}
    user_aliases = {}

    for tg_user_id in tg_user_handler.get_users_row():
        if not tg_user_id.isnumeric():
            continue

        _tg_user = TGUser(id=tg_user_id)
        _tg_user_handler = TGUserSpreadsheetHandler(sheet, _tg_user)

        monthly_sum_by_user[tg_user_id] = _tg_user_handler.get_monthly(result_dummy.month)
        user_aliases[tg_user_id] = _tg_user_handler.get_user_note()

    logging.debug(f"Resulting map: {monthly_sum_by_user}")

    result_plot = LeaderboardPlot()
    plot = result_plot.generate(monthly_sum_by_user, user_aliases)
    fname = result_plot.save(plot, fname=chat_id)

    leader_id = max(monthly_sum_by_user, key=monthly_sum_by_user.get)
    leader_value = max(monthly_sum_by_user.values())

    _tg_user = TGUser(id=leader_id)
    _tg_user_handler = TGUserSpreadsheetHandler(sheet, _tg_user)
    leader_alias = _tg_user_handler.get_user_note()

    text = "{webhook_leaderboard_monthly}".format(**i18n.lang_map).format(
        **{"leader": leader_alias or leader_id, "leader_value": leader_value}
    )

    logging.warning(f"Opening file in async way: {fname}")
    async with aiofiles.open(fname, "rb") as afp:
        image_data = await afp.read()

    logging.warning("Sending file data to redis")
    redis_handler.set(fname, image_data)
    redis_handler.expire(fname, REDIS_TTL)

    message = {
        "type": "photo",
        "chat_id": chat_id,
        "photo": fname,
        "text": text,
    }
    data = pickle.dumps(message)

    nats_subject_ = f"{nats_subject}.{chat_id}"

    logging.warning(f"Sending response message to bus: {nats_subject_}")
    await nats_handler.publish(nats_subject_, data)


async def job_notify():
    logging.warning("Starting job/notify")

    logging.warning(f"Connecting to NATS at {nats_address}")
    nc = await nats.connect(nats_address)

    await send_reminder(nats_handler=nc)


async def job_result():
    logging.warning("Starting job/result")

    logging.warning(f"Connecting to NATS at {nats_address}")
    nc = await nats.connect(nats_address)

    if date.today().day == 1 or app_dev_mode:
        await send_leaderboards_if_new_month_starts(nats_handler=nc)


async def main():
    if app_dev_mode:
        logging.warning("Running single dev run")

        schedule.every(1).seconds.do(job_notify)
        time.sleep(1)
        await schedule.run_pending()
        sys.exit()

    schedule.every().day.at(time_notify).do(job_notify)
    schedule.every().day.at(time_result).do(job_result)

    while True:
        await schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    logging.critical("Starting svc/recurrent")

    asyncio.run(main())
