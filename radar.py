import os
import feedparser
from datetime import datetime
from zoneinfo import ZoneInfo
from twilio.rest import Client

TWILIO_SID = os.environ.get('TWILIO_SID')
TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN')
NUMERO_TWILIO = 'whatsapp:+14155238886' 
TU_CELULAR = os.environ.get('TU_CELULAR')

# Usamos los canales RSS de Economía (Garantizan orden cronológico y fecha exacta)
FUENTES_RSS = [
    "https://www.infobae.com/arc/outboundfeeds/rss/economia/?outputType=xml",
    "https://www.ambito.com/rss/economia.xml",
    "https://www.clarin.com/rss/economia/",
    "https://www.pagina12.com.ar/rss/secciones/economia/notas"
]

KEYWORDS = ["dólar", "economía", "industria", "macro", "finanzas", "bonos", "energía", "riesgo país", "metalúrgica", "pymes", "rigi", "vaca muerta", "inflación", "tarifas", "bcra", "insumos", "capacidad instalada"]

def obtener_noticias_de_hoy():
    noticias_filtradas = []
    # Fijamos la hora local para que no se confunda con el servidor de GitHub
    hoy_argentina = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()

    for url in FUENTES_RSS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Verificamos si la noticia tiene fecha de publicación
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    fecha_pub = datetime(*entry.published_parsed[:6]).date()
                    
                    # Filtro 1: Estrictamente de HOY
                    if fecha_pub == hoy_argentina:
                        titulo = entry.title.strip()
                        
                        # Filtro 2: Palabras clave
                        if any(k in titulo.lower() for k in KEYWORDS):
                            # Limpiamos el link de rastreadores para ahorrar espacio en WhatsApp
                            link_limpio = entry.link.split('?')[0] 
                            noticias_filtradas.append((titulo, link_limpio))
        except Exception as e:
            print(f"Error en {url}: {e}")

    # Eliminamos duplicados
    noticias_unicas = list(set(noticias_filtradas))
    return noticias_unicas

def enviar_reporte():
    noticias = obtener_noticias_de_hoy()
    fecha_str = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%d/%m")
    
    if not noticias:
        mensaje_final = f"🤖 *Radar Diario - {fecha_str}*\n\nHoy no hay noticias nuevas que coincidan con tus filtros."
    else:
        mensaje_final = f"🤖 *Radar Diario - {fecha_str}*\n\n"
        
        # Algoritmo de llenado dinámico (aprovechamos cada espacio sin pasarnos de 1600)
        for titulo, link in noticias:
            item_texto = f"📌 {titulo}\n🔗 {link}\n\n"
            # Si agregando este ítem superamos los 1550 caracteres, frenamos
            if len(mensaje_final) + len(item_texto) > 1550:
                mensaje_final += "⚠️ [Hay más noticias, pero se alcanzó el límite de WhatsApp]"
                break
            mensaje_final += item_texto

    cliente = Client(TWILIO_SID, TWILIO_TOKEN)
    cliente.messages.create(body=mensaje_final.strip(), from_=NUMERO_TWILIO, to=TU_CELULAR)
    print("Reporte optimizado enviado con éxito")

if __name__ == "__main__":
    enviar_reporte()
