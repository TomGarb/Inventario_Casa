import os
import calendar
import threading
import telebot
import google.generativeai as genai
import base64
import json
import pytz
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, date, timedelta, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import whisper
import uuid
import re
import difflib
import random
import string
from functools import wraps

# ==========================================
# 1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================

# Configuración global de PATH para que ffmpeg sea encontrado por whisper sin errores
ffmpeg_dir = r"C:\Users\tomga\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin"
if ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + ffmpeg_dir

modelo_whisper = whisper.load_model("base")
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-homestock-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///homestock.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
from flask_migrate import Migrate
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
TELEGRAM_GROUP_ID = os.getenv('TELEGRAM_GROUP_ID')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', TELEGRAM_GROUP_ID)

bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
CHAT_ID = TELEGRAM_CHAT_ID

pending_voice_commands = {}
recent_transactions = {}

# ==========================================
# 2. MODELOS DE BASE DE DATOS
# ==========================================
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    telegram_chat_id = db.Column(db.String(50), unique=True, nullable=True)
    telegram_link_token = db.Column(db.String(10), unique=True, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'telegram_chat_id': self.telegram_chat_id,
            'is_admin': self.is_admin
        }

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


usuario_tarea = db.Table('usuario_tarea',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True),
    db.Column('tarea_id', db.Integer, db.ForeignKey('tareas.id'), primary_key=True)
)

usuario_modelo_tarea = db.Table('usuario_modelo_tarea',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True),
    db.Column('modelo_tarea_id', db.Integer, db.ForeignKey('modelo_tareas.id'), primary_key=True)
)

class ModeloTarea(db.Model):
    __tablename__ = 'modelo_tareas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    prioridad = db.Column(db.String(50), default='Esencial')
    tipo_frecuencia = db.Column(db.String(50), default='dias')
    valor_frecuencia = db.Column(db.String(50), default='1')
    alternar = db.Column(db.Boolean, default=True)
    fecha_ultima_ejecucion = db.Column(db.Date, nullable=True)
    
    usuarios = db.relationship('Usuario', secondary=usuario_modelo_tarea, lazy='subquery',
        backref=db.backref('modelos', lazy=True))
        
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'prioridad': self.prioridad,
            'tipo_frecuencia': self.tipo_frecuencia,
            'valor_frecuencia': self.valor_frecuencia,
            'alternar': self.alternar,
            'fecha_ultima_ejecucion': self.fecha_ultima_ejecucion.isoformat() if self.fecha_ultima_ejecucion else None,
            'usuarios': [{'id': u.id, 'username': u.username} for u in self.usuarios]
        }

class Tarea(db.Model):
    __tablename__ = 'tareas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    prioridad = db.Column(db.String(50), default='Esencial')
    tipo_frecuencia = db.Column(db.String(50), default='dias')
    valor_frecuencia = db.Column(db.String(50), default='1')
    fecha_ultima_ejecucion = db.Column(db.Date, nullable=True)
    fecha_programada = db.Column(db.Date, nullable=True)
    alternar = db.Column(db.Boolean, default=True)
    completada = db.Column(db.Boolean, default=False)
    modelo_id = db.Column(db.Integer, db.ForeignKey('modelo_tareas.id'), nullable=True)
    
    usuarios = db.relationship('Usuario', secondary=usuario_tarea, lazy='subquery',
        backref=db.backref('tareas_instancias', lazy=True))
        
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'prioridad': self.prioridad,
            'tipo_frecuencia': self.tipo_frecuencia,
            'valor_frecuencia': self.valor_frecuencia,
            'alternar': self.alternar,
            'completada': self.completada,
            'fecha_programada': self.fecha_programada.isoformat() if self.fecha_programada else (self.fecha_ultima_ejecucion.isoformat() if self.fecha_ultima_ejecucion else None),
            'modelo_id': self.modelo_id,
            'usuarios': [{'id': u.id, 'username': u.username} for u in self.usuarios]
        }

class HistorialTarea(db.Model):
    __tablename__ = 'historial_tareas'
    id = db.Column(db.Integer, primary_key=True)
    tarea_id = db.Column(db.Integer, db.ForeignKey('tareas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)



class SaltoTarea(db.Model):
    __tablename__ = 'salto_tareas'
    id = db.Column(db.Integer, primary_key=True)
    tarea_id = db.Column(db.Integer, db.ForeignKey('tareas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    motivo = db.Column(db.String(255), nullable=False)

class Sala(db.Model):
    __tablename__ = 'salas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    piso = db.Column(db.String(50), nullable=True)
    ubicaciones = db.relationship('Ubicacion', backref='sala', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'piso': self.piso,
            'ubicaciones': [u.to_dict() for u in self.ubicaciones]
        }

class Ubicacion(db.Model):
    __tablename__ = 'ubicaciones'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    sala_id = db.Column(db.Integer, db.ForeignKey('salas.id'), nullable=False)
    sub_ubicaciones = db.relationship('SubUbicacion', backref='ubicacion', lazy=True, cascade="all, delete-orphan")
    productos = db.relationship('Producto', backref='rel_ubicacion', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'sala_id': self.sala_id,
            'sub_ubicaciones': [su.to_dict() for su in self.sub_ubicaciones]
        }

class SubUbicacion(db.Model):
    __tablename__ = 'sub_ubicaciones'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    ubicacion_id = db.Column(db.Integer, db.ForeignKey('ubicaciones.id'), nullable=False)
    productos = db.relationship('Producto', backref='rel_sub_ubicacion', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'ubicacion_id': self.ubicacion_id
        }

class Comercio(db.Model):
    __tablename__ = 'comercios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    productos = db.relationship('Producto', backref='rel_comercio', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre
        }

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    stock_actual = db.Column(db.Float, default=0.0)
    stock_minimo = db.Column(db.Float, default=1.0)
    unidad_medida = db.Column(db.String(20), default='unidades')
    en_lista = db.Column(db.Boolean, default=False)
    es_temporal = db.Column(db.Boolean, default=False)
    fecha_vencimiento = db.Column(db.Date, nullable=True)
    fecha_ultima_compra = db.Column(db.Date, nullable=True)
    
    ubicacion_id = db.Column(db.Integer, db.ForeignKey('ubicaciones.id'), nullable=True)
    sub_ubicacion_id = db.Column(db.Integer, db.ForeignKey('sub_ubicaciones.id'), nullable=True)
    comercio_id = db.Column(db.Integer, db.ForeignKey('comercios.id'), nullable=True)

    def to_dict(self):
        ubi_nombre = self.rel_ubicacion.nombre if self.rel_ubicacion else None
        sub_nombre = self.rel_sub_ubicacion.nombre if self.rel_sub_ubicacion else None
        sala_nombre = self.rel_ubicacion.sala.nombre if self.rel_ubicacion and self.rel_ubicacion.sala else None
        comercio_nombre = self.rel_comercio.nombre if self.rel_comercio else "Sin Comercio"
        
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'ubicacion_id': self.ubicacion_id,
            'sub_ubicacion_id': self.sub_ubicacion_id,
            'comercio_id': self.comercio_id,
            'ubicacion': ubi_nombre,
            'sub_ubicacion': sub_nombre,
            'sala': sala_nombre,
            'comercio': comercio_nombre,
            'stock_actual': self.stock_actual,
            'stock_minimo': self.stock_minimo,
            'unidad_medida': self.unidad_medida,
            'en_lista': self.en_lista,
            'es_temporal': self.es_temporal,
            'fecha_vencimiento': self.fecha_vencimiento.isoformat() if self.fecha_vencimiento else None,
            'fecha_ultima_compra': self.fecha_ultima_compra.isoformat() if self.fecha_ultima_compra else None
        }

class Movimiento(db.Model):
    __tablename__ = 'movimientos'
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(255), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=True)
    tipo = db.Column(db.String(50), nullable=True)
    cantidad = db.Column(db.Float, default=0.0)

    rel_producto = db.relationship('Producto', backref='movimientos', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'descripcion': self.descripcion,
            'fecha': self.fecha.isoformat(),
            'producto_id': self.producto_id,
            'tipo': self.tipo,
            'cantidad': self.cantidad,
            'producto_nombre': self.rel_producto.nombre if self.rel_producto else None
        }


# --- NUEVOS MODULOS ---

# Modulo Finanzas
class Gasto(db.Model):
    __tablename__ = 'gastos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    imagen_ticket_url = db.Column(db.String(500), nullable=True)
    
    pagador = db.relationship('Usuario', backref='gastos_pagados')
    divisiones = db.relationship('DivisionGasto', backref='rel_gasto', cascade='all, delete-orphan')

class DivisionGasto(db.Model):
    __tablename__ = 'division_gastos'
    id = db.Column(db.Integer, primary_key=True)
    gasto_id = db.Column(db.Integer, db.ForeignKey('gastos.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    monto_adeudado = db.Column(db.Float, nullable=False)
    esta_pagado = db.Column(db.Boolean, default=False)
    
    usuario = db.relationship('Usuario', backref='deudas')

# Modulo Logistica
class EventoLogistico(db.Model):
    __tablename__ = 'eventos_logisticos'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    creador = db.relationship('Usuario', backref='eventos_creados')

# Modulo Menus
class HorarioComidas(db.Model):
    __tablename__ = 'horario_comidas'
    id = db.Column(db.Integer, primary_key=True)
    tipo_comida = db.Column(db.String(50), nullable=False) # Desayuno, Almuerzo, Merienda, Cena
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)

class IngredienteReceta(db.Model):
    __tablename__ = 'ingrediente_receta'
    receta_id = db.Column(db.Integer, db.ForeignKey('recetas.id'), primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), primary_key=True)
    cantidad_requerida = db.Column(db.Float, nullable=False, default=1.0)
    
    producto = db.relationship('Producto')
    receta = db.relationship('Receta', back_populates='ingredientes')

class Receta(db.Model):
    __tablename__ = 'recetas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(50), nullable=False) # Desayuno, Almuerzo, Merienda, Cena
    es_rapida = db.Column(db.Boolean, default=False)
    
    ingredientes = db.relationship('IngredienteReceta', back_populates='receta', cascade="all, delete-orphan")

class MenuSemanal(db.Model):
    __tablename__ = 'menu_semanal'
    id = db.Column(db.Integer, primary_key=True)
    dia_semana = db.Column(db.String(20), nullable=False) # Lunes a Domingo
    tipo_comida = db.Column(db.String(50), nullable=False) # Desayuno, Almuerzo, Merienda, Cena
    receta_id = db.Column(db.Integer, db.ForeignKey('recetas.id'), nullable=False)
    fecha_asignada = db.Column(db.Date, nullable=False)
    
    receta = db.relationship('Receta', backref='asignaciones')

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
                u_deudor = Usuario.query.get(deudor_id)
                u_acreedor = Usuario.query.get(acreedor_id)
                if u_deudor and u_acreedor and monto > 0:
                    resultado.append({
                        'deudor_id': deudor_id,
                        'deudor_nombre': u_deudor.username,
                        'acreedor_id': acreedor_id,
                        'acreedor_nombre': u_acreedor.username,
                        'monto': round(monto, 2)
                    })
        return resultado

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'error': 'Requiere permisos de administrador'}), 403
        return f(*args, **kwargs)
    return decorated_function

def crud_create(modelo, requeridos, campos_adicionales=None):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos faltantes'}), 400
    for req in requeridos:
        if req not in data:
            return jsonify({'error': f'El campo {req} es obligatorio'}), 400
            
    kwargs = {req: data[req] for req in requeridos}
    if campos_adicionales:
        for extra in campos_adicionales:
            if extra in data:
                kwargs[extra] = data[extra]
                
    try:
        entidad = modelo(**kwargs)
        db.session.add(entidad)
        db.session.commit()
        return jsonify(entidad.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def crud_update(modelo, id_entidad, requeridos, campos_adicionales=None):
    entidad = modelo.query.get_or_404(id_entidad)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos faltantes'}), 400
        
    for req in requeridos:
        if req not in data:
            return jsonify({'error': f'El campo {req} es obligatorio'}), 400
        setattr(entidad, req, data[req])
        
    if campos_adicionales:
        for extra in campos_adicionales:
            if extra in data:
                setattr(entidad, extra, data[extra])
                
    try:
        db.session.commit()
        return jsonify(entidad.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def safe_telegram_send(chat_id, mensaje, reply_markup=None, parse_mode='HTML'):
    if not bot:
        return False
    try:
        bot.send_message(chat_id, mensaje, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        print(f"Error enviando mensaje a {chat_id}: {e}")
        return False

def extraer_datos_evento(texto):
    if not GEMINI_API_KEY:
        return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        fecha_actual = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        
        prompt = f"Eres un asistente de calendario. Hoy es {fecha_actual} (Hora de Buenos Aires). Analiza este mensaje y extrae los detalles del evento. Devuelve EXCLUSIVAMENTE un JSON con las claves: 'titulo' (resumen corto), 'fecha_inicio' (formato ISO 8601), 'fecha_fin' (formato ISO 8601, si aplica), y 'descripcion'. No uses markdown."
        
        response = model.generate_content([prompt, texto])
        resultado_str = response.text.strip()
        
        if resultado_str.startswith('```json'):
            resultado_str = resultado_str.replace('```json', '').replace('```', '').strip()
        elif resultado_str.startswith('```'):
            resultado_str = resultado_str.replace('```', '').strip()
            
        return json.loads(resultado_str)
    except Exception as e:
        print(f"Error NLP Gemini: {e}")
        return None

def safe_telegram_reply(message, texto, reply_markup=None, parse_mode=None):
    if not bot:
        return False
    try:
        bot.reply_to(message, texto, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
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
        u = Usuario.query.get(usuario_id)
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

def enviar_listas_agrupadas(chat_id, comercio_objetivo=None):
    with app.app_context():
        if comercio_objetivo:
            if comercio_objetivo == "Sin Comercio":
                productos_en_lista = Producto.query.filter_by(en_lista=True, comercio_id=None).all()
            else:
                comercio = Comercio.query.filter_by(nombre=comercio_objetivo).first()
                if comercio:
                    productos_en_lista = Producto.query.filter_by(en_lista=True, comercio_id=comercio.id).all()
                else:
                    safe_telegram_send(chat_id, f"❌ No se encontró el comercio '{comercio_objetivo}'.")
                    return
        else:
            productos_en_lista = Producto.query.filter_by(en_lista=True).all()
            
        if not productos_en_lista:
            safe_telegram_send(chat_id, "🛒 Tu lista de compras está vacía.")
            return

        grupos = defaultdict(list)
        for p in productos_en_lista:
            nombre_comercio = p.rel_comercio.nombre if p.rel_comercio else "Sin Comercio"
            grupos[nombre_comercio].append(p)
            
        for comercio, productos in grupos.items():
            markup = telebot.types.InlineKeyboardMarkup()
            for p in productos:
                boton = telebot.types.InlineKeyboardButton(
                    text=f"⬜ {p.nombre} (Stock: {p.stock_actual})", 
                    callback_data=f"comprar_{p.id}"
                )
                markup.add(boton)
            safe_telegram_send(chat_id, f"📍 **{comercio}:**", reply_markup=markup, parse_mode='Markdown')

if bot:
    def is_authorized(chat_id):
        with app.app_context():
            user = Usuario.query.filter_by(telegram_chat_id=str(chat_id)).first()
            return user is not None

    @bot.message_handler(content_types=['voice', 'text'])
    def handle_voice_and_text(message):
        if not is_authorized(message.chat.id): return
        
        texto_transcrito = ''
        
        if message.content_type == 'voice':
            ogg_path = None
            try:
                safe_telegram_reply(message, "Procesando audio... 🎙️")
                
                file_info = bot.get_file(message.voice.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                
                temp_id = str(uuid.uuid4())
                base_dir = os.path.dirname(os.path.abspath(__file__))
                ogg_path = os.path.join(base_dir, f"{temp_id}.ogg")
                
                with open(ogg_path, 'wb') as new_file:
                    new_file.write(downloaded_file)
                    
                resultado = modelo_whisper.transcribe(ogg_path, language="es")
                texto_transcrito = resultado["text"].strip()
            except Exception as e:
                safe_telegram_send(message.chat.id, f"❌ Error interno: {str(e)}")
                return
            finally:
                if ogg_path and os.path.exists(ogg_path):
                    try:
                        os.remove(ogg_path)
                    except:
                        pass
        else:
            if message.text.startswith('/'): return
            texto_transcrito = message.text.strip()
            
        texto_lower = texto_transcrito.lower()
        if texto_lower.startswith('agendar') or texto_lower.startswith('aviso') or texto_lower.startswith('visita'):
            datos_evento = extraer_datos_evento(texto_transcrito)
            if datos_evento and 'titulo' in datos_evento and 'fecha_inicio' in datos_evento:
                pending_voice_commands[message.chat.id] = (datos_evento, datetime.now(), 'logistica')
                markup = InlineKeyboardMarkup()
                markup.row_width = 2
                markup.add(
                    InlineKeyboardButton("✅ Sí", callback_data="confirm_logistica"),
                    InlineKeyboardButton("❌ No", callback_data="cancel_logistica")
                )
                safe_telegram_send(message.chat.id, f"📅 Entendido. Agendaré: *{datos_evento['titulo']}* para el {datos_evento['fecha_inicio']}. ¿Confírmas?", reply_markup=markup, parse_mode="Markdown")
            else:
                safe_telegram_send(message.chat.id, "❌ No pude extraer los detalles del evento.")
            return

        if texto_lower.startswith('sug') or 'qué comemos' in texto_lower or 'que comemos' in texto_lower or 'comida' in texto_lower or 'cena' in texto_lower or 'almuerzo' in texto_lower:
            es_rapida = 'rápid' in texto_lower or 'rapid' in texto_lower
            with app.app_context():
                if es_rapida:
                    rapidas = Receta.query.filter_by(es_rapida=True).all()
                    if not rapidas:
                        safe_telegram_send(message.chat.id, "❌ No hay recetas rápidas cargadas.")
                        return
                    import random
                    sug = random.choice(rapidas)
                    safe_telegram_send(message.chat.id, f"⚡ Sugerencia rápida: *{sug.nombre}*. (No desconto inventario)", parse_mode="Markdown")
                else:
                    todas = Receta.query.all()
                    posibles = []
                    for rec in todas:
                        puede = True
                        for ing in rec.ingredientes:
                            if ing.producto.stock_actual < ing.cantidad_requerida:
                                puede = False
                                break
                        if puede: posibles.append(rec)
                    if not posibles:
                        safe_telegram_send(message.chat.id, "❌ No tienes ingredientes completos para ninguna receta de la base de datos.")
                        return
                    import random
                    sug = random.choice(posibles)
                    
                    pending_voice_commands[message.chat.id] = (sug.id, datetime.now(), 'menu')
                    markup = InlineKeyboardMarkup()
                    markup.row_width = 2
                    markup.add(
                        InlineKeyboardButton("✅ Sí, preparar", callback_data="confirm_menu"),
                        InlineKeyboardButton("❌ No", callback_data="cancel_menu")
                    )
                    safe_telegram_send(message.chat.id, f"🍽️ Puedes hacer *{sug.nombre}*. Tienes todos los ingredientes. ¿Lo preparas hoy?", reply_markup=markup, parse_mode="Markdown")
            return


        # Para inventario / compras / tareas 
        pending_voice_commands[message.chat.id] = (texto_transcrito, datetime.now(), 'inventario')
        
        markup = InlineKeyboardMarkup()
        markup.row_width = 2
        markup.add(
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm_voice"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_voice")
        )
        
        tipo_msg = "🎙️ Escuché" if message.content_type == 'voice' else "📝 Recibí"
        safe_telegram_send(message.chat.id, f"{tipo_msg}:\n\n_{texto_transcrito}_\n\n¿Procesar esta instrucción?", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('ocr_div_'))
    def handle_ocr_division(call):
        chat_id = call.message.chat.id
        if chat_id not in pending_ocr_confirmations:
            bot.answer_callback_query(call.id, "Solicitud expirada.")
            return
            
        data = pending_ocr_confirmations.pop(chat_id)
        if call.data == 'ocr_div_no':
            bot.edit_message_text("Carga de ticket cancelada.", chat_id, call.message.message_id)
            return
            
        # ocr_div_si: Dividir entre todos los activos
        with app.app_context():
            comprador = Usuario.query.get(data['usuario_id'])
            todos_usuarios = Usuario.query.all() # Asumimos todos activos
            
            nuevo_gasto = Gasto(
                usuario_id=comprador.id,
                monto=data['monto_total'],
                descripcion=data['descripcion']
            )
            db.session.add(nuevo_gasto)
            db.session.flush() # Para tener el ID
            
            monto_por_persona = data['monto_total'] / len(todos_usuarios)
            
            for u in todos_usuarios:
                # El comprador ya esta pagado consigo mismo
                esta_pagado = (u.id == comprador.id)
                div = DivisionGasto(
                    gasto_id=nuevo_gasto.id,
                    usuario_id=u.id,
                    monto_adeudado=monto_por_persona,
                    esta_pagado=esta_pagado
                )
                db.session.add(div)
                
            db.session.commit()
            
            bot.edit_message_text(f"✅ ¡Gasto registrado exitosamente!\nConcepto: {data['descripcion']}\nCada usuario debe: ${round(monto_por_persona, 2)}", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: True)
    def callback_inline(call):
        if call.data in ['confirm_voice', 'cancel_voice']:
            callback_voice(call)
            return
        if call.data in ['confirm_logistica', 'cancel_logistica']:
            handle_logistica_callback(call)
            return
        if call.data in ['confirm_menu', 'cancel_menu']:
            handle_menu_callback(call)
            return

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
                user = Usuario.query.filter_by(telegram_chat_id=str(call.message.chat.id)).first()
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
                
                safe_telegram_send(call.message.chat.id, f"✅ Evento guardado correctamente:\n*{datos_evento['titulo']}*", parse_mode="Markdown")
        except Exception as e:
            print(f"Error guardando evento: {e}")
            safe_telegram_send(call.message.chat.id, f"❌ Error interno al guardar: {e}")

    def handle_menu_callback(call):
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        
        if call.data == 'cancel_menu':
            pending_voice_commands.pop(call.message.chat.id, None)
            safe_telegram_send(call.message.chat.id, "❌ Sugerencia cancelada.")
            return
            
        pending_data = pending_voice_commands.pop(call.message.chat.id, None)
        if not pending_data or len(pending_data) != 3 or pending_data[2] != 'menu':
            safe_telegram_send(call.message.chat.id, "⚠️ La solicitud ha expirado o ya fue procesada.")
            return
            
        receta_id = pending_data[0]
        
        try:
            with app.app_context():
                receta = Receta.query.get(receta_id)
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
            
        texto_transcrito = pending_data[0] if isinstance(pending_data, tuple) else pending_data
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
            safe_telegram_send(call.message.chat.id, "❌ No pude entender la orden. Intenta decir: 'Agregar 2 de leche...' o 'Gasté 1 pan'.")
            return
            
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
                                ubicacion_obj = Ubicacion(nombre=nombre_ubicacion_limpio.capitalize(), sala_id=None)
                                db.session.add(ubicacion_obj)
                                db.session.flush()
                                
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
                                user = Usuario.query.filter_by(telegram_chat_id=str(call.message.chat.id)).first()
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith('undo_'))
    def callback_undo(call):
        tx_id = call.data.replace('undo_', '')
        if tx_id not in recent_transactions:
            bot.answer_callback_query(call.id, "⚠️ Esta acción ya expiró o fue deshecha.")
            return
            
        operaciones = recent_transactions.pop(tx_id)
        try:
            with app.app_context():
                for op in operaciones:
                    prod = Producto.query.get(op['producto_id'])
                    if not prod: continue
                    
                    
                    if op.get('is_tarea'):
                        if 'historial_id' in op:
                            h = HistorialTarea.query.get(op['historial_id'])
                            if h: db.session.delete(h)
                        if 'tarea_id' in op:
                            t = Tarea.query.get(op['tarea_id'])
                            if t and 'old_date' in op:
                                t.fecha_ultima_ejecucion = op['old_date']
                        continue

                    if op.get('is_new'):
                        if 'movimiento_id' in op:
                            mov = Movimiento.query.get(op['movimiento_id'])
                            if mov: db.session.delete(mov)
                        db.session.delete(prod)
                    else:
                        if 'added' in op:
                            prod.stock_actual = max(0, prod.stock_actual - op['added'])
                        if 'removed' in op:
                            prod.stock_actual += op['removed']
                        if 'was_en_lista' in op:
                            prod.en_lista = op['was_en_lista']
                            
                        if 'movimiento_id' in op:
                            mov = Movimiento.query.get(op['movimiento_id'])
                            if mov: db.session.delete(mov)
                db.session.commit()
            bot.edit_message_text("↩️ Acción deshecha correctamente.", call.message.chat.id, call.message.message_id)
        except Exception as e:
            safe_telegram_send(call.message.chat.id, f"❌ Error al deshacer: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data == 'add_low_stock')
    def callback_add_low_stock(call):
        try:
            with app.app_context():
                productos_bajos = Producto.query.filter(Producto.stock_actual <= Producto.stock_minimo, Producto.en_lista == False).all()
                for p in productos_bajos:
                    p.en_lista = True
                db.session.commit()
            bot.edit_message_text("✅ Productos agregados a la lista de compras.", call.message.chat.id, call.message.message_id)
        except Exception as e:
            safe_telegram_send(call.message.chat.id, f"❌ Error: {str(e)}")

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        safe_telegram_reply(message, "¡Hola! Bienvenido a Homestock. Para vincular tu cuenta, ingresa a la aplicación web, ve a tu Perfil, genera un token y envíalo aquí con el comando:\n/vincular <Tu Token>")

    @bot.message_handler(commands=['vincular'])
    def cmd_vincular(message):
        texto = message.text.replace('/vincular', '').strip()
        if not texto:
            safe_telegram_reply(message, "Por favor, envía tu token. Ejemplo: /vincular ABC123")
            return
            
        with app.app_context():
            user = Usuario.query.filter_by(telegram_link_token=texto).first()
            if user:
                user.telegram_chat_id = str(message.chat.id)
                user.telegram_link_token = None
                db.session.commit()
                safe_telegram_reply(message, f"¡Cuenta vinculada con éxito! Hola, {user.username}. Ya recibirás notificaciones aquí.")
            else:
                safe_telegram_reply(message, "Token inválido o expirado. Genera uno nuevo en la web.")

        pending_ocr_confirmations = {}

    @bot.message_handler(commands=['balance'])
    def handle_balance(message):
        if not is_authorized(message.chat.id): return
        balances = calcular_balances_globales()
        if not balances:
            safe_telegram_reply(message, "🎉 ¡Todo está al día! Nadie le debe dinero a nadie en la casa.")
            return
        
        respuesta = "⚖️ <b>Balances Actuales de la Casa:</b>\n\n"
        for b in balances:
            respuesta += f"🔹 <b>{b['deudor_nombre']}</b> le debe a <b>{b['acreedor_nombre']}</b>: ${b['monto']}\n"
        
        safe_telegram_reply(message, respuesta, parse_mode='HTML')

    @bot.message_handler(content_types=['photo', 'document'])
    def handle_photo(message):
        if not is_authorized(message.chat.id): return
        
        if not GEMINI_API_KEY:
            safe_telegram_reply(message, "❌ Gemini no está configurado para leer tickets. Sube el gasto manualmente en la web.")
            return
            
        try:
            usuario = get_usuario_por_chat(message.chat.id)
            if not usuario:
                safe_telegram_reply(message, "❌ No encuentro tu usuario en el sistema.")
                return
                
            safe_telegram_reply(message, "📸 Recibí el ticket. Analizando con IA, dame unos segundos...")
            
            if message.content_type == 'photo':
                file_id = message.photo[-1].file_id
            else:
                file_id = message.document.file_id
                
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(downloaded_file)
                temp_file_path = temp_file.name
                
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                imagen_gemini = genai.upload_file(temp_file_path)
                
                prompt = "Eres un asistente contable. Analiza este ticket/factura y devuelve EXCLUSIVAMENTE un JSON con tres claves: 'descripcion' (resumen de la compra en 3-4 palabras), 'monto_total' (numero float, el total final pagado), e 'items' (lista de productos si es legible). No uses markdown ni texto adicional."
                response = model.generate_content([prompt, imagen_gemini])
                
                resultado_str = response.text.strip()
                if resultado_str.startswith('```json'):
                    resultado_str = resultado_str.replace('```json', '').replace('```', '').strip()
                elif resultado_str.startswith('```'):
                    resultado_str = resultado_str.replace('```', '').strip()
                    
                resultado = json.loads(resultado_str)
                monto_total = float(resultado.get('monto_total', 0))
                descripcion = resultado.get('descripcion', 'Ticket')
                
                if monto_total <= 0:
                    safe_telegram_reply(message, "❌ No pude detectar un monto válido en el ticket.")
                    return
                    
                pending_ocr_confirmations[message.chat.id] = {
                    'usuario_id': usuario.id,
                    'monto_total': monto_total,
                    'descripcion': descripcion
                }
                
                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton("✅ Sí, dividir", callback_data="ocr_div_si"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="ocr_div_no")
                )
                safe_telegram_reply(message, f"🧾 <b>Ticket detectado</b>\n\nConcepto: {descripcion}\nTotal: ${monto_total}\n\n¿Se divide en partes iguales entre todos los usuarios activos?", reply_markup=markup, parse_mode='HTML')
                
            finally:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            
        except Exception as e:
            safe_telegram_reply(message, f"❌ Falló la lectura: {str(e)}")

    @bot.message_handler(commands=['comprado'])
    def handle_comprado(message):
        if not is_authorized(message.chat.id): return
        texto = message.text.replace('/comprado', '').strip()
        if not texto:
            safe_telegram_reply(message, "⚠️ Usa: /comprado <producto> [cantidad]")
            return
            
        partes = texto.split()
        cantidad = 1
        nombre_producto = texto
        
        if partes[-1].isdigit():
            cantidad = int(partes[-1])
            nombre_producto = " ".join(partes[:-1])

        with app.app_context():
            producto = Producto.query.filter(Producto.nombre.ilike(f"%{nombre_producto}%")).first()
            if not producto:
                safe_telegram_reply(message, f"❌ No encontré '{nombre_producto}' en la base de datos.")
                return
                
            producto.stock_actual += cantidad
            producto.en_lista = False
            db.session.commit()
            safe_telegram_reply(message, f"✅ '{producto.nombre}' actualizada. Nuevo stock: {producto.stock_actual}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('comprar_'))
    def callback_comprar(call):
        if not is_authorized(call.message.chat.id): return
        producto_id = int(call.data.split('_')[1])
        with app.app_context():
            producto = Producto.query.get(producto_id)
            if not producto:
                return

            producto.en_lista = False
            comercio_id = producto.comercio_id
            nombre_comercio = producto.rel_comercio.nombre if producto.rel_comercio else "Sin Comercio"
            db.session.commit()
            
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
                
            if comercio_id is not None:
                productos_restantes = Producto.query.filter_by(en_lista=True, comercio_id=comercio_id).all()
            else:
                productos_restantes = Producto.query.filter(Producto.en_lista==True, Producto.comercio_id.is_(None)).all()
                
            if productos_restantes:
                markup = telebot.types.InlineKeyboardMarkup()
                for p in productos_restantes:
                    boton = telebot.types.InlineKeyboardButton(
                        text=f"⬜ {p.nombre} (Stock: {p.stock_actual})", 
                        callback_data=f"comprar_{p.id}"
                    )
                    markup.add(boton)
                safe_telegram_send(call.message.chat.id, f"📍 **{nombre_comercio}:**", parse_mode='Markdown', reply_markup=markup)
            else:
                safe_telegram_send(call.message.chat.id, f"✅ ¡Lista de {nombre_comercio} completada!")

    @bot.message_handler(commands=['test_lista'])
    def cmd_test_lista(message):
        if not is_authorized(message.chat.id): return
        enviar_listas_agrupadas(message.chat.id)

    @bot.message_handler(commands=['sugerir_compra'])
    def sugerir_compra(message):
        if not is_authorized(message.chat.id): return
        with app.app_context():
            sugerencias = Producto.query.filter(Producto.stock_actual < Producto.stock_minimo, Producto.en_lista == False).all()
            
            if not sugerencias:
                safe_telegram_reply(message, "✅ Todo en orden, tienes buen stock de todos tus productos.")
                return
                
            grupos = defaultdict(list)
            for p in sugerencias:
                comercio = p.rel_comercio.nombre if p.rel_comercio else "Sin Comercio"
                grupos[comercio].append(p)
                
            for comercio, productos in grupos.items():
                mensaje = f"Tienes {len(productos)} productos en **{comercio}** por debajo del mínimo. ¿Deseas agregarlos a la lista de compras?\n\n"
                for p in productos:
                    mensaje += f"- {p.nombre} (Stock: {p.stock_actual}/{p.stock_minimo})\n"
                
                ids_str = ",".join([str(p.id) for p in productos][:10])
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(
                    telebot.types.InlineKeyboardButton(text="✅ Agregar a la lista", callback_data=f"sugerir_add_{comercio}_{ids_str}"),
                    telebot.types.InlineKeyboardButton(text="❌ Ignorar", callback_data=f"sugerir_ignorar")
                )
                
                safe_telegram_send(message.chat.id, mensaje, reply_markup=markup, parse_mode='Markdown')

    @bot.message_handler(commands=['añadir', 'add'])
    def cmd_anadir(message):
        if not is_authorized(message.chat.id): return
        texto = message.text.replace('/añadir', '').replace('/add', '').strip()
        if not texto:
            safe_telegram_reply(message, "Uso: /añadir <nombre> <stock> <ubicacion>")
            return
            
        partes = texto.split()
        stock = None
        stock_idx = -1
        
        for i, part in enumerate(partes):
            try:
                stock = float(part)
                stock_idx = i
                break
            except ValueError:
                pass
                
        if stock_idx == -1 or stock_idx == 0:
            safe_telegram_reply(message, "No se pudo interpretar el formato. Asegúrate de incluir el stock.\nEjemplo: /añadir Leche 2 Heladera")
            return
            
        nombre = " ".join(partes[:stock_idx]).strip()
        ubicacion_nombre = " ".join(partes[stock_idx+1:]).strip()
        
        with app.app_context():
            ubi_id = None
            if ubicacion_nombre:
                ubi = Ubicacion.query.filter(Ubicacion.nombre.ilike(f"%{ubicacion_nombre}%")).first()
                if ubi:
                    ubi_id = ubi.id
                else:
                    safe_telegram_reply(message, f"⚠️ No se encontró la ubicación '{ubicacion_nombre}'. El producto quedará Sin Asignar.")
                    
            nuevo_prod = Producto(
                nombre=nombre.capitalize(),
                stock_actual=stock,
                stock_minimo=1.0,
                ubicacion_id=ubi_id,
                unidad_medida='unidades'
            )
            db.session.add(nuevo_prod)
            
            mov = Movimiento(
                descripcion=f"Añadido vía Telegram",
                producto_id=nuevo_prod.id,
                tipo="add",
                cantidad=stock
            )
            db.session.add(mov)
            db.session.commit()
            
            mov.producto_id = nuevo_prod.id
            db.session.commit()
            
            msg = f"✅ Producto '{nuevo_prod.nombre}' creado con éxito con {stock} unidades."
            if ubi_id:
                msg += f" (Ubicado en {ubi.nombre})"
            safe_telegram_reply(message, msg)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('sugerir_'))
    def callback_sugerir(call):
        if not is_authorized(call.message.chat.id): return
        if call.data == 'sugerir_ignorar':
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            return
            
        partes = call.data.split('_')
        if len(partes) >= 4 and partes[1] == 'add':
            ids_str = partes[-1]
            ids = [int(id_str) for id_str in ids_str.split(',')]
            
            with app.app_context():
                for p_id in ids:
                    producto = Producto.query.get(p_id)
                    if producto:
                        producto.en_lista = True
                db.session.commit()
                
            try:
                bot.edit_message_text("✅ Productos agregados a tu lista de compras.", chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass


# ==========================================
# 5. RUTAS WEB Y API
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Usuario.query.filter(Usuario.username.ilike(username)).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'danger')
        
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if Usuario.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe', 'danger')
        else:
            new_user = Usuario(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_page'))

@app.route('/perfil')
@login_required
def perfil():
    return render_template('views/perfil.html', active_page='perfil')

@app.route('/api/generar_token', methods=['POST'])
@login_required
def generar_token():
    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    current_user.telegram_link_token = token
    db.session.commit()
    return jsonify({'token': token})

@app.before_request
def require_login():
    allowed_routes = ['login_page', 'register_page', 'static']
    if request.endpoint not in allowed_routes and not current_user.is_authenticated:
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect(url_for('login_page'))

@app.route('/finanzas')
@login_required
def finanzas_page():
    return render_template('views/finanzas.html', active_page='finanzas')

@app.route('/')
@login_required
def dashboard():
    hoy = datetime.now().date()
    mes_actual = hoy.month
    ano_actual = hoy.year
    
    # 1. Mis Tareas Pendientes (del usuario, hoy o vencidas, o TODAS si es admin)
    mis_tareas = []
    tareas = Tarea.query.all()
    es_admin = getattr(current_user, 'is_admin', False)
    
    for t in tareas:
        if current_user in t.usuarios or es_admin:
            current_date = t.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
            proxima = calcular_proxima_fecha(t, current_date)
            if t.tipo_frecuencia == 'fecha_fija':
                try: proxima = datetime.strptime(t.valor_frecuencia, '%Y-%m-%d').date()
                except: proxima = hoy
            if proxima <= hoy:
                # Es mi turno o soy admin?
                prox_user_id = calcular_proximo_turno(t)
                
                if prox_user_id == current_user.id or es_admin:
                    prox_user = Usuario.query.get(prox_user_id) if prox_user_id else None
                    nombre_asignado = prox_user.username if prox_user else "Todos/Nadie"
                    
                    if prox_user_id == current_user.id:
                        nombre_mostrar = t.nombre
                    else:
                        nombre_mostrar = f"{t.nombre} ({nombre_asignado})"
                        
                    mis_tareas.append({'nombre': nombre_mostrar, 'vencida': (hoy - proxima).days > 0})
                    
    # 2. Ranking del Hogar (completadas en mes actual)
    usuarios = Usuario.query.all()
    ranking = []
    for u in usuarios:
        completadas = HistorialTarea.query.filter(
            HistorialTarea.usuario_id == u.id,
            extract('month', HistorialTarea.fecha) == mes_actual,
            extract('year', HistorialTarea.fecha) == ano_actual
        ).count()
        ranking.append({'username': u.username, 'completadas': completadas})
    ranking.sort(key=lambda x: x['completadas'], reverse=True)
    
    # 3. Radar de Tareas Críticas (vencidas > 2 días)
    criticas = []
    for t in tareas:
        current_date = t.fecha_ultima_ejecucion or (hoy - timedelta(days=3))
        proxima = calcular_proxima_fecha(t, current_date)
        if t.tipo_frecuencia == 'fecha_fija':
            try: proxima = datetime.strptime(t.valor_frecuencia, '%Y-%m-%d').date()
            except: proxima = hoy
        dias_vencida = (hoy - proxima).days
        if dias_vencida > 2:
            criticas.append({'nombre': t.nombre, 'dias_vencida': dias_vencida})
            
    # 4. Medidor de Excusas (Skips en mes actual)
    skips_por_usuario = {}
    for u in usuarios:
        skips = SaltoTarea.query.filter(
            SaltoTarea.usuario_id == u.id,
            extract('month', SaltoTarea.fecha) == mes_actual,
            extract('year', SaltoTarea.fecha) == ano_actual
        ).count()
        skips_por_usuario[u.username] = skips
        
    # 5. Última Actividad (ultimos 5 registros: historiales o saltos)
    actividad = []
    historiales = HistorialTarea.query.order_by(HistorialTarea.fecha.desc()).limit(5).all()
    saltos = SaltoTarea.query.order_by(SaltoTarea.fecha.desc()).limit(5).all()
    
    for h in historiales:
        u = Usuario.query.get(h.usuario_id)
        t = Tarea.query.get(h.tarea_id)
        actividad.append({'tipo': 'completada', 'fecha': h.fecha, 'texto': f"{u.username} completó: {t.nombre}"})
        
    for s in saltos:
        u = Usuario.query.get(s.usuario_id)
        t = Tarea.query.get(s.tarea_id)
        actividad.append({'tipo': 'skip', 'fecha': s.fecha, 'texto': f"{u.username} saltó: {t.nombre}"})
        
    actividad.sort(key=lambda x: x['fecha'], reverse=True)
    actividad = actividad[:5]
    
    # 6. Finanzas
    gastos_mes = db.session.query(db.func.sum(Gasto.monto)).filter(
        extract('month', Gasto.fecha) == mes_actual,
        extract('year', Gasto.fecha) == ano_actual
    ).scalar() or 0.0
    balances = calcular_balances_globales()

    # 7. Logística (Próximo evento y agenda hoy/mañana)
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora = datetime.now(tz)
    fin_manana = (ahora + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    
    eventos_agenda = EventoLogistico.query.filter(
        EventoLogistico.fecha_inicio >= ahora,
        EventoLogistico.fecha_inicio <= fin_manana
    ).order_by(EventoLogistico.fecha_inicio.asc()).limit(3).all()
    
    proximo_evento = EventoLogistico.query.filter(
        EventoLogistico.fecha_inicio >= ahora
    ).order_by(EventoLogistico.fecha_inicio.asc()).first()

    return render_template('views/dashboard.html', 
        active_page='dashboard',
        mis_tareas=mis_tareas,
        ranking=ranking,
        criticas=criticas,
        skips_por_usuario=skips_por_usuario,
        actividad=actividad,
        gastos_mes=gastos_mes,
        balances=balances,
        eventos_agenda=eventos_agenda,
        proximo_evento=proximo_evento,
        usuarios=usuarios
    )

@app.route('/inventario')
def inventario():
    return render_template('views/inventario.html', active_page='inventario')

@app.route('/compras')
def compras():
    return render_template('views/compras.html', active_page='compras')

# === Usuarios CRUD (Admin) ===
@app.route('/api/usuarios', methods=['GET'])
@admin_required
def get_usuarios():
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios])

@app.route('/api/usuarios', methods=['POST'])
@admin_required
def crear_usuario():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
        
    if Usuario.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'El usuario ya existe'}), 400
        
    u = Usuario(username=data['username'], is_admin=data.get('is_admin', False))
    u.set_password(data['password'])
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict()), 201

@app.route('/api/usuarios/<int:id_user>', methods=['DELETE'])
@admin_required
def delete_usuario(id_user):
    if current_user.id == id_user:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400
    u = Usuario.query.get_or_404(id_user)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'mensaje': 'Usuario eliminado'})

@app.route('/api/usuarios/<int:id_user>', methods=['PUT'])
@admin_required
def update_usuario(id_user):
    data = request.get_json()
    u = Usuario.query.get_or_404(id_user)
    
    if 'is_admin' in data:
        if current_user.id == id_user and not data['is_admin']:
            return jsonify({'error': 'No puedes quitarte tu propio rol de admin'}), 400
        u.is_admin = data['is_admin']
        
    if 'password' in data and data['password']:
        u.set_password(data['password'])
        
    db.session.commit()
    return jsonify({'mensaje': 'Usuario actualizado'})

@app.route('/api/usuarios/<int:id>/password', methods=['PUT'])
@login_required
def change_password(id):
    if current_user.id != id and not current_user.is_admin:
        return jsonify({'error': 'No tienes permisos para cambiar esta contraseña'}), 403
        
    data = request.get_json()
    if not data or 'nueva_password' not in data:
        return jsonify({'error': 'Falta la nueva contraseña'}), 400
        
    u = Usuario.query.get_or_404(id)
    u.set_password(data['nueva_password'])
    db.session.commit()
    return jsonify({'mensaje': 'Contraseña actualizada correctamente'})

# === Espacios (Salas, Ubicaciones, SubUbicaciones, Comercios) ===
@app.route('/api/espacios', methods=['GET'])
def obtener_espacios():
    salas = Sala.query.all()
    return jsonify([s.to_dict() for s in salas])

@app.route('/api/salas', methods=['POST'])
def crear_sala():
    return crud_create(Sala, ['nombre'], ['piso'])

@app.route('/api/sala/editar/<int:id>', methods=['PUT'])
def editar_sala(id):
    return crud_update(Sala, id, ['nombre'])

@app.route('/api/salas/<int:id_sala>', methods=['DELETE'])
def eliminar_sala(id_sala):
    s = Sala.query.get_or_404(id_sala)
    for u in s.ubicaciones:
        for su in u.sub_ubicaciones:
            for p in su.productos:
                p.sub_ubicacion_id = None
                p.ubicacion_id = None
        for p in u.productos:
            p.ubicacion_id = None
            p.sub_ubicacion_id = None
    db.session.delete(s)
    db.session.commit()
    return jsonify({'mensaje': 'Sala eliminada y productos movidos a Sin asignar'})

@app.route('/api/ubicaciones', methods=['POST'])
def crear_ubicacion():
    return crud_create(Ubicacion, ['nombre', 'sala_id'])

@app.route('/api/ubicacion/editar/<int:id>', methods=['PUT'])
def editar_ubicacion(id):
    return crud_update(Ubicacion, id, ['nombre'])

@app.route('/api/ubicaciones/<int:id_ubi>', methods=['DELETE'])
def eliminar_ubicacion(id_ubi):
    u = Ubicacion.query.get_or_404(id_ubi)
    for su in u.sub_ubicaciones:
        for p in su.productos:
            p.sub_ubicacion_id = None
            p.ubicacion_id = None
    for p in u.productos:
        p.ubicacion_id = None
        p.sub_ubicacion_id = None
    db.session.delete(u)
    db.session.commit()
    return jsonify({'mensaje': 'Ubicacion eliminada y productos movidos a Sin asignar'})

@app.route('/api/sub_ubicaciones', methods=['POST'])
def crear_sububicacion():
    return crud_create(SubUbicacion, ['nombre', 'ubicacion_id'])

@app.route('/api/sububicacion/editar/<int:id>', methods=['PUT'])
def editar_sububicacion(id):
    return crud_update(SubUbicacion, id, ['nombre'])

@app.route('/api/sub_ubicaciones/<int:id_sub>', methods=['DELETE'])
def eliminar_sububicacion(id_sub):
    su = SubUbicacion.query.get_or_404(id_sub)
    for p in su.productos:
        p.sub_ubicacion_id = None
    db.session.delete(su)
    db.session.commit()
    return jsonify({'mensaje': 'Sububicacion eliminada y productos movidos a la Ubicación padre'})

@app.route('/api/comercios', methods=['GET'])
def obtener_comercios():
    comercios = Comercio.query.all()
    return jsonify([c.to_dict() for c in comercios])

@app.route('/api/comercios', methods=['POST'])
def crear_comercio():
    return crud_create(Comercio, ['nombre'])

@app.route('/api/comercios/<int:id_comercio>', methods=['PUT'])
def editar_comercio(id_comercio):
    return crud_update(Comercio, id_comercio, ['nombre'])

@app.route('/api/comercios/<int:id_comercio>', methods=['DELETE'])
def eliminar_comercio(id_comercio):
    c = Comercio.query.get_or_404(id_comercio)
    for p in c.productos:
        p.comercio_id = None
    db.session.delete(c)
    db.session.commit()
    return jsonify({'mensaje': 'Comercio eliminado'})


@app.route('/tareas')
@login_required
def tareas_view():
    return render_template('views/tareas.html', active_page='tareas')

@app.route('/api/modelos', methods=['GET'])
@login_required
def get_modelos():
    modelos = ModeloTarea.query.all()
    hoy = datetime.now().date()
    res = []
    for m in modelos:
        d = m.to_dict()
        current_date = m.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
        proxima = calcular_proxima_fecha(m, current_date)
        if m.tipo_frecuencia == 'fecha_fija':
            try: proxima = datetime.strptime(m.valor_frecuencia, '%Y-%m-%d').date()
            except: proxima = hoy
        d['proxima_fecha_calculada'] = proxima.isoformat()
        res.append(d)
    return jsonify(res)

@app.route('/api/tareas', methods=['GET'])
@login_required
def get_tareas_activas():
    # Return instantiated tasks (for table and dashboard)
    tareas = Tarea.query.all()
    return jsonify([t.to_dict() for t in tareas])

@app.route('/api/modelos', methods=['POST'])
@login_required
def crear_modelo():
    data = request.json
    if not data or 'nombre' not in data:
        return jsonify({'error': 'Falta el nombre'}), 400
    nueva = ModeloTarea(
        nombre=data['nombre'],
        tipo_frecuencia=data.get('tipo_frecuencia', 'dias'),
        valor_frecuencia=str(data.get('valor_frecuencia', '1')),
        prioridad=data.get('prioridad', 'Esencial'),
        alternar=data.get('alternar', True)
    )
    if 'fecha_inicio' in data and data['fecha_inicio']:
        nueva.fecha_ultima_ejecucion = datetime.strptime(data['fecha_inicio'], '%Y-%m-%d').date() - timedelta(days=1)
        
    if 'usuarios_ids' in data and isinstance(data['usuarios_ids'], list):
        for uid in data['usuarios_ids']:
            u = Usuario.query.get(uid)
            if u: nueva.usuarios.append(u)
            
    db.session.add(nueva)
    db.session.commit()
    return jsonify(nueva.to_dict()), 201

@app.route('/api/modelos/<int:id_modelo>', methods=['PUT'])
@login_required
def editar_modelo(id_modelo):
    data = request.json
    modelo = ModeloTarea.query.get_or_404(id_modelo)
    if 'nombre' in data:
        modelo.nombre = data['nombre']
    if 'tipo_frecuencia' in data:
        modelo.tipo_frecuencia = data['tipo_frecuencia']
    if 'valor_frecuencia' in data:
        modelo.valor_frecuencia = str(data['valor_frecuencia'])
    if 'prioridad' in data:
        modelo.prioridad = data['prioridad']
    if 'alternar' in data:
        modelo.alternar = data['alternar']
    if 'usuarios_ids' in data and isinstance(data['usuarios_ids'], list):
        modelo.usuarios.clear()
        for uid in data['usuarios_ids']:
            u = Usuario.query.get(uid)
            if u: modelo.usuarios.append(u)
    db.session.commit()
    return jsonify(modelo.to_dict())

@app.route('/api/modelos/<int:id_modelo>', methods=['DELETE'])
@login_required
def eliminar_modelo(id_modelo):
    modelo = ModeloTarea.query.get_or_404(id_modelo)
    
    # Unlink instantiated tasks instead of deleting them
    Tarea.query.filter_by(modelo_id=modelo.id).update({'modelo_id': None})
    
    db.session.delete(modelo)
    db.session.commit()
    return jsonify({'mensaje': 'Modelo Eliminado'})

@app.route('/api/tareas/<int:id_tarea>', methods=['DELETE'])
@login_required
def eliminar_tarea(id_tarea):
    tarea = Tarea.query.get_or_404(id_tarea)
    HistorialTarea.query.filter_by(tarea_id=tarea.id).delete()
    SaltoTarea.query.filter_by(tarea_id=tarea.id).delete()
    db.session.delete(tarea)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


@app.route('/api/tareas/<int:id_tarea>/skip', methods=['POST'])
@login_required
def skip_tarea(id_tarea):
    data = request.json
    if not data or 'motivo' not in data:
        return jsonify({'error': 'Falta el motivo'}), 400
        
    tarea = Tarea.query.get_or_404(id_tarea)
    
    now = datetime.now()
    saltos_mes = SaltoTarea.query.filter(
        SaltoTarea.usuario_id == current_user.id,
        extract('year', SaltoTarea.fecha) == now.year,
        extract('month', SaltoTarea.fecha) == now.month
    ).count()
    
    if saltos_mes >= 3:
        return jsonify({'error': 'Has alcanzado el límite de 3 delegaciones este mes.'}), 403
        
    nuevo_salto = SaltoTarea(
        tarea_id=tarea.id,
        usuario_id=current_user.id,
        motivo=data['motivo']
    )
    db.session.add(nuevo_salto)
    
    fake_historial = HistorialTarea(tarea_id=tarea.id, usuario_id=current_user.id)
    db.session.add(fake_historial)
    db.session.flush()
    
    nuevo_encargado_id = calcular_proximo_turno(tarea)
    nuevo_encargado_nombre = "Nadie"
    nuevo_encargado = None
    if nuevo_encargado_id:
        nuevo_encargado = Usuario.query.get(nuevo_encargado_id)
        if nuevo_encargado: nuevo_encargado_nombre = nuevo_encargado.username
        
    db.session.commit()
    
    skips_restantes = 3 - (saltos_mes + 1)
    
    # 1. Avisar al grupo
    mensaje_grupo = (f"⚠️ <b>{current_user.username}</b> ha delegado su turno de <b>{tarea.nombre}</b>.\n"
                     f"Motivo: {data['motivo']}\n"
                     f"(Le quedan {skips_restantes} skips este mes).\n"
                     f"El nuevo encargado es: <b>{nuevo_encargado_nombre}</b>")
    enviar_al_grupo(mensaje_grupo)
    
    # 2. Avisar al usuario por privado
    if nuevo_encargado:
        mensaje_privado = f"🔄 <b>{current_user.username}</b> te ha delegado una tarea.\n\nHoy es tu turno de: <b>{tarea.nombre}</b>."
        enviar_al_usuario(nuevo_encargado.id, mensaje_privado)
    
    return jsonify({'mensaje': 'Turno delegado con éxito', 'nuevo_encargado': nuevo_encargado_nombre}), 200

@app.route('/api/calendario_tareas', methods=['GET'])
@login_required
def calendario_tareas():
    # Only return actual Tarea instances, no projection needed!
    tareas = Tarea.query.all()
    eventos = []
    
    for t in tareas:
        usuarios_ids = [u.id for u in t.usuarios]
        nombres_asignados = [u.username for u in t.usuarios]
        
        if not t.alternar:
            label_asignados = "Todos (" + ", ".join(nombres_asignados) + ")"
            user_id = None
        elif len(nombres_asignados) > 1:
            label_asignados = f"{t.usuarios[0].username} (de {len(nombres_asignados)})"
            user_id = t.usuarios[0].id
        else:
            label_asignados = t.usuarios[0].username if t.usuarios else "Nadie"
            user_id = t.usuarios[0].id if t.usuarios else None
            
        prioridad_emoji = "🔹"
        if getattr(t, 'completada', False): prioridad_emoji = "✅"
        elif t.prioridad == 'Urgente': prioridad_emoji = "🔥"
        elif t.prioridad == 'Secundaria': prioridad_emoji = "💤"
            
        color = '#0d6efd' # Esencial
        if getattr(t, 'completada', False): color = '#198754' # Verde si esta completada
        elif t.prioridad == 'Urgente': color = '#dc3545'
        elif t.prioridad == 'Secundaria': color = '#6c757d'
        
        proxima = getattr(t, 'fecha_programada', None) or t.fecha_ultima_ejecucion
        if not proxima: continue
        
        eventos.append({
            'title': f"{prioridad_emoji} {t.nombre} ({label_asignados})",
            'start': proxima.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'tarea_id': t.id,
                'usuario_asignado': user_id,
                'nombre_tarea': t.nombre,
                'tipo_frecuencia': t.tipo_frecuencia,
                'valor_frecuencia': t.valor_frecuencia,
                'completada': getattr(t, 'completada', False)
            }
        })
                
    return jsonify(eventos)

# === REST Productos ===
@app.route('/api/productos', methods=['GET'])
def obtener_productos():
    productos = Producto.query.order_by(Producto.id).all()
    return jsonify([p.to_dict() for p in productos])

@app.route('/api/productos', methods=['POST'])
def agregar_producto():
    data = request.json
    if not data or 'nombre' not in data:
        return jsonify({'error': 'El nombre es obligatorio'}), 400

    nuevo_producto = Producto(
        nombre=data['nombre'],
        descripcion=data.get('descripcion', ''),
        comercio_id=data.get('comercio_id'),
        stock_actual=float(data.get('stock_actual', 0)),
        stock_minimo=float(data.get('stock_minimo', 1)),
        unidad_medida=data.get('unidad_medida', 'unidades'),
        es_temporal=data.get('es_temporal', False),
        ubicacion_id=data.get('ubicacion_id'),
        sub_ubicacion_id=data.get('sub_ubicacion_id')
    )
    db.session.add(nuevo_producto)
    
    m = Movimiento(descripcion=f"Se creó un nuevo producto: {nuevo_producto.nombre} con stock {nuevo_producto.stock_actual}", producto_id=nuevo_producto.id, tipo="creacion", cantidad=nuevo_producto.stock_actual)
    db.session.add(m)
    db.session.commit()
    return jsonify(nuevo_producto.to_dict()), 201

@app.route('/api/productos/<int:id_producto>', methods=['PUT'])
def editar_producto(id_producto):
    data = request.json
    if not data:
        return jsonify({'error': 'Faltan datos'}), 400
        
    producto = Producto.query.get_or_404(id_producto)
    
    if 'nombre' in data:
        producto.nombre = data['nombre']
    if 'descripcion' in data:
        producto.descripcion = data['descripcion']
    if 'comercio_id' in data:
        producto.comercio_id = data['comercio_id'] if data['comercio_id'] != '' else None
    if 'stock_actual' in data:
        producto.stock_actual = float(data['stock_actual'])
    if 'stock_minimo' in data:
        producto.stock_minimo = float(data['stock_minimo'])
    if 'unidad_medida' in data:
        producto.unidad_medida = data['unidad_medida']
    if 'ubicacion_id' in data:
        producto.ubicacion_id = data['ubicacion_id'] if data['ubicacion_id'] != '' else None
    if 'sub_ubicacion_id' in data:
        producto.sub_ubicacion_id = data['sub_ubicacion_id'] if data['sub_ubicacion_id'] != '' else None
    if 'en_lista' in data:
        producto.en_lista = data['en_lista']
        
    db.session.commit()
    
    m = Movimiento(descripcion=f"Se editó el producto: {producto.nombre}", producto_id=producto.id, tipo="edicion", cantidad=0)
    db.session.add(m)
    db.session.commit()
    
    return jsonify(producto.to_dict())

@app.route('/api/productos/<int:id_producto>', methods=['DELETE'])
def eliminar_producto(id_producto):
    producto = Producto.query.get_or_404(id_producto)
    db.session.delete(producto)
    db.session.commit()
    return jsonify({'mensaje': 'Producto eliminado exitosamente'})

@app.route('/api/producto/mover/<int:id_producto>', methods=['POST'])
def mover_producto(id_producto):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No se enviaron datos'}), 400
        
    producto = Producto.query.get_or_404(id_producto)
    if 'ubicacion_id' in data:
        producto.ubicacion_id = data['ubicacion_id'] if data['ubicacion_id'] else None
    if 'sub_ubicacion_id' in data:
        producto.sub_ubicacion_id = data['sub_ubicacion_id'] if data['sub_ubicacion_id'] else None
        
    db.session.commit()
    return jsonify({'mensaje': 'Ubicación actualizada', 'producto': producto.to_dict()})

@app.route('/api/productos/bulk-mover', methods=['POST'])
def bulk_mover_productos():
    data = request.json
    if not data or 'producto_ids' not in data:
        return jsonify({'error': 'Faltan IDs de productos'}), 400
        
    producto_ids = data['producto_ids']
    ubicacion_id = data.get('ubicacion_id')
    sub_ubicacion_id = data.get('sub_ubicacion_id')
    
    productos = Producto.query.filter(Producto.id.in_(producto_ids)).all()
    for p in productos:
        if 'ubicacion_id' in data:
            p.ubicacion_id = ubicacion_id if ubicacion_id else None
        if 'sub_ubicacion_id' in data:
            p.sub_ubicacion_id = sub_ubicacion_id if sub_ubicacion_id else None
            
    db.session.commit()
    return jsonify({'mensaje': f'{len(productos)} productos movidos con éxito'})

@app.route('/api/productos/bulk', methods=['POST'])
def crear_productos_bulk():
    data = request.get_json()
    if not data or 'sub_ubicacion_id' not in data or 'productos' not in data:
        return jsonify({'error': 'Faltan datos (sub_ubicacion_id o productos)'}), 400
        
    sub_ubicacion_id = data['sub_ubicacion_id']
    ubicacion_id = data.get('ubicacion_id')
    productos_lista = data['productos']
    
    if not productos_lista:
        return jsonify({'error': 'La lista de productos está vacía'}), 400
        
    nombres_enviados = [p['nombre'].strip().lower() for p in productos_lista]
    existentes = Producto.query.filter(
        Producto.sub_ubicacion_id == sub_ubicacion_id,
        db.func.lower(Producto.nombre).in_(nombres_enviados)
    ).all()
    
    mapa_existentes = {p.nombre.lower(): p for p in existentes}
    conflictos = []
    
    for prod_data in productos_lista:
        nombre_lower = prod_data['nombre'].strip().lower()
        if nombre_lower in mapa_existentes:
            if 'accion_duplicado' not in prod_data or not prod_data['accion_duplicado']:
                conflictos.append(prod_data['nombre'])
                
    if conflictos:
        return jsonify({'error': 'Conflictos encontrados', 'conflictos': list(set(conflictos))}), 409
        
    procesados = 0
    for prod_data in productos_lista:
        nombre_lower = prod_data['nombre'].strip().lower()
        if nombre_lower in mapa_existentes:
            accion = prod_data.get('accion_duplicado')
            existente = mapa_existentes[nombre_lower]
            if accion == 'sumar':
                existente.stock_actual += float(prod_data.get('stock_actual', 0))
                procesados += 1
            elif accion == 'sobreescribir':
                existente.stock_actual = float(prod_data.get('stock_actual', 1))
                existente.stock_minimo = float(prod_data.get('stock_minimo', 1))
                if 'unidad_medida' in prod_data:
                    existente.unidad_medida = prod_data['unidad_medida']
                existente.comercio_id = prod_data.get('comercio_id')
                procesados += 1
        else:
            nuevo = Producto(
                nombre=prod_data['nombre'].strip(),
                stock_actual=float(prod_data.get('stock_actual', 1)),
                stock_minimo=float(prod_data.get('stock_minimo', 1)),
                unidad_medida=prod_data.get('unidad_medida', 'unidades'),
                ubicacion_id=ubicacion_id,
                sub_ubicacion_id=sub_ubicacion_id,
                comercio_id=prod_data.get('comercio_id')
            )
            db.session.add(nuevo)
            procesados += 1
        
    if procesados > 0:
        m = Movimiento(descripcion=f"Carga masiva: se procesaron {procesados} productos.", tipo="carga_masiva", cantidad=procesados)
        db.session.add(m)
    
    db.session.commit()
    return jsonify({'mensaje': f'{procesados} productos procesados correctamente.'}), 201

@app.route('/api/productos/<int:id_producto>/stock', methods=['PATCH'])
def actualizar_stock(id_producto):
    data = request.get_json()
    if not data or 'stock_actual' not in data:
        return jsonify({'error': 'Se requiere el campo stock_actual'}), 400
        
    producto = Producto.query.get_or_404(id_producto)
    diff = float(data['stock_actual']) - producto.stock_actual
    
    if abs(diff) > 0.001:
        accion = "Se agregaron" if diff > 0 else "Se descontaron"
        m = Movimiento(descripcion=f"{accion} {abs(diff)} {producto.unidad_medida} de {producto.nombre}", producto_id=producto.id, tipo="ajuste_stock", cantidad=diff)
        db.session.add(m)
        
    producto.stock_actual = float(data['stock_actual'])
    alerta_enviada = False
    
    if producto.es_temporal and producto.stock_actual <= 0:
        db.session.delete(producto)
        db.session.commit()
        return jsonify({'mensaje': 'Producto temporal consumido y eliminado', 'alerta_enviada': False})
    
    if producto.stock_actual <= producto.stock_minimo and not producto.en_lista:
        producto.en_lista = True
        ubi_str = producto.rel_ubicacion.nombre if producto.rel_ubicacion else "Sin asignar"
        comercio_nombre = producto.rel_comercio.nombre if producto.rel_comercio else "Sin Comercio"
        mensaje = (
            f"⚠️ <b>Alerta de Stock Bajo</b>\n\n"
            f"El producto <b>{producto.nombre}</b> ({ubi_str})\n"
            f"ha bajado a {producto.stock_actual} unidad(es).\n\n"
            f"🛒 <i>Se ha añadido automáticamente a la lista ({comercio_nombre}).</i>"
        )
        enviar_al_grupo(mensaje)
        alerta_enviada = True
                
    db.session.commit()
    return jsonify({
        'mensaje': 'Stock actualizado',
        'producto': producto.to_dict(),
        'alerta_enviada': alerta_enviada
    })

@app.route('/api/productos/<int:id_producto>/lista', methods=['PATCH'])
def actualizar_estado_lista(id_producto):
    data = request.get_json()
    if not data or 'en_lista' not in data:
        return jsonify({'error': 'Se requiere el campo en_lista'}), 400
    producto = Producto.query.get_or_404(id_producto)
    producto.en_lista = data['en_lista']
    db.session.commit()
    return jsonify({'mensaje': 'Estado en la lista actualizado', 'producto': producto.to_dict()})

@app.route('/api/compras/bulk', methods=['POST'])
def crear_compras_bulk():
    data = request.get_json()
    if not data or 'sub_ubicacion_id' not in data or 'productos' not in data:
        return jsonify({'error': 'Faltan datos (sub_ubicacion_id o productos)'}), 400
        
    sub_ubicacion_id = data['sub_ubicacion_id']
    ubicacion_id = data.get('ubicacion_id')
    productos_lista = data['productos']
    
    if not productos_lista:
        return jsonify({'error': 'La lista de productos está vacía'}), 400
        
    procesados = 0
    for prod_data in productos_lista:
        nuevo_prod = Producto(
            nombre=prod_data['nombre'].strip(),
            comercio_id=prod_data.get('comercio_id'),
            stock_actual=0.0,
            stock_minimo=float(prod_data.get('cantidad', 1)),
            unidad_medida=prod_data.get('unidad_medida', 'unidades'),
            ubicacion_id=ubicacion_id,
            sub_ubicacion_id=sub_ubicacion_id,
            en_lista=True
        )
        db.session.add(nuevo_prod)
        procesados += 1
        
    m = Movimiento(descripcion=f"Carga rápida de compras: se añadieron {procesados} productos a la lista de compras.", tipo="carga_rapida", cantidad=procesados)
    db.session.add(m)
    db.session.commit()
    return jsonify({'mensaje': f'{procesados} productos añadidos a compras.'}), 201

@app.route('/api/compras/bulk-comprar', methods=['POST'])
def bulk_comprar():
    data = request.json
    if not data or 'productos' not in data:
        return jsonify({'error': 'Falta la lista de productos'}), 400
        
    ids = data['productos']
    productos = Producto.query.filter(Producto.id.in_(ids)).all()
    
    procesados = 0
    eliminados = 0
    for p in productos:
        if p.es_temporal:
            db.session.delete(p)
            eliminados += 1
        else:
            p.en_lista = False
            procesados += 1
            
    db.session.commit()
    return jsonify({'mensaje': f'Se removieron {procesados} productos de la lista y se eliminaron {eliminados} temporales.'})

@app.route('/api/añadir_rapido', methods=['POST'])
def añadir_rapido():
    data = request.json
    nuevo = Producto(
        nombre=data['nombre'],
        comercio_id=data.get('comercio_id'),
        stock_actual=0.0,
        stock_minimo=1.0,
        unidad_medida='unidades',
        en_lista=True,
        es_temporal=True
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201

@app.route('/api/producto/consumir_rapido/<int:id_producto>', methods=['POST'])
def consumir_rapido(id_producto):
    producto = Producto.query.get_or_404(id_producto)
    if producto.stock_actual > 0:
        producto.stock_actual -= 1
        m = Movimiento(descripcion=f"Consumo rápido: se descontó 1 {producto.nombre}", producto_id=producto.id, tipo="consumo", cantidad=-1)
        db.session.add(m)
        
        if producto.es_temporal and producto.stock_actual <= 0:
            db.session.delete(producto)
            db.session.commit()
            return jsonify({'mensaje': 'Producto temporal consumido y eliminado'})
            
        if producto.stock_actual <= producto.stock_minimo and not producto.en_lista:
            producto.en_lista = True
            ubi_str = producto.rel_ubicacion.nombre if producto.rel_ubicacion else "Sin asignar"
            comercio_nombre = producto.rel_comercio.nombre if producto.rel_comercio else "Sin Comercio"
            mensaje = (
                f"⚠️ <b>Alerta de Stock Bajo</b>\n\n"
                f"El producto <b>{producto.nombre}</b> ({ubi_str})\n"
                f"ha bajado a {producto.stock_actual} unidad(es).\n\n"
                f"🛒 <i>Se ha añadido automáticamente a la lista ({comercio_nombre}).</i>"
            )
            enviar_al_grupo(mensaje)
                    
        db.session.commit()
        return jsonify({'mensaje': 'Consumo rápido exitoso'})
    return jsonify({'error': 'Stock ya en 0'}), 400

@app.route('/api/marcar_comprado/<int:id_producto>', methods=['POST'])
def marcar_comprado(id_producto):
    producto = Producto.query.get_or_404(id_producto)
    if producto.es_temporal:
        db.session.delete(producto)
        accion = "eliminado_completamente"
    else:
        producto.en_lista = False
        accion = "removido_de_lista"
        
    db.session.commit()
    return jsonify({'mensaje': f'Producto {accion}', 'accion': accion})

@app.route('/api/telegram/enviar_lista', methods=['POST'])
def enviar_lista():
    if not bot or not CHAT_ID:
        return jsonify({'error': 'Telegram no configurado'}), 500
    data = request.get_json(silent=True) or {}
    comercio = data.get('comercio')
    try:
        enviar_listas_agrupadas(CHAT_ID, comercio)
        return jsonify({'mensaje': 'Listas enviadas con éxito'})
    except Exception as e:
        print(f"Error Telegram: {e}")
        return jsonify({'error': 'Error enviando mensaje'}), 500

@app.route('/api/dashboard_stats', methods=['GET'])
def dashboard_stats():
    alertas_stock = Producto.query.filter(Producto.es_temporal == False, Producto.stock_actual <= Producto.stock_minimo).all()
    
    compras = Producto.query.filter(Producto.en_lista == True).all()
    compras_agrupadas = {}
    for p in compras:
        nombre_comercio = p.rel_comercio.nombre if p.rel_comercio else "Sin Comercio"
        compras_agrupadas[nombre_comercio] = compras_agrupadas.get(nombre_comercio, 0) + 1
        
    hoy = datetime.now().date()
    limite_vencimiento = hoy + timedelta(days=7)
    por_vencer = Producto.query.filter(Producto.fecha_vencimiento != None, Producto.fecha_vencimiento <= limite_vencimiento).all()
    
    limite_inactivo = hoy - timedelta(days=30)
    inactivos = Producto.query.filter(Producto.fecha_ultima_compra != None, Producto.fecha_ultima_compra <= limite_inactivo).all()
    
    return jsonify({
        'alertas_stock': [p.to_dict() for p in alertas_stock],
        'compras_por_comercio': [{'comercio': k, 'cantidad': v} for k, v in compras_agrupadas.items()],
        'por_vencer': [p.to_dict() for p in por_vencer],
        'inactivos': [p.to_dict() for p in inactivos]
    })

@app.route('/api/dashboard/movimientos', methods=['GET'])
def get_movimientos():
    q = request.args.get('q', '').strip()
    query = Movimiento.query
    if q:
        query = query.filter(Movimiento.descripcion.ilike(f'%{q}%'))
        limit = 50
    else:
        limit = 10
        
    movs = query.order_by(Movimiento.fecha.desc()).limit(limit).all()
    return jsonify([{'id': m.id, 'descripcion': m.descripcion, 'fecha': m.fecha.strftime("%Y-%m-%d %H:%M")} for m in movs])



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

def iniciar_bot():
    if bot:
        print("Iniciando bot de Telegram en segundo plano...")
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Error en polling de Telegram: {e}")

# ================= WSGI ARRANQUE SEGURO =================
# Usar un archivo de bloqueo para asegurar que solo un worker en Gunicorn/Waitress 
# inicie el bot de Telegram y el APScheduler.
LOCK_FILE = "bot_scheduler.lock"


@app.route('/api/tareas/<int:id_tarea>/completar', methods=['POST'])
@login_required
def completar_tarea(id_tarea):
    tarea = Tarea.query.get_or_404(id_tarea)
    tarea.completada = True
    
    # Register in Historial
    hist = HistorialTarea(tarea_id=tarea.id, usuario_id=current_user.id)
    db.session.add(hist)
    
    # Update model's last execution date if applicable
    if tarea.modelo_id:
        mod = ModeloTarea.query.get(tarea.modelo_id)
        if mod:
            mod.fecha_ultima_ejecucion = datetime.now().date()
            
    db.session.commit()
    return jsonify({'mensaje': 'Tarea completada'})
    
@app.route('/api/generar_mes', methods=['POST'])
@login_required
def generar_mes():
    hoy = datetime.now().date()
    modelos = ModeloTarea.query.all()
    
    from dateutil.relativedelta import relativedelta
    fin_de_mes = hoy + relativedelta(day=31)
    
    nuevas_tareas = 0
    for m in modelos:
        # Compute dates up to fin_de_mes
        current_date = m.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
        
        usuarios_ids = [u.id for u in m.usuarios]
        if not usuarios_ids: continue
        
        # Determine starting index for turn rotation based on historial
        # For simplicity in generation, we can just randomly start or start at 0
        idx = 0 
        
        while True:
            proxima = calcular_proxima_fecha(m, current_date)
            if m.tipo_frecuencia == 'fecha_fija':
                try: proxima = datetime.strptime(m.valor_frecuencia, '%Y-%m-%d').date()
                except: proxima = hoy
                
            if proxima > fin_de_mes or proxima < hoy:
                break
                
            # Check if this task already exists for this date
            exists = Tarea.query.filter_by(modelo_id=m.id, fecha_programada=proxima).first()
            
            if not exists:
                nueva_tarea = Tarea(
                    nombre=m.nombre,
                    prioridad=m.prioridad,
                    tipo_frecuencia='fecha_fija',
                    valor_frecuencia=proxima.isoformat(),
                    fecha_programada=proxima,
                    fecha_ultima_ejecucion=proxima,
                    alternar=m.alternar,
                    modelo_id=m.id,
                    completada=False
                )
                
                # Assign users
                if m.alternar:
                    u = Usuario.query.get(usuarios_ids[idx])
                    if u: nueva_tarea.usuarios.append(u)
                    idx = (idx + 1) % len(usuarios_ids)
                else:
                    for uid in usuarios_ids:
                        u = Usuario.query.get(uid)
                        if u: nueva_tarea.usuarios.append(u)
                        
                db.session.add(nueva_tarea)
                nuevas_tareas += 1
                
            if m.tipo_frecuencia == 'fecha_fija':
                break
            
            current_date = proxima
            
    db.session.commit()
    return jsonify({'mensaje': f'Se generaron {nuevas_tareas} tareas para este mes.'})

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

def start_background_tasks():
    # Previene ejecuciones múltiples usando un archivo de bloqueo o variable de entorno
    if not os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "w") as f:
                f.write(str(os.getpid()))
                
            print(f"Worker {os.getpid()} está iniciando hilos de fondo...")
            threading.Thread(target=iniciar_bot, daemon=True).start()
            
            # APScheduler con zona horaria America/Argentina/Buenos_Aires
            tz = pytz.timezone('America/Argentina/Buenos_Aires')
            scheduler = BackgroundScheduler(timezone=tz)
            scheduler.add_job(func=check_low_stock, trigger="cron", hour=10, minute=0)
            scheduler.add_job(func=check_tareas_pendientes, trigger="cron", hour=9, minute=0)
            scheduler.add_job(func=enviar_resumen_matutino, trigger="cron", hour=8, minute=0)
            scheduler.add_job(func=cleanup_pending_commands, trigger="interval", hours=1)
            scheduler.start()
        except IOError:
            pass

# Intentar arrancar tareas de fondo solo una vez (compatible con WSGI)
start_background_tasks()


# ==========================================
# 12. ENDPOINTS NUEVOS MODULOS (STUBS)
# ==========================================

@app.route('/logistica')
@login_required
def logistica_page():
    return render_template('views/logistica.html', active_page='logistica')

@app.route('/api/logistica/eventos', methods=['GET'])
@login_required
def api_logistica_get():
    eventos = EventoLogistico.query.all()
    result = []
    for ev in eventos:
        result.append({
            'id': ev.id,
            'title': ev.titulo,
            'start': ev.fecha_inicio.isoformat(),
            'end': ev.fecha_fin.isoformat() if ev.fecha_fin else None
        })
    return jsonify(result)

@app.route('/api/logistica/eventos', methods=['POST'])
@login_required
def api_logistica_post():
    data = request.json
    try:
        # Front end manda 'YYYY-MM-DDTHH:MM' (hora local de BA)
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        
        # Parse naive dt and localize it
        dt_inicio_naive = datetime.strptime(data['start'], "%Y-%m-%dT%H:%M")
        f_inicio = tz.localize(dt_inicio_naive)
        
        f_fin = None
        if data.get('end'):
            dt_fin_naive = datetime.strptime(data['end'], "%Y-%m-%dT%H:%M")
            f_fin = tz.localize(dt_fin_naive)
            
        nuevo_evento = EventoLogistico(
            titulo=data['title'],
            fecha_inicio=f_inicio,
            fecha_fin=f_fin,
            creador_id=current_user.id
        )
        db.session.add(nuevo_evento)
        db.session.commit()
        return jsonify({'success': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/finanzas/ocr', methods=['POST'])
@login_required
def finanzas_ocr():
    try:
        data = request.json
        if not data or 'image_base64' not in data:
            return jsonify({'error': 'No se proporcionó imagen'}), 400
        
        image_base64 = data['image_base64']
        
        # Si tiene un header tipo data:image/jpeg;base64,... se lo quitamos
        if ',' in image_base64:
            image_base64 = image_base64.split(',', 1)[1]

        if not GEMINI_API_KEY:
            return jsonify({'error': 'Gemini API key no configurada'}), 500
            
        import tempfile
        import os
        
        # Guardar en temporal para subir a Gemini
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(base64.b64decode(image_base64))
            temp_file_path = temp_file.name

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            # Gemini python sdk admite subir el archivo local
            imagen_gemini = genai.upload_file(temp_file_path)
            
            prompt = "Eres un asistente contable. Analiza este ticket/factura y devuelve EXCLUSIVAMENTE un JSON con tres claves: 'descripcion' (resumen de la compra en 3-4 palabras), 'monto_total' (número float, el total final pagado), e 'items' (lista de productos si es legible). No uses markdown ni texto adicional."
            
            response = model.generate_content([prompt, imagen_gemini])
            
            resultado_str = response.text.strip()
            # Limpiar backticks por si la IA devuelve markdown
            if resultado_str.startswith('```json'):
                resultado_str = resultado_str.replace('```json', '').replace('```', '').strip()
            elif resultado_str.startswith('```'):
                resultado_str = resultado_str.replace('```', '').strip()
                
            resultado = json.loads(resultado_str)
            return jsonify(resultado), 200
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/finanzas/gasto', methods=['POST'])
@login_required
def agregar_gasto_api():
    try:
        data = request.json
        descripcion = data.get('descripcion')
        monto_total = float(data.get('monto_total', 0))
        deudores_ids = data.get('deudores_ids', []) # Lista de IDs de usuarios que deben pagar

        if not descripcion or monto_total <= 0 or not deudores_ids:
            return jsonify({'success': False, 'error': 'Faltan datos obligatorios o monto inválido.'}), 400

        nuevo_gasto = Gasto(
            usuario_id=current_user.id,
            monto=monto_total,
            descripcion=descripcion,
            fecha=datetime.now()
        )
        db.session.add(nuevo_gasto)
        db.session.flush()

        monto_por_persona = monto_total / len(deudores_ids)

        for u_id_str in deudores_ids:
            u_id = int(u_id_str)
            esta_pagado = (u_id == current_user.id)
            div = DivisionGasto(
                gasto_id=nuevo_gasto.id,
                usuario_id=u_id,
                monto_adeudado=monto_por_persona,
                esta_pagado=esta_pagado
            )
            db.session.add(div)

        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error agregando gasto API: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/finanzas/balances', methods=['GET'])
@login_required
def finanzas_balances():
    try:
        balances = calcular_balances_globales()
        return jsonify(balances), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/finanzas/exportar', methods=['GET'])
@login_required
def exportar_finanzas():
    try:
        import io
        import csv
        from flask import Response
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeceras
        writer.writerow(['ID_Gasto', 'Fecha', 'Concepto', 'Monto_Total', 'ID_Deudor', 'Nombre_Deudor', 'ID_Comprador', 'Nombre_Comprador', 'Monto_Adeudado', 'Esta_Pagado'])
        
        divisiones = DivisionGasto.query.join(Gasto).order_by(Gasto.fecha.desc()).all()
        for div in divisiones:
            gasto = div.rel_gasto
            comprador = Usuario.query.get(gasto.usuario_id)
            deudor = Usuario.query.get(div.usuario_id)
            
            writer.writerow([
                gasto.id,
                gasto.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                gasto.descripcion,
                gasto.monto,
                deudor.id if deudor else '',
                deudor.username if deudor else 'Desconocido',
                comprador.id if comprador else '',
                comprador.username if comprador else 'Desconocido',
                div.monto_adeudado,
                'Sí' if div.esta_pagado else 'No'
            ])
            
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=finanzas_homestock.csv"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
def consumir_receta(receta_id):
    with app.app_context():
        receta = Receta.query.get(receta_id)
        if not receta: return False
        
        for ing in receta.ingredientes:
            if ing.producto.stock_actual >= ing.cantidad_requerida:
                ing.producto.stock_actual -= ing.cantidad_requerida
            else:
                ing.producto.stock_actual = 0
        db.session.commit()
        return True

@app.route('/menus')
@login_required
def menus_page():
    return render_template('views/menus.html', active_page='menus')

@app.route('/api/menus/horarios', methods=['GET'])
@login_required
def api_horarios_get():
    horarios = HorarioComidas.query.all()
    # Si no hay, crear defaults
    if not horarios:
        defaults = [
            HorarioComidas(tipo_comida='Desayuno', hora_inicio=datetime.strptime('06:00', '%H:%M').time(), hora_fin=datetime.strptime('11:00', '%H:%M').time()),
            HorarioComidas(tipo_comida='Almuerzo', hora_inicio=datetime.strptime('11:00', '%H:%M').time(), hora_fin=datetime.strptime('15:00', '%H:%M').time()),
            HorarioComidas(tipo_comida='Merienda', hora_inicio=datetime.strptime('15:00', '%H:%M').time(), hora_fin=datetime.strptime('19:00', '%H:%M').time()),
            HorarioComidas(tipo_comida='Cena', hora_inicio=datetime.strptime('19:00', '%H:%M').time(), hora_fin=datetime.strptime('23:59', '%H:%M').time())
        ]
        db.session.bulk_save_objects(defaults)
        db.session.commit()
        horarios = HorarioComidas.query.all()
        
    res = []
    for h in horarios:
        res.append({
            'id': h.id,
            'tipo_comida': h.tipo_comida,
            'hora_inicio': h.hora_inicio.strftime('%H:%M'),
            'hora_fin': h.hora_fin.strftime('%H:%M')
        })
    return jsonify(res)

@app.route('/api/menus/horarios', methods=['POST'])
@login_required
def api_horarios_post():
    data = request.json
    try:
        for item in data:
            h = HorarioComidas.query.get(item['id'])
            if h:
                h.hora_inicio = datetime.strptime(item['hora_inicio'], '%H:%M').time()
                h.hora_fin = datetime.strptime(item['hora_fin'], '%H:%M').time()
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/menus/sugerir', methods=['GET'])
@login_required
def menus_sugerir():
    todas_recetas = Receta.query.all()
    posibles = []
    for rec in todas_recetas:
        puede_hacerse = True
        for ing in rec.ingredientes:
            if ing.producto.stock_actual < ing.cantidad_requerida:
                puede_hacerse = False
                break
        if puede_hacerse:
            posibles.append(rec)
            
    if not posibles:
        return jsonify({'error': 'No hay ingredientes suficientes para ninguna receta.'}), 404
        
    sugerida = random.choice(posibles)
    return jsonify({'id': sugerida.id, 'nombre': sugerida.nombre, 'tipo': sugerida.tipo, 'es_rapida': sugerida.es_rapida})

@app.route('/api/menus/sugerir_rapida', methods=['GET'])
@login_required
def menus_sugerir_rapida():
    rapidas = Receta.query.filter_by(es_rapida=True).all()
    if not rapidas:
        return jsonify({'error': 'No hay recetas rápidas cargadas.'}), 404
    sugerida = random.choice(rapidas)
    return jsonify({'id': sugerida.id, 'nombre': sugerida.nombre, 'tipo': sugerida.tipo, 'es_rapida': sugerida.es_rapida})

@app.route('/api/menus/semana/duplicar', methods=['POST'])
@login_required
def menus_duplicar():
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(tz).date()
    # Identificar la semana pasada (hace 7 a 14 dias)
    fecha_limite_inf = hoy - timedelta(days=14)
    fecha_limite_sup = hoy - timedelta(days=7)
    
    pasada = MenuSemanal.query.filter(MenuSemanal.fecha_asignada >= fecha_limite_inf, MenuSemanal.fecha_asignada <= fecha_limite_sup).all()
    if not pasada:
        return jsonify({'error': 'No hay menú la semana pasada para duplicar.'}), 404
        
    nuevos = []
    for m in pasada:
        nueva_fecha = m.fecha_asignada + timedelta(days=7)
        nuevo_menu = MenuSemanal(
            dia_semana=m.dia_semana,
            tipo_comida=m.tipo_comida,
            receta_id=m.receta_id,
            fecha_asignada=nueva_fecha
        )
        nuevos.append(nuevo_menu)
        
    db.session.bulk_save_objects(nuevos)
    db.session.commit()
    return jsonify({'success': True, 'duplicados': len(nuevos)}), 200

@app.route('/api/menus/eventos', methods=['GET'])
@login_required
def api_menus_get():
    menus = MenuSemanal.query.all()
    result = []
    for m in menus:
        # Fake a time based on meal type for visualization on fullcalendar if it's month view, or just map it to an all-day event
        result.append({
            'id': m.id,
            'title': f"[{m.tipo_comida}] {m.receta.nombre}",
            'start': m.fecha_asignada.isoformat(),
            'allDay': True,
            'color': 'var(--success-color)' if m.tipo_comida == 'Almuerzo' else 'var(--primary-color)'
        })
    return jsonify(result)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
