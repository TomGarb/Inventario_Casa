
    let carritoGastos = [];
    
    document.addEventListener("DOMContentLoaded", function() {
        cargarBalances();
        cargarHistorialGastos();
    });

    
    function cargarBalances() {
        fetch('/api/finanzas/balances')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('balances-container');
            container.innerHTML = '';
            if (data.length === 0) {
                container.innerHTML = '<p style=\"color: var(--success-color); font-size: 0.9rem; margin-top: 10px;\">¡Todo al día! No hay deudas.</p>';
                return;
            }
            
            const ul = document.createElement('ul');
            ul.style.listStyle = 'none';
            ul.style.padding = '0';
            ul.style.fontSize = '0.9rem';
            ul.style.width = '100%';
            
            data.forEach(b => {
                const li = document.createElement('li');
                li.style.padding = '5px 0';
                li.style.borderBottom = '1px solid var(--border-color)';
                li.innerHTML = `<strong>${b.deudor_nombre}</strong> debe a <strong>${b.acreedor_nombre}</strong>: 
                                <span style=\"color: var(--danger-color); float: right; font-weight: bold;\">$${b.monto.toFixed(2)}</span>`;
                ul.appendChild(li);
            });
            container.appendChild(ul);
        })
        .catch(err => {
            console.error(\"Error al cargar balances:\", err);
            document.getElementById('balances-container').innerHTML = '<p style=\"color: red;\">Error cargando balances</p>';
        });
    }

    function cargarHistorialGastos() {
        fetch('/api/finanzas/gastos')
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('historial-gastos');
            tbody.innerHTML = '';
            if(data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">No hay gastos registrados.</td></tr>';
                return;
            }
            
            // Guardar en variable global para ver el detalle luego
            window.gastosData = data;
            
            data.forEach((g, index) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${g.fecha}</td>
                    <td>${g.descripcion}</td>
                    <td>${g.pagador}</td>
                    <td>$${g.monto.toFixed(2)}</td>
                    <td><button class="btn btn-secondary btn-sm" onclick="verDetalleGasto(${index})">👁️ Ver Detalle</button></td>
                `;
                tbody.appendChild(tr);
            });
        })
        .catch(err => {
            console.error("Error al cargar historial:", err);
            document.getElementById('historial-gastos').innerHTML = '<tr><td colspan="5" style="color: red;">Error cargando historial</td></tr>';
        });
    }
    
    function verDetalleGasto(index) {
        const g = window.gastosData[index];
        const tbody = document.getElementById('detalle-gasto-tbody');
        tbody.innerHTML = '';
        
        document.getElementById('detalle-gasto-info').innerHTML = `
            <strong>Concepto:</strong> ${g.descripcion}<br>
            <strong>Fecha:</strong> ${g.fecha}<br>
            <strong>Pagador:</strong> ${g.pagador}
        `;
        
        if (g.detalles && g.detalles.length > 0) {
            g.detalles.forEach(d => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${d.descripcion}</td>
                    <td>${d.cantidad}</td>
                    <td>$${d.precio_unitario.toFixed(2)}</td>
                    <td>$${d.subtotal.toFixed(2)}</td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No hay desglose de ítems para este gasto.</td></tr>';
        }
        
        document.getElementById('detalle-gasto-total').innerText = g.monto.toFixed(2);
        document.getElementById('modal-detalle-gasto').style.display = 'block';
    }

    function agregarItemCarrito() {
        const descInput = document.getElementById('item-desc');
        const cantInput = document.getElementById('item-cant');
        const precioInput = document.getElementById('item-precio');
        
        const desc = descInput.value.trim();
        const cant = parseFloat(cantInput.value) || 1;
        const precio = parseFloat(precioInput.value) || 0;
        
        if (!desc || precio <= 0) {
            showToast("Ingrese artículo y precio válido.", "error");
            return;
        }
        
        carritoGastos.push({ descripcion: desc, cantidad: cant, precio: precio });
        renderCarrito();
        
        descInput.value = '';
        cantInput.value = '1';
        precioInput.value = '';
        descInput.focus();
    }
    
    function eliminarItemCarrito(index) {
        carritoGastos.splice(index, 1);
        renderCarrito();
    }
    
    function renderCarrito() {
        const container = document.getElementById('carrito-items');
        container.innerHTML = '';
        let total = 0;
        
        if (carritoGastos.length === 0) {
            container.innerHTML = '<div style="color: var(--text-secondary); text-align: center;">El carrito está vacío. Agrega ítems abajo.</div>';
        } else {
            carritoGastos.forEach((item, index) => {
                const subtotal = item.cantidad * item.precio;
                total += subtotal;
                const div = document.createElement('div');
                div.style.display = 'flex';
                div.style.justifyContent = 'space-between';
                div.style.borderBottom = '1px solid var(--border-color)';
                div.style.padding = '5px 0';
                div.innerHTML = `
                    <div style="flex: 2;">${item.descripcion}</div>
                    <div style="flex: 1; text-align: center;">${item.cantidad} x $${item.precio.toFixed(2)}</div>
                    <div style="flex: 1; text-align: right; font-weight: bold;">$${subtotal.toFixed(2)}</div>
                    <div style="margin-left: 10px;"><button type="button" class="btn btn-danger btn-sm" onclick="eliminarItemCarrito(${index})">❌</button></div>
                `;
                container.appendChild(div);
            });
        }
        document.getElementById('gasto-monto-total').innerText = total.toFixed(2);
    }
    
    function cerrarModalGasto() {
        document.getElementById('modal-gasto').style.display = 'none';
        document.getElementById('ticket-file').value = '';
        carritoGastos = [];
        renderCarrito();
        document.getElementById('gasto-concepto').value = '';
    }

    function setTabGasto(tab) {
        if (tab === 'manual') {
            document.getElementById('tab-manual').style.display = 'block';
            document.getElementById('tab-ia').style.display = 'none';
            document.getElementById('btn-tab-manual').className = 'btn btn-primary';
            document.getElementById('btn-tab-ia').className = 'btn btn-secondary';
        } else {
            document.getElementById('tab-manual').style.display = 'none';
            document.getElementById('tab-ia').style.display = 'block';
            document.getElementById('btn-tab-manual').className = 'btn btn-secondary';
            document.getElementById('btn-tab-ia').className = 'btn btn-primary';
        }
    }

    function escanearTicket() {
        const fileInput = document.getElementById('ticket-file');
        if (!fileInput.files || fileInput.files.length === 0) {
            showToast("Por favor selecciona una imagen primero.", "error");
            return;
        }

        const file = fileInput.files[0];
        const reader = new FileReader();

        reader.onload = function(e) {
            const base64Image = e.target.result;
            
            document.getElementById('btn-escanear-ia').style.display = 'none';
            document.getElementById('ia-loading').style.display = 'block';
            
            fetch('/api/finanzas/ocr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_base64: base64Image })
            })
            .then(res => res.json())
            .then(data => {
                document.getElementById('btn-escanear-ia').style.display = 'block';
                document.getElementById('ia-loading').style.display = 'none';

                if(data.error) {
                    showToast(data.error, "error");
                } else {
                    showToast("¡Ticket leído con éxito!", "success");
                    document.getElementById('gasto-concepto').value = data.descripcion || '';
                    document.getElementById('item-desc').value = data.descripcion || 'Compra (Total)';
                    document.getElementById('item-cant').value = '1';
                    document.getElementById('item-precio').value = data.monto_total || '';
                    setTabGasto('manual');
                }
            })
            .catch(err => {
                document.getElementById('btn-escanear-ia').style.display = 'block';
                document.getElementById('ia-loading').style.display = 'none';
                showToast("Error de conexión con el OCR.", "error");
                console.error(err);
            });
        };
        reader.readAsDataURL(file);
    }
    
    function abrirModalGasto() {
        document.getElementById('modal-gasto').style.display = 'block';
        setTabGasto('manual');
        carritoGastos = [];
        renderCarrito();
        document.getElementById('gasto-concepto').value = '';
    }

    document.getElementById('form-gasto').addEventListener('submit', function(e) {
        e.preventDefault();
        const concepto = document.getElementById('gasto-concepto').value;
        const totalHtml = document.getElementById('gasto-monto-total').innerText;
        const total = parseFloat(totalHtml) || 0;
        
        if (carritoGastos.length === 0) {
            showToast("Añade al menos un artículo al carrito.", "error");
            return;
        }
        
        fetch('/api/finanzas/gasto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                descripcion: concepto,
                monto_total: total,
                items: carritoGastos
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(data.mensaje || "Gasto registrado correctamente", "success");
                cerrarModalGasto();
                cargarBalances();
                cargarHistorialGastos();
            } else {
                showToast(data.error || "Error al registrar gasto", "error");
            }
        })
        .catch(err => {
            showToast("Error al procesar la solicitud", "error");
            console.error(err);
        });
    });
