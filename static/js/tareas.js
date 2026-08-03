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





let calendar;
let selectedDate = new Date();
selectedDate.setHours(0,0,0,0);

function isSameDay(d1, d2) {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
}

document.addEventListener('DOMContentLoaded', async () => {
    // Wait for initial load if necessary, but actually we can just init fullcalendar
    const calendarEl = document.getElementById('calendar');
    calendar = new FullCalendar.Calendar(calendarEl, {
        height: 'auto',
        contentHeight: 450,
        initialView: 'dayGridMonth',
        locale: 'es',
        dayHeaderFormat: { weekday: 'long' },
        events: '/api/calendario_tareas',
        selectable: true,
        dateClick: function(info) {
            // Check if clicking inside addBtn
            if (info.jsEvent.target.classList.contains('add-task-btn')) {
                openModal('modal-crear-tarea');
                document.getElementById('tipo-frecuencia').value = 'fecha_fija';
                updateValorInput();
                document.getElementById('valor-fecha-fija').value = info.dateStr;
                return;
            }
            // Update selected date and reload table
            const [yyyy, mm, dd] = info.dateStr.split('-');
            selectedDate = new Date(yyyy, mm - 1, dd);
            
            let lbl = info.dateStr;
            const hoy = new Date(); hoy.setHours(0,0,0,0);
            if (isSameDay(selectedDate, hoy)) lbl = 'Hoy';
            
            document.getElementById('lbl-fecha-seleccionada').innerText = lbl;
            loadTareas();
        },
        dayCellContent: function(e) {
            let wrapper = document.createElement('div');
            wrapper.style.display = 'flex';
            wrapper.style.justifyContent = 'space-between';
            wrapper.style.width = '100%';
            
            let addBtn = document.createElement('div');
            addBtn.innerHTML = '+';
            addBtn.className = 'add-task-btn';
            addBtn.style.cursor = 'pointer';
            addBtn.style.fontWeight = 'bold';
            addBtn.style.color = 'var(--primary-color)';
            addBtn.style.padding = '0 5px';
            
            let dayNum = document.createElement('span');
            dayNum.innerText = e.dayNumberText;
            
            wrapper.appendChild(addBtn);
            wrapper.appendChild(dayNum);
            
            return { domNodes: [wrapper] };
        },
        eventClick: function(info) {
            if (typeof abrirModalEdicionTareaCal === 'function') {
                abrirModalEdicionTareaCal(info);
            }
        }
    });
    calendar.render();
});

function openSkipModal(tareaId, nombreTarea) {
    document.getElementById('delegar-tarea-id').value = tareaId;
    document.getElementById('modal-delegar-title').innerText = "Delegar: " + nombreTarea;
    document.getElementById('delegar-motivo').value = "";
    document.getElementById('modal-delegar').style.display = 'block';
}

function closeSkipModal() {
    document.getElementById('modal-delegar').style.display = 'none';
}

let allUsers = [];

async function init() {
    await fetchUsuarios();
    await loadModelos(); loadTareas();
}

async function fetchUsuarios() {
    try {
        const response = await fetch('/api/usuarios');
        if (response.ok) {
            allUsers = await response.json();
        }
    } catch (e) {
        console.error("Error obteniendo usuarios", e);
    }
}


function selectAllUsers() {
    const checkboxes = document.querySelectorAll('.usuario-chk');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

function renderUsuariosCheckboxes(selectedIds = []) {
    const container = document.getElementById('usuarios-checkboxes');
    container.innerHTML = '';
    
    if (allUsers.length === 0) {
        container.innerHTML = '<span style="color: var(--danger-color); font-size: 0.9rem;">(No hay usuarios registrados. La lista de compras o tareas no podrá ser asignada).</span>';
        return;
    }

    allUsers.forEach(u => {
        const div = document.createElement('div');
        div.style.display = 'flex';
        div.style.alignItems = 'center';
        div.style.gap = '10px';
        
        const isChecked = selectedIds.includes(u.id) ? 'checked' : '';
        div.innerHTML = `
            <input type="checkbox" id="user_${u.id}" class="usuario-chk" value="${u.id}" ${isChecked}>
            <label for="user_${u.id}" style="margin: 0; cursor: pointer;">${u.username}</label>
        `;
        container.appendChild(div);
    });
}

function switchTab(tab) {
    if (tab === 'calendario') {
        document.getElementById('view-calendario').style.display = 'flex';
        document.getElementById('view-modelos').style.display = 'none';
        
        document.getElementById('tab-calendario').classList.add('active');
        document.getElementById('tab-modelos').classList.remove('active');
        
        if (calendar) {
            setTimeout(() => {
                calendar.updateSize();
                calendar.render();
            }, 10);
        }
    } else {
        document.getElementById('view-calendario').style.display = 'none';
        document.getElementById('view-modelos').style.display = 'block';
        
        document.getElementById('tab-modelos').classList.add('active');
        document.getElementById('tab-calendario').classList.remove('active');
        
        loadModelos();
    }
}

async function loadModelos() {
    try {
        const response = await fetch('/api/modelos');
        const modelos = await response.json();
        const tbody = document.getElementById('modelos-tbody');
        tbody.innerHTML = '';
        
        if (modelos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px;">No hay plantillas configuradas.</td></tr>';
            return;
        }
        
        modelos.forEach(m => {
            const tr = document.createElement('tr');
            const asignados = m.usuarios.map(u => u.username).join(', ') || '<em style="color:#aaa;">Sin asignar</em>';
            
            tr.innerHTML = `
                <td style="padding: 10px;">${m.id}</td>
                <td style="padding: 10px;"><b>${m.nombre}</b></td>
                <td style="padding: 10px;">
                    <span style="font-size: 0.8em; padding: 2px 6px; border-radius: 4px; color: white; background-color: ${m.prioridad === 'Urgente' ? 'var(--danger-color)' : m.prioridad === 'Secundaria' ? 'var(--text-secondary)' : 'var(--primary-color)'};">
                        ${m.prioridad || 'Esencial'}
                    </span>
                </td>
                <td style="padding: 10px;">
                    ${m.tipo_frecuencia === 'dias' ? 'Cada ' + m.valor_frecuencia + ' día(s)' : ''}
                    ${m.tipo_frecuencia === 'dia_semana' ? 'Día ' + m.valor_frecuencia : ''}
                    ${m.tipo_frecuencia === 'mes' ? 'Mensual (' + m.valor_frecuencia + ')' : ''}
                    ${m.tipo_frecuencia === 'fecha_fija' ? 'Fija: ' + m.valor_frecuencia : ''}
                </td>
                <td style="padding: 10px;">${asignados}</td>
                <td style="padding: 10px;">
                    <button class="btn-secundario" onclick='editModelo(${JSON.stringify(m).replace(/'/g, "&#39;")})' title="Editar Modelo">✏️</button>
                    <button class="btn-delete-sm" onclick="deleteModelo(${m.id})" title="Eliminar Modelo">🗑️</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Error al cargar los modelos", e);
    }
}

function deleteModelo(id) {
    showConfirm("¿Seguro que deseas eliminar esta plantilla? (Las tareas generadas en el calendario no se borrarán)", async () => {
        try {
            const response = await fetch(`/api/modelos/${id}`, { method: 'DELETE' });
            if(response.ok) {
                showToast("Plantilla eliminada", 'success');
                loadModelos();
            } else {
                showToast("Error eliminando modelo.", 'error');
            }
        } catch(err) {
            showToast("Error de red.", 'error');
        }
    });
}

function editModelo(m) {
    document.getElementById('tarea-id').value = m.id;
    document.getElementById('modal-title').innerText = "Editar Modelo";
    
    document.getElementById('tarea-nombre').value = m.nombre;
    if (m.prioridad) document.getElementById('tarea-prioridad').value = m.prioridad;
    document.getElementById('tarea-alternar').checked = m.alternar !== false;
    
    if (m.tipo_frecuencia) {
        document.getElementById('tipo-frecuencia').value = m.tipo_frecuencia;
        updateValorInput();
        if (m.tipo_frecuencia === 'dias') document.getElementById('valor-dias').value = m.valor_frecuencia;
        if (m.tipo_frecuencia === 'dia_semana') document.getElementById('valor-dia-semana').value = m.valor_frecuencia;
        if (m.tipo_frecuencia === 'mes') document.getElementById('valor-mes').value = m.valor_frecuencia;
        if (m.tipo_frecuencia === 'fecha_fija') document.getElementById('valor-fecha-fija').value = m.valor_frecuencia;
    }
    
    renderUsuariosCheckboxes(m.usuarios.map(u => u.id));
    openModal('modal-crear-tarea');
}

function generarMes() {
    showConfirm("¿Deseas generar todas las tareas del mes actual en el calendario?", async () => {
        try {
            const response = await fetch('/api/generar_mes', { method: 'POST' });
            const data = await response.json();
            showToast(data.mensaje, 'success');
            loadModelos(); loadTareas();
            if (calendar) calendar.refetchEvents();
        } catch(err) {
            showToast("Error al generar el mes.", 'error');
        }
    });
}

async function completarTarea() {
    const id = document.getElementById('delegar-tarea-id').value;
    if(!id) return;
    
    closeSkipModal();
    showToast("Completando tarea...", "info");
    
    try {
        const response = await fetch(`/api/tareas/${id}/completar`, { method: 'POST' });
        if(response.ok) {
            showToast("Tarea marcada como completada", "success");
            loadModelos(); loadTareas();
            if (calendar) calendar.refetchEvents();
        } else {
            showToast("Error completando la tarea.", "error");
        }
    } catch(err) {
        showToast("Error de red.", "error");
    }
}

// Override original loadTareas so it just loads instances
async function loadTareas() {
    try {
        const response = await fetch('/api/tareas');
        const tareas = await response.json();
        const tbody = document.getElementById('tareas-tbody');
        tbody.innerHTML = '';
        
        const tareasDelDia = tareas.filter(t => {
            if (!t.fecha_programada) return false;
            const hoy = new Date();
            hoy.setHours(0,0,0,0);
            const [yyyy, mm, dd] = t.fecha_programada.split('-');
            const prox = new Date(yyyy, mm - 1, dd);
            
            // Mostrar si es para hoy, o si ya venció y no está completada
            return (prox.getTime() === hoy.getTime()) || (prox < hoy && !t.completada);
        });

        if (tareasDelDia.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">No hay tareas para hoy.</td></tr>';
            return;
        }
        
        tareasDelDia.forEach(t => {
            const tr = document.createElement('tr');
            const asignados = t.usuarios.map(u => u.username).join(', ') || '<em style="color:#aaa;">Sin asignar</em>';
            
            let fecha_str = "N/A";
            if(t.fecha_programada) {
                const hoy = new Date();
                hoy.setHours(0,0,0,0);
                const [yyyy, mm, dd] = t.fecha_programada.split('-');
                const prox = new Date(yyyy, mm - 1, dd);
                
                if (prox < hoy && !t.completada) {
                    fecha_str = `<span style="color: var(--danger-color); font-weight: bold;">${t.fecha_programada} (Vencida)</span>`;
                } else if (prox.getTime() === hoy.getTime() && !t.completada) {
                    fecha_str = `<span style="color: var(--warning-color); font-weight: bold;">Hoy</span>`;
                } else {
                    fecha_str = t.fecha_programada;
                }
            }
            
            let status = t.completada ? '<span style="color:var(--success-color)">✅ Lista</span>' : '<span style="color:var(--warning-color)">⏳ Pdt</span>';
            
            tr.innerHTML = `
                <td style="padding: 10px;">${t.id}</td>
                <td style="padding: 10px;"><b>${escapeHTML(t.nombre)}</b> <br><small>${status}</small></td>
                <td style="padding: 10px;">
                    <span style="font-size: 0.8em; padding: 2px 6px; border-radius: 4px; color: white; background-color: ${t.prioridad === 'Urgente' ? 'var(--danger-color)' : t.prioridad === 'Secundaria' ? 'var(--text-secondary)' : 'var(--primary-color)'};">
                        ${t.prioridad || 'Esencial'}
                    </span>
                </td>
                <td style="padding: 10px;">Fija</td>
                <td style="padding: 10px;">${fecha_str}</td>
                <td style="padding: 10px;">${asignados}</td>
                <td style="padding: 10px;">
                    <button class="btn-secundario" onclick="openSkipModal(${t.id}, '${escapeHTML(t.nombre)}')" title="Acciones">🚀</button>
                    <button class="btn-delete-sm" onclick="deleteTarea(${t.id})" title="Eliminar">🗑️</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Error al cargar las tareas activas", e);
    }
}


/* OLD LOADTAREAS DISABLED */
async function oldLoadTareas() {
    try {
        const response = await fetch('/api/tareas');
        const tareas = await response.json();
        const tbody = document.getElementById('tareas-tbody');
        tbody.innerHTML = '';
        
        if (tareas.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">No hay tareas configuradas.</td></tr>';
            return;
        }
        
        tareas.forEach(t => {
            const tr = document.createElement('tr');
            const asignados = t.usuarios.map(u => u.username).join(', ') || '<em style="color:#aaa;">Sin asignar</em>';
            
            let fecha_str = "N/A";
            if(t.proxima_fecha_calculada) {
                const hoy = new Date();
                hoy.setHours(0,0,0,0);
                // Convert YYYY-MM-DD to Date object avoiding timezone offset issues
                const [yyyy, mm, dd] = t.proxima_fecha_calculada.split('-');
                const prox = new Date(yyyy, mm - 1, dd);
                
                if (prox < hoy) {
                    fecha_str = `<span style="color: var(--danger-color); font-weight: bold;">${t.proxima_fecha_calculada} (Vencida)</span>`;
                } else if (prox.getTime() === hoy.getTime()) {
                    fecha_str = `<span style="color: var(--warning-color); font-weight: bold;">Hoy</span>`;
                } else {
                    fecha_str = t.proxima_fecha_calculada;
                }
            }
            
            tr.innerHTML = `
                <td style="padding: 10px;">${t.id}</td>
                <td style="padding: 10px;"><b>${escapeHTML(t.nombre)}</b></td>
                <td style="padding: 10px;">
                    <span style="font-size: 0.8em; padding: 2px 6px; border-radius: 4px; color: white; background-color: ${t.prioridad === 'Urgente' ? 'var(--danger-color)' : t.prioridad === 'Secundaria' ? 'var(--text-secondary)' : 'var(--primary-color)'};">
                        ${t.prioridad || 'Esencial'}
                    </span>
                </td>
                <td style="padding: 10px;">
                    ${t.tipo_frecuencia === 'dias' ? 'Cada ' + t.valor_frecuencia + ' día(s)' : ''}
                    ${t.tipo_frecuencia === 'dia_semana' ? 'Día ' + t.valor_frecuencia : ''}
                    ${t.tipo_frecuencia === 'mes' ? 'Mensual (' + t.valor_frecuencia + ')' : ''}
                    ${t.tipo_frecuencia === 'fecha_fija' ? 'Fija: ' + t.valor_frecuencia : ''}
                </td>
                <td style="padding: 10px;">${fecha_str}</td>
                <td style="padding: 10px; font-size: 0.9em;">${asignados}</td>
                <td style="padding: 10px; display: flex; gap: 5px;">
                    <button class="btn-primary" onclick='editTarea(${JSON.stringify(t).replace(/'/g, "&apos;")})'>✏️ Editar</button>
                    <button class="btn-delete-sm" onclick="deleteTarea(${t.id})">🗑️ Borrar</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Error al cargar las tareas", e);
    }
}

function openModal(id) {
    document.getElementById(id).style.display = 'block';
    if(id === 'modal-crear-tarea' && !document.getElementById('tarea-id').value) {
        document.getElementById('modal-title').innerText = "Crear Nueva Tarea";
        renderUsuariosCheckboxes();
    }
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
    document.getElementById('form-tarea').reset();
    document.getElementById('tarea-id').value = '';
}

function editTarea(tarea) {
    document.getElementById('tarea-id').value = tarea.id;
    document.getElementById('tarea-nombre').value = tarea.nombre;
    if (tarea.prioridad) document.getElementById('tarea-prioridad').value = tarea.prioridad;
    document.getElementById('tarea-alternar').checked = tarea.alternar !== false; // true by default
    if (tarea.tipo_frecuencia) {
        document.getElementById('tipo-frecuencia').value = tarea.tipo_frecuencia;
        updateValorInput();
        if (tarea.tipo_frecuencia === 'dias') document.getElementById('valor-dias').value = tarea.valor_frecuencia;
        else if (tarea.tipo_frecuencia === 'dia_semana') document.getElementById('valor-dia-semana').value = tarea.valor_frecuencia;
        else if (tarea.tipo_frecuencia === 'mes') document.getElementById('valor-mes').value = tarea.valor_frecuencia;
        else if (tarea.tipo_frecuencia === 'fecha_fija') document.getElementById('valor-fecha-fija').value = tarea.valor_frecuencia;
    }
    document.getElementById('modal-title').innerText = "Editar Tarea";
    
    const assignedIds = tarea.usuarios.map(u => u.id);
    renderUsuariosCheckboxes(assignedIds);
    
    openModal('modal-crear-tarea');
}

document.getElementById('form-tarea').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('tarea-id').value;
    const nombre = document.getElementById('tarea-nombre').value;
    const tipo_frecuencia = document.getElementById('tipo-frecuencia').value;
    let valor_frecuencia = '1';
    let fecha_inicio = null;
    if (tipo_frecuencia === 'dias') valor_frecuencia = document.getElementById('valor-dias').value;
    else if (tipo_frecuencia === 'dia_semana') valor_frecuencia = document.getElementById('valor-dia-semana').value;
    else if (tipo_frecuencia === 'mes') valor_frecuencia = document.getElementById('valor-mes').value;
    else if (tipo_frecuencia === 'fecha_fija') {
        valor_frecuencia = document.getElementById('valor-fecha-fija').value;
        fecha_inicio = valor_frecuencia;
    }
    
    const checkboxes = document.querySelectorAll('.usuario-chk:checked');
    const usuarios_ids = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/modelos/${id}` : '/api/modelos';
    
    const prioridad = document.getElementById('tarea-prioridad').value;
    const alternar = document.getElementById('tarea-alternar').checked;
    const payload = { nombre, tipo_frecuencia, valor_frecuencia, usuarios_ids, prioridad, alternar };
    if (fecha_inicio && !id) {
        payload.fecha_inicio = fecha_inicio; // set initial run date to yesterday so it triggers today
    }
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            closeModal('modal-crear-tarea');
            loadModelos(); loadTareas();
            if (calendar) { calendar.refetchEvents(); }
        } else {
            const data = await response.json();
            alert("Error: " + (data.error || "Desconocido"));
        }
    } catch(err) {
        alert("Error de red.");
    }
});

function deleteTarea(id) {
    showConfirm("¿Seguro que deseas eliminar esta tarea? Esto borrará también el historial.", async () => {
        try {
            const response = await fetch(`/api/tareas/${id}`, { method: 'DELETE' });
            if(response.ok) {
                showToast("Tarea eliminada", 'success');
                loadModelos(); loadTareas();
                if (calendar) calendar.refetchEvents();
            } else {
                showToast("Error eliminando la tarea.", 'error');
            }
        } catch(err) {
            showToast("Error de red.", 'error');
        }
    });
}


document.getElementById('form-delegar').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('delegar-tarea-id').value;
    const motivo = document.getElementById('delegar-motivo').value;
    
    closeSkipModal();
    showToast("Delegando turno...", "info");
    
    try {
        const response = await fetch(`/api/tareas/${id}/skip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ motivo })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.mensaje + ". Nuevo encargado: " + data.nuevo_encargado, "success");
            calendar.refetchEvents();
            loadModelos(); loadTareas();
        } else {
            showToast("Error: " + (data.error || "Desconocido"), "error");
        }
    } catch(err) {
        showToast("Error de red.", "error");
    }
});

document.addEventListener('DOMContentLoaded', init);

function updateValorInput() {
    const tipo = document.getElementById('tipo-frecuencia').value;
    document.getElementById('valor-dias').style.display = 'none';
    document.getElementById('valor-dia-semana').style.display = 'none';
    document.getElementById('valor-mes').style.display = 'none';
    document.getElementById('valor-fecha-fija').style.display = 'none';
    
    document.getElementById('valor-dias').required = false;
    document.getElementById('valor-dia-semana').required = false;
    document.getElementById('valor-mes').required = false;
    document.getElementById('valor-fecha-fija').required = false;
    
    if (tipo === 'dias') {
        document.getElementById('valor-dias').style.display = 'block';
        document.getElementById('valor-dias').required = true;
    } else if (tipo === 'dia_semana') {
        document.getElementById('valor-dia-semana').style.display = 'block';
        document.getElementById('valor-dia-semana').required = true;
    } else if (tipo === 'mes') {
        document.getElementById('valor-mes').style.display = 'block';
        document.getElementById('valor-mes').required = true;
    } else if (tipo === 'fecha_fija') {
        document.getElementById('valor-fecha-fija').style.display = 'block';
        document.getElementById('valor-fecha-fija').required = true;
    }
}


