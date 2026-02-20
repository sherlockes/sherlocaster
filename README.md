# Sherlocaster

Estamos frente a una solución automatizada y dockerizada en Python diseñada para convertir contenido de video de plataformas populares (YouTube, Twitch y Kick) en un feed de podcast (RSS) privado y optimizado.

Ideal para usuarios que prefieren consumir contenido de plataformas de video en formato audio, ahorrando ancho de banda y datos móviles.

# Características principales
Multi-plataforma: Soporte nativo para YouTube (vía yt-dlp), Twitch (vía twitch-dl) y Kick.

Optimización de Audio: Procesa automáticamente el audio a formato MP3 Mono (64kbps) para minimizar el tamaño del archivo sin sacrificar la claridad de la voz.

Sincronización Remota: Integración con rclone para subir los audios y el feed RSS a proveedores de almacenamiento en la nube (Google Drive, S3, Dropbox, etc.).

Gestión de Estados: Mantiene un historial de episodios procesados para evitar duplicados.

Interfaz Web: Incluye una API y una pequeña interfaz web (FastAPI) para:

Editar la configuración (config.yaml) en vivo.

Visualizar logs de las últimas ejecuciones.

Consultar el estado del feed y los episodios recientes.

Limpieza Automática: Motor de retención que borra archivos antiguos tanto localmente como en el almacenamiento remoto.

# Arquitectura del Sistema
La aplicación se divide en dos componentes principales mediante Docker:

Worker (sherlocaster): El motor que se encarga de escanear canales, descargar, procesar audio, generar el XML del feed y subirlo a la nube.

Web (sherlocaster-web): Servidor FastAPI que expone la API y sirve la interfaz de administración y los archivos estáticos.

Stack Tecnológico:

Lenguaje: Python 3.12

Framework Web: FastAPI / Uvicorn

Descarga: yt-dlp, twitch-dl, Deno

Procesamiento: FFmpeg

Nube: Rclone

# Instalación y Despliegue
1. Requisitos previos
Docker y Docker Compose instalados.

Un archivo de configuración de rclone (usualmente en ~/.config/rclone/rclone.conf).

Un token de Twitch (si vas a usar esa fuente).

2. Estructura de carpetas
Se recomienda la siguiente estructura en el servidor:

Bash
sherlocaster/
├── config.yaml          # Configuración de canales y feed
├── docker-compose.yaml
├── config/
│   └── twitch_token.env # Variables de entorno para Twitch
└── data/                # (Se crea automáticamente) Audios y estado
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

Bash
# Ejemplo: Ejecutar cada 6 horas
0 */6 * * * cd /ruta/a/sherlocaster && docker-compose start sherlocaster
⚙️ Variables de Entorno
En el archivo ./config/twitch_token.env:

TWITCH_TOKEN: Tu token de acceso para descargas de Twitch.

# Mantenimiento
La aplicación gestiona automáticamente el espacio:

Local: Se rige por retention en el config.yaml.

Remoto: Rclone borra los archivos que superen los retention_days.


Desarrollado por: Sherlockes

Licencia: MIT
