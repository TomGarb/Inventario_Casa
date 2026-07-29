import re

filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    source = f.read()

old_vincular = '''    @bot.message_handler(commands=['vincular'])
    def cmd_vincular(message):
        import logging
        texto = message.text.replace('/vincular', '').strip()
        if not texto:
            safe_telegram_send(message.chat.id, "Por favor, envía tu token. Ejemplo: /vincular ABC123")
            return

        try:
            with app.app_context():
                user = Usuario.query.filter_by(telegram_link_token=texto).first()
                if user:
                    user.telegram_chat_id = str(message.from_user.id)
                    user.telegram_link_token = None
                    db.session.commit()
                    logging.info(f"[Vincular] Cuenta '{user.username}' vinculada a Telegram ID {message.from_user.id} (desde chat {message.chat.id})")
                    safe_telegram_send(message.chat.id, f"✅ ¡Cuenta vinculada con éxito! Hola, {user.username}. Ya estás autorizado/a para usar el bot y recibirás notificaciones.")
                else:
                    logging.warning(f"[Vincular] Intento fallido con token '{texto}' desde Telegram ID {message.from_user.id}")
                    safe_telegram_send(message.chat.id, "❌ Token inválido o expirado. Genera uno nuevo en la web y vuelve a intentar.")
        except Exception as e:
            logging.error(f"[Vincular] Error al vincular cuenta en BD: {e}", exc_info=True)
            safe_telegram_send(message.chat.id, "❌ Hubo un error interno al intentar vincular tu cuenta. Por favor, revisa los logs del servidor.")'''

new_vincular = '''    @bot.message_handler(commands=['vincular'])
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

source = source.replace(old_vincular, new_vincular)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(source)

print("Comando /vincular depurado implementado con éxito.")
