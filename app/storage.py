from google.cloud import storage
import os
from flask import current_app
import uuid
from werkzeug.utils import secure_filename

def upload_to_cloud_storage(file, destination_folder):
    """Sube un archivo a Google Cloud Storage y devuelve su URL pública"""
    from flask import current_app, has_app_context
    
    # Verificar que estamos dentro de un contexto de aplicación
    if not has_app_context():
        raise RuntimeError(
            "upload_to_cloud_storage() requiere un contexto de aplicación Flask activo. "
            "Asegúrese de llamar a esta función dentro de 'with app.app_context():'")
            
    # Obtiene el nombre del bucket desde las variables de entorno
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    
    # Si no hay un bucket configurado, guarda localmente (para desarrollo)
    if not bucket_name:
        # Guardar en el sistema de archivos local
        filename = secure_filename(file.filename)
        # Generar nombre único para evitar colisiones
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        local_path = os.path.join(current_app.config['UPLOAD_FOLDER'], destination_folder)
        
        # Crear directorio si no existe
        os.makedirs(local_path, exist_ok=True)
        
        # Guardar archivo
        file_path = os.path.join(local_path, unique_filename)
        file.save(file_path)
        
        # Devolver ruta relativa para desarrollo
        return f"/static/uploads/{destination_folder}/{unique_filename}"
    
    # Crea un cliente de Cloud Storage
    storage_client = storage.Client()
    
    # Obtiene el bucket
    bucket = storage_client.bucket(bucket_name)
    
    # Crea un nombre único para el archivo
    original_filename = secure_filename(file.filename)
    filename = f"{uuid.uuid4().hex}_{original_filename}"
    destination = f"{destination_folder}/{filename}"
    
    # Crea un nuevo blob y sube el archivo
    blob = bucket.blob(destination)
    
    # Posicionar al inicio del archivo para asegurar carga completa
    file.seek(0)
    blob.upload_from_file(file, content_type=file.content_type)
    
    # Hace el blob públicamente accesible
    blob.make_public()
    
    # Devuelve la URL pública
    return blob.public_url

def delete_from_cloud_storage(file_url):
    """Elimina un archivo de Google Cloud Storage basado en su URL"""
    from flask import current_app, has_app_context
    
    # Verificar que estamos dentro de un contexto de aplicación
    if not has_app_context():
        raise RuntimeError(
            "delete_from_cloud_storage() requiere un contexto de aplicación Flask activo. "
            "Asegúrese de llamar a esta función dentro de 'with app.app_context():'")
            
    bucket_name = os.environ.get('GCS_BUCKET_NAME')
    
    # Si es una URL de desarrollo local, eliminar del sistema de archivos
    if not bucket_name or '/static/uploads/' in file_url:
        try:
            # Convertir la URL relativa a ruta del sistema de archivos
            if file_url.startswith('/static/uploads/'):
                file_path = os.path.join(
                    current_app.root_path, 
                    'static', 
                    file_url.replace('/static/', '')
                )
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return True
        except Exception as e:
            current_app.logger.error(f"Error al eliminar archivo local: {e}")
        return False
    
    try:
        # Extraer el nombre del objeto de la URL
        # Formato típico: https://storage.googleapis.com/BUCKET_NAME/path/to/file.jpg
        parts = file_url.replace('https://storage.googleapis.com/', '').split('/', 1)
        if len(parts) < 2 or parts[0] != bucket_name:
            current_app.logger.error(f"URL de archivo inválida: {file_url}")
            return False
        
        object_name = parts[1]
        
        # Eliminar el archivo
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.delete()
        
        return True
    except Exception as e:
        current_app.logger.error(f"Error al eliminar archivo de Cloud Storage: {e}")
        return False 