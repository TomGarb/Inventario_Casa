#!/bin/bash

echo -e "\e[36m=========================================\e[0m"
echo -e "\e[36m   Iniciando configuracion de HomeStock  \e[0m"
echo -e "\e[36m=========================================\e[0m"

# 1. Configurar variables de entorno
if [ ! -f .env ]; then
    echo -e "\e[33m\n¡Hola! Veo que es la primera vez que configuras el sistema.\e[0m"
    echo -e "\e[33mVamos a crear tu archivo secreto '.env' paso a paso.\e[0m"
    
    # Generar clave secreta automaticamente
    SECRET_KEY=$(head -c 32 /dev/urandom | base64)
    
    echo -e "\e[35m\n--- PASO 1: INTELIGENCIA ARTIFICIAL (Opcional) ---\e[0m"
    echo -e "\e[90mSi dejas esto en blanco, la plataforma web funcionara al 100%, pero la IA no leera tus tickets.\e[0m"
    echo "1. Ingresa a: https://aistudio.google.com/app/apikey"
    read -p "-> Pega tu GEMINI_API_KEY aqui (o presiona ENTER para omitir): " GEMINI_KEY
    
    echo -e "\e[35m\n--- PASO 2: BOT DE TELEGRAM (Opcional) ---\e[0m"
    echo -e "\e[90mSi dejas esto en blanco, el bot de Telegram estara apagado temporalmente.\e[0m"
    echo "1. Habla con '@BotFather' en Telegram y usa el comando /newbot"
    read -p "-> Pega tu TELEGRAM_TOKEN aqui (o presiona ENTER para omitir): " TELEGRAM_KEY
    
    cat <<EOF > .env
# Configuracion de Base de Datos (Docker Local)
DATABASE_URL=postgresql://homestock_user:homestock_pass@db:5432/homestock_db

# Seguridad de Flask (Generado automaticamente)
SECRET_KEY=$SECRET_KEY

# APIs Externas
GEMINI_API_KEY=$GEMINI_KEY
TELEGRAM_TOKEN=$TELEGRAM_KEY
OPENWEATHER_API_KEY=
OPENWEATHER_CITY=Buenos Aires, AR
EOF
    echo -e "\e[32m\nArchivo .env generado con exito.\e[0m"
    
    if [ -z "$GEMINI_KEY" ] || [ -z "$TELEGRAM_KEY" ]; then
        echo -e "\e[33mAviso: Omitiste algunas claves. Para agregarlas luego, solo edita el archivo '.env' y ejecuta 'docker-compose restart'.\e[0m"
    fi
else
    echo -e "\e[32mEl archivo .env ya existe. Saltando generacion.\e[0m"
fi

# 2. Descargar y levantar Docker
echo -e "\e[36m\nLevantando los contenedores de Docker...\e[0m"
docker-compose pull
docker-compose up -d

echo -e "\e[33m\nEsperando 5 segundos para que la Base de Datos inicie...\e[0m"
sleep 5

# 3. Crear las tablas vacías en la nueva base de datos
echo -e "\e[36m\nCreando la estructura de tablas vacias (esquema inicial)...\e[0m"
docker-compose exec web flask db upgrade

echo -e "\e[32m\n=========================================\e[0m"
echo -e "\e[32m  ¡HomeStock esta listo y corriendo!     \e[0m"
echo -e "\e[32m  Accede desde: http://localhost:5000    \e[0m"
echo -e "\e[32m=========================================\e[0m"
