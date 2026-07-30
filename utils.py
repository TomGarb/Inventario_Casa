from functools import wraps
from flask import jsonify, request
from flask_login import current_user
from extensions import db

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
