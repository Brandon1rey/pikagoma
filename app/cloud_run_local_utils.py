"""
Utilidades para emular servicios de Google Cloud en entorno local.
Este módulo proporciona funciones que simulan el comportamiento de
servicios de Google Cloud cuando se ejecuta la aplicación localmente.
"""

import os
import logging
import tempfile
import shutil
from pathlib import Path
from flask import current_app

# Configurar logging
logger = logging.getLogger(__name__)

class LocalStorageEmulator:
    """
    Emula el comportamiento de Google Cloud Storage en entorno local.
    Proporciona una interfaz similar a la de Cloud Storage pero utilizando
    el sistema de archivos local.
    """
    
    def __init__(self, bucket_name=None):
        """
        Inicializa el emulador de almacenamiento.
        
        Args:
            bucket_name: Nombre del bucket a emular (opcional)
        """
        self.bucket_name = bucket_name or os.environ.get('GCS_BUCKET_NAME', 'local-bucket')
        self.root_dir = os.path.join(tempfile.gettempdir(), 'gcs_emulator', self.bucket_name)
        
        # Crear directorio si no existe
        os.makedirs(self.root_dir, exist_ok=True)
        logger.info(f"Emulador de Cloud Storage inicializado en: {self.root_dir}")
    
    def upload_file(self, source_file_path, destination_blob_name):
        """
        Sube un archivo al bucket emulado.
        
        Args:
            source_file_path: Ruta al archivo local a subir
            destination_blob_name: Nombre del blob en el bucket
            
        Returns:
            URL pública del archivo (simulada)
        """
        # Crear estructura de directorios si es necesario
        dest_path = os.path.join(self.root_dir, destination_blob_name)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Copiar archivo
        try:
            shutil.copy2(source_file_path, dest_path)
            logger.info(f"Archivo copiado a: {dest_path}")
            
            # Generar URL simulada
            public_url = f"/static/uploads/{destination_blob_name}"
            return public_url
        except Exception as e:
            logger.error(f"Error al copiar archivo: {e}")
            raise
    
    def download_file(self, blob_name, destination_file_path):
        """
        Descarga un archivo del bucket emulado.
        
        Args:
            blob_name: Nombre del blob en el bucket
            destination_file_path: Ruta donde guardar el archivo
            
        Returns:
            bool: True si la operación fue exitosa
        """
        source_path = os.path.join(self.root_dir, blob_name)
        
        try:
            # Crear directorio destino si no existe
            os.makedirs(os.path.dirname(destination_file_path), exist_ok=True)
            
            # Copiar archivo
            shutil.copy2(source_path, destination_file_path)
            logger.info(f"Archivo descargado a: {destination_file_path}")
            return True
        except Exception as e:
            logger.error(f"Error al descargar archivo: {e}")
            return False
    
    def delete_file(self, blob_name):
        """
        Elimina un archivo del bucket emulado.
        
        Args:
            blob_name: Nombre del blob en el bucket
            
        Returns:
            bool: True si la operación fue exitosa
        """
        file_path = os.path.join(self.root_dir, blob_name)
        
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Archivo eliminado: {file_path}")
                return True
            else:
                logger.warning(f"Archivo no encontrado: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Error al eliminar archivo: {e}")
            return False
    
    def list_files(self, prefix=None):
        """
        Lista archivos en el bucket emulado.
        
        Args:
            prefix: Prefijo para filtrar archivos (opcional)
            
        Returns:
            list: Lista de nombres de archivos
        """
        search_dir = self.root_dir
        if prefix:
            search_dir = os.path.join(self.root_dir, prefix)
        
        result = []
        try:
            if os.path.exists(search_dir):
                for root, _, files in os.walk(search_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.root_dir)
                        result.append(rel_path)
            return result
        except Exception as e:
            logger.error(f"Error al listar archivos: {e}")
            return []

def get_storage_client():
    """
    Devuelve un cliente de almacenamiento apropiado según el entorno.
    En entorno local, devuelve el emulador de almacenamiento.
    En Cloud Run real, devuelve el cliente de Google Cloud Storage.
    
    Returns:
        object: Cliente de almacenamiento
    """
    if os.environ.get('EMULATE_CLOUD_ENVIRONMENT', 'False') == 'True':
        # Usar emulador local
        bucket_name = os.environ.get('GCS_BUCKET_NAME', 'local-bucket')
        return LocalStorageEmulator(bucket_name)
    else:
        # En entorno real, usar cliente de Google Cloud Storage
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket_name = os.environ.get('GCS_BUCKET_NAME')
            if not bucket_name:
                raise ValueError("GCS_BUCKET_NAME no está configurado")
            bucket = client.bucket(bucket_name)
            return bucket
        except ImportError:
            logger.error("google-cloud-storage no está instalado")
            raise

def is_cloud_run_emulation():
    """
    Determina si la aplicación está ejecutándose en modo de emulación de Cloud Run.
    
    Returns:
        bool: True si está en modo de emulación
    """
    return (
        os.environ.get('CLOUD_RUN', 'False') == 'True' and
        os.environ.get('EMULATE_CLOUD_ENVIRONMENT', 'False') == 'True'
    ) 