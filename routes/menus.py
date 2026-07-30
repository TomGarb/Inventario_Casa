from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging

menus_bp = Blueprint('menus', __name__)

@menus_bp.route('/api/generar_mes', methods=['POST'])
@login_required
def generar_mes():
    hoy = datetime.now().date()
    modelos = ModeloTarea.query.all()
    
    from dateutil.relativedelta import relativedelta
    fin_de_mes = hoy + relativedelta(day=31)
    
    nuevas_tareas = 0
    for m in modelos:
        # Compute dates up to fin_de_mes
        current_date = m.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
        
        usuarios_ids = [u.id for u in m.usuarios]
        if not usuarios_ids: continue
        
        # Determine starting index for turn rotation based on historial
        # For simplicity in generation, we can just randomly start or start at 0
        idx = 0 
        
        while True:
            proxima = calcular_proxima_fecha(m, current_date)
            if m.tipo_frecuencia == 'fecha_fija':
                try: proxima = datetime.strptime(m.valor_frecuencia, '%Y-%m-%d').date()
                except: proxima = hoy
                
            if proxima > fin_de_mes or proxima < hoy:
                break
                
            # Check if this task already exists for this date
            exists = Tarea.query.filter_by(modelo_id=m.id, fecha_programada=proxima).first()
            
            if not exists:
                nueva_tarea = Tarea(
                    nombre=m.nombre,
                    prioridad=m.prioridad,
                    tipo_frecuencia='fecha_fija',
                    valor_frecuencia=proxima.isoformat(),
                    fecha_programada=proxima,
                    fecha_ultima_ejecucion=proxima,
                    alternar=m.alternar,
                    modelo_id=m.id,
                    completada=False
                )
                
                # Assign users
                if m.alternar:
                    u = db.session.get(Usuario, usuarios_ids[idx])
                    if u: nueva_tarea.usuarios.append(u)
                    idx = (idx + 1) % len(usuarios_ids)
                else:
                    for uid in usuarios_ids:
                        u = db.session.get(Usuario, uid)
                        if u: nueva_tarea.usuarios.append(u)
                        
                db.session.add(nueva_tarea)
                nuevas_tareas += 1
                
            if m.tipo_frecuencia == 'fecha_fija':
                break
            
            current_date = proxima
            
    db.session.commit()
    return jsonify({'mensaje': f'Se generaron {nuevas_tareas} tareas para este mes.'})


@menus_bp.route('/api/menus/manual', methods=['POST'])
@login_required
def agregar_menu_manual():
    try:
        data = request.json
        dia_semana = data.get('dia_semana')
        tipo_comida = data.get('tipo_comida')
        nombre = data.get('nombre')
        
        if not dia_semana or not tipo_comida or not nombre:
            return jsonify({'error': 'Faltan datos (día, tipo, nombre).'}), 400
            
        # Buscar receta o crear nueva
        receta = Receta.query.filter(Receta.nombre.ilike(f"%{nombre}%")).first()
        if not receta:
            receta = Receta(nombre=nombre, tipo=tipo_comida, es_rapida=True)
            db.session.add(receta)
            db.session.flush()
            
        # Calcular la fecha del dia de la semana (semana actual)
        dias_es = {'Lunes':0, 'Martes':1, 'Miércoles':2, 'Jueves':3, 'Viernes':4, 'Sábado':5, 'Domingo':6}
        if dia_semana not in dias_es:
            return jsonify({'error': 'Día de la semana inválido.'}), 400
            
        hoy = date.today()
        # Lunes es 0, Domingo es 6
        dia_actual_idx = hoy.weekday()
        target_idx = dias_es[dia_semana]
        delta = target_idx - dia_actual_idx
        fecha_asignada = hoy + timedelta(days=delta)
        
        # Opcional: Eliminar comida anterior si existe en ese turno
        existente = MenuSemanal.query.filter_by(
            dia_semana=dia_semana, 
            tipo_comida=tipo_comida, 
            fecha_asignada=fecha_asignada
        ).first()
        
        if existente:
            db.session.delete(existente)
            db.session.flush()
            
        nuevo_menu = MenuSemanal(
            dia_semana=dia_semana,
            tipo_comida=tipo_comida,
            receta_id=receta.id,
            fecha_asignada=fecha_asignada
        )
        db.session.add(nuevo_menu)
        db.session.commit()
        
        return jsonify({'success': True, 'mensaje': 'Comida agregada al calendario.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@menus_bp.route('/menus')
@login_required
def menus_page():
    return render_template('views/menus.html', active_page='menus')


@menus_bp.route('/api/menus/horarios', methods=['GET'])
@login_required
def api_horarios_get():
    horarios = HorarioComidas.query.all()
    res = []
    for h in horarios:
        res.append({
            'id': h.id,
            'tipo_comida': h.tipo_comida,
            'hora_inicio': h.hora_inicio.strftime('%H:%M'),
            'hora_fin': h.hora_fin.strftime('%H:%M')
        })
    return jsonify(res)


@menus_bp.route('/api/menus/horarios', methods=['POST'])
@login_required
def api_horarios_post():
    data = request.json
    try:
        for item in data:
            h = db.session.get(HorarioComidas, item['id'])
            if h:
                h.hora_inicio = datetime.strptime(item['hora_inicio'], '%H:%M').time()
                h.hora_fin = datetime.strptime(item['hora_fin'], '%H:%M').time()
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@menus_bp.route('/api/menus/sugerir', methods=['GET'])
@login_required
def menus_sugerir():
    todas_recetas = Receta.query.all()
    posibles = []
    for rec in todas_recetas:
        puede_hacerse = True
        for ing in rec.ingredientes:
            if ing.producto.stock_actual < ing.cantidad_requerida:
                puede_hacerse = False
                break
        if puede_hacerse:
            posibles.append(rec)
            
    if not posibles:
        return jsonify({'error': 'No hay ingredientes suficientes para ninguna receta.'}), 404
        
    sugerida = random.choice(posibles)
    return jsonify({'id': sugerida.id, 'nombre': sugerida.nombre, 'tipo': sugerida.tipo, 'es_rapida': sugerida.es_rapida})


@menus_bp.route('/api/menus/sugerir_rapida', methods=['GET'])
@login_required
def menus_sugerir_rapida():
    rapidas = Receta.query.filter_by(es_rapida=True).all()
    if not rapidas:
        return jsonify({'error': 'No hay recetas rápidas cargadas.'}), 404
    sugerida = random.choice(rapidas)
    return jsonify({'id': sugerida.id, 'nombre': sugerida.nombre, 'tipo': sugerida.tipo, 'es_rapida': sugerida.es_rapida})


@menus_bp.route('/api/menus/<int:menu_id>', methods=['DELETE'])
@login_required
def eliminar_menu_api(menu_id):
    try:
        menu = db.session.get(MenuSemanal, menu_id)
        if not menu:
            return jsonify({'success': False, 'error': 'Menú no encontrado'}), 404
        
        db.session.delete(menu)
        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Comida eliminada correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@menus_bp.route('/api/menus/<int:menu_id>', methods=['PUT'])
@login_required
def editar_menu_api(menu_id):
    try:
        menu = db.session.get(MenuSemanal, menu_id)
        if not menu:
            return jsonify({'success': False, 'error': 'Menú no encontrado'}), 404

        data = request.json
        dia_semana = data.get('dia_semana')
        tipo_comida = data.get('tipo_comida')
        nombre = data.get('nombre')

        if not dia_semana or not tipo_comida or not nombre:
            return jsonify({'error': 'Faltan datos (día, tipo, nombre).'}), 400

        # Buscar receta o crear nueva
        receta = Receta.query.filter(Receta.nombre.ilike(f"%{nombre}%")).first()
        if not receta:
            receta = Receta(nombre=nombre, tipo=tipo_comida, es_rapida=True)
            db.session.add(receta)
            db.session.flush()

        dias_es = {'Lunes':0, 'Martes':1, 'Miércoles':2, 'Jueves':3, 'Viernes':4, 'Sábado':5, 'Domingo':6}
        if dia_semana not in dias_es:
            return jsonify({'error': 'Día de la semana inválido.'}), 400

        hoy = date.today()
        dia_actual_idx = hoy.weekday()
        target_idx = dias_es[dia_semana]
        delta = target_idx - dia_actual_idx
        fecha_asignada = hoy + timedelta(days=delta)

        menu.dia_semana = dia_semana
        menu.tipo_comida = tipo_comida
        menu.receta_id = receta.id
        menu.fecha_asignada = fecha_asignada

        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Comida actualizada correctamente.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@menus_bp.route('/api/menus/semana/duplicar', methods=['POST'])
@login_required
def menus_duplicar():
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(tz).date()
    # Identificar la semana pasada (hace 7 a 14 dias)
    fecha_limite_inf = hoy - timedelta(days=14)
    fecha_limite_sup = hoy - timedelta(days=7)
    
    pasada = MenuSemanal.query.filter(MenuSemanal.fecha_asignada >= fecha_limite_inf, MenuSemanal.fecha_asignada <= fecha_limite_sup).all()
    if not pasada:
        return jsonify({'error': 'No hay menú la semana pasada para duplicar.'}), 404
        
    nuevos = []
    for m in pasada:
        nueva_fecha = m.fecha_asignada + timedelta(days=7)
        nuevo_menu = MenuSemanal(
            dia_semana=m.dia_semana,
            tipo_comida=m.tipo_comida,
            receta_id=m.receta_id,
            fecha_asignada=nueva_fecha
        )
        nuevos.append(nuevo_menu)
        
    db.session.bulk_save_objects(nuevos)
    db.session.commit()
    return jsonify({'success': True, 'duplicados': len(nuevos)}), 200


@menus_bp.route('/api/menus/eventos', methods=['GET'])
@login_required
def api_menus_get():
    menus = MenuSemanal.query.all()
    result = []
    for m in menus:
        # Fake a time based on meal type for visualization on fullcalendar if it's month view, or just map it to an all-day event
        result.append({
            'id': m.id,
            'title': f"[{m.tipo_comida}] {m.receta.nombre}",
            'start': m.fecha_asignada.isoformat(),
            'allDay': True,
            'color': '#f39c12' if m.tipo_comida == 'Desayuno' else ('var(--success-color)' if m.tipo_comida == 'Almuerzo' else ('#9b59b6' if m.tipo_comida == 'Merienda' else 'var(--primary-color)')),
            'extendedProps': {
                'tipo_comida': m.tipo_comida,
                'nombre': m.receta.nombre,
                'dia_semana': m.dia_semana
            }
        })
    return jsonify(result)


