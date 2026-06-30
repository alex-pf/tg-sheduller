import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    source_channel_id: int
    check_interval: int = 600
    lookahead_minutes: int = 10
    timezone: str = "Europe/Moscow"


def load_config() -> Config:
    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        raise ValueError("BOT_TOKEN не задан в переменных окружения")

    source_channel_id_str = os.environ.get("SOURCE_CHANNEL_ID", "")
    if not source_channel_id_str:
        raise ValueError("SOURCE_CHANNEL_ID не задан в переменных окружения")

    try:
        source_channel_id = int(source_channel_id_str)
    except ValueError:
        raise ValueError(f"SOURCE_CHANNEL_ID должен быть числом, получено: {source_channel_id_str!r}")

    timezone = os.environ.get("TIMEZONE", "Europe/Moscow")
    check_interval = int(os.environ.get("CHECK_INTERVAL", "600"))
    lookahead_minutes = int(os.environ.get("LOOKAHEAD_MINUTES", "10"))

    return Config(
        bot_token=bot_token,
        source_channel_id=source_channel_id,
        timezone=timezone,
        check_interval=check_interval,
        lookahead_minutes=lookahead_minutes,
    )
