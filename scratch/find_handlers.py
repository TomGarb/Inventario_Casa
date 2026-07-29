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
                        # Check if it has 'commands'
                        has_commands = any(k.arg == 'commands' for k in dec.keywords)
                        if has_commands:
                            type_ = 'command'
                        else:
                            type_ = 'text'
                    elif dec.func.attr == 'callback_query_handler':
                        type_ = 'callback'
        if is_handler:
            # find end line
            end_lineno = node.end_lineno
            handlers.append({
                'name': node.name,
                'type': type_,
                'start': node.lineno - 1, # Decorator line is usually lineno - len(decorators), but let's be careful.
                # Actually, node.lineno is the 'def' line. The decorators are above it.
                'dec_start': node.decorator_list[0].lineno - 1,
                'end': node.end_lineno - 1
            })

# Sort handlers so we can extract them from bottom to top without messing up lines, or just extract them all.
handlers.sort(key=lambda x: x['dec_start'])

for h in handlers:
    print(f"Found {h['type']} handler {h['name']} from {h['dec_start']} to {h['end']}")
