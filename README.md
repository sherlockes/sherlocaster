# SherloCaster 🎙️

SherloCaster es una solución automatizada y dockerizada diseñada para convertir contenido de vídeo de plataformas populares (YouTube, Twitch y Kick) en un feed de podcast (RSS) privado y optimizado. 

Ideal para consumir contenido de vídeo en formato audio, ahorrando ancho de banda y permitiendo la escucha offline en cualquier app de podcasts.

## 🚀 Características principales

- **Multi-plataforma:** Soporte nativo para YouTube (vía yt-dlp), Twitch (vía twitch-dl) y Kick.
- **Optimización de Audio:** Conversión automática a MP3 Mono (64kbps) para minimizar el tamaño sin perder calidad de voz.
- **Sincronización Remota:** Integración con `rclone` para subir audios y el feed RSS a la nube (Google Drive, S3, etc.).
- **Gestión de Estado Inteligente:** - Evita duplicados comparando IDs procesados.
    - **Caché de descartes:** Recuerda vídeos que no cumplen la duración mínima para no volver a analizar su metadata, acelerando las ejecuciones sucesivas.
- **Seguridad de Ejecución:** Sistema de **bloqueo (Lock)** mediante `fcntl` que impide que dos instancias del worker se solapen y corrompan los archivos.
- **Logs Limpios:** Procesamiento de salida que elimina códigos de color ANSI, generando archivos `.log` legibles y ligeros.
- **Interfaz Web (FastAPI):** - Editor de configuración (`config.yaml`) integrado.
    - Visualizador de logs en tiempo real y registro histórico.

## 🛠️ Arquitectura del Sistema

La aplicación utiliza dos componentes principales en Docker:

1. **Worker (`sherlocaster`):** El motor que escanea, descarga y procesa. 
   - Utiliza `/data/sherlocaster.lock` para garantizar exclusividad.
   - Actualiza el `state.json` con episodios nuevos y vídeos ignorados.
2. **Web (`sherlocaster-web`):** Servidor FastAPI que expone la interfaz de administración y sirve el feed.

## 📦 Instalación y Configuración

1. **Clonar el repositorio** y entrar en la carpeta.
2. **Configurar Rclone:** Coloca tu `rclone.conf` en `./config/`.
3. **Editar Configuración:** Puedes editar el `config.yaml` inicial.

Stack Tecnológico:
- Lenguaje: Python 3.12
- Framework Web: FastAPI / Uvicorn
- Descarga: yt-dlp, twitch-dl, Deno
- Procesamiento: FFmpeg
- Nube: Rclone

# Instalación y Despliegue
1. Requisitos previos
   - Docker y Docker Compose instalados.
   - Un archivo de configuración de rclone (usualmente en ~/.config/rclone/rclone.conf).
   - Un token de Twitch (si vas a usar esa fuente).

2. Estructura de carpetas
Se recomienda la siguiente estructura en el servidor:

```Bash
sherlocaster/
├── config.yaml          # Configuración de canales y feed
├── docker-compose.yaml
├── config/
│   └── twitch_token.env # Variables de entorno para Twitch
└── data/                # (Se crea automáticamente) Audios y estado
```

3. Configuración (config.yaml)
Edita el archivo según tus necesidades. Ejemplo básico:

```md
YAML
sources:
  youtube:
    enabled: true
    channels:
      - name: "Nombre del Canal"
        url: "https://www.youtube.com/@Canal/videos"
    limit_days: 10
    audio_bitrate: "64k"

storage:
  base_path: "/data"
  state_file: "state/episodes.json"

feed:
  url_base: "http://tu-servidor.com/audio/"
  title: "Mi Podcast Privado"

rclone:
  remote: "MiGoogleDrive"
  path: "/podcasts/sherlocaster"
  retention_days: 15
```

4. Despliegue
Levanta los contenedores:

```bash
docker-compose up -d
```

# Uso y Administración
Acceso Web
- Configuración: http://tu-ip:8000/config - Edita el YAML directamente desde el navegador.
- Logs: http://tu-ip:8000/logs - Revisa qué ha pasado en la última descarga.
- Feed Info: http://tu-ip:8000/feed - Estado actual del RSS generado.

El proceso de actualización
El contenedor sherlocaster (worker) está diseñado para ejecutarse y cerrarse. Se recomienda programar su ejecución mediante un Cron en el host o un orquestador:

```Bash
# Ejemplo: Ejecutar cada 4 horas
0 */4 * * * cd ~/dockers/sherlocaster && docker compose run --rm sherlocaster
```
# Variables de Entorno
En el archivo ./config/twitch_token.env:

```txt
TWITCH_TOKEN: Tu token de acceso para descargas de Twitch.
```

# Mantenimiento
La aplicación gestiona automáticamente el espacio:

Local: Se rige por retention en el config.yaml.

Remoto: Rclone borra los archivos que superen los retention_days.

Desarrollado por: [Sherlockes](https://github.com/sherlockes)

Más artículos en: www.sherblog.es
