import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import CallbackContext

from bot.parser import parse_message
from bot.publisher import mark_as_published, publish_post

logger = logging.getLogger(__name__)


async def check_and_publish(context: CallbackContext) -> None:
    config = context.job.data
    bot = context.bot
    now = datetime.now(tz=ZoneInfo(config.timezone))
    window_start = now - timedelta(minutes=config.lookahead_minutes)
    window_end = now

    # Забираем все накопившиеся апдейты с момента последнего запуска
    offset = context.bot_data.get("update_offset", 0)
    try:
        updates = await bot.get_updates(
            offset=offset, timeout=0, limit=100,
            allowed_updates=["message", "edited_message", "my_chat_member"],
        )
    except Exception as e:
        logger.error("Ошибка get_updates: %s", e)
        return

    # Продвигаем offset — потребляем все апдейты
    if updates:
        context.bot_data["update_offset"] = updates[-1].update_id + 1

    # Обновляем список каналов где бот является админом
    for u in updates:
        if u.my_chat_member:
            r = u.my_chat_member
            chat = r.chat
            status = r.new_chat_member.status
            channels = context.bot_data.setdefault("admin_channels", {})
            if status == "administrator":
                channels[chat.id] = {"id": chat.id, "title": chat.title, "username": chat.username}
            elif status in ("left", "kicked", "member"):
                channels.pop(chat.id, None)

    # Собираем сообщения из технического канала.
    # Редактированное сообщение перезаписывает оригинал (по message_id).
    posts: dict[int, object] = {}
    for u in updates:
        msg = u.message or u.edited_message
        if msg is None or msg.chat_id != config.source_channel_id:
            continue
        post = parse_message(msg, config)
        if post is not None:
            posts[post.source_message_id] = post

    # Фильтруем по окну [now-10min, now]
    due = sorted(
        [p for p in posts.values() if window_start <= p.publish_at <= window_end],
        key=lambda p: p.publish_at,
    )

    if not due:
        logger.info("Нет постов для публикации в окне [%s … %s]", window_start, window_end)
        return

    logger.info("Постов к публикации: %d", len(due))
    for post in due:
        logger.info("Публикация: id=%s channel=%s at=%s",
                    post.source_message_id, post.channel, post.publish_at)
        success = await publish_post(bot, post)
        if success:
            await mark_as_published(bot, config.source_channel_id, post.source_message_id)
