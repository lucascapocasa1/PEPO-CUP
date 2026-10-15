#!/bin/bash
# Deploy en PythonAnywhere.
# Correr desde la consola Bash de PythonAnywhere:
#   bash ~/PEPOCUP/deploy.sh
set -e

cd ~/PEPOCUP

# Activar el virtualenv (el nombre puede variar si lo creaste con otro)
source ~/.virtualenvs/pepocup/bin/activate

# Bajar los últimos cambios
git pull origin main

# Dependencias
pip install -r requirements.txt

# Base de datos y estáticos
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Recargar la web app
touch pepocup/wsgi.py

echo "Deploy listo."
