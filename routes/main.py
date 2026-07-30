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
    mes_actual = hoy.month
    ano_actual = hoy.year
    
    # 1. Mis Tareas Pendientes (del usuario, hoy o vencidas, o TODAS si es admin)
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
                # Es mi turno o soy admin?
                prox_user_id = calcular_proximo_turno(t)
                
                if prox_user_id == current_user.id or es_admin:
                    prox_user = db.session.get(Usuario, prox_user_id) if prox_user_id else None
                    nombre_asignado = prox_user.username if prox_user else "Todos/Nadie"
                    
                    if prox_user_id == current_user.id:
                        nombre_mostrar = t.nombre
                    else:
                        nombre_mostrar = f"{t.nombre} ({nombre_asignado})"
                        
                    mis_tareas.append({'nombre': nombre_mostrar, 'vencida': (hoy - proxima).days > 0})
                    
    # 2. Ranking del Hogar (completadas en mes actual)
    usuarios = Usuario.query.all()
    ranking = []
    for u in usuarios:
        completadas = HistorialTarea.query.filter(
            HistorialTarea.usuario_id == u.id,
            extract('month', HistorialTarea.fecha) == mes_actual,
            extract('year', HistorialTarea.fecha) == ano_actual
        ).count()
        ranking.append({'username': u.username, 'completadas': completadas})
    ranking.sort(key=lambda x: x['completadas'], reverse=True)
    
    # 3. Radar de Tareas Críticas (vencidas > 2 días)
    criticas = []
    for t in tareas:
        current_date = t.fecha_ultima_ejecucion or (hoy - timedelta(days=3))
        proxima = calcular_proxima_fecha(t, current_date)
        if t.tipo_frecuencia == 'fecha_fija':
            try: proxima = datetime.strptime(t.valor_frecuencia, '%Y-%m-%d').date()
            except: proxima = hoy
        dias_vencida = (hoy - proxima).days
        if dias_vencida > 2:
            criticas.append({'nombre': t.nombre, 'dias_vencida': dias_vencida})
            
    # 4. Medidor de Excusas (Skips en mes actual)
    skips_por_usuario = {}
    for u in usuarios:
        skips = SaltoTarea.query.filter(
            SaltoTarea.usuario_id == u.id,
            extract('month', SaltoTarea.fecha) == mes_actual,
            extract('year', SaltoTarea.fecha) == ano_actual
        ).count()
        skips_por_usuario[u.username] = skips
        
    # 5. Última Actividad (ultimos 5 registros: historiales o saltos)
    actividad = []
    historiales = HistorialTarea.query.order_by(HistorialTarea.fecha.desc()).limit(5).all()
    saltos = SaltoTarea.query.order_by(SaltoTarea.fecha.desc()).limit(5).all()
    
    for h in historiales:
        u = db.session.get(Usuario, h.usuario_id)
        t = db.session.get(Tarea, h.tarea_id)
        actividad.append({'tipo': 'completada', 'fecha': h.fecha, 'texto': f"{u.username} completó: {t.nombre}"})
        
    for s in saltos:
        u = db.session.get(Usuario, s.usuario_id)
        t = db.session.get(Tarea, s.tarea_id)
        actividad.append({'tipo': 'skip', 'fecha': s.fecha, 'texto': f"{u.username} saltó: {t.nombre}"})
        
    actividad.sort(key=lambda x: x['fecha'], reverse=True)
    actividad = actividad[:5]
    
    # 6. Finanzas
    gastos_mes = db.session.query(db.func.sum(Gasto.monto)).filter(
        extract('month', Gasto.fecha) == mes_actual,
        extract('year', Gasto.fecha) == ano_actual
    ).scalar() or 0.0
    balances = calcular_balances_globales()

    # 7. Logística (Próximo evento y agenda hoy/mañana)
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora = datetime.now(tz)
    fin_manana = (ahora + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    
    eventos_agenda = EventoLogistico.query.filter(
        EventoLogistico.fecha_inicio >= ahora,
        EventoLogistico.fecha_inicio <= fin_manana
    ).order_by(EventoLogistico.fecha_inicio.asc()).limit(3).all()
    
    proximo_evento = EventoLogistico.query.filter(
        EventoLogistico.fecha_inicio >= ahora
    ).order_by(EventoLogistico.fecha_inicio.asc()).first()

    return render_template('views/dashboard.html', 
        active_page='dashboard',
        mis_tareas=mis_tareas,
        ranking=ranking,
        criticas=criticas,
        skips_por_usuario=skips_por_usuario,
        actividad=actividad,
        gastos_mes=gastos_mes,
        balances=balances,
        eventos_agenda=eventos_agenda,
        proximo_evento=proximo_evento,
        usuarios=usuarios
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


