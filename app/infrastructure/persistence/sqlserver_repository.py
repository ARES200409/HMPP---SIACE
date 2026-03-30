# RUTA: app/infrastructure/persistence/sqlserver_repository.py
from datetime import datetime
import logging
from app.database.connector import get_db_read, get_db_write
from app.domain.models.usuario import Usuario
from app.domain.models.personal import Personal
from app.domain.repositories.i_usuario_repository import IUsuarioRepository
from app.domain.repositories.i_personal_repository import IPersonalRepository
from app.domain.repositories.i_auditoria_repository import IAuditoriaRepository
from app.utils.pagination import SimplePagination

logger = logging.getLogger(__name__)

def _row_to_dict(cursor, row):
    # Función de utilidad para convertir una fila del cursor a un diccionario
    if not row:
        return None
    if not cursor.description:
        return None
    return dict(zip([column[0] for column in cursor.description], row))

class SqlServerUsuarioRepository(IUsuarioRepository):
    
    # -------------------------------------------------------------
    # MÉTODO PARA LISTAR USUARIOS (Corregido para usar p_obtener_usuarios_para_gestion)
    # -------------------------------------------------------------

    def get_all_users_with_roles(self):
        """
        Obtiene todos los usuarios con sus roles.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            cursor.execute("{CALL sp_listar_todos_los_usuarios}")
            rows = cursor.fetchall()
            usuarios = []
            for row in rows:
                # Mapeo manual de la fila al objeto Usuario
                # Aseguramos de capturar el email (índice 2 según el SP)
                usuario = Usuario(
                    id_usuario=row.id_usuario,
                    username=row.username,
                    email=row.email if hasattr(row, 'email') else None, # Capturamos email
                    id_rol=0, # El ID del rol no viene en este SP, solo el nombre
                    activo=row.activo
                )
                # Asignamos atributos adicionales que no están en el modelo base pero sirven para la vista
                usuario.nombre_rol = row.nombre_rol
                usuario.ultimo_login = row.ultimo_login
                
                usuarios.append(usuario)
            return usuarios
        finally:
            cursor.close()
            


    def find_all_users_with_roles(self):
        """
        Obtiene la lista completa de usuarios con sus roles y estados para 
        la tabla de Gestión de Usuarios.
        Usa query directa en lugar de SP para evitar problemas de permisos.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        
        try:
            # Query directa en lugar de SP
            query = """
            SELECT 
                u.id_usuario, 
                u.username, 
                u.email,
                r.nombre_rol, 
                u.activo, 
                u.ultimo_login,
                u.nombre_completo
            FROM 
                usuarios u
            JOIN 
                roles r ON u.id_rol = r.id_rol
            LEFT JOIN 
                personal p ON u.id_personal = p.id_personal
            ORDER BY 
                u.username
            """
            cursor.execute(query)
            results = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
            # --- CORRECCIÓN: Construcción manual y segura de objetos ---
            # Esto previene errores si el SP no devuelve todas las columnas esperadas.
            usuarios = []
            for data in results:
                if data:
                    usuario = Usuario(
                        id_usuario=data.get('id_usuario'),
                        username=data.get('username'),
                        id_rol=data.get('id_rol'),  # Si 'id_rol' no existe, pasará None
                        password_hash=data.get('password_hash'),
                        activo=data.get('activo'),
                        email=data.get('email'),
                        nombre_rol=data.get('nombre_rol'),
                        nombre_completo=data.get('nombre_completo') or 'Sin nombre registrado',
                        ultimo_login=data.get('ultimo_login')
                    )
                    # Asignar alias para compatibilidad con la vista
                    usuario.rol_nombre = usuario.nombre_rol
                    usuario.last_login = usuario.fecha_ultimo_login
                    # Nota: is_active es una propiedad de Flask-Login, no se puede asignar
                    usuarios.append(usuario)
            return usuarios
        except Exception as e:
            logger.error(f"Error al obtener usuarios: {e}")
            return []
        finally:
            cursor.close()
           

    def find_by_id(self, user_id):
        """Busca un usuario por su ID con todos los campos incluyendo email y rol."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # Query con JOIN a tabla roles para obtener nombre del rol
            query = """
            SELECT 
                u.id_usuario, 
                u.username, 
                u.email, 
                u.password_hash, 
                u.id_rol, 
                u.activo,
                u.two_factor_code,
                u.two_factor_expiry,
                u.id_personal,
                u.foto_perfil,
                r.nombre_rol,
                u.nombre_completo
            FROM usuarios u
            LEFT JOIN roles r ON u.id_rol = r.id_rol
            WHERE u.id_usuario = ?
            """
            cursor.execute(query, user_id)
            row = cursor.fetchone()
            
            if row:
                row_dict = _row_to_dict(cursor, row)
                return Usuario(**row_dict) if row_dict else None
            
            return None
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            
            # Si falla por permisos en roles, intentar sin el JOIN
            if "roles" in str(e).lower() or "permission" in str(e).lower() or "229" in str(e):
                logger.warning(f"JOIN a roles falló para user_id {user_id}, intentando sin JOIN")
                try:
                    query_fallback = """
                    SELECT 
                        u.id_usuario, 
                        u.username, 
                        u.email, 
                        u.password_hash, 
                        u.id_rol, 
                        u.activo,
                        u.two_factor_code,
                        u.id_personal,
                        u.two_factor_expiry,
                        u.foto_perfil
                    FROM usuarios u
                    WHERE u.id_usuario = ?
                    """
                    cursor.execute(query_fallback, user_id)
                    row = cursor.fetchone()
                    
                    if row:
                        row_dict = _row_to_dict(cursor, row)
                        
                        return Usuario(**row_dict) if row_dict else None
                    return None
                except Exception as e2:
                    logger.error(f"Fallback también falló para user_id {user_id}: {e2}")
                    return None
            else:
                logger.error(f"Error al obtener usuario por ID {user_id}: {e}")
                return None

    def find_by_username_with_email(self, username):
        """Busca un usuario por su nombre de usuario para login (con email y rol)."""
        conn = get_db_read()
        cursor = conn.cursor()
        
        try:
            # Intentar con query directa que incluye JOIN a roles
            query = """
            SELECT 
                u.id_usuario, 
                u.username, 
                u.email, 
                u.password_hash, 
                u.id_rol, 
                u.activo,
                u.two_factor_code,
                u.two_factor_expiry,
                r.nombre_rol,
                u.nombre_completo
            FROM usuarios u
            LEFT JOIN roles r ON u.id_rol = r.id_rol
            WHERE u.username = ?
            """
            cursor.execute(query, username)
            row = cursor.fetchone()
            
            if row:
                row_dict = _row_to_dict(cursor, row)
                return Usuario(**row_dict) if row_dict else None
            
            return None
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            
            # Si falla por permisos en roles, intentar sin el JOIN
            if "roles" in str(e).lower() or "permission" in str(e).lower() or "229" in str(e):
                logger.warning(f"JOIN a roles falló, intentando sin JOIN: {e}")
                try:
                    # Fallback: Query sin JOIN a roles
                    query_fallback = """
                    SELECT 
                        u.id_usuario, 
                        u.username, 
                        u.email, 
                        u.password_hash, 
                        u.id_rol, 
                        u.activo,
                        u.two_factor_code,
                        u.two_factor_expiry
                    FROM usuarios u
                    WHERE u.username = ?
                    """
                    cursor.execute(query_fallback, username)
                    row = cursor.fetchone()
                    
                    if row:
                        row_dict = _row_to_dict(cursor, row)
                        return Usuario(**row_dict) if row_dict else None
                    return None
                    
                except Exception as e2:
                    logger.error(f"Fallback también falló para usuario '{username}': {e2}")
                    return None
            else:
                logger.error(f"Error al obtener usuario por username '{username}': {e}")
                return None

    def find_by_username(self, username):
        """Busca un usuario por su nombre de usuario."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
            SELECT 
                u.id_usuario, 
                u.username, 
                u.email, 
                u.password_hash, 
                u.id_rol, 
                u.activo,
                u.two_factor_code,
                u.two_factor_expiry,
                r.nombre_rol
            FROM usuarios u
            LEFT JOIN roles r ON u.id_rol = r.id_rol
            WHERE u.username = ?
            """
            cursor.execute(query, username)
            row_dict = _row_to_dict(cursor, cursor.fetchone())
            return Usuario(**row_dict) if row_dict else None
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            
            # Si falla por roles, intentar sin JOIN
            if "roles" in str(e).lower() or "permission" in str(e).lower():
                logger.warning(f"JOIN a roles falló para {username}, intentando sin JOIN")
                try:
                    query_fallback = """
                    SELECT 
                        u.id_usuario, 
                        u.username, 
                        u.email, 
                        u.password_hash, 
                        u.id_rol, 
                        u.activo,
                        u.two_factor_code,
                        u.two_factor_expiry
                    FROM usuarios u
                    WHERE u.username = ?
                    """
                    cursor.execute(query_fallback, username)
                    row_dict = _row_to_dict(cursor, cursor.fetchone())
                    return Usuario(**row_dict) if row_dict else None
                except Exception as e2:
                    logger.error(f"Fallback falló para {username}: {e2}")
                    return None
            else:
                logger.error(f"Error al buscar usuario por username: {e}")
                return None

    def find_by_email(self, email):
        """Busca un usuario por su correo electrónico."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
            SELECT 
                u.id_usuario, 
                u.username, 
                u.email, 
                u.password_hash, 
                u.id_rol, 
                u.activo,
                u.two_factor_code,
                u.two_factor_expiry,
                r.nombre_rol
            FROM usuarios u
            LEFT JOIN roles r ON u.id_rol = r.id_rol
            WHERE u.email = ?
            """
            cursor.execute(query, email)
            row_dict = _row_to_dict(cursor, cursor.fetchone())
            return Usuario(**row_dict) if row_dict else None
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            
            # Si falla por roles, intentar sin JOIN
            if "roles" in str(e).lower() or "permission" in str(e).lower():
                logger.warning(f"JOIN a roles falló para {email}, intentando sin JOIN")
                try:
                    query_fallback = """
                    SELECT 
                        u.id_usuario, 
                        u.username, 
                        u.email, 
                        u.password_hash, 
                        u.id_rol, 
                        u.activo,
                        u.two_factor_code,
                        u.two_factor_expiry
                    FROM usuarios u
                    WHERE u.email = ?
                    """
                    cursor.execute(query_fallback, email)
                    row_dict = _row_to_dict(cursor, cursor.fetchone())
                    return Usuario(**row_dict) if row_dict else None
                except Exception as e2:
                    logger.error(f"Fallback falló para {email}: {e2}")
                    return None
            else:
                logger.error(f"Error al buscar usuario por email: {e}")
                return None

    def set_2fa_code(self, user_id, hashed_code, expiry_date):
        conn = get_db_write()
        cursor = conn.cursor()
        query = "UPDATE usuarios SET two_factor_code = ?, two_factor_expiry = ? WHERE id_usuario = ?"
        cursor.execute(query, hashed_code, expiry_date, user_id)
        conn.commit()

    def clear_2fa_code(self, user_id):
        conn = get_db_write()
        cursor = conn.cursor()
        query = "UPDATE usuarios SET two_factor_code = NULL, two_factor_expiry = NULL WHERE id_usuario = ?"
        cursor.execute(query, user_id)
        conn.commit()

    def update_password_hash(self, username, new_hash):
        conn = get_db_write()
        cursor = conn.cursor()
        query = "UPDATE usuarios SET password_hash = ? WHERE username = ?"
        cursor.execute(query, new_hash, username)
        conn.commit()     

    def update_user_password(self, user_id, new_hash):
        """Actualiza la contraseña de un usuario por su ID."""
        conn = get_db_write()
        cursor = conn.cursor()
        # Actualizar directamente por ID sin usar SP
        query = "UPDATE usuarios SET password_hash = ? WHERE id_usuario = ?"
        cursor.execute(query, new_hash, user_id)
        if cursor.rowcount == 0:
            raise ValueError("Usuario no encontrado.")
        conn.commit()

    def update_last_login(self, user_id):
        """Llama a un SP para actualizar la fecha del último login."""
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_actualizar_ultimo_login(?)}", user_id)
        conn.commit()

    def deactivate_user(self, user_id):
        """Desactiva el acceso y el legajo de forma sincronizada."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # 1. Identificamos al personal vinculado antes de desactivar
            cursor.execute("SELECT id_personal FROM usuarios WHERE id_usuario = ?", user_id)
            row = cursor.fetchone()
            id_personal = row[0] if row else None

            # 2. Desactivamos la cuenta de acceso (Visto por Sistemas)
            cursor.execute("UPDATE usuarios SET activo = 0 WHERE id_usuario = ?", user_id)

            # 3. Desactivamos la ficha de personal (Visto por RRHH y Legajos)
            if id_personal:
                cursor.execute("UPDATE personal SET activo = 0 WHERE id_personal = ?", id_personal)
            
            conn.commit()
            return True
        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"Error en sincronización de inactividad: {e}")
            return False
        finally:
            cursor.close()

    def activate_user(self, user_id):
        """Activa el acceso y el legajo simultáneamente."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_personal FROM usuarios WHERE id_usuario = ?", user_id)
            id_personal = cursor.fetchone()[0]

            cursor.execute("UPDATE usuarios SET activo = 1 WHERE id_usuario = ?", user_id)
            if id_personal:
                cursor.execute("UPDATE personal SET activo = 1 WHERE id_personal = ?", id_personal)
            
            conn.commit()
        finally:
            cursor.close()

    def update_user_role(self, user_id, new_role_id):
        """Actualiza el rol de un usuario."""
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_actualizar_rol_usuario(?, ?)}", user_id, new_role_id)
        conn.commit()

    def update_username(self, user_id, new_username):
        """Actualiza el nombre de usuario."""
        conn = get_db_write()
        cursor = conn.cursor()
        
        # Verificar que el nuevo username no esté duplicado
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE username = ? AND id_usuario != ?", new_username, user_id)
        if cursor.fetchone()[0] > 0:
            raise ValueError(f"El nombre de usuario '{new_username}' ya está en uso por otro usuario.")
        
        # Actualizar directamente en la tabla usuarios
        cursor.execute("UPDATE usuarios SET username = ? WHERE id_usuario = ?", new_username, user_id)
        conn.commit()

    def update_email(self, user_id, new_email):
        """Actualiza el correo electrónico de un usuario."""
        conn = get_db_write()
        cursor = conn.cursor()
        
        # Verificar que el nuevo email no esté duplicado
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE email = ? AND id_usuario != ?", new_email, user_id)
        if cursor.fetchone()[0] > 0:
            raise ValueError(f"El correo electrónico '{new_email}' ya está en uso por otro usuario.")
        
        # Actualizar directamente en la tabla usuarios
        cursor.execute("UPDATE usuarios SET email = ? WHERE id_usuario = ?", new_email, user_id)
        conn.commit()

    def update_foto_perfil(self, user_id, foto_filename):
        """Actualiza la foto de perfil de un usuario."""
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET foto_perfil = ? WHERE id_usuario = ?", foto_filename, user_id)
        if cursor.rowcount == 0:
            raise ValueError("Usuario no encontrado.")
        conn.commit()

    def create_user(self, username, email, password_hash, id_rol, nombre_completo, activo=True, fecha_creacion=None, id_personal=None):
        """
        Crea un nuevo usuario en la base de datos.
        Utiliza la conexión de administrador debido a permisos de INSERT.
        
        Args:
            username: Nombre de usuario único
            email: Correo electrónico único
            password_hash: Hash de la contraseña
            id_rol: ID del rol a asignar
            activo: Estado del usuario (default: True)
            fecha_creacion: Fecha de creación (si no se proporciona, usa NOW())
            id_personal: ID del personal asociado (opcional)
        
        Returns:
            Usuario creado con su ID asignado
        """
        from app.database.connector import get_db_admin
        from datetime import datetime
        
        conn = get_db_admin()
        cursor = conn.cursor()
        
        try:
            # Insertar el nuevo usuario
            query = """
            INSERT INTO usuarios (username, email, password_hash, id_rol, nombre_completo, activo, fecha_creacion, id_personal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, username, email, password_hash, id_rol, nombre_completo, activo, fecha_creacion or datetime.utcnow(), id_personal)
            conn.commit()
            
            # Obtener el ID del usuario creado
            cursor.execute("SELECT @@IDENTITY as id_usuario")
            new_id = cursor.fetchone()[0]
            
            # Retornar el usuario creado
            new_user = Usuario(
                id_usuario=new_id,
                username=username,
                nombre_completo=nombre_completo,
                email=email,
                password_hash=password_hash,
                id_rol=id_rol,
                activo=activo
            )
            
            return new_user
            
        except Exception as e:
            conn.rollback()
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al crear usuario: {e}")
            raise

    def get_all_roles(self):
        """Obtiene todos los roles disponibles de la base de datos.
        
        Si hay problemas de permisos, devuelve los roles hardcodeados.
        """
        # Roles estándar del sistema - actualiza aquí si agregas nuevos roles
        roles_data = [
            (1, 'Sistemas'),
            (2, 'AdministradorLegajos'),
            (3, 'RRHH'),
        ]
        
        try:
            # Intenta obtener de la BD
            conn = get_db_write()  # Usar conexión de escritura que tiene más permisos
            cursor = conn.cursor()
            cursor.execute("SELECT id_rol, nombre_rol FROM roles ORDER BY nombre_rol")
            
            roles_list = []
            for row in cursor.fetchall():
                roles_list.append((row[0], row[1]))
            
            if roles_list:
                roles_data = roles_list
        except:
            # Si falla, usa los roles hardcodeados
            pass
        
        # Crear objetos con atributos id_rol y nombre_rol
        roles = []
        for id_rol, nombre_rol in roles_data:
            role = type('Role', (), {'id_rol': id_rol, 'nombre_rol': nombre_rol})()
            roles.append(role)
        
        return roles
        


    def find_by_personal_id(self, personal_id):
        """Busca el usuario vinculado por ID numérico. CLAVE PARA EL CASO MARCO."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # Buscamos por la FK id_personal directamente
            query = "SELECT id_usuario, username, email, activo FROM usuarios WHERE id_personal = ?"
            cursor.execute(query, (personal_id,))
            row = cursor.fetchone()
            if row:
                return Usuario(id_usuario=row[0], username=row[1], email=row[2], activo=row[3])
            return None
        finally:
            cursor.close()

# --- REPOSITORIO DE PERSONAL ---
class SqlServerPersonalRepository(IPersonalRepository):
    # ... (Métodos de personal) ...


    def limpiar_historial_errores(self):
        """Vacia la tabla de errores en SQL Server."""
        from app.database import get_db_write # 🛡️ Usa tu conector oficial
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # 🚀 Asegúrate de usar el nombre que ves en el SSMS (image_2e6a22.png)
            cursor.execute("DELETE FROM dbo.bitacora_errores") 
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al limpiar: {str(e)}")
            return False
        finally:
            cursor.close()
            
    def get_cargos_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_cargo, nombre_cargo FROM cargos ORDER BY nombre_cargo")
        return [(str(row.id_cargo), row.nombre_cargo) for row in cursor.fetchall()]

    def get_tipos_contrato_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_tipo_contrato, nombre_tipo FROM tipos_contrato ORDER BY nombre_tipo")
        return [(str(row.id_tipo_contrato), row.nombre_tipo) for row in cursor.fetchall()]

    def registrar_contrato_inicial(self, form_data, file_bytes, filename):
        """
        Registra la contratación inicial de forma estricta:
        1. Actualiza el estado del personal (activo y asignación de cargo/unidad).
        2. Inserta el contrato en 'dbo.contratos' incluyendo el PDF para el 'ojito'.
        3. Crea el usuario solo si no existe para evitar el error de DNI duplicado.
        """
        import zlib
        from app.database.connector import get_db_write
        from datetime import datetime
        conn = get_db_write()
        cursor = conn.cursor()
        
        try:
            conn.autocommit = False  # 🛡️ Iniciamos transacción manual para seguridad
            ahora_sistema = datetime.now() 

            # 🚀 1. ACTUALIZAR FICHA MAESTRA (dbo.personal)
            # Marcamos al trabajador como ACTIVO y actualizamos su cargo/unidad actual
            query_update_personal = """
                UPDATE dbo.personal 
                SET id_cargo = ?, 
                    id_unidad = ?, 
                    id_tipo_contrato = ?,
                    sueldo = ?,
                    activo = 1 
                WHERE id_personal = ?
            """
            cursor.execute(query_update_personal, (
                form_data['id_cargo'], 
                form_data['id_unidad'], 
                form_data['id_tipo_contrato'],
                form_data.get('sueldo', 0),
                form_data['id_personal']
            ))

            # 🔥 MINIMIZAR TAMAÑO (Magia de Compresión Nivel 9)
            # Esto reduce un archivo de 2MB a una fracción de su tamaño original
            try:
                file_bytes_optimizado = zlib.compress(file_bytes, 9)
                print(f"📦 Optimizando {filename}: De {len(file_bytes)} bytes a {len(file_bytes_optimizado)} bytes.")
            except Exception as e:
                file_bytes_optimizado = file_bytes # Si falla, guardamos el original
                print(f"⚠️ No se pudo minimizar: {e}")

            # 🚀 2. INSERTAR CONTRATO (dbo.contratos)
            # Se han incluido las columnas de archivo y auditoría para que funcione el 'ojito'
            # y se vea la hora real de registro independientemente de la fecha de inicio.
            query_contrato = """
                INSERT INTO dbo.contratos (
                    id_personal, id_tipo_contrato, fecha_inicio, fecha_fin, 
                    sueldo, resolucion, id_cargo, modalidad,
                    nombre_archivo_real, archivo_binario, fecha_registro_auditoria
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Presencial', ?, ?, ?)
            """
            cursor.execute(query_contrato, (
                form_data['id_personal'], 
                form_data['id_tipo_contrato'], 
                form_data['fecha_inicio'], 
                form_data.get('fecha_fin'),
                form_data['sueldo'], 
                form_data.get('resolucion'),
                form_data['id_cargo'],
                filename,           # nombre_archivo_real
                file_bytes_optimizado,         # archivo_binario (VARBINARY)
                ahora_sistema       # fecha_registro_auditoria
            ))

            # 🚀 3. GESTIÓN DE USUARIO (Evita error 'Violation of UNIQUE KEY' del DNI)
            # Primero recuperamos el DNI del personal para la verificación
            cursor.execute("SELECT dni FROM dbo.personal WHERE id_personal = ?", (form_data['id_personal'],))
            dni_row = cursor.fetchone()
            
            if dni_row:
                dni_trabajador = dni_row[0]
                # Verificamos si ya existe una cuenta con ese DNI antes de insertar
                cursor.execute("SELECT COUNT(*) FROM dbo.usuarios WHERE username = ?", (dni_trabajador,))
                if cursor.fetchone()[0] == 0:
                    # Si no existe el usuario, se crea la cuenta de acceso inicial
                    query_usuario = """
                        INSERT INTO dbo.usuarios (username, password_hash, id_rol, activo, id_personal)
                        VALUES (?, ?, ?, 1, ?)
                    """
                    # 'hmpp2026' como contraseña temporal
                    cursor.execute(query_usuario, (dni_trabajador, 'hmpp2026', 2, form_data['id_personal']))

            conn.commit() # ✅ Éxito: Todo guardado correctamente en contratos
            return True

        except Exception as e:
            if 'conn' in locals(): conn.rollback() # ❌ Si algo falla, se deshacen los cambios
            print(f"!!! Error crítico en contratación HMPP: {str(e)}")
            raise e
        finally:
            conn.autocommit = True
            cursor.close()


    def get_document_owner(self, document_id):
        """Devuelve el id_personal del dueño de un documento."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # Consulta directa ligera para seguridad
            cursor.execute("SELECT id_personal FROM documentos WHERE id_documento = ?", document_id)
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()




    def check_dni_exists(self, dni):
        """Verifica si un DNI ya existe en la tabla de personal."""
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM personal WHERE dni = ?", dni)
        return cursor.fetchone() is not None

    def get_all_documents_with_expiration(self):
        """Llama al SP para obtener todos los documentos activos con fecha de vencimiento."""
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_listar_documentos_con_vencimiento}")
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]


    def find_document_by_id(self, document_id):
        """
        Llama al SP para obtener los datos de un único documento por su ID.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_obtener_documento_por_id(?)}", document_id)
        return cursor.fetchone()

    def delete_document_by_id(self, document_id):
        """
        Llama al SP para la eliminación lógica de un documento.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_eliminar_documento_logico(?)}", document_id)
        conn.commit()


    def find_tipos_documento_by_seccion(self, id_seccion):
        """
        Llama a un procedimiento almacenado para obtener los tipos de documento 
        asociados a una sección.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        
        cursor.execute("{CALL sp_listar_tipos_documento_por_seccion(?)}", id_seccion)
        
        # Devuelve una lista de diccionarios, ideal para ser convertida a JSON
        return [{"id": row.id_tipo, "nombre": row.nombre_tipo} for row in cursor.fetchall()]


    # Llama a un SP para obtener la lista de documentos de un empleado.
    def find_documents_by_personal_id(self, personal_id):
        conn = get_db_read()
        cursor = conn.cursor()
        # Este SP debe devolver la lista de documentos para un id_personal.
        cursor.execute("{CALL sp_listar_documentos_por_personal(?)}", personal_id)
        # Se asume que el SP devuelve filas que se pueden mapear al modelo Documento.
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]


    # 1. ACTUALIZACIÓN: Obtener Legajo Completo (Forzando lectura de fechas)
    # Busca este método dentro de SqlServerPersonalRepository:

    def get_full_legajo_by_id(self, personal_id):
        """
        Obtiene el legajo completo de un trabajador. 
        CORREGIDO: Implementación de context manager para cursor y protección de conexión.
        """
        from app.database.connector import get_db_read
        conn = get_db_read()
        
        # 🛡️ IMPORTANTE: No cerramos 'conn' manualmente. Flask-SQLAlchemy o tu pool 
        # lo gestionan. Solo nos aseguramos de cerrar los cursores.
        try:
            with conn.cursor() as cursor:
                # 1. Ejecutar procedimiento para info básica
                cursor.execute("{CALL sp_obtener_legajo_completo_por_personal(?)}", (personal_id,))
                row = cursor.fetchone()
                personal_info = _row_to_dict(cursor, row)
                
                if not personal_info: 
                    return None 

                # 🚀 EL PUENTE MANUAL: Buscamos el nombre de la unidad
                id_unidad = personal_info.get('id_unidad')
                if id_unidad:
                    cursor.execute("SELECT nombre FROM unidad_administrativa WHERE id_unidad = ?", (id_unidad,))
                    unidad_row = cursor.fetchone()
                    personal_info['nombre_unidad'] = unidad_row[0] if unidad_row else "No especificada"
                else:
                    personal_info['nombre_unidad'] = "Sin Unidad Asignada"
                    
                legajo = {"personal": personal_info}
                
                # 2. Cargar sets intermedios del SP (Estudios, Capacitaciones, etc.)
                # nextset() mueve el cursor al siguiente bloque de resultados del SP
                if cursor.nextset(): 
                    legajo["estudios"] = [_row_to_dict(cursor, r) for r in cursor.fetchall()]
                if cursor.nextset(): 
                    legajo["capacitaciones"] = [_row_to_dict(cursor, r) for r in cursor.fetchall()]
                if cursor.nextset(): 
                    legajo["contratos"] = [_row_to_dict(cursor, r) for r in cursor.fetchall()]
                if cursor.nextset(): 
                    legajo["historial_laboral"] = [_row_to_dict(cursor, r) for r in cursor.fetchall()]
                if cursor.nextset(): 
                    legajo["licencias"] = [_row_to_dict(cursor, r) for r in cursor.fetchall()]
                
                # 3. Documentos del Legajo (DNI, CV, etc.)
                query_docs = """
                    SELECT d.*, td.nombre_tipo 
                    FROM documentos d
                    LEFT JOIN tipo_documento td ON d.id_tipo = td.id_tipo
                    WHERE d.id_personal = ? AND d.activo = 1
                    ORDER BY d.fecha_subida DESC
                """
                cursor.execute(query_docs, (personal_id,))
                legajo["documentos"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]

                # 4. RÉCORD LABORAL (PLANILLAS Y PAGOS)
                query_record = """
                    SELECT 
                        id_record, 
                        anio, 
                        mes, 
                        descripcion, 
                        nombre_archivo, 
                        fecha_registro,
                        fecha_inicio, 
                        fecha_fin_vencimiento
                    FROM record_laboral 
                    WHERE id_personal = ? AND activo = 1
                    ORDER BY fecha_registro DESC
                """
                cursor.execute(query_record, (personal_id,))
                legajo["record_laboral"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
                
                return legajo

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"🔥 Error al cargar legajo completo para ID {personal_id}: {e}")
            return None
        # ✅ 'with' cierra el cursor automáticamente. No incluimos conn.close().
        
            
    # Llama a un SP para listar, filtrar y paginar al personal.
    # RUTA: app/infrastructure/persistence/sqlserver_repository.py

    def get_all_paginated(self, page, per_page, filters):
        """
        Obtiene la lista de personal uniendo datos de contratos y cargos de forma segura.
        """
        from app.database import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        
        dni_filter = filters.get('dni') if filters else None
        nombres_filter = filters.get('nombres') if filters else None
        
        try:
            # 1. Ejecutamos el SP para traer DNI y Nombres
            cursor.execute("{CALL sp_listar_personal_paginado(?, ?, ?, ?)}", 
                           page, per_page, dni_filter, nombres_filter)
            results = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
            # 2. Consumimos el total ANTES del bucle para liberar la conexión
            total = 0
            if cursor.nextset():
                total_row = cursor.fetchone()
                total = total_row[0] if total_row else 0
            
            # 🚀 3. EL PARCHE DEFINITIVO (Carga Sueldo y Cargo Real)
            for persona in results:
                # A. Buscamos el SUELDO más reciente en contratos
                cursor.execute("""
                    SELECT TOP 1 sueldo 
                    FROM dbo.contratos 
                    WHERE id_personal = ? 
                    ORDER BY id_contrato DESC
                """, (persona['id_personal'],))
                sueldo_row = cursor.fetchone()
                persona['sueldo'] = sueldo_row[0] if sueldo_row else None
                
                # B. Buscamos el CARGO uniendo Personal con Cargos (Evita el error de columna)
                cursor.execute("""
                    SELECT car.nombre_cargo 
                    FROM dbo.personal p
                    LEFT JOIN dbo.cargos car ON p.id_cargo = car.id_cargo
                    WHERE p.id_personal = ?
                """, (persona['id_personal'],))
                cargo_row = cursor.fetchone()
                persona['nombre_cargo'] = cargo_row[0] if cargo_row else "No asignado"

                # Traducción de unidad para el HTML
                persona['nombre_unidad'] = persona.get('unidad_administrativa') or "Sin Unidad Asignada"
            
            return SimplePagination(results, page, per_page, total)
            
        finally:
            cursor.close()

    # Llama a un SP para crear un nuevo registro de personal.
    def create(self, form_data):
        conn = get_db_write()
        cursor = conn.cursor()
        
        # Normalizar nombres y apellidos a formato título (Primera Letra Mayúscula)
        # Usar .lower() primero para manejar correctamente caracteres especiales como Ñ
        nombres = form_data.get('nombres', '').strip().lower().title() if form_data.get('nombres') else None
        apellidos = form_data.get('apellidos', '').strip().lower().title() if form_data.get('apellidos') else None
        
        # Convertir valores vacíos o '0' a ID 19 ('No especificado') para mantener integridad referencial
        id_unidad = form_data.get('id_unidad')
        if id_unidad in ('0', '', None, 0):
            id_unidad = 19  # ID de 'No especificado' en unidad_administrativa
        
        fecha_ingreso = form_data.get('fecha_ingreso')
        if not fecha_ingreso:
            fecha_ingreso = None
        
        params = (form_data.get('dni'), nombres, apellidos, form_data.get('sexo'),
                  form_data.get('fecha_nacimiento'), form_data.get('direccion'), form_data.get('telefono'),
                  form_data.get('email') or None, form_data.get('estado_civil') or None, form_data.get('nacionalidad'),
                  id_unidad, fecha_ingreso)
        cursor.execute("{CALL sp_registrar_personal(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", params)
        new_id = cursor.fetchone()[0]
        conn.commit()
        return new_id
    
    # 2. ACTUALIZACIÓN: Guardar Documento (Sincronizado con tus nuevas columnas)
    def add_document(self, doc_data, file_bytes):
        conn = get_db_write()
        cursor = conn.cursor()
        # CORRECCIÓN: 'archivo' en lugar de 'archivo_binario'
        query = """
                    INSERT INTO documentos (
                        id_personal, id_tipo, id_seccion, nombre_archivo, 
                        descripcion, archivo, activo, fecha_subida, 
                        fecha_emision, fecha_inicio, fecha_fin
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, GETDATE(), ?, ?, ?)
                """
        params = (
                    doc_data.get('id_personal'), 
                    doc_data.get('id_tipo'), 
                    doc_data.get('id_seccion'), 
                    doc_data.get('nombre_archivo'), 
                    doc_data.get('descripcion'), 
                    file_bytes,
                    doc_data.get('fecha_emision'), # <--- ¡AQUÍ ESTÁ EL ESLABÓN PERDIDO!
                    doc_data.get('fecha_inicio'), 
                    doc_data.get('fecha_fin')
                )
        try:
            cursor.execute(query, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    # Métodos para obtener listas para los formularios SelectField.
    def get_unidades_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_unidad, nombre FROM unidad_administrativa ORDER BY nombre")
        return [(row.id_unidad, row.nombre) for row in cursor.fetchall()]

    def get_secciones_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_seccion, nombre_seccion FROM legajo_secciones ORDER BY id_seccion")
        return [(row.id_seccion, row.nombre_seccion) for row in cursor.fetchall()]



    def get_tipos_documento_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_tipo, nombre_tipo FROM tipo_documento ORDER BY nombre_tipo")
        return [(row.id_tipo, row.nombre_tipo) for row in cursor.fetchall()]

    # Implementación del método de actualización.
    # RUTA: app/infrastructure/persistence/sqlserver_repository.py

    def update(self, personal_id, form_data):
        """
        Actualiza los datos del personal en la BaseDatosHMPP usando el SP.
        Garantiza que el cambio de unidad administrativa (ej. ID 6) se guarde correctamente.
        """
        try:
            # Importación local para asegurar el acceso al conector de escritura
            from app.database.connector import get_db_write
            conn = get_db_write()
            cursor = conn.cursor()
            
            # 1. Normalización de nombres y apellidos (Formato Título)
            nombres = form_data.get('nombres', '').strip().lower().title() if form_data.get('nombres') else None
            apellidos = form_data.get('apellidos', '').strip().lower().title() if form_data.get('apellidos') else None
            
            # 2. Manejo de la Unidad Administrativa (Evita el ID 19 si el dato es válido)
            id_unidad = form_data.get('id_unidad')
            if id_unidad in ('0', '', None, 0, 'None'):
                id_unidad = 19  # 'No especificado' para mantener integridad referencial
            
            # 3. Limpieza de campos opcionales para evitar errores en el SP
            email = form_data.get('email', '').strip() or None
            telefono = form_data.get('telefono', '').strip() or None
            direccion = form_data.get('direccion', '').strip() or None
            nacionalidad = form_data.get('nacionalidad', '').strip() or "Peruana"
            estado_civil = form_data.get('estado_civil') or None
            
            # 4. Preparación de los 13 parámetros exactos para sp_actualizar_personal
            params = (
                personal_id,                    # 1. ID del trabajador
                form_data.get('dni'),           # 2. DNI
                nombres,                        # 3. Nombres
                apellidos,                      # 4. Apellidos
                form_data.get('sexo'),          # 5. Sexo (M/F)
                form_data.get('fecha_nacimiento') or None, # 6. F. Nacimiento
                direccion,                      # 7. Dirección
                telefono,                       # 8. Teléfono
                email,                          # 9. Email
                estado_civil,                   # 10. Estado Civil
                nacionalidad,                   # 11. Nacionalidad
                id_unidad,                      # 12. ID Unidad (ej. 6 para ADMIN)
                form_data.get('fecha_ingreso') or None # 13. F. Ingreso
            )
            
            # 5. Ejecución del Procedimiento Almacenado
            cursor.execute("{CALL sp_actualizar_personal(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", params)
            conn.commit()
            # 3. Actualización Manual (Lógica Personal)
            # Aquí tomamos la nueva llave 'email_personal' que definimos en la ruta
            email_privado_nuevo = form_data.get('email_personal') 
            telefono = form_data.get('telefono')
            direccion = form_data.get('direccion')
            estado_civil = form_data.get('estado_civil')
            query_fix = """
                UPDATE personal 
                SET email_personal = ?,  -- Aquí se guarda el privado (ejemplo1@gmail.com)
                    telefono = ?,
                    direccion = ?,
                    estado_civil = ?
                WHERE id_personal = ?
            """
            cursor.execute(query_fix, (email_privado_nuevo, telefono, direccion, estado_civil, personal_id))
            
            conn.commit()
            # --- CLAVE DEL ÉXITO: Devolver True para que la Ruta de Flask sepa que funcionó ---
            return True 

        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            # Este mensaje aparecerá en tu terminal de VS Code para depuración
            print(f"Error crítico al actualizar personal ID {personal_id}: {str(e)}")
            return False
        finally:
            cursor.close()


    # Llama a un SP para obtener todos los datos necesarios para el reporte general.
    def get_all_for_report(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_generar_reporte_general_personal}")
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]     
    
    # Llama al SP para el borrado suave (desactivación) de un empleado.
    def delete_by_id(self, personal_id):
        """
        Baja integral sincronizada. Apaga el legajo y el usuario al mismo tiempo.
        Esto garantiza consistencia para los 3 roles de la HMPP.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # 1. Inactivar el legajo (Visto por Administrador de Legajos)
            cursor.execute("UPDATE personal SET activo = 0 WHERE id_personal = ?", personal_id)
            
            # 2. Inactivar el usuario vinculado (Visto por Sistemas y RRHH)
            # Usamos el id_personal como puente directo, ignorando correos nulos.
            cursor.execute("UPDATE usuarios SET activo = 0 WHERE id_personal = ?", personal_id)
            
            conn.commit()
            logger.info(f"BAJA SINCRONIZADA: Personal y Usuario ID {personal_id} inactivados con éxito.")
            return True
        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"Error crítico en baja sincronizada para ID {personal_id}: {e}")
            raise e
        finally:
            cursor.close()
    
    def activate_by_id(self, personal_id):
        """Reactiva un empleado previamente desactivado."""
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_reactivar_personal(?)}", personal_id)
        conn.commit()
        
    def find_by_id(self, personal_id):
        """
        Busca un registro de personal por su ID.
        VERSIÓN BLINDADA: Usa context manager para el cursor y protege la conexión global.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG REPO] Buscando Personal ID: {personal_id}") 
        
        # 1. Obtenemos la conexión (No la cerramos aquí, Flask lo hará al final del request)
        from app.database.connector import get_db_read
        conn = get_db_read()
        
        try:
            # 2. 🛡️ El bloque 'with' asegura que el cursor se limpie solo al terminar
            # pero deja que 'conn' siga disponible para el resto de la página.
            with conn.cursor() as cursor:
                # Ejecutamos el Stored Procedure
                cursor.execute("{CALL sp_obtener_personal_por_id(?)}", (personal_id,))
                row = cursor.fetchone()
                
                if row:
                    # Convertimos la fila cruda de SQL Server a un diccionario Python
                    row_dict = _row_to_dict(cursor, row)
                    
                    # 💡 ASEGURAR ID: Garantizamos que el objeto tenga su llave primaria
                    # para que los botones de 'Editar' o 'Ver' funcionen en la web.
                    row_dict['id_personal'] = personal_id 
                    
                    # Transformamos el diccionario al Objeto de Dominio 'Personal'
                    personal_obj = Personal.from_dict(row_dict)

                    if personal_obj and hasattr(personal_obj, 'nombres'):
                        logger.info(f"[DEBUG REPO] Registro encontrado: {personal_obj.nombres} {personal_obj.apellidos}")
                    
                    return personal_obj
                
                logger.warning(f"[DEBUG REPO] Registro NO encontrado para ID: {personal_id}.")
                return None
                
        except Exception as e:
            logger.error(f"Error crítico al buscar Personal ID {personal_id}: {str(e)}", exc_info=True)
            return None
        
        # ✅ NOTA: No hay 'finally' con cursor.close() porque el 'with' lo hace por ti.
        # ❌ NUNCA pongas conn.close() aquí si quieres que el legajo cargue completo.



    def get_tipos_documento_by_seccion(self, id_seccion):
        """
        Consulta DIRECTA (Ignorando el SP). 
        Apunta a la tabla correcta: tipo_documento_seccion_relacion
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
                SELECT 
                    t.id_tipo, 
                    t.nombre_tipo 
                FROM tipo_documento t
                INNER JOIN tipo_documento_seccion_relacion r ON t.id_tipo = r.id_tipo_documento
                WHERE r.id_seccion = ?
                ORDER BY t.nombre_tipo ASC
            """
            cursor.execute(query, id_seccion)
            
            # Devolvemos la lista de diccionarios para el JavaScript
            return [{"id": row[0], "nombre": row[1]} for row in cursor.fetchall()]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al listar tipos de documento por sección: {e}")
            return []
        finally:
            cursor.close()     

    def count_empleados_por_unidad(self):
        """
        Realiza una consulta para contar el número de empleados activos
        en cada unidad administrativa.
        """
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            query = """
                SELECT ua.nombre AS nombre_unidad, COUNT(p.id_personal) AS cantidad
                FROM unidad_administrativa ua
                LEFT JOIN personal p ON ua.id_unidad = p.id_unidad AND p.activo = 1
                GROUP BY ua.nombre, ua.id_unidad
                ORDER BY cantidad DESC;
            """
            cursor.execute(query)
            result = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
            return result if result else []
        except Exception as e:
            print(f"ERROR en count_empleados_por_unidad: {str(e)}")
            return []

    def count_empleados_por_estado(self):
        """Cuenta el número de empleados activos e inactivos."""
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            query = """
                SELECT 
                    CASE WHEN activo = 1 THEN 'Activos' ELSE 'Inactivos' END AS estado,
                    COUNT(id_personal) AS cantidad
                FROM personal
                GROUP BY activo;
            """
            cursor.execute(query)
            result = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
            cursor.close() # Solo cerrar cursor
            return result if result else []
        except Exception as e:
            print(f"ERROR en count_empleados_por_estado: {str(e)}")
            return []

    def count_empleados_por_sexo(self):
        """Cuenta el número de empleados por sexo."""
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            query = """
                SELECT 
                    CASE WHEN sexo = 'M' THEN 'Masculino' WHEN sexo = 'F' THEN 'Femenino' ELSE 'No especificado' END AS sexo,
                    COUNT(id_personal) AS cantidad
                FROM personal
                GROUP BY sexo;
            """
            cursor.execute(query)
            result = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
            cursor.close() # Solo cerrar cursor
            return result if result else []
        except Exception as e:
            print(f"ERROR en count_empleados_por_sexo: {str(e)}")
            return []


    def get_deleted_documents(self):
        """
        Obtiene documentos eliminados unificados (Legajo + Récord Laboral).
        Consulta la vista v_auditoria_papelera_unificada.
        """
        deleted_docs = []
        conn = get_db_read()
        cursor = conn.cursor()
        
        try:
            query = "SELECT * FROM v_auditoria_papelera_unificada ORDER BY fecha_accion DESC"
            cursor.execute(query)
            documents = cursor.fetchall()
            
            for row in documents:
                raw_dict = _row_to_dict(cursor, row)
                if raw_dict:
                    doc_dict = {k.lower(): v for k, v in raw_dict.items()}
                    
                    # Mapeo para que el HTML no se rompa
                    doc_dict['id_documento'] = doc_dict.get('id_interno')
                    doc_dict['nombre_personal'] = doc_dict.get('personal')
                    doc_dict['tipo_documento'] = doc_dict.get('tipo_doc')
                    doc_dict['fecha_eliminacion'] = doc_dict.get('fecha_accion')
                    
                    deleted_docs.append(doc_dict)
            
            return deleted_docs
        except Exception as e:
            logger.error(f"Error en auditoría unificada: {e}")
            return []
        finally:
            cursor.close()


    def recover_document(self, document_id):
        """
        Restaura un documento de la papelera unificada (Récord Laboral o Legajo).
        Aplica la lógica de 'Intento y Error' en ambas tablas.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        conn = get_db_write()
        cursor = conn.cursor()
        
        try:
            # --- FASE 1: Intentar en Récord Laboral ---
            # Buscamos reactivar el registro en la nueva tabla de pagos
            cursor.execute("UPDATE record_laboral SET activo = 1 WHERE id_record = ?", document_id)
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"Documento {document_id} recuperado de record_laboral exitosamente.")
                return True

            # --- FASE 2: Intentar en Legajos (Tu lógica original) ---
            try:
                # INTENTO 1: Usar SP si existe
                logger.info(f"Intentando recuperar de legajos usando SP...")
                cursor.execute("{CALL sp_recuperar_documento(?)}", document_id)
                conn.commit()
                logger.info(f"Documento {document_id} recuperado de legajos via SP.")
                return True
                
            except Exception as sp_error:
                logger.warning(f"SP falló: {sp_error}. Intentando UPDATE directo en documentos...")
                
                # INTENTO 2: Fallback - UPDATE directo en tabla documentos
                cursor.execute(
                    "UPDATE documentos SET activo = 1, fecha_eliminacion = NULL WHERE id_documento = ?",
                    document_id
                )
                conn.commit()
                logger.info(f"Documento {document_id} recuperado de legajos via UPDATE directo.")
                return True

        except Exception as e:
            logger.error(f"Error crítico al recuperar documento {document_id}: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()

    def permanently_delete_document(self, document_id):
        """
        Elimina permanentemente un documento de la BD (Récord Laboral o Legajo).
        Asegura que el archivo desaparezca de la papelera unificada.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        conn = get_db_write()
        cursor = conn.cursor()
        
        try:
            # --- FASE 1: Intentar borrar de Récord Laboral ---
            cursor.execute("DELETE FROM record_laboral WHERE id_record = ?", document_id)
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"Documento {document_id} eliminado permanentemente de record_laboral.")
                return True

            # --- FASE 2: Intentar borrar de Legajos (Tu lógica original) ---
            try:
                # INTENTO 1: Usar SP si existe
                logger.info(f"Intentando eliminación permanente en legajos usando SP...")
                cursor.execute("{CALL sp_eliminar_documento_permanente(?)}", document_id)
                conn.commit()
                logger.info(f"Documento {document_id} eliminado de legajos via SP.")
                return True
                
            except Exception as sp_error:
                logger.warning(f"SP falló: {sp_error}. Intentando DELETE directo en documentos...")
                
                # INTENTO 2: Fallback - DELETE directo en tabla documentos
                cursor.execute("DELETE FROM documentos WHERE id_documento = ?", document_id)
                conn.commit()
                logger.info(f"Documento {document_id} eliminado de legajos via DELETE directo.")
                return True

        except Exception as e:
            logger.error(f"Error crítico al eliminar permanentemente documento {document_id}: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()

    # 3. ACTUALIZACIÓN: Búsqueda de documentos (Ya estaba bien, pero aseguramos columnas)
    def search_documents(self, query=None, id_seccion=None, id_tipo=None):
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT 
                    d.id_documento, d.nombre_archivo, d.descripcion, d.fecha_emision,
                    d.fecha_subida, d.fecha_inicio, d.fecha_fin, -- Columnas para alertas
                    d.id_personal, d.id_seccion, d.id_tipo,
                    p.dni, p.nombres, p.apellidos,
                    ls.nombre_seccion, td.nombre_tipo
                FROM documentos d
                INNER JOIN personal p ON d.id_personal = p.id_personal
                LEFT JOIN legajo_secciones ls ON d.id_seccion = ls.id_seccion
                LEFT JOIN tipo_documento td ON d.id_tipo = td.id_tipo
                WHERE d.activo = 1
            """
            # ... (mantener el resto de la lógica de filtros igual)
            params = []
            
            # Filtro por texto (descripción o nombre de archivo)
            if query:
                sql += " AND (d.descripcion LIKE ? OR d.nombre_archivo LIKE ? OR p.nombres LIKE ?)"
                search_term = f"%{query}%"
                params.extend([search_term, search_term, search_term])
            
            # Filtro por sección
            if id_seccion and int(id_seccion) > 0:
                sql += " AND d.id_seccion = ?"
                params.append(int(id_seccion))
            
            # Filtro por tipo de documento
            if id_tipo and int(id_tipo) > 0:
                sql += " AND d.id_tipo = ?"
                params.append(int(id_tipo))
            
            sql += " ORDER BY d.fecha_subida DESC"
            cursor.execute(sql, params)
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en búsqueda de documentos: {e}")
            return []
        finally:
            cursor.close()

    # ========================================================================
    # MÉTODOS PARA GESTIÓN DE SECCIONES (AdministradorLegajos)
    # ========================================================================
    
    def get_all_secciones(self):
        """Obtiene todas las secciones de legajo."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_seccion, nombre_seccion FROM legajo_secciones ORDER BY nombre_seccion")
            return [{'id_seccion': row.id_seccion, 'nombre_seccion': row.nombre_seccion} for row in cursor.fetchall()]
        finally:
            cursor.close()
    
    def get_seccion_by_id(self, id_seccion):
        """Obtiene una sección por su ID."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_seccion, nombre_seccion FROM legajo_secciones WHERE id_seccion = ?", id_seccion)
            row = cursor.fetchone()
            return {'id_seccion': row.id_seccion, 'nombre_seccion': row.nombre_seccion} if row else None
        finally:
            cursor.close()
    
    def create_seccion(self, nombre_seccion):
        """Crea una nueva sección de legajo."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO legajo_secciones (nombre_seccion) VALUES (?)", nombre_seccion)
            conn.commit()
            cursor.execute("SELECT @@IDENTITY as id_seccion")
            return cursor.fetchone()[0]
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def update_seccion(self, id_seccion, nombre_seccion):
        """Actualiza una sección existente."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE legajo_secciones SET nombre_seccion = ? WHERE id_seccion = ?", 
                          nombre_seccion, id_seccion)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def delete_seccion(self, id_seccion):
        """Elimina una sección de legajo."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM legajo_secciones WHERE id_seccion = ?", id_seccion)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    # ========================================================================
    # MÉTODOS PARA GESTIÓN DE TIPOS DE DOCUMENTO (AdministradorLegajos)
    # ========================================================================
    
    def get_all_tipos_documento(self):
        """Obtiene todos los tipos de documento."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_tipo, nombre_tipo FROM tipo_documento ORDER BY nombre_tipo")
            return [{'id_tipo': row.id_tipo, 'nombre_tipo': row.nombre_tipo} for row in cursor.fetchall()]
        finally:
            cursor.close()
    
    def get_tipo_documento_by_id(self, id_tipo):
        """Obtiene un tipo de documento por su ID."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_tipo, nombre_tipo FROM tipo_documento WHERE id_tipo = ?", id_tipo)
            row = cursor.fetchone()
            return {'id_tipo': row.id_tipo, 'nombre_tipo': row.nombre_tipo} if row else None
        finally:
            cursor.close()
    
    def create_tipo_documento(self, nombre_tipo):
        """Crea un nuevo tipo de documento."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO tipo_documento (nombre_tipo) VALUES (?)", nombre_tipo)
            conn.commit()
            cursor.execute("SELECT @@IDENTITY as id_tipo")
            return cursor.fetchone()[0]
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def update_tipo_documento(self, id_tipo, nombre_tipo):
        """Actualiza un tipo de documento existente."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE tipo_documento SET nombre_tipo = ? WHERE id_tipo = ?", 
                          nombre_tipo, id_tipo)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def delete_tipo_documento(self, id_tipo):
        """Elimina un tipo de documento."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tipo_documento WHERE id_tipo = ?", id_tipo)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    # ========================================================================
    # MÉTODOS PARA GESTIÓN DE RELACIÓN TIPO_DOCUMENTO - SECCIÓN
    # ========================================================================
    
    def get_secciones_by_tipo_documento(self, id_tipo):
        """Obtiene las secciones asociadas a un tipo de documento."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
            SELECT ls.id_seccion, ls.nombre_seccion 
            FROM tipo_documento_seccion_relacion tdsr
            JOIN legajo_secciones ls ON tdsr.id_seccion = ls.id_seccion
            WHERE tdsr.id_tipo_documento = ?
            ORDER BY ls.nombre_seccion
            """
            cursor.execute(query, id_tipo)
            return [{'id_seccion': row.id_seccion, 'nombre_seccion': row.nombre_seccion} for row in cursor.fetchall()]
        finally:
            cursor.close()
    
    def add_tipo_documento_to_seccion(self, id_tipo, id_seccion):
        """Asocia un tipo de documento a una sección."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # Verificar si ya existe la relación
            cursor.execute(
                "SELECT 1 FROM tipo_documento_seccion_relacion WHERE id_tipo_documento = ? AND id_seccion = ?", 
                id_tipo, id_seccion
            )
            if cursor.fetchone():
                return False  # Ya existe la relación
            
            cursor.execute(
                "INSERT INTO tipo_documento_seccion_relacion (id_tipo_documento, id_seccion) VALUES (?, ?)", 
                id_tipo, id_seccion
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def remove_tipo_documento_from_seccion(self, id_tipo, id_seccion):
        """Elimina la asociación entre un tipo de documento y una sección."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM tipo_documento_seccion_relacion WHERE id_tipo_documento = ? AND id_seccion = ?", 
                id_tipo, id_seccion
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    

    # RUTA: app/infrastructure/repositories/sqlserver_repository.py

    def get_documentos_filtrados(self, id_personal, nombre_seccion):
        """
        Trae solo los documentos de una sección específica (ej: 'Récord Laboral').
        Esto mantiene la tabla de RRHH limpia de otros archivos del legajo.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        query = """
            SELECT 
                d.id_documento, d.nombre_archivo, d.descripcion, 
                d.fecha_subida, d.fecha_inicio, d.fecha_fin,
                td.nombre_tipo
            FROM documentos d
            JOIN tipo_documento td ON d.id_tipo = td.id_tipo
            JOIN legajo_secciones ls ON d.id_seccion = ls.id_seccion
            WHERE d.id_personal = ? 
            AND ls.nombre_seccion = ?  -- Filtro por nombre de sección
            AND d.activo = 1
            ORDER BY d.fecha_subida DESC
        """
        cursor.execute(query, id_personal, nombre_seccion)
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]


    def get_personal_para_escalafon(self, page, per_page, dni=None, nombres=None):
        """
        Versión final HÍBRIDA (Moderno + Histórico).
        Lee el 'id_tipo_contrato' directamente de la tabla personal.
        Si el trabajador NO tiene sueldo/cargo moderno (cesado antiguo), 
        busca inteligentemente en la bóveda de 'Planillas_Historicas'.
        """
        from app.database.connector import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        
        # 🚀 SQL HÍBRIDO (El Cerebro del Récord Unificado)
        query = """
            SELECT 
                p.id_personal, p.dni, p.nombres, p.apellidos, p.activo,
                
                -- CARGO: Si tiene contrato moderno usa ese, si no, usa el último histórico
                COALESCE(c.nombre_cargo, ph.cargo_historico, 'No asignado') AS nombre_cargo, 
                
                -- UNIDAD: Misma lógica híbrida
                COALESCE(u.nombre, ph.unidad_historica, 'Sin Unidad Asignada') AS nombre_unidad,
                
                -- SUELDO: Si hay contrato moderno lo usa, si no, usa el último neto histórico
                COALESCE(con.sueldo, ph.monto_neto, 0.00) AS sueldo,
                
                -- CONTRATO: Muestra el actual o etiqueta como 'Histórico' si viene del pasado
                COALESCE(tc.nombre_tipo, CASE WHEN ph.id_planilla_historica IS NOT NULL THEN 'HISTÓRICO' ELSE 'S/N' END) AS nombre_tipo_contrato,
                
                COUNT(*) OVER() as total_count
            FROM dbo.personal p
            
            -- JOINS MODERNOS (Lo de siempre)
            LEFT JOIN dbo.cargos c ON p.id_cargo = c.id_cargo
            LEFT JOIN dbo.unidad_administrativa u ON p.id_unidad = u.id_unidad 
            LEFT JOIN dbo.tipos_contrato tc ON p.id_tipo_contrato = tc.id_tipo_contrato
            LEFT JOIN dbo.contratos con ON con.id_contrato = (
                SELECT MAX(id_contrato) FROM dbo.contratos 
                WHERE id_personal = p.id_personal
            )
            
            -- 🕰️ JOIN AL PASADO (La Bóveda Histórica)
            -- Trae la planilla más reciente guardada en la bóveda de esta persona
            LEFT JOIN dbo.Planillas_Historicas ph ON ph.id_planilla_historica = (
                SELECT TOP 1 id_planilla_historica 
                FROM dbo.Planillas_Historicas 
                WHERE id_personal = p.id_personal 
                ORDER BY anio DESC, 
                         CASE mes 
                            WHEN 'Diciembre' THEN 12 WHEN 'Noviembre' THEN 11 WHEN 'Octubre' THEN 10
                            WHEN 'Septiembre' THEN 9 WHEN 'Agosto' THEN 8 WHEN 'Julio' THEN 7
                            WHEN 'Junio' THEN 6 WHEN 'Mayo' THEN 5 WHEN 'Abril' THEN 4
                            WHEN 'Marzo' THEN 3 WHEN 'Febrero' THEN 2 WHEN 'Enero' THEN 1
                         END DESC
            )
            WHERE 1=1
        """
        
        params = []
        if dni:
            query += " AND p.dni LIKE ?"
            params.append(f"%{dni}%")
        if nombres:
            query += " AND (p.nombres LIKE ? OR p.apellidos LIKE ?)"
            params.extend([f"%{nombres}%", f"%{nombres}%"])

        query += " ORDER BY p.apellidos ASC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, per_page])

        try:
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            total = results[0]['total_count'] if results else 0
            return results, total
        except Exception as e:
            print(f"DEBUG ERROR SQL HÍBRIDO: {str(e)}")
            raise e
        finally:
            cursor.close()

    def get_personal_by_id(self, id_personal):
        """
        Obtiene la información básica de un trabajador incluyendo el ID de contrato
        para que los encabezados de RRHH funcionen correctamente.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # ✅ CORRECCIÓN: Agregamos 'id_tipo_contrato' al SELECT
            query = """
                SELECT id_personal, nombres, apellidos, dni, activo, id_tipo_contrato 
                FROM personal 
                WHERE id_personal = ? 
            """
            cursor.execute(query, (id_personal,)) # Pasamos como tupla para evitar errores de tipo
            row = cursor.fetchone()
            
            # _row_to_dict ahora sí encontrará el campo y lo enviará al HTML
            return _row_to_dict(cursor, row) if row else None
        except Exception as e:
            print(f"🔥 Error crítico en get_personal_by_id: {e}")
            return None
        finally:
            cursor.close()

    def add_record_laboral(self, data, file_bytes):
        """Guarda el récord capturando el tiempo exacto del sistema."""
        from datetime import datetime # Nos aseguramos de que datetime esté disponible
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            ahora = datetime.now() 
            
            query = """
                INSERT INTO record_laboral 
                (id_personal, anio, mes, dia, hora, nombre_archivo, archivo_binario, 
                 descripcion, fecha_inicio, fecha_fin_vencimiento)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                data['id_personal'], ahora.year, ahora.month, ahora.day, ahora.strftime('%H:%M:%S'),
                data['nombre_archivo'], file_bytes, data['descripcion'],
                data['fecha_inicio'], 
                data['fecha_fin_vencimiento']  # 🔥 AQUÍ ESTABA EL ERROR (se llamaba diferente)
            )
            cursor.execute(query, params)
            conn.commit()
            print("✅ Récord guardado exitosamente en BD.")
            return True
        except Exception as e:
            print(f"!!! FALLO EN SQL SERVER: {e}") 
            conn.rollback()
            return False
        finally:
            cursor.close()
            

    def get_records_by_personal(self, id_personal):
        """
        Trae el historial completo de la tabla record_laboral.
        Sincronizado para mostrar fechas, horas, archivos y descripciones sin errores.
        """
        from app.database import get_db_read # Asegúrate de que la ruta de importación sea la correcta
        conn = get_db_read()
        cursor = conn.cursor()
        
        try:
            # 🚀 CAMBIOS CLAVE:
            # 1. Seleccionamos columnas específicas para evitar errores de columnas inexistentes.
            # 2. Usamos 'fecha_inicio' y 'fecha_fin_vencimiento' en lugar de anio/mes.
            # 3. Incluimos 'nombre_archivo' y 'descripcion' para que no salgan vacíos.
            # 4. Ordenamos por 'fecha_registro' para ver lo más reciente al principio.
            
            query = """
                SELECT 
                    id_record, 
                    fecha_inicio,           -- 📅 Fecha del periodo/contrato
                    fecha_fin_vencimiento,  -- 📅 Fecha de vigencia
                    fecha_registro,         -- 🕒 Marca de tiempo del sistema (Evita ceros)
                    descripcion,            -- 📝 Descripción del documento
                    nombre_archivo,         -- 📄 Nombre del PDF/Excel
                    archivo_ruta, 
                    activo 
                FROM dbo.record_laboral 
                WHERE id_personal = ? AND activo = 1 
                ORDER BY fecha_registro DESC
            """
            
            # 🚀 CORRECCIÓN DE PARÁMETRO:
            # Se debe pasar como una tupla (id_personal,) para evitar errores de ejecución en SQL Server.
            cursor.execute(query, (id_personal,))
            
            # Convertimos las filas a diccionarios para que Flask pueda leerlos fácilmente
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
        except Exception as e:
            print(f"❌ Error al obtener récords de personal #{id_personal}: {str(e)}")
            return [] # Devolvemos lista vacía para que la tabla no rompa la página
            
        finally:
            cursor.close()
    
    def get_record_file_by_id(self, id_record):
        """Recupera el archivo binario de la tabla record_laboral para su visualización."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # Usamos el nombre de columna 'archivo_binario' que definiste en tu INSERT
            query = "SELECT archivo_binario, nombre_archivo FROM record_laboral WHERE id_record = ?"
            cursor.execute(query, (id_record,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'contenido': row[0],
                    'nombre_archivo': row[1]
                }
            return None
        except Exception as e:
            print(f"Error al obtener archivo binario: {e}")
            return None
        finally:
            cursor.close()

    def delete_record_laboral(self, id_record):
        """
        Realiza una baja lógica del registro y captura el momento exacto de la acción.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # Actualizamos activo y guardamos la fecha de eliminación actual
            query = """
                UPDATE record_laboral 
                SET activo = 0, fecha_eliminacion = GETDATE() 
                WHERE id_record = ?
            """
            cursor.execute(query, (id_record,))
            conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            print(f"!!! ERROR AL ELIMINAR REGISTRO {id_record}: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

    def get_deleted_records_report(self):
        """
        Opcional: Recupera todos los registros eliminados para un reporte de auditoría.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = "SELECT * FROM record_laboral WHERE activo = 0 ORDER BY anio DESC"
            cursor.execute(query)
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    
    # RUTA: app/infrastructure/persistence/sqlserver_repository.py

    def create_personal_basico(self, nombres, apellidos, dni, sexo, id_unidad, email, fecha_nacimiento, nacionalidad, activo=1):
        from app.database.connector import get_db_admin 
        conn = get_db_admin() 
        cursor = conn.cursor()
        try:
            # Añadimos los campos que estaban causando el bloqueo en el formulario
            query = """
            INSERT INTO personal (dni, nombres, apellidos, sexo, id_unidad, email, fecha_nacimiento, nacionalidad, activo) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, (dni, nombres, apellidos, sexo, id_unidad, email, fecha_nacimiento, nacionalidad, activo)) 
            conn.commit()

            cursor.execute("SELECT @@IDENTITY AS id_personal")
            new_id = cursor.fetchone()[0]
            return type('Personal', (), {'id_personal': new_id})()
        except Exception as e:
            if conn: conn.rollback()
            raise Exception(f"Error al crear personal con campos completos: {e}")
    # RECUPERAR Y ELIMAR MASIVO


    def recover_all_documents(self):
        """Restaura todos los documentos de ambas tablas de forma masiva."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # Restaurar Récords Laborales
            cursor.execute("UPDATE record_laboral SET activo = 1, fecha_eliminacion = NULL WHERE activo = 0")
            # Restaurar Legajos
            cursor.execute("UPDATE documentos SET activo = 1, fecha_eliminacion = NULL WHERE activo = 0")
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            cursor.close()

    def empty_recycle_bin(self):
        """Elimina permanentemente todos los registros inactivos (Vaciar Papelera)."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM record_laboral WHERE activo = 0")
            cursor.execute("DELETE FROM documentos WHERE activo = 0")
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            cursor.close()

    # Dentro de SqlServerPersonalRepository en sqlserver_repository.py

    def existe_dni_en_otros(self, dni, id_personal_actual):
        """
        Verifica si un DNI ya existe en la municipalidad, 
        pero ignora al trabajador que estamos editando actualmente.
        """
        from app.database.connector import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        
        # 🚀 LA LÓGICA DE INGENIERÍA:
        # Buscamos el DNI pero pedimos que el ID sea DIFERENTE (<>) al actual.
        query = "SELECT COUNT(*) FROM personal WHERE dni = ? AND id_personal <> ?"
        
        cursor.execute(query, (dni, id_personal_actual))
        resultado = cursor.fetchone()
        
        # Si el conteo es mayor a 0, significa que el DNI ya lo tiene OTRA persona
        return resultado[0] > 0
    

    # AGREGAR AL FINAL DE LA CLASE SqlServerPersonalRepository

    def get_contratos_directo(self, id_personal):
        """
        Consulta de emergencia directa a la tabla contratos para obtener fechas.
        """
        from app.database import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
                SELECT id_contrato, fecha_inicio, fecha_fin, sueldo
                FROM contratos
                WHERE id_personal = ?
                ORDER BY fecha_inicio DESC
            """
            cursor.execute(query, id_personal)
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error en get_contratos_directo: {e}")
            return []
        finally:
            cursor.close()




# Implementación completa, corregida y BLINDADA del repositorio de auditoría.
import logging

logger = logging.getLogger(__name__)

class SqlServerAuditoriaRepository(IAuditoriaRepository):
    
    # Llama a un SP para registrar un evento en la bitácora.
    def log_event(self, id_usuario, modulo, accion, descripcion, detalle_json=None):
        conn = None
        cursor = None
        try:
            conn = get_db_write()
            cursor = conn.cursor()
            cursor.execute(
                "{CALL sp_registrar_bitacora(?, ?, ?, ?, ?)}", 
                id_usuario, modulo, accion, descripcion, detalle_json
            )
            conn.commit()
        except Exception as e:
            # Si la auditoría falla, guardamos el error en un archivo de texto del servidor,
            # pero hacemos "rollback" para que no se corrompa la BD.
            if conn:
                conn.rollback()
            logger.error(f"Fallo crítico al registrar auditoría ({accion}): {str(e)}")
        finally:
            # SIEMPRE cerrar el cursor para liberar memoria del servidor
            if cursor:
                cursor.close()

    # Obtiene los logs de forma paginada.
    def get_all_logs_paginated(self, page, per_page):
        conn = None
        cursor = None
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            
            # Llama a un SP que maneja la paginación de la tabla bitacora.
            cursor.execute("{CALL sp_listar_bitacora_paginada(?, ?)}", page, per_page)
            
            # Procesa los resultados.
            results = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
            # Obtiene el total de registros para los controles de paginación.
            if cursor.nextset():
                total_row = cursor.fetchone()
                total = total_row[0] if total_row else 0
            else:
                total = len(results)
                
            return SimplePagination(results, page, per_page, total)
            
        except Exception as e:
            logger.error(f"Error al listar la bitácora paginada: {str(e)}")
            # En caso de error, devolvemos una paginación vacía para que no se rompa la pantalla web
            return SimplePagination([], page, per_page, 0)
        finally:
            # SIEMPRE cerrar el cursor
            if cursor:
                cursor.close()

class SqlServerBackupRepository:
    # --- SECCIÓN DE BACKUPS SINCRONIZADA CON .ENV ---
    # RUTA: app/infrastructure/persistence/sqlserver_repository.py

    def run_db_backup(self, db_name, file_path):
        try:
            db_server = os.getenv('DB_SERVER')
            db_username = os.getenv('DB_USERNAME_WRITE')
            db_password = os.getenv('DB_PASSWORD_WRITE')

            if not all([db_server, db_username, db_password]):
                raise ValueError("Variables de BD no configuradas en .env")

            backup_query = f"BACKUP DATABASE [{db_name}] TO DISK = N'{file_path}' WITH FORMAT, STATS = 10;"
            
            # 🚀 EL PARCHE FINAL: Añadimos "-C" para ignorar el error de certificado SSL
            sqlcmd_command = [
                "sqlcmd", 
                "-S", db_server, 
                "-U", db_username, 
                "-P", db_password, 
                "-C",  # <--- CONFÍA EN EL CERTIFICADO (Trust Server Certificate)
                "-Q", backup_query, 
                "-b"
            ]

            process = subprocess.run(sqlcmd_command, capture_output=True, text=True, timeout=120, check=False)
            
            if process.returncode == 0:
                print(f"---[ÉXITO]: Backup creado en {file_path}")
                return True
            else:
                error_message = f"FALLO SQLCMD: {process.stderr}"
                print(error_message)
                raise Exception(error_message)
        except Exception as e:
            print(f"!!! ERROR INESPERADO en run_db_backup: {e}")
            raise


    # RUTA: app/infrastructure/persistence/sqlserver_repository.py

    # RUTA: app/infrastructure/persistence/sqlserver_repository.py

    def get_backup_history(self):
        """
        Obtiene los últimos 5 backups leyendo el tamaño real de 'detalle_json'.
        """
        try:
            from app.database.connector import get_db_read
            import json
            conn = get_db_read()
            cursor = conn.cursor()
            
            # 🚀 CORRECCIÓN: Seleccionamos la columna real 'detalle_json'
            query = """
                SELECT TOP 5 
                    fecha_hora AS fecha_registro, 
                    modulo, 
                    descripcion, 
                    'FULL' AS Tipo, 
                    'Éxito' AS Estado,
                    detalle_json -- <--- AQUÍ ESTÁ EL PESO REAL
                FROM bitacora 
                WHERE accion IN ('BACKUP', 'COPIA_SEGURIDAD') 
                ORDER BY fecha_registro DESC;
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            historial_real = []
            for row in rows:
                item = _row_to_dict(cursor, row)
                
                # 🚀 EXTRACCIÓN DINÁMICA:
                tamanio_mostrado = "Calculando..." 
                if item.get('detalle_json'):
                    try:
                        # Convertimos el texto JSON en datos de Python
                        meta_datos = json.loads(item['detalle_json'])
                        tamanio_mostrado = meta_datos.get('tamano', 'Sin registro')
                    except:
                        tamanio_mostrado = "Error format"
                
                # Reemplazamos el valor para la tabla web
                item['Tamanio'] = tamanio_mostrado
                historial_real.append(item)
                
            return historial_real
        except Exception as e:
            print(f"!!! ERROR al mostrar historial real: {e}")
            return []

    # --- SECCIÓN DE MANEJO DE ERRORES (Añadida anteriormente) ---
    def registrar_error(self, modulo, descripcion, usuario_id=None):
        conn = None
        try:
            from app.database.connector import get_db_write
            conn = get_db_write()
            cursor = conn.cursor()
            sql = "INSERT INTO bitacora (fecha_hora, accion, modulo, descripcion, id_usuario) VALUES (GETDATE(), ?, ?, ?, ?)"
            cursor.execute(sql, 'ERROR', modulo, descripcion, usuario_id)
            conn.commit()
        except Exception as e:
            print(f"!!! FALLO AL REGISTRAR ERROR EN LA BITÁCORA: {e}")
            if conn:
                conn.rollback()

    def obtener_historial_errores(self):
        try:
            from app.database.connector import get_db_read
            conn = get_db_read()
            cursor = conn.cursor()
            query = """
            SELECT TOP 50 b.fecha_hora, b.modulo, b.descripcion, u.username AS usuario
            FROM bitacora b LEFT JOIN usuarios u ON b.id_usuario = u.id_usuario
            WHERE b.accion = 'ERROR' ORDER BY b.fecha_hora DESC;
            """
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"!!! ERROR OBTENIENDO HISTORIAL DE ERRORES: {e}")
            return []

    # --- NUEVA LÓGICA PARA EL BORRADO SUAVE (SOFT DELETE) ---

    def solicitar_eliminacion_documento(self, documento_id, solicitante_id):
        """
        Realiza un borrado suave: cambia el estado del documento y crea una solicitud.
        Todo dentro de una única transacción para garantizar la consistencia.
        """
        conn = None
        try:
            from app.database.connector import get_db_write
            conn = get_db_write()
            cursor = conn.cursor()

            # 1. Obtener los detalles del documento antes de hacer nada
            # Nos aseguramos de obtener la llave primaria de legajo (id_legajo)
            cursor.execute("SELECT id_legajo, nombre_archivo, ruta_archivo FROM documentos WHERE id_documento = ?", documento_id)
            doc_row = cursor.fetchone()
            if not doc_row:
                raise Exception(f"No se encontró el documento con ID {documento_id}.")
            
            id_legajo, nombre_archivo, ruta_archivo = doc_row

            # Inicia la transacción
            conn.autocommit = False

            # 2. Actualizar el estado del documento para "ocultarlo"
            sql_update = "UPDATE documentos SET estado = 'PENDIENTE_ELIMINACION' WHERE id_documento = ?"
            cursor.execute(sql_update, documento_id)

            # 3. Insertar el registro en la tabla de solicitudes para que el admin de sistemas lo vea
            sql_insert_solicitud = """
            INSERT INTO solicitudes_eliminacion 
            (id_documento, nombre_documento, ruta_archivo, id_legajo, solicitado_por_id, estado)
            VALUES (?, ?, ?, ?, ?, 'PENDIENTE')
            """
            cursor.execute(sql_insert_solicitud, documento_id, nombre_archivo, ruta_archivo, id_legajo, solicitante_id)

            # Si todo fue bien, confirma la transacción
            conn.commit()
            print(f"---[INFO]: Solicitud de eliminación creada para el documento ID {documento_id}")
            return True

        except Exception as e:
            print(f"!!! FALLO EN SOLICITUD DE ELIMINACIÓN: {e}")
            if conn:
                conn.rollback() # Si algo falla, deshace todos los cambios
            return False
        finally:
            if conn:
                conn.autocommit = True # Restaura el modo autocommit


# --- REPOSITORIO DE SOLICITUDES DE MODIFICACIÓN ---


# En app/infrastructure/persistence/sqlserver_repository.py

class SqlServerSolicitudRepository:
    
    def get_pending_requests(self):
        """Obtiene todas las solicitudes de modificación pendientes."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
            SELECT 
                sm.id_solicitud,
                sm.id_personal,
                sm.id_usuario_solicitante,
                sm.campo_modificado,
                sm.valor_anterior AS motivo,
                sm.valor_nuevo AS ruta_archivo_nuevo,
                sm.estado,
                sm.fecha_solicitud,
                -- Datos del personal afectado (dueño del legajo)
                p.nombres + ' ' + p.apellidos AS nombre_personal,
                p.dni,
                -- Datos del usuario que solicita el cambio
                ISNULL(u.username, 'N/A') AS username,
                ISNULL(p_solicitante.nombres, '') AS nombres,
                ISNULL(p_solicitante.apellidos, '') AS apellidos,
                -- Nombre del tipo de documento
                ISNULL(td.nombre_tipo, 'Documento') AS nombre_doc_original
            FROM solicitudes_modificacion sm
            LEFT JOIN personal p ON sm.id_personal = p.id_personal
            LEFT JOIN usuarios u ON sm.id_usuario_solicitante = u.id_usuario
            LEFT JOIN personal p_solicitante ON u.id_personal = p_solicitante.id_personal
            LEFT JOIN documentos d ON TRY_CAST(sm.campo_modificado AS INT) = d.id_documento
            LEFT JOIN tipo_documento td ON d.id_tipo = td.id_tipo
            WHERE sm.estado = 'Pendiente'
            ORDER BY sm.fecha_solicitud DESC
            """
            cursor.execute(query)
            return [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error al obtener solicitudes pendientes: {e}")
            return []
        finally:
            cursor.close()
    
    def get_by_id(self, solicitud_id):
        """Obtiene una solicitud por su ID."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
            SELECT 
                sm.id_solicitud,
                sm.id_personal,
                sm.id_usuario_solicitante,
                sm.campo_modificado,
                sm.valor_anterior,
                sm.valor_nuevo AS ruta_nuevo_archivo,
                sm.estado,
                sm.fecha_solicitud
            FROM solicitudes_modificacion sm
            WHERE sm.id_solicitud = ?
            """
            cursor.execute(query, solicitud_id)
            row = cursor.fetchone()
            return _row_to_dict(cursor, row) if row else None
        finally:
            cursor.close()
    
    def process_request(self, solicitud_id, action):
        """Procesa una solicitud (aprobar/rechazar)."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            nuevo_estado = 'Aprobada' if action == 'aprobar' else 'Rechazada'
            cursor.execute(
                "UPDATE solicitudes_modificacion SET estado = ? WHERE id_solicitud = ?",
                nuevo_estado, solicitud_id
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            logger.error(f"Error al procesar solicitud {solicitud_id}: {e}")
            return False
        finally:
            cursor.close()
    
    def obtener_id_personal_por_documento(self, id_documento):
        """Helper para obtener el id_personal dueño de un documento."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_personal FROM documentos WHERE id_documento = ?", id_documento)
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            cursor.close()
    
    def crear_solicitud_modificacion(self, data):
        """
        Crea una solicitud de modificación en la tabla solicitudes_modificacion.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # Si no viene id_personal en 'data', intentamos inferirlo
            # deberíamos obtenerlo del documento, pero asumiremos que viene en 'data'.
            if not data.get('id_personal'):
                 # Lógica opcional: obtener id_personal desde el documento si falta
                 cursor.execute("SELECT id_personal FROM documentos WHERE id_documento = ?", 
                                int(data['campo_modificado'].split(': ')[1]))
                 row = cursor.fetchone()
                 if row:
                     data['id_personal'] = row[0]
            
            # Llamada al Stored Procedure definido en tu SQL
            cursor.execute("{CALL sp_solicitar_modificacion_personal(?, ?, ?, ?, ?)}",
                           data['id_personal'],
                           data['id_usuario_solicitante'],
                           data['campo_modificado'], # VARCHAR(100)
                           data['valor_anterior'],   # VARCHAR(500) - Motivo
                           data['valor_nuevo']       # VARCHAR(500) - Ruta Archivo
                           )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
