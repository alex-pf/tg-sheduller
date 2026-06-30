import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import CallbackContext

from bot.publisher import mark_as_published, publish_post

logger = logging.getLogger(__name__)


async def check_and_publish(context: CallbackContext) -> None:
    config = context.job.data
    now = datetime.now(tz=ZoneInfo(config.timezone))
    pending_posts: dict = context.bot_data.get("pending_posts", {})

    for msg_id, post in sorted(pending_posts.items(), key=lambda x: x[1].publish_at):
        window_start = now - timedelta(minutes=5)
        window_end = now + timedelta(minutes=config.lookahead_minutes)

        if window_start <= post.publish_at <= window_end:
            logger.info(
                "Публикация поста message_id=%s, канал=%s, время=%s",
                msg_id,
                post.channel,
                post.publish_at,
            )
            success = await publish_post(context.bot, post)
            if success:
                await mark_as_published(context.bot, config.source_channel_id, msg_id)
                del pending_posts[msg_id]
        elif post.publish_at < window_start:
            logger.warning(
                "Пропущена публикация message_id=%s, время=%s",
                msg_id,
                post.publish_at,
            )
            del pending_posts[msg_id]
