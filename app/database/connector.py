# app/database/connector.py
import pyodbc
from flask import g, current_app

def _get_db_connection(username, password):
    """
    Función auxiliar interna para crear una conexión a la base de datos.
    Configurada para alta compatibilidad con ODBC Driver 17 y 18.
    """
    try:
        # Construye la cadena de conexión usando la configuración de la aplicación.
        # TrustServerCertificate=yes y Encrypt=yes son vitales para SQL Server moderno.
        conn_str = (
            f"DRIVER={{{current_app.config['DB_DRIVER']}}};"
            f"SERVER={current_app.config['DB_SERVER']};"
            f"DATABASE={current_app.config['DB_DATABASE']};"
            f"UID={username};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
            "Encrypt=yes;"
            "Connection Timeout=30;" # Evita bloqueos infinitos
        )
        return pyodbc.connect(conn_str)
    except pyodbc.Error as ex:
        current_app.logger.error(f"❌ Error de conexión a la BD con usuario {username}: {ex}")
        raise

# --------------------------------------------------------------------------
# FUNCIONES DE OBTENCIÓN DE CONEXIÓN (CON BLINDAJE)
# --------------------------------------------------------------------------

def get_db_read():
    """Obtiene una conexión de SOLO LECTURA. Persiste durante el request."""
    # Verificamos si no existe O si por algún motivo la conexión en 'g' fue cerrada
    if 'db_read' not in g:
        g.db_read = _get_db_connection(
            current_app.config['DB_USERNAME_READ'],
            current_app.config['DB_PASSWORD_READ']
        )
    return g.db_read

def get_db_write():
    """Obtiene una conexión de LECTURA/ESCRITURA para transacciones."""
    if 'db_write' not in g:
        g.db_write = _get_db_connection(
            current_app.config['DB_USERNAME_WRITE'],
            current_app.config['DB_PASSWORD_WRITE']
        )
    return g.db_write

def get_db_admin():
    """Obtiene una conexión con permisos de administrador (Sistemas)."""
    if 'db_admin' not in g:
        g.db_admin = _get_db_connection(
            current_app.config['DB_USERNAME_SYSTEMS_ADMIN'],
            current_app.config['DB_PASSWORD_SYSTEMS_ADMIN']
        )
    return g.db_admin

# --------------------------------------------------------------------------
# GESTIÓN DEL CICLO DE VIDA (LIMPIEZA AUTOMÁTICA)
# --------------------------------------------------------------------------

def close_db(e=None):
    """
    Cierra todas las conexiones activas en el objeto 'g' al finalizar el request.
    Esta es la ÚNICA parte del sistema que debe cerrar las conexiones.
    """
    # 1. Limpieza de Conexión de Lectura
    db_read = g.pop('db_read', None)
    if db_read is not None:
        try:
            db_read.close()
        except Exception:
            pass 

    # 2. Limpieza de Conexión de Escritura
    db_write = g.pop('db_write', None)
    if db_write is not None:
        try:
            db_write.close()
        except Exception:
            pass 

    # 3. Limpieza de Conexión Admin
    db_admin = g.pop('db_admin', None)
    if db_admin is not None:
        try:
            db_admin.close()
        except Exception:
            pass

def init_app_db(app):
    """
    Registra la limpieza automática de la base de datos en Flask.
    """
    # teardown_appcontext asegura que close_db se ejecute incluso si hubo un error 500
    app.teardown_appcontext(close_db)