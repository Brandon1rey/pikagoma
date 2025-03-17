"""
Configuraciones y utilidades específicas para ejecutar la aplicación en Google Cloud Run.
Este archivo contiene optimizaciones y mejores prácticas para entornos sin estado como Cloud Run.
"""

import os
import logging
from flask import Flask, current_app, g
import tempfile

# Configuración de logging para Google Cloud Run
def setup_cloud_logging(app):
    """
    Configura el logging para Google Cloud Run integrándose con Cloud Logging.
    """
    if os.environ.get('CLOUD_RUN', 'False') == 'True':
        # Configurar logging para Cloud Run
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Desactivar logging a archivo para Cloud Run ya que usa sistema de archivos efímero
        app.config['DEBUG_LOG_TO_FILE'] = False
        app.config['DEBUG_CONSOLE_OUTPUT'] = True
        
        app.logger.info("Configuración de logging para Cloud Run activada")
    
    return app

# Gestión de archivos temporales para entornos sin estado
def get_temp_directory():
    """
    Devuelve el directorio adecuado para archivos temporales en Cloud Run.
    En Cloud Run, los archivos temporales deben estar en /tmp.
    """
    if os.environ.get('CLOUD_RUN', 'False') == 'True':
        # En Cloud Run, usar /tmp para archivos temporales
        return '/tmp'
    else:
        # En entorno de desarrollo, usar el directorio temporal del sistema
        return tempfile.gettempdir()

# Optimización de la configuración de base de datos para Cloud Run
def optimize_db_pool(app):
    """
    Optimiza la configuración del pool de conexiones de SQLAlchemy para Cloud Run.
    """
    if os.environ.get('CLOUD_RUN', 'False') == 'True':
        # SQLAlchemy engine options optimizadas para Cloud Run
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,                # Tamaño reducido del pool de conexiones
            'max_overflow': 10,            # Máximo número adicional de conexiones
            'pool_timeout': 30,            # Tiempo de espera para obtener conexión
            'pool_recycle': 1800,          # Reciclar conexiones cada 30 minutos
            'pool_pre_ping': True          # Verificar conexiones antes de usarlas
        }
        
        app.logger.info("Configuración de pool de base de datos optimizada para Cloud Run")
    
    return app

# Configuración para manejo de archivos estáticos
def configure_static_files(app):
    """
    Configura el manejo de archivos estáticos para Cloud Run.
    En producción, deberíamos usar Cloud Storage en lugar del sistema de archivos local.
    """
    if os.environ.get('CLOUD_RUN', 'False') == 'True':
        # Verificar si estamos en modo de emulación local
        if os.environ.get('EMULATE_CLOUD_ENVIRONMENT', 'False') == 'True':
            # En modo de emulación, usar el emulador local de Cloud Storage
            app.config['USE_CLOUD_STORAGE'] = True
            app.config['EMULATE_CLOUD_STORAGE'] = True
            bucket_name = os.environ.get('GCS_BUCKET_NAME', 'local-bucket')
            app.logger.info(f"Usando emulador local de Cloud Storage: {bucket_name}")
            
            # Configurar directorio de uploads para emulación
            upload_folder = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
            app.config['UPLOAD_FOLDER'] = upload_folder
            # Crear el directorio si no existe
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            app.logger.info(f"Directorio de uploads configurado en: {upload_folder}")
        else:
            # En Cloud Run real, verificar si tenemos un bucket configurado
            bucket_name = os.environ.get('GCS_BUCKET_NAME')
            
            if bucket_name:
                # Configurar para usar Cloud Storage para uploads
                app.config['USE_CLOUD_STORAGE'] = True
                app.config['EMULATE_CLOUD_STORAGE'] = False
                app.logger.info(f"Usando Cloud Storage para archivos: {bucket_name}")
            else:
                app.logger.warning("No se ha configurado GCS_BUCKET_NAME, usando almacenamiento local")
                # Configurar directorio temporal para uploads en Cloud Run
                app.config['UPLOAD_FOLDER'] = os.path.join(get_temp_directory(), 'uploads')
                # Crear el directorio si no existe
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    return app

# Función para aplicar todas las optimizaciones de Cloud Run
def optimize_for_cloud_run(app):
    """
    Aplica todas las optimizaciones para Google Cloud Run.
    """
    # Verificar si estamos en Cloud Run
    if os.environ.get('CLOUD_RUN', 'False') == 'True':
        app.logger.info("Iniciando optimizaciones para Google Cloud Run")
        
        # Detectar si estamos en modo de emulación
        if os.environ.get('EMULATE_CLOUD_ENVIRONMENT', 'False') == 'True':
            app.logger.info("Modo de emulación de Cloud Run activado")
        
        # Aplicar todas las optimizaciones
        app = setup_cloud_logging(app)
        app = optimize_db_pool(app)
        app = configure_static_files(app)
        
        # Configuración adicional específica para Cloud Run
        app.config['PREFERRED_URL_SCHEME'] = 'https'  # Forzar HTTPS
        
        # Establecer timeouts adecuados
        app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {
            'connect_timeout': 10  # Timeout de conexión en segundos
        }
        
        app.logger.info("Optimizaciones para Google Cloud Run completadas")
    
    return app 