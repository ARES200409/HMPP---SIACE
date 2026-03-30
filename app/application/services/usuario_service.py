# RUTA: app/application/services/usuario_service.py

import random
import string
from datetime import datetime, timedelta
from flask import current_app
from app.core.security import generate_password_hash
import logging 

# Configura un logger para este módulo
logger = logging.getLogger(__name__)

class UsuarioService:
    def __init__(self, usuario_repository, personal_repo, email_service):
        self._usuario_repo = usuario_repository
        self._email_service = email_service
        self._personal_repo = personal_repo

    def attempt_login(self, username, password):
        """
        Valida credenciales y genera código 2FA.
        Retorna: (user_id, raw_code) si es exitoso, o None.
        """
        user = self._usuario_repo.find_by_username_with_email(username)

        if user and user.activo and user.check_password(password):
            # 1. Generar código real de 6 dígitos
            code = ''.join(random.choices(string.digits, k=6))
            
            # 2. Encriptar para la Base de Datos (Seguridad)
            hashed_code = generate_password_hash(code)
            expiry_date = datetime.utcnow() + timedelta(minutes=10)

            # 3. Guardar el HASH en SQL Server
            self._usuario_repo.set_2fa_code(user.id, hashed_code, expiry_date)

            # 4. Modo Desarrollo: Imprimir en consola para VS Code
            if current_app.config.get('DEBUG'):
                print("---------------------------------------------------------")
                print(f"--- CÓDIGO 2FA (PARA DESARROLLO): {code} ---")
                print("---------------------------------------------------------")
            
            # 🚀 RETORNO CLAVE: Enviamos el ID y el código real (limpio)
            return (user.id, code) 
        
        return None

    def verify_2fa_code(self, user_id, code):
        """Verifica el código 2FA proporcionado por el usuario."""
        user = self._usuario_repo.find_by_id(user_id)
        
        if not user or not user.two_factor_code or user.two_factor_expiry < datetime.utcnow():
            return None

        # Compara el código ingresado con el HASH de la BD
        if user.check_2fa_code(code):
            self._usuario_repo.clear_2fa_code(user.id)
            return user
        
        return None

    def update_last_login(self, user_id):
        """Orquesta la actualización de la fecha del último login para un usuario."""
        self._usuario_repo.update_last_login(user_id)

    def get_user_by_id(self, user_id):
        """Obtiene un usuario por su ID."""
        return self._usuario_repo.find_by_id(user_id)

    def get_user_by_id_for_editing(self, user_id):
        """Obtiene un usuario por su ID para edición."""
        return self._usuario_repo.find_by_id(user_id)

    # ====================================================================
    # >>> MÉTODO AGREGADO: get_all_users_with_roles <<<
    #    Este método corrige el 'AttributeError'.
    # ====================================================================
    def get_all_users_with_roles(self):
        """
        Obtiene todos los usuarios y los mapea con su información de rol,
        llamando a la capa de repositorio.
        """
        try:
            # Debe asegurarse de que su UsuarioRepository (self._usuario_repo)
            # tenga implementado el método 'find_all_users_with_roles()'.
            usuarios_con_roles = self._usuario_repo.find_all_users_with_roles()
            logger.info("Usuarios con roles obtenidos correctamente para la gestión.")
            return usuarios_con_roles
        except Exception as e:
            logger.error(f"Error al obtener todos los usuarios con roles desde el repositorio: {e}")
            # Devolvemos una lista vacía para evitar un crash si la BD falla
            return []

    def update_user_role(self, user_id, new_role_id):
        """Actualiza el rol de un usuario."""
        try:
            self._usuario_repo.update_user_role(user_id, new_role_id)
            logger.info(f"Rol del usuario {user_id} actualizado a {new_role_id}")
            return "El rol del usuario ha sido actualizado correctamente.", "success"
        except Exception as e:
            logger.error(f"Error al actualizar el rol del usuario {user_id}: {e}")
            return f"Error al actualizar el rol: {e}", "danger"

    def update_user_password(self, user_id, new_password):
        """Actualiza la contraseña de un usuario."""
        try:
            # Generar hash de la contraseña
            password_hash = generate_password_hash(new_password)
            self._usuario_repo.update_user_password(user_id, password_hash)
            logger.info(f"Contraseña del usuario {user_id} actualizada")
            return "La contraseña del usuario ha sido actualizada correctamente.", "success"
        except Exception as e:
            logger.error(f"Error al actualizar la contraseña del usuario {user_id}: {e}")
            return f"Error al actualizar la contraseña: {e}", "danger"

    def reset_user_password(self, user_id):
        """Resetea la contraseña de un usuario a una contraseña temporal predeterminada."""
        try:
            # Contraseña temporal por defecto
            temporary_password = "Temporal123!"
            password_hash = generate_password_hash(temporary_password)
            self._usuario_repo.update_user_password(user_id, password_hash)
            logger.info(f"Contraseña del usuario {user_id} reseteada a temporal")
            return "La contraseña ha sido reseteada correctamente.", "success"
        except Exception as e:
            logger.error(f"Error al resetear la contraseña del usuario {user_id}: {e}")
            return f"Error al resetear la contraseña: {e}", "danger"

    def update_password(self, user_id, new_password):
        """Alias para update_user_password - Actualiza la contraseña de un usuario."""
        return self.update_user_password(user_id, new_password)

    def update_username(self, user_id, new_username):
        """Actualiza el nombre de usuario."""
        try:
            self._usuario_repo.update_username(user_id, new_username)
            logger.info(f"Nombre de usuario del usuario {user_id} actualizado a {new_username}")
            return "El nombre de usuario ha sido actualizado correctamente.", "success"
        except ValueError as e:
            # Error de validación (duplicado, etc.)
            logger.warning(f"Validación al actualizar usuario {user_id}: {e}")
            return str(e), "warning"
        except Exception as e:
            logger.error(f"Error al actualizar el nombre de usuario {user_id}: {e}")
            return "Error al actualizar el nombre de usuario. Por favor intenta de nuevo.", "danger"

    def update_email(self, user_id, new_email):
        """Actualiza el correo electrónico de un usuario."""
        try:
            self._usuario_repo.update_email(user_id, new_email)
            logger.info(f"Correo electrónico del usuario {user_id} actualizado a {new_email}")
            return "El correo electrónico ha sido actualizado correctamente.", "success"
        except ValueError as e:
            # Error de validación (duplicado, etc.)
            logger.warning(f"Validación al actualizar correo del usuario {user_id}: {e}")
            return str(e), "warning"
        except Exception as e:
            logger.error(f"Error al actualizar el correo electrónico del usuario {user_id}: {e}")
            return "Error al actualizar el correo electrónico. Por favor intenta de nuevo.", "danger"

    def update_foto_perfil(self, user_id, foto_filename):
        """Actualiza la foto de perfil de un usuario."""
        try:
            self._usuario_repo.update_foto_perfil(user_id, foto_filename)
            logger.info(f"Foto de perfil del usuario {user_id} actualizada a {foto_filename}")
            return "La foto de perfil ha sido actualizada correctamente.", "success"
        except Exception as e:
            logger.error(f"Error al actualizar la foto de perfil del usuario {user_id}: {e}")
            return "Error al actualizar la foto de perfil. Por favor intenta de nuevo.", "danger"

    def create_user(self, user_data):
        """
        Crea un nuevo usuario y su ficha de personal básica automáticamente.
        Garantiza que el legajo sea 'editable' al incluir campos obligatorios desde el inicio.
        """
        try:
            # 1. Extraer y limpiar datos del formulario
            username = user_data.get('username', '').strip().lower()
            nombre_completo = user_data.get('nombre_completo', '').strip()
            email_form = user_data.get('email', '').strip()
            password = user_data.get('password', '').strip()
            id_rol = user_data.get('id_rol')
            
            # 2. Validaciones básicas obligatorias
            if not username or not password or not id_rol:
                return "Usuario, contraseña y rol son obligatorios", "warning"
            
            if not nombre_completo:
                return "El nombre completo es requerido para generar el legajo automático", "warning"

            # 3. Verificaciones de duplicidad en la tabla de Usuarios
            if self._usuario_repo.find_by_username(username):
                return f"El nombre de usuario '{username}' ya existe", "warning"
            
            # 4. LÓGICA DE VINCULACIÓN AUTOMÁTICA (Opción B)
            id_personal = user_data.get('id_personal')

            if not id_personal:
                # --- PREPARACIÓN DE DATOS PARA EVITAR BLOQUEOS DE EDICIÓN ---
                
                # Dividimos el nombre para la estructura Nombres/Apellidos
                partes = nombre_completo.split(' ', 1)
                nom = partes[0]
                ape = partes[1] if len(partes) > 1 else "Apellido por Completar"

                # Generamos un email único para evitar el error UNIQUE (Mens 2627)
                email_personal = email_form if email_form else f"{username}@legajo.hmpp.gob.pe"

                # Valores por defecto para campos obligatorios (NOT NULL)
                fecha_temp = datetime.now().strftime('%Y-%m-%d') # Fecha de hoy como placeholder
                nacionalidad_temp = "Peruana"

                try:
                    # CREACIÓN DEL LEGAJO COMPLETO: Ahora incluimos Nacimiento y Nacionalidad
                    nuevo_personal = self._personal_repo.create_personal_basico(
                        dni=username,           # Usamos el username como DNI
                        nombres=nom,
                        apellidos=ape,
                        sexo='M',               # Valor por defecto obligatorio
                        id_unidad=1,            # ID 1 = Sistemas (Oficina inicial)
                        email=email_personal,    # Email único garantizado
                        fecha_nacimiento=fecha_temp, # <--- Agregado para desbloquear edición
                        nacionalidad=nacionalidad_temp, # <--- Agregado para desbloquear edición
                        activo=1                # Activo por defecto
                    )
                    id_personal = nuevo_personal.id_personal
                    logger.info(f"Legajo editable #{id_personal} creado para {username}")
                    
                except Exception as e:
                    logger.error(f"Error al crear legajo automático: {e}")
                    return f"Error al generar la ficha de personal vinculada: {str(e)}", "danger"

            # 5. Cifrado de contraseña y creación del usuario final
            password_hash = generate_password_hash(password)
            
            new_user = self._usuario_repo.create_user(
                username=username,
                nombre_completo=nombre_completo,
                email=email_personal if not email_form else email_form,
                password_hash=password_hash,
                id_rol=id_rol,
                activo=True,
                id_personal=id_personal, # Vínculo garantizado en la BaseDatosHMPP
                fecha_creacion=datetime.utcnow()
            )
            
            logger.info(f"Usuario {username} vinculado exitosamente al personal {id_personal}")
            
            # 6. Envío opcional de bienvenida
            try:
                self._email_service.send_user_welcome(new_user.email, username)
            except Exception as e:
                logger.warning(f"No se pudo enviar email de bienvenida: {e}")
            
            return f"Usuario '{username}' y su legajo técnico fueron creados con éxito", "success"
                
        except Exception as e:
            logger.error(f"Error crítico en el servicio: {str(e)}")
            return f"Error interno: {str(e)}", "danger"
        

    def get_current_2fa(self, user_id):
        """
        ¡CUIDADO!: Este método devuelve el código tal como está en la BD (encriptado).
        Solo úsalo si necesitas el HASH. Para el correo, usa el retorno de attempt_login.
        """
        try:
            user = self._usuario_repo.find_by_id(user_id)
            if user and user.two_factor_code:
                return user.two_factor_code
            return None
        except Exception as e:
            logger.error(f"Error al recuperar código 2FA: {e}")
            return None

    # --- Otros métodos de gestión (Sin cambios) ---
    def get_user_by_id(self, user_id):
        return self._usuario_repo.find_by_id(user_id)

    def update_last_login(self, user_id):
        self._usuario_repo.update_last_login(user_id)

    def get_all_users_with_roles(self):
        try:
            return self._usuario_repo.find_all_users_with_roles()
        except Exception as e:
            logger.error(f"Error al obtener usuarios con roles: {e}")
            return []
    # Agrega esto dentro de la clase UsuarioService
    def reset_user_password(self, user_id):
        """
        Resetea la contraseña del usuario a su mismo nombre de usuario (DNI).
        """
        try:
            # 1. Buscar al usuario
            user = self.get_user_by_id(user_id)
            if not user:
                return "Usuario no encontrado.", "warning"

            # 2. Nueva contraseña = username (DNI)
            nueva_pass = user.username
            password_hash = generate_password_hash(nueva_pass)

            # 3. Actualizar en BD (Usamos la conexión que ya tiene el servicio)
            # NOTA: Si tu servicio usa un repositorio, úsalo. Si usa SQL directo:
            conn = get_db_read() # O la función de conexión que use tu servicio arriba
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id_usuario = ?", (password_hash, user_id))
            conn.commit()
            conn.close()

            return f"Contraseña restablecida correctamente al DNI: {nueva_pass}", "success"

        except Exception as e:
            print(f"Error reset password service: {e}")
            return "Error interno al procesar la solicitud.", "danger"