import os
import subprocess
import threading
import time
import requests
from flask import Flask, send_from_directory

# HLS segmentlerinin kaydedileceği klasörü otomatik oluştur
os.makedirs("hls_stream", exist_ok=True)

app = Flask(__name__)

def start_stream_generator():
    target_url = "https://www.atvavrupa.tv/canli-yayin"
    
    try:
        ydl_cmd = ["yt-dlp", "-g", target_url]
        output = subprocess.check_output(ydl_cmd, text=True).strip()
        resolved_url = output.splitlines()[0] if output else ""
    except Exception:
        resolved_url = ""

    if not resolved_url:
        resolved_url = target_url

    streamlink_cmd = [
        "streamlink",
        "--stdout",
        resolved_url,
        "best"
    ]
    
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i", "pipe:0",
        "-c:v", "copy",
        "-c:a", "copy",
        "-f", "hls",
        "-hls_time", "4",
        "-hls_list_size", "10",
        "-hls_flags", "delete_segments+append_list",
        "hls_stream/master.m3u8"
    ]
    
    p1 = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p1.stdout.close()

def periodic_site_trigger():
    """Her 2 saatte bir kendi /start adresine istek atarak yayını tetikler"""
    target_start_url = "https://flask-api-hls-atvavrupa-trkvzlive.onrender.com/start"
    
    # Sunucu tam ayağa kalkabilsin diye ilk başta 5 saniye bekle
    time.sleep(5)
    
    while True:
        try:
            print(f"[{target_start_url}] adresine 2 saatlik periyodik tetikleme isteği gönderiliyor...")
            response = requests.get(target_start_url, timeout=10)
            print(f"Tetikleme sonucu: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Tetikleme isteği sırasında hata oluştu: {e}")
        
        # 2 saat bekle (7200 saniye)
        time.sleep(7200)

@app.route("/")
def index():
    return "<h1>ATV Avrupa HLS Streamer Aktif!</h1><p>Yayını başlatmak için: <a href='/start'>/start</a></p><p>Oynatma listesi: <a href='/hls_stream/master.m3u8'>/hls_stream/master.m3u8</a></p>"

@app.route("/start")
def trigger_stream():
    try:
        start_stream_generator()
        return "ATV Avrupa yayını başarıyla başlatıldı ve işleniyor! Birkaç saniye sonra /hls_stream/master.m3u8 adresinden izleyebilirsiniz."
    except Exception as e:
        return f"Hata oluştu: {str(e)}", 500

# HLS dosyalarının dışarıdan okunmasını sağlayan rota
@app.route("/hls_stream/<path:filename>")
def serve_hls(filename):
    return send_from_directory("hls_stream", filename)

if __name__ == "__main__":
    # 2 saatte bir /start adresine istek atacak arka plan iş parçacığını başlat
    trigger_thread = threading.Thread(target=periodic_site_trigger, daemon=True)
    trigger_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
