import re

filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    source = f.read()

old_vincular = '''    @bot.message_handler(commands=['vincular'])
    def cmd_vincular(message):
        import logging
        try:
            partes = message.text.split(maxsplit=1)
            
            if len(partes) < 2:
                safe_telegram_send(message.chat.id, "⚠️ Formato incorrecto. Debes usar: /vincular TU_CODIGO")
                return
                
            codigo_ingresado = partes[1].strip()
            print(f"🔗 Intento de vinculación - Chat ID: {message.chat.id} - Código: {codigo_ingresado}")
            
            with app.app_context():
                user = Usuario.query.filter_by(telegram_link_token=codigo_ingresado).first()
                if user:
                    # Prevención de Unique Constraint: 
                    # Si este dispositivo (chat_id) ya estaba vinculado a OTRO usuario, lo desvinculamos primero.
                    old_user = Usuario.query.filter_by(telegram_chat_id=str(message.chat.id)).first()
                    if old_user and old_user.id != user.id:
                        old_user.telegram_chat_id = None
                        print(f"⚠️ Se desvinculó automáticamente la cuenta '{old_user.username}' del dispositivo {message.chat.id} por conflicto de unicidad.")

                    user.telegram_chat_id = str(message.chat.id)
                    user.telegram_link_token = None
                    db.session.commit()
                    logging.info(f"[Vincular] Cuenta '{user.username}' vinculada a Telegram ID {message.chat.id}")
                    safe_telegram_send(message.chat.id, f"✅ ¡Cuenta vinculada con éxito! Hola, {user.username}. Ya estás autorizado/a para usar el bot y recibirás notificaciones.")
                else:
                    logging.warning(f"[Vincular] Intento fallido con token '{codigo_ingresado}' desde Telegram ID {message.chat.id}")
                    safe_telegram_send(message.chat.id, "❌ Token inválido o expirado. Genera uno nuevo en la web y vuelve a intentar.")
        except Exception as e:
            print(f"🔴 ERROR EN COMANDO VINCULAR: {e}")
            logging.error(f"[Vincular] Error al vincular cuenta en BD: {e}", exc_info=True)
            safe_telegram_send(message.chat.id, "❌ Ocurrió un error interno al intentar vincular. Revisa la consola.")'''

new_vincular = '''    @bot.message_handler(commands=['vincular'])
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
            safe_telegram_send(message.chat.id, "❌ Ocurrió un error general.")'''

source = source.replace(old_vincular, new_vincular)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(source)

print("Vincular refactor applied")
