import os
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai.errors import ServerError
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from twilio.rest import Client

# ─────────────────────────────────────────
# Configuración de Credenciales
# ─────────────────────────────────────────
TWILIO_SID    = os.environ.get('TWILIO_SID')
TWILIO_TOKEN  = os.environ.get('TWILIO_TOKEN')
NUMERO_TWILIO = 'whatsapp:+14155238886'
TU_CELULAR    = os.environ.get('TU_CELULAR')
GEMINI_KEY    = os.environ.get('GEMINI_API_KEY')
MOMENTO       = os.environ.get('MOMENTO', 'apertura')  # 'apertura' o 'cierre'

TZ_ARG = ZoneInfo("America/Argentina/Buenos_Aires")

# ─────────────────────────────────────────
# Fuentes RSS — macro, finanzas e industria
# ─────────────────────────────────────────
FUENTES_RSS = [
    # Macro y finanzas
    "https://www.infobae.com/arc/outboundfeeds/rss/economia/?outputType=xml",
    "https://www.ambito.com/rss/economia.xml",
    "https://www.ambito.com/rss/finanzas.xml",
    "https://www.cronista.com/rss/",
    "https://www.iprofesional.com/rss/economia",
    "https://www.eleconomista.com.ar/feed/",
    # Industria y producción
    "https://www.clarin.com/rss/economia/",
    "https://www.pagina12.com.ar/rss/secciones/economia/notas",
    "https://www.parlamentario.com/rss/economia",
]


def obtener_cotizaciones_dolar():
    """Extrae las cotizaciones del d\u00f3lar desde DolarHoy.com."""
    URL_DH = "https://dolarhoy.com/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    cotizaciones = {}
    try:
        response = requests.get(URL_DH, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Los tiles de cotizaci\u00f3n suelen tener la clase 'tile-comp'
            tiles = soup.find_all('div', class_='tile-comp')
            for tile in tiles:
                tit = tile.find('a', class_='title')
                if not tit:
                    continue
                nombre = tit.text.strip().lower()
                
                # Extraemos valores de compra y venta
                val_compra = tile.find('div', class_='compra')
                val_venta = tile.find('div', class_='venta')
                
                if val_compra and val_venta:
                    v_compra = val_compra.find('div', class_='val').text.strip()
                    v_venta = val_venta.find('div', class_='val').text.strip()
                    
                    if 'blue' in nombre or 'libre' in nombre:
                        cotizaciones['Blue'] = f"Compra: {v_compra} / Venta: {v_venta}"
                    elif 'mep' in nombre or 'bolsa' in nombre:
                        cotizaciones['MEP'] = f"Compra: {v_compra} / Venta: {v_venta}"
                    elif 'liqui' in nombre or 'ccl' in nombre:
                        cotizaciones['CCL'] = f"Compra: {v_compra} / Venta: {v_venta}"
                    elif 'oficial' in nombre:
                        cotizaciones['Oficial'] = f"Compra: {v_compra} / Venta: {v_venta}"
        else:
            print(f"[WARN] No se pudo acceder a DolarHoy. Status: {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error al obtener cotizaciones: {e}")
    
    return cotizaciones


# ─────────────────────────────────────────
# Obtener noticias del día con ventana dinámica
# ─────────────────────────────────────────

def obtener_noticias_crudas():
    """
    Scrapeea todos los feeds RSS y devuelve las noticias
    publicadas en las \u00faltimas 24 horas (o 72 horas si es lunes).
    """
    noticias = set()
    ahora_arg = datetime.now(TZ_ARG)
    
    # Definir ventana: lunes cubre el finde (72h), resto 24h
    horas_atras = 72 if ahora_arg.weekday() == 0 else 24
    limite_temporal = ahora_arg - timedelta(hours=horas_atras)

    for url in FUENTES_RSS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed') or not entry.published_parsed:
                    continue

                # Convertir publicaci\u00f3n a datetime con zona horaria Argentina
                fecha_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                fecha_arg = fecha_utc.astimezone(TZ_ARG)

                # Comparar con el l\u00edmite temporal
                if fecha_arg >= limite_temporal:
                    link_limpio = entry.link.split('?')[0]
                    noticias.add(f"T\u00cdTULO: {entry.title} | LINK: {link_limpio}")

        except Exception as e:
            print(f"[WARN] Error procesando {url}: {e}")
            continue

    return list(noticias)


# ─────────────────────────────────────────
# Analizar con Gemini según el momento del día
# ─────────────────────────────────────────
def analizar_con_ia(noticias: list[str], cotizaciones: dict) -> str:
    texto_noticias = "\n".join(noticias)
    ahora_str = datetime.now(TZ_ARG).strftime("%d/%m/%Y %H:%M")

    # Formatear cotizaciones para el prompt
    precios_str = "\n".join([f"- {k}: {v}" for k, v in cotizaciones.items()])
    if not precios_str:
        precios_str = "No se pudieron obtener cotizaciones en tiempo real."

    if MOMENTO == "cierre":
        contexto_momento = (
            "Es el cierre de la jornada. Enfocate en: movimiento del tipo de cambio durante el día, "
            "datos de producción/industria publicados, decisiones de política económica, "
            "y el balance del mercado financiero local."
        )
        emoji_momento = "🌆"
        label_momento = "Cierre"
    else:
        contexto_momento = (
            "Es la apertura del día. Enfocate en: novedades de la noche anterior, "
            "apertura de mercados, datos macro publicados antes del mediodía, "
            "y agenda económica del día."
        )
        emoji_momento = "🌅"
        label_momento = "Apertura"

    prompt = f"""
Sos un analista económico senior argentino que redacta un reporte diario ejecutivo para directivos industriales.
{contexto_momento}

COTIZACIONES REALES DEL DÓLAR (USAR ESTOS DATOS):
{precios_str}

NOTICIAS DEL DÍA:
{texto_noticias}

Redactá el reporte con EXACTAMENTE este formato (respetalo al pie de la letra, es para WhatsApp):

{emoji_momento} *Radar Económico — {label_momento} | {ahora_str}*

💵 *MERCADO & DÓLAR*
[Resumí en una sola línea los valores del Blue, MEP y CCL usando las COTIZACIONES REALES provistas arriba. Si hay noticias sobre brecha o tendencia, podés agregarlas brevemente.]

📊 *MACROECONOMÍA* (las 3 noticias de mayor impacto)
• [Título muy corto, máx. 12 palabras] → [Link]
• [Título muy corto] → [Link]
• [Título muy corto] → [Link]

🏭 *INDUSTRIA & PRODUCCIÓN* (las 2 más relevantes)
• [Título muy corto] → [Link]
• [Título muy corto] → [Link]

💡 *DATO CLAVE DEL DÍA*
[1 frase de impacto: cuál es LA noticia más importante y por qué le interesa a la industria argentina]

CRITERIOS DE SELECCIÓN:
- Macro prioritario: inflación (IPC/IPC núcleo), reservas BCRA, tipo de cambio, balanza comercial, PBI, actividad económica (EMAE), deuda, riesgo país.
- Industria prioritario: EMI (Estimador Mensual Industrial), tarifas de energía, importaciones de insumos, crédito productivo, regulaciones sectoriales.
- DESCARTÁ: opinión sin datos, lifestyle, deportes, política sin impacto económico directo, noticias duplicadas.
- Máximo 1800 caracteres totales en la respuesta.
"""

    client = genai.Client(api_key=GEMINI_KEY)

    for intento in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text
        except ServerError:
            print(f"[WARN] Servidor Gemini saturado. Reintentando ({intento + 1}/3)...")
            time.sleep(15)

    return (
        f"{emoji_momento} *Radar Económico — {label_momento} | {ahora_str}*\n\n"
        "⚠️ Las noticias fueron recolectadas pero el analizador de IA está saturado. "
        "Intente más tarde o ejecute el workflow manualmente."
    )


# ─────────────────────────────────────────
# Enviar reporte por WhatsApp
# ─────────────────────────────────────────
def enviar_reporte():
    print(f"[INFO] Ejecutando Radar — Momento: {MOMENTO}")
    noticias = obtener_noticias_crudas()
    print(f"[INFO] Noticias encontradas hoy: {len(noticias)}")
    
    # Nuevo: obtener cotizaciones antes de analizar
    cotizaciones = obtener_cotizaciones_dolar()
    print(f"[INFO] Cotizaciones obtenidas: {len(cotizaciones)}")

    if len(noticias) < 3:
        ahora_str = datetime.now(TZ_ARG).strftime("%d/%m/%Y %H:%M")
        resumen = (
            f"🤖 *Radar Económico | {ahora_str}*\n\n"
            "⚠️ No se encontraron suficientes noticias económicas hoy. "
            "Es posible que los feeds estén sin actualizar o que sea un día sin actividad."
        )
    else:
        resumen = analizar_con_ia(noticias, cotizaciones)

    cliente = Client(TWILIO_SID, TWILIO_TOKEN)
    cliente.messages.create(
        body=resumen.strip(),
        from_=NUMERO_TWILIO,
        to=TU_CELULAR
    )
    print(f"[OK] Reporte enviado correctamente ({len(resumen)} caracteres).")


if __name__ == "__main__":
    enviar_reporte()
