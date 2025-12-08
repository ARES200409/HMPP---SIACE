# app/database/connector.py
# Importa la librería pyodbc para la conexión con SQL Server y Flask's 'g' y 'current_app'.
import pyodbc
from flask import g, current_app

# Define una función auxiliar interna para crear una conexión a la base de datos.
def _get_db_connection(username, password):
    try:
        # Construye la cadena de conexión usando la configuración de la aplicación.
        # Se agrega TrustServerCertificate=yes para compatibilidad con ODBC Driver 18
        conn_str = (
            f"DRIVER={{{current_app.config['DB_DRIVER']}}};"
            f"SERVER={current_app.config['DB_SERVER']};"
            f"DATABASE={current_app.config['DB_DATABASE']};"
            f"UID={username};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
            "Encrypt=yes;"
        )
        # Establece y devuelve la conexión.
        return pyodbc.connect(conn_str)
    except pyodbc.Error as ex:
        # Si hay un error, lo registra en el log de la aplicación y lo relanza.
        current_app.logger.error(f"Error de conexión a la BD con usuario {username}: {ex}")
        raise

# Define una función para obtener una conexión de SOLO LECTURA.
# Utiliza el objeto 'g' de Flask para almacenar la conexión durante el ciclo de una petición.
def get_db_read():
    if 'db_read' not in g:
        # Si no hay conexión de lectura en 'g', crea una nueva con las credenciales de lectura.
        g.db_read = _get_db_connection(
            current_app.config['DB_USERNAME_READ'],
            current_app.config['DB_PASSWORD_READ']
        )
    return g.db_read

# Define una función para obtener una conexión de LECTURA/ESCRITURA.
def get_db_write():
    if 'db_write' not in g:
        # Si no hay conexión de escritura en 'g', crea una nueva con las credenciales de escritura.
        g.db_write = _get_db_connection(
            current_app.config['DB_USERNAME_WRITE'],
            current_app.config['DB_PASSWORD_WRITE']
        )
    return g.db_write

# Define una función para obtener una conexión con permisos de administrador de sistemas
def get_db_admin():
    if 'db_admin' not in g:
        # Si no hay conexión de admin en 'g', crea una nueva con las credenciales de administrador.
        g.db_admin = _get_db_connection(
            current_app.config['DB_USERNAME_SYSTEMS_ADMIN'],
            current_app.config['DB_PASSWORD_SYSTEMS_ADMIN']
        )
    return g.db_admin

# Define una función para cerrar las conexiones al final de la petición.
def close_db(e=None):
    # Busca y cierra la conexión de lectura si existe.
    db_read = g.pop('db_read', None)
    if db_read is not None:
        try:
            db_read.close()
        except Exception:
            pass  # Ignorar errores al cerrar
    
    # Busca y cierra la conexión de escritura si existe.
    db_write = g.pop('db_write', None)
    if db_write is not None:
        try:
            db_write.close()
        except Exception:
            pass  # Ignorar errores al cerrar
    
    # Busca y cierra la conexión de admin si existe.
    db_admin = g.pop('db_admin', None)
    if db_admin is not None:
        try:
            db_admin.close()
        except Exception:
            pass  # Ignorar errores al cerrar

# Define una función para inicializar el manejo de la base de datos en la aplicación Flask.
def init_app_db(app):
    # Registra la función 'close_db' para que se ejecute al final de cada contexto de aplicación.
    app.teardown_appcontext(close_db)