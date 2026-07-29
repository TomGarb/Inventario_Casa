import ast

filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    source = f.read()

lines = source.split('\n')

tree = ast.parse(source)

handlers = []
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        is_handler = False
        type_ = None
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.value.id == 'bot':
                    is_handler = True
                    if dec.func.attr == 'message_handler':
                        has_commands = any(k.arg == 'commands' for k in dec.keywords)
                        if has_commands:
                            type_ = 'command'
                        else:
                            type_ = 'text'
                    elif dec.func.attr == 'callback_query_handler':
                        type_ = 'callback'
        if is_handler:
            handlers.append({
                'name': node.name,
                'type': type_,
                'dec_start': node.decorator_list[0].lineno - 1,
                'end': node.end_lineno - 1
            })

handlers.sort(key=lambda x: x['dec_start'])

# Ensure no overlaps (AST lines should be disjoint)
# Extract chunks
blocks = {'command': [], 'callback': [], 'text': []}

# We need to extract them from bottom to top to avoid messing up line numbers, or extract by content
# Let's extract by content.
extracted = []
for h in handlers:
    chunk = lines[h['dec_start']:h['end']+1]
    # Handle possible empty lines after function body by appending an empty line
    extracted.append((h['dec_start'], h['end'], chunk, h['type'], h['name']))

# Separate non-handler lines
new_lines = []
skip_until = -1
for i, line in enumerate(lines):
    in_handler = False
    for h in handlers:
        if h['dec_start'] <= i <= h['end']:
            in_handler = True
            break
    if not in_handler:
        new_lines.append(line)

# Now we have all the non-handler lines in new_lines.
# We need to find the injection point: right after `if bot:` at line 76 (which is now in new_lines).
# Let's find `bot = telebot.TeleBot` and `if bot:`
inject_idx = -1
for i, line in enumerate(new_lines):
    if line.startswith('if bot:'):
        inject_idx = i + 1
        break

if inject_idx == -1:
    print("Could not find if bot:")
    exit(1)

# Group extracted
commands = []
callbacks = []
texts = []
catch_all = None

for ext in extracted:
    h_type = ext[3]
    h_name = ext[4]
    chunk = ext[2]
    # Ensure they are indented with 4 spaces since they go inside `if bot:`
    # Wait, some might already be indented with 4 spaces, some might be indented with 0 spaces?
    # AST tells us they are under `if bot:` if they were indented.
    # Let's just ensure they are indented correctly.
    # We will enforce 4 spaces.
    for i in range(len(chunk)):
        if chunk[i].strip(): # if not empty
            if not chunk[i].startswith('    '):
                chunk[i] = '    ' + chunk[i]
    
    if h_name == 'handle_voice_and_text':
        catch_all = chunk
    elif h_type == 'command':
        commands.extend(chunk + [''])
    elif h_type == 'callback':
        callbacks.extend(chunk + [''])
    else:
        texts.extend(chunk + [''])

assembled_handlers = []
assembled_handlers.append('    # 1. COMANDOS')
assembled_handlers.extend(commands)
assembled_handlers.append('    # 2. CALLBACKS')
assembled_handlers.extend(callbacks)
assembled_handlers.append('    # 3. TEXTO / CATCH-ALL')
assembled_handlers.extend(texts)
if catch_all:
    assembled_handlers.extend(catch_all + [''])

final_lines = new_lines[:inject_idx] + assembled_handlers + new_lines[inject_idx:]

# Additionally, we need to inject the diagnostic print right before bot_thread.start()
for i, line in enumerate(final_lines):
    if 'bot_thread.start()' in line:
        indent = line[:len(line) - len(line.lstrip())]
        final_lines.insert(i, f'{indent}print(f"🛠️ Diagnóstico: El bot tiene {{len(bot.message_handlers)}} handlers de mensajes registrados antes de iniciar.")')
        break

with open(filepath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))

print("Restructured successfully.")
