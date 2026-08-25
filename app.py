import logging
import os
import telebot
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, redirect, url_for, session
from extensions import db, login_manager, csrf, migrate, bot

from sqlalchemy import event, bindparam
from sqlalchemy.orm import with_loader_criteria
from contextvars import ContextVar
bot_tenant_var = ContextVar('bot_tenant_var', default=None)

def get_current_tenant_id():
    tenant_id = None
    try:
        from flask import request, session
        from flask_login import current_user
        if request:
            if session.get('current_casa_id'):
                tenant_id = int(session['current_casa_id'])
            elif current_user and current_user.is_authenticated and current_user.casa_activa_id:
                tenant_id = int(current_user.casa_activa_id)
    except Exception:
        pass
        
    if not tenant_id:
        val = bot_tenant_var.get()
        if val: tenant_id = int(val)
        
    return tenant_id if tenant_id else -1

tenant_param = bindparam('tenant_id', callable_=get_current_tenant_id)


from dotenv import load_dotenv
from datetime import datetime, timedelta
from flask_login import current_user

# ==========================================
# 1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================
import sys
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

load_dotenv()

app = Flask(__name__)
csrf.init_app(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-homestock-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///homestock.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres"):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
with app.app_context():
    @event.listens_for(db.session, "do_orm_execute")
    def _do_orm_execute(orm_execute_state):
        if not (orm_execute_state.is_select or orm_execute_state.is_update or orm_execute_state.is_delete):
            return
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                db.Model,
                lambda cls: cls.casa_id == tenant_param if hasattr(cls, 'casa_id') and cls.__name__ not in ['Casa', 'Usuario', 'UsuarioCasa', 'EventoLogistico'] else True,
                include_aliases=True
            )
        )
        
    @event.listens_for(db.mapper, "before_insert")
    def receive_before_insert(mapper, connection, target):
        if hasattr(target, 'casa_id') and target.__class__.__name__ not in ['Casa', 'Usuario', 'UsuarioCasa', 'EventoLogistico']:
            if not target.casa_id:
                t_id = get_current_tenant_id()
                if t_id > 0:
                    target.casa_id = t_id


migrate.init_app(app, db)

login_manager.init_app(app)
login_manager.login_view = 'auth.login_page'

# Importación de modelos
from models.database import Usuario, Tarea, Producto, EventoLogistico

@login_manager.user_loader
def load_user(user_id):
    # Cambia 'Usuario' por el nombre de tu clase en la base de datos (ej. User)
    return db.session.get(Usuario, int(user_id))

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
TELEGRAM_GROUP_ID = os.getenv('TELEGRAM_GROUP_ID')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', TELEGRAM_GROUP_ID)

from telebot import apihelper
apihelper.READ_TIMEOUT = 120
apihelper.CONNECT_TIMEOUT = 120

CHAT_ID = TELEGRAM_CHAT_ID

# ==========================================
# 5. RUTAS WEB Y API
# ==========================================

@app.before_request
def require_login():
    if request.path == '/webhook/telegram':
        return
    allowed_routes = ['auth.login_page', 'auth.register_page', 'static', 'main.tv_dashboard', 'main.get_tv_data']
    if request.endpoint not in allowed_routes and not current_user.is_authenticated:
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect(url_for('auth.login_page'))
        
    # Restricciones para el usuario Tablet
    
    if current_user.is_authenticated and not getattr(current_user, 'is_tablet', False):
        if 'current_casa_id' not in session and current_user.casa_activa_id:
            session['current_casa_id'] = current_user.casa_activa_id
            
        allowed_casa_routes = ['casas.seleccionar', 'casas.nueva', 'casas.api_casas', 'auth.logout_page', 'static']
        if not session.get('current_casa_id') and request.endpoint not in allowed_casa_routes and not request.path.startswith('/api/'):
            # Si no tiene casa y no va a una ruta permitida
            if current_user.casas_rel: # if they have houses
                session['current_casa_id'] = current_user.casas_rel[0].casa_id
                current_user.casa_activa_id = session['current_casa_id']
                db.session.commit()
            else:
                pass # Later redirect to select/create house

    if current_user.is_authenticated and getattr(current_user, 'is_tablet', False):
        allowed_tablet_endpoints = [
            'main.tablet_dashboard', 
            'main.get_tablet_data', 
            'tareas.completar_tarea',
            'inventario.actualizar_estado_lista',
            'inventario.consumir_rapido',
            'inventario.actualizar_stock',
            'menus.agregar_menu_manual',
            'logistica.api_logistica_post',
            'auth.logout_page',
            'static'
        ]
        if request.endpoint not in allowed_tablet_endpoints:
            return redirect(url_for('main.tablet_dashboard'))

# ==========================================
# 6. TAREAS PROGRAMADAS Y ARRANQUE
# ==========================================




from services.bot_telegram import enviar_al_usuario, safe_telegram_send

def check_tareas_pendientes():
    with app.app_context():
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        hoy = datetime.now().date()
        # Query only pending Tareas
        tareas = Tarea.query.filter_by(completada=False).all()
        for t in tareas:
            vencida = False
            es_manana = False
            
            proxima = t.fecha_programada or t.fecha_ultima_ejecucion
            if not proxima: continue
            
            if hoy >= proxima:
                vencida = True
            elif proxima == hoy + timedelta(days=1):
                es_manana = True
                
            if vencida or es_manana:
                for u in t.usuarios:
                    if not u.recibir_recordatorios_tareas:
                        continue
                        
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton(f"✅ Completar", callback_data=f"done_tarea_{t.id}"))
                    
                    if vencida:
                        enviar_al_usuario(u.id, f"📅 <b>Recordatorio de Tarea</b>\n\nHola {u.username}, hoy te toca encargarte de: <b>{t.nombre}</b>.\n\nCuando la termines, pulsa el botón de abajo o márcala como completada en la web.", reply_markup=markup)
                    elif es_manana:
                        enviar_al_usuario(u.id, f"📅 <b>Aviso Anticipado</b>\n\nHola {u.username}, te recuerdo que <b>mañana</b> debes encargarte de: <b>{t.nombre}</b>.", reply_markup=markup)

def check_low_stock():
    with app.app_context():
        from models.database import ConfiguracionGlobal
        config = ConfiguracionGlobal.query.first()
        
        hora_alerta = config.hora_alerta_stock if config and config.hora_alerta_stock else "10:00"
        import pytz
        from datetime import datetime
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        now = datetime.now(tz)
        if now.strftime("%H:%M") != hora_alerta:
            return
            
        grupo_id = config.grupo_principal_telegram_id if config and config.grupo_principal_telegram_id else ADMIN_CHAT_ID
        
        productos_bajos = Producto.query.filter(Producto.stock_actual <= Producto.stock_minimo, Producto.en_lista == False).all()
        if productos_bajos and grupo_id:
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            nombres = [p.nombre for p in productos_bajos]
            mensaje = f"⚠️ Atención: Te estás quedando sin: {', '.join(nombres)}. ¿Los agrego a la lista de compras?"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Agregar todos a la lista", callback_data="add_low_stock"))
            safe_telegram_send(grupo_id, mensaje, reply_markup=markup)

# (Legacy iniciar_bot removed)

# ================= WSGI ARRANQUE SEGURO =================
# Usar un archivo de bloqueo para asegurar que solo un worker en Gunicorn/Waitress 
# inicie el bot de Telegram y el APScheduler.
LOCK_FILE = "bot_scheduler.lock"


    

def enviar_resumen_matutino():
    with app.app_context():
        from models.database import Usuario, ConfiguracionGlobal
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        hoy = datetime.now(tz).date()
        
        # Buscar eventos de hoy
        eventos = EventoLogistico.query.filter(
            db.func.date(EventoLogistico.fecha_inicio) == hoy
        ).order_by(EventoLogistico.fecha_inicio.asc()).all()
        
        if not eventos:
            return
            
        mensaje = "🌅 ¡Buen día! Logística para hoy:\n"
        for ev in eventos:
            hora = ev.fecha_inicio.strftime("%H:%M")
            mensaje += f"- {hora}hs: {ev.titulo}\n"
            
        app_url = os.getenv('APP_URL', 'http://localhost:5000')
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Ver calendario web", url=f"{app_url}/logistica"))
        
        # Enviar al grupo principal
        config = ConfiguracionGlobal.query.first()
        grupo_id = config.grupo_principal_telegram_id if config and config.grupo_principal_telegram_id else ADMIN_CHAT_ID
        if grupo_id:
            safe_telegram_send(grupo_id, mensaje, reply_markup=markup)
            
        # Enviar a usuarios con la preferencia activada
        usuarios = Usuario.query.filter_by(recibir_resumen_matutino=True).all()
        for u in usuarios:
            if u.telegram_chat_id and u.telegram_chat_id != grupo_id:
                enviar_al_usuario(u.id, mensaje, reply_markup=markup)

def _pid_vivo(pid):
    """Devuelve True si el PID todavia esta corriendo en este sistema Y no es un archivo stale."""
    try:
        pid_int = int(pid)
        if pid_int == os.getpid():
            return True
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid_int)
        if handle == 0:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False

def cleanup_pending_commands():
    """Limpia los comandos pendientes que quedaron huerfanos."""
    from services.bot_telegram import (
        pending_voice_commands, 
        pending_menu_config, 
        pending_ocr_confirmations, 
        pending_dedup
    )
    pending_voice_commands.clear()
    pending_menu_config.clear()
    pending_ocr_confirmations.clear()
    pending_dedup.clear()

def configurar_bot_telegram():
    if bot:
        logging.info("[Bot Telemetría] Configurando bot de Telegram...")
        try:
            from telebot.types import BotCommand
            comandos = [
                BotCommand("start", "Inicia el bot y verifica el estado"),
                BotCommand("vincular", "Conecta tu cuenta de HomeStock"),
                BotCommand("desvincular", "Desconecta este chat de tu cuenta"),
                BotCommand("menu", "Abre el menú interactivo"),
                BotCommand("compras", "Muestra la lista de compras pendiente"),
                BotCommand("ayuda", "Muestra los comandos disponibles")
            ]
            bot.set_my_commands(comandos)
        except Exception as ec:
            print(f"Error configurando comandos en Telegram: {ec}")
            
        try:
            print("🟢 CONFIGURANDO WEBHOOK DE TELEGRAM...")
            bot.remove_webhook()
            WEBHOOK_URL = "https://inventario-casa-m8an.onrender.com/webhook/telegram"
            bot.set_webhook(url=WEBHOOK_URL)
            logging.info(f"[Bot Telemetría] Webhook configurado con éxito en: {WEBHOOK_URL}")
        except Exception as e:
            print(f"🔴 ERROR FATAL AL CONFIGURAR WEBHOOK: {e}")
            logging.error(f"[Bot Telemetría] Error crítico configurando Webhook: {e}", exc_info=True)

# ================= WSGI ARRANQUE SEGURO =================
LOCK_FILE = "bot_scheduler.lock"

import atexit
def _limpiar_lock():
    if os.path.exists(LOCK_FILE):
        try:
            pid = open(LOCK_FILE).read().strip()
            if int(pid) == os.getpid():
                os.remove(LOCK_FILE)
        except Exception:
            pass
atexit.register(_limpiar_lock)

def seed_suscripciones():
    """Inyecta suscripciones deportivas iniciales si la tabla está vacía."""
    with app.app_context():
        from models.database import SuscripcionDeporte, Usuario
        import sqlalchemy
        try:
            if SuscripcionDeporte.query.first() is not None:
                return  # Ya hay datos
            
            admin = Usuario.query.filter_by(is_admin=True).first()
            if not admin:
                admin = Usuario.query.first()
            if not admin:
                logging.warning("[Seed] No hay usuarios para asignar suscripciones deportivas.")
                return
            
            seeds = [
                # Equipos
                {'nombre': 'San Lorenzo', 'external_api_id': '135173', 'tipo': 'equipo', 'color': '#0a1f44'},
                {'nombre': 'River Plate', 'external_api_id': '135171', 'tipo': 'equipo', 'color': '#e60000'},
                {'nombre': 'Scuderia Ferrari HP', 'external_api_id': '134806', 'tipo': 'equipo', 'color': '#ff2800'},
                {'nombre': 'Argentina', 'external_api_id': '134509', 'tipo': 'equipo', 'color': '#75aadb'},
                {'nombre': 'Bayern Munich', 'external_api_id': '133664', 'tipo': 'equipo', 'color': '#dc052d'},
                {'nombre': 'Chelsea', 'external_api_id': '133610', 'tipo': 'equipo', 'color': '#034694'},
                # Ligas
                {'nombre': 'Formula 1', 'external_api_id': '4370', 'tipo': 'liga', 'color': '#e10600'},
                {'nombre': 'UEFA Champions League', 'external_api_id': '4480', 'tipo': 'liga', 'color': '#0e1e5b'},
                {'nombre': 'NBA', 'external_api_id': '4387', 'tipo': 'liga', 'color': '#c9082a'},
            ]
            
            for s in seeds:
                db.session.add(SuscripcionDeporte(
                    usuario_id=admin.id, 
                    casa_id=admin.casa_activa_id,
                    **s
                ))
            
            db.session.commit()
            logging.info(f"[Seed] {len(seeds)} suscripciones deportivas inyectadas para {admin.username}.")
        except sqlalchemy.exc.ProgrammingError:
            db.session.rollback()
            logging.info("[Seed] La tabla SuscripcionDeporte no existe aún, saltando inyección de datos (probablemente durante migración).")
        except Exception as e:
            db.session.rollback()
            logging.warning(f"[Seed] Error inyectando datos semilla: {e}")

def sync_eventos_deportivos_job():
    """Wrapper para ejecutar la sincronización deportiva desde el scheduler."""
    from services.api_eventos import sync_eventos_deportivos
    sync_eventos_deportivos(app)

def start_background_tasks():
    lock_activo = False
    if os.path.exists(LOCK_FILE):
        try:
            pid_guardado = open(LOCK_FILE).read().strip()
            if _pid_vivo(pid_guardado) and int(pid_guardado) != os.getpid():
                lock_activo = True
            else:
                logging.info(f"[Bot] Lock stale o PID reciclado ({pid_guardado}). Limpiando y reiniciando...")
                os.remove(LOCK_FILE)
        except Exception as e_lock:
            logging.warning(f"[Bot] Error comprobando lock: {e_lock}")
            if os.path.exists(LOCK_FILE):
                try:
                    os.remove(LOCK_FILE)
                except Exception:
                    pass

    if not lock_activo:
        try:
            with open(LOCK_FILE, "w") as f:
                f.write(str(os.getpid()))

            logging.info(f"Worker {os.getpid()} está iniciando background scheduler y configurando el bot...")
            configurar_bot_telegram()

            tz = pytz.timezone('America/Argentina/Buenos_Aires')
            scheduler = BackgroundScheduler(timezone=tz)
            scheduler.add_job(func=check_low_stock, trigger="cron", minute="*")
            scheduler.add_job(func=check_tareas_pendientes, trigger="cron", hour=9, minute=0)
            scheduler.add_job(func=enviar_resumen_matutino, trigger="cron", hour=8, minute=0)
            scheduler.add_job(func=cleanup_pending_commands, trigger="interval", hours=1)
            scheduler.add_job(func=sync_eventos_deportivos_job, trigger="cron", day_of_week='mon', hour=3)
            scheduler.start()
            logging.info("[Scheduler] Tareas cron de fondo iniciadas correctamente.")
        except Exception as e:
            logging.error(f"[Scheduler/Bot] Error al iniciar tareas de fondo: {e}", exc_info=True)

from routes import register_blueprints
register_blueprints(app)
from services.bot_telegram import registrar_handlers
if bot:
    registrar_handlers(bot, app)

# Intentar arrancar tareas de fondo solo una vez (compatible con WSGI)
start_background_tasks()

# Seed data después de arranque
seed_suscripciones()

# ==========================================
# 12. ENDPOINTS NUEVOS MODULOS (STUBS) Y WEBHOOK
# ==========================================

from flask import request, abort
import telebot
from extensions import csrf

@app.route('/webhook/telegram', methods=['POST'])
@csrf.exempt
def telegram_webhook():
    print(">>> UPDATE RECIBIDO EN WEBHOOK")
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        print(f">>> UPDATE PARSEADO: {update}")
        print(f">>> HANDLERS DEL BOT: {len(bot.message_handlers)}")
        bot.process_new_updates([update])
        return "OK", 200
    else:
        abort(403)

if __name__ == '__main__':
    # 3. Arrancar Flask de forma segura
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)