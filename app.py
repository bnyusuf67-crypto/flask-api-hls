import os
import subprocess
import threading
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

@app.route("/")
def index():
    return "<h1>ATV Avrupa HLS Streamer Aktif!</h1><p>Oynatma listesi: <a href='/hls_stream/master.m3u8'>/hls_stream/master.m3u8</a></p>"

@app.route("/start")
def trigger_stream():
    try:
        # İsteğe bağlı olarak manuel tetikleme için de kalabilir
        threading.Thread(target=start_stream_generator, daemon=True).start()
        return "ATV Avrupa yayını tetiklendi ve arka planda işleniyor!"
    except Exception as e:
        return f"Hata oluştu: {str(e)}", 500

# HLS dosyalarının dışarıdan okunmasını sağlayan rota
@app.route("/hls_stream/<path:filename>")
def serve_hls(filename):
    return send_from_directory("hls_stream", filename)

if __name__ == "__main__":
    # Flask sunucusu başlar başlamaz arka planda akışı otomatik başlat
    auto_thread = threading.Thread(target=start_stream_generator, daemon=True)
    auto_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
