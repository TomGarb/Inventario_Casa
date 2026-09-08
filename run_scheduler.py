import logging
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from app import app, check_low_stock, check_tareas_pendientes, enviar_resumen_matutino, cleanup_pending_commands, sync_eventos_deportivos_job

if __name__ == '__main__':
    logging.info("=========================================")
    logging.info("  Iniciando Microservicio: SCHEDULER     ")
    logging.info("=========================================")
    
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    scheduler = BlockingScheduler(timezone=tz)
    
    # Añadir los cron jobs usando las mismas funciones que app.py
    scheduler.add_job(func=check_low_stock, trigger="cron", minute="*")
    scheduler.add_job(func=check_tareas_pendientes, trigger="cron", hour=9, minute=0)
    scheduler.add_job(func=enviar_resumen_matutino, trigger="cron", hour=8, minute=0)
    scheduler.add_job(func=cleanup_pending_commands, trigger="interval", hours=1)
    scheduler.add_job(func=sync_eventos_deportivos_job, trigger="cron", day_of_week='mon', hour=3)
    
    logging.info("[Scheduler] Tareas cron programadas. Arrancando loop infinito...")
    # Bloquea el hilo y mantiene el contenedor vivo
    scheduler.start()
