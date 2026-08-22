# HomeStock 📦🎙️

HomeStock es un ERP doméstico y gestor inteligente diseñado para registrar, consultar y administrar todas las áreas de tu hogar de manera sencilla. Integra un Bot de Telegram con Inteligencia Artificial (Gemini 2.0 Flash) para interpretar texto y leer tickets de compra, un calendario logístico, módulo de finanzas compartidas y dashboards multi-dispositivo.

## Características Principales
* **Inteligencia Artificial Multimodal (Gemini)**: Procesamiento de texto natural para detectar intenciones y lectura de tickets de supermercado mediante OCR para carga automática de gastos. *(Nota: El soporte de audio se encuentra deshabilitado para optimizar cuota de IA).*
* **Manejo de Intenciones NLP**: Detección inteligente de intenciones (Inventario, Finanzas, Logística, Tareas) directo desde Telegram.
* **Módulo de Finanzas (Tipo Splitwise)**: Carga de gastos, subida de tickets por foto, y división automática de deudas entre los habitantes del hogar.
* **Logística y Entretenimiento (TheSportsDB)**: Calendario compartido del hogar. Permite sincronizar y agregar automáticamente los próximos partidos de tus equipos y ligas favoritas (F1, NBA, Fútbol).
* **Métricas y Gamificación**: Sistema de "Metas de Ahorro" con barras de progreso visuales y estadísticas de gastos mensuales.
* **Gestor de Menú y Recetas**: Creación de recetas (Desayuno, Almuerzo, Cena), armado de menús semanales automáticos y su cruce con el inventario para deducir qué ingredientes faltan.
* **Dashboards Multi-Dispositivo (TV y Tablet)**: Vistas animadas dedicadas (`/tv-dashboard`, `/tablet`) que auto-scrollean y se refrescan solas para tenerlas siempre en pantalla.
* **Interfaz Neomórfica (UI/UX)**: Diseño completamente renovado basado en Neomorfismo, con sombras suaves, componentes redondeados y modo responsivo absoluto.
* **Sistema Avanzado de Tareas**: Tareas recurrentes, saltos de turno (`SaltoTarea`), asignaciones por usuario e historial de completado.

## Tecnologías Utilizadas (Stack)
* **Backend**: Python 3.12+, Flask, SQLAlchemy, Flask-Migrate.
* **Base de Datos**: PostgreSQL.
* **Bot de Telegram**: `pyTelegramBotAPI` con webhooks simulados (Safe Polling).
* **Inteligencia Artificial**: `google-genai` (Gemini 2.0 Flash).
* **Programación de Tareas**: `APScheduler` (Cron jobs para stock bajo y sincronización).
* **Frontend**: HTML5, CSS3 (Neomorfismo), Vanilla JavaScript (Jinja2 Templates).
* **Servidor (WSGI)**: Preparado para `Gunicorn` / `Waitress`.

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
Abre el archivo `.env` y configura tus claves:
* `TELEGRAM_TOKEN`: El token de tu bot de Telegram.
* `DATABASE_URL`: Tu cadena de conexión a PostgreSQL (Ej: `postgresql://usuario:password@localhost:5432/homestock`).
* `SECRET_KEY`: Llave de encriptación para las sesiones de Flask.
* `GEMINI_API_KEY`: Tu API Key de Google AI Studio.

### 5. Iniciar la Aplicación (Modo Desarrollo)
Ejecuta las migraciones y lanza el servidor:
```bash
flask db upgrade
python app.py
```
*El sistema inyectará automáticamente los datos semilla (Suscripciones base, configuraciones) al arrancar.*

### 6. Despliegue en Producción
El proyecto está optimizado con un sistema de _Lock_ (`bot_scheduler.lock`) para evitar la colisión de hilos de Telegram y Scheduler.
En Render o Linux (Gunicorn):
```bash
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

## Uso Básico del Telegram Bot
1. Regístrate en la interfaz web y ve a **Mi Perfil** para generar un **Token de Vinculación**.
2. Abre Telegram y envíale al Bot el comando `/vincular [TU_TOKEN]`.
3. Ya puedes enviarle comandos de texto natural:
   * "Compré 3 litros de leche en Coto por 2500"
   * "Agrega el partido de hoy al calendario"
   * También puedes enviarle **fotos de tickets de compra** y Gemini extraerá los gastos automáticamente.

## Seguridad
* Todos los endpoints de la API web están protegidos por CSRF tokens dinámicos en el frontend.
* Las rutas de administración están protegidas con el decorador `@admin_required`.
* Las credenciales nunca se exponen en código (gestión por `.env`).

---
*Desarrollado con ❤️ para centralizar el control del hogar.*
