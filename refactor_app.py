import os
import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# This is a complex refactoring. We will write the new app.py directly.
new_code = """import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import whisper
import uuid
import re
import difflib
import random
import string
from functools import wraps
import pytz

# ==========================================
# 1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================

# Configuración global de PATH para que ffmpeg sea encontrado por whisper sin errores
ffmpeg_dir = r"C:\\Users\\tomga\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-8.1.2-full_build\\bin"
if ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + ffmpeg_dir

modelo_whisper = whisper.load_model("base")
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-homestock-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/homestock')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', TELEGRAM_CHAT_ID)

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

# ==========================================
# 3. HELPERS Y UTILIDADES
# ==========================================

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

def enviar_mensaje_a_todos(mensaje, parse_mode='HTML'):
    with app.app_context():
        usuarios = Usuario.query.filter(Usuario.telegram_chat_id != None).all()
        for u in usuarios:
            safe_telegram_send(u.telegram_chat_id, mensaje, parse_mode=parse_mode)

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

    @bot.message_handler(content_types=['voice'])
    def handle_voice(message):
        if not is_authorized(message.chat.id): return
        
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
            
            pending_voice_commands[message.chat.id] = (texto_transcrito, datetime.now())
            
            markup = InlineKeyboardMarkup()
            markup.row_width = 2
            markup.add(
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm_voice"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_voice")
            )
            
            safe_telegram_send(message.chat.id, f"🎙️ Escuché:\\n\\n_{texto_transcrito}_\\n\\n¿Procesar esta instrucción?", reply_markup=markup, parse_mode="Markdown")
                    
        except Exception as e:
            safe_telegram_send(message.chat.id, f"❌ Error interno: {str(e)}")
        finally:
            if ogg_path and os.path.exists(ogg_path):
                try:
                    os.remove(ogg_path)
                except:
                    pass

    @bot.callback_query_handler(func=lambda call: call.data in ['confirm_voice', 'cancel_voice'])
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
        
        if match_inv:
            rama = "inventario"
            texto_sin_accion = match_inv.group(2)
        elif match_comp:
            rama = "compras"
            texto_sin_accion = match_comp.group(2)
        elif match_resta:
            rama = "restar"
            texto_sin_accion = match_resta.group(2)
            
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

                    db.session.commit()
                    
                    if respuestas:
                        markup_undo = InlineKeyboardMarkup()
                        markup_undo.add(InlineKeyboardButton("↩️ Deshacer", callback_data=f"undo_{tx_id}"))
                        
                        if rama == "inventario":
                            safe_telegram_send(call.message.chat.id, "✅ Procesado:\\n- " + "\\n- ".join(respuestas), reply_markup=markup_undo)
                        elif rama == "compras":
                            safe_telegram_send(call.message.chat.id, "🛒 Añadido a compras:\\n- " + "\\n- ".join(respuestas), reply_markup=markup_undo)
                        elif rama == "restar":
                            safe_telegram_send(call.message.chat.id, "➖ Descontado del inventario:\\n- " + "\\n- ".join(respuestas), reply_markup=markup_undo)
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
        safe_telegram_reply(message, "¡Hola! Bienvenido a Homestock. Para vincular tu cuenta, ingresa a la aplicación web, ve a tu Perfil, genera un token y envíalo aquí con el comando:\\n/vincular <Tu Token>")

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
                mensaje = f"Tienes {len(productos)} productos en **{comercio}** por debajo del mínimo. ¿Deseas agregarlos a la lista de compras?\\n\\n"
                for p in productos:
                    mensaje += f"- {p.nombre} (Stock: {p.stock_actual}/{p.stock_minimo})\\n"
                
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
            safe_telegram_reply(message, "No se pudo interpretar el formato. Asegúrate de incluir el stock.\\nEjemplo: /añadir Leche 2 Heladera")
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

@app.route('/')
def dashboard():
    return render_template('views/dashboard.html', active_page='dashboard')

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

@app.route('/api/usuarios/<int:id_user>', methods=['DELETE'])
@admin_required
def delete_usuario(id_user):
    if current_user.id == id_user:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400
    u = Usuario.query.get_or_404(id_user)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'mensaje': 'Usuario eliminado'})

@app.route('/api/usuarios/<int:id_user>/rol', methods=['PUT'])
@admin_required
def update_rol(id_user):
    data = request.get_json()
    if 'is_admin' not in data:
        return jsonify({'error': 'Falta is_admin'}), 400
    if current_user.id == id_user:
        return jsonify({'error': 'No puedes cambiar tu propio rol'}), 400
    u = Usuario.query.get_or_404(id_user)
    u.is_admin = data['is_admin']
    db.session.commit()
    return jsonify({'mensaje': 'Rol actualizado'})

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
            f"⚠️ <b>Alerta de Stock Bajo</b>\\n\\n"
            f"El producto <b>{producto.nombre}</b> ({ubi_str})\\n"
            f"ha bajado a {producto.stock_actual} unidad(es).\\n\\n"
            f"🛒 <i>Se ha añadido automáticamente a la lista ({comercio_nombre}).</i>"
        )
        enviar_mensaje_a_todos(mensaje)
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
                f"⚠️ <b>Alerta de Stock Bajo</b>\\n\\n"
                f"El producto <b>{producto.nombre}</b> ({ubi_str})\\n"
                f"ha bajado a {producto.stock_actual} unidad(es).\\n\\n"
                f"🛒 <i>Se ha añadido automáticamente a la lista ({comercio_nombre}).</i>"
            )
            enviar_mensaje_a_todos(mensaje)
                    
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

@app.route('/api/dashboard/grafico', methods=['GET'])
def grafico_dashboard():
    salas = Sala.query.all()
    result = []
    for s in salas:
        total = sum(p.stock_actual for u in s.ubicaciones for p in u.productos)
        if total > 0:
            result.append({'sala': s.nombre, 'total': total})
    return jsonify(result)

@app.route('/api/stats/tendencias', methods=['GET'])
def estadisticas_tendencias():
    hace_30_dias = datetime.utcnow() - timedelta(days=30)
    movs = Movimiento.query.filter(Movimiento.fecha >= hace_30_dias, Movimiento.producto_id.isnot(None)).all()
    conteo = {}
    for m in movs:
        if m.producto_id not in conteo:
            conteo[m.producto_id] = 0
        conteo[m.producto_id] += 1
        
    top_5 = sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:5]
    result = []
    for pid, count in top_5:
        p = Producto.query.get(pid)
        if p:
            result.append({'nombre': p.nombre, 'movimientos': count})
            
    return jsonify(result)

# ==========================================
# 6. TAREAS PROGRAMADAS Y ARRANQUE
# ==========================================

def cleanup_pending_commands():
    ahora = datetime.now()
    vencidos = [chat_id for chat_id, data in pending_voice_commands.items() 
                if isinstance(data, tuple) and (ahora - data[1]) > timedelta(hours=1)]
    for chat_id in vencidos:
        pending_voice_commands.pop(chat_id, None)

def check_low_stock():
    with app.app_context():
        productos_bajos = Producto.query.filter(Producto.stock_actual <= Producto.stock_minimo, Producto.en_lista == False).all()
        if productos_bajos and ADMIN_CHAT_ID:
            nombres = [p.nombre for p in productos_bajos]
            mensaje = f"⚠️ Atención: Te estás quedando sin: {', '.join(nombres)}. ¿Los agrego a la lista de compras?"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🛒 Agregar todos a la lista", callback_data="add_low_stock"))
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
            scheduler.add_job(func=cleanup_pending_commands, trigger="interval", hours=1)
            scheduler.start()
        except IOError:
            pass

# Intentar arrancar tareas de fondo solo una vez (compatible con WSGI)
start_background_tasks()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
"""

with open("t:/Proyectos/Inventario_Casa/homestock_bot/app.py", "w", encoding="utf-8") as f:
    f.write(new_code)

print("Refactoring completado y guardado en app.py")
