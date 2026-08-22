from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging
import pytz
from utils import calcular_balances_globales, calcular_proxima_fecha, calcular_proximo_turno

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    hoy = datetime.now().date()
    
    # 1. Mis Tareas Pendientes
    mis_tareas = []
    tareas = Tarea.query.all()
    es_admin = getattr(current_user, 'is_admin', False)
    
    for t in tareas:
        if current_user in t.usuarios or es_admin:
            current_date = t.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
            proxima = calcular_proxima_fecha(t, current_date)
            if t.tipo_frecuencia == 'fecha_fija':
                try: proxima = datetime.strptime(t.valor_frecuencia, '%Y-%m-%d').date()
                except: proxima = hoy
            if proxima <= hoy:
                prox_user_id = calcular_proximo_turno(t)
                if prox_user_id == current_user.id or es_admin:
                    mis_tareas.append({'tarea': t, 'vencida': proxima < hoy})
                    
    total_tareas_hoy = len(mis_tareas)
    
    # 2. Logistica proximas 24hs
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora = datetime.now(tz)
    fin_manana = (ahora + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    eventos_agenda = EventoLogistico.query.filter(
        EventoLogistico.fecha_inicio >= ahora,
        EventoLogistico.fecha_inicio <= fin_manana
    ).order_by(EventoLogistico.fecha_inicio.asc()).all()
    
    # 3. Alertas de Stock
    alertas_stock = Producto.query.filter(Producto.es_temporal == False, Producto.stock_actual <= Producto.stock_minimo).all()
    total_faltantes = len(alertas_stock)
    
    # 4. Deuda Compartida
    balances = calcular_balances_globales()
    lo_que_debo = sum(b['monto'] for b in balances if b['deudor_id'] == current_user.id)
    lo_que_me_deben = sum(b['monto'] for b in balances if b['acreedor_id'] == current_user.id)
    mi_balance = lo_que_me_deben - lo_que_debo
    deuda_compartida = abs(mi_balance) if mi_balance < 0 else 0
    
    # 5. Ultimos movimientos
    movimientos = Movimiento.query.order_by(Movimiento.fecha.desc()).limit(5).all()

    return render_template('views/dashboard.html', 
        active_page='dashboard',
        mis_tareas=mis_tareas,
        total_tareas_hoy=total_tareas_hoy,
        total_faltantes=total_faltantes,
        deuda_compartida=deuda_compartida,
        eventos_agenda=eventos_agenda,
        alertas_stock=alertas_stock,
        movimientos=movimientos,
        mi_balance=mi_balance
    )

@main_bp.route('/api/dashboard_stats', methods=['GET'])
def dashboard_stats():
    alertas_stock = Producto.query.filter(Producto.es_temporal == False, Producto.stock_actual <= Producto.stock_minimo).all()
    
    compras = Producto.query.filter(Producto.en_lista == True).all()
    compras_agrupadas = {}
    for p in compras:
        nombre_comercio = p.rel_comercio.nombre if p.rel_comercio else "Sin Comercio"
        compras_agrupadas[nombre_comercio] = compras_agrupadas.get(nombre_comercio, 0) + 1
        
    hoy = datetime.now().date()
    limite_vencimiento = hoy + timedelta(days=7)
    por_vencer = Producto.query.filter(Producto.fecha_vencimiento != None, Producto.fecha_vencimiento <= limite_vencimiento).all()
    
    limite_inactivo = hoy - timedelta(days=30)
    inactivos = Producto.query.filter(Producto.fecha_ultima_compra != None, Producto.fecha_ultima_compra <= limite_inactivo).all()
    
    return jsonify({
        'alertas_stock': [p.to_dict() for p in alertas_stock],
        'compras_por_comercio': [{'comercio': k, 'cantidad': v} for k, v in compras_agrupadas.items()],
        'por_vencer': [p.to_dict() for p in por_vencer],
        'inactivos': [p.to_dict() for p in inactivos]
    })


@main_bp.route('/api/dashboard/movimientos', methods=['GET'])
def get_movimientos():
    q = request.args.get('q', '').strip()
    query = Movimiento.query
    if q:
        query = query.filter(Movimiento.descripcion.ilike(f'%{q}%'))
        limit = 50
    else:
        limit = 10
        
    movs = query.order_by(Movimiento.fecha.desc()).limit(limit).all()
    return jsonify([{'id': m.id, 'descripcion': m.descripcion, 'fecha': m.fecha.strftime("%Y-%m-%d %H:%M")} for m in movs])

import os

@main_bp.route('/tv/<pin>', methods=['GET'])
def tv_dashboard_alias(pin):
    return redirect(url_for('main.tv_dashboard', token=pin))

@main_bp.route('/tv-dashboard', methods=['GET'])
def tv_dashboard():
    # Simple token protection (e.g. ?token=micasa123)
    # The token can be set in .env as TV_DASHBOARD_TOKEN, default 'micasa123'
    expected_token = os.environ.get('TV_DASHBOARD_TOKEN', 'micasa123')
    token = request.args.get('token')
    
    if token != expected_token:
        return f'''
        <div style="background:#1e1e2f; color:white; font-family:sans-serif; height:100vh; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center;">
            <h1 style="color:#f43f5e; font-size: 3rem;">Acceso Denegado</h1>
            <p style="font-size: 1.5rem;">Para acceder a la TV sin iniciar sesión, debes ingresar el PIN secreto en la URL.</p>
            <p style="font-size: 1.5rem;">Usando el control remoto, entra a esta dirección exacta:</p>
            <div style="background:#2dd4bf; color:black; padding:20px; font-size:2rem; font-weight:bold; border-radius:15px; margin: 20px;">
                tusitio.com/tv/{expected_token}
            </div>
        </div>
        ''', 403
        
    weather_api_key = os.environ.get('OPENWEATHER_API_KEY', '')
    weather_city = os.environ.get('OPENWEATHER_CITY', 'Buenos Aires, AR')
    
    return render_template('views/tv_dashboard.html', 
                           weather_api_key=weather_api_key, 
                           weather_city=weather_city,
                           token=token)

@main_bp.route('/api/tv_data', methods=['GET'])
def get_tv_data():
    expected_token = os.environ.get('TV_DASHBOARD_TOKEN', 'micasa123')
    token = request.args.get('token')
    
    if token != expected_token:
        return jsonify({'error': 'Acceso Denegado'}), 403
        
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(tz).date()
    
    # 1. Alertas de Stock
    alertas_stock = Producto.query.filter(Producto.es_temporal == False, Producto.stock_actual <= Producto.stock_minimo).all()
    stock_data = [{'nombre': p.nombre, 'stock_actual': p.stock_actual, 'stock_minimo': p.stock_minimo} for p in alertas_stock]
    
    # 2. Menús del Día
    menus_hoy = MenuSemanal.query.filter(MenuSemanal.fecha_asignada == hoy).all()
    menu_data = [{'tipo': m.tipo_comida, 'receta': m.receta.nombre} for m in menus_hoy]
    
    # 3. Logística (Próximos 3 eventos desde hoy)
    ahora = datetime.now(tz)
    fin_manana = (ahora + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    eventos = EventoLogistico.query.filter(
        EventoLogistico.fecha_inicio >= ahora,
        EventoLogistico.fecha_inicio <= fin_manana
    ).order_by(EventoLogistico.fecha_inicio.asc()).limit(3).all()
    logistica_data = [{'titulo': e.titulo, 'hora': e.fecha_inicio.strftime('%H:%M')} for e in eventos]
    
    # 4. Tareas (Vencidas y Hoy)
    tareas_data = []
    tareas = Tarea.query.all()
    for t in tareas:
        current_date = t.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
        proxima = calcular_proxima_fecha(t, current_date)
        if t.tipo_frecuencia == 'fecha_fija':
            try: proxima = datetime.strptime(t.valor_frecuencia, '%Y-%m-%d').date()
            except: proxima = hoy
            
        if proxima <= hoy:
            prox_user_id = calcular_proximo_turno(t)
            prox_user = db.session.get(Usuario, prox_user_id) if prox_user_id else None
            nombre_asignado = prox_user.username if prox_user else "Todos"
            
            tareas_data.append({
                'nombre': t.nombre,
                'asignado': nombre_asignado,
                'vencida': (hoy - proxima).days > 0,
                'prioridad': t.prioridad
            })
            
    # Sort tareas: Vencidas and Urgentes first
    tareas_data.sort(key=lambda x: (not x['vencida'], x['prioridad'] != 'Urgente'))
    
    return jsonify({
        'stock': stock_data,
        'menus': menu_data,
        'logistica': logistica_data,
        'tareas': tareas_data[:6]
    })


@main_bp.route('/tablet-dashboard', methods=['GET'])
@login_required
def tablet_dashboard():
    return render_template('views/tablet_dashboard.html')


@main_bp.route('/api/tablet_data', methods=['GET'])
@login_required
def get_tablet_data():
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(tz).date()
    
    # 1. Tareas de hoy (pendientes)
    tareas_data = []
    tareas = Tarea.query.filter_by(completada=False).all()
    for t in tareas:
        current_date = t.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
        proxima = calcular_proxima_fecha(t, current_date)
        if t.tipo_frecuencia == 'fecha_fija':
            try: proxima = datetime.strptime(t.valor_frecuencia, '%Y-%m-%d').date()
            except: proxima = hoy
            
        if proxima <= hoy:
            tareas_data.append({
                'id': t.id,
                'nombre': t.nombre,
                'prioridad': t.prioridad,
                'vencida': (hoy - proxima).days > 0
            })
            
    tareas_data.sort(key=lambda x: (not x['vencida'], x['prioridad'] != 'Urgente'))
    
    # 2. Productos Comunes (para marcarlos rápido como faltantes)
    # Mostramos los que NO están en la lista y no son temporales
    productos = Producto.query.filter_by(es_temporal=False, en_lista=False).order_by(Producto.nombre).all()
    inventario_data = [{'id': p.id, 'nombre': p.nombre, 'stock': p.stock_actual} for p in productos]
    
    # 3. Menú de Hoy
    menus_hoy = MenuSemanal.query.filter(MenuSemanal.fecha_asignada == hoy).all()
    menu_data = [{'tipo': m.tipo_comida, 'receta': m.receta.nombre} for m in menus_hoy]
    
    # 4. Usuarios Reales (no tablet) para asignar acciones
    usuarios = Usuario.query.filter_by(is_tablet=False).all()
    usuarios_data = [{'id': u.id, 'username': u.username} for u in usuarios]
    
    return jsonify({
        'tareas': tareas_data,
        'inventario': inventario_data,
        'menus': menu_data,
        'usuarios': usuarios_data
    })




@main_bp.route('/metricas', methods=['GET'])
@login_required
def metricas():
    return render_template('views/metricas.html', active_page='metricas')

@main_bp.route('/api/metricas_data', methods=['GET'])
@login_required
def get_metricas_data():
    hoy = datetime.now().date()
    # Gasto mes actual
    mes_actual = hoy.month
    ano_actual = hoy.year
    gastos_mes = db.session.query(db.func.sum(Gasto.monto)).filter(extract('month', Gasto.fecha) == mes_actual, extract('year', Gasto.fecha) == ano_actual).scalar() or 0
    
    # Total productos falta
    total_productos_falta = Producto.query.filter(Producto.es_temporal == False, Producto.stock_actual <= Producto.stock_minimo).count()
    
    # Dias para proximo evento
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora = datetime.now(tz)
    proximo_evento = EventoLogistico.query.filter(EventoLogistico.fecha_inicio >= ahora).order_by(EventoLogistico.fecha_inicio.asc()).first()
    if proximo_evento:
        dias_evento = (proximo_evento.fecha_inicio.date() - hoy).days
    else:
        dias_evento = "-"
        
    # Grafico gastos (ultimos 7 dias)
    labels = []
    datos_gastos = []
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        g = db.session.query(db.func.sum(Gasto.monto)).filter(db.func.date(Gasto.fecha) == dia).scalar() or 0
        labels.append(dia.strftime('%d/%m'))
        datos_gastos.append(float(g))
        
    # Excepciones (deudas y tareas vencidas)
    tareas_vencidas = []
    tareas = Tarea.query.all()
    for t in tareas:
        current_date = t.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
        proxima = calcular_proxima_fecha(t, current_date)
        if t.tipo_frecuencia == 'fecha_fija':
            try: proxima = datetime.strptime(t.valor_frecuencia, '%Y-%m-%d').date()
            except: proxima = hoy
        if proxima < hoy:
            tareas_vencidas.append({'nombre': t.nombre, 'dias_retraso': (hoy - proxima).days})
            
    # Deudas
    balances = calcular_balances_globales()
    deudas = []
    for b in balances:
        deudas.append({
            'usuario': f"{b['deudor_nombre']} a {b['acreedor_nombre']}",
            'monto': b['monto']
        })
            
    return jsonify({
        'kpis': {
            'gasto_mes_actual': float(gastos_mes),
            'total_productos_falta': total_productos_falta,
            'dias_para_proximo_evento': dias_evento
        },
        'chart': {
            'labels': labels,
            'data': datos_gastos
        },
        'excepciones': {
            'tareas_vencidas': tareas_vencidas,
            'deudas': deudas
        }
    })
