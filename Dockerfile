FROM python:3.11-slim

# FFmpeg for video assembly
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create required directories
RUN mkdir -p assets/broll assets/clients config/clients output

EXPOSE 8080

CMD ["python", "startup.py"]
