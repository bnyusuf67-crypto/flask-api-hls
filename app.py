import subprocess

def start_stream_generator(target_url):
    # 1. Streamlink komutu: Hedef adresteki yayını çözer ve stdout'a (çıktıya) verir
    streamlink_cmd = [
        "streamlink",
        "--stdout",               # Çıktıyı doğrudan boruya ver
        target_url,
        "best"                    # En iyi kalitede al (veya 720p, 480p yazabilirsin)
    ]
    
    # 2. FFmpeg komutu: Streamlink'ten gelen ham veriyi (pipe:0) alır ve HLS segmentlerine böler
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", "pipe:0",           # Veriyi standard input'tan al
        "-c:v", "copy",           # Video codec'ini değiştirme (hızlı olur)
        "-c:a", "copy",           # Ses codec'ini değiştirme
        "-f", "hls",
        "-hls_time", "4",         # Her segment 4 saniye
        "-hls_list_size", "10",   # Listede tutulacak max segment
        "-hls_flags", "delete_segments+append_list",
        "hls_stream/master.m3u8"  # Çıkış dosyası
    ]
    
    # İki komutu birbirine bağlama (Streamlink çıktısı -> FFmpeg girdisi)
    p1 = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # p1'in stdout akışını serbest bırak
    p1.stdout.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
