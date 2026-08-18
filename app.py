import os
import subprocess
from flask import Flask

# HLS segmentlerinin kaydedileceği klasörü otomatik oluştur
os.makedirs("hls_stream", exist_ok=True)

app = Flask(__name__)

def start_stream_generator():
    # ATV Avrupa'nın resmi canlı yayın sayfası sabit olarak belirlendi
    target_url = "https://www.atvavrupa.tv/canli-yayin"
    
    # yt-dlp kullanarak hedef web sayfasındaki güncel m3u8 adresini otomatik çöz
    try:
        ydl_cmd = ["yt-dlp", "-g", target_url]
        output = subprocess.check_output(ydl_cmd, text=True).strip()
        resolved_url = output.splitlines()[0] if output else ""
    except Exception:
        resolved_url = ""

    # Eğer çözülemezse yedek olarak orijinal adresi kullan
    if not resolved_url:
        resolved_url = target_url

    # 1. Streamlink komutu: Çözülen akışı stdout'a verir
    streamlink_cmd = [
        "streamlink",
        "--stdout",
        resolved_url,
        "best"
    ]
    
    # 2. FFmpeg komutu: Ham veriyi alıp HLS segmentlerine böler
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", "pipe:0",
        "-c:v", "copy",
        "-c:a", "copy",
        "-f", "hls",
        "-hls_time", "4",
        "-hls_list_size", "10",
        "-hls_flags", "delete_segments+append_list",
        "hls_stream/master.m3u8"
    ]
    
    # Süreçleri birbirine bağla
    p1 = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p1.stdout.close()

@app.route("/")
def index():
    return "<h1>ATV Avrupa HLS Streamer Aktif!</h1><p>Yayın üreticisini başlatmak için: <a href='/start'>/start</a></p>"

@app.route("/start")
def trigger_stream():
    try:
        start_stream_generator()
        return "ATV Avrupa yayını başarıyla başlatıldı ve işleniyor!"
    except Exception as e:
        return f"Hata oluştu: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
