from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models.database import db, Mascota, Producto, Tarea, EventoLogistico, ModeloTarea
from datetime import datetime
import pytz

mascotas_bp = Blueprint('mascotas', __name__)

@mascotas_bp.route('/mascotas', methods=['GET'])
@login_required
def mascotas_page():
    if not current_user.casa_activa_id:
        return render_template('views/mascotas.html', active_page='mascotas', mascotas=[], inventario=[], tareas=[], logistica=[])
        
    mascotas = Mascota.query.all()
    
    inventario = Producto.query.filter(
        (Producto.nombre.ilike('%mascota%')) |
        (Producto.nombre.ilike('%alimento%')) |
        (Producto.nombre.ilike('%perro%')) |
        (Producto.nombre.ilike('%gato%')) |
        (Producto.nombre.ilike('%pipeta%')) |
        (Producto.nombre.ilike('%accesorio%'))
    ).all()
    
    tareas = Tarea.query.join(ModeloTarea).filter(
        (ModeloTarea.nombre.ilike('%paseo%')) |
        (ModeloTarea.nombre.ilike('%comida%')) |
        (ModeloTarea.nombre.ilike('%baño%')) |
        (ModeloTarea.nombre.ilike('%bano%'))
    ).all()
    
    logistica = EventoLogistico.query.filter(
        (EventoLogistico.titulo.ilike('%veterinari%')) |
        (EventoLogistico.titulo.ilike('%vacuna%')) |
        (EventoLogistico.titulo.ilike('%desparasitaci%'))
    ).order_by(EventoLogistico.fecha_inicio.asc()).all()

    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(tz).date()
    for m in mascotas:
        if m.fecha_nacimiento:
            dias = (hoy - m.fecha_nacimiento).days
            anos = dias // 365
            meses = (dias % 365) // 30
            m.edad_str = f"{anos} años, {meses} meses" if anos > 0 else f"{meses} meses"
        else:
            m.edad_str = "Edad desconocida"

    return render_template('views/mascotas.html', 
                          active_page='mascotas',
                          mascotas=mascotas,
                          inventario=inventario,
                          tareas=tareas,
                          logistica=logistica)
