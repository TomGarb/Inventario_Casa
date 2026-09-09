from flask import Blueprint, request, jsonify, render_template, session
from flask_login import login_required, current_user
from extensions import db
from models.database import EventoLogistico, UsuarioCasa
from datetime import datetime, timedelta
import pytz
from sqlalchemy import or_

logistica_bp = Blueprint('logistica', __name__)

@logistica_bp.route('/logistica')
@login_required
def logistica_page():
    return render_template('views/logistica.html', active_page='logistica')


@logistica_bp.route('/api/logistica/eventos', methods=['GET'])
@login_required
def api_logistica_get():
    from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
    from dateutil import parser
    
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    try:
        start_date = parser.isoparse(start_str).replace(tzinfo=None) if start_str else None
        end_date = parser.isoparse(end_str).replace(tzinfo=None) if end_str else None
    except Exception:
        start_date = None
        end_date = None

    casas_ids = [rel.casa_id for rel in current_user.casas_rel]
    if not casas_ids and current_user.casa_activa_id:
        casas_ids = [current_user.casa_activa_id]

    usuarios_casas = [rel.usuario_id for rel in UsuarioCasa.query.filter(UsuarioCasa.casa_id.in_(casas_ids)).all()] if casas_ids else []
    if current_user.id not in usuarios_casas:
        usuarios_casas.append(current_user.id)

    # Auto-asociar eventos huérfanos sin casa_id (por ejemplo, deportivos previamente sincronizados) a la casa activa
    casa_activa = session.get('current_casa_id', current_user.casa_activa_id) or (casas_ids[0] if casas_ids else None)
    if casa_activa:
        huerfanos = EventoLogistico.query.filter(
            EventoLogistico.casa_id.is_(None),
            EventoLogistico.creador_id.in_(usuarios_casas)
        ).all()
        if huerfanos:
            for h in huerfanos:
                h.casa_id = casa_activa
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    condiciones = [EventoLogistico.casa_id.is_(None)]
    if casas_ids:
        condiciones.append(EventoLogistico.casa_id.in_(casas_ids))
        
    eventos = EventoLogistico.query.filter(or_(*condiciones)).all()
    result = []
    
    for ev in eventos:
        color = getattr(ev, 'color', None) or '#6f42c1' # Default to purple if no color
        
        # Build base event
        creador_nombre = ev.creador.username if getattr(ev, 'creador', None) else None
        asignado_nombre = ev.asignado.username if getattr(ev, 'asignado', None) else None
        if asignado_nombre:
            display_title = f"{ev.titulo} ({asignado_nombre})"
        elif creador_nombre and not ev.titulo.startswith('['):
            display_title = f"{ev.titulo} ({creador_nombre})"
        else:
            display_title = ev.titulo

        base_event = {
            'id': ev.id,
            'title': display_title,
            'raw_title': ev.titulo,
            'frecuencia': ev.frecuencia,
            'asignado_id': ev.asignado_id,
            'backgroundColor': color,
            'borderColor': color
        }
        
        if ev.frecuencia == 'none' or not ev.frecuencia:
            # Not recurring, just check if within bounds
            if start_date and end_date:
                fecha_limite_fin = ev.fecha_fin or ev.fecha_inicio
                if ev.fecha_inicio >= end_date or fecha_limite_fin < start_date:
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


@logistica_bp.route('/api/logistica/eventos/<int:id_evento>', methods=['PUT', 'DELETE'])
@login_required
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
        except Exception:
            pass
    if 'end' in data:
        if data['end']:
            try:
                dt_fin_naive = datetime.strptime(data['end'][:16], "%Y-%m-%dT%H:%M")
                ev.fecha_fin = tz.localize(dt_fin_naive)
            except Exception:
                pass
        else:
            ev.fecha_fin = None
    if 'frecuencia' in data:
        ev.frecuencia = data['frecuencia']
    if 'asignado_id' in data:
        ev.asignado_id = int(data['asignado_id']) if data['asignado_id'] else None
    db.session.commit()
    return jsonify({'success': True, 'id': ev.id})


@logistica_bp.route('/api/logistica/eventos', methods=['POST'])
@login_required
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
            
        from flask import session
        nuevo_evento = EventoLogistico(
            titulo=data['title'],
            fecha_inicio=f_inicio,
            fecha_fin=f_fin,
            creador_id=current_user.id,
            casa_id=session.get('current_casa_id', current_user.casa_activa_id),
            frecuencia=data.get('frecuencia', 'none'),
            asignado_id=data.get('asignado_id') if data.get('asignado_id') else None
        )
        db.session.add(nuevo_evento)
        db.session.commit()
        return jsonify({'success': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


