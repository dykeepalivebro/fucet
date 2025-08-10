import os
import re
import json
import html
import base64
import requests
import threading
from time import sleep
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from colorama import Fore, Style, init
from http.cookies import SimpleCookie
from flask import Flask, send_from_directory, jsonify, request, session, redirect, url_for

init(autoreset=True)
s = requests.Session()
app = Flask(__name__, static_folder='public', static_url_path='')
app.secret_key = os.urandom(24)

log_data = []
data = {
    "username": "Bot Stopped",
    "bot_status": "stopped",
    "current_activity": "Idle",
    "total_bal": "0.00000000",
    "faucet_earn": "0.00000000",
    "ptc_earn": "0.00000000",
    "invest_earn": "0.00000000",
    "reff_earn": "0.00000000",
    "latest_reward": "0.00000000",
    "best_reward": "0.00000000",
    "streak": 0
}
sc_ver = "FAUCET EARNER v5 (Unified)"
host = 'faucetearner.org'

bot_control = threading.Event()

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    log_data.append(full_msg)
    if len(log_data) > 500:
        log_data.pop(0)

class Bot:
    def __init__(self):
        self.best_claim = 0.0
        self.streak = 0
        self.user_agent = ""
        self.is_configured = False

    def config(self):
        if self.is_configured:
            return True
        try:
            with open('config.json', 'r') as f:
                config_data = json.load(f)
            
            if not config_data.get('Cookies') or not config_data.get('User-Agent'):
                log(f"{Fore.RED}❗ Missing 'Cookies' or 'User-Agent' in config.json{Style.RESET_ALL}")
                return False

            self.user_agent = config_data['User-Agent']
            s.headers.update({"User-Agent": self.user_agent})
            s.cookies.clear()
            s.cookies.update({"Cookie": config_data.get("Cookies", "")})
            
            self.is_configured = True
            log(f"{Fore.GREEN}✅ Configuration loaded successfully.{Style.RESET_ALL}")
            return True

        except (FileNotFoundError, json.JSONDecodeError):
            log(f"{Fore.RED}Error reading or parsing config.json.{Style.RESET_ALL}")
            return False

    def perform_claim(self):
        data['current_activity'] = "Claiming Faucet"
        log(f"{Fore.CYAN}▶ [FAUCET] Memulai claim...{Style.RESET_ALL}")
        try:
            r = s.post(f"https://{host}/api.php?act=faucet", timeout=15)
            r_json = r.json()
            if r_json.get('message'):
                v = self.data_account()
                match = re.search(r'(\d+\.\d+) XRP', r_json['message'])
                earn_str = match.group(1) if match else "0"
                earn_float = float(earn_str)
                earn_formatted = f"{earn_float:.8f}"
                if earn_float > self.best_claim:
                    self.streak = 1; self.best_claim = earn_float
                elif earn_float == self.best_claim and self.best_claim > 0:
                    self.streak += 1
                data.update({
                    'latest_reward': earn_formatted,
                    'best_reward': f"{self.best_claim:.8f}",
                    'streak': self.streak
                })
                if v and 'total_bal' in v: data['total_bal'] = v['total_bal']
                log(f"{Fore.GREEN}💸 [FAUCET] Reward: {earn_formatted} XRP{Style.RESET_ALL}")
        except (json.JSONDecodeError, requests.exceptions.RequestException) as e:
            log(f"{Fore.RED}Error di Faucet: {e}{Style.RESET_ALL}")

    def get_ad_links(self):
        data['current_activity'] = "Checking PTC Ads"
        log(f"{Fore.MAGENTA}[PTC] Mengambil daftar iklan...{Style.RESET_ALL}")
        try:
            r = s.get("https://faucetearner.org/ptc.php", timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            links = [urljoin(f"https://{host}/", re.search(r"window\.open\('([^']+)'", btn.get("onclick")).group(1)) for btn in soup.select('button[onclick^="window.open"]')]
            log(f"{Fore.MAGENTA}[PTC] Ditemukan {len(links)} iklan.{Style.RESET_ALL}")
            return links
        except requests.exceptions.RequestException as e:
            log(f"{Fore.RED}[PTC] Gagal mengambil halaman PTC: {e}{Style.RESET_ALL}")
            return []

    def watch_ad(self, ad_url, ad_num, total_ads):
        data['current_activity'] = f"Watching PTC Ad {ad_num}/{total_ads}"
        log(f"{Fore.YELLOW}[PTC] [{ad_num}/{total_ads}] Mengunjungi iklan...{Style.RESET_ALL}")
        try:
            go_page_res = s.get(ad_url, timeout=15)
            soup = BeautifulSoup(go_page_res.text, "html.parser")
            timer_element = soup.find(string=re.compile(r'(\d+) seconds'))
            wait_time = int(re.search(r'(\d+)', timer_element).group(1)) if timer_element else 125
            
            for i in range(wait_time, 0, -1):
                if not bot_control.is_set(): log(f"{Fore.RED}\n[PTC] Proses dihentikan manual.{Style.RESET_ALL}"); return False
                log(f"{Fore.YELLOW}      ⏳ Sisa waktu: {i:02d} detik...{Style.RESET_ALL}" + " "*10)
                sleep(1)

            verify_form = soup.find('form', {'action': re.compile(r'ptc\.php\?verify=')})
            if not verify_form: log(f"{Fore.RED}   [PTC] ⚠️ Form validasi tidak ditemukan.{Style.RESET_ALL}"); return True
            
            form_action = urljoin(ad_url, verify_form['action'])
            form_data = {inp.get('name'): inp.get('value', '') for inp in verify_form.find_all('input') if inp.get('name')}
            verify_res = s.post(form_action, data=form_data, timeout=15)
            
            if "has been credited" in verify_res.text: log(f"{Fore.GREEN}   [PTC] ✅ Iklan berhasil divalidasi!{Style.RESET_ALL}")
            else: log(f"{Fore.RED}   [PTC] ⚠️ Validasi gagal.{Style.RESET_ALL}")
            self.data_account()
            return True
        except Exception as e:
            log(f"{Fore.RED}   [PTC] ❌ Gagal memproses iklan: {e}{Style.RESET_ALL}"); return False

    def data_account(self):
        log("🔍 Getting user info...")
        try:
            r = s.get(f"https://{host}/dashboard.php", timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            username = soup.find('span', class_='username')
            balance_div = soup.find('div', class_='balance')
            v = {"username": username.text.strip() if username else "N/A"}
            if balance_div: v['total_bal'] = f"{float(balance_div.text.strip().split()[0]):.8f}"
            else: v['total_bal'] = "0.00000000"
            data.update(v)
            return v
        except Exception as e:
            log(f"{Fore.RED}Gagal ambil data akun: {e}{Style.RESET_ALL}"); return None

bot = Bot()

def run_master_loop():
    log("🤖 Bot Master thread started. Waiting for start signal from admin.")
    while True:
        if bot_control.is_set():
            data['bot_status'] = 'running'
            if not bot.is_configured and not bot.config():
                log(f"{Fore.RED}Konfigurasi gagal, Bot berhenti.{Style.RESET_ALL}")
                bot_control.clear()
                continue
            
            ads = bot.get_ad_links()
            if ads:
                for i, ad_url in enumerate(ads, 1):
                    if not bot_control.is_set(): break
                    if bot.watch_ad(ad_url, i, len(ads)): sleep(3)
            else:
                bot.perform_claim()
                data['current_activity'] = "Cooldown Faucet"
                log(f"⏳ [FAUCET] Rehat sejenak...")
                for _ in range(60):
                    if not bot_control.is_set(): break
                    sleep(1)
        else:
            data['bot_status'] = 'stopped'
            data['current_activity'] = 'Idle'
            sleep(1)

@app.route('/')
def index(): return send_from_directory(app.static_folder, 'index.html')
@app.route('/admin')
def admin_login_page(): return send_from_directory(app.static_folder, 'admin.html')
@app.route('/api/data')
def api_data(): return jsonify(data)
@app.route('/logs')
def logs(): return jsonify(log_data)

@app.route('/admin/login', methods=['POST'])
def admin_login():
    try:
        with open('config.json', 'r') as f: config = json.load(f)
        with open('admin.json', 'r') as f: creds = json.load(f)
    except FileNotFoundError: return jsonify({"success": False, "message": "Server configuration error."}), 500
    
    recaptcha_response = request.form.get('g-recaptcha-response')
    secret_key = config.get('recaptcha_secret_key')
    if not recaptcha_response or not secret_key: return jsonify({"success": False, "message": "reCAPTCHA error."}), 400

    verify_payload = {'secret': secret_key, 'response': recaptcha_response}
    try:
        result = requests.post('https://www.google.com/recaptcha/api/siteverify', data=verify_payload, timeout=5).json()
    except requests.exceptions.RequestException: return jsonify({"success": False, "message": "Could not verify reCAPTCHA."}), 500

    if not result.get('success'): return jsonify({"success": False, "message": "Invalid reCAPTCHA. Please try again."}), 400
    
    if request.form.get('username') == creds.get('username') and request.form.get('password') == creds.get('password'):
        session['logged_in'] = True; return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login_page'))

@app.route('/api/control/start', methods=['POST'])
def start_bot_control():
    if not session.get('logged_in'): return jsonify({"success": False, "message": "Unauthorized"}), 401
    bot_control.set()
    log(f"{Fore.GREEN}▶️ [BOT] Admin memberi sinyal START.{Style.RESET_ALL}")
    return jsonify({"success": True})

@app.route('/api/control/stop', methods=['POST'])
def stop_bot_control():
    if not session.get('logged_in'): return jsonify({"success": False, "message": "Unauthorized"}), 401
    bot_control.clear()
    log(f"{Fore.RED}⏹️ [BOT] Admin memberi sinyal STOP.{Style.RESET_ALL}")
    return jsonify({"success": True})

@app.route('/api/control/status')
def bot_status():
    if not session.get('logged_in'): return jsonify({"status": "unauthorized"}), 401
    return jsonify({"status": "running" if bot_control.is_set() else "stopped", "activity": data['current_activity']})

if __name__ == '__main__':
    threading.Thread(target=run_master_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)