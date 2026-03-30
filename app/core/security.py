# app/core/security.py
# Módulo de seguridad mejorado con bloqueo de cuenta e IDOR protection

from datetime import datetime, timedelta
from math import ceil
from werkzeug.security import generate_password_hash as werkzeug_generate_hash
from werkzeug.security import check_password_hash as werkzeug_check_hash
from app.database.connector import get_db_write, get_db_read
import logging
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

logger = logging.getLogger(__name__)

# Define el método de hashing scrypt con parámetros de coste recomendados.
SCRYPT_METHOD = "scrypt:32768:8:1"

# Define una función para generar un hash de una contraseña.
def generate_password_hash(password):
    return werkzeug_generate_hash(password, method=SCRYPT_METHOD)

# Define una función para verificar si una contraseña coincide con un hash existente.
def check_password_hash(pwhash, password):
    return werkzeug_check_hash(pwhash, password)


class AccountLockoutManager:
    """
    Gestiona el bloqueo de cuentas tras múltiples intentos fallidos.
    
    Política:
    - 5 intentos fallidos: bloqueo de 15 minutos
    - 10 intentos fallidos: bloqueo de 1 hora
    - 20+ intentos fallidos: bloqueo de 24 horas + alerta admin
    """
    
    MAX_ATTEMPTS_15MIN = 5
    MAX_ATTEMPTS_1HOUR = 10
    MAX_ATTEMPTS_24HOUR = 20
    
    LOCKOUT_15MIN = timedelta(minutes=15)
    LOCKOUT_1HOUR = timedelta(hours=1)
    LOCKOUT_24HOUR = timedelta(hours=24)
    
    @staticmethod
    def increment_failed_attempts(username: str) -> bool:
        """
        Incrementa contador de intentos fallidos para un usuario.
        
        Retorna:
            True si la cuenta fue bloqueada
            False si aún hay intentos disponibles
        """
        try:
            conn = get_db_write()
            cursor = conn.cursor()
            
            # Obtener intentos actuales
            query = """
            SELECT intentos_fallidos, ultima_intento_fallido, bloqueado_hasta
            FROM usuarios
            WHERE username = ?
            """
            cursor.execute(query, username)
            row = cursor.fetchone()
            
            if not row:
                return False
            
            intentos_actuales = row[0] if row[0] else 0
            bloqueado_hasta = row[2]
            
            # Si está bloqueado, verificar si expira el bloqueo
            if bloqueado_hasta:
                if datetime.utcnow() < bloqueado_hasta:
                    # Aún está bloqueado
                    return True
                else:
                    # Expiró bloqueo, reiniciar contador
                    intentos_actuales = 0
            
            # Incrementar intento fallido
            nuevo_intento = intentos_actuales + 1
            nuevo_bloqueado_hasta = None
            
            # Determinar si bloquear cuenta
            if nuevo_intento >= AccountLockoutManager.MAX_ATTEMPTS_24HOUR:
                nuevo_bloqueado_hasta = datetime.utcnow() + AccountLockoutManager.LOCKOUT_24HOUR
                logger.warning(f"SEGURIDAD: Cuenta {username} bloqueada 24h tras {nuevo_intento} intentos fallidos")
                AccountLockoutManager._alert_admin(username, nuevo_intento)
                
            elif nuevo_intento >= AccountLockoutManager.MAX_ATTEMPTS_1HOUR:
                nuevo_bloqueado_hasta = datetime.utcnow() + AccountLockoutManager.LOCKOUT_1HOUR
                logger.warning(f"SEGURIDAD: Cuenta {username} bloqueada 1h tras {nuevo_intento} intentos fallidos")
                
            elif nuevo_intento >= AccountLockoutManager.MAX_ATTEMPTS_15MIN:
                nuevo_bloqueado_hasta = datetime.utcnow() + AccountLockoutManager.LOCKOUT_15MIN
                logger.warning(f"SEGURIDAD: Cuenta {username} bloqueada 15min tras {nuevo_intento} intentos fallidos")
            
            # Actualizar BD
            query = """
            UPDATE usuarios
            SET intentos_fallidos = ?,
                ultima_intento_fallido = GETUTCDATE(),
                bloqueado_hasta = ?
            WHERE username = ?
            """
            cursor.execute(query, nuevo_intento, nuevo_bloqueado_hasta, username)
            conn.commit()
            
            # Retorna True si fue bloqueado
            return nuevo_bloqueado_hasta is not None
            
        except Exception as e:
            logger.error(f"Error en increment_failed_attempts: {str(e)}")
            return False
    
    @staticmethod
    def reset_failed_attempts(username: str) -> bool:
        """
        Reinicia contador de intentos fallidos tras login exitoso.
        """
        try:
            conn = get_db_write()
            cursor = conn.cursor()
            
            query = """
            UPDATE usuarios
            SET intentos_fallidos = 0,
                bloqueado_hasta = NULL,
                ultimo_login = GETUTCDATE()
            WHERE username = ?
            """
            cursor.execute(query, username)
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error en reset_failed_attempts: {str(e)}")
            return False
    
    @staticmethod
    def is_account_locked(username: str) -> tuple:
        """
        Verifica si una cuenta está bloqueada.
        
        Retorna:
            (locked: bool, tiempo_restante_minutos: int)
        """
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            
            query = """
            SELECT bloqueado_hasta
            FROM usuarios
            WHERE username = ?
            """
            cursor.execute(query, username)
            row = cursor.fetchone()
            
            if not row or not row[0]:
                return False, 0
            
            bloqueado_hasta = row[0]
            ahora = datetime.utcnow()
            
            if ahora < bloqueado_hasta:
                # Calcular minutos restantes
                tiempo_restante = (bloqueado_hasta - ahora).total_seconds() / 60
                return True, int(ceil(tiempo_restante))
            
            return False, 0
            
        except Exception as e:
            logger.error(f"Error en is_account_locked: {str(e)}")
            return False, 0
    
    @staticmethod
    def _alert_admin(username: str, intentos: int):
        """
        Envía alerta a administrador por múltiples intentos fallidos.
        """
        try:
            from app.application.services.email_service import send_email
            
            subject = f"⚠️ ALERTA SEGURIDAD: Múltiples intentos fallidos de login - {username}"
            body = f"""
            ALERTA DE SEGURIDAD
            
            Usuario: {username}
            Intentos fallidos: {intentos}
            Timestamp: {datetime.utcnow().isoformat()}
            Acción: Cuenta bloqueada por 24 horas
            
            Por favor revisa el archivo de auditoría para más detalles.
            
            Sistema de Seguridad - Legajo Digital HMPP
            """
            
            # Obtener email del admin
            conn = get_db_read()
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM usuarios WHERE id_rol = (SELECT id_rol FROM roles WHERE nombre_rol = 'Sistemas') LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                send_email(row[0], subject, body)
                
        except Exception as e:
            logger.error(f"Error al enviar alerta admin: {str(e)}")
    
    @staticmethod
    def get_account_status(username: str) -> dict:
        """
        Obtiene estado completo de seguridad de una cuenta.
        """
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            
            query = """
            SELECT 
                intentos_fallidos,
                bloqueado_hasta,
                ultima_intento_fallido,
                activo
            FROM usuarios
            WHERE username = ?
            """
            cursor.execute(query, username)
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                'intentos_fallidos': row[0] or 0,
                'bloqueado_hasta': row[1],
                'ultima_intento_fallido': row[2],
                'activo': row[3]
            }
            
        except Exception as e:
            logger.error(f"Error en get_account_status: {str(e)}")
            return None


class IDORProtection:
    """
    Protección contra Insecure Direct Object Reference (IDOR).
    Verifica que un usuario pueda acceder a un recurso específico.
    """
    
    @staticmethod
    def can_access_personal(user_id: int, personal_id: int, user_role: str) -> bool:
        """
        Verifica si un usuario puede acceder a un registro de personal específico.
        
        Reglas:
        - 'Personal' solo puede ver su propio legajo
        - 'RRHH', 'AdministradorLegajos' pueden ver todos
        - 'Sistemas' acceso total
        - Otros no pueden acceder
        """
        if user_role == 'Sistemas' or user_role == 'AdministradorLegajos':
            return True
        
        if user_role == 'RRHH':
            # RRHH puede ver personal de su departamento
            return IDORProtection._check_rrhh_department(user_id, personal_id)
        
        if user_role == 'Personal':
            # Personal solo ve su propio legajo
            return IDORProtection._get_personal_id_for_user(user_id) == personal_id
        
        return False
    
    @staticmethod
    def _get_personal_id_for_user(user_id: int) -> int:
        """Obtiene el personal_id asociado a un usuario empleado."""
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            
            # Intenta obtener el personal_id de diferentes formas
            # Primero intenta con id_usuario
            query = """
            SELECT id_personal FROM personal
            WHERE id_usuario = ?
            """
            cursor.execute(query, user_id)
            row = cursor.fetchone()
            
            # Si no encuentra por id_usuario, intenta con id_usuario (otro campo)
            if not row:
                query = """
                SELECT id_personal FROM personal
                WHERE id_personal = ?
                """
                cursor.execute(query, user_id)
                row = cursor.fetchone()
            
            return row[0] if row else None
            
        except Exception as e:
            logger.error(f"Error en _get_personal_id_for_user: {str(e)}")
            # En caso de error, retornar None (deniega acceso por seguridad)
            return None
    
    @staticmethod
    def _check_rrhh_department(user_id: int, personal_id: int) -> bool:
        """Verifica si el personal pertenece al departamento del RRHH."""
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            
            query = """
            SELECT COUNT(*)
            FROM personal p
            WHERE p.id = ?
            AND p.id_unidad_administrativa = (
                SELECT id_unidad_administrativa 
                FROM personal 
                WHERE id_usuario = ?
            )
            """
            cursor.execute(query, personal_id, user_id)
            result = cursor.fetchone()[0]
            
            return result > 0
            
        except Exception as e:
            logger.error(f"Error en _check_rrhh_department: {str(e)}")
            return False 
        
def role_required(*roles):
        """
        Decorador para restringir el acceso a rutas según el rol del usuario.
        Permite pasar múltiples roles permitidos.
        Ejemplo: @role_required('Sistemas', 'Personal')
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # 1. Verificar si está logueado
                if not current_user.is_authenticated:
                    return redirect(url_for('auth.login'))
                
                # 2. Verificar si su rol está en la lista de permitidos
                if current_user.rol not in roles:
                    flash('No tienes permisos necesarios para acceder a esta página.', 'danger')
                    # Si no tiene permiso, lo regresamos a una página segura (ej. index)
                    return redirect(url_for('index'))
                    
                # 3. Si todo está bien, lo dejamos pasar
                return f(*args, **kwargs)
            return decorated_function
        return decorator