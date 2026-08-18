import os
import subprocess
import threading
import time
from flask import Flask, send_from_directory

# HLS segmentlerinin kaydedileceği klasörü otomatik oluştur
os.makedirs("hls_stream", exist_ok=True)

app = Flask(__name__)

# Aktif süreçleri takip etmek için global değişkenler
current_p1 = None
current_p2 = None
stream_lock = threading.Lock()

def start_stream_generator():
    global current_p1, current_p2
    
    with stream_lock:
        # Eğer daha önce çalışan bir yayın varsa önce onları güvenli şekilde sonlandır
        if current_p1 and current_p1.poll() is None:
            try:
                current_p1.terminate()
            except Exception:
                pass
        if current_p2 and current_p2.poll() is None:
            try:
                current_p2.terminate()
            except Exception:
                pass

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
        
        try:
            current_p1 = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            current_p2 = subprocess.Popen(ffmpeg_cmd, stdin=current_p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            current_p1.stdout.close()
            print("Yayın başarıyla başlatıldı / yenilendi.")
        except Exception as e:
            print(f"Yayın başlatılırken hata oluştu: {e}")

def periodic_stream_refresher():
    """Her 2 saatte bir (7200 saniye) yayını yeniden başlatan döngü"""
    # İlk açılışta hemen başlat
    start_stream_generator()
    
    while True:
        # 2 saat bekle (7200 saniye)
        time.sleep(7200)
        print("2 saatlik süre doldu, yayın token'ı yenileniyor...")
        start_stream_generator()

@app.route("/")
def index():
    return "<h1>ATV Avrupa HLS Streamer Aktif!</h1><p>Oynatma listesi: <a href='/hls_stream/master.m3u8'>/hls_stream/master.m3u8</a></p>"

@app.route("/start")
def trigger_stream():
    try:
        # Manuel olarak tetiklemek isterseniz de çalışır
        threading.Thread(target=start_stream_generator, daemon=True).start()
        return "ATV Avrupa yayını manuel olarak tetiklendi ve yenileniyor!"
    except Exception as e:
        return f"Hata oluştu: {str(e)}", 500

# HLS dosyalarının dışarıdan okunmasını sağlayan rota
@app.route("/hls_stream/<path:filename>")
def serve_hls(filename):
    return send_from_directory("hls_stream", filename)

if __name__ == "__main__":
    # 2 saatte bir otomatik yenileme yapacak döngüyü arka planda (daemon thread) başlat
    refresher_thread = threading.Thread(target=periodic_stream_refresher, daemon=True)
    refresher_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
