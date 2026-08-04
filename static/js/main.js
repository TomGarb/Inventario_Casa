window.CustomDialog = {
    show: function(options) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'modal';
            overlay.style.display = 'flex';
            overlay.style.zIndex = '9999';
            
            const content = document.createElement('div');
            content.className = 'modal-content';
            content.style.maxWidth = '450px';
            content.style.textAlign = 'center';
            
            const title = document.createElement('h2');
            title.innerText = options.type === 'confirm' ? '⚠️ Confirmar Acción' : '✏️ Ingresar Valor';
            title.style.marginBottom = '1rem';
            
            const msg = document.createElement('p');
            msg.innerText = options.message;
            msg.style.marginBottom = '1.5rem';
            msg.style.color = 'var(--text-secondary)';
            
            content.appendChild(title);
            content.appendChild(msg);
            
            let inputField = null;
            if (options.type === 'prompt') {
                inputField = document.createElement('input');
                inputField.type = 'text';
                inputField.value = options.defaultValue || '';
                inputField.style.width = '100%';
                inputField.style.padding = '0.75rem';
                inputField.style.marginBottom = '1.5rem';
                inputField.style.borderRadius = 'var(--radius-md)';
                inputField.style.border = '1px solid var(--border-color)';
                inputField.style.backgroundColor = 'var(--bg-color)';
                inputField.style.color = 'var(--text-primary)';
                content.appendChild(inputField);
            }
            
            const actions = document.createElement('div');
            actions.className = 'modal-actions';
            actions.style.justifyContent = 'center';
            actions.style.gap = '1rem';
            
            const btnCancel = document.createElement('button');
            btnCancel.className = 'btn btn-secundario';
            btnCancel.innerText = 'Cancelar';
            
            const btnOk = document.createElement('button');
            btnOk.className = 'btn btn-primary';
            btnOk.innerText = 'Aceptar';
            
            actions.appendChild(btnCancel);
            actions.appendChild(btnOk);
            content.appendChild(actions);
            overlay.appendChild(content);
            document.body.appendChild(overlay);
            
            if (inputField) {
                inputField.focus();
                inputField.select();
                inputField.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') btnOk.click();
                    if (e.key === 'Escape') btnCancel.click();
                });
            }
            
            const close = (val) => {
                document.body.removeChild(overlay);
                resolve(val);
            };
            
            btnCancel.onclick = () => close(options.type === 'prompt' ? null : false);
            btnOk.onclick = () => close(options.type === 'prompt' ? inputField.value : true);
        });
    },
    confirm: function(message) {
        return this.show({ type: 'confirm', message: message });
    },
    prompt: function(message, defaultValue) {
        return this.show({ type: 'prompt', message: message, defaultValue: defaultValue });
    }
};

let dbEspacios = []; // Almacena Salas -> Ubicaciones -> SubUbicaciones
let dbComercios = []; // Almacena Comercios
let allProducts = [];

document.addEventListener('input', (e) => { console.log('✏️ [Live Test] Input detectado en:', e.target.id || e.target.name, ' | Valor:', e.target.value); });
document.addEventListener('change', (e) => { if(e.target.tagName === 'SELECT') console.log('🔽 [Live Test] Desplegable cambiado:', e.target.id || e.target.name, ' | Nuevo valor:', e.target.value); });

function cerrarModalInfo() {
    document.getElementById('modal-info').classList.add('oculto');
    localStorage.setItem('homestock_welcome_shown', 'true');
}

// Inicialización global
document.addEventListener('DOMContentLoaded', () => {
    
    const buscadorMovs = document.getElementById('buscador-movimientos');
    if (buscadorMovs) {
        buscadorMovs.addEventListener('input', (e) => {
            fetchMovimientos(e.target.value);
        });
    }
    
    // Mostrar modal bienvenida si es nuevo
    if (!localStorage.getItem('homestock_welcome_shown')) {
        const modalInfo = document.getElementById('modal-info');
        if (modalInfo) modalInfo.classList.remove('oculto');
    }
    
    const path = window.location.pathname;

    if (path === '/') {
        initDashboard();
    } else if (path === '/inventario') {
        initInventario();
    } else if (path === '/compras') {
        initCompras();
    }
});


// --- Notificaciones Personalizadas ---
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = '✅';
    if(type === 'error') icon = '❌';
    else if(type === 'info') icon = 'ℹ️';
    
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('toast-hiding');
        setTimeout(() => {
            if (toast.parentElement) toast.remove();
        }, 300); // Wait for transition
    }, 3000);
    
    if (type === 'success') {
        setTimeout(() => {
            window.location.reload();
        }, 800); // Give the user 800ms to see the success toast before reloading
    }
}

window.alert = function(message) {
    // Override default alert
    showToast(message, 'info');
};

function showConfirm(message, callback) {
    CustomDialog.confirm(message).then(res => {
        if(res) callback();
    });
}
