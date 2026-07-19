import os
from sqlalchemy import create_engine, MetaData, text
from app import app, db

# 1. Asegurarse de que las tablas existen en PostgreSQL
with app.app_context():
    print("Creando tablas en PostgreSQL...")
    db.create_all()

# 2. Conectarse a ambas bases de datos
# SQLite
base_dir = os.path.dirname(os.path.abspath(__file__))
sqlite_uri = f'sqlite:///{os.path.join(base_dir, "instance", "homestock.db")}'
engine_sqlite = create_engine(sqlite_uri)

# PostgreSQL (leer la URI de la app configurada)
pg_uri = app.config['SQLALCHEMY_DATABASE_URI']
engine_pg = create_engine(pg_uri)

# 3. Reflejar metadatos
meta_sqlite = MetaData()
meta_sqlite.reflect(bind=engine_sqlite)

meta_pg = MetaData()
meta_pg.reflect(bind=engine_pg)

# 4. Iniciar copia de datos
tablas_en_orden = ['usuarios', 'salas', 'ubicaciones', 'sub_ubicaciones', 'comercios', 'productos', 'movimientos']

with engine_pg.begin() as conn_pg:
    for table_name in tablas_en_orden:
        print(f"Migrando tabla: {table_name}...")
        table_sqlite = meta_sqlite.tables.get(table_name)
        table_pg = meta_pg.tables.get(table_name)
        
        if table_sqlite is None or table_pg is None:
            print(f"  Tabla {table_name} no encontrada, omitiendo.")
            continue
            
        with engine_sqlite.connect() as conn_sqlite:
            rows = conn_sqlite.execute(table_sqlite.select()).fetchall()
            if rows:
                # Convertir los resultados a diccionarios
                dicts = [dict(row._mapping) for row in rows]
                
                # Insertar en PostgreSQL
                conn_pg.execute(table_pg.insert(), dicts)
                print(f"  {len(dicts)} registros insertados.")
                
                # Sincronizar el autoincremental de la secuencia (crítico en Postgres tras forzar IDs)
                try:
                    # En SQLAlchemy 2.0+ hay que usar text()
                    conn_pg.execute(text(f"SELECT setval('{table_name}_id_seq', COALESCE((SELECT MAX(id) FROM {table_name}), 1));"))
                except Exception as e:
                    print(f"  Aviso: no se pudo sincronizar la secuencia de {table_name}: {e}")
            else:
                print(f"  Tabla vacía, nada que migrar.")

print("¡Migración completada exitosamente!")
