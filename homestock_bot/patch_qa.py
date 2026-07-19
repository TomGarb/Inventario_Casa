import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update handle_voice (add datetime import, update pending_voice_commands, add finally block)
# Make sure datetime is imported. It's already there in the file.
handle_voice_pattern = r"        texto_transcrito = resultado\[\"text\"\]\.strip\(\)\n\s+pending_voice_commands\[message\.chat\.id\] = texto_transcrito\n\s+markup = InlineKeyboardMarkup\(\)"
handle_voice_replacement = r"""        texto_transcrito = resultado["text"].strip()
            
            pending_voice_commands[message.chat.id] = (texto_transcrito, datetime.now())
            
            markup = InlineKeyboardMarkup()"""
content = re.sub(handle_voice_pattern, lambda m: handle_voice_replacement, content)

# Add finally block to handle_voice
finally_pattern = r"        except Exception as e:\n            bot\.reply_to\(message, f\"❌ Error procesando el audio: \{str\(e\)\}\"\)"
finally_replacement = r"""        except Exception as e:
            bot.reply_to(message, f"❌ Error procesando el audio: {str(e)}")
        finally:
            if ogg_path and os.path.exists(ogg_path):
                try:
                    os.remove(ogg_path)
                except Exception:
                    pass"""
content = re.sub(finally_pattern, lambda m: finally_replacement, content)

# 2. Update callback_voice (tuple unpack, rollback, regex changes)
voice_handler_pattern = r"    @bot\.callback_query_handler\(func=lambda call: call\.data in \['confirm_voice', 'cancel_voice'\]\).*?(?=    @bot\.callback_query_handler\(func=lambda call: call\.data\.startswith\('undo_'\)\))"

voice_handler_replacement = r"""    @bot.callback_query_handler(func=lambda call: call.data in ['confirm_voice', 'cancel_voice'])
    def callback_voice(call):
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        
        if call.data == 'cancel_voice':
            pending_voice_commands.pop(call.message.chat.id, None)
            bot.send_message(call.message.chat.id, "❌ Operación cancelada.")
            return
            
        pending_data = pending_voice_commands.pop(call.message.chat.id, None)
        if not pending_data:
            bot.send_message(call.message.chat.id, "⚠️ La solicitud ha expirado o ya fue procesada.")
            return
            
        texto_transcrito = pending_data[0] if isinstance(pending_data, tuple) else pending_data
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
                try:
                    # 3. Procesamiento en Bucle
                    for item_texto in articulos_raw:
                        # Extraer cantidad (opcional) y nombre
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
                            # Limpieza de artículos y ruido en nombre_ubicacion
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
                    db.session.rollback()
                    bot.send_message(call.message.chat.id, f"❌ Error guardando datos, transacción revertida: {str(e)}")
                    recent_transactions.pop(tx_id, None)
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error interno: {str(e)}")

"""
content = re.sub(voice_handler_pattern, lambda m: voice_handler_replacement, content, flags=re.DOTALL)

# 3. APScheduler cleanup_pending_commands
cleanup_pattern = r"def check_low_stock\(\):"
cleanup_replacement = r"""def cleanup_pending_commands():
    ahora = datetime.now()
    vencidos = [chat_id for chat_id, data in pending_voice_commands.items() 
                if isinstance(data, tuple) and (ahora - data[1]) > timedelta(hours=1)]
    for chat_id in vencidos:
        pending_voice_commands.pop(chat_id, None)

def check_low_stock():"""
content = re.sub(cleanup_pattern, lambda m: cleanup_replacement, content)

scheduler_pattern = r"        scheduler\.add_job\(func=check_low_stock, trigger=\"cron\", hour=10, minute=0\)"
scheduler_replacement = r"""        scheduler.add_job(func=check_low_stock, trigger="cron", hour=10, minute=0)
        scheduler.add_job(func=cleanup_pending_commands, trigger="interval", hours=1)"""
content = re.sub(scheduler_pattern, lambda m: scheduler_replacement, content)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied.")
