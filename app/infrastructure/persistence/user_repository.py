# app/infrastructure/persistence/user_repository.py

from app.database.connector import get_db_read, get_db_write
from app.domain.models.usuario import Usuario

class SqlServerUserRepository:
    """
    Repositorio para gestionar los accesos y roles en SQL Server (OSCAR).
    """

    def find_by_username(self, username):
        """
        Busca un usuario por su DNI (username).
        """
        conn = get_db_read()
        cursor = conn.cursor()
        
        # 🚀 Consulta que trae el nombre del rol y el vínculo con personal
        query = """
            SELECT u.id_usuario, u.username, u.id_rol, u.email, 
                   u.password_hash, u.id_personal, u.activo, r.nombre_rol
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            WHERE u.username = ?
        """
        cursor.execute(query, (username,))
        row = cursor.fetchone()
        
        if row:
            return Usuario(
                id_usuario=row.id_usuario,
                username=row.username,
                id_rol=row.id_rol,
                email=row.email,
                password_hash=row.password_hash,
                id_personal=row.id_personal, # Puede ser NULL para admin_sistemas
                activo=row.activo,
                nombre_rol=row.nombre_rol
            )
        return None

    def create_user(self, user_data):
        """
        Registra un nuevo acceso en la base de datos.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO usuarios (username, id_rol, email, password_hash, id_personal, activo)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            user_data['username'],
            user_data['id_rol'],
            user_data.get('email'),
            user_data['password_hash'],
            user_data.get('id_personal'), # 🔗 Aquí se hace el vínculo con Legajos
            1 # Activo por defecto
        ))
        conn.commit()
        return True