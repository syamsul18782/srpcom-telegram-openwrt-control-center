#!/bin/sh
set -e

echo "=========================================================="
echo "    SRPCOM Telegram OpenWrt Control Center Installer     "
echo "=========================================================="

IPK_URL="https://github.com/syamsul18782/srpcom-telegram-openwrt-control-center/releases/download/v1.0.0/SRPCOM_telegram_OPENWRT_CONTROL_CENTER.ipk"
TMP_IPK="/tmp/SRPCOM_telegram_OPENWRT_CONTROL_CENTER.ipk"

echo "[1/4] Memperbarui daftar paket (opkg update)..."
opkg update

echo "[2/4] Memeriksa dan menginstall dependensi..."
opkg install python3 curl 2>/dev/null || true
opkg install vnstat2 vnstati2 2>/dev/null || opkg install vnstat vnstati 2>/dev/null || true

echo "[3/4] Mengunduh paket SRPCOM Telegram Control Center..."
curl -fsSL -o "$TMP_IPK" "$IPK_URL" || wget -q -O "$TMP_IPK" "$IPK_URL"

echo "[4/4] Memasang paket .ipk..."
opkg install --force-reinstall "$TMP_IPK"
rm -f "$TMP_IPK"

echo ""
echo "=========================================================="
echo " ✅ Instalasi Berhasil Selesai!"
echo ""
echo " Silakan atur Bot Token & Chat ID Telegram Anda:"
echo "   uci set telegram.settings.bot_token='BOT_TOKEN_ANDA'"
echo "   uci set telegram.settings.group_id='CHAT_ID_ANDA'"
echo "   uci commit telegram"
echo "   /etc/init.d/srpcom_bot restart"
echo "=========================================================="
