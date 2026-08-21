import os

tv_code = r'''
document.addEventListener("DOMContentLoaded", () => {
    const token = document.querySelector('meta[name="tv-token"]').content;
    const weatherKey = document.querySelector('meta[name="weather-api-key"]').content;
    const weatherCity = document.querySelector('meta[name="weather-city"]').content;

    // Reloj
    function updateClock() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
        
        const opcionesFecha = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const dateString = now.toLocaleDateString('es-AR', opcionesFecha);
        
        document.getElementById('tv-clock').textContent = timeString;
        document.getElementById('tv-date').textContent = dateString.charAt(0).toUpperCase() + dateString.slice(1);
    }
    
    setInterval(updateClock, 1000);
    updateClock();

    // Fetch API Datos Internos
    async function fetchDashboardData() {
        try {
            const res = await fetch('/api/tv_data?token=' + token);
            if (!res.ok) throw new Error("Error en API");
            const data = await res.json();
            
            // Stock
            const stockContainer = document.getElementById('tv-stock-container');
            if (data.stock && data.stock.length > 0) {
                stockContainer.innerHTML = data.stock.map(p => 
                    '<div class="tv-item">' +
                        '<span>' + p.nombre + '</span>' +
                        '<span class="badge badge-danger">' + p.stock_actual + ' / ' + p.stock_minimo + '</span>' +
                    '</div>'
                ).join('');
            } else {
                stockContainer.innerHTML = '<div class="empty-state">Todo el stock esta en orden \u2705</div>';
            }

            // Tareas
            const tareasContainer = document.getElementById('tv-tareas-container');
            if (data.tareas && data.tareas.length > 0) {
                tareasContainer.innerHTML = data.tareas.map(t => {
                    let badge = t.vencida ? '<span class="badge badge-danger">Vencida</span>' 
                                          : '<span class="badge badge-warning">Hoy</span>';
                    return '<div class="tv-item">' +
                        '<span><strong>' + t.nombre + '</strong> <span style="font-size:1.2rem;color:var(--tv-text-muted)">(' + t.asignado + ')</span></span>' +
                        badge +
                    '</div>'
                }).join('');
            } else {
                tareasContainer.innerHTML = '<div class="empty-state">No hay tareas pendientes hoy \u2728</div>';
            }

            // Logistica
            const logisticaContainer = document.getElementById('tv-logistica-container');
            if (data.logistica && data.logistica.length > 0) {
                logisticaContainer.innerHTML = data.logistica.map(l => 
                    '<div class="tv-item">' +
                        '<span>' + l.titulo + '</span>' +
                        '<span class="badge badge-primary">' + l.hora + '</span>' +
                    '</div>'
                ).join('');
            } else {
                logisticaContainer.innerHTML = '<div class="empty-state">Sin eventos proximos</div>';
            }

            // Menus
            const menuContainer = document.getElementById('tv-menu-container');
            if (data.menus && data.menus.length > 0) {
                menuContainer.innerHTML = data.menus.map(m => 
                    '<div class="tv-item">' +
                        '<span style="text-transform:capitalize; color:var(--tv-text-muted)">' + m.tipo + ':</span>' +
                        '<span style="font-weight:bold">' + m.receta + '</span>' +
                    '</div>'
                ).join('');
            } else {
                menuContainer.innerHTML = '<div class="empty-state">Menu no asignado para hoy</div>';
            }

        } catch (error) {
            console.error("Error fetching tv data:", error);
        }
    }

    // Fetch OpenWeather
    async function fetchWeather() {
        if (!weatherKey) return;
        
        try {
            const url = 'https://api.openweathermap.org/data/2.5/weather?q=' + weatherCity + '&appid=' + weatherKey + '&units=metric&lang=es';
            const res = await fetch(url);
            if (!res.ok) throw new Error("Weather Error");
            const data = await res.json();
            
            const temp = Math.round(data.main.temp);
            const icon = data.weather[0].icon;
            const desc = data.weather[0].description;
            
            const iconUrl = 'https://openweathermap.org/img/wn/' + icon + '@2x.png';
            
            document.getElementById('tv-weather').innerHTML = 
                '<img src="' + iconUrl + '" alt="weather" style="width: 80px; height: 80px;">' +
                '<div>' +
                    '<div>' + temp + '\u00B0C</div>' +
                    '<div style="font-size: 1.2rem; color: var(--tv-text-muted); text-transform: capitalize;">' + desc + '</div>' +
                '</div>';
            
        } catch (error) {
            console.error("Error fetching weather:", error);
            document.getElementById('tv-weather').innerHTML = '<div class="weather-missing">Error obteniendo clima</div>';
        }
    }

    fetchDashboardData();
    fetchWeather();
    
    setInterval(fetchDashboardData, 5 * 60 * 1000);
    setInterval(fetchWeather, 30 * 60 * 1000);
});
'''

tablet_code = r'''
const csrfToken = document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').getAttribute('content') : '';
const originalFetch = window.fetch;
window.fetch = async function() {
    let [resource, config] = arguments;
    if (config && config.method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method.toUpperCase())) {
        config.headers = {
            ...config.headers,
            'X-CSRFToken': csrfToken
        };
    }
    return originalFetch(resource, config);
};

let currentPendingAction = null; // { type: 'tarea'|'inventario', id: number }
let globalUsers = [];

document.addEventListener("DOMContentLoaded", () => {
    // Reloj
    setInterval(() => {
        document.getElementById('tablet-clock').textContent = new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
    }, 1000);
    document.getElementById('tablet-clock').textContent = new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });

    // Cargar datos
    fetchData();
    setInterval(fetchData, 60000); // 1 minuto refresh

    // Búsqueda de inventario
    document.getElementById('inventarioSearch').addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase();
        document.querySelectorAll('.product-btn').forEach(btn => {
            if (btn.dataset.name.toLowerCase().includes(q)) {
                btn.style.display = 'flex';
            } else {
                btn.style.display = 'none';
            }
        });
    });
});

async function fetchData() {
    try {
        const res = await fetch('/api/tablet_data');
        if (!res.ok) {
            if(res.status === 401) window.location.href = '/login';
            throw new Error("Error fetching");
        }
        const data = await res.json();
        
        globalUsers = data.usuarios || [];
        renderTareas(data.tareas);
        renderInventario(data.inventario);
        renderMenus(data.menus);

    } catch (e) {
        console.error("Error fetching tablet data", e);
    }
}

function renderTareas(tareas) {
    const container = document.getElementById('tablet-tareas');
    if (!tareas || tareas.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding: 40px; font-size:1.5rem; color:var(--text-secondary)">No hay tareas pendientes! \u2728</div>';
        return;
    }
    
    container.innerHTML = tareas.map(t => 
        '<div class="touch-btn" id="tarea-' + t.id + '" onclick="promptUser(\'tarea\', ' + t.id + ')">' +
            '<div style="display:flex; align-items:center; gap: 15px;">' +
                '<div style="width:30px;height:30px;border:3px solid var(--border-color);border-radius:50%;"></div>' +
                '<div style="font-size:1.4rem; font-weight:bold;">' + t.nombre + '</div>' +
            '</div>' +
            (t.vencida ? '<span class="badge badge-danger">Vencida</span>' : '') +
        '</div>'
    ).join('');
}

function renderInventario(productos) {
    const container = document.getElementById('tablet-inventario');
    if (!productos || productos.length === 0) return;
    
    container.innerHTML = productos.map(p => 
        '<div class="product-btn" data-name="' + p.nombre.replace(/"/g, '&quot;') + '" id="prod-' + p.id + '" onclick="promptUser(\'inventario\', ' + p.id + ')">' +
            '<i class="fas fa-box"></i>' +
            '<span>' + p.nombre + '</span>' +
        '</div>'
    ).join('');
}

function renderMenus(menus) {
    const container = document.getElementById('tablet-menus');
    if (!menus || menus.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:var(--text-secondary)">Sin menu hoy</div>';
        return;
    }
    
    container.innerHTML = menus.map(m => 
        '<div class="menu-item">' +
            '<div style="color:var(--primary-color); font-weight:bold; font-size:1.1rem; text-transform:uppercase">' + m.tipo + '</div>' +
            '<div style="font-size:1.4rem;">' + m.receta + '</div>' +
        '</div>'
    ).join('');
}

window.promptUser = function(type, id) {
    currentPendingAction = { type, id };
    const modal = document.getElementById('userSelectorModal');
    const container = document.getElementById('userButtons');
    
    container.innerHTML = globalUsers.map(u => 
        '<button class="user-btn" onclick="executeAction(' + u.id + ')">' + u.username + '</button>'
    ).join('');
    
    modal.style.display = 'flex';
}

window.closeUserSelector = function() {
    document.getElementById('userSelectorModal').style.display = 'none';
    currentPendingAction = null;
}

window.executeAction = async function(userId) {
    const action = currentPendingAction;
    closeUserSelector();
    if (!action) return;
    
    try {
        if (action.type === 'tarea') {
            await fetch('/api/tareas/' + action.id + '/completar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ usuario_id: userId })
            });
            
            // Visual feedback
            const btn = document.getElementById('tarea-' + action.id);
            if(btn) {
                btn.style.backgroundColor = 'var(--success-color)';
                btn.style.color = '#fff';
                btn.innerHTML = '<div style="text-align:center;width:100%"><i class="fas fa-check"></i> \u00A1Completada!</div>';
                setTimeout(() => fetchData(), 1000);
            }
            
        } else if (action.type === 'inventario') {
            await fetch('/api/productos/' + action.id + '/lista', {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ estado: true })
            });
            
            const btn = document.getElementById('prod-' + action.id);
            if(btn) {
                btn.innerHTML = '<i class="fas fa-check-circle" style="color:var(--success-color)"></i><div>A\u00F1adido</div>';
                btn.style.borderColor = 'var(--success-color)';
            }
        }
    } catch(e) {
        console.error("Action error", e);
        alert("Error al procesar la accion");
    }
}
'''

with open(r't:\Proyectos\Inventario_Casa\static\js\tv_dashboard.js', 'w', encoding='utf-8') as f:
    f.write(tv_code)

with open(r't:\Proyectos\Inventario_Casa\static\js\tablet_dashboard.js', 'w', encoding='utf-8') as f:
    f.write(tablet_code)
