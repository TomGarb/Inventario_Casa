
    let calendarMenus;
    let horariosCargados = [];
    let editandoMenuId = null;
    let menuSeleccionadoId = null;
    let menuSeleccionadoData = null;

    document.addEventListener("DOMContentLoaded", function() {
        var calendarEl = document.getElementById('calendar-menus');
        calendarMenus = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: 'es',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            events: '/api/menus/eventos',
            themeSystem: 'standard',
            height: 'auto',
            eventClick: function(info) {
                const event = info.event;
                menuSeleccionadoId = event.id;
                menuSeleccionadoData = event.extendedProps;
                
                const props = event.extendedProps;
                const dateStr = event.start.toLocaleDateString('es-AR', {weekday: 'long', day: '2-digit', month: '2-digit'});
                
                document.getElementById('detalle-menu-info').innerHTML = `
                    <strong>Fecha:</strong> ${dateStr} <br>
                    <strong>Día:</strong> ${props.dia_semana} <br>
                    <strong>Tipo:</strong> ${props.tipo_comida} <br>
                    <strong>Comida:</strong> ${props.nombre}
                `;
                document.getElementById('modal-detalle-menu').style.display = 'block';
            },
            eventsSet: function(events) {
                const lista = document.getElementById('agenda-comidas');
                lista.innerHTML = '';
                
                const hoy = new Date();
                const diaSemana = hoy.getDay() === 0 ? 6 : hoy.getDay() - 1; // 0=Lunes
                const inicioSemana = new Date(hoy);
                inicioSemana.setDate(hoy.getDate() - diaSemana);
                inicioSemana.setHours(0,0,0,0);
                
                const finSemana = new Date(inicioSemana);
                finSemana.setDate(inicioSemana.getDate() + 6);
                finSemana.setHours(23,59,59,999);

                const eventosSemana = events.filter(ev => {
                    const d = ev.start;
                    return d >= inicioSemana && d <= finSemana;
                }).sort((a, b) => a.start - b.start);
                
                if (eventosSemana.length === 0) {
                    lista.innerHTML = '<li>No hay comidas en la semana actual.</li>';
                    return;
                }
                
                eventosSemana.forEach(ev => {
                    const li = document.createElement('li');
                    li.style.padding = '8px 0';
                    li.style.borderBottom = '1px solid var(--border-color)';
                    
                    const dateStr = ev.start.toLocaleDateString('es-AR', {weekday: 'short', day: '2-digit', month: '2-digit'});
                    
                    li.innerHTML = `<strong>${dateStr}</strong> - ${escapeHTML(ev.title)}`;
                    lista.appendChild(li);
                });
            }
        });
        calendarMenus.render();

        cargarHorarios();

        document.getElementById('form-horarios').addEventListener('submit', function(e) {
            e.preventDefault();
            guardarHorarios();
        });
    });

    
    
    function cerrarModalDetalleMenu() {
        document.getElementById('modal-detalle-menu').style.display = 'none';
        menuSeleccionadoId = null;
        menuSeleccionadoData = null;
    }

    function editarMenuSeleccionado() {
        if (!menuSeleccionadoId || !menuSeleccionadoData) return;
        
        // Cargar datos en el form
        editandoMenuId = menuSeleccionadoId;
        document.getElementById('manual-dia').value = menuSeleccionadoData.dia_semana;
        document.getElementById('manual-tipo').value = menuSeleccionadoData.tipo_comida;
        document.getElementById('manual-nombre').value = menuSeleccionadoData.nombre;
        
        // Permitir la opcion de 'todos los dias' al editar
        if(document.getElementById('manual-todos-dias')) {
            document.getElementById('manual-todos-dias').checked = false;
            document.getElementById('manual-todos-dias').disabled = false;
            document.getElementById('manual-dia').disabled = false;
        }

        cerrarModalDetalleMenu();
        document.getElementById('modal-comida-manual').style.display = 'block';
    }

    async function eliminarMenuSeleccionado() {
        if (!menuSeleccionadoId) return;
        if (!await CustomDialog.confirm('¿Seguro que deseas eliminar esta comida del planificador?')) return;

        fetch(`/api/menus/${menuSeleccionadoId}`, {
            method: 'DELETE'
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast(data.mensaje, "success");
                cerrarModalDetalleMenu();
                if (calendarMenus) calendarMenus.refetchEvents();
            } else {
                showToast(data.error || "Error", "error");
            }
        })
        .catch(err => {
            console.error(err);
            showToast("Error de red", "error");
        });
    }

    function abrirModalComidaManual() {
        editandoMenuId = null; // Ensure we are not in edit mode
        if(document.getElementById('manual-todos-dias')) {
            document.getElementById('manual-todos-dias').disabled = false;
        }
        document.getElementById('modal-comida-manual').style.display = 'block';
    }


    function cerrarModalComidaManual() {
        document.getElementById('modal-comida-manual').style.display = 'none';
        document.getElementById('form-comida-manual').reset();
        if(document.getElementById('manual-todos-dias')) {
            document.getElementById('manual-todos-dias').checked = false;
        }
        if(document.getElementById('manual-dia')) {
            document.getElementById('manual-dia').disabled = false;
        }
    }

    document.getElementById('form-comida-manual').addEventListener('submit', function(e) {
        e.preventDefault();
        const dia = document.getElementById('manual-dia').value;
        const tipo = document.getElementById('manual-tipo').value;
        const nombre = document.getElementById('manual-nombre').value;
        const todosDias = document.getElementById('manual-todos-dias') ? document.getElementById('manual-todos-dias').checked : false;

        const dias = todosDias ? ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"] : [dia];

        let promesas = [];
        if (editandoMenuId) {
            // Edit mode
            if (todosDias) {
                // PUT the current one to the FIRST day in the list, and POST the other 6
                promesas.push(
                    fetch(`/api/menus/${editandoMenuId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            dia_semana: dias[0],
                            tipo_comida: tipo,
                            nombre: nombre
                        })
                    }).then(res => res.json())
                );
                dias.slice(1).forEach(d => {
                    promesas.push(
                        fetch('/api/menus/manual', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                dia_semana: d,
                                tipo_comida: tipo,
                                nombre: nombre
                            })
                        }).then(res => res.json())
                    );
                });
            } else {
                // single day edit
                promesas.push(
                    fetch(`/api/menus/${editandoMenuId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            dia_semana: dia,
                            tipo_comida: tipo,
                            nombre: nombre
                        })
                    }).then(res => res.json())
                );
            }
        } else {
            // Create mode
            promesas = dias.map(d => {
                return fetch('/api/menus/manual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        dia_semana: d,
                        tipo_comida: tipo,
                        nombre: nombre
                    })
                }).then(res => res.json());
            });
        }

        Promise.all(promesas)
        .then(resultados => {
            const errores = resultados.filter(r => !r.success);
            if (errores.length > 0) {
                showToast("Hubo algunos errores al guardar: " + errores[0].error, "error");
            } else {
                showToast(todosDias ? "Comida añadida a todos los días exitosamente" : resultados[0].mensaje, "success");
            }
            cerrarModalComidaManual();
            if (calendarMenus) {
                calendarMenus.refetchEvents();
            }
        })
        .catch(err => {
            showToast("Error de red", "error");
            console.error(err);
        });
    });

    async function duplicarMenuSemanaPasada() {
        if(!await CustomDialog.confirm('¿Seguro que deseas copiar el menú de la semana anterior a la semana actual?')) return;
        
        fetch('/api/menus/semana/duplicar', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast(`Se duplicaron ${data.duplicados} comidas.`, 'success');
                calendarMenus.refetchEvents();
            } else {
                showToast(data.error || 'Error', 'error');
            }
        })
        .catch(err => {
            console.error(err);
            showToast('Error de red', 'error');
        });
    }

    function cargarHorarios() {
        fetch('/api/menus/horarios')
        .then(res => res.json())
        .then(data => {
            horariosCargados = data;
            const container = document.getElementById('horarios-list');
            container.innerHTML = '';
            data.forEach((h, index) => {
                container.innerHTML += `
                    <div class="form-group" style="border: 1px solid var(--border-color); padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                        <h4>${h.tipo_comida}</h4>
                        <div style="display: flex; gap: 10px;">
                            <div style="flex:1;">
                                <label>Inicio</label>
                                <input type="time" id="h-inicio-${index}" value="${h.hora_inicio}" required>
                            </div>
                            <div style="flex:1;">
                                <label>Fin</label>
                                <input type="time" id="h-fin-${index}" value="${h.hora_fin}" required>
                            </div>
                        </div>
                    </div>
                `;
            });
        });
    }

    function abrirModalHorarios() {
        document.getElementById('modal-horarios').style.display = 'block';
    }

    function cerrarModalHorarios() {
        document.getElementById('modal-horarios').style.display = 'none';
    }

    function guardarHorarios() {
        const data = horariosCargados.map((h, index) => {
            return {
                id: h.id,
                hora_inicio: document.getElementById(`h-inicio-${index}`).value,
                hora_fin: document.getElementById(`h-fin-${index}`).value
            };
        });

        fetch('/api/menus/horarios', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(result => {
            if (result.success) {
                showToast('Horarios guardados', 'success');
                cerrarModalHorarios();
                cargarHorarios();
            } else {
                showToast(result.error || 'Error guardando horarios', 'error');
            }
        });
    }


