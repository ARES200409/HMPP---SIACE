 # app/database/__init__.py

# Importamos las funciones desde connector.py para que sean accesibles desde fuera
from .connector import get_db_read, get_db_write, get_db_admin, init_app_db

# Si quieres seguir usando el nombre 'db' en tus rutas como un acceso rápido:
db = get_db_write
