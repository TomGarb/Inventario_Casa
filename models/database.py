from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    telegram_chat_id = db.Column(db.String(50), unique=True, nullable=True)
    telegram_link_token = db.Column(db.String(10), unique=True, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_tablet = db.Column(db.Boolean, default=False)
    
    # Nuevas preferencias de notificaciones
    recibir_resumen_matutino = db.Column(db.Boolean, default=True)
    recibir_alertas_vencimiento = db.Column(db.Boolean, default=True)
    recibir_recordatorios_tareas = db.Column(db.Boolean, default=True)

class ConfiguracionGlobal(db.Model):
    __tablename__ = 'configuracion_global'
    id = db.Column(db.Integer, primary_key=True)
    grupo_principal_telegram_id = db.Column(db.String(50), nullable=True)
    hora_alerta_stock = db.Column(db.String(5), default="10:00")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'telegram_chat_id': self.telegram_chat_id,
            'is_admin': self.is_admin,
            'recibir_resumen_matutino': self.recibir_resumen_matutino,
            'recibir_alertas_vencimiento': self.recibir_alertas_vencimiento,
            'recibir_recordatorios_tareas': self.recibir_recordatorios_tareas
        }

usuario_tarea = db.Table('usuario_tarea',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True),
    db.Column('tarea_id', db.Integer, db.ForeignKey('tareas.id'), primary_key=True)
)

usuario_modelo_tarea = db.Table('usuario_modelo_tarea',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True),
    db.Column('modelo_tarea_id', db.Integer, db.ForeignKey('modelo_tareas.id'), primary_key=True)
)

class ModeloTarea(db.Model):
    __tablename__ = 'modelo_tareas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    prioridad = db.Column(db.String(50), default='Esencial')
    tipo_frecuencia = db.Column(db.String(50), default='dias')
    valor_frecuencia = db.Column(db.String(50), default='1')
    alternar = db.Column(db.Boolean, default=True)
    fecha_ultima_ejecucion = db.Column(db.Date, nullable=True)
    
    usuarios = db.relationship('Usuario', secondary=usuario_modelo_tarea, lazy='subquery',
        backref=db.backref('modelos', lazy=True))
        
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'prioridad': self.prioridad,
            'tipo_frecuencia': self.tipo_frecuencia,
            'valor_frecuencia': self.valor_frecuencia,
            'alternar': self.alternar,
            'fecha_ultima_ejecucion': self.fecha_ultima_ejecucion.isoformat() if self.fecha_ultima_ejecucion else None,
            'usuarios': [{'id': u.id, 'username': u.username} for u in self.usuarios]
        }

class Tarea(db.Model):
    __tablename__ = 'tareas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    prioridad = db.Column(db.String(50), default='Esencial')
    tipo_frecuencia = db.Column(db.String(50), default='dias')
    valor_frecuencia = db.Column(db.String(50), default='1')
    fecha_ultima_ejecucion = db.Column(db.Date, nullable=True)
    fecha_programada = db.Column(db.Date, nullable=True)
    alternar = db.Column(db.Boolean, default=True)
    completada = db.Column(db.Boolean, default=False)
    modelo_id = db.Column(db.Integer, db.ForeignKey('modelo_tareas.id'), nullable=True)
    
    usuarios = db.relationship('Usuario', secondary=usuario_tarea, lazy='subquery',
        backref=db.backref('tareas_instancias', lazy=True))
        
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'prioridad': self.prioridad,
            'tipo_frecuencia': self.tipo_frecuencia,
            'valor_frecuencia': self.valor_frecuencia,
            'alternar': self.alternar,
            'completada': self.completada,
            'fecha_programada': self.fecha_programada.isoformat() if self.fecha_programada else (self.fecha_ultima_ejecucion.isoformat() if self.fecha_ultima_ejecucion else None),
            'modelo_id': self.modelo_id,
            'usuarios': [{'id': u.id, 'username': u.username} for u in self.usuarios]
        }

class HistorialTarea(db.Model):
    __tablename__ = 'historial_tareas'
    id = db.Column(db.Integer, primary_key=True)
    tarea_id = db.Column(db.Integer, db.ForeignKey('tareas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

class SaltoTarea(db.Model):
    __tablename__ = 'salto_tareas'
    id = db.Column(db.Integer, primary_key=True)
    tarea_id = db.Column(db.Integer, db.ForeignKey('tareas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    motivo = db.Column(db.String(255), nullable=False)

class Sala(db.Model):
    __tablename__ = 'salas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    piso = db.Column(db.String(50), nullable=True)
    ubicaciones = db.relationship('Ubicacion', backref='sala', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'piso': self.piso,
            'ubicaciones': [u.to_dict() for u in self.ubicaciones]
        }

class Ubicacion(db.Model):
    __tablename__ = 'ubicaciones'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    sala_id = db.Column(db.Integer, db.ForeignKey('salas.id'), nullable=False)
    sub_ubicaciones = db.relationship('SubUbicacion', backref='ubicacion', lazy=True, cascade="all, delete-orphan")
    productos = db.relationship('Producto', backref='rel_ubicacion', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'sala_id': self.sala_id,
            'sub_ubicaciones': [su.to_dict() for su in self.sub_ubicaciones]
        }

class SubUbicacion(db.Model):
    __tablename__ = 'sub_ubicaciones'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    ubicacion_id = db.Column(db.Integer, db.ForeignKey('ubicaciones.id'), nullable=False)
    productos = db.relationship('Producto', backref='rel_sub_ubicacion', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'ubicacion_id': self.ubicacion_id
        }

class Comercio(db.Model):
    __tablename__ = 'comercios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    productos = db.relationship('Producto', backref='rel_comercio', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre
        }

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    stock_actual = db.Column(db.Float, default=0.0)
    stock_minimo = db.Column(db.Float, default=1.0)
    unidad_medida = db.Column(db.String(20), default='unidades')
    en_lista = db.Column(db.Boolean, default=False)
    es_temporal = db.Column(db.Boolean, default=False)
    fecha_vencimiento = db.Column(db.Date, nullable=True)
    fecha_ultima_compra = db.Column(db.Date, nullable=True)
    
    ubicacion_id = db.Column(db.Integer, db.ForeignKey('ubicaciones.id'), nullable=True)
    sub_ubicacion_id = db.Column(db.Integer, db.ForeignKey('sub_ubicaciones.id'), nullable=True)
    comercio_id = db.Column(db.Integer, db.ForeignKey('comercios.id'), nullable=True)

    def to_dict(self):
        ubi_nombre = self.rel_ubicacion.nombre if self.rel_ubicacion else None
        sub_nombre = self.rel_sub_ubicacion.nombre if self.rel_sub_ubicacion else None
        sala_nombre = self.rel_ubicacion.sala.nombre if self.rel_ubicacion and self.rel_ubicacion.sala else None
        comercio_nombre = self.rel_comercio.nombre if self.rel_comercio else "Sin Comercio"
        
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'ubicacion_id': self.ubicacion_id,
            'sub_ubicacion_id': self.sub_ubicacion_id,
            'comercio_id': self.comercio_id,
            'ubicacion': ubi_nombre,
            'sub_ubicacion': sub_nombre,
            'sala': sala_nombre,
            'comercio': comercio_nombre,
            'stock_actual': self.stock_actual,
            'stock_minimo': self.stock_minimo,
            'unidad_medida': self.unidad_medida,
            'en_lista': self.en_lista,
            'es_temporal': self.es_temporal,
            'fecha_vencimiento': self.fecha_vencimiento.isoformat() if self.fecha_vencimiento else None,
            'fecha_ultima_compra': self.fecha_ultima_compra.isoformat() if self.fecha_ultima_compra else None
        }

class Movimiento(db.Model):
    __tablename__ = 'movimientos'
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(255), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=True)
    tipo = db.Column(db.String(50), nullable=True)
    cantidad = db.Column(db.Float, default=0.0)

    rel_producto = db.relationship('Producto', backref='movimientos', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'descripcion': self.descripcion,
            'fecha': self.fecha.isoformat(),
            'producto_id': self.producto_id,
            'tipo': self.tipo,
            'cantidad': self.cantidad,
            'producto_nombre': self.rel_producto.nombre if self.rel_producto else None
        }

class Gasto(db.Model):
    __tablename__ = 'gastos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    imagen_ticket_url = db.Column(db.String(500), nullable=True)
    
    pagador = db.relationship('Usuario', backref='gastos_pagados')
    divisiones = db.relationship('DivisionGasto', backref='rel_gasto', cascade='all, delete-orphan')
    detalles = db.relationship('DetalleGasto', backref='rel_gasto', cascade='all, delete-orphan')

class DetalleGasto(db.Model):
    __tablename__ = 'detalle_gastos'
    id = db.Column(db.Integer, primary_key=True)
    gasto_id = db.Column(db.Integer, db.ForeignKey('gastos.id'), nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    cantidad = db.Column(db.Float, default=1.0)
    precio_unitario = db.Column(db.Float, nullable=False)

class DivisionGasto(db.Model):
    __tablename__ = 'division_gastos'
    id = db.Column(db.Integer, primary_key=True)
    gasto_id = db.Column(db.Integer, db.ForeignKey('gastos.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    monto_adeudado = db.Column(db.Float, nullable=False)
    esta_pagado = db.Column(db.Boolean, default=False)
    
    usuario = db.relationship('Usuario', backref='deudas')

class EventoLogistico(db.Model):
    __tablename__ = 'eventos_logisticos'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_fin = db.Column(db.DateTime, nullable=True)
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    asignado_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    frecuencia = db.Column(db.String(20), default='none')
    
    creador = db.relationship('Usuario', foreign_keys=[creador_id], backref='eventos_creados')
    asignado = db.relationship('Usuario', foreign_keys=[asignado_id], backref='eventos_asignados')

class HorarioComidas(db.Model):
    __tablename__ = 'horario_comidas'
    id = db.Column(db.Integer, primary_key=True)
    tipo_comida = db.Column(db.String(50), nullable=False) # Desayuno, Almuerzo, Merienda, Cena
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)

class IngredienteReceta(db.Model):
    __tablename__ = 'ingrediente_receta'
    receta_id = db.Column(db.Integer, db.ForeignKey('recetas.id'), primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), primary_key=True)
    cantidad_requerida = db.Column(db.Float, nullable=False, default=1.0)
    
    producto = db.relationship('Producto')
    receta = db.relationship('Receta', back_populates='ingredientes')

class Receta(db.Model):
    __tablename__ = 'recetas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(50), nullable=False) # Desayuno, Almuerzo, Merienda, Cena
    es_rapida = db.Column(db.Boolean, default=False)
    
    ingredientes = db.relationship('IngredienteReceta', back_populates='receta', cascade="all, delete-orphan")

class MenuSemanal(db.Model):
    __tablename__ = 'menu_semanal'
    id = db.Column(db.Integer, primary_key=True)
    dia_semana = db.Column(db.String(20), nullable=False) # Lunes a Domingo
    tipo_comida = db.Column(db.String(50), nullable=False) # Desayuno, Almuerzo, Merienda, Cena
    receta_id = db.Column(db.Integer, db.ForeignKey('recetas.id'), nullable=False)
    fecha_asignada = db.Column(db.Date, nullable=False)
    
    receta = db.relationship('Receta', backref='asignaciones')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))