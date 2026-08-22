
document.getElementById('btn-generar-token').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/generar_token', { method: 'POST' });
        const data = await response.json();
        
        if (data.token) {
            document.getElementById('token-code').innerText = `/vincular ${data.token}`;
            document.getElementById('token-container').style.display = 'block';
        }
    } catch (error) {
        alert("Error al generar el token.");
    }
});

// Admin Logic
async function loadUsuarios() {
    try {
        const response = await fetch('/api/usuarios');
        const usuarios = await response.json();
        const tbody = document.getElementById('usuarios-tbody');
        tbody.innerHTML = '';
        
        usuarios.forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${u.id}</td>
                <td>${u.username}</td>
                <td>${u.telegram_chat_id ? '✅ Sí' : '❌ No'}</td>
                <td>
                    <input type="checkbox" onchange="toggleAdmin(${u.id}, this.checked)" ${u.is_admin ? 'checked' : ''} ${u.id === CURRENT_USER_ID ? 'disabled' : ''}>
                </td>
                <td>
                    
                    <button class="btn btn-secondary btn-sm" onclick="openChangePasswordModal(${u.id}, '${u.username}')" title="Cambiar Clave">🔑</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteUsuario(${u.id})" ${u.id === CURRENT_USER_ID ? 'disabled' : ''}>Eliminar</button>

                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error("Error loading users", error);
    }
}

async function toggleAdmin(id, isAdmin) {
    try {
        const response = await fetch(`/api/usuarios/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_admin: isAdmin })
        });
        if(!response.ok) {
            const res = await response.json();
            alert(res.error || "Error al cambiar rol");
            loadUsuarios();
        }
    } catch (e) {
        showToast("Error de conexión", 'error');
        loadUsuarios();
    }
}

function deleteUsuario(id) {
    showConfirm("¿Estás seguro de eliminar este usuario?", async () => {
        try {
            const response = await fetch(`/api/usuarios/${id}`, { method: 'DELETE' });
            if(response.ok) {
                showToast("Usuario eliminado", 'success');
                loadUsuarios();
            } else {
                const res = await response.json();
                showToast(res.error || "Error al eliminar", 'error');
            }
        } catch(e) {
            showToast("Error de red", 'error');
        }
    });
}

function openCreateUserModal() {
    document.getElementById('create-user-modal').style.display = 'block';
}

function closeCreateUserModal() {
    document.getElementById('create-user-modal').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', () => {
    loadUsuarios();
    
    const formCreateUser = document.getElementById('form-create-user');
    if (formCreateUser) {
        formCreateUser.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('new-new-username') ? document.getElementById('new-new-username').value : document.getElementById('new-username').value;
            const password = document.getElementById('new-password').value;
            const is_admin = document.getElementById('new-isadmin').checked;
            
            try {
                const response = await fetch('/api/usuarios', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password, is_admin })
                });
                
                if (response.ok) {
                    closeCreateUserModal();
                    document.getElementById('form-create-user').reset();
                    loadUsuarios();
                    alert("Usuario creado exitosamente");
                } else {
                    const res = await response.json();
                    alert(res.error || "Error al crear usuario");
                }
            } catch (error) {
                alert("Error de conexión");
            }
        });
    }
});

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
    } else {
        input.type = 'password';
    }
}

function openChangePasswordModal(userId, username) {
    document.getElementById('pwd-user-id').value = userId;
    document.getElementById('modal-pwd-title').innerText = "Cambiar Contraseña: " + username;
    document.getElementById('form-cambiar-password').reset();
    document.getElementById('modal-cambiar-password').style.display = 'block';
}

function closeChangePasswordModal() {
    document.getElementById('modal-cambiar-password').style.display = 'none';
}

document.getElementById('form-cambiar-password').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('pwd-user-id').value;
    const pwd1 = document.getElementById('new-pwd-1').value;
    const pwd2 = document.getElementById('new-pwd-2').value;
    
    if (pwd1 !== pwd2) {
        alert("Las contraseñas no coinciden.");
        return;
    }
    
    if (pwd1.trim() === "") {
        alert("La contraseña no puede estar vacía.");
        return;
    }
    
    try {
        const response = await fetch(`/api/usuarios/${id}/password`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nueva_password: pwd1 })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(data.mensaje);
            closeChangePasswordModal();
        } else {
            alert("Error: " + (data.error || "Desconocido"));
        }
    } catch(err) {
        alert("Error de red.");
    }
});

/* =========================
   PERFIL TABS LOGIC
   ========================= */
document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.perfil-tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            // Add active class to clicked button and target panel
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
            
            if (targetId === 'panel-entret') {
                cargarSuscripciones();
            }
        });
    });
    
    // Load config global if admin
    if (document.getElementById('config-grupo-id')) {
        fetch('/api/perfil/configuracion')
            .then(res => res.json())
            .then(data => {
                if (data.grupo_principal_telegram_id) {
                    document.getElementById('config-grupo-id').value = data.grupo_principal_telegram_id;
                }
                if (data.hora_alerta_stock) {
                    document.getElementById('config-hora-stock').value = data.hora_alerta_stock;
                }
            })
            .catch(e => console.error("Error loading config", e));
    }
});

/* =========================
   PREFERENCES & CONFIG API
   ========================= */
async function guardarPreferencias(event) {
    const btn = event ? event.target : document.querySelector('#form-preferencias .btn');
    const originalText = btn.innerText;
    btn.innerText = "Guardando...";
    btn.disabled = true;
    
    const payload = {
        recibir_resumen_matutino: document.getElementById('pref-resumen').checked,
        recibir_alertas_vencimiento: document.getElementById('pref-vencimientos').checked,
        recibir_recordatorios_tareas: document.getElementById('pref-tareas').checked
    };
    
    try {
        const response = await fetch('/api/perfil/preferencias', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if(response.ok) {
            alert("Preferencias guardadas correctamente.");
        } else {
            alert("Error al guardar preferencias.");
        }
    } catch(e) {
        alert("Error de red al guardar preferencias.");
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

async function guardarConfiguracionGlobal(event) {
    const btn = event ? event.target : document.querySelector('#panel-admin .btn-primary');
    const originalText = btn.innerText;
    btn.innerText = "Guardando...";
    btn.disabled = true;
    
    const payload = {
        grupo_principal_telegram_id: document.getElementById('config-grupo-id').value.trim(),
        hora_alerta_stock: document.getElementById('config-hora-stock').value || "10:00"
    };
    
    try {
        const response = await fetch('/api/perfil/configuracion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if(response.ok) {
            alert("Configuración global guardada correctamente.");
        } else {
            alert("Error al guardar configuración.");
        }
    } catch(e) {
        alert("Error de red al guardar configuración.");
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

// ==========================
// SUSCRIPCIONES DEPORTIVAS
// ==========================

async function cargarSuscripciones() {
    const container = document.getElementById('subs-container');
    if (!container) return;
    
    try {
        const res = await fetch('/api/suscripciones');
        if (!res.ok) throw new Error('Error al cargar suscripciones');
        const subs = await res.json();
        
        if (subs.length === 0) {
            container.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 20px;">No tienes suscripciones activas.</div>';
            return;
        }
        
        container.innerHTML = subs.map(s => `
            <div class="neo-card" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 15px; border-left: 5px solid ${s.color || '#3b82f6'};">
                <div>
                    <strong>${s.nombre}</strong>
                    <span class="badge badge-info" style="margin-left: 10px; text-transform: capitalize;">${s.tipo}</span>
                    <div style="font-size: 0.8rem; color: var(--text-secondary);">API ID: ${s.external_api_id}</div>
                </div>
                <button class="neo-button-secondary" onclick="eliminarSuscripcion(${s.id})" style="color: var(--danger-color); padding: 5px 15px;">🗑️ Eliminar</button>
            </div>
        `).join('');
    } catch(e) {
        container.innerHTML = `<div class="alert alert-danger">Error: ${e.message}</div>`;
    }
}

async function agregarSuscripcion() {
    const id = document.getElementById('sub-id').value.trim();
    const nombre = document.getElementById('sub-nombre').value.trim();
    const tipo = document.getElementById('sub-tipo').value;
    const color = document.getElementById('sub-color').value;
    
    if (!id || !nombre) {
        showToast('Completa ID y Nombre', 'error');
        return;
    }
    
    try {
        const res = await fetch('/api/suscripciones', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ external_api_id: id, nombre, tipo, color })
        });
        if (!res.ok) throw new Error('Error al guardar');
        
        document.getElementById('sub-id').value = '';
        document.getElementById('sub-nombre').value = '';
        document.getElementById('sub-color').value = '#3b82f6';
        
        showToast('Suscripción agregada', 'success');
        cargarSuscripciones();
    } catch(e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function eliminarSuscripcion(id) {
    if (!confirm('¿Eliminar esta suscripción?')) return;
    try {
        const res = await fetch('/api/suscripciones/' + id, { method: 'DELETE' });
        if (!res.ok) throw new Error('Error al eliminar');
        showToast('Eliminada', 'success');
        cargarSuscripciones();
    } catch(e) {
        showToast('Error: ' + e.message, 'error');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btnSyncDeportes = document.getElementById('btn-sync-deportes');
    if (btnSyncDeportes) {
        btnSyncDeportes.addEventListener('click', async () => {
            const originalText = btnSyncDeportes.innerHTML;
            btnSyncDeportes.innerHTML = '⏳ Sincronizando...';
            btnSyncDeportes.disabled = true;
            
            try {
                const res = await fetch('/api/sincronizar_deportes', { method: 'POST' });
                const data = await res.json();
                
                if (res.ok && data.status === 'success') {
                    showToast(data.message, 'success');
                } else {
                    throw new Error(data.message || 'Error desconocido');
                }
            } catch (e) {
                showToast('Error al sincronizar: ' + e.message, 'error');
            } finally {
                btnSyncDeportes.innerHTML = originalText;
                btnSyncDeportes.disabled = false;
            }
        });
    }
});
