# 🤖 SRPCOM Telegram OpenWrt Control Center

Panel Kontrol STB / Router OpenWrt berbasis **Telegram Bot Daemon** dengan tampilan **100% Tombol Interaktif (Inline Keyboard)**.

---

## ⚡ Fitur Utama:
- 📊 **Status Sistem & Jaringan Lengkap**: Uptime, CPU Temperature bar & Overheat alert, RAM bar, IP Publik, Ping test, Jumlah klien aktif.
- 📈 **Monitoring Pemakaian Kuota (vnStat & vnstati)**:
  - Teks akurat kuota Hari Ini, Kemarin, Bulan Ini, dan Total Akumulasi.
  - Pengiriman gambar grafik visual beresolusi tinggi langsung ke chat: **Grafik Harian**, **Grafik Bulanan**, **Grafik Bandwidth 24 Jam**, dan **Rekap Ringkas**.
  - Pendaftaran otomatis interface monitor (`br-lan` & `eth1`).
- 🚀 **Official Ookla Speedtest CLI**:
  - Binary resmi Ookla Speedtest (`aarch64`) dibundel langsung tanpa perlu download ulang.
  - Menampilkan download/upload speed, ping latency, jitter, ISP, dan link hasil uji resmi Speedtest.net.
  - Fallback otomatis ke Cloudflare CDN jika port jaringan dibatasi.
- 👥 **Manajemen Klien & Keamanan**:
  - Lihat daftar perangkat klien yang terhubung beserta nama host, IP, dan MAC address.
  - Blokir dan buka blokir perangkat klien secara instan dengan 1 tombol (*iptables*).
- 📶 **Modem Hilink & SMS Integration**:
  - Cek informasi modem, frekuensi/band, dan kekuatan sinyal (RSSI, RSRP, RSRQ, SINR).
  - Notifikasi instan saat ada SMS baru masuk ke modem.
  - Baca pesan SMS masuk langsung dari tombol Telegram.
- 🧹 **Pembersihan Cache RAM**: Bebaskan swap/pagecache RAM router dengan 1 klik.
- 💾 **Backup Konfigurasi**: Buat backup konfigurasi OpenWrt (`sysupgrade -b`) dan langsung kirimkan file `.tar.gz` ke chat Telegram.
- 🔄 **Restart Router**: Restart STB/router secara remote dengan dialog konfirmasi aman.
- 🔔 **Notifikasi Pasif Cerdas**: Alert saat STB baru menyala, peringatan suhu tinggi (>70°C), dan notifikasi saat IP publik berubah.

---

## 🚀 Cara Install 1 Kali Copas (One-Liner Install):

Jalankan perintah ini di terminal **Terminal / SSH / TTYD** OpenWrt Anda:

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/syamsul18782/srpcom-telegram-openwrt-control-center/main/install.sh 2>/dev/null || wget -qO- https://raw.githubusercontent.com/syamsul18782/srpcom-telegram-openwrt-control-center/main/install.sh)"
```

---

## ⚙️ Pengaturan Token Bot & Chat ID:

Setelah instalasi selesai, masukkan Token Bot dan ID Chat Telegram Anda:

```sh
uci set telegram.settings.bot_token='TOKEN_BOT_TELEGRAM_ANDA'
uci set telegram.settings.group_id='CHAT_ID_ANDA'
uci commit telegram
/etc/init.d/srpcom_bot restart
```

---

## 📦 Download Paket Manual (.ipk):
Download rilis terbaru langsung dari [Releases](https://github.com/syamsul18782/srpcom-telegram-openwrt-control-center/releases/latest):
- **`SRPCOM_telegram_OPENWRT_CONTROL_CENTER.ipk`**

Install manual:
```sh
opkg update && opkg install python3 curl vnstat2 vnstati2
opkg install SRPCOM_telegram_OPENWRT_CONTROL_CENTER.ipk
```

---
👤 *Created & Maintained by [SRPCOM](https://srpcom.cloud)*
