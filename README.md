# tg-scheduler — Telegram-бот планировщик публикаций

Бот читает сообщения из технического канала, парсит время публикации и целевой канал, затем автоматически публикует сообщения по расписанию.

## Формат сообщений в техническом канале

```
channel: @mychannel
time: 25.12 15:00
Текст публикации
```

### Поле `channel`

- `@username` — публичный канал
- `-1001234567890` — числовой ID канала (бот должен быть там администратором)

### Поле `time` — поддерживаемые форматы

| Формат | Пример |
|---|---|
| `HH:MM` | `14:30` |
| `HH:MM:SS` | `14:30:00` |
| `DD.MM HH:MM` | `25.12 15:00` |
| `DD.MM.YYYY HH:MM` | `25.12.2025 15:00` |
| `YYYY-MM-DD HH:MM` | `2025-12-25 15:00` |
| `YYYY-MM-DDTHH:MM` | `2025-12-25T15:00` |
| `YYYY-MM-DDTHH:MM+HH:MM` | `2025-12-25T15:00+03:00` |

Если указан только `HH:MM` и это время уже прошло более часа назад — считается следующий день.

---

## Установка на VPS

### 1. Подготовка сервера

```bash
# Создать пользователя (если нет)
adduser devuser
usermod -aG sudo devuser

# Установить зависимости
apt update && apt install -y python3.11 python3.11-venv git
```

### 2. Клонировать репозиторий

```bash
mkdir -p /opt/tg-scheduler
cd /opt/tg-scheduler
git clone https://github.com/YOUR_USER/tg-sheduller.git .
chown -R devuser:devuser /opt/tg-scheduler
```

### 3. Виртуальное окружение и зависимости

```bash
su - devuser
cd /opt/tg-scheduler
python3.11 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

### 4. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

Заполнить:
```
BOT_TOKEN=токен_от_BotFather
SOURCE_CHANNEL_ID=-1001234567890   # ID технического канала
TIMEZONE=Europe/Moscow
```

### 5. Настройка systemd-сервиса

```bash
# От root
cp tg-scheduler.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable tg-scheduler
systemctl start tg-scheduler
```

Проверить статус:
```bash
systemctl status tg-scheduler
journalctl -u tg-scheduler -f
```

### 6. Настройка бота в Telegram

1. Создать бота через @BotFather, получить токен.
2. Добавить бота в **технический канал** (SOURCE_CHANNEL_ID) как администратора.
3. Добавить бота как администратора во все **целевые каналы**, куда нужно публиковать.
4. После добавления в канал бот автоматически запомнит его — проверить командой `/channels`.

---

## Автодеплой через GitHub Actions

В настройках репозитория (Settings → Secrets and variables → Actions) задать:

| Secret | Значение |
|---|---|
| `VPS_HOST` | IP или домен VPS |
| `VPS_USER` | Пользователь SSH (например `devuser`) |
| `VPS_SSH_KEY` | Приватный SSH-ключ (содержимое `~/.ssh/id_rsa`) |

При каждом push в ветку `main` GitHub Actions автоматически выполнит pull и перезапустит сервис.

---

## Локальный запуск и тесты

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить бота
cp .env.example .env  # заполнить значения
python main.py

# Запустить тесты
pip install pytest
pytest tests/
```

## Команды бота

| Команда | Описание |
|---|---|
| `/channels` | Показать список каналов, где бот является администратором |
