import os
import feedparser
import google.generativeai as genai
from datetime import datetime
from zoneinfo import ZoneInfo
from twilio.rest import Client

# Configuración de Credenciales
TWILIO_SID = os.environ.get('TWILIO_SID')
TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN')
NUMERO_TWILIO = 'whatsapp:+14155238886' 
TU_CELULAR = os.environ.get('TU_CELULAR')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

FUENTES_RSS = [
    "https://www.infobae.com/arc/outboundfeeds/rss/economia/?outputType=xml",
    "https://www.ambito.com/rss/economia.xml",
    "https://www.clarin.com/rss/economia/",
    "https://www.pagina12.com.ar/rss/secciones/economia/notas"
]

def obtener_noticias_crudas():
    noticias = []
    hoy = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    for url in FUENTES_RSS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    fecha_pub = datetime(*entry.published_parsed[:6]).date()
                    if fecha_pub == hoy:
                        noticias.append(f"TÍTULO: {entry.title} | LINK: {entry.link.split('?')[0]}")
        except: continue
    return "\n".join(list(set(noticias)))

def analizar_con_ia(texto_noticias):
    prompt = f"""
    Sos un analista económico senior para una cámara industrial argentina. 
    Tu tarea es filtrar y resumir esta lista de noticias del día:
    
    {texto_noticias}
    
    REGLAS ESTRICTAS:
    1. Agrupá TODAS las cotizaciones del dólar (blue, oficial, MEP, CCL) en una sola línea informativa inicial.
    2. Seleccioná las 5 noticias de mayor impacto para la MACROECONOMÍA, la INDUSTRIA y la ENERGÍA en Argentina.
    3. Descartá noticias repetidas o irrelevantes (clima, opinión genérica).
    4. Formato de salida: 
       💵 *Mercado:* [Resumen dólar]
       📌 [Título noticia relevante]
       🔗 [Link]
    5. No uses negritas exageradas, mantené el formato limpio para WhatsApp.
    6. Límite: Máximo 1500 caracteres totales.
    """
    response = model.generate_content(prompt)
    return response.text

def enviar_reporte():
    noticias_raw = obtener_noticias_crudas()
    if not noticias_raw:
        resumen = "🤖 *Radar Diario*\nNo se encontraron noticias nuevas hoy."
    else:
        resumen = analizar_con_ia(noticias_raw)

    cliente = Client(TWILIO_SID, TWILIO_TOKEN)
    cliente.messages.create(body=resumen.strip(), from_=NUMERO_TWILIO, to=TU_CELULAR)
    print("Reporte con IA enviado.")

if __name__ == "__main__":
    enviar_reporte()
