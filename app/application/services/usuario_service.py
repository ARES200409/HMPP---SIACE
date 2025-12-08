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
    def __init__(self, usuario_repository, email_service):
        self._usuario_repo = usuario_repository
        self._email_service = email_service

    def attempt_login(self, username, password):
        """
        Verifica las credenciales. Si son válidas, envía un código 2FA por correo
        en producción, o lo imprime en consola para desarrollo.
        
        Retorna:
            - user_id (int): Si el login fue exitoso
            - None: Si las credenciales son inválidas
            - ('email_error', str): Tupla si falla el envío de email
        """
        user = self._usuario_repo.find_by_username_with_email(username)

        if user and user.activo and user.check_password(password):
            code = ''.join(random.choices(string.digits, k=6))
            hashed_code = generate_password_hash(code)
            expiry_date = datetime.utcnow() + timedelta(minutes=10)

            self._usuario_repo.set_2fa_code(user.id, hashed_code, expiry_date)

            # --- Lógica Condicional para 2FA ---
            if not current_app.config.get('DEBUG'):
                # Modo Producción: Enviar correo electrónico.
                try:
                    self._email_service.send_2fa_code(user.email, user.nombre_completo or user.username, code)
                    logger.info(f"Código 2FA enviado por correo a {user.email}")
                except Exception as e:
                    logger.error(f"Fallo al enviar correo 2FA a {user.email}: {e}")
                    # Retornar tupla indicando error de email
                    return ('email_error', f"No se pudo enviar el código de verificación a {user.email}. Por favor, verifica tu correo electrónico o contacta al administrador.")
            else:
                # Modo Desarrollo: Imprimir en consola.
                print("---------------------------------------------------------")
                print(f"--- CÓDIGO 2FA (PARA DESARROLLO): {code} ---")
                print("---------------------------------------------------------")
            
            return user.id
        
        return None

    def verify_2fa_code(self, user_id, code):
        """Verifica el código 2FA proporcionado por el usuario."""
        user = self._usuario_repo.find_by_id(user_id)
        
        if not user or not user.two_factor_code or user.two_factor_expiry < datetime.utcnow():
            return None

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
        Crea un nuevo usuario en el sistema con validaciones.
        
        Args:
            user_data: Diccionario con los datos del usuario (username, email, password, id_rol)
        
        Returns:
            Tupla (mensaje, tipo_flash)
        """
        try:
            # Extraer datos del formulario
            username = user_data.get('username', '').strip()
            email = user_data.get('email', '').strip()
            password = user_data.get('password', '').strip()
            id_rol = user_data.get('id_rol')
            
            # Validaciones básicas - email es opcional para creación automática
            if not username or not password or not id_rol:
                return "Usuario, contraseña y rol son obligatorios", "warning"
            
            # Si no hay email, generar uno por defecto basado en el username (DNI)
            if not email:
                email = f"{username}@noespecificado.local"
            
            if len(username) < 3:
                return "El nombre de usuario debe tener al menos 3 caracteres", "warning"
            
            if len(password) < 8:
                return "La contraseña debe tener al menos 8 caracteres", "warning"
            
            # Verificar que el username no exista
            existing_user = self._usuario_repo.find_by_username(username)
            if existing_user:
                return f"El nombre de usuario '{username}' ya existe en el sistema", "warning"
            
            # Verificar que el email no exista (si es un email real, no el placeholder)
            if not email.endswith('@noespecificado.local'):
                existing_email = self._usuario_repo.find_by_email(email)
                if existing_email:
                    return f"El correo electrónico '{email}' ya está registrado", "warning"
            
            # Generar hash de la contraseña
            password_hash = generate_password_hash(password)
            
            # Obtener id_personal si está disponible
            id_personal = user_data.get('id_personal')
            
            # Crear el usuario en la base de datos
            new_user = self._usuario_repo.create_user(
                username=username,
                email=email,
                password_hash=password_hash,
                id_rol=id_rol,
                activo=True,
                id_personal=id_personal,
                fecha_creacion=datetime.utcnow()
            )
            
            logger.info(f"Nuevo usuario creado: {username} (ID: {new_user.id})")
            
            # Opcional: Enviar email de bienvenida
            try:
                self._email_service.send_user_welcome(email, username)
                logger.info(f"Email de bienvenida enviado a {email}")
            except Exception as e:
                logger.warning(f"No se pudo enviar email de bienvenida a {email}: {e}")
            
            return f"Usuario '{username}' creado exitosamente", "success"
            
        except Exception as e:
            logger.error(f"Error al crear usuario: {str(e)}")
            return f"Error al crear usuario: {str(e)}", "danger"