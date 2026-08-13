from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db, bot
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging
import os
from utils import crud_create, crud_update
from services.bot_telegram import enviar_listas_agrupadas, enviar_al_grupo

CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

inventario_bp = Blueprint('inventario', __name__)

@inventario_bp.route('/inventario')
def inventario():
    return render_template('views/inventario.html', active_page='inventario')


@inventario_bp.route('/compras')
def compras():
    return render_template('views/compras.html', active_page='compras')


@inventario_bp.route('/api/espacios', methods=['GET'])
def obtener_espacios():
    salas = Sala.query.all()
    return jsonify([s.to_dict() for s in salas])


@inventario_bp.route('/api/salas', methods=['POST'])
def crear_sala():
    return crud_create(Sala, ['nombre'], ['piso'])


@inventario_bp.route('/api/sala/editar/<int:id>', methods=['PUT'])
def editar_sala(id):
    return crud_update(Sala, id, ['nombre'])


@inventario_bp.route('/api/salas/<int:id_sala>', methods=['DELETE'])
def eliminar_sala(id_sala):
    s = db.get_or_404(Sala, id_sala)
    for u in s.ubicaciones:
        for su in u.sub_ubicaciones:
            for p in su.productos:
                p.sub_ubicacion_id = None
                p.ubicacion_id = None
        for p in u.productos:
            p.ubicacion_id = None
            p.sub_ubicacion_id = None
    db.session.delete(s)
    db.session.commit()
    return jsonify({'mensaje': 'Sala eliminada y productos movidos a Sin asignar'})


@inventario_bp.route('/api/ubicaciones', methods=['POST'])
def crear_ubicacion():
    return crud_create(Ubicacion, ['nombre', 'sala_id'])


@inventario_bp.route('/api/ubicacion/editar/<int:id>', methods=['PUT'])
def editar_ubicacion(id):
    return crud_update(Ubicacion, id, ['nombre'])


@inventario_bp.route('/api/ubicaciones/<int:id_ubi>', methods=['DELETE'])
def eliminar_ubicacion(id_ubi):
    u = db.get_or_404(Ubicacion, id_ubi)
    for su in u.sub_ubicaciones:
        for p in su.productos:
            p.sub_ubicacion_id = None
            p.ubicacion_id = None
    for p in u.productos:
        p.ubicacion_id = None
        p.sub_ubicacion_id = None
    db.session.delete(u)
    db.session.commit()
    return jsonify({'mensaje': 'Ubicacion eliminada y productos movidos a Sin asignar'})


@inventario_bp.route('/api/sub_ubicaciones', methods=['POST'])
def crear_sububicacion():
    return crud_create(SubUbicacion, ['nombre', 'ubicacion_id'])


@inventario_bp.route('/api/sububicacion/editar/<int:id>', methods=['PUT'])
def editar_sububicacion(id):
    return crud_update(SubUbicacion, id, ['nombre'])


@inventario_bp.route('/api/sub_ubicaciones/<int:id_sub>', methods=['DELETE'])
def eliminar_sububicacion(id_sub):
    su = db.get_or_404(SubUbicacion, id_sub)
    for p in su.productos:
        p.sub_ubicacion_id = None
    db.session.delete(su)
    db.session.commit()
    return jsonify({'mensaje': 'Sububicacion eliminada y productos movidos a la Ubicación padre'})


@inventario_bp.route('/api/comercios', methods=['GET'])
def obtener_comercios():
    comercios = Comercio.query.all()
    return jsonify([c.to_dict() for c in comercios])


@inventario_bp.route('/api/comercios', methods=['POST'])
def crear_comercio():
    return crud_create(Comercio, ['nombre'])


@inventario_bp.route('/api/comercios/<int:id_comercio>', methods=['PUT'])
def editar_comercio(id_comercio):
    return crud_update(Comercio, id_comercio, ['nombre'])


@inventario_bp.route('/api/comercios/<int:id_comercio>', methods=['DELETE'])
def eliminar_comercio(id_comercio):
    c = db.get_or_404(Comercio, id_comercio)
    for p in c.productos:
        p.comercio_id = None
    db.session.delete(c)
    db.session.commit()
    return jsonify({'mensaje': 'Comercio eliminado'})


@inventario_bp.route('/api/productos', methods=['GET'])
def obtener_productos():
    productos = Producto.query.order_by(Producto.id).all()
    return jsonify([p.to_dict() for p in productos])


@inventario_bp.route('/api/productos', methods=['POST'])
def agregar_producto():
    data = request.json
    if not data or 'nombre' not in data:
        return jsonify({'error': 'El nombre es obligatorio'}), 400

    nuevo_producto = Producto(
        nombre=data['nombre'],
        descripcion=data.get('descripcion', ''),
        comercio_id=data.get('comercio_id'),
        stock_actual=float(data.get('stock_actual', 0)),
        stock_minimo=float(data.get('stock_minimo', 1)),
        unidad_medida=data.get('unidad_medida', 'unidades'),
        es_temporal=data.get('es_temporal', False),
        ubicacion_id=data.get('ubicacion_id'),
        sub_ubicacion_id=data.get('sub_ubicacion_id')
    )
    db.session.add(nuevo_producto)
    
    m = Movimiento(descripcion=f"Se creó un nuevo producto: {nuevo_producto.nombre} con stock {nuevo_producto.stock_actual}", producto_id=nuevo_producto.id, tipo="creacion", cantidad=nuevo_producto.stock_actual)
    db.session.add(m)
    db.session.commit()
    return jsonify(nuevo_producto.to_dict()), 201


@inventario_bp.route('/api/productos/<int:id_producto>', methods=['PUT'])
def editar_producto(id_producto):
    data = request.json
    if not data:
        return jsonify({'error': 'Faltan datos'}), 400
        
    producto = db.get_or_404(Producto, id_producto)
    
    if 'nombre' in data:
        producto.nombre = data['nombre']
    if 'descripcion' in data:
        producto.descripcion = data['descripcion']
    if 'comercio_id' in data:
        producto.comercio_id = data['comercio_id'] if data['comercio_id'] != '' else None
    if 'stock_actual' in data:
        producto.stock_actual = float(data['stock_actual'])
    if 'stock_minimo' in data:
        producto.stock_minimo = float(data['stock_minimo'])
    if 'unidad_medida' in data:
        producto.unidad_medida = data['unidad_medida']
    if 'ubicacion_id' in data:
        producto.ubicacion_id = data['ubicacion_id'] if data['ubicacion_id'] != '' else None
    if 'sub_ubicacion_id' in data:
        producto.sub_ubicacion_id = data['sub_ubicacion_id'] if data['sub_ubicacion_id'] != '' else None
    if 'en_lista' in data:
        producto.en_lista = data['en_lista']
        
    db.session.commit()
    
    m = Movimiento(descripcion=f"Se editó el producto: {producto.nombre}", producto_id=producto.id, tipo="edicion", cantidad=0)
    db.session.add(m)
    db.session.commit()
    
    return jsonify(producto.to_dict())


@inventario_bp.route('/api/productos/<int:id_producto>', methods=['DELETE'])
def eliminar_producto(id_producto):
    producto = db.get_or_404(Producto, id_producto)
    db.session.delete(producto)
    db.session.commit()
    return jsonify({'mensaje': 'Producto eliminado exitosamente'})


@inventario_bp.route('/api/producto/mover/<int:id_producto>', methods=['POST'])
def mover_producto(id_producto):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No se enviaron datos'}), 400
        
    producto = db.get_or_404(Producto, id_producto)
    if 'ubicacion_id' in data:
        producto.ubicacion_id = data['ubicacion_id'] if data['ubicacion_id'] else None
    if 'sub_ubicacion_id' in data:
        producto.sub_ubicacion_id = data['sub_ubicacion_id'] if data['sub_ubicacion_id'] else None
        
    db.session.commit()
    return jsonify({'mensaje': 'Ubicación actualizada', 'producto': producto.to_dict()})


@inventario_bp.route('/api/productos/bulk-mover', methods=['POST'])
def bulk_mover_productos():
    data = request.json
    if not data or 'producto_ids' not in data:
        return jsonify({'error': 'Faltan IDs de productos'}), 400
        
    producto_ids = data['producto_ids']
    ubicacion_id = data.get('ubicacion_id')
    sub_ubicacion_id = data.get('sub_ubicacion_id')
    
    productos = Producto.query.filter(Producto.id.in_(producto_ids)).all()
    for p in productos:
        if 'ubicacion_id' in data:
            p.ubicacion_id = ubicacion_id if ubicacion_id else None
        if 'sub_ubicacion_id' in data:
            p.sub_ubicacion_id = sub_ubicacion_id if sub_ubicacion_id else None
            
    db.session.commit()
    return jsonify({'mensaje': f'{len(productos)} productos movidos con éxito'})


@inventario_bp.route('/api/productos/bulk', methods=['POST'])
def crear_productos_bulk():
    data = request.get_json()
    if not data or 'sub_ubicacion_id' not in data or 'productos' not in data:
        return jsonify({'error': 'Faltan datos (sub_ubicacion_id o productos)'}), 400
        
    sub_ubicacion_id = data['sub_ubicacion_id']
    ubicacion_id = data.get('ubicacion_id')
    productos_lista = data['productos']
    
    if not productos_lista:
        return jsonify({'error': 'La lista de productos está vacía'}), 400
        
    nombres_enviados = [p['nombre'].strip().lower() for p in productos_lista]
    existentes = Producto.query.filter(
        Producto.sub_ubicacion_id == sub_ubicacion_id,
        db.func.lower(Producto.nombre).in_(nombres_enviados)
    ).all()
    
    mapa_existentes = {p.nombre.lower(): p for p in existentes}
    conflictos = []
    
    for prod_data in productos_lista:
        nombre_lower = prod_data['nombre'].strip().lower()
        if nombre_lower in mapa_existentes:
            if 'accion_duplicado' not in prod_data or not prod_data['accion_duplicado']:
                conflictos.append(prod_data['nombre'])
                
    if conflictos:
        return jsonify({'error': 'Conflictos encontrados', 'conflictos': list(set(conflictos))}), 409
        
    procesados = 0
    for prod_data in productos_lista:
        nombre_lower = prod_data['nombre'].strip().lower()
        if nombre_lower in mapa_existentes:
            accion = prod_data.get('accion_duplicado')
            existente = mapa_existentes[nombre_lower]
            if accion == 'sumar':
                existente.stock_actual += float(prod_data.get('stock_actual', 0))
                procesados += 1
            elif accion == 'sobreescribir':
                existente.stock_actual = float(prod_data.get('stock_actual', 1))
                existente.stock_minimo = float(prod_data.get('stock_minimo', 1))
                if 'unidad_medida' in prod_data:
                    existente.unidad_medida = prod_data['unidad_medida']
                existente.comercio_id = prod_data.get('comercio_id')
                procesados += 1
        else:
            nuevo = Producto(
                nombre=prod_data['nombre'].strip(),
                stock_actual=float(prod_data.get('stock_actual', 1)),
                stock_minimo=float(prod_data.get('stock_minimo', 1)),
                unidad_medida=prod_data.get('unidad_medida', 'unidades'),
                ubicacion_id=ubicacion_id,
                sub_ubicacion_id=sub_ubicacion_id,
                comercio_id=prod_data.get('comercio_id')
            )
            db.session.add(nuevo)
            procesados += 1
        
    if procesados > 0:
        m = Movimiento(descripcion=f"Carga masiva: se procesaron {procesados} productos.", tipo="carga_masiva", cantidad=procesados)
        db.session.add(m)
    
    db.session.commit()
    return jsonify({'mensaje': f'{procesados} productos procesados correctamente.'}), 201


@inventario_bp.route('/api/productos/<int:id_producto>/stock', methods=['PATCH'])
def actualizar_stock(id_producto):
    data = request.get_json()
    if not data or 'stock_actual' not in data:
        return jsonify({'error': 'Se requiere el campo stock_actual'}), 400
        
    producto = db.get_or_404(Producto, id_producto)
    diff = float(data['stock_actual']) - producto.stock_actual
    
    if abs(diff) > 0.001:
        accion = "Se agregaron" if diff > 0 else "Se descontaron"
        m = Movimiento(descripcion=f"{accion} {abs(diff)} {producto.unidad_medida} de {producto.nombre}", producto_id=producto.id, tipo="ajuste_stock", cantidad=diff)
        db.session.add(m)
        
    producto.stock_actual = float(data['stock_actual'])
    alerta_enviada = False
    
    if producto.es_temporal and producto.stock_actual <= 0:
        db.session.delete(producto)
        db.session.commit()
        return jsonify({'mensaje': 'Producto temporal consumido y eliminado', 'alerta_enviada': False})
    
    if producto.stock_actual <= producto.stock_minimo and not producto.en_lista:
        producto.en_lista = True
        ubi_str = producto.rel_ubicacion.nombre if producto.rel_ubicacion else "Sin asignar"
        comercio_nombre = producto.rel_comercio.nombre if producto.rel_comercio else "Sin Comercio"
        mensaje = (
            f"⚠️ <b>Alerta de Stock Bajo</b>\n\n"
            f"El producto <b>{producto.nombre}</b> ({ubi_str})\n"
            f"ha bajado a {producto.stock_actual} unidad(es).\n\n"
            f"🛒 <i>Se ha añadido automáticamente a la lista ({comercio_nombre}).</i>"
        )
        enviar_al_grupo(mensaje)
        alerta_enviada = True
                
    db.session.commit()
    return jsonify({
        'mensaje': 'Stock actualizado',
        'producto': producto.to_dict(),
        'alerta_enviada': alerta_enviada
    })


@inventario_bp.route('/api/productos/<int:id_producto>/lista', methods=['PATCH'])
def actualizar_estado_lista(id_producto):
    data = request.get_json()
    if not data or 'en_lista' not in data:
        return jsonify({'error': 'Se requiere el campo en_lista'}), 400
    producto = db.get_or_404(Producto, id_producto)
    producto.en_lista = data['en_lista']
    db.session.commit()
    return jsonify({'mensaje': 'Estado en la lista actualizado', 'producto': producto.to_dict()})


@inventario_bp.route('/api/compras/bulk', methods=['POST'])
def crear_compras_bulk():
    data = request.get_json()
    if not data or 'sub_ubicacion_id' not in data or 'productos' not in data:
        return jsonify({'error': 'Faltan datos (sub_ubicacion_id o productos)'}), 400
        
    sub_ubicacion_id = data['sub_ubicacion_id']
    ubicacion_id = data.get('ubicacion_id')
    productos_lista = data['productos']
    
    if not productos_lista:
        return jsonify({'error': 'La lista de productos está vacía'}), 400
        
    procesados = 0
    for prod_data in productos_lista:
        nuevo_prod = Producto(
            nombre=prod_data['nombre'].strip(),
            comercio_id=prod_data.get('comercio_id'),
            stock_actual=0.0,
            stock_minimo=float(prod_data.get('cantidad', 1)),
            unidad_medida=prod_data.get('unidad_medida', 'unidades'),
            ubicacion_id=ubicacion_id,
            sub_ubicacion_id=sub_ubicacion_id,
            en_lista=True
        )
        db.session.add(nuevo_prod)
        procesados += 1
        
    m = Movimiento(descripcion=f"Carga rápida de compras: se añadieron {procesados} productos a la lista de compras.", tipo="carga_rapida", cantidad=procesados)
    db.session.add(m)
    db.session.commit()
    return jsonify({'mensaje': f'{procesados} productos añadidos a compras.'}), 201


@inventario_bp.route('/api/compras/bulk-comprar', methods=['POST'])
def bulk_comprar():
    data = request.json
    if not data or 'productos' not in data:
        return jsonify({'error': 'Falta la lista de productos'}), 400
        
    ids = data['productos']
    productos = Producto.query.filter(Producto.id.in_(ids)).all()
    
    procesados = 0
    eliminados = 0
    for p in productos:
        if p.es_temporal:
            db.session.delete(p)
            eliminados += 1
        else:
            p.en_lista = False
            procesados += 1
            
    db.session.commit()
    return jsonify({'mensaje': f'Se removieron {procesados} productos de la lista y se eliminaron {eliminados} temporales.'})


@inventario_bp.route('/api/producto/consumir_rapido/<int:id_producto>', methods=['POST'])
def consumir_rapido(id_producto):
    producto = db.get_or_404(Producto, id_producto)
    if producto.stock_actual > 0:
        producto.stock_actual -= 1
        m = Movimiento(descripcion=f"Consumo rápido: se descontó 1 {producto.nombre}", producto_id=producto.id, tipo="consumo", cantidad=-1)
        db.session.add(m)
        
        if producto.es_temporal and producto.stock_actual <= 0:
            db.session.delete(producto)
            db.session.commit()
            return jsonify({'mensaje': 'Producto temporal consumido y eliminado'})
            
        if producto.stock_actual <= producto.stock_minimo and not producto.en_lista:
            producto.en_lista = True
            ubi_str = producto.rel_ubicacion.nombre if producto.rel_ubicacion else "Sin asignar"
            comercio_nombre = producto.rel_comercio.nombre if producto.rel_comercio else "Sin Comercio"
            mensaje = (
                f"⚠️ <b>Alerta de Stock Bajo</b>\n\n"
                f"El producto <b>{producto.nombre}</b> ({ubi_str})\n"
                f"ha bajado a {producto.stock_actual} unidad(es).\n\n"
                f"🛒 <i>Se ha añadido automáticamente a la lista ({comercio_nombre}).</i>"
            )
            enviar_al_grupo(mensaje)
                    
        db.session.commit()
        return jsonify({'mensaje': 'Consumo rápido exitoso'})
    return jsonify({'error': 'Stock ya en 0'}), 400


@inventario_bp.route('/api/telegram/enviar_lista', methods=['POST'])
def enviar_lista():
    if not bot or not CHAT_ID:
        return jsonify({'error': 'Telegram no configurado'}), 500
    data = request.get_json(silent=True) or {}
    comercio = data.get('comercio')
    try:
        enviar_listas_agrupadas(CHAT_ID, comercio)
        return jsonify({'mensaje': 'Listas enviadas con éxito'})
    except Exception as e:
        print(f"Error Telegram: {e}")
        return jsonify({'error': 'Error enviando mensaje'}), 500


