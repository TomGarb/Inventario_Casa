import os

html_dir = r't:\Proyectos\Inventario_Casa\templates'
for root, _, files in os.walk(html_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            orig_content = content
            content = content.replace('var(--bg-card)', 'var(--card-bg)')
            content = content.replace('var(--bg-darker)', 'var(--bg-color)')
            content = content.replace('var(--text-color)', 'var(--text-primary)')
            
            if content != orig_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
