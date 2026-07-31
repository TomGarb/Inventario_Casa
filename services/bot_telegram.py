from functools import wraps
import os
import uuid
import json
import logging
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Tarea
from extensions import db, bot
from utils import is_authorized
from services.gemini_service import clasificar_intencion, procesar_gasto_texto, check_api_quota_error

_bot_app = None

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

def registrar_handlers(bot, app):
    global _bot_app
    _bot_app = app

    def with_app_context(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with app.app_context():
                return func(*args, **kwargs)
        return wrapper

    # 1. COMANDOS
    @bot.message_handler(commands=['desvincular'])
    @with_app_context
    def cmd_desvincular(message):
        try:
            with app.app_context():
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
            print(f"📩 COMANDO RECIBIDO: {message.text}")
            if not is_authorized(message.from_user.id): return
            procesar_menu_config(message)
        except Exception as e:
            print(f"🔴 ERROR INTERNO EN HANDLER DE MENU: {e}")
            bot.reply_to(message, "Hubo un error interno. Revisa la consola.")

    @bot.message_handler(commands=['start'])
    @with_app_context
    def cmd_start(message):
        safe_telegram_reply(message, "¡Hola! Bienvenido a Homestock. Para vincular tu cuenta, ingresa a la aplicación web, ve a tu Perfil, genera un token y envíalo aquí con el comando:\n/vincular <Tu Token>")

    @bot.message_handler(commands=['vincular'])
    @with_app_context
    def cmd_vincular(message):
        import logging
        from sqlalchemy.exc import IntegrityError
        try:
            partes = message.text.split(maxsplit=1)
            
            if len(partes) < 2:
                safe_telegram_send(message.chat.id, "⚠️ Formato incorrecto. Debes usar: /vincular TU_CODIGO")
                return
                
            codigo_ingresado = partes[1].strip()
            print(f"🔗 Intento de vinculación - Chat ID: {message.chat.id} - Código: {codigo_ingresado}")
            
            with app.app_context():
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

        with app.app_context():
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
        with app.app_context():
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
        with app.app_context():
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
            with app.app_context():
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
            with app.app_context():
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
        with app.app_context():
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
            
            with app.app_context():
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
            with app.app_context():
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
                        model='gemini-1.5-flash',
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

    @bot.message_handler(content_types=['text', 'voice'])
    @with_app_context
    def handle_voice_and_text(message):
        try:
            print(f"📩 MENSAJE RECIBIDO DE TELEGRAM: {message.text}")
            import logging
            logging.info(f"[Bot Telemetría] Mensaje entrante recibido en servidor. Chat ID: {message.chat.id}, Tipo: {message.content_type}")
            if not is_authorized(message.from_user.id):
                logging.warning(f"[Bot Telemetría] Chat ID {message.chat.id} no está autorizado. Ignorando mensaje.")
                return

            texto_transcrito = ''

            if message.content_type == 'voice':
                try:
                    safe_telegram_reply(message, "Procesando audio... 🎙️")
                    file_info = bot.get_file(message.voice.file_id)
                    downloaded_file = bot.download_file(file_info.file_path)

                    client = genai.Client(api_key=GEMINI_API_KEY)
                    part = genai.types.Part.from_bytes(data=downloaded_file, mime_type='audio/ogg')
                    
                    response = client.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=["Transcribe exactamente lo que dice este audio, sin agregar ningún otro comentario.", part]
                    )
                    texto_transcrito = response.text.strip()
                except Exception as e:
                    safe_telegram_send(message.chat.id, f"❌ Error interno: {str(e)}")
                    return
            else:
                if message.text.startswith('/'): return
                texto_transcrito = message.text.strip()

            if not texto_transcrito:
                return

            if message.chat.id in pending_menu_config:
                dia, tipo = pending_menu_config.pop(message.chat.id)
                guardar_menu_desde_bot(message.chat.id, dia, tipo, texto_transcrito)
                return

            # --- ENRUTADOR INTELIGENTE HÍBRIDO (PALABRAS CLAVE + GEMINI) ---
            intencion = clasificar_intencion(texto_transcrito, message.chat.id)
            if intencion == "ERROR_CUOTA":
                return
            import logging
            logging.info(f"[Enrutador Bot] Mensaje: '{texto_transcrito}' -> Intención final: {intencion}")

            if intencion in ["FINANZAS", "GASTO"]:
                procesar_gasto_texto(texto_transcrito, message)
            elif intencion == "COMPRAS":
                procesar_compras_texto(texto_transcrito, message)
            elif intencion in ["LOGISTICA", "EVENTO"]:
                procesar_evento_texto(texto_transcrito, message)
            elif intencion == "TAREAS":
                procesar_tareas_texto(texto_transcrito, message)
            elif intencion == "MENU":
                procesar_menu_config(message)
            elif intencion in ["RECETA", "RECETAS"]:
                procesar_recetas_texto(texto_transcrito, message)
            else:  # INVENTARIO (Fallback por defecto)
                procesar_inventario_texto(texto_transcrito, message)

        except Exception as e:
            print(f"🔴 ERROR INTERNO EN HANDLER DE TEXTO: {e}")
            bot.reply_to(message, "Hubo un error interno. Revisa la consola.")