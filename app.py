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
        print("Yayinkaynağı çözümleniyor (yt-dlp)...")
        ydl_cmd = ["yt-dlp", "-g", target_url]
        output = subprocess.check_output(ydl_cmd, text=True).strip()
        resolved_url = output.splitlines()[0] if output else ""
    except Exception as e:
        print(f"yt-dlp hatası: {e}")
        resolved_url = ""

    if not resolved_url:
        resolved_url = target_url

    print(f"Kullanılacak URL: {resolved_url}")

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
    
    try:
        # Hataları daha rahat görmek için stderr'i DEVNULL yerine kapatabilir veya loglayabilirsiniz
        p1 = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        p1.stdout.close()
        print("Streamlink ve FFmpeg başarıyla başlatıldı.")
    except Exception as e:
        print(f"Yayın başlatma hatası: {e}")

@app.route("/")
def index():
    return "<h1>ATV Avrupa HLS Streamer Aktif!</h1><p>Oynatma listesi: <a href='/hls_stream/master.m3u8'>/hls_stream/master.m3u8</a></p>"

@app.route("/start")
def trigger_stream():
    try:
        threading.Thread(target=start_stream_generator, daemon=True).start()
        return "Yayın tetiklendi!"
    except Exception as e:
        return f"Hata oluştu: {str(e)}", 500

@app.route("/hls_stream/<path:filename>")
def serve_hls(filename):
    return send_from_directory("hls_stream", filename)

if __name__ == "__main__":
    auto_thread = threading.Thread(target=start_stream_generator, daemon=True)
    auto_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
