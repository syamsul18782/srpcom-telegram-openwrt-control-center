# 🤖 SRPCOM Telegram OpenWrt Control Center

Panel Kontrol STB / Router OpenWrt berbasis **Telegram Bot Daemon** dengan tampilan **100% Tombol Interaktif (Inline Keyboard)** dan dilengkapi **Web GUI LuCI** untuk konfigurasi praktis tanpa terminal!

---

## ⚡ Fitur Utama:
- 🌐 **Web GUI LuCI Terintegrasi**:
  - Menu pengaturan langsung di LuCI: **Services ➔ SRPCOM Telegram**.
  - Form pengisian **Bot Token**, **Chat ID / Group ID**, dan **Message Thread ID**.
  - Indikator status daemon real-time (**Aktif Berjalan / Berhenti**) beserta nomor PID.
  - Tombol **Restart Bot** langsung dari web.
  - Tombol **Kirim Pesan Uji Coba (Test Message)** untuk memastikan koneksi bot bekerja seketika.
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

---

## 🚀 Cara Install 1 Kali Copas (One-Liner Install):

Jalankan perintah ini di **Terminal / SSH / TTYD** OpenWrt Anda:

```sh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/syamsul18782/srpcom-telegram-openwrt-control-center/main/install.sh 2>/dev/null || wget -qO- https://raw.githubusercontent.com/syamsul18782/srpcom-telegram-openwrt-control-center/main/install.sh)"
```

---

## 🖥️ Pengaturan Melalui Web GUI LuCI:

Setelah proses instalasi selesai:
1. Buka browser dan login ke LuCI OpenWrt Anda.
2. Buka menu: **Services ➔ SRPCOM Telegram**.
3. Masukkan **Telegram Bot Token** dan **Chat ID / Group ID** Anda.
4. Klik tombol **Save & Apply** (Simpan & Terapkan).
5. Anda juga dapat mengklik tombol **Kirim Pesan Uji Coba** untuk langsung menguji pengiriman pesan ke Telegram!

---

## 📦 Download Paket Manual (.ipk):
Download rilis terbaru langsung dari [Releases](https://github.com/syamsul18782/srpcom-telegram-openwrt-control-center/releases/latest):
- **`SRPCOM_telegram_OPENWRT_CONTROL_CENTER.ipk`** (v1.1.0)

---
👤 *Created & Maintained by [SRPCOM](https://srpcom.cloud)*
