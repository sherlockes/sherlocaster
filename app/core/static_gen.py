import os
import subprocess
from datetime import datetime
from pathlib import Path
import shutil

# Importamos las funciones de tu proyecto
from app.core.config import load_config
from app.core.state import load_state

class StaticGenerator:
    def __init__(self):
        # En Docker, la raíz es /app
        self.base_path = Path("/app")
        self.output_dir = self.base_path / "docs"
        
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def sync_assets(self):
        """Busca el feed.xml en la ruta indicada por el usuario y lo copia a docs/rss.xml"""
        # Según tu indicación, la ruta es /data/feed.xml (en el contenedor /app/data/feed.xml)
        rss_source = self.base_path / "data" / "feed.xml"
        
        if rss_source.exists():
            # Lo copiamos como rss.xml para que coincida con el enlace del HTML
            shutil.copy2(rss_source, self.output_dir / "rss.xml")
            print(f"✅ Feed copiado: {rss_source} -> {self.output_dir}/rss.xml")
        else:
            print(f"⚠️ Error: No se encuentra el archivo en {rss_source}")

        # Sincronizar CSS
        css_source = self.base_path / "data" / "html" / "static-style.css"
        
        if css_source.exists():
            shutil.copy2(css_source, self.output_dir / "static-style.css")
            print(f"✅ Asset copiado: static-style.css")
        else:
            print(f"⚠️ Error: No se encuentra {css_source}")

    def get_last_logs(self):
        """Lista los archivos existentes y muestra el contenido ÍNTEGRO del más reciente."""
        log_dir = self.base_path / "data/logs"
        if not log_dir.exists(): 
            return "Carpeta de logs no encontrada."
        
        # Obtenemos todos los archivos .log ordenados por fecha (más nuevo primero)
        log_files = sorted(list(log_dir.glob("*.log")), key=os.path.getmtime, reverse=True)
        
        if not log_files: 
            return "No se han encontrado archivos .log."
        
        # 1. Cabecera con la lista de archivos
        resumen_archivos = "Archivos en data/logs:\n"
        for f in log_files[:5]:
            resumen_archivos += f"- {f.name}\n"
        
        resumen_archivos += "\n" + "="*30 + "\n"
        resumen_archivos += f"Contenido de: {log_files[0].name}\n"
        resumen_archivos += "="*30 + "\n\n"
        
        # 2. Leemos el contenido íntegro
        try:
            with open(log_files[0], 'r', encoding='utf-8') as f:
                # Leemos todo el archivo de una vez
                contenido = f.read() 
                
                # Combinamos con la cabecera y escapamos caracteres HTML
                return (resumen_archivos + contenido).replace("<", "&lt;").replace(">", "&gt;")
        except Exception as e:
            return f"Error al leer el log más reciente: {str(e)}"

    def generate_site(self):
        """Genera el HTML con cajas de estadísticas forzadas en una sola línea."""
        config = load_config()
        state = load_state()
        last_update = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        ep_list = state.get('episodes', []) if state else []
        
        # --- LÓGICA DE ESTADÍSTICAS ---
        stats = {
            "youtube": {"count": 0, "last": "", "color": "#ff0000"},
            "twitch": {"count": 0, "last": "", "color": "#9146ff"},
            "kick": {"count": 0, "last": "", "color": "#53fc18"}
        }
        all_dates = []

        for e in ep_list:
            src = e.get('source', '').lower()
            pub_at = e.get('published_at', '')
            if src in stats:
                stats[src]["count"] += 1
                if pub_at > stats[src]["last"]:
                    stats[src]["last"] = pub_at
            if pub_at:
                all_dates.append(pub_at)

        # Formato ultra compacto para las cajas: "10/04 20:35"
        def fmt_dt(dt_str):
            if not dt_str or len(dt_str) < 16: return "N/A"
            return f"{dt_str[8:10]}/{dt_str[5:7]} {dt_str[11:16]}"

        last_added_overall = fmt_dt(max(all_dates)) if all_dates else "N/A"
        # -----------------------------------------

        episodes = sorted(ep_list, key=lambda x: x.get('published_at', ''), reverse=True)[:15]
        source_labels = {"youtube": "Yt-Link", "twitch": "Tw-Link", "kick": "Kc-Link"}

        episodes_html = ""
        for e in episodes:
            raw_date = e.get('published_at', 'N/A')
            clean_date = raw_date[:10] if raw_date != 'N/A' else 'N/A'
            url = e.get('original_url', '#')
            title = e.get('title', 'Sin título')
            source = e.get('source', '').lower()
            label = source_labels.get(source, "Link")
            episodes_html += f"""
            <div class="episode-card">
                <div class="meta-sidebar">
                    <span class="date-tag">{clean_date}</span>
                    <a href="{url}" target="_blank" role="button" class="outline tiny-button">{label}</a>
                </div>
                <div class="title-content">{title}</div>
            </div>"""

        html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
        <link rel="stylesheet" href="static-style.css">
        <title>Sherlocaster</title>
    </head>
    <body>
        <main class="container">
        <section>
            <div class="stats-container">
                <div class="stat-box" style="border: 1px solid {stats['youtube']['color']};">
                    🔴 Youtube <br>
                    {stats['youtube']['count']} eps
                    <small>{fmt_dt(stats['youtube']['last'])}</small>
                </div>
                <div class="stat-box" style="border: 1px solid {stats['twitch']['color']};">
                    🟣 Twitch <br>
                    {stats['twitch']['count']} eps
                    <small>{fmt_dt(stats['twitch']['last'])}</small>
                </div>
                <div class="stat-box" style="border: 1px solid {stats['kick']['color']};">
                    🟢 Kick <br>
                    {stats['kick']['count']} eps
                    <small>{fmt_dt(stats['kick']['last'])}</small>
                </div>
            </div>

        <div class="info-bar">
                <span class="info-badge">
                    🕒 {last_update}
                </span>
                <span class="info-badge">
                    📚 {len(ep_list)} eps
                </span>
                <a href="rss.xml" target="_blank" class="info-badge rss-link">
                    📻 RSS Feed
                </a>
            </div>
        </section>
        <section>
             <div class="episodes-list">
             {episodes_html if episodes_html else '<p>No hay episodios aún.</p>'}
             </div>
        </section>
            
        <section>
             <pre style="max-height: 400px; overflow-y: auto; font-size: 0.7rem;"><code>{self.get_last_logs()}</code></pre>
        </section>
        </main>
    </body>
    </html>"""

        file_path = self.output_dir / "index.html"
        with open(file_path, "w", encoding='utf-8') as f:
            f.write(html)
        return file_path

    
    def publish_to_github(self):
        """Recibe la ruta del archivo y lo sube a GitHub usando Token HTTPS."""
        try:
            # 1. Configuración básica de Git
            subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app"], check=True)
            subprocess.run(["git", "config", "user.name", "Sherlockes"], check=True, cwd=str(self.base_path))
            subprocess.run(["git", "config", "user.email", "sherlockes@yahoo.es"], check=True, cwd=str(self.base_path))

            # 2. Añadir y comprobar cambios
            #subprocess.run(["git", "add", str(file_path)], check=True, cwd=str(self.base_path))
            subprocess.run(["git", "add", "docs/"], check=True, cwd=str(self.base_path))
            check = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(self.base_path))
            if check.returncode == 0:
                print("ℹ️ No hay cambios para subir.")
                return

            # 3. Commit
            msg = f"web: update {datetime.now().strftime('%H:%M')}"
            subprocess.run(["git", "commit", "-m", msg], check=True, cwd=str(self.base_path))
            
            # 4. Inyección del Token HTTPS para el Push
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                print("❌ Error: Falta la variable GITHUB_TOKEN en docker-compose.yaml")
                return

            # Obtenemos la URL actual (que seguramente sea git@github.com:...)
            result = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True, cwd=str(self.base_path))
            origin_url = result.stdout.strip()
            
            # Transformamos la URL para inyectar el token
            if origin_url.startswith("git@github.com:"):
                repo_path = origin_url.split(":", 1)[1]
                push_url = f"https://{token}@github.com/{repo_path}"
            elif origin_url.startswith("https://github.com/"):
                repo_path = origin_url.replace("https://github.com/", "")
                push_url = f"https://{token}@github.com/{repo_path}"
            else:
                push_url = "origin" # Por si acaso

            # 5. Push usando la URL con el Token
            # Silenciamos la salida estándar para que el Token no se imprima en los logs si hay error
            subprocess.run(["git", "push", push_url, "main"], check=True, cwd=str(self.base_path), capture_output=True)
            
            print("🚀 ¡Publicado con éxito en GitHub Pages!")
            
        except subprocess.CalledProcessError as e:
            # Imprimimos el error de Git limpio, sin revelar la URL con el token
            err_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            print(f"❌ Error de Git en el push: {err_msg}")
        except Exception as e:
            print(f"❌ Error inesperado en la publicación: {e}")

    def run(self):
        self.sync_assets()   # 1º Copiar RSS
        self.generate_site() # 2º Crear HTML
        self.publish_to_github() # 3º Subir todo

if __name__ == "__main__":
    gen = StaticGenerator()
    gen.run()
