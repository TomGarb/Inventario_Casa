import os
import telebot
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN')

print(f"Probando conexion con Telegram (Token: {token[:5]}...)")
try:
    bot = telebot.TeleBot(token)
    me = bot.get_me()
    print(f"✅ Conexion exitosa. El bot se llama: {me.first_name} (@{me.username})")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"❌ Error de conexion: {e}")
