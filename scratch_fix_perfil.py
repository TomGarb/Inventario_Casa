import os

filepath = r't:\Proyectos\Inventario_Casa\templates\views\perfil.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('var(--bg-card)', 'var(--card-bg)')
content = content.replace('var(--bg-darker)', 'var(--bg-color)')
content = content.replace('var(--text-color)', 'var(--text-primary)')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
