"""
Servicio de sincronización de eventos deportivos desde TheSportsDB.
Usa la API key pública "1" para consultar próximos partidos de equipos y ligas.
"""
import requests
import logging
from datetime import datetime
from extensions import db

SPORTS_API_BASE = "https://www.thesportsdb.com/api/v1/json/3"

def sync_eventos_deportivos(app):
    """
    Itera sobre las suscripciones deportivas y crea EventoLogistico
    para cada partido/evento futuro que no exista aún en la BD.
    """
    with app.app_context():
        from models.database import SuscripcionDeporte, EventoLogistico
        
        suscripciones = SuscripcionDeporte.query.all()
        if not suscripciones:
            logging.info("[SportsSync] No hay suscripciones deportivas configuradas.")
            return
        
        creados = 0
        existentes = 0
        errores = 0
        
        for sub in suscripciones:
            try:
                # Elegir endpoint según tipo
                if sub.tipo == 'equipo':
                    url = f"{SPORTS_API_BASE}/eventsnext.php?id={sub.external_api_id}"
                elif sub.tipo == 'liga':
                    url = f"{SPORTS_API_BASE}/eventsnextleague.php?id={sub.external_api_id}"
                else:
                    logging.warning(f"[SportsSync] Tipo desconocido: {sub.tipo} para {sub.nombre}")
                    continue
                
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                eventos = data.get('events') or []
                
                for evento in eventos:
                    nombre_evento = evento.get('strEvent', 'Evento Deportivo')
                    fecha_str = evento.get('dateEvent', '')
                    hora_str = evento.get('strTime', '00:00:00')
                    
                    if not fecha_str:
                        continue
                    
                    # Parsear fecha y hora a hora de Argentina (UTC-3)
                    try:
                        timestamp_str = evento.get('strTimestamp')
                        if timestamp_str:
                            # strTimestamp suele venir en formato "2026-09-01T00:15:00" y es UTC
                            utc_dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
                            fecha_hora = utc_dt - timedelta(hours=3)
                        elif hora_str and hora_str != '00:00:00':
                            utc_dt = datetime.strptime(f"{fecha_str} {hora_str[:5]}", "%Y-%m-%d %H:%M")
                            fecha_hora = utc_dt - timedelta(hours=3)
                        else:
                            fecha_hora = datetime.strptime(fecha_str, "%Y-%m-%d")
                    except (ValueError, TypeError):
                        fecha_hora = datetime.strptime(fecha_str, "%Y-%m-%d")
                    
                    # Título con prefijo de la suscripción
                    titulo = f"[{sub.nombre}] {nombre_evento}"
                    
                    # Truncar a 100 chars (límite del modelo)
                    if len(titulo) > 100:
                        titulo = titulo[:97] + "..."
                    
                    # Verificar si ya existe
                    existe = EventoLogistico.query.filter(
                        EventoLogistico.titulo == titulo,
                        db.func.date(EventoLogistico.fecha_inicio) == fecha_hora.date()
                    ).first()
                    
                    if existe:
                        existentes += 1
                        continue
                    
                    # Crear el evento
                    nuevo = EventoLogistico(
                        titulo=titulo,
                        descripcion=f"Evento deportivo sincronizado automáticamente desde TheSportsDB ({sub.tipo}: {sub.nombre})",
                        fecha_inicio=fecha_hora,
                        creador_id=sub.usuario_id,
                        color=sub.color,
                        frecuencia='none'
                    )
                    db.session.add(nuevo)
                    creados += 1
                    
            except requests.exceptions.RequestException as e:
                logging.error(f"[SportsSync] Error de red para {sub.nombre}: {e}")
                errores += 1
            except Exception as e:
                logging.error(f"[SportsSync] Error procesando {sub.nombre}: {e}")
                errores += 1
        
        if creados > 0:
            db.session.commit()
            
        logging.info(f"[SportsSync] Sincronización completada: {creados} creados, {existentes} ya existían, {errores} errores.")
