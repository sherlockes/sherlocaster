FROM python:3.12-slim

WORKDIR /app

# Dependencias necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    pipx \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# instalar rclone
RUN curl -fsSL https://rclone.org/install.sh | bash

# crear el directorio de config
RUN mkdir -p /app/config

# copiar el rclone.conf
COPY config/rclone.conf /app/config/rclone.conf

# Instalar yt-dlp
RUN python3 -m pip install -U pip
RUN python3 -m pip install -U --no-cache-dir "yt-dlp[default]"

# instalar Deno (desde el script oficial)
RUN curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

RUN mkdir -p /root/.config/yt-dlp && \
    echo "--remote-components ejs:github" > /root/.config/yt-dlp/config && \
    echo "--compat-options all" >> /root/.config/yt-dlp/config

# Instalar twitch-dl vía pipx
RUN pipx install twitch-dl && \
    ln -s /root/.local/bin/twitch-dl /usr/local/bin/twitch-dl

# Dependencias de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Código fuente
COPY app /app/app

# Config
COPY config.yaml /app/

EXPOSE 8085

ENTRYPOINT ["python", "-m", "app.main"]
