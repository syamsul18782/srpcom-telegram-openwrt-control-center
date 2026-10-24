#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRPCOM OpenWrt Telegram Bot Daemon
Features:
1. Smart Passive Alerts: Startup, Overheat (>70C), WAN IP Change, SMS Notice
2. Interactive Remote Commands & Inline Keyboards for ALL features
3. Security & Access Control: One-click Inline Block/Unblock via iptables
"""

import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import threading
import xml.etree.ElementTree as ET

BLOCKED_FILE = "/etc/srpcom_blocked.json"
STATE_FILE = "/tmp/srpcom_bot_state.json"

def get_uci(path, default=""):
    try:
        out = subprocess.check_output(f"uci get {path} 2>/dev/null", shell=True).decode().strip()
        return out if out else default
    except:
        return default

def get_hostname():
    try:
        out = subprocess.check_output("ubus call system board 2>/dev/null", shell=True).decode()
        data = json.loads(out)
        return data.get("hostname", "OpenWrt")
    except:
        return "OpenWrt"

BOT_TOKEN = get_uci("telegram.settings.bot_token")
CHAT_ID = get_uci("telegram.settings.group_id")
MSG_THREAD_ID = get_uci("telegram.settings.message_thread_id", "0")
HOSTNAME = get_hostname()

# ----------------- IPTABLES FIREWALL BLOCKING -----------------
def init_firewall():
    subprocess.run("iptables -N SRPCOM_BLOCK 2>/dev/null || true", shell=True)
    subprocess.run("iptables -C FORWARD -j SRPCOM_BLOCK 2>/dev/null || iptables -I FORWARD 1 -j SRPCOM_BLOCK", shell=True)
    blocked = load_blocked_macs()
    for mac in blocked:
        subprocess.run(f"iptables -C SRPCOM_BLOCK -m mac --mac-source {mac} -j DROP 2>/dev/null || iptables -A SRPCOM_BLOCK -m mac --mac-source {mac} -j DROP", shell=True)

def load_blocked_macs():
    if os.path.exists(BLOCKED_FILE):
        try:
            with open(BLOCKED_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_blocked_macs(data):
    try:
        with open(BLOCKED_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving blocked MACs: {e}")

def block_mac(mac, name="Unknown"):
    mac = mac.strip().lower()
    subprocess.run(f"iptables -C SRPCOM_BLOCK -m mac --mac-source {mac} -j DROP 2>/dev/null || iptables -A SRPCOM_BLOCK -m mac --mac-source {mac} -j DROP", shell=True)
    blocked = load_blocked_macs()
    blocked[mac] = {"name": name, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_blocked_macs(blocked)

def unblock_mac(mac):
    mac = mac.strip().lower()
    subprocess.run(f"iptables -D SRPCOM_BLOCK -m mac --mac-source {mac} -j DROP 2>/dev/null || true", shell=True)
    blocked = load_blocked_macs()
    if mac in blocked:
        del blocked[mac]
        save_blocked_macs(blocked)

# ----------------- TELEGRAM API HELPERS -----------------
def tg_request(method, params=None, timeout=30):
    if not BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        if params is not None:
            data = urllib.parse.urlencode(params).encode("utf-8")
            req = urllib.request.Request(url, data=data)
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"TG API {method} error: {e}")
        return None

def send_message(text, reply_markup=None, target_chat=None):
    chat = target_chat or CHAT_ID
    if not chat:
        return None
    params = {
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true"
    }
    if MSG_THREAD_ID and MSG_THREAD_ID != "0":
        params["message_thread_id"] = MSG_THREAD_ID
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    return tg_request("sendMessage", params)

def edit_message_text(chat_id, message_id, text, reply_markup=None):
    if not BOT_TOKEN or not chat_id or not message_id:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true"
    }
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    try:
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if "message is not modified" in err_body:
            return {"ok": True, "not_modified": True}
        print(f"editMessageText HTTP error: {e} -> {err_body}")
        return None
    except Exception as e:
        print(f"editMessageText error: {e}")
        return None

def answer_callback(callback_id, text="", alert=False):
    params = {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": "true" if alert else "false"
    }
    return tg_request("answerCallbackQuery", params)

def edit_reply_markup(chat_id, message_id, reply_markup):
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": json.dumps(reply_markup)
    }
    return tg_request("editMessageReplyMarkup", params)

def send_document(filepath, caption="", target_chat=None):
    chat = target_chat or CHAT_ID
    if not BOT_TOKEN or not chat or not os.path.exists(filepath):
        return None
    cmd = [
        "curl", "-s",
        "-F", f"chat_id={chat}",
        "-F", f"caption={caption}",
        "-F", "parse_mode=HTML",
        "-F", f"document=@{filepath}",
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    ]
    if MSG_THREAD_ID and MSG_THREAD_ID != "0":
        cmd.extend(["-F", f"message_thread_id={MSG_THREAD_ID}"])
    try:
        subprocess.run(cmd, timeout=60)
    except Exception as e:
        print(f"Send document error: {e}")

def send_photo(filepath, caption="", reply_markup=None, target_chat=None):
    chat = target_chat or CHAT_ID
    if not BOT_TOKEN or not chat or not os.path.exists(filepath):
        return None
    cmd = [
        "curl", "-s",
        "-F", f"chat_id={chat}",
        "-F", f"caption={caption}",
        "-F", "parse_mode=HTML",
        "-F", f"photo=@{filepath}",
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    ]
    if MSG_THREAD_ID and str(MSG_THREAD_ID) != "0":
        cmd.extend(["-F", f"message_thread_id={MSG_THREAD_ID}"])
    if reply_markup:
        cmd.extend(["-F", f"reply_markup={json.dumps(reply_markup)}"])
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return json.loads(res.stdout.decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f"Send photo error: {e}")
        return None

def render_view(chat_id, msg_id, text, markup=None, is_media=False):
    """
    Renders an interactive menu or view.
    If the source message was media (photo/document) or if editMessageText fails,
    it automatically falls back to send_message so the user is never left hanging.
    """
    if is_media:
        return send_message(text, reply_markup=markup, target_chat=chat_id)
    res = edit_message_text(chat_id, msg_id, text, reply_markup=markup)
    if not res or not res.get("ok"):
        return send_message(text, reply_markup=markup, target_chat=chat_id)
    return res

# ----------------- SYSTEM METRICS HELPERS -----------------
def make_progress_bar(pct, length=10):
    filled = min(length, max(0, int(round((pct / 100.0) * length))))
    empty = length - filled
    return "■" * filled + "□" * empty

def get_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return round(int(f.read().strip()) / 1000, 1)
    except:
        return 0.0

def get_uptime_str():
    try:
        with open("/proc/uptime", "r") as f:
            sec = int(float(f.readline().split()[0]))
        d, rem = divmod(sec, 86400)
        h, rem = divmod(rem, 3600)
        m, _ = divmod(rem, 60)
        if d > 0:
            return f"{d} hari {h} jam {m} menit"
        elif h > 0:
            return f"{h} jam {m} menit"
        else:
            return f"{m} menit"
    except:
        return "Unknown"

def get_ram_info():
    total = avail = 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "MemTotal:" in line:
                    total = int(line.split()[1])
                elif "MemAvailable:" in line:
                    avail = int(line.split()[1])
        used = total - avail
        pct = round((used / total) * 100, 1) if total else 0
        return round(used / 1024), round(total / 1024), pct
    except:
        return 0, 0, 0

def get_public_ip():
    providers = ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]
    for url in providers:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                ip = resp.read().decode("utf-8").strip()
                if ip and len(ip) < 45:
                    return ip
        except:
            continue
    return "N/A"

def get_ping():
    try:
        out = subprocess.check_output("ping -c 1 -W 2 1.1.1.1 2>/dev/null", shell=True).decode()
        for line in out.splitlines():
            if "time=" in line:
                idx = line.find("time=")
                return line[idx+5:].split()[0] + " ms"
    except:
        pass
    return "RTO"

def get_dhcp_clients():
    clients = []
    blocked = load_blocked_macs()
    if os.path.exists("/tmp/dhcp.leases"):
        try:
            with open("/tmp/dhcp.leases", "r") as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) >= 4:
                        mac = p[1].lower()
                        ip = p[2]
                        name = p[3]
                        if name == "*":
                            name = f"Device-{ip.split('.')[-1]}"
                        clients.append({
                            "mac": mac,
                            "ip": ip,
                            "name": name,
                            "blocked": mac in blocked
                        })
        except:
            pass
    return clients

def get_modem_info():
    info = {"operator": "N/A", "rat": "4G LTE", "signal": "N/A", "dl_rate": "0 KB/s", "ul_rate": "0 KB/s", "dl_total": "0 GB", "ul_total": "0 GB"}
    try:
        req = urllib.request.urlopen("http://192.168.8.1/api/webserver/SesTokInfo", timeout=2)
        root = ET.fromstring(req.read().decode("utf-8"))
        ses = root.findtext("SesInfo", "")
        tok = root.findtext("TokInfo", "")
        headers = {"Cookie": ses, "__RequestVerificationToken": tok}
        
        # PLMN
        try:
            r = urllib.request.Request("http://192.168.8.1/api/net/current-plmn", headers=headers)
            with urllib.request.urlopen(r, timeout=2) as resp:
                proot = ET.fromstring(resp.read().decode("utf-8"))
                info["operator"] = proot.findtext("FullName") or proot.findtext("ShortName") or "Telkomsel"
        except: pass

        # Status
        try:
            r = urllib.request.Request("http://192.168.8.1/api/monitoring/status", headers=headers)
            with urllib.request.urlopen(r, timeout=2) as resp:
                sroot = ET.fromstring(resp.read().decode("utf-8"))
                sig = sroot.findtext("SignalIcon", "5")
                info["signal"] = f"{sig}/5 bar"
        except: pass

        # Traffic
        try:
            r = urllib.request.Request("http://192.168.8.1/api/monitoring/traffic-statistics", headers=headers)
            with urllib.request.urlopen(r, timeout=2) as resp:
                troot = ET.fromstring(resp.read().decode("utf-8"))
                dl_rate = int(troot.findtext("CurrentDownloadRate", "0"))
                ul_rate = int(troot.findtext("CurrentUploadRate", "0"))
                dl_tot = int(troot.findtext("TotalDownload", "0"))
                ul_tot = int(troot.findtext("TotalUpload", "0"))
                info["dl_rate"] = f"{round(dl_rate / 1024, 1)} KB/s"
                info["ul_rate"] = f"{round(ul_rate / 1024, 1)} KB/s"
                info["dl_total"] = f"{round(dl_tot / (1024**3), 2)} GB"
                info["ul_total"] = f"{round(ul_tot / (1024**3), 2)} GB"
        except: pass
    except Exception as e:
        info["operator"] = f"Tidak terhubung ({e})"
    return info

def get_sms_unread_count():
    try:
        req = urllib.request.urlopen("http://192.168.8.1/api/sms/sms-count", timeout=2)
        root = ET.fromstring(req.read().decode("utf-8"))
        unread = int(root.findtext("LocalUnread", "0"))
        inbox = int(root.findtext("LocalInbox", "0"))
        return unread, inbox
    except:
        return 0, 0

def get_sms_list(limit=3):
    messages = []
    try:
        req = urllib.request.urlopen("http://192.168.8.1/api/webserver/SesTokInfo", timeout=2)
        root = ET.fromstring(req.read().decode("utf-8"))
        ses = root.findtext("SesInfo", "")
        tok = root.findtext("TokInfo", "")
        headers = {
            "Cookie": ses,
            "__RequestVerificationToken": tok,
            "Content-Type": "application/xml"
        }
        payload = f"<request><pageindex>1</pageindex><readcount>{limit}</readcount><boxtype>1</boxtype><sorttype>0</sorttype><ascending>0</ascending><unreadpreferred>0</unreadpreferred></request>"
        req2 = urllib.request.Request("http://192.168.8.1/api/sms/sms-list", data=payload.encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req2, timeout=3) as resp:
            sroot = ET.fromstring(resp.read().decode("utf-8"))
            for m in sroot.findall(".//Message"):
                phone = m.findtext("Phone", "Unknown")
                date = m.findtext("Date", "")
                content = m.findtext("Content", "")
                messages.append({"phone": phone, "date": date, "content": content})
    except Exception as e:
        print(f"Error fetching SMS list: {e}")
    return messages

# ----------------- VIEW GENERATORS (TEXT & INLINE KEYBOARD) -----------------
def view_main_menu():
    temp = get_temp()
    used_mb, total_mb, pct = get_ram_info()
    uptime = get_uptime_str()
    temp_icon = "🔥" if temp >= 70 else ("⚡" if temp >= 60 else "❄️")

    text = (
        "🤖 <b>SRPCOM OPENWRT CONTROL CENTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Selamat datang di Panel Kontrol STB OpenWrt!\n"
        "Silakan pilih menu di bawah ini untuk mengelola router secara interaktif:\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏠 <b>Router Host</b> : <code>{HOSTNAME}</code>\n"
        f"⏱ <b>Waktu Aktif</b> : {uptime}\n"
        f"{temp_icon} <b>Suhu CPU</b> : <b>{temp}°C</b>\n"
        f"🧠 <b>Pemakaian RAM</b> : {used_mb}MB / {total_mb}MB (<b>{pct}%</b>)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Sentuh tombol di bawah untuk navigasi instan:</i>\n"
        "👤 <i>by SRPCOM</i>"
    )

    markup = {
        "inline_keyboard": [
            [
                {"text": "📊 Status STB", "callback_data": "menu_status"},
                {"text": "📈 Pemakaian Kuota", "callback_data": "menu_vnstat"}
            ],
            [
                {"text": "🚀 Speedtest", "callback_data": "menu_speedtest"},
                {"text": "👥 Daftar Klien", "callback_data": "menu_clients"}
            ],
            [
                {"text": "📶 Info Modem", "callback_data": "menu_modem"},
                {"text": "📩 Pesan SMS", "callback_data": "menu_sms"}
            ],
            [
                {"text": "🧹 Bersihkan RAM", "callback_data": "menu_clearcache"},
                {"text": "🛡 Daftar Blokir", "callback_data": "menu_blocked"}
            ],
            [
                {"text": "💾 Backup Config", "callback_data": "menu_backup"},
                {"text": "🔄 Restart STB", "callback_data": "menu_reboot_ask"}
            ],
            [
                {"text": "🔄 Refresh Menu", "callback_data": "menu_main"}
            ]
        ]
    }
    return text, markup

def view_status():
    temp = get_temp()
    used_mb, total_mb, pct = get_ram_info()
    uptime = get_uptime_str()
    ip = get_public_ip()
    ping = get_ping()
    bar = make_progress_bar(pct)

    leases = 0
    if os.path.exists("/tmp/dhcp.leases"):
        try:
            with open("/tmp/dhcp.leases") as f:
                leases = sum(1 for l in f if l.strip())
        except:
            pass

    temp_status = "Tinggi (Perlu Kipas)" if temp >= 70 else ("Sedang" if temp >= 60 else "Dingin & Aman")
    temp_icon = "🔥" if temp >= 70 else ("⚡" if temp >= 60 else "❄️")
    now_str = time.strftime("%H:%M:%S WIB")

    text = (
        "📊 <b>STATUS SISTEM & JARINGAN STB</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏠 <b>Router Host</b> : <code>{HOSTNAME}</code>\n"
        f"⏱ <b>Waktu Aktif</b> : {uptime}\n"
        f"{temp_icon} <b>Suhu CPU</b> : <b>{temp}°C</b> <i>({temp_status})</i>\n"
        f"🧠 <b>Memori RAM</b> : {used_mb}MB / {total_mb}MB (<b>{pct}%</b>)\n"
        f"   └ <code>[{bar}]</code>\n"
        f"🌐 <b>IP Publik</b> : <code>{ip}</code>\n"
        f"📶 <b>Ping (1.1.1.1)</b> : <b>{ping}</b>\n"
        f"📱 <b>Klien Aktif</b> : <b>{leases} perangkat</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>Diperbarui: {now_str}</i>\n"
        "👤 <i>by SRPCOM</i>"
    )

    markup = {
        "inline_keyboard": [
            [
                {"text": "🔄 Refresh Status", "callback_data": "menu_status"},
                {"text": "📈 Pemakaian Kuota", "callback_data": "menu_vnstat"}
            ],
            [
                {"text": "🚀 Speedtest", "callback_data": "menu_speedtest"},
                {"text": "🧹 Bersihkan RAM", "callback_data": "menu_clearcache"}
            ],
            [
                {"text": "👥 Kelola Klien", "callback_data": "menu_clients"},
                {"text": "📶 Info Modem", "callback_data": "menu_modem"}
            ],
            [
                {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }
    return text, markup

def view_clients():
    clients = get_dhcp_clients()
    now_str = time.strftime("%H:%M:%S WIB")

    if not clients:
        text = (
            "📱 <b>DAFTAR KLIEN AKTIF</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️ <i>Tidak ada perangkat terhubung di tabel DHCP leases saat ini.</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>Diperiksa: {now_str}</i>\n"
            "👤 <i>by SRPCOM</i>"
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Refresh Klien", "callback_data": "menu_clients"},
                    {"text": "🛡 Daftar Blokir", "callback_data": "menu_blocked"}
                ],
                [
                    {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
                ]
            ]
        }
        return text, markup

    lines = []
    keyboard = []
    btn_row = []

    for idx, c in enumerate(clients, 1):
        name = c["name"]
        mac = c["mac"]
        ip = c["ip"]
        is_blocked = c["blocked"]
        tag = "🚫 [DIBLOKIR]" if is_blocked else "✅"
        lines.append(f"{idx}. {tag} <b>{name}</b>\n   └ IP: <code>{ip}</code> | MAC: <code>{mac}</code>")

        short_name = name[:10] + "…" if len(name) > 10 else name
        if is_blocked:
            btn_text = f"✅ Buka: {short_name}"
            btn_data = f"unblock_{mac}"
        else:
            btn_text = f"🚫 Blokir: {short_name}"
            btn_data = f"block_{mac}"

        btn_row.append({"text": btn_text, "callback_data": btn_data})
        if len(btn_row) == 2:
            keyboard.append(btn_row)
            btn_row = []

    if btn_row:
        keyboard.append(btn_row)

    text = (
        f"📱 <b>DAFTAR KLIEN AKTIF ({len(clients)})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n" +
        "\n".join(lines) +
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Sentuh tombol perangkat di bawah untuk blokir/buka blokir:</i>\n"
        f"🕒 <i>Diperbarui: {now_str}</i>\n"
        "👤 <i>by SRPCOM</i>"
    )

    keyboard.append([
        {"text": "🔄 Refresh Klien", "callback_data": "menu_clients"},
        {"text": "🛡 Daftar Blokir", "callback_data": "menu_blocked"}
    ])
    keyboard.append([
        {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
    ])

    return text, {"inline_keyboard": keyboard}

def view_blocked():
    blocked = load_blocked_macs()
    now_str = time.strftime("%H:%M:%S WIB")

    if not blocked:
        text = (
            "🛡 <b>DAFTAR PERANGKAT DIBLOKIR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✅ <i>Semua perangkat memiliki akses penuh. Tidak ada MAC yang diblokir saat ini.</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>Diperiksa: {now_str}</i>\n"
            "👤 <i>by SRPCOM</i>"
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "👥 Kelola Klien", "callback_data": "menu_clients"},
                    {"text": "🔄 Refresh", "callback_data": "menu_blocked"}
                ],
                [
                    {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
                ]
            ]
        }
        return text, markup

    lines = []
    keyboard = []
    btn_row = []

    for idx, (mac, data) in enumerate(blocked.items(), 1):
        name = data.get("name", "Unknown") if isinstance(data, dict) else "Blocked"
        t = data.get("time", "-") if isinstance(data, dict) else "-"
        lines.append(f"{idx}. 🚫 <b>{name}</b>\n   └ MAC: <code>{mac}</code> <i>({t})</i>")

        short_name = name[:10] + "…" if len(name) > 10 else name
        btn = {"text": f"✅ Buka: {short_name}", "callback_data": f"unblock_{mac}"}
        btn_row.append(btn)
        if len(btn_row) == 2:
            keyboard.append(btn_row)
            btn_row = []

    if btn_row:
        keyboard.append(btn_row)

    text = (
        f"🛡 <b>DAFTAR PERANGKAT DIBLOKIR ({len(blocked)})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n" +
        "\n".join(lines) +
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Sentuh tombol di bawah untuk membuka blokir secara instan:</i>\n"
        f"🕒 <i>Diperbarui: {now_str}</i>\n"
        "👤 <i>by SRPCOM</i>"
    )

    keyboard.append([
        {"text": "🔄 Refresh Blokir", "callback_data": "menu_blocked"},
        {"text": "👥 Daftar Klien", "callback_data": "menu_clients"}
    ])
    keyboard.append([
        {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
    ])

    return text, {"inline_keyboard": keyboard}

def view_modem():
    info = get_modem_info()
    now_str = time.strftime("%H:%M:%S WIB")

    text = (
        "📶 <b>STATUS MODEM 4G LTE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Operator</b> : <b>{info['operator']}</b>\n"
        f"📶 <b>Sinyal</b> : <b>{info['signal']}</b> ({info['rat']})\n"
        f"📥 <b>Speed Download</b> : <b>{info['dl_rate']}</b>\n"
        f"📤 <b>Speed Upload</b> : <b>{info['ul_rate']}</b>\n"
        f"📊 <b>Total Download</b> : {info['dl_total']}\n"
        f"📊 <b>Total Upload</b> : {info['ul_total']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>Diperbarui: {now_str}</i>\n"
        "👤 <i>by SRPCOM</i>"
    )

    markup = {
        "inline_keyboard": [
            [
                {"text": "🔄 Refresh Modem", "callback_data": "menu_modem"},
                {"text": "📩 Cek SMS", "callback_data": "menu_sms"}
            ],
            [
                {"text": "📊 Status STB", "callback_data": "menu_status"},
                {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }
    return text, markup

def view_sms():
    unread, inbox = get_sms_unread_count()
    status_icon = "📩" if unread > 0 else "📭"
    now_str = time.strftime("%H:%M:%S WIB")
    msg_items = get_sms_list(limit=3)

    body = [
        f"{status_icon} <b>STATUS & KOTAK MASUK SMS MODEM</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📬 <b>Total SMS Disimpan</b> : {inbox} pesan",
        f"🆕 <b>SMS Belum Dibaca</b> : <b>{unread} pesan</b>",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    if msg_items:
        body.append("<b>📩 Pesan Terbaru:</b>")
        for i, m in enumerate(msg_items, 1):
            phone = m["phone"]
            date = m["date"]
            content = m["content"].replace("<", "&lt;").replace(">", "&gt;")
            if len(content) > 120:
                content = content[:120] + "…"
            body.append(f"<b>{i}. Dari:</b> <code>{phone}</code> <i>({date})</i>\n   └ <i>{content}</i>")
        body.append("━━━━━━━━━━━━━━━━━━━━")
    else:
        body.append("💡 <i>Buka LuCI → Modem → SMS Tool untuk membaca atau mengirim SMS lengkap.</i>\n━━━━━━━━━━━━━━━━━━━━")

    body.append(f"🕒 <i>Diperiksa: {now_str}</i>\n👤 <i>by SRPCOM</i>")
    text = "\n".join(body)

    markup = {
        "inline_keyboard": [
            [
                {"text": "🔄 Refresh SMS", "callback_data": "menu_sms"},
                {"text": "📶 Info Modem", "callback_data": "menu_modem"}
            ],
            [
                {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }
    return text, markup

def view_clearcache():
    b_used, b_tot, _ = get_ram_info()
    subprocess.run("sync && echo 3 > /proc/sys/vm/drop_caches", shell=True)
    time.sleep(0.5)
    a_used, a_tot, pct = get_ram_info()
    freed = max(0, b_used - a_used)
    bar = make_progress_bar(pct)
    now_str = time.strftime("%H:%M:%S WIB")

    text = (
        "🧹 <b>PEMBERSIHAN MEMORI RAM SELESAI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>RAM Sebelum</b> : {b_used} MB\n"
        f"📈 <b>RAM Sesudah</b> : <b>{a_used} MB</b> / {a_tot} MB (<b>{pct}%</b>)\n"
        f"   └ <code>[{bar}]</code>\n"
        f"✨ <b>Ruang Dibebaskan</b> : <b>+{freed} MB</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>Selesai pada: {now_str}</i>\n"
        "👤 <i>by SRPCOM</i>"
    )

    markup = {
        "inline_keyboard": [
            [
                {"text": "🧹 Bersihkan Lagi", "callback_data": "menu_clearcache"},
                {"text": "📊 Status STB", "callback_data": "menu_status"}
            ],
            [
                {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }
    return text, markup

def view_reboot_ask():
    uptime = get_uptime_str()
    text = (
        "⚠️ <b>KONFIRMASI RESTART STB</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Apakah Anda yakin ingin me-restart router <code>{HOSTNAME}</code> sekarang?\n\n"
        f"⏱ <b>Uptime saat ini:</b> {uptime}\n"
        "⚠️ <i>Koneksi internet dan bot akan offline selama 1-2 menit hingga proses restart selesai.</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <i>by SRPCOM</i>"
    )
    markup = {
        "inline_keyboard": [
            [
                {"text": "⚠️ Ya, Restart Sekarang!", "callback_data": "confirm_reboot"}
            ],
            [
                {"text": "❌ Batal", "callback_data": "menu_main"}
            ]
        ]
    }
    return text, markup

# ----------------- VNSTAT & VNSTATI HELPERS -----------------
def format_bytes(b):
    if b >= 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024 * 1024):.2f} GB"
    elif b >= 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    elif b >= 1024:
        return f"{b / 1024:.0f} KB"
    else:
        return f"{b} B"

def get_vnstat_data(selected_iface=None):
    try:
        out = subprocess.check_output("vnstat --json 2>/dev/null", shell=True).decode()
        data = json.loads(out)
        ifaces = data.get("interfaces", [])
        if not ifaces:
            return None, "Database vnStat kosong atau daemon belum aktif."

        chosen = None
        if selected_iface:
            for ifc in ifaces:
                if ifc.get("name") == selected_iface:
                    chosen = ifc
                    break

        if not chosen:
            # Prefer eth1 if it has day traffic, otherwise br-lan
            for ifc in ifaces:
                if ifc.get("name") == "eth1" and len(ifc.get("traffic", {}).get("day", [])) > 0:
                    chosen = ifc
                    break
            if not chosen:
                for ifc in ifaces:
                    if ifc.get("name") == "br-lan":
                        chosen = ifc
                        break
            if not chosen and len(ifaces) > 0:
                chosen = ifaces[0]

        if not chosen:
            return None, "Interface tidak ditemukan di database vnStat."

        ifname = chosen.get("name", "br-lan")
        traffic = chosen.get("traffic", {})

        is_lan = ifname.startswith("br-") or ifname.startswith("lan")

        def parse_entry(entry):
            if not entry:
                return 0, 0, 0
            rx = entry.get("rx", 0)
            tx = entry.get("tx", 0)
            dl = tx if is_lan else rx
            ul = rx if is_lan else tx
            return dl, ul, (dl + ul)

        days = traffic.get("day", [])
        months = traffic.get("month", [])

        now = time.localtime()
        cur_y = now.tm_year
        cur_m = now.tm_mon
        cur_d = now.tm_mday

        yest_time = time.localtime(time.time() - 86400)
        yest_y = yest_time.tm_year
        yest_m = yest_time.tm_mon
        yest_d = yest_time.tm_mday

        today_entry = next((d for d in days if d.get("date", {}).get("year") == cur_y and d.get("date", {}).get("month") == cur_m and d.get("date", {}).get("day") == cur_d), None)
        yest_entry = next((d for d in days if d.get("date", {}).get("year") == yest_y and d.get("date", {}).get("month") == yest_m and d.get("date", {}).get("day") == yest_d), None)
        cur_month_entry = next((m for m in months if m.get("date", {}).get("year") == cur_y and m.get("date", {}).get("month") == cur_m), None)

        today_dl, today_ul, today_tot = parse_entry(today_entry)
        yest_dl, yest_ul, yest_tot = parse_entry(yest_entry)
        month_dl, month_ul, month_tot = parse_entry(cur_month_entry)

        tot_raw = traffic.get("total", {})
        tot_dl, tot_ul, tot_sum = parse_entry(tot_raw)

        avail_ifaces = [i.get("name") for i in ifaces if i.get("name")]

        return {
            "ifname": ifname,
            "avail_ifaces": avail_ifaces,
            "today": {"dl": today_dl, "ul": today_ul, "total": today_tot},
            "yesterday": {"dl": yest_dl, "ul": yest_ul, "total": yest_tot},
            "month": {"dl": month_dl, "ul": month_ul, "total": month_tot},
            "total": {"dl": tot_dl, "ul": tot_ul, "total": tot_sum}
        }, None
    except Exception as e:
        return None, str(e)

def view_vnstat(selected_iface=None):
    data, err = get_vnstat_data(selected_iface)
    if err or not data:
        text = (
            "📊 <b>MONITORING PEMAKAIAN KUOTA (vnStat)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>Gagal membaca statistik vnStat:</b>\n<code>{err}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <i>by SRPCOM</i>"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "🔄 Coba Lagi", "callback_data": "menu_vnstat"}],
                [{"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
            ]
        }
        return text, markup

    ifname = data["ifname"]
    today = data["today"]
    yest = data["yesterday"]
    month = data["month"]
    tot = data["total"]
    now_str = time.strftime("%H:%M:%S WIB")

    if_label = "WAN Modem (eth1)" if ifname == "eth1" else f"LAN Client ({ifname})"

    text = (
        "📊 <b>MONITORING PEMAKAIAN KUOTA INTERNET</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Interface Monitor</b> : <code>{ifname}</code> <i>({if_label})</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📅 <b>HARI INI:</b>\n"
        f"  📥 Download : <b>{format_bytes(today['dl'])}</b>\n"
        f"  📤 Upload   : <b>{format_bytes(today['ul'])}</b>\n"
        f"  🔄 <b>Total Hari Ini</b> : <b>{format_bytes(today['total'])}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📅 <b>KEMARIN:</b>\n"
        f"  📥 Download : <b>{format_bytes(yest['dl'])}</b>\n"
        f"  📤 Upload   : <b>{format_bytes(yest['ul'])}</b>\n"
        f"  🔄 <b>Total Kemarin</b> : <b>{format_bytes(yest['total'])}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📆 <b>BULAN INI:</b>\n"
        f"  📥 Download : <b>{format_bytes(month['dl'])}</b>\n"
        f"  📤 Upload   : <b>{format_bytes(month['ul'])}</b>\n"
        f"  🔄 <b>Total Bulan Ini</b> : <b>{format_bytes(month['total'])}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Akumulasi Total</b> : <b>{format_bytes(tot['total'])}</b>\n"
        f"🕒 <i>Diperbarui: {now_str}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📈 <i>Sentuh tombol di bawah untuk kirim grafik langsung ke chat:</i>\n"
        "👤 <i>by SRPCOM</i>"
    )

    markup = {
        "inline_keyboard": [
            [
                {"text": "📊 Grafik Harian", "callback_data": f"vnstat_img_daily_{ifname}"},
                {"text": "📅 Grafik Bulanan", "callback_data": f"vnstat_img_monthly_{ifname}"}
            ],
            [
                {"text": "⏱ Grafik 24 Jam", "callback_data": f"vnstat_img_hourly_{ifname}"},
                {"text": "🖼 Rekap Ringkas", "callback_data": f"vnstat_img_summary_{ifname}"}
            ]
        ]
    }

    avail = data.get("avail_ifaces", [])
    if len(avail) > 1:
        other_iface = "eth1" if ifname == "br-lan" else "br-lan"
        if other_iface in avail:
            markup["inline_keyboard"].append([
                {"text": f"🔀 Ganti ke Interface {other_iface}", "callback_data": f"vnstat_view_{other_iface}"}
            ])

    markup["inline_keyboard"].append([
        {"text": "🔄 Refresh Data", "callback_data": f"vnstat_view_{ifname}"},
        {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
    ])

    return text, markup

def run_vnstat_graph_thread(graph_type, iface, target_chat):
    img_path = f"/tmp/vnstat_{graph_type}_{int(time.time() * 1000)}.png"

    flag = "-vs"
    title = "Rekap Grafik & Tabel"
    if graph_type == "daily":
        flag = "-d"
        title = "Grafik Kuota Harian"
    elif graph_type == "monthly":
        flag = "-m"
        title = "Grafik Kuota Bulanan"
    elif graph_type == "hourly":
        flag = "-hg"
        title = "Grafik Bandwidth 24 Jam"
    elif graph_type == "summary":
        flag = "-vs"
        title = "Rekap Grafik & Tabel"

    cmd = f"vnstati {flag} -i {iface} -o {img_path}"
    subprocess.run(cmd, shell=True)

    if os.path.exists(img_path):
        now_str = time.strftime("%H:%M:%S WIB")
        caption = (
            f"📈 <b>{title.upper()} ({iface})</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>Dibuat: {now_str}</i>\n"
            "👤 <i>by SRPCOM</i>"
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "📊 Harian", "callback_data": f"vnstat_img_daily_{iface}"},
                    {"text": "📅 Bulanan", "callback_data": f"vnstat_img_monthly_{iface}"},
                    {"text": "⏱ 24 Jam", "callback_data": f"vnstat_img_hourly_{iface}"}
                ],
                [
                    {"text": "📋 Ringkasan Kuota", "callback_data": f"vnstat_view_{iface}"},
                    {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
                ]
            ]
        }
        send_photo(img_path, caption=caption, reply_markup=markup, target_chat=target_chat)
        try:
            os.remove(img_path)
        except:
            pass
    else:
        markup = {
            "inline_keyboard": [
                [{"text": "📋 Ringkasan Kuota", "callback_data": f"vnstat_view_{iface}"}, {"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
            ]
        }
        send_message(
            f"❌ <b>Gagal menghasilkan grafik {title} untuk interface {iface}.</b>\n"
            "Pastikan database vnStat memiliki catatan traffic untuk interface ini.",
            reply_markup=markup,
            target_chat=target_chat
        )

# ----------------- ASYNC WORKERS -----------------
def run_speedtest_thread(target_chat, message_id=None):
    progress_text = (
        "⏳ <b>Memulai Speedtest...</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Mohon tunggu sekitar 15-25 detik selagi menguji kecepatan download & upload langsung dari STB."
    )
    if message_id:
        render_view(target_chat, message_id, progress_text)
    else:
        send_message(progress_text, target_chat=target_chat)
    
    data = None
    # 1. Try Ookla Speedtest (auto server)
    try:
        out = subprocess.check_output(
            "/usr/bin/speedtest --accept-license --accept-gdpr --format=json 2>/dev/null",
            shell=True, timeout=35
        ).decode()
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    d = json.loads(line)
                    if d.get("type") == "result":
                        data = d
                        break
                except:
                    pass
    except Exception as e:
        print(f"Ookla auto failed: {e}")

    # 2. If auto failed, try CBN server (12807)
    if not data:
        try:
            out = subprocess.check_output(
                "/usr/bin/speedtest --accept-license --accept-gdpr -s 12807 --format=json 2>/dev/null",
                shell=True, timeout=35
            ).decode()
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        d = json.loads(line)
                        if d.get("type") == "result":
                            data = d
                            break
                    except:
                        pass
        except Exception as e:
            print(f"Ookla 12807 failed: {e}")

    now_str = time.strftime("%H:%M:%S WIB")

    # 3. If Ookla returned result, format and send
    if data:
        ping = data.get("ping", {}).get("latency", 0)
        jitter = data.get("ping", {}).get("jitter", 0)
        dl_bytes = data.get("download", {}).get("bandwidth", 0)
        ul_bytes = data.get("upload", {}).get("bandwidth", 0)
        dl_mbps = round(dl_bytes * 8 / 1000000, 2)
        ul_mbps = round(ul_bytes * 8 / 1000000, 2)
        isp = data.get("isp", "Unknown ISP")
        server_info = data.get("server", {})
        srv_name = server_info.get("name", "Unknown Server")
        srv_loc = server_info.get("location", "")
        srv_str = f"{srv_name} ({srv_loc})" if srv_loc else srv_name
        res_url = data.get("result", {}).get("url", "")
        ext_ip = data.get("interface", {}).get("externalIp", "")

        msg = (
            "🚀 <b>HASIL SPEEDTEST (Ookla)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 <b>Download</b> : <b>{dl_mbps} Mbps</b>\n"
            f"📤 <b>Upload</b>   : <b>{ul_mbps} Mbps</b>\n"
            f"📶 <b>Ping</b>     : <b>{round(ping, 1)} ms</b> (Jitter: {round(jitter, 1)} ms)\n"
            f"🏢 <b>Server</b>   : {srv_str}\n"
            f"🌐 <b>ISP</b>      : {isp} ({ext_ip})\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>Diuji: {now_str}</i>\n"
            "👤 <i>by SRPCOM</i>"
        )
        
        btn_rows = [
            [
                {"text": "🚀 Uji Kecepatan Lagi", "callback_data": "menu_speedtest"},
                {"text": "📊 Status STB", "callback_data": "menu_status"}
            ]
        ]
        if res_url:
            btn_rows.append([{"text": "🌐 Lihat di Speedtest.net", "url": res_url}])
        btn_rows.append([{"text": "🏠 Menu Utama", "callback_data": "menu_main"}])

        markup = {"inline_keyboard": btn_rows}
        if message_id:
            render_view(target_chat, message_id, msg, markup)
        else:
            send_message(msg, markup, target_chat=target_chat)
        return

    # 4. Fallback to Cloudflare CDN Download Test
    try:
        ping_val = get_ping()
        pub_ip = get_public_ip()
        url = "https://speed.cloudflare.com/__down?bytes=10000000"
        t0 = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
        dur = max(0.1, time.time() - t0)
        dl_mbps = round((len(content) * 8) / (dur * 1000000), 2)
        
        msg = (
            "🚀 <b>HASIL SPEEDTEST (Cloudflare CDN)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 <b>Download</b> : <b>{dl_mbps} Mbps</b>\n"
            f"📶 <b>Ping</b>     : <b>{ping_val}</b>\n"
            f"🏢 <b>Server</b>   : Cloudflare Anycast CDN\n"
            f"🌐 <b>IP Publik</b> : <code>{pub_ip}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>(Fallback CDN aktif otomatis karena port Ookla terlimit oleh proxy/tun)</i>\n"
            f"🕒 <i>Diuji: {now_str}</i>\n"
            "👤 <i>by SRPCOM</i>"
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Uji Lagi", "callback_data": "menu_speedtest"},
                    {"text": "📊 Status STB", "callback_data": "menu_status"}
                ],
                [
                    {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
                ]
            ]
        }
        if message_id:
            render_view(target_chat, message_id, msg, markup)
        else:
            send_message(msg, markup, target_chat=target_chat)
    except Exception as e:
        err_msg = f"❌ <b>Pengujian Gagal:</b> {e}"
        markup = {"inline_keyboard": [[{"text": "🏠 Menu Utama", "callback_data": "menu_main"}]]}
        if message_id:
            render_view(target_chat, message_id, err_msg, markup)
        else:
            send_message(err_msg, markup, target_chat=target_chat)

def run_backup_thread(target_chat, message_id=None):
    progress_text = "⏳ <i>Sedang membuat file backup konfigurasi OpenWrt...</i>"
    if message_id:
        render_view(target_chat, message_id, progress_text)
    else:
        send_message(progress_text, target_chat=target_chat)

    backup_file = f"/tmp/backup-{HOSTNAME}-{time.strftime('%Y%m%d-%H%M')}.tar.gz"
    res = subprocess.run(f"sysupgrade -b {backup_file} 2>&1", shell=True)
    if os.path.exists(backup_file):
        send_document(backup_file, caption=f"💾 <b>Backup Konfigurasi {HOSTNAME}</b>\nTanggal: {time.strftime('%Y-%m-%d %H:%M:%S')}\n👤 <i>by SRPCOM</i>", target_chat=target_chat)
        subprocess.run(f"rm -f {backup_file}", shell=True)
        markup = {
            "inline_keyboard": [
                [
                    {"text": "💾 Buat Backup Baru", "callback_data": "menu_backup"},
                    {"text": "📊 Status STB", "callback_data": "menu_status"}
                ],
                [
                    {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
                ]
            ]
        }
        send_message("✅ <b>Backup Konfigurasi Berhasil Dibuat &amp; Dikirim!</b>\nSimpan file ini untuk me-restore router sewaktu-waktu.", reply_markup=markup, target_chat=target_chat)
    else:
        markup = {"inline_keyboard": [[{"text": "🏠 Menu Utama", "callback_data": "menu_main"}]]}
        send_message("❌ <b>Gagal membuat backup konfigurasi.</b>", reply_markup=markup, target_chat=target_chat)

# ----------------- BACKGROUND MONITOR THREAD -----------------
def background_monitor():
    last_temp_alert = 0
    last_ip = ""
    last_unread = 0

    time.sleep(3)
    pub_ip = get_public_ip()
    last_ip = pub_ip
    temp = get_temp()
    uptime = get_uptime_str()
    unread, _ = get_sms_unread_count()
    last_unread = unread

    startup_msg = (
        "🚀 <b>STB Online & Siap!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏠 <b>Router</b> : <code>{HOSTNAME}</code>\n"
        f"⏱ <b>Uptime</b> : {uptime}\n"
        f"🌐 <b>IP Publik</b> : <code>{pub_ip}</code>\n"
        f"🌡 <b>Suhu CPU</b> : {temp}°C\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Sentuh tombol di bawah untuk melihat menu kontrol:</i>\n"
        "👤 <i>by SRPCOM</i>"
    )
    startup_markup = {
        "inline_keyboard": [
            [
                {"text": "📊 Status STB", "callback_data": "menu_status"},
                {"text": "🚀 Speedtest", "callback_data": "menu_speedtest"}
            ],
            [
                {"text": "👥 Daftar Klien", "callback_data": "menu_clients"},
                {"text": "🏠 Menu Utama", "callback_data": "menu_main"}
            ]
        ]
    }
    send_message(startup_msg, reply_markup=startup_markup)

    while True:
        try:
            time.sleep(60)

            cur_temp = get_temp()
            now = time.time()
            if cur_temp >= 70.0 and (now - last_temp_alert > 1800):
                last_temp_alert = now
                warn_msg = (
                    "🔥 <b>PERINGATAN SUHU TINGGI (OVERHEAT)!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏠 <b>Router</b> : <code>{HOSTNAME}</code>\n"
                    f"🌡 <b>Suhu STB</b> : <b>{cur_temp}°C</b>\n"
                    "⚠️ <i>Suhu melebihi 70°C. Periksa sirkulasi udara atau kipas pendingin STB Anda!</i>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "👤 <i>by SRPCOM</i>"
                )
                warn_markup = {
                    "inline_keyboard": [
                        [{"text": "📊 Cek Suhu Sekarang", "callback_data": "menu_status"}, {"text": "🧹 Bersihkan RAM", "callback_data": "menu_clearcache"}],
                        [{"text": "⚠️ Restart STB", "callback_data": "menu_reboot_ask"}]
                    ]
                }
                send_message(warn_msg, reply_markup=warn_markup)

            cur_ip = get_public_ip()
            if cur_ip != "N/A" and last_ip and cur_ip != last_ip:
                ip_msg = (
                    "🌐 <b>IP PUBLIK BERUBAH!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏠 <b>Router</b> : <code>{HOSTNAME}</code>\n"
                    f"🔄 <b>IP Lama</b> : <code>{last_ip}</code>\n"
                    f"✨ <b>IP Baru</b> : <code>{cur_ip}</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "👤 <i>by SRPCOM</i>"
                )
                ip_markup = {
                    "inline_keyboard": [
                        [{"text": "📊 Status STB", "callback_data": "menu_status"}, {"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
                    ]
                }
                send_message(ip_msg, reply_markup=ip_markup)
                last_ip = cur_ip
            elif cur_ip != "N/A":
                last_ip = cur_ip

            cur_unread, _ = get_sms_unread_count()
            if cur_unread > last_unread:
                sms_alert = (
                    "📩 <b>SMS BARU DITERIMA DI MODEM!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"Terdapat <b>{cur_unread}</b> pesan belum dibaca di modem.\n"
                    "Sentuh tombol di bawah untuk membaca pesan langsung.\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "👤 <i>by SRPCOM</i>"
                )
                sms_markup = {
                    "inline_keyboard": [
                        [{"text": "📩 Baca SMS Sekarang", "callback_data": "menu_sms"}, {"text": "📶 Info Modem", "callback_data": "menu_modem"}],
                        [{"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
                    ]
                }
                send_message(sms_alert, reply_markup=sms_markup)
            last_unread = cur_unread

        except Exception as e:
            print(f"Monitor loop error: {e}")

# ----------------- INCOMING MESSAGE & CALLBACK HANDLERS -----------------
def handle_message(msg):
    chat = msg.get("chat", {})
    from_id = str(chat.get("id", ""))
    
    if CHAT_ID and from_id != str(CHAT_ID):
        print(f"Unauthorized message from {from_id}")
        return

    text = msg.get("text", "").strip()
    if not text:
        return

    cmd = text.split()[0].lower()
    args = text.split()[1:]

    if "@" in cmd:
        cmd = cmd.split("@")[0]

    if cmd in ["/start", "/help", "/menu", "/bantuan"]:
        text_out, markup = view_main_menu()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd == "/status":
        text_out, markup = view_status()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd in ["/kuota", "/vnstat", "/bandwidth"]:
        text_out, markup = view_vnstat()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd == "/speedtest":
        threading.Thread(target=run_speedtest_thread, args=(from_id,), daemon=True).start()
    elif cmd == "/clients":
        text_out, markup = view_clients()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd == "/modem":
        text_out, markup = view_modem()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd == "/sms":
        text_out, markup = view_sms()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd == "/clearcache":
        text_out, markup = view_clearcache()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd == "/blocked":
        text_out, markup = view_blocked()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    elif cmd == "/backup":
        threading.Thread(target=run_backup_thread, args=(from_id,), daemon=True).start()
    elif cmd == "/block":
        if args:
            mac = args[0].strip().lower()
            block_mac(mac, name="Manual")
            markup = {
                "inline_keyboard": [
                    [{"text": "✅ Buka Blokir", "callback_data": f"unblock_{mac}"}],
                    [{"text": "🛡 Daftar Blokir", "callback_data": "menu_blocked"}, {"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
                ]
            }
            send_message(f"🛡 <b>Perangkat Berhasil Diblokir!</b>\nMAC: <code>{mac}</code>\n👤 <i>by SRPCOM</i>", reply_markup=markup, target_chat=from_id)
        else:
            send_message("⚠️ Format: <code>/block &lt;MAC&gt;</code>\nContoh: <code>/block c8:09:a8:f3:c7:a8</code>", target_chat=from_id)
    elif cmd == "/unblock":
        if args:
            mac = args[0].strip().lower()
            unblock_mac(mac)
            markup = {
                "inline_keyboard": [
                    [{"text": "🚫 Blokir Kembali", "callback_data": f"block_{mac}"}],
                    [{"text": "👥 Daftar Klien", "callback_data": "menu_clients"}, {"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
                ]
            }
            send_message(f"✅ <b>Blokir Dibuka!</b>\nMAC: <code>{mac}</code>\n👤 <i>by SRPCOM</i>", reply_markup=markup, target_chat=from_id)
        else:
            send_message("⚠️ Format: <code>/unblock &lt;MAC&gt;</code>", target_chat=from_id)
    elif cmd == "/reboot":
        text_out, markup = view_reboot_ask()
        send_message(text_out, reply_markup=markup, target_chat=from_id)
    else:
        # Default fallback: show main interactive menu
        text_out, markup = view_main_menu()
        send_message(text_out, reply_markup=markup, target_chat=from_id)

def handle_callback_query(cq):
    cq_id = cq.get("id")
    data = cq.get("data", "")
    msg = cq.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")
    is_media = ("photo" in msg) or ("document" in msg) or ("video" in msg) or ("text" not in msg)

    if not chat_id:
        return

    if CHAT_ID and str(chat_id) != str(CHAT_ID):
        answer_callback(cq_id, "⛔ Akses tidak diizinkan!", alert=True)
        return

    # Navigation callbacks
    if data in ["menu_main", "cmd_menu"]:
        answer_callback(cq_id, "🏠 Menu Utama")
        text, markup = view_main_menu()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data in ["menu_status", "cmd_status"]:
        answer_callback(cq_id, "🔄 Memperbarui status...")
        text, markup = view_status()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data in ["menu_vnstat", "cmd_vnstat"]:
        answer_callback(cq_id, "📊 Memuat statistik kuota...")
        text, markup = view_vnstat()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data.startswith("vnstat_view_"):
        sel_iface = data[12:].strip()
        answer_callback(cq_id, f"📊 Memuat kuota {sel_iface}...")
        text, markup = view_vnstat(selected_iface=sel_iface)
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data.startswith("vnstat_img_"):
        parts = data.split("_")
        if len(parts) >= 4:
            g_type = parts[2]
            g_iface = "_".join(parts[3:])
            answer_callback(cq_id, f"📈 Membuat grafik {g_type}...")
            threading.Thread(target=run_vnstat_graph_thread, args=(g_type, g_iface, chat_id), daemon=True).start()

    elif data in ["menu_clients", "cmd_clients"]:
        answer_callback(cq_id, "👥 Memuat daftar klien...")
        text, markup = view_clients()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data in ["menu_blocked", "cmd_blocked"]:
        answer_callback(cq_id, "🛡 Memuat daftar blokir...")
        text, markup = view_blocked()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data in ["menu_modem", "cmd_modem"]:
        answer_callback(cq_id, "📶 Memuat info modem...")
        text, markup = view_modem()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data in ["menu_sms", "cmd_sms"]:
        answer_callback(cq_id, "📩 Memeriksa SMS...")
        text, markup = view_sms()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data in ["menu_clearcache", "cmd_clearcache"]:
        answer_callback(cq_id, "🧹 Membersihkan RAM...")
        text, markup = view_clearcache()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data in ["menu_speedtest", "cmd_speedtest"]:
        answer_callback(cq_id, "🚀 Menyiapkan speedtest...")
        target_msg_id = None if is_media else msg_id
        threading.Thread(target=run_speedtest_thread, args=(chat_id, target_msg_id), daemon=True).start()

    elif data in ["menu_backup", "cmd_backup"]:
        answer_callback(cq_id, "💾 Menyiapkan backup...")
        target_msg_id = None if is_media else msg_id
        threading.Thread(target=run_backup_thread, args=(chat_id, target_msg_id), daemon=True).start()

    elif data in ["menu_reboot_ask", "cmd_reboot"]:
        answer_callback(cq_id, "⚠️ Konfirmasi reboot")
        text, markup = view_reboot_ask()
        render_view(chat_id, msg_id, text, markup, is_media=is_media)

    elif data == "confirm_reboot":
        answer_callback(cq_id, "🔄 Me-restart STB...", alert=True)
        reboot_text = (
            "🔄 <b>STB SEDANG ME-RESTART...</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Perangkat <code>{HOSTNAME}</code> sedang memulai ulang sistem.\n"
            "Koneksi internet dan bot akan offline selama 1-2 menit.\n"
            "Bot akan mengirim notifikasi saat sistem kembali aktif.\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <i>by SRPCOM</i>"
        )
        render_view(chat_id, msg_id, reboot_text, None, is_media=is_media)
        time.sleep(1)
        subprocess.run("reboot", shell=True)

    elif data.startswith("block_"):
        mac = data[6:].strip().lower()
        dev_name = "Perangkat"
        for c in get_dhcp_clients():
            if c["mac"] == mac:
                dev_name = c["name"]
                break
        block_mac(mac, name=dev_name)
        answer_callback(cq_id, f"🚫 {dev_name} ({mac}) berhasil diblokir!", alert=True)

        msg_text = msg.get("text", "")
        if "DAFTAR KLIEN" in msg_text:
            text, markup = view_clients()
            render_view(chat_id, msg_id, text, markup, is_media=is_media)
        elif "DAFTAR PERANGKAT DIBLOKIR" in msg_text:
            text, markup = view_blocked()
            render_view(chat_id, msg_id, text, markup, is_media=is_media)
        else:
            new_markup = {
                "inline_keyboard": [
                    [{"text": f"✅ Buka Blokir {dev_name[:12]}", "callback_data": f"unblock_{mac}"}],
                    [{"text": "👥 Daftar Klien", "callback_data": "menu_clients"}, {"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
                ]
            }
            edit_reply_markup(chat_id, msg_id, new_markup)

    elif data.startswith("unblock_"):
        mac = data[8:].strip().lower()
        dev_name = "Perangkat"
        blocked = load_blocked_macs()
        if mac in blocked and isinstance(blocked[mac], dict):
            dev_name = blocked[mac].get("name", "Perangkat")
        unblock_mac(mac)
        answer_callback(cq_id, f"✅ Blokir untuk {dev_name} ({mac}) dibuka!", alert=True)

        msg_text = msg.get("text", "")
        if "DAFTAR PERANGKAT DIBLOKIR" in msg_text:
            text, markup = view_blocked()
            render_view(chat_id, msg_id, text, markup, is_media=is_media)
        elif "DAFTAR KLIEN" in msg_text:
            text, markup = view_clients()
            render_view(chat_id, msg_id, text, markup, is_media=is_media)
        else:
            new_markup = {
                "inline_keyboard": [
                    [{"text": "❌ Blokir Perangkat", "callback_data": f"block_{mac}"}],
                    [{"text": "👥 Daftar Klien", "callback_data": "menu_clients"}, {"text": "🏠 Menu Utama", "callback_data": "menu_main"}]
                ]
            }
            edit_reply_markup(chat_id, msg_id, new_markup)

def main():
    global BOT_TOKEN, CHAT_ID, MSG_THREAD_ID
    print("Starting SRPCOM Telegram Bot Daemon with Interactive Inline Keyboards...")
    init_firewall()

    while not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN atau CHAT_ID belum dikonfigurasi di /etc/config/telegram. Menunggu...")
        time.sleep(10)
        BOT_TOKEN = get_uci("telegram.settings.bot_token")
        CHAT_ID = get_uci("telegram.settings.group_id")
        MSG_THREAD_ID = get_uci("telegram.settings.message_thread_id", "0")

    t = threading.Thread(target=background_monitor, daemon=True)
    t.start()

    offset = 0
    tg_request("deleteWebhook", {"drop_pending_updates": "false"})

    while True:
        try:
            params = {"timeout": 25, "offset": offset}
            res = tg_request("getUpdates", params, timeout=35)
            if res and res.get("ok"):
                for upd in res.get("result", []):
                    offset = upd["update_id"] + 1
                    if "message" in upd:
                        handle_message(upd["message"])
                    elif "callback_query" in upd:
                        handle_callback_query(upd["callback_query"])
            time.sleep(0.5)
        except Exception as e:
            print(f"Polling loop error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
