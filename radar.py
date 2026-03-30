import os
import time
import feedparser
from google import genai
from google.genai.errors import ServerError
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from twilio.rest import Client

# Configuracion de Credenciales
TWILIO_SID    = os.environ.get('TWILIO_SID')
TWILIO_TOKEN  = os.environ.get('TWILIO_TOKEN')
NUMERO_TWILIO = 'whatsapp:+14155238886'
TU_CELULAR    = os.environ.get('TU_CELULAR')
GEMINI_KEY    = os.environ.get('GEMINI_API_KEY')
MOMENTO       = os.environ.get('MOMENTO', 'apertura')

TZ_ARG = ZoneInfo("America/Argentina/Buenos_Aires")

FUENTES_RSS = [
        "https://www.infobae.com/arc/outboundfeeds/rss/economia/?outputType=xml",
        "https://www.ambito.com/rss/economia.xml",
        "https://www.ambito.com/rss/finanzas.xml",
        "https://www.cronista.com/rss/",
        "https://www.iprofesional.com/rss/economia",
        "https://www.eleconomista.com.ar/feed/",
        "https://www.clarin.com/rss/economia/",
        "https://www.pagina12.com.ar/rss/secciones/economia/notas",
        "https://www.parlamentario.com/rss/economia",
]


def obtener_noticias_crudas():
        noticias = set()
        hoy_arg  = datetime.now(TZ_ARG).date()

    for url in FUENTES_RSS:
                try:
                                feed = feedparser.parse(url)
                                for entry in feed.entries:
                                                    if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                                                                            continue
                                                                        fecha_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                                                    fecha_arg = fecha_utc.astimezone(TZ_ARG).date()
                                                    if fecha_arg == hoy_arg:
                                                                            link_limpio = entry.link.split('?')[0]
                                                                            noticias.add(f"TITULO: {entry.title} | LINK: {link_limpio}")
                except Exception as e:
                                print(f"[WARN] Error procesando {url}: {e}")
                                continue

            return list(noticias)


def analizar_con_ia(noticias):
        texto_noticias = "\n".join(noticias)
        ahora_str = datetime.now(TZ_ARG).strftime("%d/%m/%Y %H:%M")

    if MOMENTO == "cierre":
                contexto_momento = "Es el cierre de la jornada. Enfocate en: movimiento del tipo de cambio durante el dia, datos de produccion/industria publicados, decisiones de politica economica, y el balance del mercado financiero local."
                emoji_momento = "Cierre"
                label_momento = "Cierre"
else:
            contexto_momento = "Es la apertura del dia. Enfocate en: novedades de la noche anterior, apertura de mercados, datos macro publicados antes del mediodia, y agenda economica del dia."
            emoji_momento = "Apertura"
            label_momento = "Apertura"

    prompt = f"""Sos un analista economico senior argentino que redacta un reporte diario ejecutivo para directivos industriales.
    {contexto_momento}

    NOTICIAS DEL DIA:
    {texto_noticias}

    Redacta el reporte con EXACTAMENTE este formato para WhatsApp:

    *Radar Economico - {label_momento} | {ahora_str}*

    MERCADO Y DOLAR:
    [Una linea concisa con valores del dolar blue, oficial, MEP y CCL si aparecen. Si no hay datos, escribi Sin datos de cotizacion en esta edicion.]

    MACROECONOMIA (las 3 noticias de mayor impacto):
    - [Titulo muy corto] URL
    - [Titulo muy corto] URL
    - [Titulo muy corto] URL

    INDUSTRIA Y PRODUCCION (las 2 mas relevantes):
    - [Titulo muy corto] URL
    - [Titulo muy corto] URL

    DATO CLAVE DEL DIA:
    [1 frase de impacto sobre la noticia mas importante y por que le interesa a la industria argentina]

    CRITERIOS: Priorizar inflacion, reservas BCRA, tipo de cambio, balanza comercial, PBI, EMAE, deuda, riesgo pais, EMI, tarifas energia, credito productivo. Descartar opinion sin datos, lifestyle, deportes. Maximo 1800 caracteres.
    """


    client = genai.Client(api_key=GEMINI_KEY)

    for intento in range(3):
                try:
                                response = client.models.generate_content(
                                                    model='gemini-2.0-flash',
                                                    contents=prompt
                                )
                                return response.text
except Exception as e:
            print(f"[WARN] Servidor Gemini saturado. Reintentando ({intento + 1}/3)...")
            time.sleep(15)

    ahora_str2 = datetime.now(TZ_ARG).strftime("%d/%m/%Y %H:%M")
    return f"*Radar Economico | {ahora_str2}*\n\nLas noticias fueron recolectadas pero el analizador de IA esta saturado. Intente mas tarde."


def enviar_reporte():
        print(f"[INFO] Ejecutando Radar - Momento: {MOMENTO}")
        noticias = obtener_noticias_crudas()
        print(f"[INFO] Noticias encontradas hoy: {len(noticias)}")

    if len(noticias) < 3:
                ahora_str = datetime.now(TZ_ARG).strftime("%d/%m/%Y %H:%M")
                resumen = f"*Radar Economico | {ahora_str}*\n\nNo se encontraron suficientes noticias economicas hoy."
else:
            resumen = analizar_con_ia(noticias)

    cliente = Client(TWILIO_SID, TWILIO_TOKEN)
    cliente.messages.create(
                body=resumen.strip(),
                from_=NUMERO_TWILIO,
                to=TU_CELULAR
    )
    print(f"[OK] Reporte enviado correctamente ({len(resumen)} caracteres).")


if __name__ == "__main__":
        enviar_reporte()
    
