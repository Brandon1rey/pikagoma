# app/models.py - Versión optimizada
from app import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta
import pandas as pd
import os
import json
from sqlalchemy import event
import threading
import logging
from app.utils import DeferredInventoryOperation
import traceback
from app.constants import *

# Configurar logging
logger = logging.getLogger('inventario')
logger.setLevel(logging.INFO)

# Semáforo para proteger operaciones de inventario
inventory_lock = threading.RLock()

# Clase auxiliar para operaciones seguras de inventario
class SafeInventoryOperation:
    def __init__(self, producto_id=None):
        self.producto_id = producto_id
        
    def __enter__(self):
        inventory_lock.acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        inventory_lock.release()
        
    @staticmethod
    def validate_stock(producto_id, cantidad_necesaria):
        """Valida si hay suficiente stock"""
        with inventory_lock:
            inventario = Inventario.query.filter_by(producto_id=producto_id).first()
            if not inventario:
                return False, 0  # No hay registro de inventario
            
            if inventario.cantidad <= 0:
                return False, 0  # Sin stock
                
            if inventario.cantidad < cantidad_necesaria:
                return False, inventario.cantidad  # Stock insuficiente
                
            return True, inventario.cantidad  # Stock disponible

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    nombre = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con ventas
    ventas = db.relationship('Venta', backref='vendedor', lazy='dynamic')
    
    # Relación con reportes
    reportes = db.relationship('Reporte', backref='vendedor', lazy='dynamic')
    
    @property
    def password(self):
        raise AttributeError('password no es un atributo legible')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Producto(db.Model):
    __tablename__ = 'productos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), unique=True)
    tipo = db.Column(db.String(20), default=TIPO_PRODUCTO_TERMINADO)  # 'materia_prima', 'producto_terminado', 'miscelaneo'
    
    # Restauramos la definición de la columna después de la migración exitosa
    costo_unitario = db.Column(db.Float, default=0)
    
    def __repr__(self):
        return f'<Producto {self.nombre}>'
    
    @property
    def es_materia_prima(self):
        return self.tipo == TIPO_MATERIA_PRIMA
        
    @property
    def es_producto_terminado(self):
        return self.tipo == TIPO_PRODUCTO_TERMINADO
        
    @property
    def es_miscelaneo(self):
        return self.tipo == TIPO_MISCELANEO
    
    @classmethod
    def crear_nuevo(cls, nombre, tipo=TIPO_PRODUCTO_TERMINADO):
        """Método para crear un nuevo producto desde el inventario"""
        # Verificar si ya existe
        existente = cls.query.filter_by(nombre=nombre).first()
        if existente:
            return existente
            
        # Crear nuevo producto
        nuevo = cls(nombre=nombre, tipo=tipo)
        db.session.add(nuevo)
        db.session.flush()  # Para obtener el ID generado
        
        return nuevo

# Tabla para relación entre productos terminados y materias primas
class ComponenteProducto(db.Model):
    __tablename__ = 'componentes_producto'
    
    id = db.Column(db.Integer, primary_key=True)
    producto_terminado_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)  # Cantidad necesaria por unidad de producto terminado
    unidad_medida = db.Column(db.String(20), default='unidades')
    
    # Relaciones
    producto_terminado = db.relationship('Producto', foreign_keys=[producto_terminado_id],
                                         backref=db.backref('componentes', lazy='dynamic'))
    materia_prima = db.relationship('Producto', foreign_keys=[materia_prima_id],
                                    backref=db.backref('usado_en', lazy='dynamic'))
    
    def __repr__(self):
        return f'<ComponenteProducto {self.materia_prima.nombre} en {self.producto_terminado.nombre}>'

class Presentacion(db.Model):
    __tablename__ = 'presentaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), unique=True)
    
    def __repr__(self):
        return f'<Presentacion {self.nombre}>'

# Nueva clase para los detalles de productos en una venta
class DetalleVenta(db.Model):
    __tablename__ = 'detalle_ventas'
    
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, default=1)
    
    # Relaciones
    producto = db.relationship('Producto', backref=db.backref('detalles', lazy='dynamic'))
    
    def __repr__(self):
        return f'<DetalleVenta {self.id} - Producto: {self.producto.nombre}, Cantidad: {self.cantidad}>'
        
    def to_dict(self, include_venta=False):
        """Convierte el detalle a un diccionario para reportes"""
        data = {
            'id': self.id,
            'producto': self.producto.nombre,
            'tipo_producto': self.producto.tipo,
            'cantidad': self.cantidad
        }
        
        if include_venta and self.venta:
            data.update({
                'venta_id': self.venta_id,
                'fecha_venta': self.venta.fecha.strftime('%Y-%m-%d') if self.venta.fecha else None,
                'importe_venta': self.venta.importe,
                'usuario': self.venta.vendedor.nombre if self.venta.vendedor else None
            })
            
        return data

class Venta(db.Model):
    __tablename__ = 'ventas'
    
    id = db.Column(db.Integer, primary_key=True)
    presentacion_id = db.Column(db.Integer, db.ForeignKey('presentaciones.id'))
    importe = db.Column(db.Float)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    pedido_especial = db.Column(db.Boolean, default=False)
    comentarios = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relaciones
    presentacion = db.relationship('Presentacion', backref=db.backref('ventas', lazy='dynamic'))
    detalles = db.relationship('DetalleVenta', backref='venta', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_productos_str(self):
        """Obtiene una cadena con los productos de la venta"""
        productos = []
        for detalle in self.detalles:
            productos.append(f"{detalle.producto.nombre} (x{detalle.cantidad})")
        
        if not productos:
            return "Sin productos"
        
        return " + ".join(productos)
    
    def to_dict(self):
        return {
            'id': self.id,
            'productos': self.get_productos_str(),
            'presentacion': self.presentacion.nombre if self.presentacion else 'Sin presentación',
            'importe': self.importe,
            'fecha': self.fecha.strftime('%Y-%m-%d'),
            'pedido_especial': 'Sí' if self.pedido_especial else 'No',
            'comentarios': self.comentarios,
            'usuario': self.vendedor.nombre if self.vendedor else 'Sin usuario'
        }
    
    def to_dict_detailed(self):
        """Versión detallada que incluye cada producto por separado y sus componentes"""
        detalles = []
        
        for detalle in self.detalles:
            info_producto = {
                'venta_id': self.id,
                'producto': detalle.producto.nombre,
                'tipo_producto': detalle.producto.tipo,
                'cantidad': detalle.cantidad,
                'presentacion': self.presentacion.nombre if self.presentacion else 'Sin presentación',
                'importe': self.importe,
                'fecha': self.fecha.strftime('%Y-%m-%d'),
                'pedido_especial': 'Sí' if self.pedido_especial else 'No',
                'comentarios': self.comentarios,
                'usuario': self.vendedor.nombre if self.vendedor else 'Sin usuario'
            }
            
            # Agregar información de componentes si es un producto terminado
            if detalle.producto.es_producto_terminado:
                componentes = []
                for componente in ComponenteProducto.query.filter_by(
                    producto_terminado_id=detalle.producto_id).all():
                    componentes.append({
                        'materia_prima': componente.materia_prima.nombre,
                        'cantidad_unitaria': componente.cantidad,
                        'cantidad_total': componente.cantidad * detalle.cantidad,
                        'unidad': componente.unidad_medida
                    })
                
                info_producto['componentes'] = componentes
            
            detalles.append(info_producto)
        
        return detalles
        
    def to_dict_analytics(self):
        """Versión extendida para análisis de negocios con métricas adicionales"""
        base_data = self.to_dict()
        
        # Agregar detalles avanzados
        detalles_list = []
        for detalle in self.detalles:
            detalles_list.append({
                'producto': detalle.producto.nombre,
                'tipo': detalle.producto.tipo,
                'cantidad': detalle.cantidad
            })
            
        # Calcular métricas adicionales
        metrics = {
            'detalles': detalles_list,
            'num_productos': sum(d.cantidad for d in self.detalles),
            'productos_distintos': self.detalles.count(),
            'margen': 0,  # Placeholder, se calculará si se tienen datos de costo
            'canal_venta': 'Tienda'  # Placeholder
        }
        
        # Combinar datos
        base_data.update(metrics)
        return base_data
    
    @staticmethod
    def to_csv(ventas, filename, detailed=False):
        """Convierte una lista de ventas a un archivo CSV
        
        Args:
            ventas: Lista de objetos Venta
            filename: Ruta del archivo a generar
            detailed: Si es True, genera un CSV con un producto por fila
        """
        if detailed:
            # Versión detallada (un producto por fila)
            data = []
            for venta in ventas:
                data.extend(venta.to_dict_detailed())
        else:
            # Versión simplificada (una venta por fila)
            data = [venta.to_dict() for venta in ventas]
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        return filename
    
    def __repr__(self):
        return f'<Venta {self.id}>'

class Reporte(db.Model):
    __tablename__ = 'reportes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    periodo = db.Column(db.String(64))  # Ej: "Marzo 2024"
    archivo = db.Column(db.String(255))
    enviado = db.Column(db.Boolean, default=False)
    fecha_envio = db.Column(db.DateTime)
    formato_detallado = db.Column(db.Boolean, default=False)  # Nuevo campo para formato de reporte
    tipo_reporte = db.Column(db.String(20), default=REPORTE_VENTAS)  # ventas, gastos, inventario, global
    
    def __repr__(self):
        return f'<Reporte {self.periodo}>'

# Modelos para el módulo de gastos
class CategoriaGasto(db.Model):
    __tablename__ = 'categorias_gasto'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), unique=True)
    descripcion = db.Column(db.Text)
    
    # Relación con gastos
    gastos = db.relationship('Gasto', backref='categoria', lazy='dynamic')
    
    def __repr__(self):
        return f'<CategoriaGasto {self.nombre}>'


class Gasto(db.Model):
    __tablename__ = 'gastos'
    
    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias_gasto.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    importe = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.Text)
    comprobante = db.Column(db.String(255))  # Ruta a imagen/PDF del comprobante
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Para gastos de materias primas
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    cantidad_materia = db.Column(db.Float)  # Cantidad de materia prima adquirida
    unidad_medida = db.Column(db.String(20))  # kg, g, l, ml, etc.
    
    # Para gastos de publicidad
    fecha_inicio_campania = db.Column(db.DateTime)
    fecha_fin_campania = db.Column(db.DateTime)
    plataforma = db.Column(db.String(64))  # Facebook, Instagram, Volantes, etc.
    alcance_estimado = db.Column(db.Integer)  # Personas alcanzadas estimadas
    
    # Relación con productos para análisis costo-beneficio
    producto = db.relationship('Producto', backref='gastos_asociados', foreign_keys=[producto_id])
    
    # Relación con usuario que registró el gasto
    user = db.relationship('User', backref='gastos_registrados')
    
    def to_dict(self):
        """Convierte el gasto a un diccionario para reportes"""
        return {
            'id': self.id,
            'categoria': self.categoria.nombre if self.categoria else 'Sin categoría',
            'fecha': self.fecha.strftime('%Y-%m-%d'),
            'importe': self.importe,
            'descripcion': self.descripcion,
            'usuario': self.user.nombre if self.user else 'Sistema',
            'producto': self.producto.nombre if self.producto else None,
            'cantidad_materia': self.cantidad_materia,
            'unidad_medida': self.unidad_medida
        }
    
    def to_dict_analytics(self):
        """Versión extendida con datos para análisis"""
        basic_data = self.to_dict()
        
        # Agregar datos de análisis según tipo de gasto
        if self.categoria and self.categoria.nombre == "Publicidad":
            analytics_data = {
                'fecha_inicio_campania': self.fecha_inicio_campania.strftime('%Y-%m-%d') if self.fecha_inicio_campania else None,
                'fecha_fin_campania': self.fecha_fin_campania.strftime('%Y-%m-%d') if self.fecha_fin_campania else None,
                'plataforma': self.plataforma,
                'alcance_estimado': self.alcance_estimado,
                'roi_estimado': 0,  # Se calculará en el informe
                'incremento_porcentual': 0,  # Se calculará en el informe
                'efectividad': 'Pendiente'  # Se calculará en el informe
            }
            basic_data.update(analytics_data)
            
        elif self.categoria and self.categoria.nombre == "Materias primas" and self.producto:
            analytics_data = {
                'tipo_producto': self.producto.tipo,
                'costo_unitario': self.importe / self.cantidad_materia if self.cantidad_materia and self.cantidad_materia > 0 else 0,
                'existe_en_inventario': Inventario.query.filter_by(producto_id=self.producto_id).first() is not None
            }
            basic_data.update(analytics_data)
            
        return basic_data
    
    def __repr__(self):
        return f'<Gasto {self.id} - {self.categoria.nombre if self.categoria else "Sin categoría"}>'


# Modelos para el módulo de inventario
class Inventario(db.Model):
    __tablename__ = 'inventario'
    
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Float, nullable=False, default=0)
    unidad_medida = db.Column(db.String(20), default='unidades')  # unidades, kg, g, l, ml, etc.
    cantidad_alerta = db.Column(db.Float, default=10)  # Cantidad mínima para alerta de stock bajo
    ubicacion = db.Column(db.String(120))  # Ubicación física del producto
    ultima_actualizacion = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Usuario que actualizó por última vez
    
    # Relaciones
    producto = db.relationship('Producto', backref='inventario_item', uselist=False)
    usuario = db.relationship('User', backref='actualizaciones_inventario')
    
    @property
    def estado(self):
        """Retorna el estado del inventario (normal, bajo, sin stock)"""
        if self.cantidad <= 0:
            return ESTADO_SIN_STOCK
        elif self.cantidad <= self.cantidad_alerta:
            return ESTADO_BAJO
        else:
            return ESTADO_NORMAL
            
    def to_dict(self):
        """Convierte el inventario a un diccionario para reportes"""
        return {
            'producto': self.producto.nombre,
            'tipo_producto': self.producto.tipo,
            'cantidad': self.cantidad,
            'unidad_medida': self.unidad_medida,
            'estado': self.estado,
            'ultima_actualizacion': self.ultima_actualizacion.strftime('%Y-%m-%d')
        }
    
    def __repr__(self):
        return f'<Inventario {self.producto.nombre}: {self.cantidad} {self.unidad_medida}>'


class MovimientoInventario(db.Model):
    __tablename__ = 'movimientos_inventario'
    
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # entrada, salida, ajuste
    cantidad = db.Column(db.Float, nullable=False)
    cantidad_anterior = db.Column(db.Float, nullable=False)
    cantidad_posterior = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    motivo = db.Column(db.String(120))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'))  # Si se reduce por venta
    gasto_id = db.Column(db.Integer, db.ForeignKey('gastos.id'))  # Si se incrementa por compra
    
    # Relaciones
    producto = db.relationship('Producto', backref='movimientos')
    usuario = db.relationship('User', backref='movimientos')
    venta = db.relationship('Venta', backref='movimientos')
    gasto = db.relationship('Gasto', backref='movimientos')
    
    def __repr__(self):
        return f'<MovimientoInventario {self.tipo}: {self.cantidad} de {self.producto.nombre}>'


# Función para inicializar datos
def init_app_data():
    """Inicializa datos básicos de la aplicación"""
    # Lista de productos
    productos = [
        "Skwincles piña", "Skwincles salsaguetti", "Skittles gomita", "Skittles clásicos",
        "Pulparindots", "Winis", "Manguitos", "Panditas", "Panditas mango", "Gusano",
        "Charola", "Gajos de naranja", "Tiburones", "Pingüinos", "Ositos ice",
        "Moritas", "Llavecitas", "Jolly", "Salvavidas", "Xtreme bites", "Pica fresa", "Gushers"
    ]
    
    # Lista de presentaciones
    presentaciones = [
        "bolsa 50 gramos", "bolsa 100 gramos", "bolsa 500 gramos",
        "mix 50 gramos", "mix 100 gramos", "mix 500 gramos", "charola"
    ]
    
    # Agregar productos a la BD si no existen
    for nombre_producto in productos:
        producto = Producto.query.filter_by(nombre=nombre_producto).first()
        if producto is None:
            producto = Producto(nombre=nombre_producto)
            db.session.add(producto)
    
    # Agregar presentaciones a la BD si no existen
    for nombre_presentacion in presentaciones:
        presentacion = Presentacion.query.filter_by(nombre=nombre_presentacion).first()
        if presentacion is None:
            presentacion = Presentacion(nombre=nombre_presentacion)
            db.session.add(presentacion)
    
    # Crear usuario administrador si no existe
    admin = User.query.filter_by(username='admin').first()
    if admin is None:
        admin = User(
            username='admin',
            email='admin@gomitasenchiladas.com',
            nombre='Administrador',
            password='admin123',  # Cambiar en producción
            is_admin=True
        )
        db.session.add(admin)
    
    # Categorías de gastos
    categorias_gasto = [
        {"nombre": "Materias primas", "descripcion": "Ingredientes o materiales para elaborar productos."},
        {"nombre": "Publicidad", "descripcion": "Gastos en promoción y marketing."},
        {"nombre": "Empaquetado", "descripcion": "Bolsas, cajas y materiales para empaquetar productos."},
        {"nombre": "Viáticos", "descripcion": "Gastos de transporte, alimentación, etc."},
        {"nombre": "Renta", "descripcion": "Alquiler de local o espacio para el negocio."},
        {"nombre": "Servicios", "descripcion": "Electricidad, agua, internet, etc."},
        {"nombre": "Equipo", "descripcion": "Compra de equipamiento o herramientas."},
        {"nombre": "Otros", "descripcion": "Gastos diversos no clasificados."}
    ]
    
    # Agregar categorías de gasto a la BD si no existen
    for cat_data in categorias_gasto:
        categoria = CategoriaGasto.query.filter_by(nombre=cat_data["nombre"]).first()
        if categoria is None:
            categoria = CategoriaGasto(
                nombre=cat_data["nombre"],
                descripcion=cat_data["descripcion"]
            )
            db.session.add(categoria)
        elif not categoria.descripcion:
            # Si existe pero no tiene descripción, actualizarla
            categoria.descripcion = cat_data["descripcion"]
            
    db.session.commit()


# ==================== EVENTOS DE INVENTARIO MEJORADOS ====================

@event.listens_for(DetalleVenta, 'after_insert')
def reducir_inventario_venta(mapper, connection, detalle):
    """Registra operaciones de reducción de inventario para el producto y sus componentes"""
    try:
        # Obtener la venta relacionada con este detalle
        venta = Venta.query.get(detalle.venta_id)
        
        # Obtener información del producto
        producto = Producto.query.get(detalle.producto_id)
        if not producto:
            raise ValueError(f"Producto no encontrado (ID: {detalle.producto_id})")
        
        # Registrar la operación diferida para el producto terminado
        DeferredInventoryOperation.register(
            operation_type=MOVIMIENTO_SALIDA,
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            motivo='Venta',
            user_id=venta.user_id if venta else None,
            venta_id=detalle.venta_id
        )
        
        # Ya no reducimos el inventario de componentes aquí porque se hace en el momento de fabricación
        # Mantenemos el log para seguimiento
        if producto and producto.es_producto_terminado:
            componentes = ComponenteProducto.query.filter_by(producto_terminado_id=detalle.producto_id).all()
            from flask import current_app
            current_app.logger.info(f"Producto terminado: {producto.nombre} con {len(componentes)} componentes")
            current_app.logger.info(f"No se reduce stock de componentes en venta, ya que se redujo durante fabricación")
            
            # Registrar el consumo de materias primas para análisis, pero sin hacer commit
            for componente in componentes:
                # Calcular cantidad de materia prima usada
                cantidad_mp_usada = componente.cantidad * detalle.cantidad
                
                # Registrar el consumo de materia prima
                consumo = ConsumoMateriaPrima(
                    venta_id=detalle.venta_id,
                    detalle_venta_id=detalle.id,
                    producto_terminado_id=detalle.producto_id,
                    materia_prima_id=componente.materia_prima_id,
                    cantidad=cantidad_mp_usada,
                    fecha=datetime.utcnow()
                )
                db.session.add(consumo)
                
                # Log para debug
                try:
                    materia_prima = Producto.query.get(componente.materia_prima_id)
                    current_app.logger.info(f"Registrado consumo de {cantidad_mp_usada} de {materia_prima.nombre} para venta de {producto.nombre}")
                except:
                    pass
            
            # NO hacemos commit aquí, dejamos que la transacción principal lo haga
                
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al registrar operación diferida: {str(e)}")
        current_app.logger.error(f"Detalle: {traceback.format_exc()}")

@event.listens_for(DetalleVenta, 'after_delete')
def aumentar_inventario_venta_cancelada(mapper, connection, detalle):
    """
    Registra operaciones de aumento de inventario cuando se elimina un detalle de venta.
    NOTA: Este evento NO se activa cuando se elimina una venta completa, ya que en ese caso
    la lógica está implementada en ventas/routes.py en la función eliminar().
    Este evento solo se activa cuando se elimina un detalle específico de una venta existente.
    
    Al cancelar un detalle de venta, solo se reembolsa el producto terminado, no sus materias primas,
    ya que el proceso de fabricación es irreversible.
    """
    try:
        # Obtener la venta relacionada con este detalle
        # Si estamos en una eliminación de venta completa, esta consulta puede fallar
        # porque la venta podría estar marcada para eliminación
        from sqlalchemy.orm.session import Session
        from sqlalchemy import inspect
        
        session = Session.object_session(detalle)
        if session is None:
            return  # No hay sesión, probablemente estamos en una eliminación en cascada
            
        venta = session.query(Venta).get(detalle.venta_id)
        if venta is None or inspect(venta).deleted:
            # La venta no existe o está marcada para eliminación, no registrar operación
            return
            
        # Solo continuar si la venta aún existe y no está marcada para eliminación
        # Registrar la operación diferida para el producto
        DeferredInventoryOperation.register(
            operation_type=MOVIMIENTO_ENTRADA,
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            motivo='Cancelación de detalle de venta',
            user_id=venta.user_id if venta else None,
            venta_id=detalle.venta_id
        )
        
        # No reembolsamos las materias primas ya que el proceso de fabricación es irreversible
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al registrar operación diferida: {str(e)}")

@event.listens_for(DetalleVenta, 'after_update')
def actualizar_inventario_venta_modificada(mapper, connection, detalle):
    """
    Registra la operación de ajuste de inventario para procesarla después.
    Solo ajusta el inventario del producto terminado, no de sus materias primas,
    ya que el proceso de fabricación es irreversible.
    """
    try:
        # Obtener la diferencia entre la cantidad anterior y la nueva
        diferencia = detalle.cantidad - detalle._cantidad_anterior
        
        # Si no hay cambio en la cantidad, no hacer nada
        if diferencia == 0:
            return
            
        # Obtener la venta relacionada con este detalle
        venta = Venta.query.get(detalle.venta_id)
        
        if diferencia > 0:
            # Si aumentó la cantidad, registrar una salida adicional para el producto
            DeferredInventoryOperation.register(
                operation_type=MOVIMIENTO_SALIDA,
                producto_id=detalle.producto_id,
                cantidad=abs(diferencia),
                motivo='Modificación de venta (aumento)',
                user_id=venta.user_id if venta else None,
                venta_id=detalle.venta_id
            )
            
            # No ajustamos inventario de materias primas
            
        else:
            # Si disminuyó la cantidad, registrar una entrada para el producto
            DeferredInventoryOperation.register(
                operation_type=MOVIMIENTO_ENTRADA,
                producto_id=detalle.producto_id,
                cantidad=abs(diferencia),
                motivo='Modificación de venta (disminución)',
                user_id=venta.user_id if venta else None,
                venta_id=detalle.venta_id
            )
            
            # No ajustamos inventario de materias primas
            
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al registrar operación diferida: {str(e)}")

@event.listens_for(Gasto, 'after_insert')
def aumentar_inventario_compra(mapper, connection, gasto):
    """Registra la operación de aumento de inventario por compra para procesarla después"""
    try:
        # Verificar si es un gasto de materia prima con producto asociado
        if not gasto.categoria_id or not gasto.producto_id or not gasto.cantidad_materia:
            return
            
        # Obtener la categoría para verificar si es de materias primas
        categoria = db.session.query(CategoriaGasto).get(gasto.categoria_id)
        if not categoria or categoria.nombre != "Materias primas":
            return
        
        # Actualizar tipo del producto si no es materia prima
        producto = db.session.query(Producto).get(gasto.producto_id)
        if producto and producto.tipo != TIPO_MATERIA_PRIMA:
            producto.tipo = TIPO_MATERIA_PRIMA
        
        # Registrar la operación diferida
        DeferredInventoryOperation.register(
            operation_type=MOVIMIENTO_ENTRADA,
            producto_id=gasto.producto_id,
            cantidad=gasto.cantidad_materia,
            motivo=f'Compra de materia prima: {gasto.descripcion}',
            user_id=gasto.user_id,
            gasto_id=gasto.id
        )
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error al registrar operación diferida: {str(e)}")

# Verificación de disponibilidad de materias primas
def verificar_stock_componentes(producto_id, cantidad):
    """Verifica que haya suficiente stock de todos los componentes para fabricar el producto"""
    errores = []
    
    # Obtener el producto
    producto = Producto.query.get(producto_id)
    if not producto or not producto.es_producto_terminado:
        return errores
    
    # Obtener los componentes
    componentes = ComponenteProducto.query.filter_by(producto_terminado_id=producto_id).all()
    if not componentes:
        return errores
    
    for componente in componentes:
        cantidad_necesaria = componente.cantidad * cantidad
        with SafeInventoryOperation(componente.materia_prima_id):
            inventario = Inventario.query.filter_by(producto_id=componente.materia_prima_id).first()
            
            if not inventario:
                errores.append(f'No hay registro de inventario para la materia prima "{componente.materia_prima.nombre}"')
            elif inventario.cantidad < cantidad_necesaria:
                errores.append(f'Stock insuficiente de materia prima "{componente.materia_prima.nombre}". ' 
                               f'Disponible: {inventario.cantidad:.2f} {inventario.unidad_medida}, ' 
                               f'Necesario: {cantidad_necesaria:.2f} {componente.unidad_medida}')
    
    return errores

class ConsumoMateriaPrima(db.Model):
    """
    Modelo para registrar el consumo de materias primas en las ventas de productos terminados.
    Esto permite analizar cuántas unidades de cada materia prima se han vendido indirectamente
    a través de los productos terminados.
    """
    __tablename__ = 'consumo_materia_prima'
    
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'))
    detalle_venta_id = db.Column(db.Integer, db.ForeignKey('detalle_ventas.id'))
    producto_terminado_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    cantidad = db.Column(db.Float, default=0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    venta = db.relationship('Venta', backref='consumos_mp')
    detalle_venta = db.relationship('DetalleVenta', backref='consumos_mp')
    producto_terminado = db.relationship('Producto', foreign_keys=[producto_terminado_id], 
                                      backref='consumos_como_pt')
    materia_prima = db.relationship('Producto', foreign_keys=[materia_prima_id], 
                                 backref='consumos_como_mp')
    
    def __repr__(self):
        return f'<ConsumoMP: {self.cantidad} de {self.materia_prima.nombre} para {self.producto_terminado.nombre}>'