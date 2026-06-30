import asyncio
import logging
import os

from telegram import Update
from telegram.error import Conflict
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import load_config
from bot.parser import parse_message
from bot.scheduler import check_and_publish


async def handle_source_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data["config"]
    msg = update.effective_message
    if msg is None:
        return
    post = parse_message(msg, config)
    if post is None:
        return
    context.bot_data.setdefault("pending_posts", {})[post.source_message_id] = post
    logging.info(
        "Добавлен пост в очередь: id=%s, channel=%s, at=%s",
        post.source_message_id,
        post.channel,
        post.publish_at,
    )


async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    channels: dict = context.bot_data.get("admin_channels", {})
    if not channels:
        await update.message.reply_text("Нет доступных каналов.")
        return
    lines = [
        f"• {info['title']} ({info.get('username') or info['id']})"
        for info in channels.values()
    ]
    await update.message.reply_text("Каналы:\n" + "\n".join(lines))


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    result = update.my_chat_member
    if result is None:
        return
    chat = result.chat
    new_status = result.new_chat_member.status

    channels: dict = context.bot_data.setdefault("admin_channels", {})
    if new_status == "administrator":
        channels[chat.id] = {
            "id": chat.id,
            "title": chat.title,
            "username": chat.username,
        }
        logging.info("Бот добавлен администратором в канал: %s (%s)", chat.title, chat.id)
    elif new_status in ("left", "kicked", "member"):
        channels.pop(chat.id, None)
        logging.info("Бот удалён из канала: %s (%s)", chat.title, chat.id)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logging.critical("Конфликт getUpdates — завершаю процесс, systemd перезапустит через 30 сек")
        os._exit(1)
    logging.error("Необработанная ошибка: %s", context.error, exc_info=context.error)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()

    app = Application.builder().token(config.bot_token).build()
    app.bot_data["config"] = config

    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(
        ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.add_handler(
        MessageHandler(
            filters.Chat(config.source_channel_id) & (filters.TEXT | filters.PHOTO),
            handle_source_message,
        )
    )

    app.job_queue.run_repeating(
        check_and_publish,
        interval=config.check_interval,
        first=10,
        data=config,
        name="check_and_publish",
    )

    logging.info("Бот запущен. SOURCE_CHANNEL_ID=%s", config.source_channel_id)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
