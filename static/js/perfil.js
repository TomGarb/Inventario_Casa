
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

{% if current_user.is_admin %}
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

{% endif %}
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


