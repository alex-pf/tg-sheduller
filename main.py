import asyncio
import logging
import signal

from telegram import Bot
from telegram.ext import Application, ContextTypes

from bot.config import load_config
from bot.scheduler import check_and_publish

logger = logging.getLogger(__name__)


async def channels_command_handler(bot: Bot, chat_id: int, bot_data: dict) -> None:
    channels: dict = bot_data.get("admin_channels", {})
    if not channels:
        await bot.send_message(chat_id, "Нет доступных каналов.")
        return
    lines = [f"• {info['title']} ({info.get('username') or info['id']})"
             for info in channels.values()]
    await bot.send_message(chat_id, "Каналы:\n" + "\n".join(lines))


async def handle_commands(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отвечает на /channels — запускается в том же цикле что и check_and_publish."""
    config = context.job.data
    bot = context.bot

    offset = context.bot_data.get("cmd_offset", 0)
    try:
        updates = await bot.get_updates(
            offset=offset, timeout=0, limit=100,
            allowed_updates=["message"],
        )
    except Exception as e:
        logger.error("Ошибка get_updates (команды): %s", e)
        return

    if updates:
        context.bot_data["cmd_offset"] = updates[-1].update_id + 1

    for u in updates:
        msg = u.message
        if msg and msg.text and msg.text.startswith("/channels"):
            await channels_command_handler(bot, msg.chat_id, context.bot_data)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()

    app = Application.builder().token(config.bot_token).updater(None).build()
    app.bot_data["config"] = config

    # Основной job: просыпается каждые 10 минут, публикует запланированные посты
    app.job_queue.run_repeating(
        check_and_publish,
        interval=config.check_interval,
        first=10,
        data=config,
        name="check_and_publish",
    )

    # Лёгкий job для ответа на команды (раз в минуту)
    app.job_queue.run_repeating(
        handle_commands,
        interval=60,
        first=5,
        data=config,
        name="handle_commands",
    )

    async def run() -> None:
        async with app:
            await app.start()
            await app.bot.delete_webhook(drop_pending_updates=False)
            logger.info("Бот запущен. SOURCE_CHANNEL_ID=%s, интервал=%ds",
                        config.source_channel_id, config.check_interval)

            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            await stop_event.wait()
            logger.info("Завершение работы...")

    asyncio.run(run())


if __name__ == "__main__":
    main()
