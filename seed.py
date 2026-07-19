from app import app, db, Sala, Ubicacion, SubUbicacion, Comercio, Producto
import random
from datetime import datetime, timedelta

def seed_database():
    with app.app_context():
        print("Iniciando carga masiva de datos (Seed)...")
        
        # 1. Crear Salas
        salas_data = ['Cocina', 'Baño', 'Lavadero', 'Garaje']
        salas = {}
        for s_nombre in salas_data:
            sala = Sala.query.filter_by(nombre=s_nombre).first()
            if not sala:
                sala = Sala(nombre=s_nombre)
                db.session.add(sala)
            salas[s_nombre] = sala
        db.session.commit()

        # 2. Crear Ubicaciones
        ubicaciones_data = {
            'Alacena Principal': salas['Cocina'],
            'Heladera': salas['Cocina'],
            'Mueble Lavamanos': salas['Baño'],
            'Estantería Limpieza': salas['Lavadero'],
            'Armario Herramientas': salas['Garaje']
        }
        ubicaciones = {}
        for u_nombre, sala in ubicaciones_data.items():
            ubi = Ubicacion.query.filter_by(nombre=u_nombre, sala_id=sala.id).first()
            if not ubi:
                ubi = Ubicacion(nombre=u_nombre, sala_id=sala.id)
                db.session.add(ubi)
            ubicaciones[u_nombre] = ubi
        db.session.commit()

        # 3. Crear Sub Ubicaciones
        sub_ubicaciones_data = {
            'Estante Superior': ubicaciones['Alacena Principal'],
            'Estante Medio': ubicaciones['Alacena Principal'],
            'Cajón Verduras': ubicaciones['Heladera'],
            'Puerta Heladera': ubicaciones['Heladera'],
            'Cajón Inferior': ubicaciones['Mueble Lavamanos'],
            'Repisa Superior': ubicaciones['Estantería Limpieza'],
            'Caja 1': ubicaciones['Armario Herramientas']
        }
        sub_ubicaciones = {}
        for su_nombre, ubi in sub_ubicaciones_data.items():
            sub = SubUbicacion.query.filter_by(nombre=su_nombre, ubicacion_id=ubi.id).first()
            if not sub:
                sub = SubUbicacion(nombre=su_nombre, ubicacion_id=ubi.id)
                db.session.add(sub)
            sub_ubicaciones[su_nombre] = sub
        db.session.commit()

        # 4. Crear Comercios
        comercios_data = ['Supermercado Coto', 'Verdulería Don Pepe', 'Carnicería Los Hermanos', 'Farmacia', 'Ferretería']
        comercios = {}
        for c_nombre in comercios_data:
            comercio = Comercio.query.filter_by(nombre=c_nombre).first()
            if not comercio:
                comercio = Comercio(nombre=c_nombre)
                db.session.add(comercio)
            comercios[c_nombre] = comercio
        db.session.commit()

        # 5. Crear Productos
        productos_data = [
            # Cocina - Alacena
            {'nombre': 'Fideos Tirabuzón', 'ubicacion': 'Alacena Principal', 'sub': 'Estante Superior', 'comercio': 'Supermercado Coto', 'medida': 'unidades'},
            {'nombre': 'Arroz Blanco', 'ubicacion': 'Alacena Principal', 'sub': 'Estante Medio', 'comercio': 'Supermercado Coto', 'medida': 'kg'},
            {'nombre': 'Aceite de Girasol', 'ubicacion': 'Alacena Principal', 'sub': 'Estante Medio', 'comercio': 'Supermercado Coto', 'medida': 'L'},
            # Cocina - Heladera
            {'nombre': 'Tomates Redondos', 'ubicacion': 'Heladera', 'sub': 'Cajón Verduras', 'comercio': 'Verdulería Don Pepe', 'medida': 'kg'},
            {'nombre': 'Cebollas', 'ubicacion': 'Heladera', 'sub': 'Cajón Verduras', 'comercio': 'Verdulería Don Pepe', 'medida': 'kg'},
            {'nombre': 'Leche Descremada', 'ubicacion': 'Heladera', 'sub': 'Puerta Heladera', 'comercio': 'Supermercado Coto', 'medida': 'L'},
            {'nombre': 'Carne Picada', 'ubicacion': 'Heladera', 'sub': 'Puerta Heladera', 'comercio': 'Carnicería Los Hermanos', 'medida': 'kg'},
            # Baño
            {'nombre': 'Papel Higiénico (x4)', 'ubicacion': 'Mueble Lavamanos', 'sub': 'Cajón Inferior', 'comercio': 'Supermercado Coto', 'medida': 'unidades'},
            {'nombre': 'Jabón de tocador', 'ubicacion': 'Mueble Lavamanos', 'sub': 'Cajón Inferior', 'comercio': 'Farmacia', 'medida': 'unidades'},
            # Lavadero
            {'nombre': 'Jabón Líquido Ropa', 'ubicacion': 'Estantería Limpieza', 'sub': 'Repisa Superior', 'comercio': 'Supermercado Coto', 'medida': 'L'},
            {'nombre': 'Lavandina', 'ubicacion': 'Estantería Limpieza', 'sub': 'Repisa Superior', 'comercio': 'Supermercado Coto', 'medida': 'L'},
            # Garaje
            {'nombre': 'WD-40', 'ubicacion': 'Armario Herramientas', 'sub': 'Caja 1', 'comercio': 'Ferretería', 'medida': 'unidades'},
            {'nombre': 'Cinta Aisladora', 'ubicacion': 'Armario Herramientas', 'sub': 'Caja 1', 'comercio': 'Ferretería', 'medida': 'unidades'},
        ]

        hoy = datetime.now().date()
        nuevos_productos = 0
        for pd in productos_data:
            p_existente = Producto.query.filter_by(nombre=pd['nombre']).first()
            if not p_existente:
                ubi = ubicaciones[pd['ubicacion']]
                sub = sub_ubicaciones[pd['sub']]
                com = comercios[pd['comercio']]
                
                # Para mostrar las funcionalidades del Dashboard, algunos tendrán stock 0, otros por vencer, etc.
                stock_actual = random.choice([0, 1, 2, 5])
                stock_min = 1 if pd['medida'] == 'unidades' else 0.5
                en_lista = stock_actual <= stock_min
                
                # Simular vencimientos (algunos vencen pronto, otros no)
                vence_en = random.choice([None, 3, 5, 20, 60])
                fecha_venc = (hoy + timedelta(days=vence_en)) if vence_en else None
                
                # Simular inactividad (algunos se compraron hace mucho)
                inactivo_hace = random.choice([5, 10, 35, 40])
                fecha_compra = hoy - timedelta(days=inactivo_hace)

                nuevo_p = Producto(
                    nombre=pd['nombre'],
                    descripcion='Producto generado automáticamente (Seed).',
                    stock_actual=stock_actual,
                    stock_minimo=stock_min,
                    unidad_medida=pd['medida'],
                    en_lista=en_lista,
                    ubicacion_id=ubi.id,
                    sub_ubicacion_id=sub.id,
                    comercio_id=com.id,
                    fecha_vencimiento=fecha_venc,
                    fecha_ultima_compra=fecha_compra
                )
                db.session.add(nuevo_p)
                nuevos_productos += 1
                
        db.session.commit()
        print(f"Carga masiva completada: Se insertaron {nuevos_productos} productos de prueba distribuidos en toda la casa.")

if __name__ == '__main__':
    seed_database()
