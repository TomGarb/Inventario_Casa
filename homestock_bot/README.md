# HomeStock 📦🎙️

HomeStock es un gestor de inventario doméstico inteligente diseñado para registrar, consultar y administrar los productos de tu hogar de manera sencilla. Su principal fortaleza radica en la integración con un Bot de Telegram que permite actualizar el inventario enviando comandos de voz impulsados por OpenAI Whisper.

## Características Principales
* **Control por Voz (Telegram)**: Envía audios a tu bot ("Compré 2 litros de leche", "Gasté 1 paquete de fideos") y el sistema lo transcribe, interpreta y actualiza tu stock.
* **Manejo de Intenciones NLP**: Detección de intenciones (Agregar, Comprar, Restar, Consumir) para operaciones precisas.
* **Botones Inline**: Confirmación o rechazo de acciones directamente en el chat, con capacidad de "Deshacer" (Undo) de forma segura y concurrente.
* **Dashboard Web**: Panel de administración web responsivo y amigable para gestionar Categorías, Ubicaciones, Productos y Usuarios.
* **Panel de Administrador**: Control de roles y permisos (`@admin_required`) para proteger rutas y la gestión de usuarios.
* **Alertas de Stock Bajo**: Tareas programadas (CRON) que revisan los productos por debajo del stock mínimo y avisan al administrador por Telegram.

## Tecnologías Utilizadas (Stack)
* **Backend**: Python 3, Flask, SQLAlchemy.
* **Base de Datos**: PostgreSQL.
* **Bot de Telegram**: `pyTelegramBotAPI` con webhooks simulados (Safe Polling).
* **Inteligencia Artificial (Voz a Texto)**: `openai-whisper`.
* **Programación de Tareas**: `APScheduler` con soporte de zona horaria (`pytz`).
* **Frontend**: HTML5, CSS3, JavaScript (Jinja2 Templates).
* **Servidor (WSGI)**: Preparado para `Gunicorn` / `Waitress`.

## Requisitos Previos
1. **PostgreSQL**: Asegúrate de tener un servidor de PostgreSQL corriendo.
2. **FFmpeg**: Requerido por Whisper para procesar archivos de audio. Instálalo en tu sistema operativo:
   * Windows: `winget install ffmpeg` o descárgalo de la web oficial y agrégalo al PATH.
   * Linux (Debian/Ubuntu): `sudo apt install ffmpeg`
   * macOS: `brew install ffmpeg`
3. **Python 3.10+**.

## Instrucciones de Instalación y Despliegue

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/homestock.git
cd homestock
```

### 2. Configurar el Entorno Virtual
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

### 3. Instalar las dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar las Variables de Entorno
Copia el archivo `.env.example` y renómbralo a `.env`:
```bash
cp .env.example .env
```
Abre el archivo `.env` y configura tus claves reales:
* `TELEGRAM_TOKEN`: El token proporcionado por BotFather.
* `DATABASE_URL`: Tu cadena de conexión a PostgreSQL (Ej: `postgresql://usuario:password@localhost:5432/homestock`).
* `SECRET_KEY`: Una cadena segura para encriptar las sesiones de Flask.

### 5. Iniciar la Aplicación (Modo Desarrollo)
```bash
python app.py
```
*La base de datos se inicializará automáticamente gracias a SQLAlchemy si las tablas no existen.*

### 6. Despliegue en Producción (WSGI)
El proyecto está optimizado con un sistema de _Lock_ (`bot_scheduler.lock`) para evitar la colisión de hilos de Telegram cuando se ejecuta bajo servidores WSGI que levantan múltiples trabajadores.
Puedes iniciar el proyecto con Waitress en Windows:
```bash
waitress-serve --port=5000 app:app
```
O con Gunicorn en Linux:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Uso Básico
1. Regístrate en la interfaz web (el primer usuario requerirá que un administrador lo apruebe, o bien se le puede dar permisos manualmente por BD si es el pionero).
2. Ve a **Mi Perfil** y genera un **Token de Vinculación**.
3. Abre Telegram y envíale al Bot el comando `/vincular [TU_TOKEN]`.
4. ¡Listo! Ya puedes enviarle audios al Bot diciendo cosas como:
   * "Agrega 2 paquetes de arroz a la despensa."
   * "Saqué 1 lata de atún."
   * "Compré 3 litros de leche en el supermercado."

## Seguridad
* Todos los tokens y contraseñas de bases de datos han sido retirados del código base (utilizando `os.getenv`).
* El acceso a las rutas críticas está protegido por un sistema de roles y login. No comitees nunca tu archivo `.env`.

---
*Desarrollado con ❤️ para organizar el hogar.*
