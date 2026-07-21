# Backlog HomeOS - Pendientes y Mejoras (Proxima Sesion)

---

## 1. BUG CRITICO - Bot de Telegram (Fotos)

**Sintoma:** El bot ignora las fotos por completo, tanto en el grupo como en mensajes privados. No arroja ningun error en la consola (fallo silencioso).

**Prueba manual:**
- Enviar una foto al bot desde privado
- Enviar una foto al grupo de la casa
- Verificar si hay respuesta

**Solucion esperada:**
- Confirmar que el handler este registrado con content_types=['photo', 'document']
- El bot debe responder inmediatamente con 'Recibi el ticket. Analizando con IA, dame unos segundos...' antes de llamar a Gemini
- Si la API falla, el bot debe responder 'Fallo la lectura: [mensaje de error]' (nunca silencioso)

---

## 2. UI/UX - Pop-ups y Estados Vacios

**Sintoma:** Varios modales se abren automaticamente al cargar la pagina.

**Prueba manual:**
- Navegar a Dashboard -> verificar que no se abra ningun modal al cargar
- Navegar a Logistica -> verificar que no se abra el modal de 'Nuevo evento'
- Navegar a Finanzas -> verificar que no se abra el modal de 'Nuevo gasto'
- Navegar a Menus -> verificar que no se abra el modal de 'Configurar horarios'

**Solucion esperada:**
- Eliminar cualquier llamada a .show() o modal.style.display = 'block' en el DOMContentLoaded
- Toda apertura de modal debe ser exclusivamente por accion del usuario (clic en boton)

**Caso especial - Menus (Horarios):**
- Si no hay horarios cargados en la BD, mostrar un Empty State dentro de la pantalla:
  'No hay horarios configurados. Hace clic aqui para definirlos.'
- El boton del Empty State si abre el modal. El auto-pop-up NO debe existir.

---

## 3. UI/UX - Dashboard

**Prueba manual:**
- Verificar que la seccion 'Acciones Rapidas' ya no aparece en el Dashboard
- Verificar que el widget 'Skips de Tareas (Mes)' ya no aparece

**Ajuste de layout:**
- Reducir el widget 'Ultimos Movimientos' al 50% del ancho
- El otro 50% debe ser la tarjeta de 'Subir Ticket / Camara' (widget de Finanzas con el boton de camara)
- Ambas tarjetas deben estar en la misma fila horizontal

---

## 4. UI/UX - Calendario de Tareas

**Prueba manual:**
- Navegar a la pestana de Tareas
- Verificar si tiene el layout de dos columnas (50/50)

**Solucion esperada:**
- Replicar el mismo layout 50/50 implementado en Logistica:
  - Columna izquierda (50%): FullCalendar con las tareas del mes
  - Columna derecha (50%): Lista de tareas del dia seleccionado

---

## 5. UI/UX - Botones y Estilos Globales

**Prueba manual:**
- Recorrer todas las pestanas (Inventario, Compras, Tareas, Finanzas, Logistica, Menus)
- Verificar que todos los botones tienen clases CSS consistentes (btn, btn-primary, btn-secondary, btn-danger)

**Solucion esperada:**
- Auditar y unificar las clases CSS de todos los botones en las pestanas nuevas
- Ningun boton debe tener estilos inline que contradigan el sistema de diseno

---

## Notas para el agente en la proxima sesion

- El usuario realizara TODAS las pruebas manualmente antes de pasar a los arreglos. No crear scripts de testing automaticos.
- El archivo de estilos global es static/css/style.css. Variables en :root.
- El layout 50/50 de referencia esta en templates/views/logistica.html. Usarlo como plantilla exacta para replicar en Tareas y Dashboard.
