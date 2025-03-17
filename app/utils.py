# app/utils.py
from datetime import datetime, timedelta
import pandas as pd
import hashlib
import random
import string
import logging
import functools
import traceback
import inspect
import time
import os
from sqlalchemy.exc import SQLAlchemyError
from app.constants import *

def format_datetime(dt):
    """Formatea una fecha y hora para mostrar"""
    if dt:
        return dt.strftime('%d-%m-%Y %H:%M')
    return ""

def get_current_month_name():
    """Obtiene el nombre del mes actual en español"""
    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    return meses[datetime.now().month - 1] 

# Funciones para debugging
def get_debug_module():
    """
    Importa el módulo de debug de manera segura, evitando importaciones circulares.
    Útil para que otros módulos puedan acceder a las funciones de logging de debug.
    """
    try:
        # En lugar de importar directamente, usamos importlib para evitar la importación circular
        import importlib
        debug_module = importlib.import_module('app.debug.routes')
        if hasattr(debug_module, 'add_debug_log'):
            return debug_module.add_debug_log
        else:
            # Si la función no existe, retorna una función que no hace nada
            def dummy_log(*args, **kwargs):
                pass
            return dummy_log
    except (ImportError, AttributeError):
        # Si no se puede importar, retorna una función que no hace nada
        def dummy_log(*args, **kwargs):
            pass
        return dummy_log

def debug_log_function(func):
    """
    Decorador para loguear la entrada y salida de funciones importantes.
    Uso: 
    from app.utils import debug_log_function
    
    @debug_log_function
    def mi_funcion():
        # código aquí
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        add_debug_log = get_debug_module()
        
        # Registra la entrada a la función
        module = func.__module__
        function = func.__name__
        
        # Usamos try/except para evitar errores en caso de problemas con el logger
        try:
            add_debug_log(module, function, f"Función llamada con args: {args}, kwargs: {kwargs}", include_stack=True, obj=func)
        except Exception:
            pass  # Si falla el logging, simplemente continuamos
        
        start_time = datetime.now()
        try:
            # Ejecuta la función
            result = func(*args, **kwargs)
            
            # Registra la salida exitosa con tiempo de ejecución
            execution_time = (datetime.now() - start_time).total_seconds()
            try:
                add_debug_log(module, function, f"Función ejecutada exitosamente en {execution_time:.6f} segundos")
            except Exception:
                pass  # Si falla el logging, simplemente continuamos
                
            return result
        except Exception as e:
            # Registra errores con tiempo de ejecución
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Error en {execution_time:.6f} segundos: {str(e)}\n{traceback.format_exc()}"
            try:
                add_debug_log(module, function, error_msg, level="ERROR", include_stack=True)
            except Exception:
                pass  # Si falla el logging, simplemente continuamos
            raise  # Re-lanza la excepción para que sea manejada normalmente
    
    return wrapper

# Función útil para debugear models y SQLAlchemy
def debug_db_operation(operation_name):
    """
    Decorador para loguear operaciones de base de datos.
    
    Uso:
    @debug_db_operation('create_user')
    def create_user(username, email):
        # código de creación de usuario
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            add_debug_log = get_debug_module()
            module = func.__module__
            function = func.__name__
            
            try:
                add_debug_log(
                    module, 
                    function, 
                    f"DB Operation '{operation_name}' started with args: {args}, kwargs: {kwargs}",
                    include_stack=True,
                    obj=func
                )
            except Exception:
                pass
            
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                try:
                    add_debug_log(
                        module, 
                        function, 
                        f"DB Operation '{operation_name}' completed successfully in {execution_time:.6f} seconds"
                    )
                except Exception:
                    pass
                    
                return result
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                error_msg = f"DB Operation '{operation_name}' failed in {execution_time:.6f} seconds: {str(e)}\n{traceback.format_exc()}"
                
                try:
                    add_debug_log(module, function, error_msg, level="ERROR", include_stack=True)
                except Exception:
                    pass
                    
                raise
        return wrapper
    return decorator

# Función útil para obtener stacktrace de una función
def get_function_stack(frame_depth=2):
    """Obtiene el stack trace actual para depuración"""
    stack = inspect.stack()
    if len(stack) <= frame_depth:
        return []
    
    # Extraer frames a partir de frame_depth
    frames = stack[frame_depth:]
    result = []
    
    for frame_info in frames:
        frame = frame_info.frame
        code = frame.f_code
        result.append({
            'filename': code.co_filename,
            'lineno': frame_info.lineno,
            'function': code.co_name,
            'module': frame.f_globals.get('__name__', 'unknown'),
            'locals': {k: str(v) for k, v in frame.f_locals.items() if not k.startswith('__')}
        })
    
    return result

# Clase para medir el tiempo de ejecución de bloques de código
class Timer:
    """
    Clase para medir el tiempo de ejecución de bloques de código.
    
    Uso:
    with Timer('nombre_operacion') as timer:
        # código a medir
    print(f"Tiempo transcurrido: {timer.elapsed} segundos")
    """
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.start_time = None
        self.elapsed = 0
        self.add_debug_log = get_debug_module()
    
    def __enter__(self):
        self.start_time = time.time()
        try:
            stack = get_function_stack(3)  # Obtener stack trace saltando el frame actual
            caller = stack[0] if stack else {'module': 'unknown', 'function': 'unknown'}
            
            self.add_debug_log(
                caller['module'],
                caller['function'],
                f"Timer '{self.operation_name}' started",
                include_stack=True
            )
        except Exception:
            pass
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time
        
        try:
            stack = get_function_stack(3)  # Obtener stack trace saltando el frame actual
            caller = stack[0] if stack else {'module': 'unknown', 'function': 'unknown'}
            
            if exc_type is not None:
                # Si ocurrió una excepción
                self.add_debug_log(
                    caller['module'],
                    caller['function'],
                    f"Timer '{self.operation_name}' stopped with error after {self.elapsed:.6f} seconds: {exc_val}",
                    level="ERROR",
                    include_stack=True
                )
            else:
                # Operación exitosa
                self.add_debug_log(
                    caller['module'],
                    caller['function'],
                    f"Timer '{self.operation_name}' completed in {self.elapsed:.6f} seconds"
                )
        except Exception:
            pass

class DeferredInventoryOperation:
    """
    Clase para gestionar operaciones de inventario diferidas.
    Almacena los cambios de inventario y los aplica después de que la transacción principal se complete.
    """
    _pending_operations = []

    @classmethod
    def register(cls, operation_type, producto_id, cantidad, motivo=None, user_id=None, venta_id=None, gasto_id=None):
        """
        Registra una operación de inventario para ser procesada más tarde.
        """
        cls._pending_operations.append({
            'type': operation_type,
            'producto_id': producto_id,
            'cantidad': cantidad,
            'motivo': motivo,
            'user_id': user_id,
            'venta_id': venta_id,
            'gasto_id': gasto_id
        })
    
    @classmethod
    def process_pending_operations(cls, db_session):
        """
        Procesa las operaciones pendientes de inventario de manera eficiente,
        agrupando por producto_id para reducir consultas a la base de datos.
        """
        from app.models import Inventario, MovimientoInventario
        from sqlalchemy.orm import joinedload
        
        operations = cls._pending_operations.copy()
        cls._pending_operations = []
        
        if not operations:
            return
        
        # Agrupar operaciones por producto_id para procesarlas eficientemente
        productos_dict = {}
        for op in operations:
            if op['producto_id'] not in productos_dict:
                productos_dict[op['producto_id']] = []
            productos_dict[op['producto_id']].append(op)
        
        # Obtener todos los registros de inventario necesarios en una sola consulta
        product_ids = list(productos_dict.keys())
        inventarios = {inv.producto_id: inv for inv in 
                      db_session.query(Inventario).filter(
                          Inventario.producto_id.in_(product_ids)
                      ).all()}
        
        movimientos = []
        
        # Procesar las operaciones por producto
        for producto_id, ops in productos_dict.items():
            # Obtener o crear el inventario
            inventario = inventarios.get(producto_id)
            if not inventario:
                inventario = Inventario(
                    producto_id=producto_id,
                    cantidad=0,
                    ultima_actualizacion=datetime.utcnow()
                )
                db_session.add(inventario)
                inventarios[producto_id] = inventario
            
            for op in ops:
                # Guardar cantidad anterior
                cantidad_anterior = inventario.cantidad
                
                # Aplicar la operación
                if op['type'] == MOVIMIENTO_ENTRADA:
                    inventario.cantidad += op['cantidad']
                elif op['type'] == MOVIMIENTO_SALIDA:
                    inventario.cantidad = max(0, inventario.cantidad - op['cantidad'])
                elif op['type'] == MOVIMIENTO_AJUSTE:
                    inventario.cantidad = op['cantidad']
                
                # Actualizar timestamps
                inventario.ultima_actualizacion = datetime.utcnow()
                inventario.user_id = op.get('user_id')
                
                # Crear registro de movimiento
                movimiento = MovimientoInventario(
                    producto_id=op['producto_id'],
                    tipo=op['type'],
                    cantidad=op['cantidad'],
                    cantidad_anterior=cantidad_anterior,
                    cantidad_posterior=inventario.cantidad,
                    fecha=datetime.utcnow(),
                    motivo=op.get('motivo'),
                    user_id=op.get('user_id'),
                    venta_id=op.get('venta_id'),
                    gasto_id=op.get('gasto_id')
                )
                movimientos.append(movimiento)
        
        # Añadir todos los movimientos de una vez
        if movimientos:
            db_session.add_all(movimientos)
            
        try:
            db_session.commit()
        except SQLAlchemyError as e:
            db_session.rollback()
            # Llevar un registro del error
            error_msg = f"Error al procesar operaciones de inventario: {str(e)}"
            logging.error(error_msg)
            
            # Volver a agregar las operaciones a la cola
            cls._pending_operations = operations + cls._pending_operations

def get_storage_client():
    """
    Obtiene el cliente de almacenamiento adecuado según la configuración.
    
    Si la aplicación está configurada para usar Cloud Storage, devuelve
    el cliente correspondiente (real o emulado). Si no, devuelve None.
    
    Returns:
        object: Cliente de almacenamiento o None
    """
    from flask import current_app, has_app_context
    import os
    
    # Verificar que estamos dentro de un contexto de aplicación
    if not has_app_context():
        raise RuntimeError(
            "get_storage_client() requiere un contexto de aplicación Flask activo. "
            "Asegúrese de llamar a esta función dentro de 'with app.app_context():'")
            
    # Verificar si debemos usar Cloud Storage
    if current_app.config.get('USE_CLOUD_STORAGE', False):
        # Verificar si estamos en modo de emulación
        if current_app.config.get('EMULATE_CLOUD_STORAGE', False):
            # Usar el emulador local
            from app.cloud_run_local_utils import LocalStorageEmulator
            bucket_name = os.environ.get('GCS_BUCKET_NAME', 'local-bucket')
            return LocalStorageEmulator(bucket_name)
        else:
            # Usar el cliente real de Google Cloud Storage
            try:
                from google.cloud import storage
                client = storage.Client()
                bucket_name = os.environ.get('GCS_BUCKET_NAME')
                if not bucket_name:
                    current_app.logger.error("GCS_BUCKET_NAME no está configurado")
                    return None
                return client.bucket(bucket_name)
            except ImportError:
                current_app.logger.error("google-cloud-storage no está instalado")
                return None
    
    return None

def store_file(file_obj, destination_path, public=True):
    """
    Almacena un archivo en el sistema de almacenamiento configurado.
    
    Guarda el archivo en Cloud Storage si está configurado, o en el
    sistema de archivos local si no lo está.
    
    Args:
        file_obj: Objeto de archivo (de Flask request.files)
        destination_path: Ruta de destino relativa
        public: Si el archivo debe ser público (solo para Cloud Storage)
        
    Returns:
        str: URL o ruta del archivo almacenado
    """
    from flask import current_app
    import os
    
    # Verificar si debemos usar Cloud Storage
    if current_app.config.get('USE_CLOUD_STORAGE', False):
        # Obtener cliente de almacenamiento
        storage_client = get_storage_client()
        
        if storage_client:
            # Guardar temporalmente el archivo
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.basename(destination_path))
            file_obj.save(temp_path)
            
            try:
                # Subir a Cloud Storage (real o emulado)
                if hasattr(storage_client, 'upload_file'):  # Emulador local
                    return storage_client.upload_file(temp_path, destination_path)
                else:  # Cliente real de GCS
                    blob = storage_client.blob(destination_path)
                    blob.upload_from_filename(temp_path)
                    if public:
                        blob.make_public()
                    return blob.public_url
            finally:
                # Eliminar archivo temporal
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    
    # Si no usamos Cloud Storage o falló, guardar localmente
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, destination_path)
    
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Guardar archivo
    file_obj.save(file_path)
    
    # Devolver ruta relativa
    return os.path.join('/static/uploads', destination_path)

def get_file_url(file_path):
    """
    Obtiene la URL para acceder a un archivo.
    
    Si el archivo está en Cloud Storage, devuelve la URL pública.
    Si está en el sistema de archivos local, devuelve la ruta relativa.
    
    Args:
        file_path: Ruta del archivo (relativa al bucket o a UPLOAD_FOLDER)
        
    Returns:
        str: URL o ruta para acceder al archivo
    """
    from flask import current_app
    
    # Si la ruta ya es una URL completa, devolverla tal cual
    if file_path.startswith(('http://', 'https://')):
        return file_path
    
    # Si es una ruta relativa a /static/uploads, devolverla tal cual
    if file_path.startswith('/static/uploads/'):
        return file_path
    
    # Verificar si usamos Cloud Storage
    if current_app.config.get('USE_CLOUD_STORAGE', False):
        # Obtener cliente de almacenamiento
        storage_client = get_storage_client()
        
        if storage_client:
            # Obtener URL según el tipo de cliente
            if hasattr(storage_client, 'list_files'):  # Emulador local
                return f"/static/uploads/{file_path}"
            else:  # Cliente real de GCS
                blob = storage_client.blob(file_path)
                return blob.public_url
    
    # Si no usamos Cloud Storage o falló, devolver ruta local
    return os.path.join('/static/uploads', file_path)