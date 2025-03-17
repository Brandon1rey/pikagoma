# Guardar este código en un archivo llamado "init_categorias.py" en la raíz del proyecto
from app import create_app, db
from app.models import CategoriaGasto

def inicializar_categorias():
    """Inicializa solo las categorías de gastos"""
    # Crear instancia de la app
    app = create_app('development')
    
    with app.app_context():
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

if __name__ == "__main__":
    inicializar_categorias()