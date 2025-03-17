# Usar Python 3.9 como base para mejor compatibilidad con dependencias
FROM python:3.9-slim

# Establecer variable para indicar que estamos en Cloud Run
ENV CLOUD_RUN=True
ENV PYTHONUNBUFFERED=1

# Crear directorio de la aplicación
WORKDIR /app

# Copiar requirements.txt primero para aprovechar caché de Docker
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de la aplicación
COPY . .

# Crear directorio para archivos temporales
RUN mkdir -p /tmp/uploads && chmod 777 /tmp/uploads

# Puerto expuesto por Cloud Run
EXPOSE 8080

# Comando para iniciar la aplicación con gunicorn optimizado para Cloud Run
# - workers: usar fórmula (2 * CPU cores) + 1
# - timeout: establecer timeout para manejar solicitudes prolongadas
# - preload: cargar la aplicación antes de crear workers
CMD ["gunicorn", "--bind", ":8080", "--workers=4", "--threads=8", "--timeout=120", "--preload", "wsgi:app"]