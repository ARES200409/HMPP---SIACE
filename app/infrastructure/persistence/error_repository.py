# app/infrastructure/persistence/error_repository.py

from app.database.connector import get_db_write

class ErrorRepository:
    """
    Repositorio especializado en la gestión de fallos técnicos del sistema.
    Maneja la persistencia en la tabla bitacora_errores de SQL Server.
    """

    def save_error(self, data):
        """
        Guarda el rastro técnico completo (ADN del error) en la BD.
        """
        try:
            conn = get_db_write()
            cursor = conn.cursor()
            query = """
                INSERT INTO bitacora_errores 
                (modulo_ruta, tipo_error, mensaje, stacktrace, usuario_id, archivo, linea)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, (
                data.get('modulo'), 
                data.get('tipo'), 
                data.get('mensaje'), 
                data.get('stacktrace'), 
                data.get('usuario'), 
                data.get('archivo'), 
                data.get('linea')
            ))
            conn.commit()
            return True
        except Exception as e:
            # En caso de error crítico al guardar, imprimimos en la consola de VS Code
            print(f"!!! Error Crítico al intentar guardar el log en OSCAR: {e}")
            return False

    def obtener_todos(self):
        """
        Recupera el historial de errores ordenado del más reciente al más antiguo.
        """
        try:
            conn = get_db_write()
            cursor = conn.cursor()
            # 🚀 Seleccionamos los campos exactos que usa tu tabla HTML
            query = """
                SELECT 
                    e.fecha_hora, 
                    e.modulo_ruta AS modulo, 
                    e.tipo_error, 
                    e.mensaje, 
                    e.archivo, 
                    e.linea, 
                    u.username AS usuario -- <--- Aquí obtenemos el nombre real
                FROM bitacora_errores e
                LEFT JOIN usuarios u ON e.usuario_id = u.id_usuario
                ORDER BY e.fecha_hora DESC
            """
            cursor.execute(query)
            
            # Convertimos los resultados a una lista de diccionarios
            columnas = [column[0] for column in cursor.description]
            resultados = []
            for row in cursor.fetchall():
                resultados.append(dict(zip(columnas, row)))
            
            return resultados
        except Exception as e:
            print(f"Error al obtener historial de errores: {e}")
            return []

    def vaciar_log(self):
        """
        Limpia la tabla de errores para mantenimiento.
        """
        try:
            conn = get_db_write()
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE bitacora_errores")
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al vaciar la bitácora: {e}")
            return False