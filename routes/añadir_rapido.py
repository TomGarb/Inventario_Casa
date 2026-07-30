from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging

añadir_rapido_bp = Blueprint('añadir_rapido', __name__)

def añadir_rapido():
    data = request.json
    nuevo = Producto(
        nombre=data['nombre'],
        comercio_id=data.get('comercio_id'),
        stock_actual=0.0,
        stock_minimo=1.0,
        unidad_medida='unidades',
        en_lista=True,
        es_temporal=True
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201

