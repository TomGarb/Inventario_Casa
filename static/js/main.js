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

