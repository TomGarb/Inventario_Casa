document.addEventListener("DOMContentLoaded", async () => {
    try {
        const res = await fetch('/api/metricas_data');
        if (!res.ok) throw new Error("API Error");
        const data = await res.json();
        
        // 1. Llenar KPIs
        document.getElementById('kpi-gasto').textContent = '$' + data.kpis.gasto_mes_actual.toFixed(2);
        document.getElementById('kpi-faltantes').textContent = data.kpis.total_productos_falta;
        document.getElementById('kpi-evento').textContent = data.kpis.dias_para_proximo_evento;
        
        // 2. Renderizar Chart
        const ctx = document.getElementById('gastosChart').getContext('2d');
        
        // Determinar color de grid segn modo oscuro/claro
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const gridColor = isDark ? '#4b5563' : '#e5e7eb';
        const textColor = isDark ? '#9ca3af' : '#4b5563';
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.chart.labels,
                datasets: [{
                    label: 'Gastos Diarios ($)',
                    data: data.chart.data,
                    borderColor: '#a855f7', // Prpura Nen
                    backgroundColor: 'rgba(168, 85, 247, 0.1)',
                    borderWidth: 3,
                    tension: 0.4, // Curvas suaves
                    fill: true,
                    pointBackgroundColor: '#a855f7',
                    pointBorderColor: '#fff',
                    pointRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false }, // Ocultar grilla vertical
                        ticks: { color: textColor }
                    },
                    y: {
                        grid: { color: gridColor, borderDash: [5, 5] },
                        ticks: { color: textColor }
                    }
                }
            }
        });
        
        // 3. Excepciones
        const listaVencidas = document.getElementById('lista-vencidas');
        if (data.excepciones.tareas_vencidas.length > 0) {
            listaVencidas.innerHTML = data.excepciones.tareas_vencidas.map(t => 
                `<li style="padding: 10px; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between;">
                    <span>${t.nombre}</span>
                    <span class="badge badge-danger">Hace ${t.dias_retraso} días</span>
                </li>`
            ).join('');
        } else {
            listaVencidas.innerHTML = '<li style="color: var(--success-color); padding: 10px;">¡Todo al día! 🎉</li>';
        }
        
        const listaDeudas = document.getElementById('lista-deudas');
        if (data.excepciones.deudas.length > 0) {
            listaDeudas.innerHTML = data.excepciones.deudas.map(d => 
                `<li style="padding: 10px; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between;">
                    <span>${d.usuario}</span>
                    <span style="color: var(--danger-color); font-weight: bold;">Debe $${d.monto.toFixed(2)}</span>
                </li>`
            ).join('');
        } else {
            listaDeudas.innerHTML = '<li style="color: var(--success-color); padding: 10px;">¡Cuentas claras! 🥂</li>';
        }
        // 4. Metas de Ahorro
        renderMetas(data.metas || []);

    } catch (e) {
        console.error("Error al cargar métricas", e);
    }
});

function renderMetas(metas) {
    const container = document.getElementById('metas-container');
    if (!metas || metas.length === 0) {
        container.innerHTML = '<div class="neo-card" style="text-align: center; color: var(--text-secondary); padding: 30px; grid-column: 1/-1;">No hay metas activas. ¡Crea una para empezar a ahorrar! 🚀</div>';
        return;
    }
    
    container.innerHTML = metas.map(m => `
        <div class="neo-card">
            <div class="meta-card-header">
                <div>
                    <span class="meta-icon">${m.icono}</span>
                    <strong style="font-size: 1.1rem; margin-left: 8px;">${m.nombre}</strong>
                </div>
                <span class="meta-pct">${m.porcentaje}%</span>
            </div>
            
            <div class="neo-progress-track">
                <div class="neo-progress-fill" style="width: ${m.porcentaje}%;"></div>
            </div>
            
            <div class="meta-card-amounts">
                <span>$${m.monto_actual.toLocaleString('es-AR')}</span>
                <span>$${m.monto_objetivo.toLocaleString('es-AR')}</span>
            </div>
            ${m.fecha_limite ? '<div style="text-align: right; font-size: 0.8rem; color: var(--text-secondary); margin-top: 5px;">📅 Límite: ' + m.fecha_limite + '</div>' : ''}
            
            <div class="meta-actions">
                <button class="neo-button-primary" style="flex: 1; font-size: 0.85rem; padding: 8px;" onclick="aportarMeta(${m.id})">💰 Aportar</button>
                <button class="neo-button-secondary" style="flex: 1; font-size: 0.85rem; padding: 8px;" onclick="eliminarMeta(${m.id})">🗑️ Eliminar</button>
            </div>
        </div>
    `).join('');
}

function toggleFormMeta() {
    const form = document.getElementById('form-nueva-meta');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function crearMeta() {
    const nombre = document.getElementById('meta-nombre').value.trim();
    const monto = document.getElementById('meta-monto').value;
    const fecha = document.getElementById('meta-fecha').value;
    
    if (!nombre || !monto) {
        showToast('Completa nombre y monto objetivo', 'error');
        return;
    }
    
    try {
        const res = await fetch('/api/metas', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nombre, monto_objetivo: parseFloat(monto), fecha_limite: fecha || null })
        });
        if (!res.ok) throw new Error('Error creando meta');
        
        document.getElementById('meta-nombre').value = '';
        document.getElementById('meta-monto').value = '';
        document.getElementById('meta-fecha').value = '';
        document.getElementById('form-nueva-meta').style.display = 'none';
        
        // Recargar metas
        const dataRes = await fetch('/api/metricas_data');
        const data = await dataRes.json();
        renderMetas(data.metas || []);
        showToast('Meta creada exitosamente', 'success');
    } catch(e) {
        console.error(e);
        showToast('Error al crear la meta', 'error');
    }
}

async function aportarMeta(id) {
    const monto = prompt('¿Cuánto querés aportar a esta meta? ($)');
    if (!monto || isNaN(monto) || parseFloat(monto) <= 0) return;
    
    try {
        const res = await fetch('/api/metas/' + id, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ aporte: parseFloat(monto) })
        });
        if (!res.ok) throw new Error('Error');
        
        const dataRes = await fetch('/api/metricas_data');
        const data = await dataRes.json();
        renderMetas(data.metas || []);
        showToast('Aporte registrado 💰', 'success');
    } catch(e) {
        console.error(e);
    }
}

async function eliminarMeta(id) {
    if (!confirm('¿Eliminar esta meta de ahorro?')) return;
    
    try {
        await fetch('/api/metas/' + id, { method: 'DELETE' });
        
        const dataRes = await fetch('/api/metricas_data');
        const data = await dataRes.json();
        renderMetas(data.metas || []);
        showToast('Meta eliminada', 'success');
    } catch(e) {
        console.error(e);
    }
}
