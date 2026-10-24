#!/bin/sh
set -e

echo "=========================================================="
echo "    SRPCOM Telegram OpenWrt Control Center Installer     "
echo "=========================================================="

IPK_URL="https://github.com/syamsul18782/srpcom-telegram-openwrt-control-center/releases/download/v1.1.0/SRPCOM_telegram_OPENWRT_CONTROL_CENTER.ipk"
TMP_IPK="/tmp/SRPCOM_telegram_OPENWRT_CONTROL_CENTER.ipk"

echo "[1/3] Memeriksa dependensi sistem..."
if ! which python3 >/dev/null 2>&1 || ! which curl >/dev/null 2>&1; then
    echo " -> Memperbarui paket dan menginstall python3 & curl..."
    opkg update 2>/dev/null || true
    opkg install python3 curl libcurl4 2>/dev/null || true
fi

if ! which vnstat >/dev/null 2>&1; then
    echo " -> Menginstall vnStat traffic monitor..."
    opkg install vnstat2 vnstati2 2>/dev/null || opkg install vnstat vnstati 2>/dev/null || true
fi

echo "[2/3] Mengunduh paket SRPCOM Telegram Control Center..."
curl -fsSL -o "$TMP_IPK" "$IPK_URL" 2>/dev/null || wget -q -O "$TMP_IPK" "$IPK_URL"

echo "[3/3] Memasang paket .ipk..."
opkg install --force-reinstall --force-overwrite "$TMP_IPK"
rm -f "$TMP_IPK"

echo ""
echo "=========================================================="
echo " ✅ Instalasi Berhasil Selesai!"
echo ""
echo " 🌐 PENGATURAN DAPAT DILAKUKAN MELALUI WEB GUI LUCI:"
echo "    Buka browser: Services -> SRPCOM Telegram"
echo ""
echo " Atau via terminal (opsional):"
echo "    uci set telegram.settings.bot_token='BOT_TOKEN_ANDA'"
echo "    uci set telegram.settings.group_id='CHAT_ID_ANDA'"
echo "    uci commit telegram"
echo "    /etc/init.d/srpcom_bot restart"
echo "=========================================================="
