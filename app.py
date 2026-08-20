import os
import re
import json
import subprocess
import threading
import time
import requests
import urllib3
from flask import Flask, send_from_directory, jsonify

# Güvenlik uyarılarını bastır
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HLS_DIR = "hls_stream"
os.makedirs(HLS_DIR, exist_ok=True)

app = Flask(__name__)

# Global Durum Değişkenleri
ffmpeg_process = None
is_running = True  # Varsayılan olarak aktif
process_lock = threading.Lock()  # Çakışmaları önleyen kilit mekanizması

# ==========================================
# 1. ATV AVRUPA (TURKUVAZ) URL & TOKEN ALMA
# ==========================================
def get_atvavrupa_token_url():
    """ATV Avrupa canlı yayın sayfasından Video ID, Website ID çekip Secure Token URL'sini alır."""
    target_url = "https://www.atvavrupa.tv/canli-yayin"
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": target_url
    })

    try:
        html_res = session.get(target_url, verify=False, timeout=15)
        if html_res.status_code != 200:
            return None

        video_id_match = re.search(r'data-videoid=["\']([^"\']+)["\']', html_res.text)
        website_id_match = re.search(r'data-websiteid=["\']([^"\']+)["\']', html_res.text)

        if not video_id_match or not website_id_match:
            print("[HATA] ATV Avrupa ID bilgileri HTML içinde bulunamadı.")
            return None

        video_id = video_id_match.group(1)
        website_id = website_id_match.group(1)

        api_url = f"https://videojs.tmgrup.com.tr/getvideo/{website_id}/{video_id}"
        api_res = session.get(api_url, verify=False, timeout=10).json()

        if not api_res.get("success"):
            print("[HATA] Turkuvaz API 'success': False döndü.")
            return None

        raw_hls_url = api_res["video"]["VideoSmilUrl"]

        secure_api = "https://securevideotoken.tmgrup.com.tr/webtv/secure"
        token_res = session.get(secure_api, params={"url": raw_hls_url}, verify=False, timeout=10).json()

        if token_res.get("Success"):
            return token_res["Url"]

    except Exception as e:
        print(f"[HATA] ATV Avrupa Token alma hatası: {e}")

    return None

def build_variant_url(base_url, suffix):
    """Tokenlı .m3u8 URL'sini bozmadan kalite ekini (_576p, _360p) yerleştirir."""
    if ".m3u8" in base_url:
        return base_url.replace(".m3u8", f"{suffix}.m3u8")
    return base_url

# ==========================================
# 2. MANİFEST VE FFMPEG AKIŞ YÖNETİMİ
# ==========================================
def create_master_manifest():
    """HLS istemcileri için master.m3u8 dosyasını oluşturur."""
    master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1200000,NAME=576p,RESOLUTION=1024x576
atvavrupa_576p.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=600000,NAME=360p,RESOLUTION=640x360
atvavrupa_360p.m3u8"""

    with open(os.path.join(HLS_DIR, "master.m3u8"), "w", encoding="utf-8") as f:
        f.write(master_content)

def start_ffmpeg_process():
    """FFmpeg sürecini Thread Lock koruması ile güvenli bir şekilde başlatır."""
    global ffmpeg_process

    with process_lock:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            return True

        token_m3u8_url = get_atvavrupa_token_url()
        if not token_m3u8_url:
            print("[HATA] Akış URL'si (Token) alınamadı, FFmpeg başlatılamıyor.")
            return False

        url_576p = build_variant_url(token_m3u8_url, "_576p")
        url_360p = build_variant_url(token_m3u8_url, "_360p")

        create_master_manifest()

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-reconnect", "1", "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
            "-i", url_576p,
            "-reconnect", "1", "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
            "-i", url_360p,
            "-map", "0:v?", "-map", "0:a?", "-c", "copy",
            "-f", "hls", "-hls_time", "4", "-hls_list_size", "10",
            "-hls_flags", "delete_segments+append_list",
            os.path.join(HLS_DIR, "atvavrupa_576p.m3u8"),
            "-map", "1:v?", "-map", "1:a?", "-c", "copy",
            "-f", "hls", "-hls_time", "4", "-hls_list_size", "10",
            "-hls_flags", "delete_segments+append_list",
            os.path.join(HLS_DIR, "atvavrupa_360p.m3u8")
        ]

        ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[BİLGİ] ATV Avrupa FFmpeg süreci otomatik olarak başlatıldı.")
        return True

# ==========================================
# 3. WATCHDOG (OTOMATİK İZLEYİCİ VE YENİDEN BAŞLATICI)
# ==========================================
def stream_watchdog():
    """Süreci arka planda denetler, FFmpeg kapandığında taze token ile yeniden başlatır."""
    global ffmpeg_process, is_running
    while True:
        time.sleep(8)
        if is_running:
            if ffmpeg_process is None or ffmpeg_process.poll() is not None:
                print("[UYARI] FFmpeg aktif değil. Watchdog taze Token ile yayını başlatıyor...")
                start_ffmpeg_process()

watchdog_thread = threading.Thread(target=stream_watchdog, daemon=True)
watchdog_thread.start()

# ==========================================
# 4. FLASK ROTALARI
# ==========================================
@app.route("/")
def index():
    return """
    <h1>ATV Avrupa HLS Streamer (Otomatik Yönetim)</h1>
    <ul>
        <li><a href='/hls_stream/master.m3u8'>Master Playlist</a></li>
        <li><a href='/hls_stream/atvavrupa_576p.m3u8'>576p Playlist</a></li>
        <li><a href='/hls_stream/atvavrupa_360p.m3u8'>360p Playlist</a></li>
        <li><a href='/health'>Sağlık Durumu (Health Check)</a></li>
        <li><a href='/restart'>Acil Durum Yeniden Başlat (Force Restart)</a></li>
    </ul>
    """

@app.route("/health")
def health_check():
    """UptimeRobot veya Cron-Job servislerinin Render'ı uyanık tutması için sağlık rotası."""
    status = "running" if (ffmpeg_process and ffmpeg_process.poll() is None) else "restarting"
    return jsonify({"status": status, "watchdog": is_running}), 200

@app.route("/restart")
def force_restart():
    """Acil durumlarda yayını ve FFmpeg sürecini zorla sonlandırıp taze token ile yeniden başlatır."""
    global ffmpeg_process
    with process_lock:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            ffmpeg_process.kill()
            ffmpeg_process = None
            print("[ACİL MÜDAHALE] FFmpeg süreci zorla kapatıldı.")

    success = start_ffmpeg_process()
    if success:
        return jsonify({"status": "success", "message": "Yayın taze token ile yeniden başlatıldı!"}), 200
    return jsonify({"status": "error", "message": "Yayın başlatılırken hata oluştu!"}), 500

@app.route("/hls_stream/<path:filename>")
def serve_hls(filename):
    """Lazy-Load: Yayın dosyası istendiğinde FFmpeg çalışmıyorsa otomatik başlatılır."""
    if ffmpeg_process is None or ffmpeg_process.poll() is not None:
        start_ffmpeg_process()

    response = send_from_directory(HLS_DIR, filename)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# Uygulama ayağa kalkarken ilk tetikleme
start_ffmpeg_process()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
