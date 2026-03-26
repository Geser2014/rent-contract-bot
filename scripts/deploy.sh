#!/bin/bash
# Деплой Rent Contract Bot на Ubuntu VPS
# Запуск: bash deploy.sh

set -e

echo "=== 1. Обновление системы ==="
apt update && apt install -y git python3 python3-venv libreoffice-core libreoffice-writer fonts-crosextra-carlito fonts-crosextra-caladea

echo "=== 2. Клонирование проекта ==="
cd /home
if [ -d "rent-contract-bot" ]; then
    echo "Проект уже существует, обновляю..."
    cd rent-contract-bot && git pull
else
    git clone https://github.com/Geser2014/rent-contract-bot.git
    cd rent-contract-bot
fi

echo "=== 3. Python venv ==="
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "=== 4. Шрифт Oswald ==="
cp fonts/Oswald-VariableFont_wght.ttf /usr/local/share/fonts/ 2>/dev/null || true
fc-cache -fv

echo "=== 5. Настройка .env ==="
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "!!! ВНИМАНИЕ: Нужно отредактировать .env !!!"
    echo "Выполните: nano /home/rent-contract-bot/.env"
    echo "Вставьте TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, BOT_PASSWORD"
    echo ""
fi

echo "=== 6. Проверка LibreOffice ==="
python scripts/verify_libreoffice.py || true

echo "=== 7. Создание systemd сервиса ==="
cat > /etc/systemd/system/rent-bot.service << 'EOF'
[Unit]
Description=Rent Contract Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/rent-contract-bot
EnvironmentFile=/home/rent-contract-bot/.env
ExecStart=/home/rent-contract-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rent-bot

echo ""
echo "=== ГОТОВО ==="
echo ""
echo "Следующие шаги:"
echo "1. Отредактируйте .env:  nano /home/rent-contract-bot/.env"
echo "2. Запустите бота:       systemctl start rent-bot"
echo "3. Проверьте статус:     systemctl status rent-bot"
echo "4. Логи:                 journalctl -u rent-bot -f"
