import logging
import os
import calendar
import threading
import telebot
from google import genai
import base64
import json
import pytz
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from flask_wtf.csrf import CSRFProtect
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from extensions import db, login_manager, csrf, migrate, bot
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, date, timedelta, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import uuid
import re
import difflib
import random
import string
from functools import wraps

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
from flask_migrate import Migrate
migrate.init_app(app, db)

login_manager.init_app(app)
login_manager.login_view = 'auth.login_page'

# Asegúrate de importar el modelo de tu usuario si no está en este mismo archivo
# from models.database import Usuario 

@login_manager.user_loader
def load_user(user_id):
    # Cambia 'Usuario' por el nombre de tu clase en la base de datos (ej. User)
    return Usuario.query.get(int(user_id))

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
    allowed_routes = ['auth.login_page', 'auth.register_page', 'static']
    if request.endpoint not in allowed_routes and not current_user.is_authenticated:
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect(url_for('auth.login_page'))

# ==========================================
# 6. TAREAS PROGRAMADAS Y ARRANQUE
# ==========================================




def check_tareas_pendientes():
    with app.app_context():
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
                    if vencida:
                        enviar_al_usuario(u.id, f"📅 <b>Recordatorio de Tarea</b>\n\nHola {u.username}, hoy te toca encargarte de: <b>{t.nombre}</b>.\n\nCuando la termines, márcala como completada en la web.")
                    elif es_manana:
                        enviar_al_usuario(u.id, f"📅 <b>Aviso Anticipado</b>\n\nHola {u.username}, te recuerdo que <b>mañana</b> debes encargarte de: <b>{t.nombre}</b>.")

def check_low_stock():
    with app.app_context():
        productos_bajos = Producto.query.filter(Producto.stock_actual <= Producto.stock_minimo, Producto.en_lista == False).all()
        if productos_bajos and ADMIN_CHAT_ID:
            nombres = [p.nombre for p in productos_bajos]
            mensaje = f"⚠️ Atención: Te estás quedando sin: {', '.join(nombres)}. ¿Los agrego a la lista de compras?"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ Agregar todos a la lista", callback_data="add_low_stock"))
            safe_telegram_send(ADMIN_CHAT_ID, mensaje, reply_markup=markup)

# (Legacy iniciar_bot removed)

# ================= WSGI ARRANQUE SEGURO =================
# Usar un archivo de bloqueo para asegurar que solo un worker en Gunicorn/Waitress 
# inicie el bot de Telegram y el APScheduler.
LOCK_FILE = "bot_scheduler.lock"


    

def enviar_resumen_matutino():
    with app.app_context():
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
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Ver calendario web", url=f"{app_url}/logistica"))
        
        enviar_al_grupo(mensaje, reply_markup=markup)

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
    global pending_voice_commands, pending_ocr_confirmations
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
            scheduler.add_job(func=check_low_stock, trigger="cron", hour=10, minute=0)
            scheduler.add_job(func=check_tareas_pendientes, trigger="cron", hour=9, minute=0)
            scheduler.add_job(func=enviar_resumen_matutino, trigger="cron", hour=8, minute=0)
            scheduler.add_job(func=cleanup_pending_commands, trigger="interval", hours=1)
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

# ==========================================
# 12. ENDPOINTS NUEVOS MODULOS (STUBS) Y WEBHOOK
# ==========================================

from flask import request, abort
import telebot
from extensions import csrf

@app.route('/webhook/telegram', methods=['POST'])
@csrf.exempt
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

if __name__ == '__main__':
    # 3. Arrancar Flask de forma segura
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)