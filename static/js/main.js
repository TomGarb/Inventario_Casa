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

// ==========================================
// 1. DASHBOARD
// ==========================================
async function initDashboard() {
    await fetchDashboardStats();
    await fetchGrafico();
    await fetchTendencias();
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

// ==========================================
// 2. INVENTARIO
// ==========================================
let currentInventoryFilter = { type: null, id: null };

window.resetInventoryFilter = function() {
    currentInventoryFilter = { type: null, id: null };
    renderSidebarHierarchy();
    if(allProducts) renderInventory(allProducts);
};

window.setInventoryFilter = function(type, id) {
    currentInventoryFilter = { type, id };
    renderSidebarHierarchy();
    if(allProducts) renderInventory(allProducts);
};

function renderSidebarHierarchy() {
    const container = document.getElementById('sidebar-hierarchy');
    if (!container) return;
    
    if (!dbEspacios || dbEspacios.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); margin-top: 20px;">No hay espacios creados.</p>';
        return;
    }
    
    let html = '<ul style="list-style: none; padding: 0; margin: 0; font-size: 0.95rem;">';
    
    dbEspacios.forEach(sala => {
        const isSalaActive = currentInventoryFilter.type === 'sala' && currentInventoryFilter.id === sala.id;
        const isSalaExpanded = isSalaActive || (sala.ubicaciones && sala.ubicaciones.some(u => 
            (currentInventoryFilter.type === 'ubicacion' && currentInventoryFilter.id === u.id) ||
            (u.sub_ubicaciones && u.sub_ubicaciones.some(su => currentInventoryFilter.type === 'sub_ubicacion' && currentInventoryFilter.id === su.id))
        ));

        html += `
            <li style="margin-bottom: 5px;">
                <div style="display: flex; align-items: center; padding: 6px 10px; border-radius: 6px; cursor: pointer; transition: background 0.2s; background: ${isSalaActive ? 'var(--primary-color)' : 'transparent'}; color: ${isSalaActive ? 'white' : 'var(--text-color)'}; font-weight: ${isSalaActive ? 'bold' : 'normal'}" 
                     onclick="setInventoryFilter('sala', ${sala.id})">
                    <span style="margin-right: 8px;">${isSalaExpanded ? '📂' : '📁'}</span>
                    ${sala.nombre}
                </div>
        `;
        
        if (sala.ubicaciones && sala.ubicaciones.length > 0) {
            html += `<ul style="list-style: none; padding-left: 25px; margin: 5px 0; display: ${isSalaExpanded ? 'block' : 'none'};">`;
            sala.ubicaciones.forEach(ubi => {
                const isUbiActive = currentInventoryFilter.type === 'ubicacion' && currentInventoryFilter.id === ubi.id;
                const isUbiExpanded = isUbiActive || (ubi.sub_ubicaciones && ubi.sub_ubicaciones.some(su => currentInventoryFilter.type === 'sub_ubicacion' && currentInventoryFilter.id === su.id));
                
                html += `
                    <li style="margin-bottom: 5px;">
                        <div style="display: flex; align-items: center; padding: 5px 10px; border-radius: 6px; cursor: pointer; transition: background 0.2s; background: ${isUbiActive ? 'rgba(74, 144, 226, 0.2)' : 'transparent'}; color: ${isUbiActive ? 'var(--primary-color)' : 'var(--text-color)'}; font-weight: ${isUbiActive ? 'bold' : 'normal'}" 
                             onclick="event.stopPropagation(); setInventoryFilter('ubicacion', ${ubi.id})">
                            <span style="margin-right: 8px; font-size: 0.9em;">${isUbiExpanded ? '🔽' : '▶️'}</span>
                            ${ubi.nombre}
                        </div>
                `;
                
                if (ubi.sub_ubicaciones && ubi.sub_ubicaciones.length > 0) {
                    html += `<ul style="list-style: none; padding-left: 25px; margin: 5px 0; display: ${isUbiExpanded ? 'block' : 'none'};">`;
                    ubi.sub_ubicaciones.forEach(sub => {
                        const isSubActive = currentInventoryFilter.type === 'sub_ubicacion' && currentInventoryFilter.id === sub.id;
                        html += `
                            <li style="margin-bottom: 2px;">
                                <div style="display: flex; align-items: center; padding: 4px 10px; border-radius: 6px; cursor: pointer; transition: background 0.2s; background: ${isSubActive ? 'rgba(74, 144, 226, 0.1)' : 'transparent'}; color: ${isSubActive ? 'var(--primary-color)' : 'var(--text-color)'}; font-weight: ${isSubActive ? 'bold' : 'normal'}; font-size: 0.9em;" 
                                     onclick="event.stopPropagation(); setInventoryFilter('sub_ubicacion', ${sub.id})">
                                    <span style="margin-right: 8px; font-size: 0.8em;">•</span>
                                    ${sub.nombre}
                                </div>
                            </li>
                        `;
                    });
                    html += `</ul>`;
                }
                html += `</li>`;
            });
            html += `</ul>`;
        }
        html += `</li>`;
    });
    
    html += '</ul>';
    container.innerHTML = html;
}

async function initInventario() {
    initSubNavigation();
    initModals();
    await fetchComercios(); // Necesario para crear productos
    await fetchEspacios();
    renderSidebarHierarchy(); // Dibujar sidebar tras cargar espacios
    await fetchProductsInventario();
    initCargaMasiva();
}

function initSubNavigation() {
    // Manejar sub-pestañas como SPA
    document.querySelectorAll('.sub-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = btn.getAttribute('data-target');
            
            // Toggle active classes
            document.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Toggle views
            document.querySelectorAll('.sub-view').forEach(v => v.classList.add('oculto'));
            const targetView = document.getElementById(targetId);
            if (targetView) targetView.classList.remove('oculto');
            
            // Ocultar/Mostrar sidebar según pestaña
            const sidebar = document.getElementById('inventory-sidebar');
            if (sidebar) {
                if (targetId === 'inv-tab-espacios') {
                    sidebar.style.display = 'none';
                } else {
                    sidebar.style.display = 'flex';
                }
            }
            
            // Guardar en localStorage
            localStorage.setItem('activeSubTab_' + window.location.pathname, targetId);
        });
    });
    
    // Restaurar pestaña activa
    const savedTabId = localStorage.getItem('activeSubTab_' + window.location.pathname);
    if (savedTabId) {
        const btn = document.querySelector(`.sub-tab-btn[data-target="${savedTabId}"]`);
        if (btn) btn.click();
    } else {
        // Por defecto hacer click en el primero
        const firstBtn = document.querySelector('.sub-tab-btn');
        if (firstBtn) firstBtn.click();
    }
}

async function fetchProductsInventario() {
    try {
        const response = await fetch('/api/productos');
        allProducts = await response.json();
        renderInventory(allProducts);
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

function renderInventory(products) {
    const board = document.getElementById('inventory-board');
    const listAll = document.getElementById('inventory-list-all');
    if(board) board.innerHTML = '';
    if(listAll) listAll.innerHTML = '';
    
    // Filtro base (ocultar temporales)
    let inventoryItems = products.filter(p => !p.es_temporal);
    
    // Aplicar Filtro Lateral Jerárquico
    if (currentInventoryFilter.id !== null) {
        if (currentInventoryFilter.type === 'sala') {
            const sala = dbEspacios.find(s => s.id === currentInventoryFilter.id);
            const ubicacionIds = sala ? sala.ubicaciones.map(u => u.id) : [];
            inventoryItems = inventoryItems.filter(p => ubicacionIds.includes(p.ubicacion_id));
        } else if (currentInventoryFilter.type === 'ubicacion') {
            inventoryItems = inventoryItems.filter(p => p.ubicacion_id === currentInventoryFilter.id);
        } else if (currentInventoryFilter.type === 'sub_ubicacion') {
            inventoryItems = inventoryItems.filter(p => p.sub_ubicacion_id === currentInventoryFilter.id);
        }
    }
    
    // Fantasmas Logic (Productos sin ubicación)
    const listaFantasmas = document.getElementById('lista-fantasmas');
    const btnToggleFantasmas = document.getElementById('btnToggleFantasmas');
    if (listaFantasmas && btnToggleFantasmas) {
        // En modo filtrado por Sala/Ubicacion no mostramos fantasmas globales, solo los correspondientes al filtro o ninguno
        const fantasmas = products.filter(p => !p.es_temporal && !p.ubicacion_id);
        
        btnToggleFantasmas.textContent = `👀 Mostrar Productos sin Asignar (${fantasmas.length})`;
        
        if (fantasmas.length === 0) {
            listaFantasmas.innerHTML = `<span style="color:#666;">No hay productos sin asignar. ¡Todo ordenado! 🎉</span>`;
        } else {
            listaFantasmas.innerHTML = fantasmas.map(p => `
                <div class="task-card" draggable="true" ondragstart="window.dragGhost(event, ${p.id})" onclick="window.toggleBulkSelection(${p.id})" style="cursor: pointer; min-width: 200px; border: 1px solid #f59e0b;">
                    <div class="task-title">${p.nombre}</div>
                    <div class="task-desc">🛒 ${p.comercio || 'Sin Comercio'}</div>
                    <div style="font-size: 0.8rem; color: #888; margin-top: 5px;">Arrastra para mover o haz clic para editar</div>
                </div>
            `).join('');
        }
        
        if (!btnToggleFantasmas.dataset.hasListener) {
            btnToggleFantasmas.addEventListener('click', () => {
                const panel = document.getElementById('panel-fantasmas');
                if (panel) panel.classList.toggle('oculto');
            });
            btnToggleFantasmas.dataset.hasListener = 'true';
        }
    }
    
    // Render Lista Plana
    if (listAll) {
        if (inventoryItems.length === 0) {
            listAll.innerHTML = `<p style="text-align: center; color: var(--text-secondary); margin-top: 2rem;">No hay productos en esta selección.</p>`;
        } else {
            const container = document.createElement('div');
            container.style.display = 'grid';
            container.style.gridTemplateColumns = 'repeat(auto-fill, minmax(350px, 1fr))';
            container.style.gap = '1rem';
            
            let allItemsHtml = inventoryItems.map(p => {
                const isLowStock = p.stock_actual <= p.stock_minimo;
                const subStr = p.sub_ubicacion ? `(${p.sub_ubicacion})` : '';
                return `
                <div class="task-card" data-id="${p.id}" onclick="toggleBulkSelection(${p.id})" style="display: flex; flex-direction: row; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem; padding: 1.5rem;">
                    <div style="display: flex; flex-direction: row; align-items: center; flex: 1; min-width: 200px;">
                        <div class="bulk-checkbox-container">
                            <input type="checkbox" class="bulk-checkbox" id="bulk-check-${p.id}" style="width: 1.5rem; height: 1.5rem;" onclick="event.stopPropagation()">
                        </div>
                        <div>
                            <div class="task-title">${p.nombre}</div>
                            <div class="task-desc">📍 ${p.ubicacion || 'Sin asignar'} ${subStr} • 🏬 ${p.comercio || 'Sin Comercio'}</div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                        <div class="stock-mini">
                            <button class="btn-s" onclick="window.updateStockBtn(event, ${p.id}, 'sub', ${p.stock_actual}, '${p.unidad_medida}')">-</button>
                            <span class="s-val ${isLowStock ? 's-low' : ''}">${p.stock_actual} ${p.unidad_medida !== 'unidades' ? p.unidad_medida : ''}</span>
                            <button class="btn-s" onclick="window.updateStockBtn(event, ${p.id}, 'add', ${p.stock_actual}, '${p.unidad_medida}')">+</button>
                        </div>
                        ${!p.en_lista ? `<button class="btn-sm btn-carrito" onclick="forzarAlCarrito(${p.id})">🛒 Añadir</button>` : `<span style="font-size: 0.85rem; color: var(--success-color); font-weight: 600;">En Lista ✓</span>`}
                        <button class="btn-mover" onclick="abrirModalMover(${p.id})">📦 Mover</button>
                    </div>
                </div>
                `;
            }).join('');
            container.innerHTML = allItemsHtml;
            listAll.appendChild(container);
        }
    }
    
    // Render Agrupado Dinámico (Kanban)
    if (board) {
        // Determinar agrupación lógica basada en el filtro
        let groupBy = 'ubicacion'; 
        if (currentInventoryFilter.type === 'ubicacion' || currentInventoryFilter.type === 'sub_ubicacion') {
            groupBy = 'sub_ubicacion'; // Si estamos dentro de una ubicación, agrupar por sub-ubicaciones
        }
        
        const groups = inventoryItems.reduce((acc, p) => {
            let gid, gname;
            if (groupBy === 'ubicacion') {
                gid = p.ubicacion_id || 0;
                gname = p.ubicacion || "Sin asignar";
            } else {
                gid = p.sub_ubicacion_id || 0;
                gname = p.sub_ubicacion || "Raíz de " + (p.ubicacion || "Ubicación");
            }
            const key = `${gid}|${gname}`;
            if (!acc[key]) acc[key] = [];
            acc[key].push(p);
            return acc;
        }, {});
        
        for (const [key, items] of Object.entries(groups)) {
            const [gid_str, gname] = key.split('|');
            const gid = parseInt(gid_str);
            
            // Si agrupamos por ubicación y no tiene, no lo mostramos en kanban (van a fantasmas)
            if (groupBy === 'ubicacion' && gid === 0) continue;
            
            const col = document.createElement('div');
            col.className = 'board-column';
            
            // Arrastrar solo tiene sentido si agrupamos por ubicación
            if (groupBy === 'ubicacion' && gid !== 0) {
                col.setAttribute('ondragover', 'window.allowDropGhost(event)');
                col.setAttribute('ondrop', `window.dropGhost(event, ${gid})`);
            }
            
            let itemsHtml = items.map(p => {
                const isLowStock = p.stock_actual <= p.stock_minimo;
                const subStr = p.sub_ubicacion ? `(${p.sub_ubicacion})` : '';
                return `
                <div class="task-card" data-id="${p.id}" onclick="toggleBulkSelection(${p.id})" draggable="true" ondragstart="window.dragGhost(event, ${p.id})" style="cursor: grab;">
                    <div class="task-header">
                        <div style="display: flex; align-items: center;">
                            <div class="bulk-checkbox-container">
                                <input type="checkbox" class="bulk-checkbox" id="bulk-check2-${p.id}" style="width: 1.5rem; height: 1.5rem;" onclick="event.stopPropagation()">
                            </div>
                            <div>
                                <div class="task-title">${p.nombre} ${groupBy === 'ubicacion' ? subStr : ''}</div>
                                <div class="task-desc">Min: ${p.stock_minimo} • Comprar en: ${p.comercio}</div>
                            </div>
                        </div>
                    </div>
                    <div class="task-actions">
                        <div class="stock-mini">
                            <button class="btn-s" onclick="window.updateStockBtn(event, ${p.id}, 'sub', ${p.stock_actual}, '${p.unidad_medida}')">-</button>
                            <span class="s-val ${isLowStock ? 's-low' : ''}">${p.stock_actual} ${p.unidad_medida !== 'unidades' ? p.unidad_medida : ''}</span>
                            <button class="btn-s" onclick="window.updateStockBtn(event, ${p.id}, 'add', ${p.stock_actual}, '${p.unidad_medida}')">+</button>
                        </div>
                        ${!p.en_lista ? `<button class="btn-sm btn-carrito" onclick="forzarAlCarrito(${p.id})">🛒 Añadir</button>` : `<span style="font-size: 0.85rem; color: var(--success-color); font-weight: 600;">En Lista ✓</span>`}
                        <button class="btn-mover" onclick="abrirModalMover(${p.id})">📦 Mover</button>
                    </div>
                </div>
                `;
            }).join('');
            
            col.innerHTML = `
                <div class="column-header">
                    <span>${groupBy === 'ubicacion' ? '📦' : '🗂️'} ${gname}</span>
                    <span style="background: var(--bg-color); border: 1px solid var(--border-color); padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">${items.length}</span>
                </div>
                <div class="items-container">${itemsHtml}</div>
            `;
            board.appendChild(col);
        }
    }
}

// Drag & Drop handlers for Ghost Products
window.dragGhost = function(ev, p_id) {
    ev.dataTransfer.setData("text/plain", p_id);
    ev.dataTransfer.effectAllowed = "move";
};

window.allowDropGhost = function(ev) {
    ev.preventDefault();
    ev.dataTransfer.dropEffect = "move";
};

window.dropGhost = async function(ev, ubi_id) {
    ev.preventDefault();
    const p_id = ev.dataTransfer.getData("text/plain");
    if (!p_id || !ubi_id) return;
    try {
        const res = await fetch(`/api/productos/${p_id}/mover`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ubicacion_id: parseInt(ubi_id), sub_ubicacion_id: null })
        });
        if(res.ok) { fetchProductsInventario(); }
    } catch(e) { console.error(e); }
};

// ==========================================
// DRAG AND DROP - COMPRAS
// ==========================================
window.allowDropCompra = function(ev) {
    ev.preventDefault();
    ev.dataTransfer.dropEffect = "move";
};

window.dropCompra = async function(ev, comercio_id) {
    ev.preventDefault();
    const p_id = ev.dataTransfer.getData("text/plain");
    if (!p_id) return;
    
    try {
        const payload = {};
        if (comercio_id === null || comercio_id === 'null' || comercio_id === '') {
            payload.comercio_id = '';
        } else {
            payload.comercio_id = parseInt(comercio_id);
        }
        
        const res = await fetch(`/api/productos/${p_id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            if (typeof fetchProductsCompras === 'function') fetchProductsCompras();
            if (typeof fetchProductsInventario === 'function') fetchProductsInventario();
        }
    } catch(e) { console.error(e); }
};

// ==========================================
// 3. COMPRAS
// ==========================================
async function initCompras() {
    initTelegramButton();
    await fetchComercios();
    await fetchDashboardStats(); // Necesario para el mapa de compras
    await fetchProductsCompras();
    await fetchEspacios(); // Para los selects del modal de Carga Compras
    initCargaCompras();
    initModals();

    
    const btnGestionarComercios = document.getElementById('btn-gestionar-comercios');
    const modalComercios = document.getElementById('modal-comercios');
    if (btnGestionarComercios && modalComercios) {
        btnGestionarComercios.onclick = () => {
            console.log('🛍️ [Live Test] Botón Gestionar Comercios clickeado');
            modalComercios.classList.remove('oculto');
        };
        const btnCerrar = document.getElementById('btn-cerrar-comercios');
        if (btnCerrar) btnCerrar.onclick = () => modalComercios.classList.add('oculto');
    }

    const btnMostrarTodo = document.getElementById('btnMostrarTodo');
    if (btnMostrarTodo) {
        btnMostrarTodo.onclick = () => {
            document.querySelectorAll('.board-column').forEach(col => col.style.display = 'block');
            btnMostrarTodo.style.display = 'none';
            document.querySelectorAll('.comercio-card').forEach(el => el.classList.remove('active'));
        };
    }
}

async function fetchProductsCompras() {
    try {
        const response = await fetch('/api/productos');
        allProducts = await response.json();
        renderShoppingList(allProducts);
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

function renderShoppingList(products) {
    const board = document.getElementById('shopping-board');
    if(!board) return;
    board.innerHTML = '';
    
    const shoppingItems = products.filter(p => p.en_lista);
    const byComercio = shoppingItems.reduce((acc, p) => {
        const c = p.comercio || "Compras Generales";
        if (!acc[c]) acc[c] = [];
        acc[c].push(p);
        return acc;
    }, {});
    
    // Asegurar que todos los comercios tengan columna, aunque estén vacíos
    dbComercios.forEach(c => {
        if (!byComercio[c.nombre]) {
            byComercio[c.nombre] = [];
        }
    });

    for (const [comercio, items] of Object.entries(byComercio)) {
        const comercioObj = dbComercios.find(c => c.nombre === comercio);
        const comercioId = comercioObj ? comercioObj.id : 'null';
        const idsComercio = JSON.stringify(items.map(p => p.id));
        
        const col = document.createElement('div');
        col.className = 'board-column';
        col.dataset.comercio = comercio;
        col.setAttribute('ondragover', 'window.allowDropCompra(event)');
        col.setAttribute('ondrop', `window.dropCompra(event, ${comercioId})`);
        
        let itemsHtml = items.map(p => {
            const un = p.unidad_medida !== 'unidades' ? p.unidad_medida : '';
            return `
            <div class="task-card" draggable="true" ondragstart="window.dragGhost(event, ${p.id})" style="cursor: grab;">
                <div class="task-header">
                    <div>
                        <div class="task-title">${p.nombre}</div>
                        ${p.es_temporal ? `<div class="task-desc">⚡ Añadido rápido</div>` : `<div class="task-desc">${p.ubicacion || 'Sin asignar'} | Stock Actual: ${p.stock_actual} ${un}</div>`}
                    </div>
                </div>
                <div class="task-actions" style="margin-top: 10px; display: flex; gap: 5px;">
                    <button class="btn-sm btn-comprado" onclick="marcarComprado(${p.id})" style="flex: 1;">✔️ Comprado</button>
                    <button class="btn-sm" onclick="quitarDeLista(${p.id})" style="flex: 1; background: var(--bg-color); border: 1px solid var(--border-color); color: var(--text-color);">❌ Quitar</button>
                </div>
            </div>
            `;
        }).join('');
        
        col.innerHTML = `
            <div class="column-header" style="flex-direction: column; align-items: stretch; gap: 8px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span>🛒 ${comercio}</span>
                        <span style="background: var(--bg-color); border: 1px solid var(--border-color); padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">${items.length}</span>
                    </div>
                </div>
                <div style="display: flex; gap: 5px;">
                    <button class="btn-primary" style="flex: 1; padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="bulkComprar(${idsComercio})">✅ Comprar Todo</button>
                    <button class="btn-secundario" style="flex: 1; padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="exportarListaCompras('${comercio}')">📤 Enviar</button>
                </div>
            </div>
            <div class="items-container">${itemsHtml}</div>
            <div class="quick-add">
                <input type="text" id="quick-input-${comercio.replace(/\s+/g, '')}" placeholder="Añadir a ${comercio}..." onkeypress="handleQuickAddKey(event, ${comercioId}, '${comercio}')">
                <button onclick="añadirRapido(${comercioId}, '${comercio}')">+</button>
            </div>
        `;
        board.appendChild(col);
    }
}

// ==========================================
// 4. FETCH AUXILIARES (Comercios y Espacios)
// ==========================================
async function fetchComercios() {
    try {
        const response = await fetch('/api/comercios');
        dbComercios = await response.json();
        console.log('📡 [Fetch] Obteniendo comercios para el desplegable...', dbComercios);
        
        const selCrear = document.getElementById('crear-comercio');
        if (selCrear) {
            selCrear.innerHTML = `<option value="">-- Sin asignar --</option>` + 
                dbComercios.map(c => `<option value="${c.id}">${c.nombre}</option>`).join('');
        }
        if (window.location.pathname === '/inventario' || window.location.pathname === '/compras' || document.getElementById('lista-comercios')) {
            renderGestionComercios();
        }
    } catch (error) {
        console.error('Error fetching comercios:', error);
    }
}

async function fetchEspacios() {
    try {
        const response = await fetch('/api/espacios');
        dbEspacios = await response.json();
        console.log('📦 [Fetch] Obteniendo salas para el desplegable...', dbEspacios);
        
        if (dbEspacios.length > 0 && currentInventoryFilter.id === null) {
            currentInventoryFilter.id = dbEspacios[0].id;
        }
        
        const optionsSala = `<option value="">-- Sin asignar --</option>` + 
            dbEspacios.map(s => `<option value="${s.id}">${s.nombre}</option>`).join('');
            
        const selSala = document.getElementById('crear-sala');
        if(selSala) selSala.innerHTML = optionsSala;
        const selMover = document.getElementById('mover-sala');
        if(selMover) selMover.innerHTML = optionsSala;
        
        if (window.location.pathname === '/inventario') {
            renderGestionEspacios();
        }
    } catch (error) {
        console.error('Error fetching espacios:', error);
    }
}

// ==========================================
// 5. ACCIONES DE PRODUCTOS (Comunes)
// ==========================================
async function updateStock(id, newStock) {
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
        const input = window.prompt(`¿Cuánto deseas ${op === 'add' ? 'sumar' : 'restar'}? (ej. 0.1, 0.5, 1)`, "0.5");
        if (input === null) return; // Cancelado
        diff = parseFloat(input.replace(',', '.'));
        if (isNaN(diff) || diff <= 0) {
            alert("Cantidad inválida");
            return;
        }
    }
    
    let newVal = op === 'add' ? currentStock + diff : currentStock - diff;
    if (newVal < 0) newVal = 0.0;
    
    updateStock(id, newVal);
};

async function forzarAlCarrito(id) {
    try {
        const response = await fetch(`/api/productos/${id}/lista`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ en_lista: true })
        });
        if (response.ok) fetchProductsInventario();
    } catch (error) { console.error('Error:', error); }
}

async function marcarComprado(id) {
    try {
        const response = await fetch(`/api/marcar_comprado/${id}`, { method: 'POST' });
        if (response.ok) fetchProductsCompras();
    } catch (error) { console.error('Error marcarComprado:', error); }
}

async function quitarDeLista(id) {
    try {
        const response = await fetch(`/api/productos/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ en_lista: false })
        });
        if (response.ok) {
            fetchProductsCompras();
        }
    } catch (error) { console.error('Error quitarDeLista:', error); }
}

async function bulkComprar(ids) {
    if (!ids || ids.length === 0) return;
    try {
        const response = await fetch('/api/compras/bulk-comprar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ productos: ids })
        });
        if (response.ok) fetchProductsCompras();
    } catch (error) { console.error('Error bulk comprar:', error); }
}

function optimizarRuta() {
    const board = document.getElementById('shopping-board');
    if (!board) return;
    
    // Sort columns by item count descending
    const columns = Array.from(board.querySelectorAll('.board-column'));
    columns.sort((a, b) => {
        const aCount = a.querySelectorAll('.task-card').length;
        const bCount = b.querySelectorAll('.task-card').length;
        return bCount - aCount;
    });
    
    board.innerHTML = '';
    columns.forEach(col => board.appendChild(col));
}

function handleQuickAddKey(event, comercioId, comercioNombre) {
    if (event.key === 'Enter') añadirRapido(comercioId, comercioNombre);
}

async function añadirRapido(comercioId, comercioNombre) {
    const inputId = comercioNombre ? `quick-input-${comercioNombre.replace(/\s+/g, '')}` : `quick-input-null`;
    const input = document.getElementById(inputId);
    if(!input) return;
    
    const nombre = input.value.trim();
    if (!nombre) return;
    try {
        const response = await fetch('/api/añadir_rapido', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre, comercio_id: comercioId })
        });
        if (response.ok) {
            input.value = ''; 
            fetchProductsCompras();
        }
    } catch (error) { console.error('Error:', error); }
}

function initTelegramButton() {
    const btn = document.getElementById('btn-enviar-telegram');
    if (btn) {
        btn.addEventListener('click', () => exportarListaCompras(null));
    }
}

window.exportarListaCompras = async function(comercioObjetivo = null) {
    try {
        let bodyPayload = {};
        if (comercioObjetivo) {
            bodyPayload = { comercio: comercioObjetivo };
        }
        
        const response = await fetch('/api/telegram/enviar_lista', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyPayload)
        });
        
        if (response.ok) {
            alert(comercioObjetivo ? `¡La lista de ${comercioObjetivo} se ha enviado a Telegram con éxito!` : '¡La lista global de compras se ha enviado a Telegram con éxito!');
        } else {
            alert('Hubo un problema al enviar la lista.');
        }
    } catch (error) {
        console.error('Error enviando lista:', error);
        alert('Error de red al intentar enviar la lista.');
    }
}

// ==========================================
// 6. MODALES Y FORMULARIOS (Solo en Inventario)
// ==========================================
document.addEventListener('submit', async (e) => {
    if (e.target.tagName === 'FORM') {
        if (e.target.classList.contains('auth-form')) {
            return; // Permitir envío normal del formulario
        }
        e.preventDefault();
        const formData = new FormData(e.target);
        const dataObj = Object.fromEntries(formData);
        
        // Convert empty strings to null and handle checkboxes
        Object.keys(dataObj).forEach(k => {
            if (dataObj[k] === '') dataObj[k] = null;
        });

        console.log('🚀 [Submit] Enviando datos:', dataObj);

        const formId = e.target.getAttribute('id');

        if (formId === 'form-crear-producto') {
            const es_temp = document.getElementById('crear-temp').checked;
            dataObj.es_temporal = es_temp;
            if(dataObj.comercio_id) dataObj.comercio_id = parseInt(dataObj.comercio_id);
            if(dataObj.ubicacion_id) dataObj.ubicacion_id = parseInt(dataObj.ubicacion_id);
            if(dataObj.sub_ubicacion_id) dataObj.sub_ubicacion_id = parseInt(dataObj.sub_ubicacion_id);

            const sala_id = parseInt(document.getElementById('crear-sala').value) || null;
            if (sala_id && !dataObj.ubicacion_id) {
                alert("Para guardar en una sala, debes seleccionar obligatoriamente una Ubicación específica.");
                return;
            }

            try {
                const res = await fetch('/api/productos', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dataObj)
                });
                if (res.ok) {
                    document.getElementById('modal-crear').classList.add('oculto');
                    fetchProductsInventario();
                    if (typeof fetchProductsCompras === 'function') fetchProductsCompras();
                    if (typeof initDashboard === 'function') initDashboard();
                } else alert("Error al crear producto");
            } catch (error) { console.error(error); alert("Error de red"); }
        }
        else if (formId === 'form-mover-producto') {
            const id = document.getElementById('mover-id').value;
            const selectSala = document.getElementById('mover-sala');
            const selectUbi = document.getElementById('mover-ubi');
            const selectSub = document.getElementById('mover-sub');
            const sala_id = parseInt(selectSala.value) || null;
            const ubi_id = parseInt(selectUbi.value) || null;
            const sub_id = parseInt(selectSub.value) || null;
            
            if (sala_id && !ubi_id) {
                alert("Para mover a una sala, debes seleccionar obligatoriamente una Ubicación específica.");
                return;
            }
            
            try {
                const res = await fetch(`/api/productos/${id}/mover`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ubicacion_id: ubi_id, sub_ubicacion_id: sub_id })
                });
                if (res.ok) {
                    document.getElementById('modal-mover').classList.add('oculto');
                    fetchProductsInventario();
                    if (typeof fetchProductsCompras === 'function') fetchProductsCompras();
                    if (typeof initDashboard === 'function') initDashboard();
                } else alert("Error al mover producto");
            } catch (error) { console.error(error); alert("Error de red"); }
        }
        else if (e.target.id === 'form-crear-sala') {
            const res = await fetch('/api/salas', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ nombre: dataObj.nombre }) });
            if (res.ok) { document.getElementById('nueva-sala-nombre').value = ''; fetchEspacios(); fetchProductsInventario(); }
        }
        else if (e.target.id === 'form-crear-ubi') {
            const select = document.getElementById('seleccionar-sala-ubi');
            const sala_id = parseInt(select.value);
            if (!sala_id) { alert("Sala obligatoria"); return; }
            const res = await fetch('/api/ubicaciones', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ nombre: dataObj.nombre, sala_id }) });
            if (res.ok) { document.getElementById('nueva-ubi-nombre').value = ''; fetchEspacios(); fetchProductsInventario(); }
        }
        else if (formId === 'form-crear-sub') {
            const selectU = document.getElementById('seleccionar-ubi-sub');
            const ubicacion_id = parseInt(selectU.value);
            if (!ubicacion_id) { alert("Ubicación obligatoria"); return; }
            try {
                const res = await fetch('/api/sub_ubicaciones', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ nombre: dataObj.nombre, ubicacion_id }) });
                if (res.ok) { document.getElementById('nueva-sub-nombre').value = ''; fetchEspacios(); fetchProductsInventario(); }
            } catch(e) { console.error(e); }
        }
        else if (formId === 'form-crear-comercio') {
            const res = await fetch('/api/comercios', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ nombre: dataObj.nombre }) });
            if (res.ok) { document.getElementById('nuevo-comercio-nombre').value = ''; fetchComercios(); fetchProductsInventario(); }
        }
    }
});

function bindCascadeSelects(salaSelectId, ubiSelectId, subSelectId) {
    const salaSelect = document.getElementById(salaSelectId);
    const ubiSelect = document.getElementById(ubiSelectId);
    const subSelect = document.getElementById(subSelectId);
    if(!salaSelect || !ubiSelect || !subSelect) return;

    salaSelect.addEventListener('change', () => {
        const salaId = parseInt(salaSelect.value);
        if (!salaId) {
            ubiSelect.innerHTML = `<option value="">-- Selecciona Sala primero --</option>`;
            ubiSelect.disabled = true;
            subSelect.innerHTML = `<option value="">-- Opcional --</option>`;
            subSelect.disabled = true;
            return;
        }

        const sala = dbEspacios.find(s => s.id === salaId);
        if (sala && sala.ubicaciones.length > 0) {
            ubiSelect.innerHTML = `<option value="">-- Selecciona Ubicación --</option>` + 
                sala.ubicaciones.map(u => `<option value="${u.id}">${u.nombre}</option>`).join('');
            ubiSelect.disabled = false;
        } else {
            ubiSelect.innerHTML = `<option value="">-- No hay ubicaciones --</option>`;
            ubiSelect.disabled = true;
        }
        
        subSelect.innerHTML = `<option value="">-- Opcional --</option>`;
        subSelect.disabled = true;
    });

    ubiSelect.addEventListener('change', () => {
        const ubiId = parseInt(ubiSelect.value);
        if (!ubiId) {
            subSelect.innerHTML = `<option value="">-- Opcional --</option>`;
            subSelect.disabled = true;
            return;
        }

        const sala = dbEspacios.find(s => s.id === parseInt(salaSelect.value));
        const ubi = sala.ubicaciones.find(u => u.id === ubiId);
        
        if (ubi && ubi.sub_ubicaciones.length > 0) {
            subSelect.innerHTML = `<option value="">-- Sin asignar --</option>` + 
                ubi.sub_ubicaciones.map(su => `<option value="${su.id}">${su.nombre}</option>`).join('');
            subSelect.disabled = false;
        } else {
            subSelect.innerHTML = `<option value="">-- No hay sub-ubicaciones --</option>`;
            subSelect.disabled = true;
        }
    });
}

function initModals() {
    const modalCrear = document.getElementById('modal-crear');
    const modalMover = document.getElementById('modal-mover');
    const btnNuevoProducto = document.getElementById('btn-nuevo-producto');

    bindCascadeSelects('crear-sala', 'crear-ubi', 'crear-sub');
    bindCascadeSelects('mover-sala', 'mover-ubi', 'mover-sub');

    if (btnNuevoProducto && modalCrear) {
        btnNuevoProducto.onclick = () => {
            document.getElementById('crear-nombre').value = '';
            document.getElementById('crear-desc').value = '';
            document.getElementById('crear-comercio').value = '';
            document.getElementById('crear-stock').value = '0';
            document.getElementById('crear-minimo').value = '1';
            
            document.getElementById('crear-sala').value = '';
            document.getElementById('crear-ubi').innerHTML = `<option value="">-- Selecciona Sala primero --</option>`;
            document.getElementById('crear-ubi').disabled = true;
            document.getElementById('crear-sub').innerHTML = `<option value="">-- Opcional --</option>`;
            document.getElementById('crear-sub').disabled = true;

            document.getElementById('crear-temp').checked = false;
            modalCrear.classList.remove('oculto');
        };

        document.getElementById('btn-cancelar-crear').onclick = () => modalCrear.classList.add('oculto');
    }

    if (modalMover) {
        document.getElementById('btn-cancelar-mover').onclick = () => modalMover.classList.add('oculto');
    }

    const shoppingView = document.getElementById('shopping-view');
    if (shoppingView) {
        const subTabs = shoppingView.querySelectorAll('.sub-tab-btn');
        subTabs.forEach(btn => {
            if(btn.id === 'btnMostrarTodo') return; // ignore show all button
            btn.addEventListener('click', () => {
                subTabs.forEach(t => t.classList.remove('active'));
                btn.classList.add('active');
                
                shoppingView.querySelectorAll('.sub-view').forEach(v => {
                    v.classList.add('oculto');
                    v.classList.remove('active-sub-view');
                });
                
                const targetId = btn.getAttribute('data-target');
                if (targetId) {
                    const targetView = document.getElementById(targetId);
                    if (targetView) {
                        targetView.classList.remove('oculto');
                        targetView.classList.add('active-sub-view');
                    }
                }
            });
        });
    }
}

window.abrirModalMover = function(id) {
    document.getElementById('mover-id').value = id;
    document.getElementById('mover-sala').value = '';
    
    document.getElementById('mover-ubi').innerHTML = `<option value="">-- Selecciona Sala primero --</option>`;
    document.getElementById('mover-ubi').disabled = true;
    
    document.getElementById('mover-sub').innerHTML = `<option value="">-- Opcional --</option>`;
    document.getElementById('mover-sub').disabled = true;
    
    document.getElementById('modal-mover').classList.remove('oculto');
};

// ==========================================
// 7. GESTION ESPACIOS Y COMERCIOS
// ==========================================
function renderGestionEspacios() {
    const lSalas = document.getElementById('lista-salas');
    if(lSalas) lSalas.innerHTML = dbEspacios.map(s => `<li>${s.nombre} <div><button class="btn-secundario" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="editarEspacio('sala', ${s.id}, '${s.nombre}')">✏️ Editar</button> <button class="btn-delete-sm" onclick="eliminarEspacio('salas', ${s.id})">Borrar</button></div></li>`).join('');

    const selectSalaUbi = document.getElementById('seleccionar-sala-ubi');
    const selectSalaSub = document.getElementById('seleccionar-sala-sub');
    const selectUbiSub = document.getElementById('seleccionar-ubi-sub');

    const optionsSala = `<option value="">-- Selecciona Sala --</option>` + dbEspacios.map(s => `<option value="${s.id}">${s.nombre}</option>`).join('');
            
    if(selectSalaUbi) selectSalaUbi.innerHTML = optionsSala;
    if(selectSalaSub) selectSalaSub.innerHTML = optionsSala;

    const lUbis = document.getElementById('lista-ubicaciones');
    if(lUbis) {
        let allUbisHtml = "";
        dbEspacios.forEach(s => s.ubicaciones.forEach(u => allUbisHtml += `<li>${u.nombre} (${s.nombre}) <div><button class="btn-secundario" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="editarEspacio('ubicacion', ${u.id}, '${u.nombre}')">✏️ Editar</button> <button class="btn-delete-sm" onclick="eliminarEspacio('ubicaciones', ${u.id})">Borrar</button></div></li>`));
        lUbis.innerHTML = allUbisHtml;
    }

    const lSubs = document.getElementById('lista-sububicaciones');
    if(lSubs) {
        let allSubsHtml = "";
        dbEspacios.forEach(s => s.ubicaciones.forEach(u => u.sub_ubicaciones.forEach(su => allSubsHtml += `<li>${su.nombre} (${u.nombre}) <div><button class="btn-secundario" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="editarEspacio('sububicacion', ${su.id}, '${su.nombre}')">✏️ Editar</button> <button class="btn-delete-sm" onclick="eliminarEspacio('sub_ubicaciones', ${su.id})">Borrar</button></div></li>`)));
        lSubs.innerHTML = allSubsHtml;
    }

    if(selectSalaSub) {
        selectSalaSub.onchange = () => {
            const sid = parseInt(selectSalaSub.value);
            if (!sid) {
                selectUbiSub.innerHTML = `<option value="">-- Ubicación --</option>`;
                selectUbiSub.disabled = true;
                return;
            }
            const sala = dbEspacios.find(s => s.id === sid);
            selectUbiSub.innerHTML = `<option value="">-- Ubicación --</option>` + sala.ubicaciones.map(u => `<option value="${u.id}">${u.nombre}</option>`).join('');
            selectUbiSub.disabled = false;
        };
    }
}

async function eliminarEspacio(tipo, id) {
    if (!confirm(`¿Estás seguro de eliminar esto? Afectará a los productos asignados.`)) return;
    const res = await fetch(`/api/${tipo}/${id}`, { method: 'DELETE' });
    if (res.ok) { fetchEspacios(); fetchProductsInventario(); }
}

async function editarEspacio(tipo, id, nombreActual) {
    const nuevoNombre = prompt("Nuevo nombre:", nombreActual);
    if (!nuevoNombre || nuevoNombre.trim() === "" || nuevoNombre === nombreActual) return;
    const res = await fetch(`/api/${tipo}/editar/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: nuevoNombre.trim() })
    });
    if (res.ok) { fetchEspacios(); fetchProductsInventario(); }
}

function renderGestionComercios() {
    const lComercios = document.getElementById('lista-comercios');
    if(lComercios) {
        lComercios.innerHTML = dbComercios.map(c => `
            <li style="display: flex; justify-content: space-between; padding: 10px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-color);">
                <span>${c.nombre}</span>
                <div style="display: flex; gap: 5px;">
                    <button class="btn-secundario" style="padding: 2px 8px; font-size: 0.8rem;" onclick="editarComercio(${c.id}, '${c.nombre}')">Editar</button>
                    <button class="btn-delete-sm" onclick="eliminarComercio(${c.id})">Borrar</button>
                </div>
            </li>
        `).join('');
    }
}

async function editarComercio(id, nombreActual) {
    const nuevoNombre = prompt("Nuevo nombre para el comercio:", nombreActual);
    if (!nuevoNombre || nuevoNombre.trim() === "" || nuevoNombre === nombreActual) return;
    
    try {
        const res = await fetch(`/api/comercios/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nombre: nuevoNombre.trim() })
        });
        if (res.ok) { 
            fetchComercios(); 
            if (typeof fetchProductsCompras === 'function') fetchProductsCompras();
            if (typeof fetchProductsInventario === 'function') fetchProductsInventario();
        } else {
            alert('Error al editar comercio');
        }
    } catch(e) {
        console.error(e);
        alert('Error de red al editar comercio');
    }
}

async function eliminarComercio(id) {
    if (!confirm(`¿Estás seguro de eliminar este comercio?`)) return;
    const res = await fetch(`/api/comercios/${id}`, { method: 'DELETE' });
    if (res.ok) { fetchComercios(); fetchProductsInventario(); }
}

// ==========================================
// CARGA MASIVA
// ==========================================
function initCargaMasiva() {
    const btnCargaMasiva = document.getElementById('btnCargaMasiva');
    const modalCargaMasiva = document.getElementById('modalCargaMasiva');
    const btnCancelar = document.getElementById('btn-cancelar-bulk');
    const btnAddRow = document.getElementById('btn-add-bulk-row');
    const btnGuardar = document.getElementById('btn-guardar-bulk');
    const container = document.getElementById('bulkRowsContainer');
    
    if (!btnCargaMasiva || !modalCargaMasiva) return;
    
    // Selects
    const bSala = document.getElementById('bulk-sala');
    const bUbi = document.getElementById('bulk-ubi');
    const bSub = document.getElementById('bulk-sub');
    
    // Auto-save function
    const saveDraft = () => {
        const rows = container.querySelectorAll('.bulk-row');
        const productos = [];
        rows.forEach(r => {
            productos.push({
                nombre: r.querySelector('.bulk-name').value,
                actual: r.querySelector('.bulk-actual').value,
                minimo: r.querySelector('.bulk-minimo').value,
                comercio: r.querySelector('.bulk-comercio').value
            });
        });
        const draft = {
            sala: bSala.value, ubi: bUbi.value, sub: bSub.value,
            productos: productos
        };
        localStorage.setItem('homestock_bulk_draft', JSON.stringify(draft));
    };

    // Attach listeners for auto-save
    bSala.addEventListener('change', saveDraft);
    bUbi.addEventListener('change', saveDraft);
    bSub.addEventListener('change', saveDraft);
    container.addEventListener('input', saveDraft);

    btnCargaMasiva.addEventListener('click', () => {
        // Poblado de Sala
        bSala.innerHTML = `<option value="">-- Selecciona Sala --</option>` + dbEspacios.map(s => `<option value="${s.id}">${s.nombre}</option>`).join('');
        bUbi.innerHTML = `<option value="">-- Ubicación --</option>`; bUbi.disabled = true;
        bSub.innerHTML = `<option value="">-- Sub-ubicación --</option>`; bSub.disabled = true;
        container.innerHTML = '';

        const draftStr = localStorage.getItem('homestock_bulk_draft');
        let restore = false;
        
        if (draftStr) {
            const draft = JSON.parse(draftStr);
            if (draft.productos && draft.productos.length > 0 && draft.productos.some(p => p.nombre.trim() !== '')) {
                restore = confirm("Tienes un borrador de carga masiva guardado offline. ¿Deseas restaurarlo?");
                if (restore) {
                    // Restaurar Selects
                    if (draft.sala) {
                        bSala.value = draft.sala;
                        const sala = dbEspacios.find(s => s.id === parseInt(draft.sala));
                        if(sala) {
                            bUbi.innerHTML = `<option value="">-- Ubicación --</option>` + sala.ubicaciones.map(u => `<option value="${u.id}">${u.nombre}</option>`).join('');
                            bUbi.disabled = false;
                            if (draft.ubi) {
                                bUbi.value = draft.ubi;
                                const ubi = sala.ubicaciones.find(u => u.id === parseInt(draft.ubi));
                                if(ubi) {
                                    bSub.innerHTML = `<option value="">-- Sub-ubicación --</option>` + ubi.sub_ubicaciones.map(su => `<option value="${su.id}">${su.nombre}</option>`).join('');
                                    bSub.disabled = false;
                                    if (draft.sub) bSub.value = draft.sub;
                                }
                            }
                        }
                    }
                    
                    // Restaurar Filas
                    draft.productos.forEach(p => {
                        addBulkRow();
                        const lastRow = container.lastElementChild;
                        lastRow.querySelector('.bulk-name').value = p.nombre;
                        lastRow.querySelector('.bulk-actual').value = p.actual;
                        lastRow.querySelector('.bulk-minimo').value = p.minimo;
                        lastRow.querySelector('.bulk-comercio').value = p.comercio;
                    });
                }
            }
        }

        if (!restore) {
            addBulkRow(); addBulkRow(); addBulkRow(); // 3 por defecto
            localStorage.removeItem('homestock_bulk_draft');
        }
        
        modalCargaMasiva.classList.remove('oculto');
    });
    
    btnCancelar.addEventListener('click', () => modalCargaMasiva.classList.add('oculto'));
    
    bSala.addEventListener('change', () => {
        const sid = parseInt(bSala.value);
        if (!sid) {
            bUbi.innerHTML = `<option value="">-- Ubicación --</option>`; bUbi.disabled = true;
            bSub.innerHTML = `<option value="">-- Sub-ubicación --</option>`; bSub.disabled = true;
            return;
        }
        const sala = dbEspacios.find(s => s.id === sid);
        bUbi.innerHTML = `<option value="">-- Ubicación --</option>` + sala.ubicaciones.map(u => `<option value="${u.id}">${u.nombre}</option>`).join('');
        bUbi.disabled = false;
        bSub.innerHTML = `<option value="">-- Sub-ubicación --</option>`; bSub.disabled = true;
    });
    
    bUbi.addEventListener('change', () => {
        const uid = parseInt(bUbi.value);
        const sid = parseInt(bSala.value);
        if (!uid || !sid) {
            bSub.innerHTML = `<option value="">-- Sub-ubicación --</option>`; bSub.disabled = true;
            return;
        }
        const sala = dbEspacios.find(s => s.id === sid);
        const ubi = sala.ubicaciones.find(u => u.id === uid);
        bSub.innerHTML = `<option value="">-- Sub-ubicación --</option>` + ubi.sub_ubicaciones.map(su => `<option value="${su.id}">${su.nombre}</option>`).join('');
        bSub.disabled = false;
    });
    
    btnAddRow.addEventListener('click', addBulkRow);
    
    btnGuardar.addEventListener('click', async () => {
        const sub_id = parseInt(bSub.value);
        const ubi_id = parseInt(bUbi.value);
        if (!sub_id) {
            alert('Debes seleccionar una Sub-ubicación destino obligatoriamente.');
            return;
        }
        
        const rows = container.querySelectorAll('.bulk-row');
        const productos = [];
        rows.forEach(r => {
            const nombre = r.querySelector('.bulk-name').value.trim();
            const actual = parseFloat(r.querySelector('.bulk-actual').value) || 0;
            const minimo = parseFloat(r.querySelector('.bulk-minimo').value) || 1;
            const unidad = r.querySelector('.bulk-unidad').value;
            const comercio = parseInt(r.querySelector('.bulk-comercio').value);
            
            if (nombre) {
                productos.push({
                    nombre: nombre,
                    stock_actual: actual,
                    stock_minimo: minimo,
                    unidad_medida: unidad,
                    comercio_id: comercio ? comercio : null
                });
            }
        });
        
        if (productos.length === 0) {
            alert('Añade al menos un producto con nombre.');
            return;
        }
        
        btnGuardar.disabled = true;
        
        async function enviarLote(payload) {
            try {
                const res = await fetch('/api/productos/bulk', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                
                if (res.ok) {
                    modalCargaMasiva.classList.add('oculto');
                    fetchProductsInventario(); // Recarga
                    btnGuardar.disabled = false;
                    localStorage.removeItem('homestock_bulk_draft'); // Clean up on success

                } else if (res.status === 409) {
                    const errorData = await res.json();
                    const conflictos = errorData.conflictos;
                    
                    // Pedir al usuario accion para cada uno
                    for (const nombreConflicto of conflictos) {
                        let accion = prompt(`El producto '${nombreConflicto}' ya existe.\n¿Deseas 'sumar' el stock, 'sobreescribir' el registro u 'omitir'?\nEscribe sumar, sobreescribir u omitir:`, 'sumar');
                        let val = accion ? accion.trim().toLowerCase() : 'omitir';
                        if (!['sumar', 'sobreescribir', 'omitir'].includes(val)) {
                            val = 'omitir';
                        }
                        
                        // Encontrar en el array original
                        const prodRef = payload.productos.find(p => p.nombre.toLowerCase() === nombreConflicto.toLowerCase());
                        if (prodRef) prodRef.accion_duplicado = val;
                    }
                    
                    // Reintentar recursivamente
                    await enviarLote(payload);
                    
                } else {
                    const e = await res.json();
                    alert(e.error || 'Error en carga masiva');
                    btnGuardar.disabled = false;
                }
            } catch(e) {
                console.error(e);
                alert('Error de conexión. Se ha guardado un borrador de forma offline en tu dispositivo. Puedes reintentar enviar cuando recuperes la conexión.');
                btnGuardar.disabled = false;
            }
        }
        
        enviarLote({
            ubicacion_id: ubi_id,
            sub_ubicacion_id: sub_id,
            productos: productos
        });
    });
}

function addBulkRow() {
    const container = document.getElementById('bulkRowsContainer');
    const row = document.createElement('div');
    row.className = 'bulk-row form-group-row';
    row.style.alignItems = 'center';
    row.style.gap = '5px';
    
    const comerciosOpts = `<option value="">-- Comercio --</option>` + dbComercios.map(c => `<option value="${c.id}">${c.nombre}</option>`).join('');
    
    row.innerHTML = `
        <div style="flex: 2;"><input type="text" class="bulk-name" placeholder="Nombre de Producto"></div>
        <div style="flex: 1;"><input type="number" class="bulk-actual" placeholder="Actual" min="0" value="1" step="any"></div>
        <div style="flex: 1;"><input type="number" class="bulk-minimo" placeholder="Mín." min="0" value="1" step="any"></div>
        <div style="flex: 1;"><select class="bulk-unidad"><option value="unidades">un.</option><option value="kg">kg</option><option value="L">L</option></select></div>
        <div style="flex: 1.5;"><select class="bulk-comercio" style="padding-left:0.5rem; padding-right: 1.5rem;">${comerciosOpts}</select></div>
        <div><button type="button" class="btn-delete-sm" onclick="this.parentElement.parentElement.remove()">X</button></div>
    `;
    container.appendChild(row);
}

// ==========================================
// CARGA RÁPIDA DE COMPRAS
// ==========================================
function initCargaCompras() {
    const btnCargaCompras = document.getElementById('btnCargaCompras');
    const modalCargaCompras = document.getElementById('modalCargaCompras');
    const btnCancelar = document.getElementById('btn-cancelar-compras');
    const btnAddRow = document.getElementById('btn-add-compra-row');
    const btnGuardar = document.getElementById('btn-guardar-compras');
    const container = document.getElementById('bulkComprasRows');
    
    if (!btnCargaCompras || !modalCargaCompras) return;
    
    btnCargaCompras.addEventListener('click', () => {
        container.innerHTML = '';
        addCompraRow(); // Al menos una fila
        modalCargaCompras.classList.remove('oculto');
    });
    
    btnCancelar.addEventListener('click', () => {
        modalCargaCompras.classList.add('oculto');
    });
    
    btnAddRow.addEventListener('click', addCompraRow);
    
    btnGuardar.addEventListener('click', async () => {
        const ubi_id = null;
        const sub_id = null;
        
        const rows = container.querySelectorAll('.bulk-row');
        const productos = [];
        rows.forEach(r => {
            const nombre = r.querySelector('.bulk-name').value.trim();
            const cantidad = parseFloat(r.querySelector('.bulk-cantidad').value) || 1;
            const unidad = r.querySelector('.bulk-unidad').value;
            const comercio = parseInt(r.querySelector('.bulk-comercio').value);
            
            if (nombre) {
                productos.push({
                    nombre: nombre,
                    cantidad: cantidad,
                    unidad_medida: unidad,
                    comercio_id: comercio ? comercio : null
                });
            }
        });
        
        if (productos.length === 0) {
            alert('Añade al menos un producto con nombre.');
            return;
        }
        
        btnGuardar.disabled = true;
        try {
            const res = await fetch('/api/compras/bulk', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    ubicacion_id: ubi_id,
                    sub_ubicacion_id: sub_id,
                    productos: productos
                })
            });
            if (res.ok) {
                modalCargaCompras.classList.add('oculto');
                fetchProductsCompras(); // Recarga
            } else {
                const e = await res.json();
                alert(e.error || 'Error en carga masiva de compras');
            }
        } catch(e) {
            console.error(e);
            alert('Error de conexión');
        } finally {
            btnGuardar.disabled = false;
        }
    });
}

window.addCompraRow = function() {
    const container = document.getElementById('bulkComprasRows');
    const row = document.createElement('div');
    row.className = 'bulk-row form-group-row';
    row.style.alignItems = 'center';
    row.style.gap = '5px';
    
    const comerciosOpts = `<option value="">-- Comercio --</option>` + dbComercios.map(c => `<option value="${c.id}">${c.nombre}</option>`).join('');
    
    row.innerHTML = `
        <div style="flex: 2;"><input type="text" class="bulk-name" placeholder="Nombre de Producto"></div>
        <div style="flex: 1;"><input type="number" class="bulk-cantidad" placeholder="Cant." min="0" value="1" step="any"></div>
        <div style="flex: 1;"><select class="bulk-unidad"><option value="unidades">un.</option><option value="kg">kg</option><option value="L">L</option></select></div>
        <div style="flex: 1.5;"><select class="bulk-comercio" style="padding-left:0.5rem; padding-right: 1.5rem;">${comerciosOpts}</select></div>
        <div><button type="button" class="btn-delete-sm" onclick="this.parentElement.parentElement.remove()">X</button></div>
    `;
    container.appendChild(row);
}

// --- Bulk Edit Logic ---
let bulkModeActive = false;
let selectedProductIds = new Set();
// ==========================================
// BULK DELETE
// ==========================================
window.bulkDeleteProducts = async function() {
    if (selectedProductIds.size === 0) return;
    if (!confirm(`¿Estás seguro de que deseas eliminar permanentemente los ${selectedProductIds.size} productos seleccionados?`)) return;
    
    try {
        const ids = Array.from(selectedProductIds);
        let errors = 0;
        
        // As API might not have a bulk delete, we do it in parallel
        await Promise.all(ids.map(async id => {
            const res = await fetch(`/api/productos/${id}`, { method: 'DELETE' });
            if (!res.ok) errors++;
        }));
        
        if (errors > 0) alert(`Se eliminaron productos, pero hubo ${errors} errores.`);
        
        fetchProductsInventario();
        if (typeof fetchProductsCompras === 'function') fetchProductsCompras();
        cancelBulkEdit();
        if (typeof initDashboard === 'function') initDashboard();
        
    } catch(e) {
        console.error(e);
        alert('Error al intentar eliminar productos en lote.');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const btnModoSeleccion = document.getElementById('btn-modo-seleccion');
    const bulkEditBar = document.getElementById('bulk-edit-bar');
    const btnCancelBulk = document.getElementById('btn-cancel-bulk');
    const btnApplyBulk = document.getElementById('btn-apply-bulk');

    if (btnModoSeleccion) {
        btnModoSeleccion.addEventListener('click', () => {
            bulkModeActive = !bulkModeActive;
            document.body.classList.toggle('bulk-mode', bulkModeActive);
            if (bulkModeActive) {
                btnModoSeleccion.classList.replace('btn-secundario', 'btn-primary');
                btnModoSeleccion.innerHTML = 'Cancelar Selección';
                bulkEditBar.classList.remove('oculto');
                populateBulkDropdowns();
            } else {
                cancelBulkEdit();
            }
        });
    }

    if (btnCancelBulk) {
        btnCancelBulk.addEventListener('click', cancelBulkEdit);
    }

    if (btnApplyBulk) {
        btnApplyBulk.addEventListener('click', async () => {
            if (selectedProductIds.size === 0) return alert('No hay productos seleccionados.');
            const ubi = document.getElementById('bulk-ubicacion').value;
            const sub = document.getElementById('bulk-sububicacion').value;
            if (!ubi && !sub) return alert('Seleccione una ubicación o sububicación de destino.');
            
            const res = await fetch('/api/productos/bulk-mover', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    producto_ids: Array.from(selectedProductIds),
                    ubicacion_id: ubi ? parseInt(ubi) : null,
                    sub_ubicacion_id: sub ? parseInt(sub) : null
                })
            });
            if (res.ok) {
                cancelBulkEdit();
                fetchProductsInventario();
            } else {
                alert('Error al mover productos.');
            }
        });
    }

    const bulkUbiSelect = document.getElementById('bulk-ubicacion');
    if (bulkUbiSelect) {
        bulkUbiSelect.addEventListener('change', (e) => {
            const subSelect = document.getElementById('bulk-sububicacion');
            const ubiId = parseInt(e.target.value);
            if (!ubiId) {
                subSelect.innerHTML = `<option value="">-- Mover a Sububicación --</option>`;
                subSelect.disabled = true;
                return;
            }
            let targetUbi = null;
            for (const s of dbEspacios) {
                const found = s.ubicaciones.find(u => u.id === ubiId);
                if (found) targetUbi = found;
            }
            if (targetUbi && targetUbi.sub_ubicaciones.length > 0) {
                subSelect.innerHTML = `<option value="">-- Mover a Sububicación --</option>` + 
                    targetUbi.sub_ubicaciones.map(su => `<option value="${su.id}">${su.nombre}</option>`).join('');
                subSelect.disabled = false;
            } else {
                subSelect.innerHTML = `<option value="">-- Sin Sububicaciones --</option>`;
                subSelect.disabled = true;
            }
        });
    }
});

window.toggleBulkSelection = function(id) {
    if (!bulkModeActive) {
        if (typeof abrirModalEditar === 'function') abrirModalEditar(id);
        return;
    }
    const chk1 = document.getElementById(`bulk-check-${id}`);
    const chk2 = document.getElementById(`bulk-check2-${id}`);
    
    if (selectedProductIds.has(id)) {
        selectedProductIds.delete(id);
        if (chk1) chk1.checked = false;
        if (chk2) chk2.checked = false;
        
        // Remove selection style
        const cards = document.querySelectorAll(`.task-card[data-id="${id}"]`);
        cards.forEach(c => c.classList.remove('selected'));
    } else {
        selectedProductIds.add(id);
        if (chk1) chk1.checked = true;
        if (chk2) chk2.checked = true;
        
        // Add selection style
        const cards = document.querySelectorAll(`.task-card[data-id="${id}"]`);
        cards.forEach(c => c.classList.add('selected'));
    }
    const countSpan = document.getElementById('bulk-selected-count');
    if (countSpan) countSpan.innerText = `${selectedProductIds.size} seleccionados`;
};

function cancelBulkEdit() {
    bulkModeActive = false;
    selectedProductIds.clear();
    document.body.classList.remove('bulk-mode');
    const btnModoSeleccion = document.getElementById('btn-modo-seleccion');
    if (btnModoSeleccion) {
        btnModoSeleccion.classList.replace('btn-primary', 'btn-secundario');
        btnModoSeleccion.innerHTML = '☑️ Modo Selección';
    }
    const bulkEditBar = document.getElementById('bulk-edit-bar');
    if (bulkEditBar) bulkEditBar.classList.add('oculto');
    document.querySelectorAll('.bulk-checkbox').forEach(cb => cb.checked = false);
    document.querySelectorAll('.task-card.selected').forEach(c => c.classList.remove('selected'));
    const countSpan = document.getElementById('bulk-selected-count');
    if (countSpan) countSpan.innerText = '0 seleccionados';
}

// ==========================================
// EDICION DE PRODUCTO (MODAL DETALLADO)
// ==========================================
window.abrirModalEditar = function(id) {
    const p = allProducts.find(x => x.id === id);
    if (!p) return;
    
    document.getElementById('editar-id').value = p.id;
    document.getElementById('editar-nombre').value = p.nombre;
    document.getElementById('editar-desc').value = p.descripcion || '';
    document.getElementById('editar-stock').value = p.stock_actual;
    document.getElementById('editar-minimo').value = p.stock_minimo;
    document.getElementById('editar-unidad').value = p.unidad_medida;
    
    // Comercios
    const selectComercio = document.getElementById('editar-comercio');
    selectComercio.innerHTML = '<option value="">-- Sin asignar --</option>' + dbComercios.map(c => `<option value="${c.id}">${c.nombre}</option>`).join('');
    selectComercio.value = p.comercio_id || '';
    
    // Espacios
    const selectSala = document.getElementById('editar-sala');
    selectSala.innerHTML = '<option value="">-- Sin asignar --</option>' + dbEspacios.map(s => `<option value="${s.id}">${s.nombre}</option>`).join('');
    
    let ubiId = p.ubicacion_id || '';
    let subId = p.sub_ubicacion_id || '';
    
    // Tratar de encontrar la sala basada en ubicacion
    let salaId = '';
    if (ubiId) {
        for (const s of dbEspacios) {
            if (s.ubicaciones.some(u => u.id === ubiId)) {
                salaId = s.id;
                break;
            }
        }
    }
    selectSala.value = salaId;
    
    // Trigger the cascades manually to populate ubi and sub
    const selectUbi = document.getElementById('editar-ubi');
    const selectSub = document.getElementById('editar-sub');
    
    if (salaId) {
        const sala = dbEspacios.find(s => s.id == salaId);
        selectUbi.innerHTML = '<option value="">-- Sin asignar --</option>' + sala.ubicaciones.map(u => `<option value="${u.id}">${u.nombre}</option>`).join('');
        selectUbi.disabled = false;
        selectUbi.value = ubiId;
        
        if (ubiId) {
            const ubi = sala.ubicaciones.find(u => u.id == ubiId);
            selectSub.innerHTML = '<option value="">-- Sin asignar --</option>' + (ubi && ubi.sub_ubicaciones ? ubi.sub_ubicaciones.map(su => `<option value="${su.id}">${su.nombre}</option>`).join('') : '');
            selectSub.disabled = false;
            selectSub.value = subId;
        } else {
            selectSub.innerHTML = '<option value="">-- Opcional --</option>';
            selectSub.disabled = true;
        }
    } else {
        selectUbi.innerHTML = '<option value="">-- Selecciona Sala --</option>';
        selectUbi.disabled = true;
        selectSub.innerHTML = '<option value="">-- Opcional --</option>';
        selectSub.disabled = true;
    }
    
    document.getElementById('modal-editar').classList.remove('oculto');
};

document.addEventListener('DOMContentLoaded', () => {
    // Vincular selects en cascada para modal editar
    bindCascadeSelects('editar-sala', 'editar-ubi', 'editar-sub');
    
    const btnCancelarEditar = document.getElementById('btn-cancelar-editar');
    if(btnCancelarEditar) btnCancelarEditar.onclick = () => document.getElementById('modal-editar').classList.add('oculto');
    
    const formEditar = document.getElementById('form-editar-producto');
    if(formEditar) {
        formEditar.onsubmit = async (e) => {
            e.preventDefault();
            const id = document.getElementById('editar-id').value;
            const data = {
                nombre: document.getElementById('editar-nombre').value,
                descripcion: document.getElementById('editar-desc').value,
                comercio_id: document.getElementById('editar-comercio').value,
                stock_actual: parseFloat(document.getElementById('editar-stock').value),
                stock_minimo: parseFloat(document.getElementById('editar-minimo').value),
                unidad_medida: document.getElementById('editar-unidad').value,
                ubicacion_id: document.getElementById('editar-ubi').value,
                sub_ubicacion_id: document.getElementById('editar-sub').value
            };
            
            try {
                const res = await fetch(`/api/productos/${id}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                if(res.ok) {
                    document.getElementById('modal-editar').classList.add('oculto');
                    fetchProductsInventario();
                    if(typeof fetchProductsCompras === 'function') fetchProductsCompras();
                    if(typeof initDashboard === 'function') initDashboard();
                } else {
                    alert("Error al actualizar producto");
                }
            } catch (err) { console.error(err); alert("Error de red"); }
        };
    }
    
    const btnEliminar = document.getElementById('btn-eliminar-producto');
    if(btnEliminar) {
        btnEliminar.onclick = async () => {
            if(!confirm('¿Estás seguro de que deseas eliminar este producto permanentemente?')) return;
            const id = document.getElementById('editar-id').value;
            try {
                const res = await fetch(`/api/productos/${id}`, { method: 'DELETE' });
                if(res.ok) {
                    document.getElementById('modal-editar').classList.add('oculto');
                    fetchProductsInventario();
                    if(typeof fetchProductsCompras === 'function') fetchProductsCompras();
                    if(typeof initDashboard === 'function') initDashboard();
                } else {
                    alert("Error al eliminar producto");
                }
            } catch (err) { console.error(err); alert("Error de red"); }
        };
    }
});

function populateBulkDropdowns() {
    const ubiSelect = document.getElementById('bulk-ubicacion');
    if (!ubiSelect) return;
    let opts = `<option value="">-- Mover a Ubicación --</option>`;
    dbEspacios.forEach(s => {
        opts += `<optgroup label="${s.nombre}">`;
        s.ubicaciones.forEach(u => {
            opts += `<option value="${u.id}">${u.nombre}</option>`;
        });
        opts += `</optgroup>`;
    });
    ubiSelect.innerHTML = opts;
    const subSelect = document.getElementById('bulk-sububicacion');
    if (subSelect) {
        subSelect.innerHTML = `<option value="">-- Mover a Sububicación --</option>`;
        subSelect.disabled = true;
    }
}


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
}

window.alert = function(message) {
    // Override default alert
    showToast(message, 'info');
};

function showConfirm(message, callback) {
    const modal = document.getElementById('custom-confirm-modal');
    if (!modal) {
        // Fallback
        if(window.confirm(message)) callback();
        return;
    }
    document.getElementById('custom-confirm-message').innerText = message;
    modal.style.display = 'flex';
    
    const btnCancel = document.getElementById('custom-confirm-cancel');
    const btnOk = document.getElementById('custom-confirm-ok');
    
    // Cleanup function
    const cleanup = () => {
        modal.style.display = 'none';
        btnCancel.replaceWith(btnCancel.cloneNode(true));
        btnOk.replaceWith(btnOk.cloneNode(true));
    };
    
    btnCancel.onclick = () => {
        cleanup();
    };
    
    btnOk.onclick = () => {
        cleanup();
        callback();
    };
}
