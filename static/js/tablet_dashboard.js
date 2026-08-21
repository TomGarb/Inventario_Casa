
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
