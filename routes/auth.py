from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas, SuscripcionDeporte
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging
import random
import string
from utils import admin_required
from services.api_eventos import sync_eventos_deportivos

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Usuario.query.filter(Usuario.username.ilike(username)).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('main.dashboard'))
        flash('Usuario o contraseña incorrectos', 'danger')
        
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if Usuario.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe', 'danger')
        else:
            new_user = Usuario(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('main.dashboard'))
            
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login_page'))


@auth_bp.route('/perfil')
@login_required
def perfil():
    return render_template('views/perfil.html', active_page='perfil')


@auth_bp.route('/api/generar_token', methods=['POST'])
@login_required
def generar_token():
    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    current_user.telegram_link_token = token
    db.session.commit()
    return jsonify({'token': token})


@auth_bp.route('/api/usuarios', methods=['GET'])
@admin_required
def get_usuarios():
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios])


@auth_bp.route('/api/usuarios', methods=['POST'])
@admin_required
def crear_usuario():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
        
    if Usuario.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'El usuario ya existe'}), 400
        
    u = Usuario(username=data['username'], is_admin=data.get('is_admin', False))
    u.set_password(data['password'])
    db.session.add(u)
    db.session.commit()
    return jsonify(u.to_dict()), 201


@auth_bp.route('/api/usuarios/<int:id_user>', methods=['DELETE'])
@admin_required
def delete_usuario(id_user):
    if current_user.id == id_user:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400
    u = db.get_or_404(Usuario, id_user)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'mensaje': 'Usuario eliminado'})


@auth_bp.route('/api/usuarios/<int:id_user>', methods=['PUT'])
@admin_required
def update_usuario(id_user):
    data = request.get_json()
    u = db.get_or_404(Usuario, id_user)
    
    if 'is_admin' in data:
        if current_user.id == id_user and not data['is_admin']:
            return jsonify({'error': 'No puedes quitarte tu propio rol de admin'}), 400
        u.is_admin = data['is_admin']
        
    if 'password' in data and data['password']:
        u.set_password(data['password'])
        
    db.session.commit()
    return jsonify({'mensaje': 'Usuario actualizado'})


@auth_bp.route('/api/usuarios/<int:id>/password', methods=['PUT'])
@login_required
def change_password(id):
    if current_user.id != id and not current_user.is_admin:
        return jsonify({'error': 'No tienes permisos para cambiar esta contraseña'}), 403
        
    data = request.get_json()
    if not data or 'nueva_password' not in data:
        return jsonify({'error': 'Falta la nueva contraseña'}), 400
        
    u = db.get_or_404(Usuario, id)
    u.set_password(data['nueva_password'])
    db.session.commit()
    return jsonify({'mensaje': 'Contraseña actualizada correctamente'})

@auth_bp.route('/api/perfil/preferencias', methods=['POST'])
@login_required
def guardar_preferencias():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400
        
    current_user.recibir_resumen_matutino = data.get('recibir_resumen_matutino', True)
    current_user.recibir_alertas_vencimiento = data.get('recibir_alertas_vencimiento', True)
    current_user.recibir_recordatorios_tareas = data.get('recibir_recordatorios_tareas', True)
    
    db.session.commit()
    return jsonify({'mensaje': 'Preferencias guardadas exitosamente'})


@auth_bp.route('/api/perfil/configuracion', methods=['GET', 'POST'])
@admin_required
def configuracion_global():
    from models.database import ConfiguracionGlobal
    config = ConfiguracionGlobal.query.first()
    
    if request.method == 'GET':
        if not config:
            return jsonify({'grupo_principal_telegram_id': '', 'hora_alerta_stock': '10:00'})
        return jsonify({
            'grupo_principal_telegram_id': config.grupo_principal_telegram_id or '',
            'hora_alerta_stock': config.hora_alerta_stock or '10:00'
        })
        
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibieron datos'}), 400
            
        if not config:
            config = ConfiguracionGlobal()
            db.session.add(config)
            
        config.grupo_principal_telegram_id = data.get('grupo_principal_telegram_id', '')
        config.hora_alerta_stock = data.get('hora_alerta_stock', '10:00')
        db.session.commit()
        return jsonify({'mensaje': 'Configuración global guardada exitosamente'})

# ==========================================
# SUSCRIPCIONES DEPORTIVAS
# ==========================================

@auth_bp.route('/api/suscripciones', methods=['GET'])
@login_required
def get_suscripciones():
    subs = SuscripcionDeporte.query.filter_by(usuario_id=current_user.id).all()
    return jsonify([s.to_dict() for s in subs])

@auth_bp.route('/api/suscripciones', methods=['POST'])
@login_required
def crear_suscripcion():
    data = request.get_json()
    nombre = data.get('nombre', '').strip()
    external_api_id = data.get('external_api_id', '').strip()
    tipo = data.get('tipo', '').strip()
    color = data.get('color', '#3b82f6').strip()
    
    if not nombre or not external_api_id or tipo not in ('equipo', 'liga'):
        return jsonify({'error': 'Datos incompletos. Se requiere nombre, external_api_id y tipo (equipo/liga)'}), 400
    
    sub = SuscripcionDeporte(
        usuario_id=current_user.id,
        nombre=nombre,
        external_api_id=external_api_id,
        tipo=tipo,
        color=color
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify(sub.to_dict()), 201

@auth_bp.route('/api/suscripciones/<int:id>', methods=['DELETE'])
@login_required
def eliminar_suscripcion(id):
    sub = SuscripcionDeporte.query.get_or_404(id)
    if sub.usuario_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'No autorizado'}), 403
    db.session.delete(sub)
    db.session.commit()
    return jsonify({'mensaje': 'Suscripción eliminada'})

@auth_bp.route('/api/sincronizar_deportes', methods=['POST'])
@login_required
def sincronizar_deportes_manual():
    try:
        sync_eventos_deportivos(current_app._get_current_object())
        return jsonify({"status": "success", "message": "Eventos sincronizados correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
