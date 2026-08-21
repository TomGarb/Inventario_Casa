
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
