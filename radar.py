import os
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client

# Credenciales ocultas (las configuramos en el siguiente paso)
TWILIO_SID = os.environ.get('TWILIO_SID')
TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN')
NUMERO_TWILIO = 'whatsapp:+14155238886' # Reemplazá si Twilio te dio otro
TU_CELULAR = os.environ.get('TU_CELULAR')

FUENTES = ["https://www.infobae.com/", "https://www.ambito.com/", "https://www.clarin.com/", "https://www.pagina12.com.ar/"]
KEYWORDS = ["dólar", "economía", "industria", "macro", "finanzas", "bonos", "energía", "riesgo país", "metalúrgica", "pymes", "rigi", "vaca muerta", "inflación", "tarifas", "bcra", "insumos", "capacidad instalada"]

def obtener_noticias():
    resumen = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in FUENTES:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            sopa = BeautifulSoup(r.text, 'html.parser')
            for e in sopa.find_all('a'):
                titulo = e.get_text().strip()
                link = e.get('href', '')
                if len(titulo) > 25 and any(k in titulo.lower() for k in KEYWORDS):
                    full_link = link if link.startswith('http') else url.rstrip('/') + link
                    resumen.append(f"📌 {titulo}\n🔗 {full_link}")
        except: continue
    # Eliminamos duplicados y limitamos a 10 noticias
    return list(set(resumen))[:5]

def enviar_reporte():
    noticias = obtener_noticias()
    if not noticias:
        texto = "🤖 *Radar Económico Diario*\n\nHoy no encontré noticias relevantes con tus palabras clave."
    else:
        texto = "🤖 *Radar Económico Diario*\n\n" + "\n\n".join(noticias)
        
    # Cortamos el mensaje si supera los 1500 caracteres por seguridad
    if len(texto) > 1500:
        texto = texto[:1500] + "\n\n... [Mensaje acortado por límite de caracteres]"
        
    cliente = Client(TWILIO_SID, TWILIO_TOKEN)
    cliente.messages.create(body=texto, from_=NUMERO_TWILIO, to=TU_CELULAR)
    print("Mensaje enviado con éxito")

if __name__ == "__main__":
    enviar_reporte()
