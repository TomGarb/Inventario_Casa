import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
imports_replacement = """import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash"""
content = re.sub(
    r"import os\nimport threading\nimport telebot\nfrom telebot.types import InlineKeyboardMarkup, InlineKeyboardButton\nfrom flask import Flask.*",
    lambda m: imports_replacement,
    content,
    flags=re.MULTILINE
)

# 2. Globals
globals_replacement = """# Inicializar Bot
bot = telebot.TeleBot(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
CHAT_ID = TELEGRAM_CHAT_ID
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', TELEGRAM_CHAT_ID)

pending_voice_commands = {}
recent_transactions = {}"""
content = re.sub(
    r"# Inicializar Bot\nbot = telebot\.TeleBot\(TELEGRAM_TOKEN\) if TELEGRAM_TOKEN else None\nCHAT_ID = TELEGRAM_CHAT_ID\n\npending_voice_commands = \{\}",
    lambda m: globals_replacement,
    content
)

# 3. Voice handler refactor (Undo & Restar)
voice_handler_pattern = r"    @bot\.callback_query_handler\(func=lambda call: call\.data in \['confirm_voice', 'cancel_voice'\]\).*?(?=    @bot\.message_handler\(commands=\['start'\]\))"

voice_handler_replacement = r"""    @bot.callback_query_handler(func=lambda call: call.data in ['confirm_voice', 'cancel_voice'])
    def callback_voice(call):
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        
        if call.data == 'cancel_voice':
            pending_voice_commands.pop(call.message.chat.id, None)
            bot.send_message(call.message.chat.id, "❌ Operación cancelada.")
            return
            
        texto_transcrito = pending_voice_commands.pop(call.message.chat.id, None)
        if not texto_transcrito:
            bot.send_message(call.message.chat.id, "⚠️ La solicitud ha expirado o ya fue procesada.")
            return
            
        texto_lower = texto_transcrito.lower()
        
        num_map = {
            'un': 1, 'una': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
            'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
            'diez': 10, 'once': 11, 'doce': 12, 'media': 0.5, 'medio': 0.5,
            'quince': 15, 'veinte': 20, 'treinta': 30
        }
        
        # 1. Detección de Intención Global y Limpieza
        rama = None
        texto_sin_accion = texto_lower
        
        match_inv = re.match(r'^\s*(agregar|añadir|compré|compre|comprado|sumar|meté|mete)\s+(.*)', texto_lower)
        match_comp = re.match(r'^\s*(comprar|falta|faltan|necesito|necesitamos)\s+(.*)', texto_lower)
        match_resta = re.match(r'^\s*(gasté|gaste|consumí|consumi|usé|use|comí|comi|saqué|saque|quité|quite)\s+(.*)', texto_lower)
        
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
            bot.send_message(call.message.chat.id, "❌ No pude entender la orden. Intenta decir: 'Agregar 2 de leche...' o 'Gasté 1 pan'.")
            return
            
        # 2. Separación de Artículos
        texto_limpio = texto_sin_accion.replace(" y ", ",").replace(" e ", ",")
        articulos_raw = [a.strip() for a in texto_limpio.split(",") if a.strip()]
        
        if not articulos_raw:
            bot.send_message(call.message.chat.id, "❌ No logré detectar qué artículos quieres procesar.")
            return

        respuestas = []
        tx_id = str(uuid.uuid4())
        recent_transactions[tx_id] = []

        try:
            with app.app_context():
                # 3. Procesamiento en Bucle
                for item_texto in articulos_raw:
                    # Extraer cantidad (opcional) y nombre
                    match_item = re.match(r'^(?:(\d+(?:\.\d+)?|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|media|medio|quince|veinte|treinta)\s+)?(?:de\s+)?([a-záéíóúñ\s]+)$', item_texto)
                    
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
                    
                    # Ubicación
                    partes = re.split(r'\s+en\s+', resto_texto, maxsplit=1)
                    producto_texto = partes[0].strip()
                    nombre_ubicacion = partes[1].strip() if len(partes) > 1 else None
                    
                    # Limpieza de plurales simples
                    if producto_texto.endswith('s') and len(producto_texto) > 3:
                        producto_texto_limpio = producto_texto[:-1]
                    else:
                        producto_texto_limpio = producto_texto
                        
                    ubicacion_obj = None
                    if nombre_ubicacion:
                        ubicaciones_db = Ubicacion.query.all()
                        nombres = [u.nombre for u in ubicaciones_db]
                        coincidencias = difflib.get_close_matches(nombre_ubicacion, nombres, n=1, cutoff=0.65)
                        if coincidencias:
                            ubicacion_obj = next(u for u in ubicaciones_db if u.nombre == coincidencias[0])
                        else:
                            ubicacion_obj = Ubicacion(nombre=nombre_ubicacion.capitalize(), sala_id=None)
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
                
                # 4. Respuesta Agrupada
                if respuestas:
                    markup_undo = InlineKeyboardMarkup()
                    markup_undo.add(InlineKeyboardButton("↩️ Deshacer", callback_data=f"undo_{tx_id}"))
                    
                    if rama == "inventario":
                        bot.send_message(call.message.chat.id, "✅ Procesado:\n- " + "\n- ".join(respuestas), reply_markup=markup_undo)
                    elif rama == "compras":
                        bot.send_message(call.message.chat.id, "🛒 Añadido a compras:\n- " + "\n- ".join(respuestas), reply_markup=markup_undo)
                    elif rama == "restar":
                        bot.send_message(call.message.chat.id, "➖ Descontado del inventario:\n- " + "\n- ".join(respuestas), reply_markup=markup_undo)
                else:
                    bot.send_message(call.message.chat.id, "⚠️ No se procesó ningún artículo.")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error interno: {str(e)}")

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
                        # Fue creado temporalmente, lo borramos todo
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
            bot.send_message(call.message.chat.id, f"❌ Error al deshacer: {str(e)}")

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
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

"""
content = re.sub(voice_handler_pattern, lambda m: voice_handler_replacement, content, flags=re.DOTALL)

# 4. APScheduler check_low_stock (before iniciar_bot)
scheduler_pattern = r"# ==========================================\n# HILO DE TELEGRAM Y EJECUCIÓN\n# =========================================="
scheduler_replacement = """# ==========================================
# ALERTA DE STOCK Y PROGRAMADOR
# ==========================================
def check_low_stock():
    with app.app_context():
        productos_bajos = Producto.query.filter(Producto.stock_actual <= Producto.stock_minimo, Producto.en_lista == False).all()
        if productos_bajos and ADMIN_CHAT_ID:
            nombres = [p.nombre for p in productos_bajos]
            mensaje = f"⚠️ Atención: Te estás quedando sin: {', '.join(nombres)}. ¿Los agrego a la lista de compras?"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🛒 Agregar todos a la lista", callback_data="add_low_stock"))
            
            try:
                bot.send_message(ADMIN_CHAT_ID, mensaje, reply_markup=markup)
            except Exception as e:
                print(f"Error enviando alerta de stock: {e}")

# ==========================================
# HILO DE TELEGRAM Y EJECUCIÓN
# =========================================="""
content = content.replace(scheduler_pattern, scheduler_replacement)
content = content.replace("# ==========================================\n# HILO DE TELEGRAM Y EJECUCI\"N\n# ==========================================", scheduler_replacement.replace("EJECUCIÓN", "EJECUCI\"N"))


# 5. Start Scheduler (inside if __main__)
main_pattern = r"    if os\.environ\.get\(\"WERKZEUG_RUN_MAIN\"\) == \"true\":\n        threading\.Thread\(target=iniciar_bot, daemon=True\)\.start\(\)"
main_replacement = """    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Thread(target=iniciar_bot, daemon=True).start()
        
        # Iniciar Programador APScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=check_low_stock, trigger="cron", hour=10, minute=0)
        scheduler.start()"""
content = re.sub(main_pattern, lambda m: main_replacement, content)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied.")
