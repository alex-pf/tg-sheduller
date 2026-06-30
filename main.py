import asyncio
import logging
import signal

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.config import load_config
from bot.parser import parse_message
from bot.scheduler import check_and_publish

logger = logging.getLogger(__name__)


async def poll_updates(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Каждую минуту забирает новые updates через короткий poll (timeout=0, без конфликтов)."""
    config = context.job.data
    bot: Bot = context.bot

    offset = context.bot_data.get("update_offset", 0)
    try:
        updates = await bot.get_updates(
            offset=offset, timeout=0, limit=100,
            allowed_updates=["message", "my_chat_member"],
        )
    except Exception as e:
        logger.error("Ошибка get_updates: %s", e)
        return

    for update in updates:
        context.bot_data["update_offset"] = update.update_id + 1

        if update.my_chat_member:
            result = update.my_chat_member
            chat = result.chat
            status = result.new_chat_member.status
            channels = context.bot_data.setdefault("admin_channels", {})
            if status == "administrator":
                channels[chat.id] = {"id": chat.id, "title": chat.title, "username": chat.username}
                logger.info("Бот стал админом в: %s (%s)", chat.title, chat.id)
            elif status in ("left", "kicked", "member"):
                channels.pop(chat.id, None)

        if update.message:
            msg = update.message
            # Сообщение из технического канала — добавить в очередь
            if msg.chat_id == config.source_channel_id:
                post = parse_message(msg, config)
                if post is not None:
                    context.bot_data.setdefault("pending_posts", {})[post.source_message_id] = post
                    logger.info("Пост в очереди: id=%s channel=%s at=%s",
                                post.source_message_id, post.channel, post.publish_at)
            # Команда /channels в личке или в группе
            elif msg.text and msg.text.startswith("/channels"):
                await _send_channels(bot, msg.chat_id, context.bot_data)


async def _send_channels(bot: Bot, chat_id: int, bot_data: dict) -> None:
    channels: dict = bot_data.get("admin_channels", {})
    if not channels:
        await bot.send_message(chat_id, "Нет доступных каналов.")
        return
    lines = [f"• {info['title']} ({info.get('username') or info['id']})"
             for info in channels.values()]
    await bot.send_message(chat_id, "Каналы:\n" + "\n".join(lines))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()

    app = Application.builder().token(config.bot_token).updater(None).build()
    app.bot_data["config"] = config

    # Опрос обновлений каждые 30 сек (short poll, никогда не конфликтует)
    app.job_queue.run_repeating(poll_updates, interval=30, first=5, data=config,
                                name="poll_updates")
    # Публикация запланированных постов
    app.job_queue.run_repeating(check_and_publish, interval=config.check_interval, first=15,
                                data=config, name="check_and_publish")

    async def run() -> None:
        async with app:
            await app.start()
            # Сбросить webhook если был
            await app.bot.delete_webhook(drop_pending_updates=False)
            logger.info("Бот запущен (short-poll режим). SOURCE_CHANNEL_ID=%s",
                        config.source_channel_id)

            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            await stop_event.wait()
            logger.info("Получен сигнал завершения, останавливаю бота...")

    asyncio.run(run())


if __name__ == "__main__":
    main()
