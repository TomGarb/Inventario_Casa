from functools import wraps
from flask import jsonify, request
from flask_login import current_user
from extensions import db
from datetime import datetime, date, timedelta
import calendar
from collections import defaultdict

def is_authorized(user_id):
    from models.database import Usuario
    user = Usuario.query.filter_by(telegram_chat_id=str(user_id)).first()
    return user is not None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'error': 'Requiere permisos de administrador'}), 403
        return f(*args, **kwargs)
    return decorated_function

def crud_create(modelo, requeridos, campos_adicionales=None):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos faltantes'}), 400
    for req in requeridos:
        if req not in data:
            return jsonify({'error': f'El campo {req} es obligatorio'}), 400
            
    kwargs = {req: data[req] for req in requeridos}
    if campos_adicionales:
        for extra in campos_adicionales:
            if extra in data:
                kwargs[extra] = data[extra]
                
    try:
        entidad = modelo(**kwargs)
        db.session.add(entidad)
        db.session.commit()
        return jsonify(entidad.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def crud_update(modelo, id_entidad, requeridos, campos_adicionales=None):
    entidad = db.get_or_404(modelo, id_entidad)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos faltantes'}), 400
        
    for req in requeridos:
        if req not in data:
            return jsonify({'error': f'El campo {req} es obligatorio'}), 400
        setattr(entidad, req, data[req])
        
    if campos_adicionales:
        for extra in campos_adicionales:
            if extra in data:
                setattr(entidad, extra, data[extra])
                
    try:
        db.session.commit()
        return jsonify(entidad.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def calcular_balances_globales():
    from models.database import DivisionGasto, Usuario
    divisiones = DivisionGasto.query.filter_by(esta_pagado=False).all()
    deudas = defaultdict(lambda: defaultdict(float))
    
    for div in divisiones:
        deudor = div.usuario_id
        acreedor = div.rel_gasto.usuario_id
        if deudor != acreedor:
            deudas[deudor][acreedor] += div.monto_adeudado
            
    usuarios_ids = list(deudas.keys())
    for deudor in usuarios_ids:
        for acreedor in list(deudas[deudor].keys()):
            if deudor in deudas[acreedor]:
                deuda_ida = deudas[deudor][acreedor]
                deuda_vuelta = deudas[acreedor][deudor]
                
                if deuda_ida > deuda_vuelta:
                    deudas[deudor][acreedor] -= deuda_vuelta
                    del deudas[acreedor][deudor]
                elif deuda_vuelta > deuda_ida:
                    deudas[acreedor][deudor] -= deuda_ida
                    del deudas[deudor][acreedor]
                else:
                    del deudas[deudor][acreedor]
                    del deudas[acreedor][deudor]
                    
    resultado = []
    for deudor_id, deudores_dict in deudas.items():
        for acreedor_id, monto in deudores_dict.items():
            u_deudor = db.session.get(Usuario, deudor_id)
            u_acreedor = db.session.get(Usuario, acreedor_id)
            if u_deudor and u_acreedor and monto > 0:
                resultado.append({
                    'deudor_id': deudor_id,
                    'deudor_nombre': u_deudor.username,
                    'acreedor_id': acreedor_id,
                    'acreedor_nombre': u_acreedor.username,
                    'monto': round(monto, 2)
                })
    return resultado

def calcular_proxima_fecha(tarea, desde_fecha):
    if not desde_fecha:
        return datetime.now().date()
    if tarea.tipo_frecuencia == 'dias':
        try:
            dias = int(tarea.valor_frecuencia)
        except:
            dias = 1
        return desde_fecha + timedelta(days=dias)
    elif tarea.tipo_frecuencia == 'dia_semana':
        days_map = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6}
        target = days_map.get(str(tarea.valor_frecuencia), 0)
        days_ahead = target - desde_fecha.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return desde_fecha + timedelta(days=days_ahead)
    elif tarea.tipo_frecuencia == 'mes':
        if desde_fecha.month == 12:
            next_month = 1
            next_year = desde_fecha.year + 1
        else:
            next_month = desde_fecha.month + 1
            next_year = desde_fecha.year
        if tarea.valor_frecuencia == 'inicio':
            return date(next_year, next_month, 1)
        elif tarea.valor_frecuencia == 'fin':
            last_day = calendar.monthrange(next_year, next_month)[1]
            return date(next_year, next_month, last_day)
        else:
            try:
                day_val = int(tarea.valor_frecuencia)
                if desde_fecha.day < day_val:
                    last_day_current = calendar.monthrange(desde_fecha.year, desde_fecha.month)[1]
                    target_day = min(day_val, last_day_current)
                    return date(desde_fecha.year, desde_fecha.month, target_day)
                else:
                    last_day_next = calendar.monthrange(next_year, next_month)[1]
                    target_day = min(day_val, last_day_next)
                    return date(next_year, next_month, target_day)
            except ValueError:
                return date(next_year, next_month, 1)
    elif tarea.tipo_frecuencia == 'fecha_fija':
        try:
            return datetime.strptime(tarea.valor_frecuencia, '%Y-%m-%d').date()
        except:
            return desde_fecha
    return desde_fecha + timedelta(days=1)

def calcular_proximo_turno(tarea):
    from models.database import HistorialTarea
    if not tarea.usuarios:
        return None
    ultimo = HistorialTarea.query.filter_by(tarea_id=tarea.id).order_by(HistorialTarea.fecha.desc()).first()
    if not ultimo:
        return tarea.usuarios[0].id
    usuarios_ids = [u.id for u in tarea.usuarios]
    if ultimo.usuario_id in usuarios_ids:
        idx = usuarios_ids.index(ultimo.usuario_id)
        next_idx = (idx + 1) % len(usuarios_ids)
        return usuarios_ids[next_idx]
    return usuarios_ids[0]



def formatear_fecha_amigable(f_val):
    import re
    if not f_val: return ""
    try:
        if isinstance(f_val, str):
            clean_str = re.sub(r'([+-]\d{2}:?\d{2}|Z)$', '', f_val.strip())
            dt = None
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(clean_str[:len("2026-08-15T15:00:00")[:len(clean_str)]], fmt)
                    break
                except:
                    continue
            if not dt:
                try:
                    dt = datetime.fromisoformat(clean_str)
                except:
                    return str(f_val)
        elif isinstance(f_val, datetime):
            dt = f_val
        elif isinstance(f_val, date):
            return f_val.strftime('%d/%m/%Y')
        else:
            return str(f_val)
        return dt.strftime('%d/%m/%Y a las %H:%M hs.')
    except Exception:
        return str(f_val)

def consumir_receta(receta_id):
    from models.database import Receta
    receta = db.session.get(Receta, receta_id)
    if not receta: return False
    
    for ing in receta.ingredientes:
        if ing.producto.stock_actual >= ing.cantidad_requerida:
            ing.producto.stock_actual -= ing.cantidad_requerida
        else:
            ing.producto.stock_actual = 0
    db.session.commit()
    return True
