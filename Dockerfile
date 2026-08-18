# Hafif bir python imajı kullan
FROM python:3.9-slim

# FFmpeg ve Streamlink'in ihtiyaç duyduğu bağımlılıkları sisteme kur
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizinini ayarla
WORKDIR /app

# Python kütüphanelerini yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyala
COPY . .

# Uygulamayı başlat
CMD gunicorn app:app --bind 0.0.0.0:$PORT
