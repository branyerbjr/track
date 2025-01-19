# Usar una imagen base oficial de Python
FROM python:3.10-slim

# Configurar el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar los archivos necesarios
COPY requirements.txt requirements.txt

# Instalar las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto para Flask
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["flask", "run", "--host=0.0.0.0"]
