import logging
from app import app, bot

if __name__ == '__main__':
    logging.info("=========================================")
    logging.info("  Iniciando Microservicio: TELEGRAM BOT  ")
    logging.info("=========================================")
    
    if bot:
        with app.app_context():
            # Registrar comandos
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
                logging.info("[Bot] Comandos registrados exitosamente.")
            except Exception as e:
                logging.error(f"[Bot] Error registrando comandos: {e}")
            
            # Limpiar webhook (si existe de un despliegue anterior) y arrancar polling
            try:
                bot.remove_webhook()
                logging.info("[Bot] Webhook eliminado. Arrancando en modo Long-Polling aislado...")
                bot.infinity_polling(timeout=10, long_polling_timeout=5)
            except Exception as e:
                logging.error(f"[Bot] Error iniciando polling: {e}")
    else:
        logging.error("TELEGRAM_TOKEN no configurado. Bot apagado.")
