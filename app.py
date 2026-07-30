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

pending_voice_commands = {}
recent_transactions = {}
pending_ocr_confirmations = {}  # {chat_id: {usuario_id, monto_total, descripcion}}
pending_menu_config = {}  # {chat_id: (dia, tipo)}
pending_dedup = {}  # {chat_id: {sim_id, sim_nombre, new_nombre, cantidad, ubicacion_id}}
# ==========================================
# 3. HELPERS Y UTILIDADES
# ==========================================

def calcular_balances_globales():
    # Devuelve una lista de diccionarios con el balance simplificado
    with app.app_context():
        divisiones = DivisionGasto.query.filter_by(esta_pagado=False).all()
        # deudas[deudor_id][acreedor_id] = monto
        from collections import defaultdict
        deudas = defaultdict(lambda: defaultdict(float))
        
        for div in divisiones:
            deudor = div.usuario_id
            acreedor = div.rel_gasto.usuario_id
            if deudor != acreedor:
                deudas[deudor][acreedor] += div.monto_adeudado
                
        # Simplificar deudas cruzadas
        usuarios_ids = list(deudas.keys())
        for deudor in usuarios_ids:
            for acreedor in list(deudas[deudor].keys()):
                # Si el acreedor tambien le debe al deudor
                if deudor in deudas[acreedor]:
                    deuda_ida = deudas[deudor][acreedor]
                    deuda_vuelta = deudas[acreedor][deudor]
                    
                    if deuda_ida > deuda_vuelta:
                        deudas[deudor][acreedor] -= deuda_vuelta
                        del deudas[acreedor][deudor]
                    elif deuda_vuelta > deuda_ida:
                        deudas[acreedor][deudor] -= deuda_ida
                        del deudas[deudor][acreedor]
                    else:
                        del deudas[deudor][acreedor]
                        del deudas[acreedor][deudor]
                        
        # Formatear salida
        resultado = []
        for deudor_id, deudores_dict in deudas.items():
            for acreedor_id, monto in deudores_dict.items():
                u_deudor = db.session.get(Usuario, deudor_id)
                u_acreedor = db.session.get(Usuario, acreedor_id)
                if u_deudor and u_acreedor and monto > 0:
                    resultado.append({
                        'deudor_id': deudor_id,
                        'deudor_nombre': u_deudor.username,
                        'acreedor_id': acreedor_id,
                        'acreedor_nombre': u_acreedor.username,
                        'monto': round(monto, 2)
                    })
        return resultado


def formatear_fecha_amigable(f_val):
    if not f_val: return ""
    try:
        if isinstance(f_val, str):
            clean_str = re.sub(r'([+-]\d{2}:?\d{2}|Z)$', '', f_val.strip())
            dt = None
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(clean_str[:len("2026-08-15T15:00:00")[:len(clean_str)]], fmt)
                    break
                except:
                    continue
            if not dt:
                try:
                    dt = datetime.fromisoformat(clean_str)
                except:
                    return str(f_val)
        elif isinstance(f_val, datetime):
            dt = f_val
        elif isinstance(f_val, date):
            return f_val.strftime('%d/%m/%Y')
        else:
            return str(f_val)
        return dt.strftime('%d/%m/%Y a las %H:%M hs.')
    except Exception:
        return str(f_val)

def extraer_datos_evento(texto, chat_id=None):
    if not GEMINI_API_KEY:
        return None
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        fecha_actual = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        
        prompt = f"Eres un asistente de calendario. Hoy es {fecha_actual} (Hora de Buenos Aires). Analiza este mensaje y extrae los detalles del evento. Devuelve EXCLUSIVAMENTE un JSON con las claves: 'titulo' (resumen corto), 'fecha_inicio' (formato ISO 8601), 'fecha_fin' (formato ISO 8601, si aplica), y 'descripcion'. No uses markdown."
        
        response = model.generate_content([prompt, texto], )
        resultado_str = response.text.strip()
        
        if resultado_str.startswith('```json'):
            resultado_str = resultado_str.replace('```json', '').replace('```', '').strip()
        elif resultado_str.startswith('```'):
            resultado_str = resultado_str.replace('```', '').strip()
            
        return json.loads(resultado_str)
    except Exception as e:
        if check_api_quota_error(e, chat_id):
            return "ERROR_CUOTA"
        import logging
        logging.error(f"Error al procesar el evento con la IA: {e}", exc_info=True)
        raise e

def safe_telegram_reply(message, texto, reply_markup=None, parse_mode=None):
    if not bot:
        return False
    if parse_mode == 'Markdown':
        texto = texto.replace('**', '*')
    try:
        bot.reply_to(message, texto, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        err_str = str(e).lower()
        if "can't parse entities" in err_str and parse_mode:
            print(f"⚠️ Aviso: Falló el parseo {parse_mode} en reply, enviando como texto plano. Error: {e}")
            try:
                bot.reply_to(message, texto, reply_markup=reply_markup, parse_mode=None)
                return True
            except Exception as e2:
                print(f"Error enviando reply plano a {message.chat.id}: {e2}")
                return False
        print(f"Error respondiendo a {message.chat.id}: {e}")
        return False

# ==========================================
# 4. LÓGICA DE TELEGRAM
# ==========================================

import threading
def _enviar_al_grupo_sync(mensaje, parse_mode):
    if TELEGRAM_GROUP_ID:
        safe_telegram_send(TELEGRAM_GROUP_ID, mensaje, parse_mode=parse_mode)

def enviar_al_grupo(mensaje, parse_mode='HTML'):
    threading.Thread(target=_enviar_al_grupo_sync, args=(mensaje, parse_mode)).start()

def _enviar_al_usuario_sync(usuario_id, mensaje, parse_mode):
    with app.app_context():
        u = db.session.get(Usuario, usuario_id)
        if u and u.telegram_chat_id:
            safe_telegram_send(u.telegram_chat_id, mensaje, parse_mode=parse_mode)
        else:
            # Fallback to group
            if u:
                fallback_msg = f"@{u.username} (Aviso: No tienes vinculado tu chat privado)\n{mensaje}"
            else:
                fallback_msg = mensaje
            _enviar_al_grupo_sync(fallback_msg, parse_mode)

def enviar_al_usuario(usuario_id, mensaje, parse_mode='HTML'):
    threading.Thread(target=_enviar_al_usuario_sync, args=(usuario_id, mensaje, parse_mode)).start()


if bot:
    def is_authorized(user_id):
        with app.app_context():
            user = Usuario.query.filter_by(telegram_chat_id=str(user_id)).first()
            return user is not None


def procesar_compras_texto(texto, message):
    pending_voice_commands[message.chat.id] = (texto, datetime.now(), 'compras')
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Confirmar", callback_data="confirm_voice"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_voice")
    )
    tipo_msg = "🎙️ Escuché" if message.content_type == 'voice' else "📩 Recibí"
    safe_telegram_send(message.chat.id, f"{tipo_msg}:\n\n_{texto}_\n\n¿Añadir a la **Lista de Compras**?", reply_markup=markup, parse_mode="Markdown")

def procesar_tareas_texto(texto, message):
    pending_voice_commands[message.chat.id] = (texto, datetime.now(), 'tarea')
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Confirmar", callback_data="confirm_voice"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_voice")
    )
    tipo_msg = "🎙️ Escuché" if message.content_type == 'voice' else "📩 Recibí"
    safe_telegram_send(message.chat.id, f"{tipo_msg}:\n\n_{texto}_\n\n¿Registrar **Tarea** completada?", reply_markup=markup, parse_mode="Markdown")

def guardar_menu_desde_bot(chat_id, dia_semana, tipo_comida, nombre):
    try:
        with app.app_context():
            receta = Receta.query.filter(Receta.nombre.ilike(f"%{nombre}%")).first()
            if not receta:
                receta = Receta(nombre=nombre, tipo=tipo_comida, es_rapida=True)
                db.session.add(receta)
                db.session.flush()

            dias_es = {'Lunes':0, 'Martes':1, 'Miércoles':2, 'Jueves':3, 'Viernes':4, 'Sábado':5, 'Domingo':6,
                       'LUNES':0, 'MARTES':1, 'MIÉRCOLES':2, 'MIERCOLES':2, 'JUEVES':3, 'VIERNES':4, 'SÁBADO':5, 'SABADO':5, 'DOMINGO':6}
            dia_clean = dia_semana.capitalize()
            if dia_clean == 'Miercoles': dia_clean = 'Miércoles'
            if dia_clean == 'Sabado': dia_clean = 'Sábado'

            hoy = date.today()
            dia_actual_idx = hoy.weekday()
            target_idx = dias_es.get(dia_clean, 0)
            delta = target_idx - dia_actual_idx
            fecha_asignada = hoy + timedelta(days=delta)

            existente = MenuSemanal.query.filter_by(
                dia_semana=dia_clean,
                tipo_comida=tipo_comida,
                fecha_asignada=fecha_asignada
            ).first()

            if existente:
                db.session.delete(existente)
                db.session.flush()

            nuevo_menu = MenuSemanal(
                dia_semana=dia_clean,
                tipo_comida=tipo_comida,
                receta_id=receta.id,
                fecha_asignada=fecha_asignada
            )
            db.session.add(nuevo_menu)
            db.session.commit()
            safe_telegram_send(chat_id, f"✅ ¡Listo! Guardé **{nombre}** para el **{tipo_comida}** del **{dia_clean}**.", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"[Menú Bot] Error al guardar menú: {e}", exc_info=True)
        safe_telegram_send(chat_id, f"❌ Error al guardar en el menú: {e}")

def procesar_menu_config(message):
    markup = InlineKeyboardMarkup(row_width=2)
    dias = [
        ("Lunes", "menu_dia_lunes"),
        ("Martes", "menu_dia_martes"),
        ("Miércoles", "menu_dia_miercoles"),
        ("Jueves", "menu_dia_jueves"),
        ("Viernes", "menu_dia_viernes"),
        ("Sábado", "menu_dia_sabado"),
        ("Domingo", "menu_dia_domingo")
    ]
    botones = [InlineKeyboardButton(nombre, callback_data=cb) for nombre, cb in dias]
    markup.add(*botones)
    markup.add(InlineKeyboardButton("🛒 Ver Lista de Compras", callback_data="ver_compras"))
    safe_telegram_send(message.chat.id, "📅 Configuración de Menús.\nSelecciona el día que deseas planificar:", reply_markup=markup)

def procesar_evento_texto(texto, message):
    import logging
    try:
        datos_evento = extraer_datos_evento(texto, message.chat.id)
        if datos_evento == "ERROR_CUOTA":
            return
        if datos_evento and 'titulo' in datos_evento and 'fecha_inicio' in datos_evento:
            pending_voice_commands[message.chat.id] = (datos_evento, datetime.now(), 'logistica')
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("✅ Sí", callback_data="confirm_logistica"),
                InlineKeyboardButton("❌ No", callback_data="cancel_logistica")
            )
            safe_telegram_send(message.chat.id, f"📅 Entendido. Agendar: *{datos_evento['titulo']}* para el {formatear_fecha_amigable(datos_evento['fecha_inicio'])}. ¿Confirmas?", reply_markup=markup, parse_mode="Markdown")
        else:
            logging.error(f"[Módulo Logística] Datos extraídos incompletos o nulos: {datos_evento}")
            safe_telegram_send(message.chat.id, "❌ Error al procesar el evento con la IA")
    except Exception as e:
        logging.error(f"[Módulo Logística] Error al procesar el evento con la IA: {e}", exc_info=True)
        safe_telegram_send(message.chat.id, "❌ Error al procesar el evento con la IA")

def procesar_recetas_texto(texto, message):
    import logging
    safe_telegram_reply(message, " Consultando inventario y pensando una receta...")
    try:
        with app.app_context():
            productos = Producto.query.filter(Producto.stock_actual > 0).all()
            ingredientes = [f"{p.nombre} ({p.stock_actual})" for p in productos]
            inv_str = ", ".join(ingredientes) if ingredientes else "No hay ingredientes registrados en inventario actualmente."
            
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""
A partir de la siguiente receta, genera una lista de los ingredientes exactos que faltan (ingredientes_faltantes).
Devuelve ÚNICAMENTE un JSON válido con esta estructura, sin comentarios ni formato markdown extra:
[
  {{"nombre": "Tomate", "cantidad": "2 unidades", "categoria": "Verduras"}},
  {{"nombre": "Queso", "cantidad": "200g", "categoria": "Lácteos"}}
]

Si la receta no tiene ingredientes faltantes, devuelve [].

Receta:
{receta_json}
"""
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            safe_telegram_send(message.chat.id, response.text.strip(), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"[Mdulo Recetas] Error generando receta: {e}", exc_info=True)
        safe_telegram_send(message.chat.id, " Error al generar la receta. Intenta nuevamente.")

def procesar_inventario_texto(texto, message):
    pending_voice_commands[message.chat.id] = (texto, datetime.now(), 'inventario')
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Confirmar", callback_data="confirm_voice"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_voice")
    )
    tipo_msg = "🎙️ Escuché" if message.content_type == 'voice' else "📩 Recibí"
    safe_telegram_send(message.chat.id, f"{tipo_msg}:\n\n_{texto}_\n\n¿Procesar esta instrucción?", reply_markup=markup, parse_mode="Markdown")

def handle_logistica_callback(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    
    if call.data == 'cancel_logistica':
        pending_voice_commands.pop(call.message.chat.id, None)
        safe_telegram_send(call.message.chat.id, "❌ Agendamiento cancelado.")
        return
        
    pending_data = pending_voice_commands.pop(call.message.chat.id, None)
    if not pending_data or len(pending_data) != 3 or pending_data[2] != 'logistica':
        safe_telegram_send(call.message.chat.id, "⚠️ La solicitud ha expirado o ya fue procesada.")
        return
        
    datos_evento = pending_data[0]
    
    try:
        with app.app_context():
            user = Usuario.query.filter_by(telegram_chat_id=str(call.from_user.id)).first()
            if not user:
                safe_telegram_send(call.message.chat.id, "❌ Usuario no autorizado.")
                return
            
            # Parsear ISO 8601 a DateTime. Gemini a veces da YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS
            def parse_fecha(f_str):
                if not f_str: return None
                try:
                    return datetime.fromisoformat(f_str.replace('Z', '+00:00'))
                except:
                    try:
                        # Intento extra manual si falla fromisoformat
                        return datetime.strptime(f_str[:19], "%Y-%m-%dT%H:%M:%S")
                    except:
                        try:
                            return datetime.strptime(f_str[:10], "%Y-%m-%d")
                        except:
                            return None
                            
            f_inicio = parse_fecha(datos_evento.get('fecha_inicio'))
            f_fin = parse_fecha(datos_evento.get('fecha_fin'))
            if not f_inicio:
                safe_telegram_send(call.message.chat.id, "❌ Error parseando la fecha de inicio del evento.")
                return
                
            nuevo_evento = EventoLogistico(
                titulo=datos_evento.get('titulo'),
                descripcion=datos_evento.get('descripcion', ''),
                fecha_inicio=f_inicio,
                fecha_fin=f_fin,
                creador_id=user.id
            )
            db.session.add(nuevo_evento)
            db.session.commit()
            
            safe_telegram_send(call.message.chat.id, f"✅ Agendado para el {formatear_fecha_amigable(f_inicio)}:\n*{datos_evento.get('titulo')}*", parse_mode="Markdown")
    except Exception as e:
        print(f"Error guardando evento: {e}")
        safe_telegram_send(call.message.chat.id, f"❌ Error interno al guardar: {e}")

def handle_menu_callback(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

    if call.data.startswith('menu_dia_'):
        dia = call.data.split('_')[-1].capitalize()
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton(f"☕ Desayuno ({dia})", callback_data=f"menu_tipo_{dia}_Desayuno"),
            InlineKeyboardButton(f"☀️ Almuerzo ({dia})", callback_data=f"menu_tipo_{dia}_Almuerzo"),
            InlineKeyboardButton(f"🥞 Merienda ({dia})", callback_data=f"menu_tipo_{dia}_Merienda"),
            InlineKeyboardButton(f"🌙 Cena ({dia})", callback_data=f"menu_tipo_{dia}_Cena")
        )
        safe_telegram_send(call.message.chat.id, f"🍽️ Planificando para el **{dia}**.\n¿Qué comida deseas configurar?", reply_markup=markup, parse_mode="Markdown")
        return

    if call.data.startswith('menu_tipo_'):
        partes = call.data.split('_')
        dia, tipo = partes[2], partes[3]
        pending_menu_config[call.message.chat.id] = (dia, tipo)
        safe_telegram_send(call.message.chat.id, f"✍️ Ingresa el nombre de la receta o plato para el **{tipo}** del **{dia}** (ej. 'Milanesas con puré'):", parse_mode="Markdown")
        return
    
    if call.data == 'cancel_menu':
        pending_voice_commands.pop(call.message.chat.id, None)
        pending_menu_config.pop(call.message.chat.id, None)
        safe_telegram_send(call.message.chat.id, "❌ Sugerencia cancelada.")
        return
        
    pending_data = pending_voice_commands.pop(call.message.chat.id, None)
    if not pending_data or len(pending_data) != 3 or pending_data[2] != 'menu':
        safe_telegram_send(call.message.chat.id, "⚠️ La solicitud ha expirado o ya fue procesada.")
        return
        
    receta_id = pending_data[0]
    
    try:
        with app.app_context():
            receta = db.session.get(Receta, receta_id)
            if not receta:
                safe_telegram_send(call.message.chat.id, "❌ No se encontró la receta.")
                return
            
            # Infer meal type based on current time
            tz = pytz.timezone('America/Argentina/Buenos_Aires')
            ahora = datetime.now(tz).time()
            
            horarios = HorarioComidas.query.all()
            tipo_inferido = "Cena" # Default
            for h in horarios:
                if h.hora_inicio <= ahora <= h.hora_fin:
                    tipo_inferido = h.tipo_comida
                    break
            
            # Consume ingredients
            if consumir_receta(receta_id):
                # Guardar en menu semanal
                nuevo_menu = MenuSemanal(
                    dia_semana=datetime.now(tz).strftime('%A'), # Not perfectly mapped to Spanish but ok for model
                    tipo_comida=tipo_inferido,
                    receta_id=receta.id,
                    fecha_asignada=datetime.now(tz).date()
                )
                db.session.add(nuevo_menu)
                db.session.commit()
                safe_telegram_send(call.message.chat.id, f"✅ ¡Excelente! He descontado los ingredientes de *{receta.nombre}* y la registré como tu {tipo_inferido} de hoy.", parse_mode="Markdown")
            else:
                safe_telegram_send(call.message.chat.id, "❌ Error consumiendo receta.")
    except Exception as e:
        print(f"Error procesando menu: {e}")
        safe_telegram_send(call.message.chat.id, f"❌ Error interno: {e}")

def callback_voice(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    
    if call.data == 'cancel_voice':
        pending_voice_commands.pop(call.message.chat.id, None)
        safe_telegram_send(call.message.chat.id, "❌ Operación cancelada.")
        return
        
    pending_data = pending_voice_commands.pop(call.message.chat.id, None)
    if not pending_data:
        safe_telegram_send(call.message.chat.id, "⚠️ La solicitud ha expirado o ya fue procesada.")
        return
        
    intencion_previa = None
    if isinstance(pending_data, tuple):
        texto_transcrito = pending_data[0]
        if len(pending_data) >= 3:
            intencion_previa = pending_data[2]
    else:
        texto_transcrito = pending_data
    texto_lower = texto_transcrito.lower()
    
    num_map = {
        'un': 1, 'una': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
        'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
        'diez': 10, 'once': 11, 'doce': 12, 'media': 0.5, 'medio': 0.5,
        'quince': 15, 'veinte': 20, 'treinta': 30
    }
    
    rama = None
    texto_sin_accion = texto_lower
    
    match_inv = re.search(r'(agregar|añadir|compré|compre|comprado|sumar|meté|mete)\s+(.*)', texto_lower)
    match_comp = re.search(r'(comprar|falta|faltan|necesito|necesitamos)\s+(.*)', texto_lower)
    match_resta = re.search(r'(gasté|gaste|consumí|consumi|usé|use|comí|comi|saqué|saque|quité|quite)\s+(.*)', texto_lower)
    match_tarea = re.search(r'(hice|terminé|termine|limpié|limpie|saqué|saque)\s+(.*)', texto_lower)
    
    if match_inv:
        rama = "inventario"
        texto_sin_accion = match_inv.group(2)
    elif match_comp:
        rama = "compras"
        texto_sin_accion = match_comp.group(2)
    elif match_resta:
        rama = "restar"
        texto_sin_accion = match_resta.group(2)
    elif match_tarea:
        rama = "tarea"
        texto_sin_accion = match_tarea.group(2)
        
    if not rama:
        if intencion_previa in ["compras", "tarea"]:
            rama = intencion_previa
        else:
            rama = "inventario"
        texto_sin_accion = texto_lower
        
    texto_limpio = texto_sin_accion.replace(" y ", ",").replace(" e ", ",")
    articulos_raw = [a.strip() for a in texto_limpio.split(",") if a.strip()]
    
    if not articulos_raw:
        safe_telegram_send(call.message.chat.id, "❌ No logré detectar qué artículos quieres procesar.")
        return

    respuestas = []
    tx_id = str(uuid.uuid4())
    recent_transactions[tx_id] = []

    try:
        with app.app_context():
            try:
                for item_texto in articulos_raw:
                    match_item = re.search(r'^(?:(\d+(?:\.\d+)?|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|media|medio|quince|veinte|treinta)\s+)?(?:(?:de|kilos? de|litros? de|paquetes? de|gramos? de)\s+)?(.*)$', item_texto)
                    
                    if not match_item:
                        cantidad = 1.0
                        resto_texto = item_texto
                    else:
                        cantidad_str = match_item.group(1)
                        if cantidad_str:
                            if cantidad_str.isdigit() or '.' in cantidad_str:
                                cantidad = float(cantidad_str)
                            else:
                                cantidad = float(num_map.get(cantidad_str, 1.0))
                        else:
                            cantidad = 1.0
                        resto_texto = match_item.group(2).strip()
                    
                    partes = re.split(r'\s+en\s+', resto_texto, maxsplit=1)
                    producto_texto = partes[0].strip()
                    nombre_ubicacion = partes[1].strip() if len(partes) > 1 else None
                    
                    if producto_texto.endswith('s') and len(producto_texto) > 3:
                        producto_texto_limpio = producto_texto[:-1]
                    else:
                        producto_texto_limpio = producto_texto
                        
                    ubicacion_obj = None
                    if nombre_ubicacion:
                        nombre_ubicacion_limpio = re.sub(r'^(el|la|los|las)\s+', '', nombre_ubicacion, flags=re.IGNORECASE).strip()
                        
                        ubicaciones_db = Ubicacion.query.all()
                        nombres = [u.nombre for u in ubicaciones_db]
                        coincidencias = difflib.get_close_matches(nombre_ubicacion_limpio, nombres, n=1, cutoff=0.65)
                        if coincidencias:
                            ubicacion_obj = next(u for u in ubicaciones_db if u.nombre == coincidencias[0])
                        else:
                            try:
                                sala_def = Sala.query.first()
                                if sala_def:
                                    ubicacion_obj = Ubicacion(nombre=nombre_ubicacion_limpio.capitalize(), sala_id=sala_def.id)
                                    db.session.add(ubicacion_obj)
                                    db.session.flush()
                                else:
                                    ubicacion_obj = None
                            except Exception as e_ubi:
                                db.session.rollback()
                                ubicacion_obj = None
                            
                    producto = Producto.query.filter(
                        (Producto.nombre.ilike(f"%{producto_texto}%")) | 
                        (Producto.nombre.ilike(f"%{producto_texto_limpio}%"))
                    ).first()
                    
                    ubi_nombre_mostrar = ubicacion_obj.nombre if ubicacion_obj else (nombre_ubicacion if nombre_ubicacion else "")
                    ubi_msg = f" en {ubi_nombre_mostrar}" if ubi_nombre_mostrar else ""
                    
                    if rama == "inventario":
                        if producto:
                            producto.stock_actual += cantidad
                            if ubicacion_obj:
                                producto.ubicacion_id = ubicacion_obj.id
                            mov = Movimiento(descripcion="Añadido por Voz", producto_id=producto.id, tipo="add", cantidad=cantidad)
                            db.session.add(mov)
                            db.session.flush()
                            recent_transactions[tx_id].append({"producto_id": producto.id, "added": cantidad, "movimiento_id": mov.id, "is_new": False})
                            respuestas.append(f"{cantidad}x {producto.nombre}{ubi_msg}")
                        else:
                            nuevo_prod = Producto(
                                nombre=producto_texto.capitalize(), 
                                stock_actual=cantidad, 
                                stock_minimo=1.0,
                                ubicacion_id=ubicacion_obj.id if ubicacion_obj else None
                            )
                            db.session.add(nuevo_prod)
                            db.session.flush()
                            mov = Movimiento(descripcion="Creado por Voz", producto_id=nuevo_prod.id, tipo="add", cantidad=cantidad)
                            db.session.add(mov)
                            db.session.flush()
                            recent_transactions[tx_id].append({"producto_id": nuevo_prod.id, "added": cantidad, "movimiento_id": mov.id, "is_new": True})
                            respuestas.append(f"{cantidad}x {nuevo_prod.nombre}{ubi_msg}")
                            
                    elif rama == "compras":
                        if producto:
                            was_en_lista = producto.en_lista
                            producto.en_lista = True
                            db.session.flush()
                            recent_transactions[tx_id].append({"producto_id": producto.id, "was_en_lista": was_en_lista, "is_new": False})
                            respuestas.append(f"{producto.nombre}{ubi_msg}")
                        else:
                            nuevo_prod = Producto(
                                nombre=producto_texto.capitalize(),
                                stock_actual=0,
                                stock_minimo=1.0,
                                en_lista=True,
                                es_temporal=True,
                                ubicacion_id=ubicacion_obj.id if ubicacion_obj else None
                            )
                            db.session.add(nuevo_prod)
                            db.session.flush()
                            recent_transactions[tx_id].append({"producto_id": nuevo_prod.id, "is_new": True})
                            respuestas.append(f"{nuevo_prod.nombre}{ubi_msg} (temporal)")

                    elif rama == "restar":
                        if producto:
                            cantidad_restada = min(producto.stock_actual, cantidad)
                            producto.stock_actual = max(0, producto.stock_actual - cantidad)
                            mov = Movimiento(descripcion="Consumido por Voz", producto_id=producto.id, tipo="remove", cantidad=cantidad_restada)
                            db.session.add(mov)
                            db.session.flush()
                            recent_transactions[tx_id].append({"producto_id": producto.id, "removed": cantidad_restada, "movimiento_id": mov.id, "is_new": False})
                            respuestas.append(f"{cantidad_restada}x {producto.nombre}{ubi_msg}")
                        else:
                            respuestas.append(f"⚠️ {producto_texto.capitalize()} no existe, omitido.")
                    elif rama == "tarea":
                        tarea_nombre = producto_texto.strip()
                        tarea_db = Tarea.query.filter(Tarea.nombre.ilike(f"%{tarea_nombre}%")).first()
                        if tarea_db:
                            user = Usuario.query.filter_by(telegram_chat_id=str(call.from_user.id)).first()
                            if user:
                                # Registrar historial y actualizar fecha
                                old_date = tarea_db.fecha_ultima_ejecucion
                                historial = HistorialTarea(tarea_id=tarea_db.id, usuario_id=user.id)
                                db.session.add(historial)
                                tarea_db.fecha_ultima_ejecucion = datetime.now().date()
                                db.session.flush()
                                recent_transactions[tx_id].append({
                                    "is_tarea": True, 
                                    "tarea_id": tarea_db.id, 
                                    "historial_id": historial.id, 
                                    "old_date": old_date
                                })
                                respuestas.append(f"✨ Tarea '{tarea_db.nombre}' completada por {user.username}.")
                        else:
                            respuestas.append(f"⚠️ No se encontró la tarea '{tarea_nombre}'.")


                db.session.commit()
                
                if respuestas:
                    markup_undo = InlineKeyboardMarkup()
                    markup_undo.add(InlineKeyboardButton("↩️ Deshacer", callback_data=f"undo_{tx_id}"))
                    
                    if rama == "inventario":
                        safe_telegram_send(call.message.chat.id, "✅ Procesado:\n- " + "\n- ".join(respuestas), reply_markup=markup_undo)
                    elif rama == "compras":
                        safe_telegram_send(call.message.chat.id, "🛒 Añadido a compras:\n- " + "\n- ".join(respuestas), reply_markup=markup_undo)
                    elif rama == "restar":
                        safe_telegram_send(call.message.chat.id, "➖ Descontado del inventario:\n- " + "\n- ".join(respuestas), reply_markup=markup_undo)
                else:
                    safe_telegram_send(call.message.chat.id, "⚠️ No se procesó ningún artículo.")
            except Exception as e:
                db.session.rollback()
                safe_telegram_send(call.message.chat.id, f"❌ Error guardando datos, transacción revertida: {str(e)}")
                recent_transactions.pop(tx_id, None)
    except Exception as e:
        safe_telegram_send(call.message.chat.id, f"❌ Error interno: {str(e)}")

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


def calcular_proxima_fecha(tarea, desde_fecha):
    if not desde_fecha:
        return datetime.now().date()
    if tarea.tipo_frecuencia == 'dias':
        try:
            dias = int(tarea.valor_frecuencia)
        except:
            dias = 1
        return desde_fecha + timedelta(days=dias)
    elif tarea.tipo_frecuencia == 'dia_semana':
        days_map = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6} # Lunes=0, Domingo=6
        target = days_map.get(str(tarea.valor_frecuencia), 0)
        days_ahead = target - desde_fecha.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return desde_fecha + timedelta(days=days_ahead)
    elif tarea.tipo_frecuencia == 'mes':
        if desde_fecha.month == 12:
            next_month = 1
            next_year = desde_fecha.year + 1
        else:
            next_month = desde_fecha.month + 1
            next_year = desde_fecha.year
        if tarea.valor_frecuencia == 'inicio':
            return date(next_year, next_month, 1)
        elif tarea.valor_frecuencia == 'fin':
            last_day = calendar.monthrange(next_year, next_month)[1]
            return date(next_year, next_month, last_day)
        else:
            try:
                day_val = int(tarea.valor_frecuencia)
                # If target day is earlier than today in the CURRENT month, schedule for next month
                if desde_fecha.day < day_val:
                    last_day_current = calendar.monthrange(desde_fecha.year, desde_fecha.month)[1]
                    target_day = min(day_val, last_day_current)
                    return date(desde_fecha.year, desde_fecha.month, target_day)
                else:
                    last_day_next = calendar.monthrange(next_year, next_month)[1]
                    target_day = min(day_val, last_day_next)
                    return date(next_year, next_month, target_day)
            except ValueError:
                return date(next_year, next_month, 1)
    elif tarea.tipo_frecuencia == 'fecha_fija':
        try:
            return datetime.strptime(tarea.valor_frecuencia, '%Y-%m-%d').date()
        except:
            return desde_fecha
    return desde_fecha + timedelta(days=1)

def calcular_proximo_turno(tarea):
    if not tarea.usuarios:
        return None
    ultimo = HistorialTarea.query.filter_by(tarea_id=tarea.id).order_by(HistorialTarea.fecha.desc()).first()
    if not ultimo:
        return tarea.usuarios[0].id
    usuarios_ids = [u.id for u in tarea.usuarios]
    if ultimo.usuario_id in usuarios_ids:
        idx = usuarios_ids.index(ultimo.usuario_id)
        next_idx = (idx + 1) % len(usuarios_ids)
        return usuarios_ids[next_idx]
    return usuarios_ids[0]

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

def iniciar_bot():
    if bot:
        logging.info("[Bot Telemetría] Iniciando bot de Telegram en segundo plano...")
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
            print("🟢 INICIANDO POLLING DE TELEGRAM...")
            bot.remove_webhook()
            logging.info("[Bot Telemetría] Webhook removido con éxito. Arrancando infinity_polling en hilo daemon...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60, logger_level=logging.INFO)
        except Exception as e:
            print(f"🔴 ERROR FATAL EN EL HILO DEL BOT: {e}")
            logging.error(f"[Bot Telemetría] Error crítico en polling de Telegram: {e}", exc_info=True)

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

            logging.info(f"Worker {os.getpid()} está iniciando hilos de fondo para bot y scheduler...")
            bot_thread = threading.Thread(target=iniciar_bot, name="TelegramBotThread", daemon=True)
            print(f"🛠️ Diagnóstico: El bot tiene {len(bot.message_handlers)} handlers de mensajes registrados antes de iniciar.")
            bot_thread.start()

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

# Intentar arrancar tareas de fondo solo una vez (compatible con WSGI)
start_background_tasks()


# ==========================================
# 12. ENDPOINTS NUEVOS MODULOS (STUBS)
# ==========================================

def consumir_receta(receta_id):
    with app.app_context():
        receta = db.session.get(Receta, receta_id)
        if not receta: return False
        
        for ing in receta.ingredientes:
            if ing.producto.stock_actual >= ing.cantidad_requerida:
                ing.producto.stock_actual -= ing.cantidad_requerida
            else:
                ing.producto.stock_actual = 0
        db.session.commit()
        return True

from routes import register_blueprints
register_blueprints(app)
from services.bot_telegram import registrar_handlers
if bot:
    registrar_handlers(bot, app)

if __name__ == '__main__':
    # 1. Forzar a Telegram a limpiar conexiones viejas
    try:
        bot.remove_webhook()
    except Exception:
        pass
        
    # 2. Arrancar el bot ignorando mensajes acumulados (skip_pending=True)
    bot_thread = threading.Thread(target=bot.infinity_polling, kwargs={'skip_pending': True})
    bot_thread.start()
    
    # 3. Arrancar Flask de forma segura
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)