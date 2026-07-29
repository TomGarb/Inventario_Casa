# -*- coding: utf-8 -*-
import os
import re

def update_app_py():
    path = 't:/Proyectos/Inventario_Casa/app.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update editar_tarea_instancia
    old_put = """@app.route('/api/tareas/<int:id_tarea>', methods=['PUT'])
@login_required
def editar_tarea_instancia(id_tarea):
    data = request.json
    tarea = db.get_or_404(Tarea, id_tarea)
    if 'nombre' in data and data['nombre']:
        tarea.nombre = data['nombre']
    if 'prioridad' in data and data['prioridad']:
        tarea.prioridad = data['prioridad']
    if 'fecha_inicio' in data or 'valor_frecuencia' in data or 'fecha' in data:
        f_str = data.get('fecha_inicio') or data.get('valor_frecuencia') or data.get('fecha')
        if f_str:
            try:
                tarea.fecha_programada = datetime.strptime(str(f_str)[:10], "%Y-%m-%d").date()
            except:
                pass
    if tarea.modelo_id:
        mod = db.session.get(ModeloTarea, tarea.modelo_id)
        if mod:
            if 'nombre' in data and data['nombre']: mod.nombre = data['nombre']
            if 'prioridad' in data and data['prioridad']: mod.prioridad = data['prioridad']
    db.session.commit()
    return jsonify(tarea.to_dict()), 200"""

    new_put = """@app.route('/api/tareas/<int:id_tarea>', methods=['PUT'])
@login_required
def editar_tarea_instancia(id_tarea):
    data = request.json
    tarea = db.get_or_404(Tarea, id_tarea)
    if 'nombre' in data and data['nombre']:
        tarea.nombre = data['nombre']
    if 'prioridad' in data and data['prioridad']:
        tarea.prioridad = data['prioridad']
    if 'estado' in data:
        tarea.completada = (data['estado'] == 'completada' or data['estado'] is True)
    if 'completada' in data:
        tarea.completada = bool(data['completada'])
    
    # Manejo de fecha programada
    f_str = data.get('fecha') or data.get('fecha_programada') or data.get('fecha_inicio')
    if f_str:
        try:
            tarea.fecha_programada = datetime.strptime(str(f_str)[:10], "%Y-%m-%d").date()
        except Exception:
            pass

    if 'tipo_frecuencia' in data and data['tipo_frecuencia']:
        tarea.tipo_frecuencia = data['tipo_frecuencia']
    if 'valor_frecuencia' in data and data['valor_frecuencia']:
        tarea.valor_frecuencia = str(data['valor_frecuencia'])

    if tarea.modelo_id:
        mod = db.session.get(ModeloTarea, tarea.modelo_id)
        if mod:
            if 'nombre' in data and data['nombre']: mod.nombre = data['nombre']
            if 'prioridad' in data and data['prioridad']: mod.prioridad = data['prioridad']
            if 'tipo_frecuencia' in data and data['tipo_frecuencia']: mod.tipo_frecuencia = data['tipo_frecuencia']
            if 'valor_frecuencia' in data and data['valor_frecuencia']: mod.valor_frecuencia = str(data['valor_frecuencia'])
    db.session.commit()
    return jsonify(tarea.to_dict()), 200"""

    if old_put in content:
        content = content.replace(old_put, new_put)
        print("Updated editar_tarea_instancia in app.py")
    else:
        # Check if already updated or try regex/partial
        if "f_str = data.get('fecha') or data.get('fecha_programada')" not in content:
            print("WARNING: Could not exact match old_put in app.py, attempting pattern replacement...")
            # We can replace the function using regex
            pattern = r"@app\.route\('/api/tareas/<int:id_tarea>', methods=\['PUT'\]\)\s*@login_required\s*def editar_tarea_instancia\(id_tarea\):.*?return jsonify\(tarea\.to_dict\(\)\), 200"
            content = re.sub(pattern, new_put, content, flags=re.DOTALL)
            print("Regex updated editar_tarea_instancia in app.py")

    # 2. Update calendario_tareas
    old_cal = """        eventos.append({
            'title': f"{prioridad_emoji} {t.nombre} ({label_asignados})",
            'start': proxima.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'tarea_id': t.id,
                'usuario_asignado': user_id,
                'nombre_tarea': t.nombre,
                'tipo_frecuencia': t.tipo_frecuencia,
                'valor_frecuencia': t.valor_frecuencia,
                'completada': getattr(t, 'completada', False)
            }
        })"""

    new_cal = """        eventos.append({
            'id': t.id,
            'title': f"{prioridad_emoji} {t.nombre} ({label_asignados})",
            'start': proxima.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'tarea_id': t.id,
                'usuario_asignado': user_id,
                'nombre_tarea': t.nombre,
                'tipo_frecuencia': t.tipo_frecuencia,
                'valor_frecuencia': t.valor_frecuencia,
                'fecha_programada': proxima.isoformat()[:10],
                'completada': getattr(t, 'completada', False)
            }
        })"""

    if old_cal in content:
        content = content.replace(old_cal, new_cal)
        print("Updated calendario_tareas in app.py")
    elif "fecha_programada': proxima.isoformat()[:10]" not in content:
        print("WARNING: Could not exact match old_cal in app.py")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def update_modals_html():
    path = 't:/Proyectos/Inventario_Casa/templates/components/modals.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    modal_html = """
<!-- Modal: Editar/Eliminar Tarea en Calendario -->
<div id="modal-tarea-calendario" class="modal oculto" style="display: none; position: fixed; z-index: 10000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.7); backdrop-filter: blur(4px);">
    <div class="modal-content" style="background-color: #212529; margin: 10% auto; padding: 20px; border: 1px solid var(--border-color); width: 90%; max-width: 500px; border-radius: 8px;">
        <h3 id="modal-tarea-cal-title" style="margin-bottom: 15px; color: var(--text-color);">Editar Tarea de Calendario</h3>
        <input type="hidden" id="modal-tarea-cal-id">
        <div class="form-group" style="margin-bottom: 15px;">
            <label style="color: var(--text-muted); display: block; margin-bottom: 5px;">Título (Nombre de la tarea):</label>
            <input type="text" id="modal-tarea-cal-nombre" class="form-control" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--border-color); background: var(--bg-darker); color: var(--text-color);" required>
        </div>
        <div class="form-group-row" style="display: flex; gap: 10px; margin-bottom: 15px;">
            <div class="form-group" style="flex: 1;">
                <label style="color: var(--text-muted); display: block; margin-bottom: 5px;">Fecha programada:</label>
                <input type="date" id="modal-tarea-cal-fecha" class="form-control" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--border-color); background: var(--bg-darker); color: var(--text-color);">
            </div>
            <div class="form-group" style="flex: 1;">
                <label style="color: var(--text-muted); display: block; margin-bottom: 5px;">Frecuencia (Tipo):</label>
                <select id="modal-tarea-cal-frec-tipo" class="form-control" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--border-color); background: var(--bg-darker); color: var(--text-color);">
                    <option value="">-- Única / Sin cambiar --</option>
                    <option value="dias">Días</option>
                    <option value="semanas">Semanas</option>
                    <option value="meses">Meses</option>
                </select>
            </div>
            <div class="form-group" style="width: 100px;">
                <label style="color: var(--text-muted); display: block; margin-bottom: 5px;">Cada:</label>
                <input type="number" id="modal-tarea-cal-frec-val" class="form-control" min="1" placeholder="Ej: 1" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid var(--border-color); background: var(--bg-darker); color: var(--text-color);">
            </div>
        </div>
        <div class="modal-actions" style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; margin-top: 20px;">
            <div style="display: flex; gap: 10px;">
                <button type="button" id="btn-delete-tarea-cal" class="btn-delete-sm" style="background: #dc3545; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer;">Eliminar Tarea 🗑️</button>
                <button type="button" id="btn-skip-tarea-cal" class="btn-secundario" style="background: #ffc107; color: #000; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-weight: bold;">Saltear (Skip)</button>
            </div>
            <div style="display: flex; gap: 10px;">
                <button type="button" id="btn-cancel-tarea-cal" class="btn-secundario" style="padding: 8px 12px; border-radius: 4px; cursor: pointer;">Cancelar</button>
                <button type="button" id="btn-save-tarea-cal" class="btn-primary" style="padding: 8px 12px; border-radius: 4px; cursor: pointer;">Guardar Cambios</button>
            </div>
        </div>
    </div>
</div>
"""

    if "id=\"modal-tarea-calendario\"" not in content:
        content = content.rstrip() + "\n" + modal_html + "\n"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Added modal-tarea-calendario to modals.html")
    else:
        print("modal-tarea-calendario already present in modals.html")

def update_tareas_html():
    path = 't:/Proyectos/Inventario_Casa/templates/views/tareas.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_click = """        eventClick: function(info) {
            const props = info.event.extendedProps;
            if (props.usuario_asignado === CURRENT_USER_ID) {
                openSkipModal(props.tarea_id, props.nombre_tarea);
            } else {
                alert("Esta tarea le toca a otro usuario. (Puedes verla pero no delegarla)");
            }
        }"""

    new_click = """        eventClick: function(info) {
            if (typeof abrirModalEdicionTareaCal === 'function') {
                abrirModalEdicionTareaCal(info);
            }
        }"""

    if old_click in content:
        content = content.replace(old_click, new_click)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Updated eventClick in tareas.html")
    elif "abrirModalEdicionTareaCal(info)" not in content:
        print("WARNING: Could not exact match eventClick in tareas.html, attempting regex...")
        pattern = r"eventClick:\s*function\(info\)\s*\{[^}]*alert\([^}]*\}\s*\}"
        content = re.sub(pattern, new_click, content)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Regex updated eventClick in tareas.html")

def update_dashboard_html():
    path = 't:/Proyectos/Inventario_Casa/templates/views/dashboard.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    old_click = """            eventClick: function(info) {
                // Previene navegacion si es link pero aca abrimos los modals si existieran
                if (info.event.url) {
                    info.jsEvent.preventDefault();
                    window.open(info.event.url);
                }
            }"""

    new_click = """            eventClick: function(info) {
                if (info.event.extendedProps && info.event.extendedProps.tarea_id) {
                    info.jsEvent.preventDefault();
                    if (typeof abrirModalEdicionTareaCal === 'function') {
                        abrirModalEdicionTareaCal(info);
                    }
                } else if (info.event.url) {
                    info.jsEvent.preventDefault();
                    window.open(info.event.url);
                }
            }"""

    if old_click in content:
        content = content.replace(old_click, new_click)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Updated eventClick in dashboard.html")
    elif "abrirModalEdicionTareaCal(info)" not in content:
        print("WARNING: Could not exact match eventClick in dashboard.html")

def update_main_js():
    path = 't:/Proyectos/Inventario_Casa/static/js/main.js'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Replace updateStock and updateStockBtn
    old_stock = """async function updateStock(id, newStock) {
    if (newStock < 0) return;
    try {
        const response = await fetch(`/api/productos/${id}/stock`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stock_actual: newStock })
        });
        if (response.ok) fetchProductsInventario();
    } catch (error) { console.error('Error:', error); }
}

window.updateStockBtn = function(e, id, op, currentStock, unidad) {
    e.stopPropagation();
    let diff = 1.0;
    if (unidad !== 'unidades') {
        const input = window.prompt(`Cunto deseas ${op === 'add' ? 'sumar' : 'restar'}? (ej. 0.1, 0.5, 1)`, "0.5");
        if (input === null) return; // Cancelado
        diff = parseFloat(input.replace(',', '.'));
        if (isNaN(diff) || diff <= 0) {
            alert("Cantidad invlida");
            return;
        }
    }

    let newVal = op === 'add' ? currentStock + diff : currentStock - diff;
    if (newVal < 0) newVal = 0.0;

    updateStock(id, newVal);
};"""

    # Handle accents or encoding in prompt text if any
    pattern_stock = r"async function updateStock\(id, newStock\)\s*\{.*?window\.updateStockBtn = function\(e, id, op, currentStock, unidad\)\s*\{.*?\};\s*\}"

    new_stock = """async function updateStock(id, newStock) {
    if (newStock < 0) return;
    try {
        const response = await fetch(`/api/productos/${id}/stock`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stock_actual: newStock })
        });
        if (response.ok) fetchProductsInventario();
    } catch (error) { console.error('Error:', error); }
}

window.updateStockBtn = async function(e, id, op, currentStock, unidad, btnElem) {
    if (e) e.stopPropagation();
    let diff = 1.0;
    if (unidad === 'kg' || unidad === 'L') {
        diff = 0.5;
    }

    let newVal = op === 'add' ? currentStock + diff : currentStock - diff;
    if (newVal < 0) newVal = 0.0;
    newVal = Math.round(newVal * 100) / 100;

    let spanElem = null;
    if (btnElem && btnElem.parentElement) {
        spanElem = btnElem.parentElement.querySelector('.s-val');
    }

    const oldSpanText = spanElem ? spanElem.innerText : '';
    if (spanElem) {
        spanElem.innerText = `${newVal} ${unidad !== 'unidades' ? unidad : ''}`;
    }

    try {
        const response = await fetch(`/api/productos/${id}/stock`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stock_actual: newVal })
        });
        if (response.ok) {
            if (btnElem && btnElem.parentElement) {
                const subBtn = btnElem.parentElement.querySelector('button:first-child');
                const addBtn = btnElem.parentElement.querySelector('button:last-child');
                if (subBtn) subBtn.setAttribute('onclick', `window.updateStockBtn(event, ${id}, 'sub', ${newVal}, '${unidad}', this)`);
                if (addBtn) addBtn.setAttribute('onclick', `window.updateStockBtn(event, ${id}, 'add', ${newVal}, '${unidad}', this)`);
            }
            fetchProductsInventario();
        } else {
            if (spanElem) spanElem.innerText = oldSpanText;
            showStockErrorUI(btnElem, "Error al actualizar stock");
        }
    } catch (error) {
        console.error('Error:', error);
        if (spanElem) spanElem.innerText = oldSpanText;
        showStockErrorUI(btnElem, "Error de red al actualizar stock");
    }
};

function showStockErrorUI(btnElem, msg) {
    if (btnElem) {
        const oldBg = btnElem.style.backgroundColor;
        btnElem.style.backgroundColor = '#dc3545';
        btnElem.style.color = '#fff';
        setTimeout(() => {
            btnElem.style.backgroundColor = oldBg;
            btnElem.style.color = '';
        }, 1500);
    }
    const container = document.getElementById('alert-container') || document.body;
    const toast = document.createElement('div');
    toast.className = 'flash-msg flash-error';
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '99999';
    toast.style.padding = '10px 15px';
    toast.style.background = '#dc3545';
    toast.style.color = '#fff';
    toast.style.borderRadius = '5px';
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}"""

    if "window.prompt(" in content or "window.updateStockBtn = function(e, id, op, currentStock, unidad) {" in content:
        content = re.sub(pattern_stock, new_stock, content, flags=re.DOTALL)
        print("Updated updateStockBtn without native alerts in main.js")

    # 2. Append modal task editing functions if not present
    if "abrirModalEdicionTareaCal" not in content:
        js_add = """

// ==========================================
// MODAL EDICIÓN/ELIMINACIÓN DE TAREAS EN CALENDARIO
// ==========================================
window.abrirModalEdicionTareaCal = function(info) {
    const props = info.event.extendedProps || {};
    const tareaId = props.tarea_id || info.event.id;
    if (!tareaId) return;

    const modal = document.getElementById('modal-tarea-calendario');
    if (!modal) return;

    document.getElementById('modal-tarea-cal-id').value = tareaId;
    document.getElementById('modal-tarea-cal-nombre').value = props.nombre_tarea || info.event.title || '';
    
    let fechaStr = '';
    if (props.fecha_programada) {
        fechaStr = props.fecha_programada.substring(0, 10);
    } else if (info.event.startStr) {
        fechaStr = info.event.startStr.substring(0, 10);
    } else if (info.event.start) {
        fechaStr = info.event.start.toISOString().substring(0, 10);
    }
    document.getElementById('modal-tarea-cal-fecha').value = fechaStr;
    document.getElementById('modal-tarea-cal-frec-tipo').value = props.tipo_frecuencia || '';
    document.getElementById('modal-tarea-cal-frec-val').value = props.valor_frecuencia || '';

    modal.classList.remove('oculto');
    modal.style.display = 'block';
};

document.addEventListener("DOMContentLoaded", function() {
    const modalTareaCal = document.getElementById('modal-tarea-calendario');
    if (modalTareaCal) {
        const btnCancel = document.getElementById('btn-cancel-tarea-cal');
        if (btnCancel) {
            btnCancel.onclick = function(e) {
                if (e) e.preventDefault();
                modalTareaCal.classList.add('oculto');
                modalTareaCal.style.display = 'none';
            };
        }

        const btnSave = document.getElementById('btn-save-tarea-cal');
        if (btnSave) {
            btnSave.onclick = async function(e) {
                if (e) e.preventDefault();
                const id = document.getElementById('modal-tarea-cal-id').value;
                if (!id) return;
                const nombre = document.getElementById('modal-tarea-cal-nombre').value;
                const fecha = document.getElementById('modal-tarea-cal-fecha').value;
                const frecTipo = document.getElementById('modal-tarea-cal-frec-tipo').value;
                const frecVal = document.getElementById('modal-tarea-cal-frec-val').value;

                const payload = {
                    nombre: nombre,
                    fecha: fecha
                };
                if (frecTipo) payload.tipo_frecuencia = frecTipo;
                if (frecVal) payload.valor_frecuencia = frecVal;

                try {
                    const res = await fetch(`/api/tareas/${id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    if (res.ok) {
                        modalTareaCal.classList.add('oculto');
                        modalTareaCal.style.display = 'none';
                        if (typeof calendar !== 'undefined' && calendar) calendar.refetchEvents();
                        if (typeof calendarMenus !== 'undefined' && calendarMenus) calendarMenus.refetchEvents();
                        if (typeof loadTareas === 'function') loadTareas();
                    } else {
                        showStockErrorUI(btnSave, "Error al guardar tarea");
                    }
                } catch (err) {
                    console.error("Error al guardar tarea:", err);
                    showStockErrorUI(btnSave, "Error de red");
                }
            };
        }

        const btnDelete = document.getElementById('btn-delete-tarea-cal');
        if (btnDelete) {
            btnDelete.onclick = async function(e) {
                if (e) e.preventDefault();
                const id = document.getElementById('modal-tarea-cal-id').value;
                if (!id) return;
                try {
                    const res = await fetch(`/api/tareas/${id}`, { method: 'DELETE' });
                    if (res.ok) {
                        modalTareaCal.classList.add('oculto');
                        modalTareaCal.style.display = 'none';
                        if (typeof calendar !== 'undefined' && calendar) calendar.refetchEvents();
                        if (typeof calendarMenus !== 'undefined' && calendarMenus) calendarMenus.refetchEvents();
                        if (typeof loadTareas === 'function') loadTareas();
                    } else {
                        showStockErrorUI(btnDelete, "Error al eliminar tarea");
                    }
                } catch (err) {
                    console.error("Error al eliminar tarea:", err);
                    showStockErrorUI(btnDelete, "Error de red");
                }
            };
        }

        const btnSkip = document.getElementById('btn-skip-tarea-cal');
        if (btnSkip) {
            btnSkip.onclick = async function(e) {
                if (e) e.preventDefault();
                const id = document.getElementById('modal-tarea-cal-id').value;
                const nombre = document.getElementById('modal-tarea-cal-nombre').value;
                modalTareaCal.classList.add('oculto');
                modalTareaCal.style.display = 'none';
                if (typeof openSkipModal === 'function') {
                    openSkipModal(id, nombre);
                } else {
                    try {
                        const res = await fetch(`/api/tareas/${id}/skip`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ motivo: "Salteada desde calendario" })
                        });
                        if (res.ok) {
                            if (typeof calendar !== 'undefined' && calendar) calendar.refetchEvents();
                            if (typeof loadTareas === 'function') loadTareas();
                        }
                    } catch (err) {
                        console.error("Error al saltear tarea:", err);
                    }
                }
            };
        }
    }
});
"""
        content = content.rstrip() + "\n" + js_add + "\n"
        print("Added modal task functions to main.js")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    update_app_py()
    update_modals_html()
    update_tareas_html()
    update_dashboard_html()
    update_main_js()
    print("ALL UI/UX IMPROVEMENTS APPLIED SUCCESSFULLY.")
