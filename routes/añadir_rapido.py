from flask import Blueprint, request, jsonify
from extensions import db
from models.database import Producto

añadir_rapido_bp = Blueprint('añadir_rapido', __name__)

@añadir_rapido_bp.route('/api/añadir_rapido', methods=['POST'])
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


