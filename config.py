import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'clave-secreta-desarrollo')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    
    # Configuración de correo electrónico
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'tu_correo@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'tu_contraseña')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'admin@gomitasenchiladas.com')
    
    # Configuración de sesión
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Configuración de administrador
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@gomitasenchiladas.com')
    
    # Configuración de carga de archivos
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max-limit
    
    # Configuración de depuración
    DEBUG_ENABLED = os.environ.get('DEBUG_ENABLED', 'True') == 'True'
    DEBUG_LEVEL = os.environ.get('DEBUG_LEVEL', 'DEBUG')
    DEBUG_LOG_TO_FILE = os.environ.get('DEBUG_LOG_TO_FILE', 'True') == 'True'
    DEBUG_LOG_DIR = os.environ.get('DEBUG_LOG_DIR', 'logs')
    DEBUG_CONSOLE_OUTPUT = os.environ.get('DEBUG_CONSOLE_OUTPUT', 'True') == 'True'
    DEBUG_INCLUDE_REQUEST_INFO = os.environ.get('DEBUG_INCLUDE_REQUEST_INFO', 'True') == 'True'
    DEBUG_PROFILE_SLOW_FUNCTIONS = os.environ.get('DEBUG_PROFILE_SLOW_FUNCTIONS', 'True') == 'True'
    DEBUG_SLOW_FUNCTION_THRESHOLD = float(os.environ.get('DEBUG_SLOW_FUNCTION_THRESHOLD', '0.5'))
    
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'

class ProductionConfig(Config):
    DEBUG = False
    # Formato: mysql+pymysql://usuario:contraseña@/nombre_base_datos?unix_socket=/cloudsql/ID_PROYECTO:REGION:INSTANCIA
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Configuración para PythonAnywhere (mantenemos por compatibilidad)
class PythonAnywhereConfig(ProductionConfig):
    # Ajusta esta URI para que coincida con tu configuración en PythonAnywhere
    SQLALCHEMY_DATABASE_URI = 'mysql://tuusuario:tucontraseña@tuusuario.mysql.pythonanywhere-services.com/tuusuario$gomitas'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'pythonanywhere': PythonAnywhereConfig,
    'default': DevelopmentConfig
} 
