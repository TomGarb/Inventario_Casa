# ROADMAP de HomeStock

Este documento traza las epics principales para el desarrollo y expansión de los módulos futuros del ecosistema HomeStock.

## 1. Módulo de Finanzas Compartidas
Centraliza y distribuye los gastos de la casa de forma equitativa y transparente.

- **Procesamiento OCR de Facturas**: Integración con tecnologías de extracción de texto para leer recibos y tickets de compra subidos como imágenes, parseando el monto y el concepto automáticamente.
- **Comando `/balance`**: Integración con el bot de Telegram para consultar rápidamente quién le debe a quién.
- **Exportación a Google Sheets**: Sincronización estructurada de los datos en formato crudo y en columnas (ID, fecha, usuario, monto, descripción, categoría, fracción de deuda). Este diseño permitirá a los integrantes usar fórmulas de cálculo avanzadas sin que la aplicación restrinja la libertad financiera del hogar.

## 2. Calendario Logístico
Permitirá organizar la convivencia más allá de las tareas de limpieza, gestionando las visitas y eventos importantes.

- **Procesamiento de Voz para Agendar**: Utilizando el motor de Whisper (ya existente), permitirá la creación de eventos logísticos (ej: "Mañana viene mi familia a cenar a las 20hs") de manera conversacional mediante audios en Telegram.
- **Resumen Matutino (Daily Digest)**: Un job programado enviará al grupo (`enviar_al_grupo`) un resumen matutino con la agenda del día (visitantes, mantenimientos del hogar, etc.).

## 3. Planificador de Menús
Ayudará a responder la incógnita diaria de "¿Qué comemos hoy?" conectando las recetas con el inventario real.

- **Generación basada en Inventario (Smart Meal Prep)**: Algoritmo que sugiere menús semanales evaluando los ingredientes disponibles y aplicando un descuento automático de stock al confirmarse la preparación.
- **Sugerencias Rápidas**: Opciones de *fall-back* que no validan stock de forma estricta, pensadas para comidas dinámicas.
- **Planificador Semanal Manual**: Interfaz tipo grilla para organizar 4 comidas diarias (Desayuno, Almuerzo, Merienda, Cena) manualmente por cada día de la semana.
