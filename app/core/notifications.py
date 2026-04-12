import os
import requests

def send_telegram_msg(text):
    """Envía un mensaje formateado a Telegram usando variables de entorno."""
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("[!] Telegram abortado: Faltan las variables TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
        return 

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[!] Error enviando notificación a Telegram: {e}")
