from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from pathlib import Path

def generate_feed(config, state):
    feed_file = config['feed']['file_name']
    base = config['feed']['url_base']

    fg = FeedGenerator()
    fg.load_extension('podcast')

    # --- Metadata opcional ---
    title = config['feed'].get('title', 'SherloCaster2')
    link = config['feed'].get('link', 'https://www.sherblog.es')
    copyright = config['feed'].get('copyright')
    author = config['feed'].get('author')

    fg.title(title)
    fg.link(href=link, rel='alternate')
    fg.description(config['feed'].get('description', 'Podcast automatizado desde YouTube y Twitch'))
    fg.language('es')

    if copyright:
        fg.copyright(copyright)

    if author:
        fg.author({'name': author})

    # --- Imagen del feed ---
    image_url = config['feed'].get('image')
    if image_url:
        # RSS estándar
        fg.image(image_url)

    fg.lastBuildDate(datetime.now(timezone.utc))

    if "episodes" not in state:
        print("[Fd] No hay episodios en el estado, feed vacío")
        state["episodes"] = []
    
    episodes = state.get("episodes", [])
    for ep in episodes:
        fe = fg.add_entry()
        fe.title(ep['title'])
        fe.guid(ep['id'], permalink=False)

        # obtener nombre del archivo real
        audio_path = Path(ep['file_path'])
        file_name = audio_path.name

        # construir url de descarga
        enclosure_url = f"{base}{file_name}"

        # obtener tamaño para <length>
        length = audio_path.stat().st_size if audio_path.exists() else ep.get('size', 0)


        fe.enclosure(
            url=enclosure_url,
            type="audio/mpeg",
            length=str(length)
        )

        fe.pubDate(ep['published_at'])

    out_path = Path("/data") / feed_file
    fg.rss_file(str(out_path))

    print(f"[Fd] generado en {out_path}")

