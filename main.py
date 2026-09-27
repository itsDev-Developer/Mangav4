import uvloop
import asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
uvloop.install()

import os
import shutil

from bot import Bot, Vars, logger
from Tools.config import apply_all
from Tools.auto import main_updates
from Tools.my_token import expired_token_
from Tools.db import remove_expired_users
from Tools.cworker import ensure_workers
from TG.post import scheduled_posts_loop, autopublish_loop

folder_path = "Process"
if os.path.exists(folder_path) and os.path.isdir(folder_path):
  shutil.rmtree(folder_path)

# Copy any settings saved from /settings (or the environment) onto `Vars`
# before anything reads it. Previously this was never called anywhere, so
# every change made from the bot's settings panel silently reverted to the
# env-var defaults on the next restart.
apply_all()


async def main_exp_():
  while True:
    try:
      await remove_expired_users()
      expired_token_()
    except Exception as e:
      logger.exception(e)
    finally:
      await asyncio.sleep(3600)


async def _start_workers():
  # Spawns exactly `Vars.WORKERS` chapter-processing workers (default 3,
  # editable live from /settings -> Performance) and keeps that count in
  # sync if the setting changes later - see Tools/cworker.py.
  #
  # The previous version unconditionally spawned 20 raw workers here,
  # ignoring the WORKERS setting entirely - each worker runs its own
  # download/convert/upload pipeline (with its own thread pool for image
  # downloads), so that alone was often running several times more
  # concurrent work than intended. This was the single biggest source of
  # unnecessary RAM/CPU use in the bot.
  ensure_workers()


if __name__ == "__main__":
  Bot.startup_hooks.append(_start_workers)
  Bot.startup_hooks.append(main_updates)
  Bot.startup_hooks.append(scheduled_posts_loop)
  Bot.startup_hooks.append(autopublish_loop)
  if Vars.SHORTENER:
    Bot.startup_hooks.append(main_exp_)

  Bot.run()
