from flask import Flask, g, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from config import config
import os
import functools  # Importación para evitar errores con decoradores
import json  # Añadir importación de json al inicio del archivo

# Inicialización de extensiones
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
mail = Mail()

# Función para inicializar categorías de gastos
def inicializar_categorias(app):
    with app.app_context():
        # Importamos aquí para evitar importaciones circulares
        from app.models import CategoriaGasto
        
        # Categorías de gastos requeridas
        categorias_gasto = [
            "Materias primas", "Publicidad", "Empaquetado", "Viáticos",
            "Servicios", "Renta", "Equipo", "Otros"
        ]
        
        # Agregar categorías si no existen
        for nombre_categoria in categorias_gasto:
            categoria = CategoriaGasto.query.filter_by(nombre=nombre_categoria).first()
            if categoria is None:
                print(f"Creando categoría: {nombre_categoria}")
                categoria = CategoriaGasto(nombre=nombre_categoria)
                db.session.add(categoria)
            else:
                print(f"La categoría {nombre_categoria} ya existe")
        
        # Guardar cambios
        db.session.commit()
        print("Categorías de gastos inicializadas correctamente")

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Verificar que la URI de la base de datos esté configurada
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        print("ADVERTENCIA: SQLALCHEMY_DATABASE_URI no está configurado en la configuración")
        # Establecer un valor por defecto si no está configurado
        app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:aguilarm78@localhost/pikagoma_db'
        print(f"Se ha configurado un valor por defecto: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Ajustar configuración de SQLAlchemy para MySQL si es necesario
    if 'mysql' in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
        # Configurar opciones de conexión para PyMySQL para evitar problemas de compatibilidad
        if 'SQLALCHEMY_ENGINE_OPTIONS' not in app.config:
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        
        if 'connect_args' not in app.config['SQLALCHEMY_ENGINE_OPTIONS']:
            app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {}
        
        # Eliminar el parámetro auth_plugin si existe (causa problemas en algunas versiones)
        app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'].pop('auth_plugin', None)
        
        # Verificar si hay configuraciones específicas para PyMySQL
        pymysql_kwargs = os.environ.get('PYMYSQL_CONNECT_KWARGS')
        if pymysql_kwargs:
            try:
                connect_kwargs = json.loads(pymysql_kwargs)
                # Eliminar auth_plugin si está presente en las configuraciones adicionales
                connect_kwargs.pop('auth_plugin', None)
                # Añadir las configuraciones de PyMySQL
                app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'].update(connect_kwargs)
                print(f"Configuración de MySQL actualizada: {app.config['SQLALCHEMY_ENGINE_OPTIONS']}")
            except json.JSONDecodeError:
                print(f"Advertencia: No se pudo parsear PYMYSQL_CONNECT_KWARGS: {pymysql_kwargs}")
    
    # Asegurar que existe el directorio de instancia
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Asegurar que existe el directorio de uploads
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'])
    except OSError:
        pass
    
    # Inicializar extensiones con la app
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Registrar inicio de aplicación
    print(f"Aplicación iniciando con configuración: {config_name}")
    
    # Aplicar optimizaciones para Google Cloud Run si corresponde
    if os.environ.get('CLOUD_RUN', 'False') == 'True':
        from app.cloud_run_config import optimize_for_cloud_run
        app = optimize_for_cloud_run(app)
    
    # Registrar manejadores de errores personalizados
    @app.errorhandler(401)
    def unauthorized(e):
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    # Registro de blueprints existentes
    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from app.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    from app.ventas import ventas as ventas_blueprint
    app.register_blueprint(ventas_blueprint, url_prefix='/ventas')
    
    from app.estadisticas import estadisticas as estadisticas_blueprint
    app.register_blueprint(estadisticas_blueprint, url_prefix='/estadisticas')
    
    from app.reportes import reportes as reportes_blueprint
    app.register_blueprint(reportes_blueprint, url_prefix='/reportes')
    
    # Registro de nuevos blueprints
    from app.gastos import gastos as gastos_blueprint
    app.register_blueprint(gastos_blueprint, url_prefix='/gastos')
    
    from app.inventario import inventario as inventario_blueprint
    app.register_blueprint(inventario_blueprint, url_prefix='/inventario')
    
    from app.debug import debug as debug_blueprint
    app.register_blueprint(debug_blueprint, url_prefix='/debug')
    
    # Inicializar categorías de gastos después de que la aplicación esté configurada
    with app.app_context():
        try:
            inicializar_categorias(app)
        except Exception as e:
            print(f"Error al inicializar categorías: {e}")
            # No detenemos la aplicación por errores en la inicialización de categorías
    
    # Contexto de shell para pruebas de consola
    @app.shell_context_processor
    def make_shell_context():
        return dict(app=app, db=db, Mail=mail)
    
    # Crear todas las tablas solo en modo de desarrollo
    if config_name == 'development':
        with app.app_context():
            try:
                db.create_all()
                print("Tablas creadas correctamente")
            except Exception as e:
                print(f"Error al crear tablas: {str(e)}")
    
    return app