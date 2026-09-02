Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Iniciando configuracion de HomeStock  " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Configurar variables de entorno
if (-not (Test-Path ".env")) {
    Write-Host "`n¡Hola! Veo que es la primera vez que configuras el sistema." -ForegroundColor Yellow
    Write-Host "Vamos a crear tu archivo secreto '.env' paso a paso." -ForegroundColor Yellow
    
    # Generar una clave secreta segura automaticamente
    $bytes = New-Object Byte[] 32
    [Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($bytes)
    $secretKey = [Convert]::ToBase64String($bytes)
    
    Write-Host "`n--- PASO 1: INTELIGENCIA ARTIFICIAL (Opcional) ---" -ForegroundColor Magenta
    Write-Host "Si dejas esto en blanco, la plataforma web funcionara al 100%, pero la IA no podra leer tus tickets." -ForegroundColor Gray
    Write-Host "1. Ingresa a: https://aistudio.google.com/app/apikey"
    $gemini = Read-Host "-> Pega tu GEMINI_API_KEY aqui (o presiona ENTER para omitir)"
    
    Write-Host "`n--- PASO 2: BOT DE TELEGRAM (Opcional) ---" -ForegroundColor Magenta
    Write-Host "Si dejas esto en blanco, el bot de Telegram estara apagado temporalmente." -ForegroundColor Gray
    Write-Host "1. Habla con '@BotFather' en Telegram y usa el comando /newbot"
    $telegram = Read-Host "-> Pega tu TELEGRAM_TOKEN aqui (o presiona ENTER para omitir)"
    
    $envContent = @"
# Configuracion de Base de Datos (Docker Local)
DATABASE_URL=postgresql://homestock_user:homestock_pass@db:5432/homestock_db

# Seguridad de Flask (Generado automaticamente)
SECRET_KEY=$secretKey

# APIs Externas
GEMINI_API_KEY=$gemini
TELEGRAM_TOKEN=$telegram
OPENWEATHER_API_KEY=
OPENWEATHER_CITY=Buenos Aires, AR
"@
    Set-Content -Path ".env" -Value $envContent
    Write-Host "`nArchivo .env generado con exito." -ForegroundColor Green
    if ($gemini -eq "" -or $telegram -eq "") {
        Write-Host "Aviso: Omitiste algunas claves. Para agregarlas luego, solo edita el archivo '.env' y ejecuta 'docker-compose restart'." -ForegroundColor Yellow
    }
} else {
    Write-Host "El archivo .env ya existe. Saltando generacion." -ForegroundColor Green
}

# 2. Descargar y levantar Docker
Write-Host "`nLevantando los contenedores de Docker (esto puede tardar la primera vez)..." -ForegroundColor Cyan
docker-compose pull
docker-compose up -d

Write-Host "`nEsperando 5 segundos para que la Base de Datos inicie correctamente..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 3. Crear las tablas vacías en la nueva base de datos
Write-Host "`nCreando la estructura de tablas vacias (esquema inicial)..." -ForegroundColor Cyan
docker-compose exec web flask db upgrade

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "  ¡HomeStock esta listo y corriendo!     " -ForegroundColor Green
Write-Host "  Accede desde: http://localhost:5000    " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
