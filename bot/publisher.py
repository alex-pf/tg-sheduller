import logging

from telegram import Bot
from telegram.constants import ReactionEmoji
from telegram.error import TelegramError
from telegram.helpers import mention_html

from bot.parser import ParsedPost

logger = logging.getLogger(__name__)


async def publish_post(bot: Bot, post: ParsedPost) -> bool:
    try:
        if post.photo_file_id:
            await bot.send_photo(
                chat_id=post.channel,
                photo=post.photo_file_id,
                caption=post.text or None,
            )
        else:
            await bot.send_message(
                chat_id=post.channel,
                text=post.text,
            )
        logger.info(
            "Опубликован пост source_message_id=%s в канал %s",
            post.source_message_id,
            post.channel,
        )
        return True
    except TelegramError as e:
        logger.error(
            "Ошибка публикации поста source_message_id=%s в канал %s: %s",
            post.source_message_id,
            post.channel,
            e,
        )
        return False


async def mark_as_published(bot: Bot, channel_id: int, message_id: int) -> None:
    try:
        from telegram import ReactionTypeEmoji

        await bot.set_message_reaction(
            chat_id=channel_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji("👍")],
        )
    except TelegramError as e:
        logger.warning(
            "Не удалось поставить реакцию на message_id=%s: %s",
            message_id,
            e,
        )
