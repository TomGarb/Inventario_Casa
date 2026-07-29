filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
for i, line in enumerate(lines):
    if line.startswith('    @bot.message_handler(content_types=[\'text\', \'voice\'])') or line.startswith('    @bot.message_handler(content_types=[\'voice\', \'text\'])'):
        start_idx = i
        break

if start_idx == -1:
    print("Could not find handle_voice_and_text")
    exit(1)

# The function body starts at start_idx + 2
# Find where it ends
end_idx = -1
for i in range(start_idx + 2, len(lines)):
    # Assuming it ends when we hit # ==========================================
    if '5. RUTAS WEB Y API' in lines[i]:
        end_idx = i - 2
        break

if end_idx == -1:
    print("Could not find end of function")
    exit(1)

# Now we indent lines from start_idx + 2 to end_idx
new_lines = lines[:start_idx+2]
new_lines.append('        try:\n')
for i in range(start_idx+2, end_idx):
    # Only indent if the line is not purely whitespace
    if lines[i].strip():
        new_lines.append('    ' + lines[i])
    else:
        new_lines.append(lines[i])

new_lines.append('        except Exception as e:\n')
new_lines.append('            print(f"🔴 ERROR INTERNO EN HANDLER DE TEXTO: {e}")\n')
new_lines.append('            bot.reply_to(message, "Hubo un error interno. Revisa la consola.")\n')

new_lines.extend(lines[end_idx:])

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Successfully wrapped handle_voice_and_text in try/except.")
