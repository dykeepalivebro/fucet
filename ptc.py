import requests
import time
import re
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def get_ad_links(session):
    print("[*] Mengambil halaman PTC...")
    try:
        r = session.get("https://faucetearner.org/ptc.php")
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        for btn in soup.select('button[onclick^="window.open"]'):
            onclick = btn.get("onclick")
            match = re.search(r"window\.open\('([^']+)'", onclick)
            if match:
                full_url = urljoin("https://faucetearner.org/", match.group(1))
                links.append(full_url)

        print(f"[+] Ditemukan {len(links)} iklan.")
        return links
    except requests.exceptions.RequestException as e:
        print(f"[!] Gagal mengambil halaman PTC: {e}")
        return []

def watch_ad(session, ad_url, ad_num, total_ads):
    print(f"\n[{ad_num}/{total_ads}] Mengunjungi: {ad_url}")
    try:
        go_page_res = session.get(ad_url)
        go_page_res.raise_for_status()
        soup = BeautifulSoup(go_page_res.text, "html.parser")

        timer_text = soup.find(string=re.compile(r'(\d+) seconds'))
        wait_time = 125
        if timer_text:
            match = re.search(r'(\d+)', timer_text)
            if match:
                wait_time = int(match.group(1))

        print(f"   ↪️  Berhasil dibuka, tunggu {wait_time} detik...")
        for i in range(wait_time, 0, -1):
            print(f"      ⏳ Sisa waktu: {i:02d} detik", end="\r")
            time.sleep(1)
        print()

        verify_form = soup.find('form', {'action': re.compile(r'ptc\.php\?verify=')})

        if not verify_form:
            print("   🔄 Tidak ditemukan form validasi, mencoba refresh ptc.php...")
            session.get("https://faucetearner.org/ptc.php")
            print("   ⚠️ Validasi tidak dapat dikonfirmasi, semoga berhasil.")
            return True

        form_action = urljoin(ad_url, verify_form['action'])
        form_data = {inp.get('name'): inp.get('value', '') for inp in verify_form.find_all('input') if inp.get('name')}

        print(f"   🔄 Menemukan form validasi, mengirimkan...")
        verify_res = session.post(form_action, data=form_data)
        verify_res.raise_for_status()

        if "has been credited" in verify_res.text or "success" in verify_res.text.lower():
            print("   ✅ Iklan berhasil divalidasi!")
        else:
            print("   ⚠️ Validasi gagal atau tidak dapat dikonfirmasi.")
        return True

    except Exception as e:
        print(f"   ❌ Gagal memproses iklan: {e}")
        return False

def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[!] Error membaca config.json: {e}")
        return None

def main():
    config = load_config()
    if not config:
        return

    config_mod_time = os.path.getmtime('config.json')

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.get("User-Agent", "Mozilla/5.0"),
        "Cookie": config.get("Cookies", "")
    })

    if not session.headers["Cookie"]:
        print("[!] Error: 'Cookies' tidak ada di config.json.")
        return

    run_count = 0
    try:
        while True:
            run_count += 1
            print(f"\n-=-=-=-= Sesi #{run_count} | {time.strftime('%d %b %Y, %H:%M:%S')} =-=-=-=-")

            try:
                current_mod_time = os.path.getmtime('config.json')
                if current_mod_time != config_mod_time:
                    print("[⚙️] Perubahan pada config.json terdeteksi, memuat ulang...")
                    config = load_config()
                    session.headers.update({"Cookie": config.get("Cookies", "")})
                    config_mod_time = current_mod_time
                    print("[✅] Konfigurasi berhasil dimuat ulang.")
            except FileNotFoundError:
                print("[!] Error: config.json dihapus saat program berjalan.")
                time.sleep(10)
                continue

            ads = get_ad_links(session)
            if ads:
                completed_count = 0
                for i, ad_url in enumerate(ads, 1):
                    if watch_ad(session, ad_url, i, len(ads)):
                        completed_count += 1
                    if i < len(ads):
                        time.sleep(3)
                print(f"\n✨ Sesi #{run_count} selesai! {completed_count}/{len(ads)} iklan dikunjungi.")
                
                wait_after_completion = 10
                print(f"   ↪️  Rehat sejenak. Refresh otomatis dalam {wait_after_completion} detik.")
                for i in range(wait_after_completion, 0, -1):
                    print(f"      ⏳ Sesi berikutnya mulai dalam: {i:02d} detik...", end="\r")
                    time.sleep(1)
                print("\n")

            else:
                wait_duration = 30 * 60
                check_interval = 15
                print(f"\n[!] Tidak ada iklan. Masuk mode 'Smart Wait', cek setiap {check_interval} detik.")

                for elapsed in range(0, wait_duration, check_interval):
                    remaining_total = wait_duration - elapsed
                    mins, secs = divmod(remaining_total, 60)
                    print(f"   ⏳ Waktu tunggu tersisa: {mins:02d} menit {secs:02d} detik... (Mengintip...)", end='\r')

                    time.sleep(check_interval)

                    new_ads = get_ad_links(session)
                    if new_ads:
                        print("\n[🎉] Iklan baru ditemukan! Menghentikan timer dan memulai sesi baru...")
                        ads = new_ads
                        break

                if not ads:
                     print("\n\n")

    except KeyboardInterrupt:
        print("\n\n[!] Program dihentikan oleh pengguna. Sampai jumpa!")


if __name__ == "__main__":
    main()