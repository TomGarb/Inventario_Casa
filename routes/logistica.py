from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging

logistica_bp = Blueprint('logistica', __name__)

def logistica_page():
    return render_template('views/logistica.html', active_page='logistica')

def api_logistica_get():
    from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
    from dateutil import parser
    
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    try:
        start_date = parser.isoparse(start_str).replace(tzinfo=None) if start_str else None
        end_date = parser.isoparse(end_str).replace(tzinfo=None) if end_str else None
    except:
        start_date = None
        end_date = None

    eventos = EventoLogistico.query.all()
    result = []
    
    for ev in eventos:
        color = '#6f42c1' # Purple default
        
        # Build base event
        base_event = {
            'id': ev.id,
            'title': f"{ev.titulo} ({ev.asignado.username})" if getattr(ev, 'asignado', None) else (f"{ev.titulo} ({ev.creador.username})" if getattr(ev, 'creador', None) else ev.titulo),
            'raw_title': ev.titulo,
            'frecuencia': ev.frecuencia,
            'asignado_id': ev.asignado_id,
            'backgroundColor': color,
            'borderColor': color
        }
        
        if ev.frecuencia == 'none' or not ev.frecuencia:
            # Not recurring, just check if within bounds
            if start_date and end_date:
                if ev.fecha_inicio >= end_date or (ev.fecha_fin and ev.fecha_fin <= start_date):
                    continue
            
            ev_dict = base_event.copy()
            ev_dict['start'] = ev.fecha_inicio.isoformat()
            if ev.fecha_fin: ev_dict['end'] = ev.fecha_fin.isoformat()
            result.append(ev_dict)
        else:
            # Recurring event
            freq_map = {
                'diaria': DAILY,
                'semanal': WEEKLY,
                'mensual': MONTHLY,
                'anual': YEARLY
            }
            if ev.frecuencia in freq_map:
                try:
                    # RRule until end_date (or max 1 year if no end bounds)
                    until_date = end_date if end_date else (ev.fecha_inicio + timedelta(days=365))
                    rule = rrule(freq_map[ev.frecuencia], dtstart=ev.fecha_inicio, until=until_date)
                    
                    duration = None
                    if ev.fecha_fin:
                        duration = ev.fecha_fin - ev.fecha_inicio
                        
                    for dt in rule:
                        if start_date and dt < start_date:
                            continue
                            
                        ev_dict = base_event.copy()
                        ev_dict['start'] = dt.isoformat()
                        if duration:
                            ev_dict['end'] = (dt + duration).isoformat()
                        result.append(ev_dict)
                except Exception as e:
                    import logging
                    logging.error(f"Error procesando rrule en evento iterativo: {e}")
                    
    return jsonify(result)

def api_logistica_evento_item(id_evento):
    ev = db.get_or_404(EventoLogistico, id_evento)
    if request.method == 'DELETE':
        db.session.delete(ev)
        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Evento eliminado'})
    
    data = request.json
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    if 'title' in data and data['title']:
        ev.titulo = data['title']
    if 'start' in data and data['start']:
        try:
            dt_inicio_naive = datetime.strptime(data['start'][:16], "%Y-%m-%dT%H:%M")
            ev.fecha_inicio = tz.localize(dt_inicio_naive)
        except Exception as e:
            pass
    if 'end' in data:
        if data['end']:
            try:
                dt_fin_naive = datetime.strptime(data['end'][:16], "%Y-%m-%dT%H:%M")
                ev.fecha_fin = tz.localize(dt_fin_naive)
            except Exception as e:
                pass
        else:
            ev.fecha_fin = None
    if 'frecuencia' in data:
        ev.frecuencia = data['frecuencia']
    if 'asignado_id' in data:
        ev.asignado_id = int(data['asignado_id']) if data['asignado_id'] else None
    db.session.commit()
    return jsonify({'success': True, 'id': ev.id})

def api_logistica_post():
    data = request.json
    try:
        # Front end manda 'YYYY-MM-DDTHH:MM' (hora local de BA)
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        
        # Parse naive dt and localize it
        dt_inicio_naive = datetime.strptime(data['start'], "%Y-%m-%dT%H:%M")
        f_inicio = tz.localize(dt_inicio_naive)
        
        f_fin = None
        if data.get('end'):
            dt_fin_naive = datetime.strptime(data['end'], "%Y-%m-%dT%H:%M")
            f_fin = tz.localize(dt_fin_naive)
            
        nuevo_evento = EventoLogistico(
            titulo=data['title'],
            fecha_inicio=f_inicio,
            fecha_fin=f_fin,
            creador_id=current_user.id,
            frecuencia=data.get('frecuencia', 'none'),
            asignado_id=data.get('asignado_id') if data.get('asignado_id') else None
        )
        db.session.add(nuevo_evento)
        db.session.commit()
        return jsonify({'success': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

