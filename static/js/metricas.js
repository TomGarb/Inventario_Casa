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

    } catch (e) {
        console.error("Error al cargar mtricas", e);
    }
});
