
    let calendar;

    document.addEventListener("DOMContentLoaded", function() {
        fetch('/api/usuarios').then(r => r.json()).then(users => {
            let select = document.getElementById('ev-asignado');
            users.forEach(u => {
                let opt = document.createElement('option');
                opt.value = u.id;
                opt.textContent = u.username;
                select.appendChild(opt);
            });
        });
        var calendarEl = document.getElementById('calendar');
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: 'es',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            dateClick: function(info) {
                // Pre-fill the start date
                document.getElementById('ev-inicio').value = info.dateStr + 'T12:00';
                abrirModalEvento();
            },
            eventClick: function(info) {
                editarEventoLogistico(info.event);
            },
            events: '/api/logistica/eventos',
            themeSystem: 'standard',
            height: 'auto',
            eventColor: 'var(--primary-color)',
            eventsSet: function(events) {
                // Update Agenda List
                const lista = document.getElementById('agenda-lista');
                lista.innerHTML = '';
                
                // Sort events by start date
                const sortedEvents = events.sort((a, b) => a.start - b.start);
                
                if (sortedEvents.length === 0) {
                    lista.innerHTML = '<li>No hay eventos en esta vista.</li>';
                    return;
                }
                
                sortedEvents.slice(0, 7).forEach(ev => {
                    const li = document.createElement('li');
                    li.style.padding = '8px 0';
                    li.style.borderBottom = '1px solid var(--border-color)';
                    
                    const dateStr = ev.start.toLocaleDateString('es-AR', {day: '2-digit', month: '2-digit'});
                    const timeStr = ev.start.toLocaleTimeString('es-AR', {hour: '2-digit', minute:'2-digit'});
                    
                    li.style.display = 'flex';
                    li.style.justifyContent = 'space-between';
                    li.style.alignItems = 'center';
                    const props = ev.extendedProps || {};
                    li.innerHTML = `<div><strong>${dateStr} ${timeStr}</strong> - ${escapeHTML(ev.title)}</div> <button class="btn-secundario" style="padding: 2px 8px; font-size: 0.8em;" onclick='editarEventoLogistico(${JSON.stringify({id: ev.id, title: ev.title, raw_title: props.raw_title, start: ev.start, end: ev.end, frecuencia: props.frecuencia, asignado_id: props.asignado_id})})'>✏️ Editar</button>`;
                    lista.appendChild(li);
                });
            }
        });
        calendar.render();

        document.getElementById('form-evento').addEventListener('submit', function(e) {
            e.preventDefault();
            guardarEvento();
        });
    });

    function abrirModalEvento() {
        document.getElementById('ev-id').value = '';
        document.querySelector('#modal-evento h2').innerText = "Nuevo Evento";
        const btnDel = document.getElementById('ev-btn-del');
        if (btnDel) btnDel.style.display = 'none';
        document.getElementById('modal-evento').style.display = 'block';
    }

    function cerrarModalEvento() {
        document.getElementById('modal-evento').style.display = 'none';
        document.getElementById('form-evento').reset();
        document.getElementById('ev-id').value = '';
    }

    function editarEventoLogistico(event) {
        const props = event.extendedProps || event || {};
        document.getElementById('ev-id').value = event.id || '';
        document.getElementById('ev-titulo').value = props.raw_title || event.title || '';
        document.querySelector('#modal-evento h2').innerText = event.id ? "Editar Evento" : "Nuevo Evento";
        const btnDel = document.getElementById('ev-btn-del');
        if (btnDel) btnDel.style.display = event.id ? 'inline-block' : 'none';
        
        if (event.start) {
            const d = new Date(event.start);
            const pad = n => n < 10 ? '0' + n : n;
            document.getElementById('ev-inicio').value = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        }
        if (event.end) {
            const d = new Date(event.end);
            const pad = n => n < 10 ? '0' + n : n;
            document.getElementById('ev-fin').value = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        } else {
            document.getElementById('ev-fin').value = '';
        }
        
        if (document.getElementById('ev-frecuencia')) {
            document.getElementById('ev-frecuencia').value = props.frecuencia || 'none';
        }
        if (document.getElementById('ev-asignado')) {
            document.getElementById('ev-asignado').value = props.asignado_id || '';
        }
        
        document.getElementById('modal-evento').style.display = 'block';
    }

    async function eliminarEventoLogistico() {
        const id = document.getElementById('ev-id').value;
        if (!id) return;
        if (await CustomDialog.confirm("¿Seguro que deseas eliminar este evento?")) {
            fetch('/api/logistica/eventos/' + id, { method: 'DELETE' })
            .then(r => r.json())
            .then(res => {
                showToast('Evento eliminado', 'success');
                cerrarModalEvento();
                calendar.refetchEvents();
            })
            .catch(err => showToast('Error de red', 'error'));
        }
    }

    function guardarEvento() {
        const id = document.getElementById('ev-id').value;
        const titulo = document.getElementById('ev-titulo').value;
        const inicio = document.getElementById('ev-inicio').value;
        const fin = document.getElementById('ev-fin').value;
        const frecuencia = document.getElementById('ev-frecuencia').value;
        const asignado_id = document.getElementById('ev-asignado').value;

        if (!titulo || !inicio) {
            showToast('Faltan campos obligatorios', 'error');
            return;
        }

        const data = {
            title: titulo,
            start: inicio,
            end: fin ? fin : null,
            frecuencia: frecuencia,
            asignado_id: asignado_id ? parseInt(asignado_id) : null
        };

        const url = id ? '/api/logistica/eventos/' + id : '/api/logistica/eventos';
        const method = id ? 'PUT' : 'POST';

        fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(result => {
            if (result.success || result.id) {
                showToast(id ? 'Evento actualizado' : 'Evento creado exitosamente', 'success');
                cerrarModalEvento();
                calendar.refetchEvents();
            } else {
                showToast(result.error || 'Error guardando evento', 'error');
            }
        })
        .catch(err => {
            console.error(err);
            showToast('Error de red', 'error');
        });
    }


