"""
/backup and /restore — export/import the entire database as one JSON file.

Covers every table automatically (users, premium, posts, tokens, config,
scheduled posts, auto-publish list, and anything added later), since
Tools.db.export_all()/import_all() walk every registered Table.
"""
import json
import os
import time

from pyrogram import filters

from bot import Bot, Vars, logger
from Tools.db import export_all, import_all
from .storage import retry_on_flood, igrone_error

BACKUP_DIR = "/tmp"


@Bot.on_message(filters.command("backup") & filters.user(Vars.ADMINS))
async def backup_cmd(client, message):
    sts = await retry_on_flood(message.reply_text)("<i>📦 Building backup...</i>", quote=True)
    dump = export_all()
    path = os.path.join(BACKUP_DIR, f"manwa_backup_{int(time.time())}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False)

        size_kb = os.path.getsize(path) / 1024
        counts = ", ".join(f"{k}: {len(v)}" for k, v in dump.items()) or "empty database"
        await retry_on_flood(client.send_document)(
            message.chat.id, path,
            caption=(
                f"<b>📦 Backup complete</b> ({size_kb:.1f} KB)\n\n<code>{counts}</code>\n\n"
                "⚠️ Keep this safe — it contains user data. To restore it, "
                "reply to this file with /restore."
            ),
        )
    except Exception as e:
        logger.exception(e)
        return await igrone_error(sts.edit_text)(f"❌ Backup failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)
    await igrone_error(sts.delete)()


@Bot.on_message(filters.command("restore") & filters.user(Vars.ADMINS))
async def restore_cmd(client, message):
    reply = message.reply_to_message
    doc = (reply.document if reply else None) or message.document
    if not doc:
        return await retry_on_flood(message.reply_text)(
            "❌ Reply to a backup <code>.json</code> file with /restore "
            "(or attach the file with /restore as the caption).\n\n"
            "Add <code>overwrite</code> after the command to force-replace "
            "existing entries instead of just filling in missing ones.",
            quote=True,
        )

    overwrite = "overwrite" in (message.text or message.caption or "").lower()
    sts = await retry_on_flood(message.reply_text)("<i>📥 Downloading backup...</i>", quote=True)

    try:
        path = await client.download_media(reply or message)
    except Exception as e:
        logger.exception(e)
        return await igrone_error(sts.edit_text)(f"❌ Couldn't download that file: {e}")

    try:
        with open(path, encoding="utf-8") as f:
            dump = json.load(f)
    except Exception as e:
        return await igrone_error(sts.edit_text)(f"❌ That doesn't look like a valid backup file: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)

    if not isinstance(dump, dict):
        return await igrone_error(sts.edit_text)("❌ That doesn't look like a valid backup file.")

    await igrone_error(sts.edit_text)(
        "<i>⚠️ Restoring in OVERWRITE mode — existing entries will be replaced...</i>"
        if overwrite else
        "<i>📥 Restoring (merge mode — only filling in missing entries)...</i>"
    )

    try:
        stats = import_all(dump, overwrite=overwrite)
    except Exception as e:
        logger.exception(e)
        return await igrone_error(sts.edit_text)(f"❌ Restore failed: {e}")

    if not stats:
        return await igrone_error(sts.edit_text)(
            "✅ Restore finished — nothing new to write "
            "(use <code>/restore overwrite</code> to force-replace existing entries)."
        )

    lines = "\n".join(f"• {k}: +{v}" for k, v in stats.items())
    await igrone_error(sts.edit_text)(f"<b>✅ Restore complete</b>\n\n{lines}")
