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
- **Interfaz Web (FastAPI):**
  - Dashboard con la info más importante
  - Editor de configuración (`config.yaml`) integrado.
  - Visualizador de logs en tiempo real y registro histórico.
  - Visualizador de los últimos episodios añadidos
- **Interface Web (Estática):**
  - Estadísticas de episodios en el feed
  - Ultima actualización
  - Listado de últimos episodios


## 🛠️ Arquitectura del Sistema
La aplicación utiliza dos componentes principales en Docker:

1. **Worker (`sherlocaster`):** El motor que escanea, descarga y procesa. 
   - Utiliza `/data/sherlocaster.lock` para garantizar exclusividad.
   - Actualiza el `state.json` con episodios nuevos y vídeos ignorados.
   - Descarga y convierte nuevos episodios.
   - Genera el feed y lo sube junto con los episodios a la nube configurada
   - Genera un sitio estático para consultar cuando el contenedor no está activo.
2. **Web (`sherlocaster-web`):** Servidor FastAPI que expone la interfaz de administración y sirve el feed.

> Para que Sherlocaster pueda actualizar automáticamente la web estática en tu repositorio (GitHub Pages), es imprescindible configurar un **Personal Access Token (PAT)**. Sin este token, el contenedor no tiene permisos para realizar un `git push` desde el interior de Docker.

## 📦 Instalación y Configuración

1. **Clonar el repositorio** y entrar en la carpeta.
2. **Configurar Rclone:** Coloca tu `rclone.conf` en `./config/`.
3. **Editar Configuración:** Puedes editar el `config.yaml` inicial.
4. **Variables de entorno:** Tendrás que crear los correspondientes archivos.

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
   - Un token de telegram y un canal para realizar las notificaciones
   - Un token de Github para la generación del sitio estático

2. Estructura de carpetas
```text
.
├── app/                    # Código fuente de la aplicación
│   ├── core/               # Lógica compartida (configuración, SSG, notificaciones)
│   ├── downloader/         # Módulos de descarga (YouTube, Twitch, Kick)
│   ├── uploader/           # Integración con rclone y subida remota
│   ├── main.py             # Worker: Procesamiento y descargas
│   └── web.py              # API/Web: FastAPI y gestión de la interfaz
├── config/                 # Configuración sensible (NO SE SUBE A GIT)
│   ├── rclone.conf         # Configuración de Rclone para subir los archivos
│   ├── telegram.env        # Token de Telegram y ID de canal para despliegues
│   ├── ghtoken.env         # Token de GitHub para despliegues
│   └── twitch_token.env    # Tokens de API para Twitch/Kick
├── data/                   # Volumen persistente (Estado y base de datos local)
│   ├── state.json          # Registro histórico de episodios procesados
│   ├── feed.xml            # Copia local del RSS
│   └── sherlocaster.lock   # Archivo de bloqueo de procesos
├── docs/                   # Web Estática (Generada automáticamente)
│   ├── index.html          # Interfaz de usuario final
│   ├── rss.xml             # Feed para podcatchers
│   └── static-style.css    # Estilos CSS (con soporte Dark Mode)
├── config.yaml             # Configuración principal del sistema
├── docker-compose.yaml     # Orquestación de contenedores
├── Dockerfile              # Definición de la imagen Python 3.12-slim
└── README.md               # Esta documentación
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
Con esto se realiza un primera escaneo y se lanza el servidor web. A partir de aquí podemos lanzar nuevos escaneos mediante

``` bash
docker compose run --rm sherlocaster
```

> Personalmente lo tengo configurado mediante el crontab para que lance, mediante el comando anterior, un escaneo cada 4 horas.

# Uso y Administración
Acceso Web
- Dashboard: http://tu-ip:8000 - Acceso la la info más relevante
- Configuración: http://tu-ip:8000/config - Edita el YAML directamente desde el navegador.
- Logs: http://tu-ip:8000/logs - Revisa qué ha pasado en la última descarga.
- Feed Info: http://tu-ip:8000/feed - Estado actual del RSS generado.


# Variables de Entorno
En el archivo `config/ghtoken.env`
```env
GITHUB_TOKEN=ghp_tu_token_de_acceso_personal
```

En el archivo `config/telegram.env`
``` txt
TELEGRAM_TOKEN=xxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=-xxxxxxxxxxxxxx
```

En el archivo `config/twitch_token.env`
``` txt
AUTH_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

# Mantenimiento
La aplicación gestiona automáticamente el espacio:

Local: Se rige por retention en el config.yaml.

Remoto: Rclone borra los archivos que superen los retention_days.

Desarrollado por: [Sherlockes](https://github.com/sherlockes)

Más artículos en: www.sherblog.es
