from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from bot.config import Config
from bot.parser import ParsedPost, parse_message

TZ = "Europe/Moscow"
tz = ZoneInfo(TZ)


def make_config() -> Config:
    return Config(bot_token="token", source_channel_id=-100, timezone=TZ)


def make_message(text: str = "", caption: str = "", photo=None, message_id: int = 1) -> MagicMock:
    msg = MagicMock()
    msg.message_id = message_id
    msg.text = text or None
    msg.caption = caption or None
    msg.photo = photo
    return msg


# 1. Базовый кейс
def test_basic_parse():
    msg = make_message(text="channel: @mychannel\ntime: 14:30\nПривет мир")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.channel == "@mychannel"
    assert result.text == "Привет мир"
    assert result.publish_at.hour == 14
    assert result.publish_at.minute == 30


# 2. channel без @
def test_channel_without_at():
    msg = make_message(text="channel: mychannel\ntime: 14:30")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.channel == "@mychannel"


# 3. Числовой ID канала
def test_channel_numeric_id():
    msg = make_message(text="channel: -1001234567890\ntime: 14:30")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.channel == -1001234567890
    assert isinstance(result.channel, int)


# 4. Дата DD.MM
def test_time_dd_mm():
    msg = make_message(text="channel: @ch\ntime: 25.12 15:00")
    result = parse_message(msg, make_config())
    assert result is not None
    now_year = datetime.now(tz=tz).year
    assert result.publish_at.day == 25
    assert result.publish_at.month == 12
    assert result.publish_at.year == now_year
    assert result.publish_at.hour == 15


# 5. Дата YYYY-MM-DD HH:MM
def test_time_full_date():
    msg = make_message(text="channel: @ch\ntime: 2025-12-25 15:00")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.publish_at == datetime(2025, 12, 25, 15, 0, tzinfo=tz)


# 5b. Дата DD.MM.YY HH:MM (2-значный год)
def test_time_dd_mm_yy():
    msg = make_message(text="channel: @ch\ntime: 02.07.26 10:11")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.publish_at == datetime(2026, 7, 2, 10, 11, tzinfo=tz)


# 6. Без строки channel:
def test_missing_channel():
    msg = make_message(text="time: 14:30\nТекст")
    result = parse_message(msg, make_config())
    assert result is None


# 7. Без строки time:
def test_missing_time():
    msg = make_message(text="channel: @ch\nТекст")
    result = parse_message(msg, make_config())
    assert result is None


# 8. Неизвестный формат времени
def test_unknown_time_format():
    msg = make_message(text="channel: @ch\ntime: завтра")
    result = parse_message(msg, make_config())
    assert result is None


# 9. Строки в обратном порядке
def test_reverse_order():
    msg = make_message(text="time: 14:30\nchannel: @mychannel\nТекст поста")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.channel == "@mychannel"
    assert result.text == "Текст поста"


# 10. CHANNEL: в верхнем регистре
def test_uppercase_channel():
    msg = make_message(text="CHANNEL: @mychannel\nTIME: 14:30\nТекст")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.channel == "@mychannel"


# 11. Пустой текст после удаления служебных строк
def test_empty_text_after_stripping():
    msg = make_message(text="channel: @ch\ntime: 14:30")
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.text == ""


# 12. Фото + caption
def test_photo_with_caption():
    photo_mock = MagicMock()
    photo_mock.file_id = "file_id_123"
    msg = make_message(
        caption="channel: @ch\ntime: 14:30\nПодпись к фото",
        photo=[photo_mock],
    )
    result = parse_message(msg, make_config())
    assert result is not None
    assert result.photo_file_id == "file_id_123"
    assert result.text == "Подпись к фото"
