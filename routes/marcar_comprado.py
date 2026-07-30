from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging

marcar_comprado_bp = Blueprint('marcar_comprado', __name__)

@marcar_comprado_bp.route('/api/marcar_comprado/<int:id_producto>', methods=['POST'])
def marcar_comprado(id_producto):
    producto = db.get_or_404(Producto, id_producto)
    if producto.es_temporal:
        db.session.delete(producto)
        accion = "eliminado_completamente"
    else:
        producto.en_lista = False
        accion = "removido_de_lista"
        
    db.session.commit()
    return jsonify({'mensaje': f'Producto {accion}', 'accion': accion})


