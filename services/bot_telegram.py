from functools import wraps
import re
import uuid
import json
import logging
from collections import defaultdict
from datetime import datetime, date, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, Sala, Comercio, Movimiento, Tarea, HistorialTarea, EventoLogistico, Receta, MenuSemanal, HorarioComidas
from extensions import db, bot
from utils import is_authorized, formatear_fecha_amigable, consumir_receta
import difflib
import pytz
from google import genai
from services.gemini_service import check_api_quota_error, extraer_datos_evento, GEMINI_API_KEY

_bot_app = None

def get_app():
    global _bot_app
    if _bot_app:
        return _bot_app
    try:
        from app import app
        return app
    except ImportError:
        return None

def with_app_context(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        from app import bot_tenant_var
        with get_app().app_context():
            # If the first arg is a message/call, get chat id
            chat_id = None
            if args and hasattr(args[0], 'chat'):
                chat_id = args[0].chat.id
            elif args and hasattr(args[0], 'message'):
                chat_id = args[0].message.chat.id
            
            if chat_id:
                from models.database import Usuario
                u = Usuario.query.filter_by(telegram_chat_id=str(chat_id)).first()
                if u and u.casa_activa_id:
                    bot_tenant_var.set(str(u.casa_activa_id))
                    
            return func(*args, **kwargs)
    return wrapper


def safe_telegram_send(chat_id, mensaje, reply_markup=None, parse_mode='HTML'):
    if not bot:
        return False
    if parse_mode == 'Markdown':
        mensaje = mensaje.replace('**', '*')
    try:
        bot.send_message(chat_id, mensaje, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        err_str = str(e).lower()
        if "can't parse entities" in err_str and parse_mode:
            print(f"⚠️ Aviso: Falló el parseo {parse_mode}, enviando como texto plano. Error: {e}")
            try:
                bot.send_message(chat_id, mensaje, reply_markup=reply_markup, parse_mode=None)
                return True
            except Exception as e2:
                print(f"Error enviando mensaje plano a {chat_id}: {e2}")
                return False
        print(f"Error enviando mensaje a {chat_id}: {e}")
        return False

def safe_telegram_reply(message, texto, reply_markup=None, parse_mode='HTML'):
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
            print(f"⚠️ Aviso: Falló el parseo {parse_mode}, enviando como texto plano. Error: {e}")
            try:
                bot.reply_to(message, texto, reply_markup=reply_markup, parse_mode=None)
                return True
            except Exception as e2:
                print(f"Error enviando mensaje plano de respuesta: {e2}")
                return False
        print(f"Error respondiendo mensaje: {e}")
        return False

def enviar_al_grupo(mensaje, reply_markup=None, parse_mode='HTML'):
    from app import ADMIN_CHAT_ID
    from models.database import ConfiguracionGlobal
    with get_app().app_context():
        config = ConfiguracionGlobal.query.first()
        grupo_id = config.grupo_principal_telegram_id if config and config.grupo_principal_telegram_id else ADMIN_CHAT_ID
        if grupo_id:
            return safe_telegram_send(grupo_id, mensaje, reply_markup=reply_markup, parse_mode=parse_mode)
    return False

def enviar_al_usuario(usuario_id, mensaje, reply_markup=None, parse_mode='HTML'):
    from models.database import Usuario
    with get_app().app_context():
        usuario = db.session.get(Usuario, usuario_id)
        if usuario and usuario.telegram_chat_id:
            return safe_telegram_send(usuario.telegram_chat_id, mensaje, reply_markup=reply_markup, parse_mode=parse_mode)
    return False

def enviar_listas_agrupadas(chat_id, comercio_objetivo=None):
    if not _bot_app: return
    with _bot_app.app_context():
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


pending_voice_commands = {}
recent_transactions = {}
pending_ocr_confirmations = {}
pending_menu_config = {}
pending_dedup = {}


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
        with get_app().app_context():
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
        with get_app().app_context():
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
                model='gemini-2.0-flash',
                contents=prompt
            )
            safe_telegram_send(message.chat.id, response.text.strip(), parse_mode="Markdown")
    except Exception as e:
        if check_api_quota_error(e, message.chat.id):
            return
        logging.error(f"[Módulo Recetas] Error generando receta: {e}", exc_info=True)
        safe_telegram_send(message.chat.id, "❌ Error al generar la receta. Intenta nuevamente.")

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
        with get_app().app_context():
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
        with get_app().app_context():
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
        with get_app().app_context():
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



def registrar_handlers(bot, app):
    global _bot_app
    _bot_app = app
    # 1. COMANDOS
    @bot.message_handler(commands=['desvincular'])
    @with_app_context
    def cmd_desvincular(message):
        try:
            with get_app().app_context():
                user = Usuario.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
                if user:
                    user.telegram_chat_id = None
                    db.session.commit()
                    safe_telegram_send(message.chat.id, "✅ Tu cuenta ha sido desvinculada de este dispositivo. Puedes usar /vincular desde otro número para reconectar.")
                else:
                    safe_telegram_send(message.chat.id, "❌ No hay ninguna cuenta vinculada a este chat.")
        except Exception as e:
            print(f"Error en /desvincular: {e}")

    @bot.message_handler(commands=['ayuda', 'comandos'])
    @with_app_context
    def cmd_ayuda(message):
        texto = '''🤖 *Comandos de HomeStock*:
• /start - Inicia el bot y verifica el estado.
• /vincular - Conecta tu cuenta de HomeStock con este chat.
• /desvincular - Desconecta este chat de tu cuenta.
• /menu - Despliega el menú interactivo para gestionar las comidas y otras opciones.
• /compras - Muestra la lista de compras pendiente.
• /ping - Verifica si el bot está en línea.
• /ayuda - Muestra este mensaje.

💡 *Recuerda*: ¡También puedes hablarme normalmente! Pídeme recetas, dime qué compraste o pregúntame qué hay en el inventario y yo me encargo del resto.'''
        safe_telegram_send(message.chat.id, texto, parse_mode="Markdown")
    @bot.message_handler(commands=['compras'])
    @with_app_context
    def cmd_compras(message):
        if not is_authorized(message.from_user.id): return
        enviar_listas_agrupadas(message.chat.id)
    @bot.message_handler(commands=['ping'])
    @with_app_context
    def test_ping(message):
        print("🏓 PING RECIBIDO!")
        bot.reply_to(message, "¡Pong! El bot está vivo y escuchando.")

    @bot.message_handler(commands=['menus', 'menu'])
    @with_app_context
    def handle_menus_command(message):
        try:
            print(">>> HANDLER /MENU EJECUTADO")
            print(f"📩 COMANDO RECIBIDO: {message.text}")
            if not is_authorized(message.from_user.id): return
            bot.clear_step_handler_by_chat_id(message.chat.id)
            enviar_menu_principal(message.chat.id)
        except Exception as e:
            print(f"🔴 ERROR INTERNO EN HANDLER DE MENU: {e}")
            bot.reply_to(message, "Hubo un error interno. Revisa la consola.")

    @bot.message_handler(commands=['start'])
    @with_app_context
    def cmd_start(message):
        if is_authorized(message.from_user.id):
            bot.clear_step_handler_by_chat_id(message.chat.id)
            safe_telegram_reply(message, "¡Hola de nuevo! Aquí tienes el menú principal:")
            enviar_menu_principal(message.chat.id)
        else:
            safe_telegram_reply(message, "¡Hola! Bienvenido a Homestock. Para vincular tu cuenta, ingresa a la aplicación web, ve a tu Perfil, genera un token y envíalo aquí con el comando:\n/vincular <Tu Token>")

    @bot.message_handler(commands=['vincular'])
    @with_app_context
    def cmd_vincular(message):
        from sqlalchemy.exc import IntegrityError
        try:
            partes = message.text.split(maxsplit=1)
            
            if len(partes) < 2:
                safe_telegram_send(message.chat.id, "⚠️ Formato incorrecto. Debes usar: /vincular TU_CODIGO")
                return
                
            codigo_ingresado = partes[1].strip()
            print(f"🔗 Intento de vinculación - Chat ID: {message.chat.id} - Código: {codigo_ingresado}")
            
            with get_app().app_context():
                try:
                    # Buscar al usuario por su código
                    usuario = db.session.query(Usuario).filter_by(telegram_link_token=codigo_ingresado).first()
                    
                    if not usuario:
                        safe_telegram_send(message.chat.id, "❌ Código de vinculación inválido o no existe.")
                        return
                        
                    # Verificar si ya tiene un ID asignado (y no es el mismo)
                    if usuario.telegram_chat_id and str(usuario.telegram_chat_id).strip() != "":
                        if str(usuario.telegram_chat_id) == str(message.chat.id):
                            safe_telegram_send(message.chat.id, "✅ Este dispositivo ya está vinculado a esta cuenta.")
                        else:
                            safe_telegram_send(message.chat.id, "⚠️ Este código ya está en uso por otro dispositivo. Desvincúlalo primero.")
                        return

                    # Prevención de Unique Constraint: desvincular el dispositivo de cualquier otro usuario previo
                    old_user = db.session.query(Usuario).filter_by(telegram_chat_id=str(message.chat.id)).first()
                    if old_user and old_user.id != usuario.id:
                        old_user.telegram_chat_id = None
                        print(f"⚠️ Se desvinculó automáticamente la cuenta '{old_user.username}' del dispositivo {message.chat.id} por conflicto de unicidad.")

                    # Asignar el nuevo ID
                    usuario.telegram_chat_id = str(message.chat.id)
                    usuario.telegram_link_token = None
                    db.session.commit() # ¡CRÍTICO!
                    
                    rol_str = "(Admin)" if usuario.is_admin else ""
                    safe_telegram_send(message.chat.id, f"✅ ¡Vinculación exitosa! Bienvenido/a, {usuario.username} {rol_str}.")
                    print(f"✅ ÉXITO: Chat {message.chat.id} vinculado al usuario {usuario.username}")
                    
                except IntegrityError as e:
                    db.session.rollback()
                    print(f"🔴 ERROR DE INTEGRIDAD (PostgreSQL): {e}")
                    safe_telegram_send(message.chat.id, "Error en la base de datos (Unique Constraint). Revisa la consola.")
                except Exception as e:
                    db.session.rollback()
                    print(f"🔴 ERROR GENERAL EN VINCULAR: {e}")
                    safe_telegram_send(message.chat.id, "Ocurrió un error interno.")
        except Exception as e:
            print(f"🔴 ERROR FUERA DEL CONTEXTO EN VINCULAR: {e}")
            safe_telegram_send(message.chat.id, "❌ Ocurrió un error general.")

    @bot.message_handler(commands=['balance'])
    @with_app_context
    def handle_balance(message):
        if not is_authorized(message.from_user.id): return
        balances = calcular_balances_globales()
        if not balances:
            safe_telegram_reply(message, "🎉 ¡Todo está al día! Nadie le debe dinero a nadie en la casa.")
            return
        
        respuesta = "⚖️ <b>Balances Actuales de la Casa:</b>\n\n"
        for b in balances:
            respuesta += f"🔹 <b>{b['deudor_nombre']}</b> le debe a <b>{b['acreedor_nombre']}</b>: ${b['monto']}\n"
        
        safe_telegram_reply(message, respuesta, parse_mode='HTML')

    @bot.message_handler(commands=['comprado'])
    @with_app_context
    def handle_comprado(message):
        if not is_authorized(message.from_user.id): return
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

        with get_app().app_context():
            producto = Producto.query.filter(Producto.nombre.ilike(f"%{nombre_producto}%")).first()
            if not producto:
                safe_telegram_reply(message, f"❌ No encontré '{nombre_producto}' en la base de datos.")
                return
                
            producto.stock_actual += cantidad
            producto.en_lista = False
            db.session.commit()
            safe_telegram_reply(message, f"✅ '{producto.nombre}' actualizada. Nuevo stock: {producto.stock_actual}")

    @bot.message_handler(commands=['test_lista'])
    @with_app_context
    def cmd_test_lista(message):
        if not is_authorized(message.from_user.id): return
        enviar_listas_agrupadas(message.chat.id)

    @bot.message_handler(commands=['sugerir_compra'])
    @with_app_context
    def sugerir_compra(message):
        if not is_authorized(message.from_user.id): return
        with get_app().app_context():
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
    @with_app_context
    def cmd_anadir(message):
        if not is_authorized(message.from_user.id): return
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
        
        with get_app().app_context():
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

    @bot.message_handler(commands=['cancelar'])
    @with_app_context
    def cmd_cancelar(message):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.reply_to(message, '🛑 Operación cancelada. Puedes continuar con normalidad.')

    # 2. CALLBACKS
    @bot.callback_query_handler(func=lambda call: call.data == 'ver_compras')
    @with_app_context
    def callback_ver_compras(call):
        bot.answer_callback_query(call.id)
        if not is_authorized(call.from_user.id): return
        enviar_listas_agrupadas(call.message.chat.id)
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
        with get_app().app_context():
            comprador = db.session.get(Usuario, data['usuario_id'])
            if call.data == 'ocr_div_mio':
                todos_usuarios = [comprador]
            else:
                todos_usuarios = Usuario.query.all()
            
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
            
            items = data.get('items', [])
            if items:
                items_agregados = []
                for it in items:
                    if not isinstance(it, dict): continue
                    nombre_prod = str(it.get('nombre', '')).strip().capitalize()
                    try:
                        cantidad_prod = float(it.get('cantidad', 1.0))
                    except:
                        cantidad_prod = 1.0
                    if not nombre_prod: continue

                    prod_db = Producto.query.filter(Producto.nombre.ilike(f"%{nombre_prod}%")).first()
                    if prod_db:
                        prod_db.stock_actual += cantidad_prod
                        mov = Movimiento(descripcion="Añadido por compra/gasto", producto_id=prod_db.id, tipo="add", cantidad=cantidad_prod)
                        db.session.add(mov)
                    else:
                        nuevo_prod = Producto(
                            nombre=nombre_prod,
                            stock_actual=cantidad_prod,
                            stock_minimo=1.0
                        )
                        db.session.add(nuevo_prod)
                        db.session.flush()
                        mov = Movimiento(descripcion="Creado por compra/gasto", producto_id=nuevo_prod.id, tipo="add", cantidad=cantidad_prod)
                        db.session.add(mov)
                    items_agregados.append(f"{round(cantidad_prod, 2)}x {nombre_prod}")
                db.session.commit()
                if items_agregados:
                    safe_telegram_send(chat_id, "📦 **Inventario actualizado automáticamente:**\n- " + "\n- ".join(items_agregados), parse_mode="Markdown")

            bot.edit_message_text(f"✅ ¡Gasto registrado exitosamente!\nConcepto: {data['descripcion']}\nCada usuario debe: ${round(monto_por_persona, 2)}", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data in ['dedup_yes', 'dedup_no'])
    @with_app_context
    def handle_dedup_callback(call):
        if not is_authorized(call.from_user.id): return
        chat_id = call.message.chat.id
        data = pending_dedup.pop(chat_id, None)
        if not data:
            bot.edit_message_text(" La solicitud de confirmacin ha expirado.", chat_id, call.message.message_id)
            return
        with get_app().app_context():
            if call.data == 'dedup_yes':
                prod = db.session.get(Producto, data['sim_id'])
                if prod:
                    prod.stock_actual += data['cantidad']
                    mov = Movimiento(descripcion="Aadido (coincidencia confirmada)", producto_id=prod.id, tipo="add", cantidad=data['cantidad'])
                    db.session.add(mov)
                    db.session.commit()
                    bot.edit_message_text(f" Sumado {data['cantidad']}x a '{prod.nombre}'. Stock actual: {prod.stock_actual}", chat_id, call.message.message_id)
                    return
            nuevo_prod = Producto(
                nombre=data['new_nombre'],
                stock_actual=data['cantidad'],
                stock_minimo=1.0,
                ubicacion_id=data['ubicacion_id']
            )
            db.session.add(nuevo_prod)
            db.session.flush()
            mov = Movimiento(descripcion="Creado por Voz", producto_id=nuevo_prod.id, tipo="add", cantidad=data['cantidad'])
            db.session.add(mov)
            db.session.commit()
            bot.edit_message_text(f" Creado nuevo producto: {data['cantidad']}x '{nuevo_prod.nombre}'.", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('done_tarea_'))
    @with_app_context
    def handle_done_tarea(call):
        tarea_id_str = call.data.replace('done_tarea_', '')
        try:
            tarea_id = int(tarea_id_str)
            from models.database import Tarea
            tarea = db.session.get(Tarea, tarea_id)
            if not tarea:
                bot.answer_callback_query(call.id, "❌ Tarea no encontrada.")
                return
                
            tarea.completada = True
            db.session.commit()
            
            bot.answer_callback_query(call.id, f"✅ Tarea completada: {tarea.nombre}")
            
            # Quitar el botón del mensaje para evitar clicks repetidos
            nuevo_texto = f"{call.message.text}\n\n✅ <i>Completada por {call.from_user.first_name}</i>"
            bot.edit_message_text(nuevo_texto, call.message.chat.id, call.message.message_id, reply_markup=None, parse_mode='HTML')
            
        except ValueError:
            bot.answer_callback_query(call.id, "❌ ID inválido.")

    @bot.callback_query_handler(func=lambda call: True)
    @with_app_context
    def callback_inline(call):
        if not is_authorized(call.from_user.id): return
        if call.data in ['confirm_voice', 'cancel_voice']:
            callback_voice(call)
            return
        if call.data in ['confirm_logistica', 'cancel_logistica']:
            handle_logistica_callback(call)
            return
        if call.data in ['confirm_menu', 'cancel_menu'] or call.data.startswith('menu_dia_') or call.data.startswith('menu_tipo_'):
            handle_menu_callback(call)
            return

    @bot.callback_query_handler(func=lambda call: call.data.startswith('undo_'))
    def callback_undo(call):
        tx_id = call.data.replace('undo_', '')
        if tx_id not in recent_transactions:
            bot.answer_callback_query(call.id, "⚠️ Esta acción ya expiró o fue deshecha.")
            return
            
        operaciones = recent_transactions.pop(tx_id)
        try:
            with get_app().app_context():
                for op in operaciones:
                    prod = db.session.get(Producto, op['producto_id'])
                    if not prod: continue
                    
                    
                    if op.get('is_tarea'):
                        if 'historial_id' in op:
                            h = db.session.get(HistorialTarea, op['historial_id'])
                            if h: db.session.delete(h)
                        if 'tarea_id' in op:
                            t = db.session.get(Tarea, op['tarea_id'])
                            if t and 'old_date' in op:
                                t.fecha_ultima_ejecucion = op['old_date']
                        continue

                    if op.get('is_new'):
                        if 'movimiento_id' in op:
                            mov = db.session.get(Movimiento, op['movimiento_id'])
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
                            mov = db.session.get(Movimiento, op['movimiento_id'])
                            if mov: db.session.delete(mov)
                db.session.commit()
            bot.edit_message_text("↩️ Acción deshecha correctamente.", call.message.chat.id, call.message.message_id)
        except Exception as e:
            safe_telegram_send(call.message.chat.id, f"❌ Error al deshacer: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data == 'add_low_stock')
    @with_app_context
    def callback_add_low_stock(call):
        try:
            with get_app().app_context():
                productos_bajos = Producto.query.filter(Producto.stock_actual <= Producto.stock_minimo, Producto.en_lista == False).all()
                for p in productos_bajos:
                    p.en_lista = True
                db.session.commit()
            bot.edit_message_text("✅ Productos agregados a la lista de compras.", call.message.chat.id, call.message.message_id)
        except Exception as e:
            safe_telegram_send(call.message.chat.id, f"❌ Error: {str(e)}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('comprar_'))
    def callback_comprar(call):
        if not is_authorized(call.from_user.id): return
        producto_id = int(call.data.split('_')[1])
        with get_app().app_context():
            producto = db.session.get(Producto, producto_id)
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith('sugerir_'))
    def callback_sugerir(call):
        if not is_authorized(call.from_user.id): return
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
            
            with get_app().app_context():
                for p_id in ids:
                    producto = db.session.get(Producto, p_id)
                    if producto:
                        producto.en_lista = True
                db.session.commit()
                
            try:
                bot.edit_message_text("✅ Productos agregados a tu lista de compras.", chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass

    # 3. TEXTO / CATCH-ALL
    @bot.message_handler(content_types=['photo', 'document'])
    @with_app_context
    def handle_photo(message):
        chat_id = message.chat.id

        # Feedback inmediato ANTES de cualquier proceso pesado
        try:
            bot.send_message(chat_id, '📸 Recibí el ticket. Analizando con IA, dame unos segundos...')
        except Exception as send_err:
            print(f'[handle_photo] No pude enviar ACK: {send_err}')

        if not GEMINI_API_KEY:
            try:
                bot.send_message(chat_id, '❌ Gemini no está configurado. Sube el gasto manualmente en la web.')
            except Exception as silent_e:
                import logging
                logging.error(f"Fallo enviando mensaje de error al usuario: {silent_e}")
            return

        try:
            with get_app().app_context():
                # Buscar usuario (reemplaza la función inexistente get_usuario_por_chat)
                usuario = Usuario.query.filter_by(telegram_chat_id=str(message.from_user.id)).first()
                if not usuario:
                    bot.send_message(chat_id, '❌ Tu cuenta no está vinculada. Usá /vincular <token> para conectarla.')
                    return

                # Descargar la imagen de Telegram
                if message.content_type == 'photo':
                    file_id = message.photo[-1].file_id
                else:
                    file_id = message.document.file_id

                file_info = bot.get_file(file_id)
                downloaded_file = bot.download_file(file_info.file_path)

                try:
                    # Enviar la imagen directamente en linea (bypass de disco)
                    imagen_gemini = genai.types.Part.from_bytes(data=downloaded_file, mime_type='image/jpeg')
                    
                    client = genai.Client(api_key=GEMINI_API_KEY)

                    prompt = (
                        "Eres un asistente contable. Analiza este ticket/factura y devuelve "
                        "EXCLUSIVAMENTE un JSON con tres claves: 'descripcion' (resumen de la "
                        "compra en 3-4 palabras), 'monto_total' (numero float, el total final "
                        "pagado), e 'items' (un array de objetos donde cada objeto tiene 'nombre', 'cantidad' y 'precio_unitario'). "
                        "No uses markdown ni texto adicional."
                    )
                    response = client.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=[prompt, imagen_gemini]
                    )

                    resultado_str = response.text.strip()
                    if resultado_str.startswith('```json'):
                        resultado_str = resultado_str.replace('```json', '').replace('```', '').strip()
                    elif resultado_str.startswith('```'):
                        resultado_str = resultado_str.replace('```', '').strip()

                    resultado = json.loads(resultado_str)
                    monto_total = float(resultado.get('monto_total', 0))
                    descripcion = resultado.get('descripcion', 'Ticket')

                    if monto_total <= 0:
                        bot.send_message(chat_id, '❌ No pude detectar un monto válido. Verificá la foto e intentá de nuevo.')
                        return

                    pending_ocr_confirmations[chat_id] = {
                        'usuario_id': usuario.id,
                        'monto_total': monto_total,
                        'descripcion': descripcion
                    }

                    # Formatear el detalle de items
                    items_str = ""
                    items_list = resultado.get('items', [])
                    if items_list and isinstance(items_list, list):
                        for item in items_list:
                            cant = item.get('cantidad', 1)
                            nombre = item.get('nombre', 'Producto')
                            precio = item.get('precio_unitario', 0)
                            items_str += f"- {cant}x {nombre} (${precio})\n"
                    else:
                        items_str = "(No se detectaron items individuales)\n"

                    markup = InlineKeyboardMarkup()
                    markup.row(InlineKeyboardButton('👥 Dividir entre todos', callback_data='ocr_div_todos'))
                    markup.row(InlineKeyboardButton('🙋‍♂️ Solo mío (no dividir)', callback_data='ocr_div_mio'))
                    markup.row(InlineKeyboardButton('❌ Cancelar', callback_data='ocr_div_no'))
                    
                    bot.send_message(
                        chat_id,
                        f'🧾 <b>Detalle del Ticket</b>\n\n{items_str}\n<b>Total a pagar: ${monto_total}</b>\n\n¿Cómo querés registrar este gasto?',
                        reply_markup=markup,
                        parse_mode='HTML'
                    )

                finally:
                    pass

        except Exception as e:
            if check_api_quota_error(e, chat_id):
                return
            import traceback
            traceback.print_exc()
            print(f'[handle_photo] Error: {e}')
            try:
                bot.send_message(chat_id, f'❌ Falló la lectura: {str(e)}')
            except Exception as silent_e:
                import logging
                logging.error(f"Fallo enviando mensaje de error al usuario: {silent_e}")

    @bot.message_handler(content_types=['voice'])
    @with_app_context
    def handle_voice(message):
        logging.info("Mensaje de voz recibido.")
        if not is_authorized(message.from_user.id): return
        safe_telegram_reply(message, "🎤 El procesamiento de audios está desactivado temporalmente para ahorrar cuota de IA. Por favor, utiliza los botones del menú inferior para registrar datos.")

    @bot.message_handler(regexp=r"(?i)Finanzas")
    @with_app_context
    def handle_btn_finanzas(message):
        logging.info(f"Mensaje recibido: {message.text}")
        if not is_authorized(message.from_user.id): return
        msg = bot.send_message(message.chat.id, "💸 **Módulo Finanzas**\n\nElige un formato:\n\n*1. Gasto Simple*\n`Monto - Concepto - Detalle`\n\n*2. Ticket / Supermercado*\n`Lugar de compra`\n`Artículo 1 - Precio`\n`Artículo 2 - Precio`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, procesar_estado_finanzas)

    @bot.message_handler(regexp=r"(?i)Inventario")
    @with_app_context
    def handle_btn_inventario(message):
        logging.info(f"Mensaje recibido: {message.text}")
        if not is_authorized(message.from_user.id): return
        msg = bot.send_message(message.chat.id, "📦 **Módulo Inventario**\n\nEnvíame los datos con este formato:\n\nAcción - Producto - Cantidad\n\n_(Acciones permitidas: Alta, Baja, Modificar)_", parse_mode="Markdown")
        bot.register_next_step_handler(msg, procesar_estado_inventario)

    @bot.message_handler(regexp=r"(?i)Tareas")
    @with_app_context
    def handle_btn_tareas(message):
        logging.info(f"Mensaje recibido: {message.text}")
        if not is_authorized(message.from_user.id): return
        msg = bot.send_message(message.chat.id, "📋 **Módulo Tareas**\n\nEnvíame los datos con este formato:\n\nTarea - Prioridad - Vencimiento (DD/MM) - Asignado_a\n\n_(Prioridades: Alta, Media, Baja)\n(Asignado_a: 'Todos', o nombres como 'Juan, Ana')_", parse_mode="Markdown")
        bot.register_next_step_handler(msg, procesar_estado_tareas)

    @bot.message_handler(regexp=r"(?i)Logística")
    @with_app_context
    def handle_btn_logistica(message):
        logging.info(f"Mensaje recibido: {message.text}")
        if not is_authorized(message.from_user.id): return
        msg = bot.send_message(message.chat.id, "🚚 **Módulo Logística**\n\nEnvíame los datos con este formato:\n\nTítulo - Fecha (DD/MM) - Hora (HH:MM) - Asignado_a\n\n_(Asignado_a: 'Todos', o nombres como 'Juan, Ana')_", parse_mode="Markdown")
        bot.register_next_step_handler(msg, procesar_estado_logistica)

    @bot.message_handler(regexp=r"(?i)Comidas")
    @with_app_context
    def handle_btn_comidas(message):
        logging.info(f"Mensaje recibido: {message.text}")
        if not is_authorized(message.from_user.id): return
        procesar_menu_config(message)

    @bot.message_handler(regexp=r"(?i)Cancelar")
    @with_app_context
    def handle_btn_cancelar(message):
        logging.info(f"Mensaje recibido: {message.text}")
        if not is_authorized(message.from_user.id): return
        enviar_menu_principal(message.chat.id, "Volviendo al menú principal.")

    @bot.message_handler(content_types=['text'])
    @with_app_context
    def handle_catch_all(message):
        if message.chat.id in pending_menu_config:
            dia, tipo = pending_menu_config.pop(message.chat.id)
            guardar_menu_desde_bot(message.chat.id, dia, tipo, message.text.strip())
            return
            
        logging.warning(f"Mensaje no manejado: {message.text}")
        if not is_authorized(message.from_user.id): return
        if message.text.startswith('/'): return
        safe_telegram_reply(message, "No entendí ese comando. Por favor, usa los botones del menú.")
# ==========================================
# 🚀 STATE MACHINE HANDLERS (DETERMINISTIC)
# ==========================================

def enviar_menu_principal(chat_id, texto="Selecciona una opción del menú principal:"):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row(KeyboardButton("💰 Finanzas"), KeyboardButton("📦 Inventario"))
    markup.row(KeyboardButton("📋 Tareas"), KeyboardButton("🚚 Logística"))
    markup.row(KeyboardButton("🍽️ Comidas"), KeyboardButton("❌ Cancelar"))
    try:
        bot.send_message(chat_id, texto, reply_markup=markup)
    except Exception as e:
        print(f"Error enviando menu principal: {e}")

@with_app_context
def procesar_estado_finanzas(message):
    if not message.text or re.search(r"(?i)Cancelar", message.text):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        enviar_menu_principal(message.chat.id, "❌ Operación cancelada.")
        return
    try:
        with get_app().app_context():
            usuario = Usuario.query.filter_by(telegram_chat_id=str(message.from_user.id)).first()
            if not usuario:
                safe_telegram_send(message.chat.id, "❌ Tu cuenta no está vinculada.")
                return
                
            lineas = [l.strip() for l in message.text.split('\n') if l.strip()]
            if not lineas: return
            
            first_char = lineas[0][0]
            if first_char.isdigit() or first_char == '$':
                agregados = 0
                for linea in lineas:
                    partes = [p.strip() for p in linea.split('-')]
                    if len(partes) < 3:
                        raise ValueError(f"Formato incompleto: '{linea}'")
                    
                    monto = float(partes[0].replace('$', '').replace(',', '').strip())
                    concepto = partes[1]
                    detalle = partes[2]
                    
                    nuevo_gasto = Gasto(
                        fecha=datetime.now(),
                        monto=monto,
                        descripcion=concepto + " - " + detalle,
                        usuario_id=usuario.id
                    )
                    db.session.add(nuevo_gasto)
                    agregados += 1
                db.session.commit()
                enviar_menu_principal(message.chat.id, f"✅ ¡Listo! Se registraron {agregados} gastos individuales.")
            else:
                concepto_principal = lineas[0]
                monto_total = 0.0
                nuevo_gasto = Gasto(
                    fecha=datetime.now(),
                    monto=0.0,
                    descripcion=concepto_principal,
                    usuario_id=usuario.id
                )
                db.session.add(nuevo_gasto)
                db.session.flush()
                
                for linea in lineas[1:]:
                    partes = [p.strip() for p in linea.split('-')]
                    if len(partes) < 2:
                        raise ValueError(f"Formato incompleto en ítem: '{linea}'. Debe ser 'Artículo - Precio'.")
                    
                    articulo = partes[0]
                    precio = float(partes[1].replace('$', '').replace(',', '').strip())
                    monto_total += precio
                    
                    detalle_obj = DetalleGasto(
                        gasto_id=nuevo_gasto.id,
                        descripcion=articulo,
                        cantidad=1.0,
                        precio_unitario=precio
                    )
                    db.session.add(detalle_obj)
                    
                nuevo_gasto.monto = monto_total
                db.session.commit()
                enviar_menu_principal(message.chat.id, f"✅ ¡Listo! Gasto agrupado '{concepto_principal}' registrado por un total de ${monto_total:.2f} con {len(lineas)-1} artículos.")
    except ValueError as ve:
        msg = bot.send_message(message.chat.id, f"⚠️ Error: {ve}\n\nVuelve a enviarme los datos con el formato correspondiente.")
        bot.register_next_step_handler(msg, procesar_estado_finanzas)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error al procesar: {e}")
        enviar_menu_principal(message.chat.id)

@with_app_context
def procesar_estado_inventario(message):
    if not message.text or re.search(r"(?i)Cancelar", message.text):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        enviar_menu_principal(message.chat.id, "❌ Operación cancelada.")
        return
    try:
        with get_app().app_context():
            linea = message.text.strip()
            partes = [p.strip() for p in linea.split('-')]
            if len(partes) < 3:
                raise ValueError("Faltan datos en la instrucción.")
            
            accion = partes[0].lower()
            if accion not in ["alta", "baja", "modificar"]:
                raise ValueError(f"Acción '{accion}' no permitida.")
                
            nombre_prod = partes[1]
            cantidad = int(partes[2])
            
            producto = Producto.query.filter(Producto.nombre.ilike(f"%{nombre_prod}%")).first()
            if not producto:
                if accion == "alta":
                    producto = Producto(nombre=nombre_prod, stock_actual=cantidad, stock_minimo=1)
                    db.session.add(producto)
                    db.session.commit()
                    enviar_menu_principal(message.chat.id, f"✅ Producto '{nombre_prod}' creado con stock {cantidad}.")
                    return
                else:
                    raise ValueError(f"No existe el producto '{nombre_prod}' para hacer {accion}.")
            
            if accion == "alta":
                producto.stock_actual += cantidad
            elif accion == "baja":
                producto.stock_actual -= cantidad
                if producto.stock_actual < 0: producto.stock_actual = 0
            elif accion == "modificar":
                producto.stock_actual = cantidad
                
            db.session.commit()
            enviar_menu_principal(message.chat.id, f"✅ Inventario actualizado. Stock de '{producto.nombre}' es ahora {producto.stock_actual}.")
    except ValueError as ve:
        msg = bot.send_message(message.chat.id, f"⚠️ Error: {ve}\n\nVuelve a enviarme los datos con el formato:\n\nAcción - Producto - Cantidad")
        bot.register_next_step_handler(msg, procesar_estado_inventario)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error interno: {e}")
        enviar_menu_principal(message.chat.id)

@with_app_context
def procesar_estado_tareas(message):
    if not message.text or re.search(r"(?i)Cancelar", message.text):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        enviar_menu_principal(message.chat.id, "❌ Operación cancelada.")
        return
    try:
        with get_app().app_context():
            partes = [p.strip() for p in message.text.split('-')]
            if len(partes) < 4:
                raise ValueError("Debes proveer los 4 campos obligatorios.")
            
            nombre_tarea = partes[0]
            prioridad = partes[1].capitalize()
            if prioridad not in ["Alta", "Media", "Baja"]:
                raise ValueError("Prioridad inválida.")
                
            vencimiento_str = partes[2]
            try:
                # DD/MM
                dia, mes = map(int, vencimiento_str.split('/'))
                año_actual = datetime.now().year
                fecha_vencimiento = date(año_actual, mes, dia)
            except:
                raise ValueError("Fecha inválida. Debe ser DD/MM.")
                
            asignados_str = partes[3]
            
            usuarios_asignar = []
            if asignados_str.lower() == "todos":
                usuarios_asignar = Usuario.query.all()
            else:
                nombres = [n.strip() for n in asignados_str.split(',')]
                for n in nombres:
                    u = Usuario.query.filter(Usuario.username.ilike(f"%{n}%")).first()
                    if u: usuarios_asignar.append(u)
                    else: raise ValueError(f"No encontré al usuario '{n}'.")
            
            if not usuarios_asignar:
                raise ValueError("No se especificaron usuarios válidos para asignar.")
                
            nueva_tarea = Tarea(
                nombre=nombre_tarea,
                tipo_frecuencia='dias', valor_frecuencia='0', prioridad=prioridad,
                fecha_programada=fecha_vencimiento
            )
            nueva_tarea.usuarios.extend(usuarios_asignar)
            db.session.add(nueva_tarea)
            db.session.commit()
            
            asignados_nombres = ", ".join([u.username for u in usuarios_asignar])
            enviar_menu_principal(message.chat.id, f"✅ Tarea '{nombre_tarea}' creada para {asignados_nombres}. Vence el {fecha_vencimiento.strftime('%d/%m')}.")
    except ValueError as ve:
        msg = bot.send_message(message.chat.id, f"⚠️ Error: {ve}\n\nVuelve a intentarlo con el formato:\n\nTarea - Prioridad - Vencimiento (DD/MM) - Asignado_a")
        bot.register_next_step_handler(msg, procesar_estado_tareas)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error interno: {e}")
        enviar_menu_principal(message.chat.id)

@with_app_context
def procesar_estado_logistica(message):
    if not message.text or re.search(r"(?i)Cancelar", message.text):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        enviar_menu_principal(message.chat.id, "❌ Operación cancelada.")
        return
    try:
        with get_app().app_context():
            partes = [p.strip() for p in message.text.split('-')]
            if len(partes) < 4:
                raise ValueError("Debes proveer los 4 campos obligatorios.")
            
            titulo = partes[0]
            fecha_str = partes[1]
            hora_str = partes[2]
            
            try:
                dia, mes = map(int, fecha_str.split('/'))
                hora, minuto = map(int, hora_str.split(':'))
                año_actual = datetime.now().year
                fecha_inicio = datetime(año_actual, mes, dia, hora, minuto)
            except:
                raise ValueError("Fecha u hora inválida. Debe ser DD/MM y HH:MM.")
                
            asignados_str = partes[3]
            usuarios_asignar = []
            if asignados_str.lower() == "todos":
                usuarios_asignar = Usuario.query.all()
            else:
                nombres = [n.strip() for n in asignados_str.split(',')]
                for n in nombres:
                    u = Usuario.query.filter(Usuario.username.ilike(f"%{n}%")).first()
                    if u: usuarios_asignar.append(u)
                    else: raise ValueError(f"No encontré al usuario '{n}'.")
            
            if not usuarios_asignar:
                raise ValueError("No se especificaron usuarios válidos para asignar.")
                
            usuario_creador = Usuario.query.filter_by(telegram_chat_id=str(message.from_user.id)).first()
            nuevo_evento = EventoLogistico(
                titulo=titulo,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_inicio + timedelta(hours=1),
                creador_id=usuario_creador.id if usuario_creador else usuarios_asignar[0].id,
                asignado_id=usuarios_asignar[0].id if usuarios_asignar else None
            )
            db.session.add(nuevo_evento)
            db.session.commit() # commit first to get ID
            
            nuevo_evento.descripcion = f"Asignado a: {', '.join([u.username for u in usuarios_asignar])}"
            db.session.commit()
            
            enviar_menu_principal(message.chat.id, f"✅ Evento logístico '{titulo}' creado exitosamente para el {fecha_inicio.strftime('%d/%m a las %H:%M')}.")
    except ValueError as ve:
        msg = bot.send_message(message.chat.id, f"⚠️ Error: {ve}\n\nVuelve a intentarlo con el formato:\n\nTítulo - Fecha (DD/MM) - Hora (HH:MM) - Asignado_a")
        bot.register_next_step_handler(msg, procesar_estado_logistica)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error interno: {e}")
        enviar_menu_principal(message.chat.id)


