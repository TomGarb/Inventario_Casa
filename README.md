# HomeStock 🏠📊

HomeStock es un ERP doméstico y gestor inteligente diseñado para registrar, consultar y administrar todas las áreas de tu hogar de manera sencilla. Integra arquitectura Multi-Tenant, un Bot de Telegram con Inteligencia Artificial (Gemini), un calendario logístico, módulo de finanzas compartidas y dashboards centralizados.

## ✨ Nuevas Funcionalidades (Última Versión)

### 🏘️ Arquitectura Multi-Tenant (Casas Aisladas)
* **Aislamiento Seguro (RLS por ORM):** El sistema permite gestionar múltiples "Casas". Todo el inventario, tareas, finanzas y agendas están estrictamente aislados por la casa activa.
* **Onboarding Dinámico:** Al registrarse, un usuario debe **Crear** una casa nueva (convirtiéndose en Administrador) o **Unirse** a una existente mediante un *Código de Invitación* y contraseña.
* **Gestión de Casas:** Los administradores pueden cambiar el nombre de su casa, expulsar usuarios, o eliminar la casa por completo (borrado en cascada seguro).
* **Visibilidad Transversal:** Puedes cambiar fácilmente de entorno activo desde el menú. El Dashboard y la Navbar siempre te indicarán en qué casa estás operando.

### 🐾 Ecosistema de Mascotas (Pet Care)
* **Hub Transversal:** Un módulo dedicado (`/mascotas`) que actúa como agregador de la salud animal.
* **Integración Total:** Vincula automáticamente el inventario (Alimentos, Pipetas, Accesorios), las rutinas diarias (Paseos, Comidas rotativas) y la agenda logística (Turnos de Veterinario y Vacunas) en un solo panel de control.
* **Vistas Dinámicas:** Cálculo automático de edades y consumo rápido de alimento (-1 ración).

### 🚀 Interfaz Renovada (Launchpad)
* **Dashboard "Launchpad":** El viejo carrusel ha sido reemplazado por un grid Launchpad Neomórfico que te permite saltar a las secciones más críticas de la casa (Inventario, Finanzas, Mascotas, Tareas).
* **Navegación Agrupada:** Barra de navegación superior condensada bajo dropdowns inteligentes (Operaciones, Planificación, Gestión) operados por puro CSS.

## 🛠️ Características Clásicas

* **Inteligencia Artificial Multimodal (Gemini):** Detección de intenciones desde Telegram y lectura de tickets de supermercado mediante OCR para carga automática de gastos.
* **Módulo de Finanzas (Tipo Splitwise):** Carga de gastos compartidos y división automática de deudas entre los habitantes de la casa. Metas de ahorro.
* **Gestor de Menú y Recetas:** Creación de recetas, armado de menús semanales automáticos y deducción cruzada de ingredientes faltantes en el inventario.
* **Logística y Entretenimiento:** Sincronización automática de eventos, citas y calendarios de partidos deportivos (F1, NBA, Fútbol) vía TheSportsDB.
* **Sistema Avanzado de Tareas:** Tareas recurrentes, saltos de turno (`SaltoTarea`), asignaciones por usuario.
* **Integración Telegram Bidireccional:** Añade productos, reporta consumos o recibe recordatorios de tareas matutinos.

## 📖 Guía Rápida de Uso

### Primeros Pasos (Multi-Casa)
1. Ve a `/register`. Podrás elegir entre crear una casa nueva o unirte a una existente.
2. Si **Creas** una casa: Ve a **Mi Perfil > Gestión de la Casa**, copia el **Código de Invitación** y compártelo con tus familiares/roomies para que se unan.
3. Puedes cambiar de casa en la barra de navegación superior si administras varias.

### Gestión de Usuarios y Permisos
* En tu Perfil, si eres Administrador de la casa activa, verás la tabla **Gestión de Usuarios**.
* Desde ahí puedes otorgar/quitar rol de Administrador a un miembro (restringido solo a la casa actual) o **Eliminarlo**, lo que expulsará a esa persona de tu casa sin borrar su cuenta de HomeStock.
* También puedes **Editar o Eliminar la Casa** entera desde el menú principal de Casas. Al eliminarla, se hará un borrado estricto de todos los inventarios y deudas.

### Uso del Inventario y Mascotas
* Entra al menú **📦 Operaciones**.
* En **Inventario**, puedes crear productos, indicarles ubicaciones y stock mínimo.
* En **Mascotas**, si creaste productos con la palabra "Alimento", "Perro" o "Gato", aparecerán vinculados automáticamente para que controles su stock. Desde ahí puedes registrar su próximo turno veterinario.

### Uso del Telegram Bot
1. Ve a **Mi Perfil** y genera un **Token de Vinculación**.
2. Escribe a tu Bot en Telegram: `/vincular [TU_TOKEN]`.
3. Ya puedes hablarle con naturalidad: *"Compré 3 litros de leche en Coto por 2500"*, *"Recuérdame pagar la luz mañana"*, o enviarle la foto de un ticket.

## 💻 Stack Tecnológico
* **Backend:** Python 3.12+, Flask, SQLAlchemy, Flask-Migrate.
* **Base de Datos:** PostgreSQL (Soporte Nativo Multi-Tenant vía SQLAlchemy Loader Criteria).
* **IA:** `google-genai` (Gemini 2.0 Flash).
* **Frontend:** HTML5, CSS3 (Neomorfismo Avanzado), Vanilla JS.

---
*Desarrollado para centralizar el control del hogar.*
