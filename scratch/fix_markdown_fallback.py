import re

filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    source = f.read()

# Replace safe_telegram_send
old_send = '''def safe_telegram_send(chat_id, mensaje, reply_markup=None, parse_mode='HTML'):
    if not bot:
        return False
    try:
        bot.send_message(chat_id, mensaje, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        print(f"Error enviando mensaje a {chat_id}: {e}")
        return False'''

new_send = '''def safe_telegram_send(chat_id, mensaje, reply_markup=None, parse_mode='HTML'):
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
        return False'''

source = source.replace(old_send, new_send)

# Replace safe_telegram_reply
old_reply = '''def safe_telegram_reply(message, texto, reply_markup=None, parse_mode=None):
    if not bot:
        return False
    try:
        bot.reply_to(message, texto, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        print(f"Error respondiendo a {message.chat.id}: {e}")
        return False'''

new_reply = '''def safe_telegram_reply(message, texto, reply_markup=None, parse_mode=None):
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
        return False'''

source = source.replace(old_reply, new_reply)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(source)

print("Fallback Markdown functions successfully implemented.")
