import os
import json
import logging
from google import genai
from datetime import datetime
from models.database import Usuario, Gasto, DetalleGasto
from extensions import db

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def check_api_quota_error(e, chat_id=None):
    try:
        from google.api_core.exceptions import ResourceExhausted, GoogleAPICallError
    except ImportError:
        ResourceExhausted = type('ResourceExhausted', (Exception,), {})
        
    try:
        from google.genai.errors import APIError, ClientError
    except ImportError:
        APIError = type('APIError', (Exception,), {})
        ClientError = type('ClientError', (Exception,), {})
        
    err_str = str(e).lower()
    
    is_quota_error = (
        isinstance(e, (ResourceExhausted,)) or 
        (isinstance(e, (APIError, ClientError)) and getattr(e, 'code', 0) == 429) or
        '429' in err_str or 
        'resourceexhausted' in err_str or 
        'quota' in err_str or 
        'exhausted' in err_str or 
        'too many requests' in err_str
    )
    
    if is_quota_error:
        if chat_id:
            try:
                from services.bot_telegram import safe_telegram_send
                safe_telegram_send(chat_id, "⏳ La inteligencia artificial está procesando demasiadas cosas. Por favor, espera 1 minuto y vuelve a enviarme el mensaje.")
            except Exception as send_err:
                print(f"Error al enviar aviso de cuota: {send_err}")
        return True
    return False

def extraer_datos_evento(texto, chat_id=None):
    if not GEMINI_API_KEY:
        return None
    try:
        import pytz
        client = genai.Client(api_key=GEMINI_API_KEY)
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        fecha_actual = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        
        prompt = f"Eres un asistente de calendario. Hoy es {fecha_actual} (Hora de Buenos Aires). Analiza este mensaje: '{texto}' y extrae los detalles del evento. Devuelve EXCLUSIVAMENTE un JSON con las claves: 'titulo' (resumen corto), 'fecha_inicio' (formato ISO 8601), 'fecha_fin' (formato ISO 8601, si aplica), y 'descripcion'. No uses markdown."
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(response_mime_type="application/json")
        )
        resultado_str = response.text.strip()
        if resultado_str.startswith('```json'):
            resultado_str = resultado_str.replace('```json', '').replace('```', '').strip()
        elif resultado_str.startswith('```'):
            resultado_str = resultado_str.replace('```', '').strip()
            
        return json.loads(resultado_str)
    except Exception as e:
        if check_api_quota_error(e, chat_id):
            return "ERROR_CUOTA"
        logging.error(f"Error al procesar el evento con la IA: {e}", exc_info=True)
        return None

def clasificar_intencion(texto, chat_id=None):
    import json
    import logging
    texto_lower = texto.lower()

    # 1. Diccionarios de Palabras Clave (Paso Local - determinista y rápido)
    keywords_map = {
        "FINANZAS": ['gasto', 'gasté', 'pagué', 'compré', 'precio', '$', 'pesos', 'tarjeta', 'mercadopago'],
        "COMPRAS": ['falta', 'anotar', 'comprar', 'lista', 'supermercado', 'súper', 'quedamos sin'],
        "LOGISTICA": ['turno', 'agendar', 'recordatorio', 'cita', 'médico', 'mecánico', 'plomero', 'electricista', 'envío', 'entrega', 'paquete', 'visita', 'servicios'],
        "TAREAS": ['limpiar', 'arreglar', 'revisar', 'ordenar', 'quehaceres'],
        "MENU": ['menú', 'comida', 'cenar', 'almorzar', 'almuerzo', 'cena', 'desayuno', 'desayunar', 'merienda', 'merendar']
    }

    for categoria, kw_list in keywords_map.items():
        for kw in kw_list:
            if kw in texto_lower:
                logging.info(f"[Enrutador] Vía: KEYWORD -> {categoria} (kw: '{kw}')")
                return categoria

    # 2. Fallback con IA (Gemini - JSON Estricto)
    if not GEMINI_API_KEY:
        logging.warning("[Enrutador] API Key de Gemini no disponible. Fallback -> INVENTARIO")
        return "INVENTARIO"

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = (
            "Clasifica este mensaje en una de estas categorías: FINANZAS, COMPRAS, INVENTARIO, TAREAS, LOGISTICA, MENU, RECETA.\n"
            "Reglas de clasificación:\n"
            "- LOGISTICA: citas, visitas de servicios (ej. plomero, electricista), envíos, entregas de paquetes y turnos.\n"
            "- TAREAS: solo acciones o quehaceres internos que deben realizar los miembros de la casa (ej. limpiar, ordenar, arreglar algo internamente).\n"
            "- MENU: consultas o configuración sobre comidas, desayuno, almuerzo, merienda, cena, menú semanal.\n"
            "- RECETA: Usa 'RECETA' para CUALQUIER pregunta sobre qué cocinar, sugerencias de comida, o cómo preparar platos, incluso si el usuario menciona palabras como 'casa' o 'ingredientes'.\n"
            "- INVENTARIO: SOLO para ingresar compras, gastar unidades o contar stock físico.\n"
            "- FINANZAS: gastos, pagos, precios, compras con monto o dinero.\n"
            f"Devuelve ÚNICAMENTE un JSON con este formato: {{'intencion': 'CATEGORIA'}}. Mensaje: {texto}"
        )
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text.strip())
        intencion = data.get("intencion", "INVENTARIO").upper()

        if intencion in ["FINANZAS", "COMPRAS", "INVENTARIO", "TAREAS", "LOGISTICA", "MENU", "RECETA"]:
            logging.info(f"[Enrutador] Vía: GEMINI -> {intencion}")
            return intencion
        else:
            logging.warning(f"[Enrutador] Vía: GEMINI -> Categoría desconocida '{intencion}', usando fallback -> INVENTARIO")
            return "INVENTARIO"
    except Exception as e:
        if check_api_quota_error(e, chat_id):
            return "ERROR_CUOTA"
        logging.error(f"[Enrutador] Error de clasificación con Gemini: {e}", exc_info=True)
        return "INVENTARIO"

def procesar_gasto_texto(texto, message):
    import re
    import json
    import logging
    if re.search(r'\d+', texto):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = (
                f"Analiza este texto de gasto: '{texto}'. "
                "Extrae el monto numérico (como float), el comercio/concepto, la categoría del gasto (ej. 'Supermercado', 'Alimentos', 'Servicios', 'Otros') "
                "y, SI detectas que se compraron productos físicos o alimentos (ej. arroz, leche, pan, jabón, detergente), extrae una lista de esos ítems con su nombre en singular y la cantidad numérica "
                "(o 1 si no se especifica). "
                "Devuelve ÚNICAMENTE un JSON con el formato exacto: {'monto': float, 'concepto': 'string', 'categoria': 'string', 'items': [{'nombre': 'string', 'cantidad': float}]}."
            )
            response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(response_mime_type="application/json")
        )
            data = json.loads(response.text.strip())
            monto = float(data.get('monto', 0))
            concepto = str(data.get('concepto', 'Gasto en general')).strip()
            items = data.get('items', [])

            if monto > 0:
                with app.app_context():
                    user = Usuario.query.filter_by(telegram_chat_id=str(message.from_user.id)).first()
                    if not user:
                        safe_telegram_send(message.chat.id, "⚠️ No estás registrado o vinculado para guardar gastos.")
                        return

                pending_ocr_confirmations[message.chat.id] = {
                    'usuario_id': user.id,
                    'monto_total': monto,
                    'descripcion': concepto,
                    'items': items
                }

                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    InlineKeyboardButton("✅ Confirmar Gasto", callback_data="ocr_div_todos"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="ocr_div_no")
                )
                safe_telegram_send(
                    message.chat.id,
                    f"💳 **Resumen de Gasto**\n\n📌 **Concepto:** {concepto}\n💰 **Monto:** ${monto}\n\n¿Deseas registrar este gasto?",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            if check_api_quota_error(e, message.chat.id):
                return
            logging.error(f"[Módulo Finanzas] Error extrayendo gasto con Gemini: {e}", exc_info=True)

    safe_telegram_send(message.chat.id, f"💳 [Módulo Finanzas] Has indicado un gasto: '{texto}'. Por favor, adjunta la foto del ticket o regístralo manualmente en la web mientras conectamos el guardado por texto.")