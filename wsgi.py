from app import create_app
import os

# Obtener entorno de la variable de entorno o usar "production" para Cloud Run
config_name = os.environ.get('FLASK_CONFIG', 'production')

# Crear la aplicación con la configuración correspondiente
app = create_app(config_name)

if __name__ == '__main__':
    # Obtener el puerto del entorno o usar 8080 por defecto (estándar para Cloud Run)
    port = int(os.environ.get('PORT', 8080))
    
    # En entorno de desarrollo, habilitar modo debug
    debug = config_name == 'development'
    
    # Iniciar servidor
    app.run(host='0.0.0.0', port=port, debug=debug) 