# RUTA: app/domain/models/usuario.py

from flask_login import UserMixin
from app.core.security import check_password_hash, generate_password_hash

# 🚨 IMPORTANTE: Define aquí los IDs de rol de tu BD para claridad
ROL_ID_SISTEMAS = 3 # ID para el Encargado de Sistemas/Admin Técnico
ROL_ID_LEGAJO = 2   # ID para el Encargado de Legajos/Usuario Clave

class Usuario(UserMixin):
    """
    Representa la entidad de un usuario, incluyendo datos de sesión y perfil.
    """
    def __init__(self, id_usuario, username, id_rol, password_hash=None, activo=True, 
                 email=None, nombre_rol=None, two_factor_code=None, two_factor_expiry=None,
                 nombre_completo=None, ultimo_login=None, id_personal=None, foto_perfil=None,
                 **kwargs):
        
        self.id = id_usuario
        self.id_usuario = id_usuario  # También guardar como id_usuario para compatibilidad
        self.username = username
        self.id_rol = id_rol           # Campo crucial para el control de acceso
        self.password_hash = password_hash
        self.activo = activo
        self.email = email
        self.nombre_rol = nombre_rol
        self.rol = nombre_rol
        self.id_personal = id_personal  # Asociación con personal
        self.foto_perfil = foto_perfil  # Ruta de la foto de perfil
        
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
    
    # --- MÉTODOS DE CONTROL DE ACCESO POR ROL (RBAC) ---

    def is_system_admin(self):
        """Retorna True si el usuario tiene el rol de Administrador de Sistemas."""
        # Compara el ID de rol con el ID definido para Sistemas
        return self.id_rol == ROL_ID_SISTEMAS
        
    def is_legajo_manager(self):
        """Retorna True si el usuario es el Encargado de Legajos (usuario clave)."""
        # Compara el ID de rol con el ID definido para Legajos
        return self.id_rol == ROL_ID_LEGAJO
        
    # --- FIN DE MÉTODOS DE CONTROL DE ACCESO ---

    def check_2fa_code(self, code):
        """Verifica el código de doble factor de autenticación."""
        if self.two_factor_code:
            return check_password_hash(self.two_factor_code, code)
        return False

    @staticmethod
    def from_dict(data):
        """Crea una instancia de Usuario a partir de un diccionario de datos (ej. desde la BD)."""
        if data:
            return Usuario(**data)
        return None

# Fin de app/domain/models/usuario.py