# RUTA: app/domain/models/usuario.py

from flask_login import UserMixin
from app.core.security import check_password_hash, generate_password_hash

# 🚨 IDs de rol sincronizados con la Base de Datos (image_72d2c8.png)
ROL_ID_SISTEMAS = 1  # Sistemas
ROL_ID_RRHH = 2      # RRHH Consulta
ROL_ID_LEGAJO = 3    # Administrador de Legajos
ROL_ID_AUDITOR = 4   # Auditor
ROL_ID_PERSONAL = 5  # Rol para acceso de empleados

class Usuario(UserMixin):
    """
    Representa la entidad de un usuario, incluyendo datos de sesión y perfil.
    Cumple con la Ley 29733 de Protección de Datos Personales.
    """
    def __init__(self, id_usuario, username, id_rol, password_hash=None, activo=True, 
                 email=None, nombre_rol=None, two_factor_code=None, two_factor_expiry=None,
                 nombre_completo=None, ultimo_login=None, id_personal=None, foto_perfil=None,
                 **kwargs):
        
        self.id = id_usuario
        self.id_usuario = id_usuario  # Compatibilidad con consultas de infraestructura
        self.username = username
        self.id_rol = id_rol           # Control de acceso por ID
        self.password_hash = password_hash
        self.activo = activo
        self.email = email
        self.nombre_rol = nombre_rol
        self.rol = nombre_rol          # Alias para decoradores @role_required
        self.id_personal = id_personal  # Vínculo con tabla personal
        self.foto_perfil = foto_perfil
        
        # Atributos de seguridad y sesión
        self.two_factor_code = two_factor_code
        self.two_factor_expiry = two_factor_expiry
        self.nombre_completo = nombre_completo
        self.fecha_ultimo_login = ultimo_login

    def set_password(self, password):
        """Genera y asigna el hash de una nueva contraseña."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica la contraseña contra el hash almacenado."""
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False
    
    # --- MÉTODOS DE CONTROL DE ACCESO (RBAC) ---

    def is_system_admin(self):
        """Retorna True si es Administrador de Sistemas (ID 1)."""
        return self.id_rol == ROL_ID_SISTEMAS
        
    def is_legajo_manager(self):
        """Retorna True si es Administrador de Legajos (ID 3)."""
        return self.id_rol == ROL_ID_LEGAJO

    def is_personal(self):
        """Retorna True si es un usuario con rol Personal (ID 5)."""
        return self.id_rol == ROL_ID_PERSONAL
        
    # --- SEGURIDAD ---

    def check_2fa_code(self, code):
        """Verifica el código 2FA generado en terminal."""
        if self.two_factor_code:
            return check_password_hash(self.two_factor_code, code)
        return False

    @staticmethod
    def from_dict(data):
        """Crea una instancia de Usuario a partir de un diccionario de la BD."""
        if data:
            return Usuario(**data)
        return None