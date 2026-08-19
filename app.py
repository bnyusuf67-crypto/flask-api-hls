import os
import re
import subprocess
import threading
import time
import requests
from flask import Flask, send_from_directory

HLS_DIR = "hls_stream"
os.makedirs(HLS_DIR, exist_ok=True)

app = Flask(__name__)
ffmpeg_process = None

def get_turkuvaz_hls_url(target_url):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": target_url
    })

    try:
        html_response = session.get(target_url, timeout=10)
        video_id_match = re.search(r'data-videoid=["\']([^"\']+)["\']', html_response.text)
        website_id_match = re.search(r'data-websiteid=["\']([^"\']+)["\']', html_response.text)

        if not video_id_match or not website_id_match:
            return None

        video_id = video_id_match.group(1)
        website_id = website_id_match.group(1)

        api_url = f"https://videojs.tmgrup.com.tr/getvideo/{website_id}/{video_id}"
        api_res = session.get(api_url, timeout=10).json()

        if not api_res.get("success"):
            return None

        hls_url = api_res["video"]["VideoSmilUrl"]

        secure_api = "https://securevideotoken.tmgrup.com.tr/webtv/secure"
        token_res = session.get(secure_api, params={"url": hls_url}, timeout=10).json()

        if token_res.get("Success"):
            return token_res["Url"]

    except Exception as e:
        print(f"Token hatası: {e}")
    
    return None

def create_master_manifest():
    """Verilen şablona birebir uygun master.m3u8 dosyasını yazar."""
    master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1200000,NAME=576p,RESOLUTION=1024x576
atvavrupa_576p.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=600000,NAME=360p,RESOLUTION=640x360
atvavrupa_360p.m3u8"""
    
    with open(os.path.join(HLS_DIR, "master.m3u8"), "w", encoding="utf-8") as f:
        f.write(master_content)

def build_variant_url(base_url, suffix):
    if ".m3u8" in base_url:
        return base_url.replace(".m3u8", f"{suffix}.m3u8")
    return base_url

def start_stream_generator():
    global ffmpeg_process
    target_url = "https://www.atvavrupa.tv/canli-yayin"
    
    base_m3u8_url = get_turkuvaz_hls_url(target_url)
    if not base_m3u8_url:
        print("M3U8 adresi alınamadı!")
        return

    url_576p = build_variant_url(base_m3u8_url, "_576p")
    url_360p = build_variant_url(base_m3u8_url, "_360p")

    create_master_manifest()

    if ffmpeg_process and ffmpeg_process.poll() is None:
        ffmpeg_process.kill()

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-re", "-i", url_576p,
        "-re", "-i", url_360p,
        
        # 576p Akışı -> atvavrupa_576p.m3u8
        "-map", "0:v?", "-map", "0:a?", "-c", "copy",
        "-f", "hls", "-hls_time", "4", "-hls_list_size", "10",
        "-hls_flags", "delete_segments+append_list",
        os.path.join(HLS_DIR, "atvavrupa_576p.m3u8"),

        # 360p Akışı -> atvavrupa_360p.m3u8
        "-map", "1:v?", "-map", "1:a?", "-c", "copy",
        "-f", "hls", "-hls_time", "4", "-hls_list_size", "10",
        "-hls_flags", "delete_segments+append_list",
        os.path.join(HLS_DIR, "atvavrupa_360p.m3u8")
    ]
    
    ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def periodic_site_trigger():
    target_start_url = "https://flaskapihls-atv-avrupa-trkvzlive.onrender.com/start"
    time.sleep(5)
    while True:
        try:
            requests.get(target_start_url, timeout=10)
        except Exception as e:
            print(f"Tetikleme hatası: {e}")
        time.sleep(7200)

@app.route("/")
def index():
    return """
    <h1>ATV Avrupa HLS Streamer</h1>
    <ul>
        <li><a href='/hls_stream/master.m3u8'>Master Playlist</a></li>
        <li><a href='/hls_stream/atvavrupa_576p.m3u8'>576p Playlist</a></li>
        <li><a href='/hls_stream/atvavrupa_360p.m3u8'>360p Playlist</a></li>
    </ul>
    """

@app.route("/start")
def trigger_stream():
    try:
        start_stream_generator()
        return "Yayın başarıyla başlatıldı!"
    except Exception as e:
        return f"Hata: {str(e)}", 500

@app.route("/hls_stream/<path:filename>")
def serve_hls(filename):
    return send_from_directory(HLS_DIR, filename)

if __name__ == "__main__":
    trigger_thread = threading.Thread(target=periodic_site_trigger, daemon=True)
    trigger_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
