import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import telegram

from bot.config import Config

logger = logging.getLogger(__name__)


@dataclass
class ParsedPost:
    channel: "str | int"
    publish_at: datetime
    text: str
    photo_file_id: "str | None"
    source_message_id: int


def _parse_time(time_str: str, config: Config) -> "datetime | None":
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz=tz)
    today = now.date()
    s = time_str.strip()

    # HH:MM
    try:
        t = datetime.strptime(s, "%H:%M")
        dt = datetime(today.year, today.month, today.day, t.hour, t.minute, tzinfo=tz)
        # Если время уже прошло более чем на 1 час — считать завтра
        if dt < now - timedelta(hours=1):
            dt += timedelta(days=1)
        return dt
    except ValueError:
        pass

    # HH:MM:SS
    try:
        t = datetime.strptime(s, "%H:%M:%S")
        dt = datetime(today.year, today.month, today.day, t.hour, t.minute, t.second, tzinfo=tz)
        if dt < now - timedelta(hours=1):
            dt += timedelta(days=1)
        return dt
    except ValueError:
        pass

    # DD.MM HH:MM
    try:
        t = datetime.strptime(s, "%d.%m %H:%M")
        dt = datetime(today.year, t.month, t.day, t.hour, t.minute, tzinfo=tz)
        return dt
    except ValueError:
        pass

    # DD.MM.YYYY HH:MM
    try:
        t = datetime.strptime(s, "%d.%m.%Y %H:%M")
        dt = datetime(t.year, t.month, t.day, t.hour, t.minute, tzinfo=tz)
        return dt
    except ValueError:
        pass

    # YYYY-MM-DD HH:MM
    try:
        t = datetime.strptime(s, "%Y-%m-%d %H:%M")
        dt = datetime(t.year, t.month, t.day, t.hour, t.minute, tzinfo=tz)
        return dt
    except ValueError:
        pass

    # YYYY-MM-DDTHH:MM
    try:
        t = datetime.strptime(s, "%Y-%m-%dT%H:%M")
        dt = datetime(t.year, t.month, t.day, t.hour, t.minute, tzinfo=tz)
        return dt
    except ValueError:
        pass

    # YYYY-MM-DDTHH:MM+HH:MM  (timezone из строки)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt
    except ValueError:
        pass

    logger.warning("Не удалось распознать время: %r", s)
    return None


def _normalize_channel(raw: str) -> "str | int":
    raw = raw.strip()
    # Числовой ID (отрицательный)
    if raw.startswith("-") and raw[1:].isdigit():
        return int(raw)
    # Положительный числовой ID
    if raw.isdigit():
        return int(raw)
    # Добавить @ если нет
    if not raw.startswith("@"):
        return "@" + raw
    return raw


def parse_message(message: telegram.Message, config: Config) -> "ParsedPost | None":
    # Получить текст или подпись
    raw_text: "str | None" = None
    if message.text:
        raw_text = message.text
    elif message.caption:
        raw_text = message.caption

    if not raw_text:
        return None

    lines = raw_text.splitlines()

    channel_value: "str | None" = None
    time_value: "str | None" = None
    service_line_indices: set = set()

    for i, line in enumerate(lines):
        lower = line.lower().lstrip()
        if lower.startswith("channel:"):
            channel_value = line.split(":", 1)[1].strip()
            service_line_indices.add(i)
        elif lower.startswith("time:"):
            time_value = line.split(":", 1)[1].strip()
            service_line_indices.add(i)

    if channel_value is None or time_value is None:
        return None

    channel = _normalize_channel(channel_value)

    publish_at = _parse_time(time_value, config)
    if publish_at is None:
        return None

    # Собрать текст без служебных строк
    content_lines = [line for i, line in enumerate(lines) if i not in service_line_indices]
    text = "\n".join(content_lines).strip()

    # Фото
    photo_file_id: "str | None" = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id

    return ParsedPost(
        channel=channel,
        publish_at=publish_at,
        text=text,
        photo_file_id=photo_file_id,
        source_message_id=message.message_id,
    )
