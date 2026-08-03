// ==========================================
// 1. DASHBOARD
// ==========================================
async function initDashboard() {
    await fetchDashboardStats();
    await fetchMovimientos();
    await fetchQuickActions();
}

async function fetchDashboardStats() {
    try {
        const response = await fetch('/api/dashboard_stats');
        const data = await response.json();
         // Render Alertas
        const dashAlertas = document.getElementById('dash-alertas-lista');
        /*
        const dashCriticas = document.getElementById('dash-alertas-criticas');
        
        if (dashCriticas) {
            dashCriticas.innerHTML = '';
            const criticas = data.alertas_stock.filter(p => p.stock_actual <= 0);
            if (criticas.length === 0) {
                dashCriticas.innerHTML = `<p style="color: var(--success-color); width: 100%; text-align: center;">Todo en orden. No hay productos agotados.</p>`;
            } else {
                criticas.forEach(p => {
                    const div = document.createElement('div');
                    div.style = "background: rgba(255,107,107,0.1); border: 1px solid var(--danger-color); padding: 6px 12px; border-radius: 6px; flex: 0 0 200px; scroll-snap-align: start; display: flex; justify-content: space-between; align-items: center;";
                    div.innerHTML = `
                        <div style="font-size: 0.9rem;">
                            <strong>${p.nombre}</strong><br>
                            <small>${p.comercio}</small>
                        </div>
                        <button class="btn-sm btn-carrito" onclick="forzarAlCarrito(${p.id})">🛒 Añadir</button>
                    `;
                    dashCriticas.appendChild(div);
                });
                
                // Limpiar intervalo anterior si existe para evitar duplicados al recargar
                if (window.critCarouselInterval) clearInterval(window.critCarouselInterval);
                
                // Auto-scroll logic
                window.critCarouselInterval = setInterval(() => {
                    const maxScroll = dashCriticas.scrollWidth - dashCriticas.clientWidth;
                    if (maxScroll > 0) {
                        if (dashCriticas.scrollLeft >= maxScroll - 5) {
                            dashCriticas.scrollTo({ left: 0, behavior: 'smooth' }); // Volver al inicio
                        } else {
                            dashCriticas.scrollBy({ left: 210, behavior: 'smooth' }); // Avanzar una tarjeta
                        }
                    }
                }, 4000); // Mover cada 4 segundos
            }
        }
        */

        if(dashAlertas) {
            dashAlertas.innerHTML = '';
            const repoList = data.alertas_stock.filter(p => p.stock_actual > 0);
            if (repoList.length === 0) {
                dashAlertas.innerHTML = `<p style="text-align: center; color: var(--text-secondary); margin-top: 2rem;">Todo en orden 👍</p>`;
            } else {
                repoList.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'dash-item';
                    div.innerHTML = `
                        <div>
                            <div class="dash-item-title">${p.nombre}</div>
                            <div class="dash-item-desc text-danger">Stock: ${p.stock_actual} (Mín: ${p.stock_minimo}) - 🏬 ${p.comercio}</div>
                        </div>
                    `;
                    dashAlertas.appendChild(div);
                });
            }
        }
        
        // Render Por Vencer
        const dashPorVencer = document.getElementById('dash-por-vencer');
        if (dashPorVencer) {
            dashPorVencer.innerHTML = '';
            if (!data.por_vencer || data.por_vencer.length === 0) {
                dashPorVencer.innerHTML = `<p style="text-align: center; color: var(--success-color); margin-top: 2rem;">No hay productos por vencer 👍</p>`;
            } else {
                data.por_vencer.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'dash-item';
                    div.innerHTML = `
                        <div>
                            <div class="dash-item-title">${p.nombre}</div>
                            <div class="dash-item-desc text-danger">Vence: ${p.fecha_vencimiento}</div>
                        </div>
                    `;
                    dashPorVencer.appendChild(div);
                });
            }
        }
        
        // Render Inactivos
        const dashInactivos = document.getElementById('dash-inactivos');
        if (dashInactivos) {
            dashInactivos.innerHTML = '';
            if (!data.inactivos || data.inactivos.length === 0) {
                dashInactivos.innerHTML = `<p style="text-align: center; color: var(--success-color); margin-top: 2rem;">No hay productos inactivos 👍</p>`;
            } else {
                data.inactivos.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'dash-item';
                    div.innerHTML = `
                        <div>
                            <div class="dash-item-title">${p.nombre}</div>
                            <div class="dash-item-desc" style="color: var(--text-secondary);">Última compra: ${p.fecha_ultima_compra}</div>
                        </div>
                    `;
                    dashInactivos.appendChild(div);
                });
            }
        }
        
        // Render Mapa Compras
        const dashMapa = document.getElementById('dash-mapa-compras');
        if(dashMapa) {
            dashMapa.innerHTML = '';
            if (data.compras_por_comercio.length === 0) {
                dashMapa.innerHTML = `<p style="text-align: center; color: var(--text-secondary); margin-top: 2rem; grid-column: 1 / -1;">No hay compras pendientes</p>`;
            } else {
                data.compras_por_comercio.forEach(c => {
                    const div = document.createElement('div');
                    div.className = 'comercio-card';
                    div.style.cursor = 'pointer';
                    div.dataset.comercio = c.comercio;
                    div.innerHTML = `
                        <div class="comercio-card-title">${c.comercio}</div>
                        <div class="comercio-card-count">${c.cantidad}</div>
                    `;
                    div.addEventListener('click', () => {
                        document.querySelectorAll('.comercio-card').forEach(el => el.classList.remove('active'));
                        div.classList.add('active');
                        
                        document.querySelectorAll('.board-column').forEach(col => {
                            col.style.display = (col.dataset.comercio === c.comercio) ? 'block' : 'none';
                        });
                        
                        const btnMostrarTodo = document.getElementById('btnMostrarTodo');
                        if(btnMostrarTodo) btnMostrarTodo.style.display = 'inline-block';
                    });
                    dashMapa.appendChild(div);
                });
            }
        }
    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
    }
}

async function fetchMovimientos(query = '') {
    try {
        const url = query ? `/api/dashboard/movimientos?q=${encodeURIComponent(query)}` : '/api/dashboard/movimientos';
        const response = await fetch(url);
        const data = await response.json();
        const ul = document.getElementById('feedMovimientos');
        if (!ul) return;
        
        if (data.length === 0) {
            ul.innerHTML = `<li style="padding: 10px 0; text-align: center; color: var(--text-secondary);">No hay movimientos</li>`;
            return;
        }
        
        ul.innerHTML = data.map(m => `
            <li style="padding: 10px 0; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between;">
                <span>${m.descripcion}</span>
                <span style="font-size: 0.8rem; color: #888;">${m.fecha}</span>
            </li>
        `).join('');
    } catch (error) {
        console.error('Error fetching movimientos:', error);
    }
}

async function fetchQuickActions() {
    try {
        const response = await fetch('/api/productos');
        const data = await response.json();
        const container = document.getElementById('quickActions');
        if (!container) return;
        
        // Take top 4 items with most stock
        const topProducts = data.filter(p => p.stock_actual > 0).sort((a, b) => b.stock_actual - a.stock_actual).slice(0, 4);
        
        if (topProducts.length === 0) {
            container.innerHTML = `<span style="color:#888;">No hay productos con stock.</span>`;
            return;
        }
        
        container.innerHTML = topProducts.map(p => `
            <button class="btn-secundario" style="flex: 1; min-width: 120px;" onclick="consumirRapido(${p.id})">
                -1 ${p.nombre}
            </button>
        `).join('');
    } catch (error) {
        console.error('Error fetching quick actions:', error);
    }
}

async function consumirRapido(id) {
    try {
        const response = await fetch(`/api/producto/consumir_rapido/${id}`, { method: 'POST' });
        if (response.ok) {
            initDashboard(); // Reload dashboard components
        } else {
            const err = await response.json();
            alert(err.error || 'Error al consumir');
        }
    } catch (error) {
        console.error('Error in consumirRapido:', error);
    }
}




function procesarTicketDash() {
    const fileInput = document.getElementById('dash-ticket-file');
    if (!fileInput.files || fileInput.files.length === 0) return;

    const file = fileInput.files[0];
    const reader = new FileReader();

    const modal = document.getElementById('modal-dash-ticket');
    const loading = document.getElementById('dash-ticket-loading');
    const form = document.getElementById('dash-ticket-form');
    
    modal.style.display = 'block';
    loading.style.display = 'block';
    form.style.display = 'none';

    reader.onload = function(e) {
        const base64Image = e.target.result.split(',')[1];
        
        fetch('/api/finanzas/ocr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_base64: base64Image })
        })
        .then(res => res.json())
        .then(data => {
            loading.style.display = 'none';
            if(data.error) {
                showToast(data.error, "error");
                modal.style.display = 'none';
            } else {
                form.style.display = 'block';
                document.getElementById('dash-gasto-concepto').value = data.descripcion || '';
                document.getElementById('dash-gasto-monto').value = data.monto_total || '';
            }
        })
        .catch(err => {
            console.error(err);
            loading.style.display = 'none';
            modal.style.display = 'none';
            showToast("Error procesando imagen", "error");
        });
    };
    reader.readAsDataURL(file);
    fileInput.value = ''; // Reset
}

function guardarGastoDash() {
    const descripcion = document.getElementById('dash-gasto-concepto').value;
    const monto = document.getElementById('dash-gasto-monto').value;
    
    if (!descripcion || !monto) {
        showToast("Completa concepto y monto", "error");
        return;
    }
    
    fetch('/api/finanzas/gasto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            descripcion: descripcion,
            monto_total: monto
        })
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            showToast("Gasto guardado exitosamente", "success");
            document.getElementById('modal-dash-ticket').style.display = 'none';
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast(data.error || "Error", "error");
        }
    })
    .catch(err => {
        console.error(err);
        showToast("Error de red", "error");
    });
}



document.addEventListener("DOMContentLoaded", function() {
    var calendarEl = document.getElementById('global-calendar');
    if (calendarEl) {
        var calendar = new FullCalendar.Calendar(calendarEl, {
            locale: 'es',
            initialView: 'dayGridMonth',
            height: 'auto',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,listWeek'
            },
            eventSources: [
                {
                    url: '/api/calendario_tareas',
                    color: '#0d6efd', // Blue
                    textColor: 'white'
                },
                {
                    url: '/api/menus/eventos',
                    color: '#fd7e14', // Orange
                    textColor: 'white'
                },
                {
                    url: '/api/logistica/eventos',
                    color: '#6f42c1', // Purple
                    textColor: 'white'
                }
            ],
            eventClick: function(info) {
                if (info.event.extendedProps && info.event.extendedProps.tarea_id) {
                    info.jsEvent.preventDefault();
                    if (typeof abrirModalEdicionTareaCal === 'function') {
                        abrirModalEdicionTareaCal(info);
                    }
                } else if (info.event.url) {
                    info.jsEvent.preventDefault();
                    window.open(info.event.url);
                }
            }
        });
        calendar.render();
    }
});


