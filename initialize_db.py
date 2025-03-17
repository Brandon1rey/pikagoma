from app import create_app, db
from app.models import User
import os

def init_db():
    print("Inicializando la base de datos...")
    
    # Crear la aplicación con configuración de desarrollo
    app = create_app('development')
    
    with app.app_context():
        # Verificar conexión a la base de datos
        try:
            # Intentar ejecutar una consulta simple
            # Nota: Usamos SQL directo "SELECT 1" por ser la forma más simple y universal
            # de comprobar que la conexión a la base de datos está funcionando
            from sqlalchemy import text
            result = db.session.execute(text("SELECT 1")).scalar()
            print(f"Conexión a la base de datos exitosa: {result}")
        except Exception as e:
            print(f"Error al conectar a la base de datos: {e}")
            print(f"URL de base de datos: {app.config.get('SQLALCHEMY_DATABASE_URI', 'No configurado')}")
            return
            
        # Crear todas las tablas
        try:
            db.create_all()
            print("Tablas creadas correctamente")
        except Exception as e:
            print(f"Error al crear tablas: {e}")
            return
        
        # Verificar si ya existe un usuario administrador
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creando usuario administrador...")
            admin = User(
                username='admin',
                email='brandon.ur17@gmail.com',
                nombre='Administrador',
                password='aguilarm78',  # Usa la misma contraseña que en otros lugares
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Usuario administrador creado correctamente")
        else:
            print("El usuario administrador ya existe")
            
        # Verificar tablas creadas
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tablas en la base de datos ({len(tables)}):")
        for table in tables:
            print(f"  - {table}")
        
if __name__ == "__main__":
    init_db()