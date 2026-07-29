import re

filepath = 't:/Proyectos/Inventario_Casa/app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

# Find the start of handle_voice_and_text
for i, line in enumerate(lines):
    if '@bot.message_handler(func=lambda message: True, content_types=[' in line or '@bot.message_handler(content_types=[' in line:
        # Check if the next line is handle_voice_and_text
        if i + 1 < len(lines) and 'def handle_voice_and_text' in lines[i+1]:
            start_idx = i
            break

if start_idx == -1:
    print("Could not find handle_voice_and_text decorator")
    exit(1)

# Find the end of handle_voice_and_text (next @bot. or class/def at same indent level)
for i in range(start_idx + 2, len(lines)):
    if lines[i].startswith('    @bot.') or (lines[i].startswith('    def ') and not lines[i].startswith('        ')):
        end_idx = i
        break

if end_idx == -1:
    print("Could not find end of handle_voice_and_text")
    exit(1)

# Extract the block
handler_lines = lines[start_idx:end_idx]

# Modify the decorator
handler_lines[0] = "    @bot.message_handler(content_types=['text', 'voice'])\n"

# Remove from original
del lines[start_idx:end_idx]

# Find the insertion point
insert_idx = -1
for i, line in enumerate(lines):
    if '5. RUTAS WEB Y API' in line:
        insert_idx = i - 1 # Insert before the comment block
        break

if insert_idx == -1:
    print("Could not find insertion point")
    exit(1)

# Prepare /cancelar handler
cancelar_handler = [
    "    @bot.message_handler(commands=['cancelar'])\n",
    "    def cmd_cancelar(message):\n",
    "        bot.clear_step_handler_by_chat_id(message.chat.id)\n",
    "        bot.reply_to(message, '🛑 Operación cancelada. Puedes continuar con normalidad.')\n",
    "\n"
]

# Insert both handlers
lines = lines[:insert_idx] + cancelar_handler + handler_lines + ["\n"] + lines[insert_idx:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Successfully moved {len(handler_lines)} lines to index {insert_idx}.")
