from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging

auth_bp = Blueprint('auth', __name__)

def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Usuario.query.filter(Usuario.username.ilike(username)).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'danger')
        
    return render_template('login.html')

def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
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
            return redirect(url_for('dashboard'))
            
    return render_template('register.html')

def logout():
    logout_user()
    return redirect(url_for('auth.login_page'))

def perfil():
    return render_template('views/perfil.html', active_page='perfil')

def generar_token():
    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    current_user.telegram_link_token = token
    db.session.commit()
    return jsonify({'token': token})

def get_usuarios():
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios])

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

def delete_usuario(id_user):
    if current_user.id == id_user:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400
    u = db.get_or_404(Usuario, id_user)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'mensaje': 'Usuario eliminado'})

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

