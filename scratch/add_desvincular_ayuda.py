import re

filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    source = f.read()

# 1. Inject handlers
nuevos_handlers = """    # 1. COMANDOS
    @bot.message_handler(commands=['desvincular'])
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
"""
source = source.replace('    # 1. COMANDOS\n', nuevos_handlers)

# 2. Inject bot.set_my_commands
old_iniciar = '''def iniciar_bot():
    if bot:
        logging.info("[Bot Telemetría] Iniciando bot de Telegram en segundo plano...")
        try:
            print("🟢 INICIANDO POLLING DE TELEGRAM...")
            bot.remove_webhook()'''

new_iniciar = '''def iniciar_bot():
    if bot:
        logging.info("[Bot Telemetría] Iniciando bot de Telegram en segundo plano...")
        try:
            from telebot.types import BotCommand
            comandos = [
                BotCommand("start", "Inicia el bot y verifica el estado"),
                BotCommand("vincular", "Conecta tu cuenta de HomeStock"),
                BotCommand("desvincular", "Desconecta este chat de tu cuenta"),
                BotCommand("menu", "Abre el menú interactivo"),
                BotCommand("compras", "Muestra la lista de compras pendiente"),
                BotCommand("ayuda", "Muestra los comandos disponibles")
            ]
            bot.set_my_commands(comandos)
        except Exception as ec:
            print(f"Error configurando comandos en Telegram: {ec}")
            
        try:
            print("🟢 INICIANDO POLLING DE TELEGRAM...")
            bot.remove_webhook()'''

source = source.replace(old_iniciar, new_iniciar)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(source)

print("Handlers desvincular and ayuda, and bot.set_my_commands injected successfully.")
