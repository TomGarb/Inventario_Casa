import sqlite3

def migrar():
    conn = sqlite3.connect('instance/homestock.db')
    c = conn.cursor()
    
    # 1. Modificar Producto
    try:
        c.execute("ALTER TABLE productos ADD COLUMN fecha_vencimiento DATE")
        print("Añadido fecha_vencimiento a productos")
    except sqlite3.OperationalError:
        print("fecha_vencimiento ya existe")
        
    try:
        c.execute("ALTER TABLE productos ADD COLUMN fecha_ultima_compra DATE")
        print("Añadido fecha_ultima_compra a productos")
    except sqlite3.OperationalError:
        print("fecha_ultima_compra ya existe")
        
    # 2. Modificar Movimientos
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN producto_id INTEGER REFERENCES productos(id)")
        print("Añadido producto_id a movimientos")
    except sqlite3.OperationalError:
        print("producto_id ya existe en movimientos")
        
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN tipo VARCHAR(50)")
        print("Añadido tipo a movimientos")
    except sqlite3.OperationalError:
        print("tipo ya existe en movimientos")
        
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN cantidad FLOAT DEFAULT 0.0")
        print("Añadido cantidad a movimientos")
    except sqlite3.OperationalError:
        print("cantidad ya existe en movimientos")
        
    conn.commit()
    conn.close()
    print("Migración completada con éxito.")

if __name__ == '__main__':
    migrar()
