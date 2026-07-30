from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging
from utils import calcular_proxima_fecha, calcular_proximo_turno

tareas_bp = Blueprint('tareas', __name__)

@tareas_bp.route('/tareas')
@login_required
def tareas_view():
    return render_template('views/tareas.html', active_page='tareas')


@tareas_bp.route('/api/modelos', methods=['GET'])
@login_required
def get_modelos():
    modelos = ModeloTarea.query.all()
    hoy = datetime.now().date()
    res = []
    for m in modelos:
        d = m.to_dict()
        current_date = m.fecha_ultima_ejecucion or (hoy - timedelta(days=1))
        proxima = calcular_proxima_fecha(m, current_date)
        if m.tipo_frecuencia == 'fecha_fija':
            try: proxima = datetime.strptime(m.valor_frecuencia, '%Y-%m-%d').date()
            except: proxima = hoy
        d['proxima_fecha_calculada'] = proxima.isoformat()
        res.append(d)
    return jsonify(res)


@tareas_bp.route('/api/tareas', methods=['GET'])
@login_required
def get_tareas_activas():
    # Return instantiated tasks (for table and dashboard)
    tareas = Tarea.query.all()
    return jsonify([t.to_dict() for t in tareas])


@tareas_bp.route('/api/modelos', methods=['POST'])
@login_required
def crear_modelo():
    data = request.json
    if not data or 'nombre' not in data:
        return jsonify({'error': 'Falta el nombre'}), 400
    nueva = ModeloTarea(
        nombre=data['nombre'],
        tipo_frecuencia=data.get('tipo_frecuencia', 'dias'),
        valor_frecuencia=str(data.get('valor_frecuencia', '1')),
        prioridad=data.get('prioridad', 'Esencial'),
        alternar=data.get('alternar', True)
    )
    if 'fecha_inicio' in data and data['fecha_inicio']:
        nueva.fecha_ultima_ejecucion = datetime.strptime(data['fecha_inicio'], '%Y-%m-%d').date() - timedelta(days=1)
        
    if 'usuarios_ids' in data and isinstance(data['usuarios_ids'], list):
        for uid in data['usuarios_ids']:
            u = db.session.get(Usuario, uid)
            if u: nueva.usuarios.append(u)
            
    db.session.add(nueva)
    db.session.commit()
    return jsonify(nueva.to_dict()), 201


@tareas_bp.route('/api/modelos/<int:id_modelo>', methods=['PUT'])
@login_required
def editar_modelo(id_modelo):
    data = request.json
    modelo = db.get_or_404(ModeloTarea, id_modelo)
    if 'nombre' in data:
        modelo.nombre = data['nombre']
    if 'tipo_frecuencia' in data:
        modelo.tipo_frecuencia = data['tipo_frecuencia']
    if 'valor_frecuencia' in data:
        modelo.valor_frecuencia = str(data['valor_frecuencia'])
    if 'prioridad' in data:
        modelo.prioridad = data['prioridad']
    if 'alternar' in data:
        modelo.alternar = data['alternar']
    if 'usuarios_ids' in data and isinstance(data['usuarios_ids'], list):
        modelo.usuarios.clear()
        for uid in data['usuarios_ids']:
            u = db.session.get(Usuario, uid)
            if u: modelo.usuarios.append(u)
    db.session.commit()
    return jsonify(modelo.to_dict())


@tareas_bp.route('/api/modelos/<int:id_modelo>', methods=['DELETE'])
@login_required
def eliminar_modelo(id_modelo):
    modelo = db.get_or_404(ModeloTarea, id_modelo)
    
    # Unlink instantiated tasks instead of deleting them
    # Eliminar las tareas futuras (no completadas)
    tareas_futuras = Tarea.query.filter_by(modelo_id=modelo.id, completada=False).all()
    for t in tareas_futuras:
        HistorialTarea.query.filter_by(tarea_id=t.id).delete()
        SaltoTarea.query.filter_by(tarea_id=t.id).delete()
        db.session.delete(t)
    
    # Desvincular las tareas completadas (historial)
    Tarea.query.filter_by(modelo_id=modelo.id, completada=True).update({'modelo_id': None})
    
    db.session.delete(modelo)
    db.session.commit()
    return jsonify({'mensaje': 'Modelo Eliminado'})


@tareas_bp.route('/api/tareas/<int:id_tarea>', methods=['PUT'])
@login_required
def editar_tarea_instancia(id_tarea):
    data = request.json
    tarea = db.get_or_404(Tarea, id_tarea)
    if 'nombre' in data and data['nombre']:
        tarea.nombre = data['nombre']
    if 'prioridad' in data and data['prioridad']:
        tarea.prioridad = data['prioridad']
    if 'estado' in data:
        tarea.completada = (data['estado'] == 'completada' or data['estado'] is True)
    if 'completada' in data:
        tarea.completada = bool(data['completada'])
    
    # Manejo de fecha programada
    f_str = data.get('fecha') or data.get('fecha_programada') or data.get('fecha_inicio')
    if f_str:
        try:
            tarea.fecha_programada = datetime.strptime(str(f_str)[:10], "%Y-%m-%d").date()
        except Exception:
            pass

    if 'tipo_frecuencia' in data and data['tipo_frecuencia']:
        tarea.tipo_frecuencia = data['tipo_frecuencia']
    if 'valor_frecuencia' in data and data['valor_frecuencia']:
        tarea.valor_frecuencia = str(data['valor_frecuencia'])

    if tarea.modelo_id:
        mod = db.session.get(ModeloTarea, tarea.modelo_id)
        if mod:
            if 'nombre' in data and data['nombre']: mod.nombre = data['nombre']
            if 'prioridad' in data and data['prioridad']: mod.prioridad = data['prioridad']
            if 'tipo_frecuencia' in data and data['tipo_frecuencia']: mod.tipo_frecuencia = data['tipo_frecuencia']
            if 'valor_frecuencia' in data and data['valor_frecuencia']: mod.valor_frecuencia = str(data['valor_frecuencia'])
    db.session.commit()
    return jsonify(tarea.to_dict()), 200


@tareas_bp.route('/api/tareas/<int:id_tarea>', methods=['DELETE'])
@login_required
def eliminar_tarea(id_tarea):
    tarea = db.get_or_404(Tarea, id_tarea)
    HistorialTarea.query.filter_by(tarea_id=tarea.id).delete()
    SaltoTarea.query.filter_by(tarea_id=tarea.id).delete()
    db.session.delete(tarea)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


@tareas_bp.route('/api/tareas/<int:id_tarea>/skip', methods=['POST'])
@login_required
def skip_tarea(id_tarea):
    data = request.json
    if not data or 'motivo' not in data:
        return jsonify({'error': 'Falta el motivo'}), 400
        
    tarea = db.get_or_404(Tarea, id_tarea)
    
    now = datetime.now()
    saltos_mes = SaltoTarea.query.filter(
        SaltoTarea.usuario_id == current_user.id,
        extract('year', SaltoTarea.fecha) == now.year,
        extract('month', SaltoTarea.fecha) == now.month
    ).count()
    
    if saltos_mes >= 3:
        return jsonify({'error': 'Has alcanzado el límite de 3 delegaciones este mes.'}), 403
        
    nuevo_salto = SaltoTarea(
        tarea_id=tarea.id,
        usuario_id=current_user.id,
        motivo=data['motivo']
    )
    db.session.add(nuevo_salto)
    
    fake_historial = HistorialTarea(tarea_id=tarea.id, usuario_id=current_user.id)
    db.session.add(fake_historial)
    db.session.flush()
    
    nuevo_encargado_id = calcular_proximo_turno(tarea)
    nuevo_encargado_nombre = "Nadie"
    nuevo_encargado = None
    if nuevo_encargado_id:
        nuevo_encargado = db.session.get(Usuario, nuevo_encargado_id)
        if nuevo_encargado: nuevo_encargado_nombre = nuevo_encargado.username
        
    db.session.commit()
    
    skips_restantes = 3 - (saltos_mes + 1)
    
    # 1. Avisar al grupo
    mensaje_grupo = (f"⚠️ <b>{current_user.username}</b> ha delegado su turno de <b>{tarea.nombre}</b>.\n"
                     f"Motivo: {data['motivo']}\n"
                     f"(Le quedan {skips_restantes} skips este mes).\n"
                     f"El nuevo encargado es: <b>{nuevo_encargado_nombre}</b>")
    enviar_al_grupo(mensaje_grupo)
    
    # 2. Avisar al usuario por privado
    if nuevo_encargado:
        mensaje_privado = f"🔄 <b>{current_user.username}</b> te ha delegado una tarea.\n\nHoy es tu turno de: <b>{tarea.nombre}</b>."
        enviar_al_usuario(nuevo_encargado.id, mensaje_privado)
    
    return jsonify({'mensaje': 'Turno delegado con éxito', 'nuevo_encargado': nuevo_encargado_nombre}), 200


@tareas_bp.route('/api/calendario_tareas', methods=['GET'])
@login_required
def calendario_tareas():
    # Only return actual Tarea instances, no projection needed!
    tareas = Tarea.query.all()
    eventos = []
    
    for t in tareas:
        usuarios_ids = [u.id for u in t.usuarios]
        nombres_asignados = [u.username for u in t.usuarios]
        
        if not t.alternar:
            label_asignados = "Todos (" + ", ".join(nombres_asignados) + ")"
            user_id = None
        elif len(nombres_asignados) > 1:
            label_asignados = f"{t.usuarios[0].username} (de {len(nombres_asignados)})"
            user_id = t.usuarios[0].id
        else:
            label_asignados = t.usuarios[0].username if t.usuarios else "Nadie"
            user_id = t.usuarios[0].id if t.usuarios else None
            
        prioridad_emoji = "🔹"
        if getattr(t, 'completada', False): prioridad_emoji = "✅"
        elif t.prioridad == 'Urgente': prioridad_emoji = "🔥"
        elif t.prioridad == 'Secundaria': prioridad_emoji = "💤"
            
        color = '#0d6efd' # Esencial
        if getattr(t, 'completada', False): color = '#198754' # Verde si esta completada
        elif t.prioridad == 'Urgente': color = '#dc3545'
        elif t.prioridad == 'Secundaria': color = '#6c757d'
        
        proxima = getattr(t, 'fecha_programada', None) or t.fecha_ultima_ejecucion
        if not proxima: continue
        
        eventos.append({
            'id': t.id,
            'title': f"{prioridad_emoji} {t.nombre} ({label_asignados})",
            'start': proxima.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'tarea_id': t.id,
                'usuario_asignado': user_id,
                'nombre_tarea': t.nombre,
                'tipo_frecuencia': t.tipo_frecuencia,
                'valor_frecuencia': t.valor_frecuencia,
                'fecha_programada': proxima.isoformat()[:10],
                'completada': getattr(t, 'completada', False)
            }
        })
                
    return jsonify(eventos)


@tareas_bp.route('/api/tareas/<int:id_tarea>/completar', methods=['POST'])
@login_required
def completar_tarea(id_tarea):
    tarea = db.get_or_404(Tarea, id_tarea)
    tarea.completada = True
    
    # Register in Historial
    hist = HistorialTarea(tarea_id=tarea.id, usuario_id=current_user.id)
    db.session.add(hist)
    
    # Update model's last execution date if applicable
    if tarea.modelo_id:
        mod = db.session.get(ModeloTarea, tarea.modelo_id)
        if mod:
            mod.fecha_ultima_ejecucion = datetime.now().date()
            
    db.session.commit()
    return jsonify({'mensaje': 'Tarea completada'})


