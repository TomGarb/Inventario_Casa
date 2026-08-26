from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from models.database import db, Casa, UsuarioCasa, Usuario

casas_bp = Blueprint('casas', __name__)

@casas_bp.route('/casas')
@login_required
def gestionar_casas():
    # Obtener las casas del usuario
    mis_casas = UsuarioCasa.query.filter_by(usuario_id=current_user.id).all()
    return render_template('views/casas.html', mis_casas=mis_casas, current_casa_id=session.get('current_casa_id'))

@casas_bp.route('/casas/seleccionar', methods=['GET', 'POST'])
@login_required
def seleccionar():
    if request.method == 'POST':
        data = request.get_json()
        casa_id = data.get('casa_id')
        if casa_id:
            # Validar que pertenezca
            relacion = UsuarioCasa.query.filter_by(usuario_id=current_user.id, casa_id=casa_id).first()
            if relacion:
                session['current_casa_id'] = casa_id
                current_user.casa_activa_id = casa_id
                db.session.commit()
                return jsonify({'success': True})
            return jsonify({'error': 'No perteneces a esta casa'}), 403
        return jsonify({'error': 'Falta casa_id'}), 400
    
    mis_casas = UsuarioCasa.query.filter_by(usuario_id=current_user.id).all()
    return render_template('views/casas.html', mis_casas=mis_casas, current_casa_id=session.get('current_casa_id'))

@casas_bp.route('/casas/nueva', methods=['GET', 'POST'])
@login_required
def nueva():
    if request.method == 'POST':
        data = request.get_json()
        nombre = data.get('nombre')
        if nombre:
            nueva_casa = Casa(nombre=nombre)
            db.session.add(nueva_casa)
            db.session.flush() # Para obtener ID
            
            rel = UsuarioCasa(usuario_id=current_user.id, casa_id=nueva_casa.id, rol='admin', estado_invitacion='aceptada')
            db.session.add(rel)
            
            current_user.casa_activa_id = nueva_casa.id
            session['current_casa_id'] = nueva_casa.id
            db.session.commit()
            return jsonify({'success': True, 'casa_id': nueva_casa.id})
        return jsonify({'error': 'Nombre requerido'}), 400
    
    return render_template('views/casas.html', mis_casas=[], current_casa_id=None, mostrar_nueva=True)

@casas_bp.route('/api/casas/invitar', methods=['POST'])
@login_required
def invitar():
    data = request.get_json()
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username requerido'}), 400
        
    usuario = Usuario.query.filter_by(username=username).first()
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
        
    casa_id = session.get('current_casa_id')
    # Check admin
    rel_admin = UsuarioCasa.query.filter_by(usuario_id=current_user.id, casa_id=casa_id, rol='admin').first()
    if not rel_admin and not current_user.is_admin:
        return jsonify({'error': 'Solo admins de la casa pueden invitar'}), 403
        
    existente = UsuarioCasa.query.filter_by(usuario_id=usuario.id, casa_id=casa_id).first()
    if existente:
        return jsonify({'error': 'El usuario ya pertenece a la casa'}), 400
        
    nueva_rel = UsuarioCasa(usuario_id=usuario.id, casa_id=casa_id, rol='miembro', estado_invitacion='aceptada')
    db.session.add(nueva_rel)
    db.session.commit()
    return jsonify({'success': True, 'mensaje': f'Usuario {username} agregado a la casa.'})

@casas_bp.route('/casas/<int:casa_id>/edit', methods=['POST'])
@login_required
def editar_casa(casa_id):
    data = request.get_json()
    nombre = data.get('nombre')
    
    # Check if admin
    relacion = UsuarioCasa.query.filter_by(usuario_id=current_user.id, casa_id=casa_id, rol='admin').first()
    if not relacion:
        return jsonify({'error': 'No tienes permisos de administrador en esta casa'}), 403
        
    casa = Casa.query.get_or_404(casa_id)
    if nombre:
        casa.nombre = nombre
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Nombre inválido'}), 400

@casas_bp.route('/casas/<int:casa_id>/delete', methods=['POST'])
@login_required
def eliminar_casa(casa_id):
    # Check if admin
    relacion = UsuarioCasa.query.filter_by(usuario_id=current_user.id, casa_id=casa_id, rol='admin').first()
    if not relacion:
        return jsonify({'error': 'No tienes permisos de administrador en esta casa'}), 403
        
    casa = Casa.query.get_or_404(casa_id)
    
    # Import all models to manually delete by casa_id
    from models.database import (DetalleGasto, DivisionGasto, Gasto, IngredienteReceta, Receta, MenuSemanal, 
                                 HistorialTarea, SaltoTarea, Tarea, ModeloTarea, Movimiento, Producto, SubUbicacion, 
                                 Ubicacion, Sala, Comercio, EventoLogistico, HorarioComidas, MetaAhorro, 
                                 SuscripcionDeporte, Mascota, ConfiguracionGlobal)
                                 
    # 1. Leaves to Roots (Order matters for foreign keys if no ON DELETE CASCADE in DB)
    DetalleGasto.query.filter_by(casa_id=casa.id).delete()
    DivisionGasto.query.filter_by(casa_id=casa.id).delete()
    Gasto.query.filter_by(casa_id=casa.id).delete()
    
    IngredienteReceta.query.filter_by(casa_id=casa.id).delete()
    Receta.query.filter_by(casa_id=casa.id).delete()
    MenuSemanal.query.filter_by(casa_id=casa.id).delete()
    
    HistorialTarea.query.filter_by(casa_id=casa.id).delete()
    SaltoTarea.query.filter_by(casa_id=casa.id).delete()
    Tarea.query.filter_by(casa_id=casa.id).delete()
    ModeloTarea.query.filter_by(casa_id=casa.id).delete()
    
    Movimiento.query.filter_by(casa_id=casa.id).delete()
    Producto.query.filter_by(casa_id=casa.id).delete()
    
    SubUbicacion.query.filter_by(casa_id=casa.id).delete()
    Ubicacion.query.filter_by(casa_id=casa.id).delete()
    
    Sala.query.filter_by(casa_id=casa.id).delete()
    Comercio.query.filter_by(casa_id=casa.id).delete()
    
    EventoLogistico.query.filter_by(casa_id=casa.id).delete()
    HorarioComidas.query.filter_by(casa_id=casa.id).delete()
    MetaAhorro.query.filter_by(casa_id=casa.id).delete()
    SuscripcionDeporte.query.filter_by(casa_id=casa.id).delete()
    Mascota.query.filter_by(casa_id=casa.id).delete()
    
    ConfiguracionGlobal.query.filter_by(casa_id=casa.id).delete()
    UsuarioCasa.query.filter_by(casa_id=casa.id).delete()
    
    # Update users who had this house as active
    usuarios_afectados = Usuario.query.filter_by(casa_activa_id=casa.id).all()
    for u in usuarios_afectados:
        # Give them another house if they have one, else None
        otra_casa = UsuarioCasa.query.filter_by(usuario_id=u.id).first()
        u.casa_activa_id = otra_casa.casa_id if otra_casa else None
        if current_user.id == u.id:
            session['current_casa_id'] = u.casa_activa_id

    # Finally, delete the house itself
    db.session.delete(casa)
    db.session.commit()
    
    return jsonify({'success': True})
