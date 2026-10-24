const https = require('https');

const cfId = '98090e7ab4f0aad2e08436faf9df00d2.access';
const cfSecret = 'cfast_AVjp5o8pQZRCxbzB82T1jVH2LGYTcnE8sSfNluR69788707c';

function execCmd(cmd) {
  return new Promise((resolve, reject) => {
    const postData = 'cmd=' + encodeURIComponent(cmd);
    const req = https.request({
      hostname: 'stb.srpcom.cloud',
      port: 443,
      path: '/tinyfm/api.php?key=srpcom_secret_api_2026&action=exec',
      method: 'POST',
      headers: {
        'CF-Access-Client-Id': cfId,
        'CF-Access-Client-Secret': cfSecret,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(postData)
      }
    }, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve({ raw: data });
        }
      });
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

const aclJson = JSON.stringify({
  "luci-app-srpcom-telegram": {
    "description": "Grant access for SRPCOM Telegram Control Center",
    "read": {
      "uci": ["telegram"],
      "ubus": {
        "service": ["list"]
      },
      "file": {
        "/etc/init.d/srpcom_bot": ["exec"],
        "/usr/bin/curl": ["exec"]
      }
    },
    "write": {
      "uci": ["telegram"],
      "file": {
        "/etc/init.d/srpcom_bot": ["exec"],
        "/usr/bin/curl": ["exec"]
      }
    }
  }
}, null, 2);

const menuJson = JSON.stringify({
  "admin/services/srpcom_telegram": {
    "title": "SRPCOM Telegram",
    "order": 55,
    "action": {
      "type": "view",
      "path": "srpcom_telegram/settings"
    },
    "depends": {
      "acl": ["luci-app-srpcom-telegram"]
    }
  }
}, null, 2);

const settingsJs = `'use strict';
'require view';
'require form';
'require rpc';
'require fs';
'require ui';
'require uci';

const callServiceList = rpc.declare({
    object: 'service',
    method: 'list',
    params: ['name'],
    expect: { '': {} }
});

function getBotStatus() {
    return L.resolveDefault(callServiceList('srpcom_bot'), {}).then(function(res) {
        var isRunning = false;
        var pid = null;
        try {
            var inst = res['srpcom_bot']['instances']['instance1'];
            isRunning = inst['running'];
            pid = inst['pid'];
        } catch(e) {}
        return { running: isRunning, pid: pid };
    });
}

return view.extend({
    load: function() {
        return Promise.all([
            getBotStatus()
        ]);
    },

    render: function(data) {
        var status = data[0];
        var m, s, o;

        m = new form.Map('telegram', _('SRPCOM Telegram Control Center'),
            _('Kelola token bot dan ID chat Telegram langsung dari antarmuka Web LuCI OpenWrt tanpa perlu membuka terminal.') + '<br />' +
            _('Panduan: Dapatkan Bot Token dari <a href="https://t.me/BotFather" target="_blank">@BotFather</a> dan ID Chat dari <a href="https://t.me/userinfobot" target="_blank">@userinfobot</a>.')
        );

        s = m.section(form.NamedSection, 'settings', 'telegram', _('Status & Kontrol Daemon'));

        o = s.option(form.DummyValue, '_status', _('Status Bot'));
        o.rawhtml = true;
        o.cfgvalue = function() {
            if (status.running) {
                return '<b><span style="color:#2ecc71;">● ' + _('Aktif Berjalan') + '</span></b>' +
                       (status.pid ? ' <small>(PID: ' + status.pid + ')</small>' : '');
            } else {
                return '<b><span style="color:#e74c3c;">● ' + _('Tidak Berjalan (Berhenti)') + '</span></b>';
            }
        };

        o = s.option(form.Button, '_restart', _('Restart Daemon'));
        o.inputtitle = _('Restart Bot');
        o.inputstyle = 'apply';
        o.onclick = function() {
            ui.showModal(_('Memulai Ulang...'), [
                E('p', { 'class': 'spinning' }, _('Sedang me-restart bot daemon...'))
            ]);
            return fs.exec('/etc/init.d/srpcom_bot', ['restart']).then(function(res) {
                ui.hideModal();
                ui.addNotification(null, E('p', _('Daemon bot Telegram berhasil di-restart!')), 'info');
                window.setTimeout(function() { window.location.reload(); }, 1200);
            }).catch(function(e) {
                ui.hideModal();
                ui.addNotification(null, E('p', _('Gagal restart: ') + e.message), 'error');
            });
        };

        s = m.section(form.NamedSection, 'settings', 'telegram', _('Pengaturan Kredensial Bot Telegram'));

        o = s.option(form.Value, 'bot_token', _('Telegram Bot Token'));
        o.password = true;
        o.rmempty = false;
        o.placeholder = 'Contoh: 8673170652:AAEJ7unwLuz...';
        o.description = _('Token bot yang diberikan oleh @BotFather.');

        o = s.option(form.Value, 'group_id', _('Chat ID / Group ID'));
        o.rmempty = false;
        o.placeholder = 'Contoh: 5666536947 atau -100...';
        o.description = _('ID akun Telegram penerima bot atau ID Group.');

        o = s.option(form.Value, 'message_thread_id', _('Message Thread ID (Opsional)'));
        o.placeholder = '0';
        o.description = _('ID Thread jika bot dimasukkan ke dalam group supergroup dengan topik (default: 0).');

        o = s.option(form.Button, '_test', _('Uji Koneksi'));
        o.inputtitle = _('Kirim Pesan Uji Coba');
        o.inputstyle = 'action';
        o.onclick = function() {
            var token = uci.get('telegram', 'settings', 'bot_token') || '';
            var chat_id = uci.get('telegram', 'settings', 'group_id') || '';
            var thread_id = uci.get('telegram', 'settings', 'message_thread_id') || '0';

            if (!token || !chat_id) {
                ui.addNotification(null, E('p', _('Harap isi Bot Token dan Chat ID lalu klik Simpan & Terapkan terlebih dahulu!')), 'warning');
                return;
            }

            ui.showModal(_('Menguji Koneksi...'), [
                E('p', { 'class': 'spinning' }, _('Sedang mengirim pesan tes ke Telegram...'))
            ]);

            var testText = '🤖 <b>TES KONEKSI DARI LUCI OPENWRT</b>%0A━━━━━━━━━━━━━━━━━━━━%0A✅ Berhasil! Pengaturan Bot Token dan Chat ID di Web GUI telah terhubung ke router.%0A👤 <i>by SRPCOM</i>';
            var url = 'https://api.telegram.org/bot' + token + '/sendMessage?chat_id=' + chat_id + '&text=' + testText + '&parse_mode=HTML';
            if (thread_id && thread_id !== '0') {
                url += '&message_thread_id=' + thread_id;
            }

            return fs.exec('/usr/bin/curl', ['-s', url]).then(function(res) {
                ui.hideModal();
                try {
                    var resp = JSON.parse(res.stdout);
                    if (resp.ok) {
                        ui.addNotification(null, E('p', _('✅ Pesan uji coba berhasil terkirim ke Telegram! Periksa chat bot Anda.')), 'info');
                    } else {
                        ui.addNotification(null, E('p', _('❌ Gagal dari Telegram: ') + resp.description), 'error');
                    }
                } catch(e) {
                    ui.addNotification(null, E('p', _('Respon: ') + res.stdout), 'warning');
                }
            }).catch(function(e) {
                ui.hideModal();
                ui.addNotification(null, E('p', _('Gagal mengirim: ') + e.message), 'error');
            });
        };

        m.apply = function() {
            return this.super('apply').then(function() {
                return fs.exec('/etc/init.d/srpcom_bot', ['restart']).then(function() {
                    ui.addNotification(null, E('p', _('Pengaturan disimpan & bot otomatis di-restart!')), 'info');
                });
            });
        };

        return m.render();
    }
});
`;

async function deployLuciGui() {
  console.log('=== Deploying LuCI GUI files to STB ===');
  
  await execCmd('mkdir -p /usr/share/rpcd/acl.d /usr/share/luci/menu.d /www/luci-static/resources/view/srpcom_telegram');

  const b64Acl = Buffer.from(aclJson).toString('base64');
  await execCmd(`echo "${b64Acl}" | base64 -d > /usr/share/rpcd/acl.d/luci-app-srpcom-telegram.json`);
  console.log('Saved /usr/share/rpcd/acl.d/luci-app-srpcom-telegram.json');

  const b64Menu = Buffer.from(menuJson).toString('base64');
  await execCmd(`echo "${b64Menu}" | base64 -d > /usr/share/luci/menu.d/luci-app-srpcom-telegram.json`);
  console.log('Saved /usr/share/luci/menu.d/luci-app-srpcom-telegram.json');

  const b64Settings = Buffer.from(settingsJs).toString('base64');
  await execCmd(`echo "${b64Settings}" | base64 -d > /www/luci-static/resources/view/srpcom_telegram/settings.js`);
  console.log('Saved /www/luci-static/resources/view/srpcom_telegram/settings.js');

  // Reload rpcd and clear LuCI cache
  console.log('Reloading rpcd and clearing LuCI cache...');
  const res = await execCmd('/etc/init.d/rpcd reload; rm -rf /tmp/luci-indexcache /tmp/luci-modulecache; echo "LuCI reloaded!"');
  console.log(res.output || res);
}

deployLuciGui().catch(console.error);
