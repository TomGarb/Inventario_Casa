from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user, login_user, logout_user
from extensions import db
from models.database import Usuario, Gasto, DetalleGasto, DivisionGasto, Producto, Ubicacion, SubUbicacion, Sala, Comercio, Movimiento, Tarea, ModeloTarea, HistorialTarea, SaltoTarea, EventoLogistico, Receta, IngredienteReceta, MenuSemanal, HorarioComidas
from datetime import datetime, date, timedelta
from sqlalchemy import extract
import json
import logging
from utils import calcular_balances_globales

finanzas_bp = Blueprint('finanzas', __name__)

@finanzas_bp.route('/finanzas')
@login_required
def finanzas_page():
    return render_template('views/finanzas.html', active_page='finanzas')


@finanzas_bp.route('/api/finanzas/ocr', methods=['POST'])
@login_required
def finanzas_ocr():
    try:
        data = request.json
        if not data or 'image_base64' not in data:
            return jsonify({'error': 'No se proporcionó imagen'}), 400
        
        image_base64 = data['image_base64']
        
        # Si tiene un header tipo data:image/jpeg;base64,... se lo quitamos
        if ',' in image_base64:
            image_base64 = image_base64.split(',', 1)[1]

        if not GEMINI_API_KEY:
            return jsonify({'error': 'Gemini API key no configurada'}), 500
            
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            image_bytes = base64.b64decode(image_base64)
            imagen_gemini = genai.types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')
            
            prompt = "Eres un asistente contable. Analiza este ticket/factura y devuelve EXCLUSIVAMENTE un JSON con tres claves: 'descripcion' (resumen de la compra en 3-4 palabras), 'monto_total' (número float, el total final pagado), e 'items' (lista de productos si es legible). No uses markdown ni texto adicional."
            
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[prompt, imagen_gemini]
            )
            
            resultado_str = response.text.strip()
            # Limpiar backticks por si la IA devuelve markdown
            if resultado_str.startswith('```json'):
                resultado_str = resultado_str.replace('```json', '').replace('```', '').strip()
            elif resultado_str.startswith('```'):
                resultado_str = resultado_str.replace('```', '').strip()
                
            resultado = json.loads(resultado_str)
            return jsonify(resultado), 200
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@finanzas_bp.route('/api/finanzas/gasto', methods=['POST'])
@login_required
def agregar_gasto_api():
    try:
        data = request.json
        descripcion = data.get('descripcion')
        monto_total = float(data.get('monto_total', 0))
        deudores_ids = data.get('deudores_ids', [])
        if not deudores_ids:
            todos_usuarios = Usuario.query.all()
            deudores_ids = [u.id for u in todos_usuarios]

        items = data.get('items', [])

        if items:
            monto_calculado = sum(float(i.get('cantidad', 1)) * float(i.get('precio', 0)) for i in items)
            if monto_calculado > 0:
                monto_total = monto_calculado

        if not descripcion or monto_total <= 0:
            return jsonify({'success': False, 'error': 'Faltan datos obligatorios o monto inválido.'}), 400

        nuevo_gasto = Gasto(
            usuario_id=current_user.id,
            monto=monto_total,
            descripcion=descripcion,
            fecha=datetime.now()
        )
        db.session.add(nuevo_gasto)
        db.session.flush()

        if items:
            for item in items:
                det = DetalleGasto(
                    gasto_id=nuevo_gasto.id,
                    descripcion=item.get('descripcion', 'Sin descripción'),
                    cantidad=float(item.get('cantidad', 1)),
                    precio_unitario=float(item.get('precio', 0))
                )
                db.session.add(det)

        monto_por_persona = monto_total / len(deudores_ids)

        for u_id_str in deudores_ids:
            u_id = int(u_id_str)
            esta_pagado = (u_id == current_user.id)
            div = DivisionGasto(
                gasto_id=nuevo_gasto.id,
                usuario_id=u_id,
                monto_adeudado=monto_por_persona,
                esta_pagado=esta_pagado
            )
            db.session.add(div)

        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Gasto registrado correctamente.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@finanzas_bp.route('/api/finanzas/gastos', methods=['GET'])
@login_required
def obtener_gastos_api():
    try:
        gastos = Gasto.query.order_by(Gasto.fecha.desc(), Gasto.id.desc()).all()
        res = []
        for g in gastos:
            detalles = []
            for d in g.detalles:
                detalles.append({
                    'descripcion': d.descripcion,
                    'cantidad': d.cantidad,
                    'precio_unitario': d.precio_unitario,
                    'subtotal': d.cantidad * d.precio_unitario
                })
            res.append({
                'id': g.id,
                'fecha': g.fecha.strftime('%Y-%m-%d'),
                'descripcion': g.descripcion,
                'pagador': g.pagador.username if g.pagador else 'Desconocido',
                'monto': g.monto,
                'detalles': detalles
            })
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@finanzas_bp.route('/api/finanzas/gasto/<int:gasto_id>', methods=['DELETE'])
@login_required
def eliminar_gasto_api(gasto_id):
    try:
        gasto = db.session.get(Gasto, gasto_id)
        if not gasto:
            return jsonify({'success': False, 'error': 'Gasto no encontrado'}), 404
        
        db.session.delete(gasto)
        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Gasto eliminado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@finanzas_bp.route('/api/finanzas/gasto/<int:gasto_id>', methods=['PUT'])
@login_required
def editar_gasto_api(gasto_id):
    try:
        gasto = db.session.get(Gasto, gasto_id)
        if not gasto:
            return jsonify({'success': False, 'error': 'Gasto no encontrado'}), 404

        data = request.json
        descripcion = data.get('descripcion')
        monto_total = float(data.get('monto_total', 0))
        deudores_ids = data.get('deudores_ids', [])
        if not deudores_ids:
            todos_usuarios = Usuario.query.all()
            deudores_ids = [u.id for u in todos_usuarios]

        items = data.get('items', [])
        if items:
            monto_calculado = sum(float(i.get('cantidad', 1)) * float(i.get('precio', 0)) for i in items)
            if monto_calculado > 0:
                monto_total = monto_calculado

        if not descripcion or monto_total <= 0:
            return jsonify({'success': False, 'error': 'Faltan datos obligatorios o monto inválido.'}), 400

        # Update base Gasto
        gasto.descripcion = descripcion
        gasto.monto = monto_total

        # Clear existing relations
        DetalleGasto.query.filter_by(gasto_id=gasto_id).delete()
        DivisionGasto.query.filter_by(gasto_id=gasto_id).delete()
        db.session.flush()

        # Add new DetalleGasto
        if items:
            for item in items:
                det = DetalleGasto(
                    gasto_id=gasto.id,
                    descripcion=item.get('descripcion', 'Sin descripción'),
                    cantidad=float(item.get('cantidad', 1)),
                    precio_unitario=float(item.get('precio', 0))
                )
                db.session.add(det)

        # Add new DivisionGasto
        monto_por_persona = monto_total / len(deudores_ids)
        for u_id_str in deudores_ids:
            u_id = int(u_id_str)
            esta_pagado = (u_id == gasto.usuario_id)
            div = DivisionGasto(
                gasto_id=gasto.id,
                usuario_id=u_id,
                monto_adeudado=monto_por_persona,
                esta_pagado=esta_pagado
            )
            db.session.add(div)

        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Gasto actualizado correctamente.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@finanzas_bp.route('/api/finanzas/balances', methods=['GET'])
@login_required
def finanzas_balances():
    try:
        balances = calcular_balances_globales()
        return jsonify(balances), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@finanzas_bp.route('/api/finanzas/exportar', methods=['GET'])
@login_required
def exportar_finanzas():
    try:
        import io
        import csv
        from flask import Response
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeceras
        writer.writerow(['ID_Gasto', 'Fecha', 'Concepto', 'Monto_Total', 'ID_Deudor', 'Nombre_Deudor', 'ID_Comprador', 'Nombre_Comprador', 'Monto_Adeudado', 'Esta_Pagado'])
        
        divisiones = DivisionGasto.query.join(Gasto).order_by(Gasto.fecha.desc()).all()
        for div in divisiones:
            gasto = div.rel_gasto
            comprador = db.session.get(Usuario, gasto.usuario_id)
            deudor = db.session.get(Usuario, div.usuario_id)
            
            writer.writerow([
                gasto.id,
                gasto.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                gasto.descripcion,
                gasto.monto,
                deudor.id if deudor else '',
                deudor.username if deudor else 'Desconocido',
                comprador.id if comprador else '',
                comprador.username if comprador else 'Desconocido',
                div.monto_adeudado,
                'Sí' if div.esta_pagado else 'No'
            ])
            
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=finanzas_homestock.csv"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


