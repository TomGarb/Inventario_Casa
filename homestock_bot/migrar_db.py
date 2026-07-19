import sqlite3

try:
    conn = sqlite3.connect('instance/homestock.db')
    c = conn.cursor()
    # Add new column if it doesn't exist
    c.execute("ALTER TABLE productos ADD COLUMN unidad_medida VARCHAR(20) DEFAULT 'unidades'")
    conn.commit()
    print("Migración exitosa: columna 'unidad_medida' añadida a 'productos'.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("La columna 'unidad_medida' ya existe.")
    else:
        print(f"Error en la base de datos: {e}")
except Exception as e:
    print(f"Error general: {e}")
finally:
    conn.close()
