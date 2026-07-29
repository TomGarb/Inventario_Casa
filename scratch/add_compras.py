import re

filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    source = f.read()

# 1. Inject /compras command
cmd_compras = """    # 1. COMANDOS
    @bot.message_handler(commands=['compras'])
    def cmd_compras(message):
        if not is_authorized(message.from_user.id): return
        enviar_listas_agrupadas(message.chat.id)
"""
source = source.replace('    # 1. COMANDOS\n', cmd_compras)

# 2. Inject callback
cb_compras = """    # 2. CALLBACKS
    @bot.callback_query_handler(func=lambda call: call.data == 'ver_compras')
    def callback_ver_compras(call):
        bot.answer_callback_query(call.id)
        if not is_authorized(call.from_user.id): return
        enviar_listas_agrupadas(call.message.chat.id)
"""
source = source.replace('    # 2. CALLBACKS\n', cb_compras)

# 3. Update procesar_menu_config
old_menu = '''def procesar_menu_config(message):
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
    safe_telegram_send(message.chat.id, "📅 Configuración de Menús.\\nSelecciona el día que deseas planificar:", reply_markup=markup)'''

new_menu = '''def procesar_menu_config(message):
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
    safe_telegram_send(message.chat.id, "📅 Configuración de Menús.\\nSelecciona el día que deseas planificar:", reply_markup=markup)'''

source = source.replace(old_menu, new_menu)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(source)

print("Compras command and callback injected successfully.")
