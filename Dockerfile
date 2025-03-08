# Usa una imagen base de Python
FROM python:3.9-slim

# Establece directorio de trabajo
WORKDIR /app

# Copia los archivos de requisitos primero para aprovechar el caché
COPY requirements.txt .

# Instala dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Crea directorios necesarios
RUN mkdir -p /app/app/static/uploads/comprobantes

# Variable de entorno para indicar que estamos en producción
ENV FLASK_ENV=production

# El puerto que Cloud Run asignará a tu aplicación
EXPOSE 8080

# Comando para iniciar la aplicación con gunicorn (un servidor web para Python)
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 'app:create_app("production")'