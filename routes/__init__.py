from flask import Blueprint

from .auth import auth_bp
from .finanzas import finanzas_bp
from .main import main_bp
from .inventario import inventario_bp
from .tareas import tareas_bp
from .añadir_rapido import añadir_rapido_bp
from .marcar_comprado import marcar_comprado_bp
from .menus import menus_bp
from .logistica import logistica_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(finanzas_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(tareas_bp)
    app.register_blueprint(añadir_rapido_bp)
    app.register_blueprint(marcar_comprado_bp)
    app.register_blueprint(menus_bp)
    app.register_blueprint(logistica_bp)
