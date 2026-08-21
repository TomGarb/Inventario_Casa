const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
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
            if(btn.dataset.name.toLowerCase().includes(q)) btn.style.display = 'flex';
            else btn.style.display = 'none';
        });
    });
});

async function fetchData() {
    try {
        const res = await fetch('/api/tablet_data');
        if (!res.ok) {
            if(res.status === 401) window.location.href = '/login';
            return;
        }
        const data = await res.json();
        
        globalUsers = data.usuarios;
        
        renderTareas(data.tareas);
        renderInventario(data.inventario);
        renderMenus(data.menus);
        renderUserModal();

    } catch (e) {
        console.error("Error fetching tablet data", e);
    }
}

function renderTareas(tareas) {
    const container = document.getElementById('tablet-tareas');
    if (tareas.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding: 40px; font-size:1.5rem; color:var(--text-secondary)">No hay tareas pendientes! 🎉</div>';
        return;
    }
    
    container.innerHTML = tareas.map(t => 
        <div class="touch-btn" id="tarea-" onclick="promptUser('tarea', )">
            <div style="display:flex; align-items:center; gap: 15px;">
                <i class="far fa-circle task-icon"></i>
                <div>
                    <div style="font-weight:bold"></div>
                    
                </div>
            </div>
            <i class="fas fa-chevron-right" style="color:var(--border-color)"></i>
        </div>
    ).join('');
}

function renderInventario(productos) {
    const container = document.getElementById('tablet-inventario');
    container.innerHTML = productos.map(p => 
        <div class="product-btn" data-name="" id="prod-" onclick="promptUser('inventario', )">
            <i class="fas fa-box"></i>
            <div></div>
            <small style="color:var(--text-secondary)">Stock: </small>
        </div>
    ).join('');
}

function renderMenus(menus) {
    const container = document.getElementById('tablet-menus');
    if (menus.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:var(--text-secondary)">Sin menú hoy</div>';
        return;
    }
    container.innerHTML = menus.map(m => 
        <div class="menu-item">
            <div style="color:var(--primary-color); font-weight:bold; font-size:1.1rem; text-transform:uppercase"></div>
            <div></div>
        </div>
    ).join('');
}

function renderUserModal() {
    const container = document.getElementById('userButtons');
    container.innerHTML = globalUsers.map(u => 
        <button class="user-btn" onclick="executeAction()"></button>
    ).join('');
}

function promptUser(type, id) {
    currentPendingAction = { type, id };
    document.getElementById('userSelectorModal').style.display = 'flex';
}

function closeUserSelector() {
    document.getElementById('userSelectorModal').style.display = 'none';
    currentPendingAction = null;
}

async function executeAction(userId) {
    if (!currentPendingAction) return;
    
    const { type, id } = currentPendingAction;
    closeUserSelector(); // Close modal immediately for snappy feel
    
    if (type === 'tarea') {
        const btn = document.getElementById('tarea-' + id);
        if(btn) btn.classList.add('completing'); // Optimistic UI
        
        await fetch('/api/tareas/' + id + '/completar', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ usuario_id: userId })
        });
        
        setTimeout(() => { if(btn) btn.remove(); }, 300); // Remove after animation
    } 
    else if (type === 'inventario') {
        const btn = document.getElementById('prod-' + id);
        if(btn) {
            btn.innerHTML = '<i class="fas fa-check-circle" style="color:var(--success-color)"></i><div>Añadido</div>';
            btn.style.borderColor = 'var(--success-color)';
        }
        
        await fetch('/api/productos/' + id + '/lista', {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ en_lista: true }) // No need for userId here based on backend, but we could add it to logs later
        });
        
        setTimeout(() => { if(btn) btn.remove(); }, 1000);
    }
}

