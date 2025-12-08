# RUTA: app/__init__.py

import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import timedelta
from flask import Flask, redirect, url_for, current_app, render_template, flash
from flask_login import LoginManager, current_user, login_required, logout_user
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from app.presentation.routes.personal_routes import personal_bp


# Seguridad: Importar las nuevas extensiones
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Importación de Servicios y Repositorios (esto está bien aquí)
from .config import Config
from .database.connector import init_app_db
from .domain.models.usuario import Usuario
from .application.services.email_service import EmailService
from .application.services.usuario_service import UsuarioService
from .application.services.legajo_service import LegajoService
from .application.services.audit_service import AuditService
from .application.services.solicitud_service import SolicitudService 
from .application.services.backup_service import BackupService 
from .application.services.monitoring_service import MonitoringService 
from .infrastructure.persistence.sqlserver_repository import (
    SqlServerUsuarioRepository, 
    SqlServerPersonalRepository, 
    SqlServerAuditoriaRepository,
    SqlServerBackupRepository, 
    SqlServerSolicitudRepository 
)

# Inicialización de extensiones de Flask (sin la app)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, inicie sesión para acceder a esta página."
login_manager.login_message_category = "info"
csrf = CSRFProtect()
mail = Mail()
# Seguridad: Crear instancias de Limiter y Talisman fuera de la factoría
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"] # Límites por defecto para todas las rutas
)
talisman = Talisman()

@login_manager.user_loader
def load_user(user_id):
    repo = current_app.config.get('USUARIO_REPOSITORY')
    if repo:
        return repo.find_by_id(int(user_id)) 
    return None

def configure_logging(app):
    """Configura el sistema de logging para la aplicación."""
    if not app.debug:
        # Usar el directorio de logs configurado en Config (en %LOCALAPPDATA%)
        log_dir = app.config.get('LOG_DIR', 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 'app.log')
        
        # Usar delay=True para evitar problemas en Windows con archivo bloqueado
        # Aumentar maxBytes a 50MB para reducir rotaciones frecuentes
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=50*1024*1024,  # 50 MB
            backupCount=5,
            delay=True  # No crear el archivo hasta el primer log
        )
        
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Aplicación iniciada')

def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder='presentation/templates',
        static_folder='presentation/static'
    )
    app.config.from_object(Config)

    # Configurar Logging
    configure_logging(app)

    # Inicializar todas las extensiones con la app
    init_app_db(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    # Seguridad: Inicializar Limiter y Talisman con la app
    limiter.init_app(app)
    
    # Configuración de la Política de Seguridad de Contenido (CSP)
    # Permite CDNs necesarios y estilos en línea para compatibilidad con SweetAlert2 y FontAwesome
    csp = {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "'unsafe-inline'",  # Permitir inline scripts con nonce o unsafe-inline como fallback
            'https://cdn.jsdelivr.net',
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",  # Necesario para SweetAlert2 y otros estilos dinámicos
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com',  # FontAwesome desde CloudFlare
        ],
        'font-src': [
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com',  # FontAwesome desde CloudFlare
        ],
        'img-src': [
            "'self'",
            'data:',
        ],
        'connect-src': [
            "'self'",
            'https://cdn.jsdelivr.net',
        ]
    }

    talisman.init_app(
        app, 
        content_security_policy=csp,
        force_https=False,  # Desactivar HTTPS para desarrollo
        content_security_policy_nonce_in=['script-src'],
        permissions_policy={},  # Ignorar browsing-topics de forma segura
    )

    # --- FILTRO DE PLANTILLA PARA ZONA HORARIA ---
    # Se define un filtro personalizado para Jinja2.
    @app.template_filter('localtime')
    def localtime_filter(utc_dt):
        """
        Convierte una fecha y hora (asumida como UTC) a la zona horaria local de Perú (UTC-5).
        """
        if utc_dt is None:
            return 'N/A'
        # Se restan 5 horas para ajustar de UTC a America/Lima.
        local_dt = utc_dt - timedelta(hours=5)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')

    # --- FUNCIÓN PARA OBTENER EL NONCE DE CSP EN TEMPLATES ---
    @app.context_processor
    def inject_csp_nonce():
        """Inyecta la función csp_nonce() en todos los templates."""
        def csp_nonce():
            from flask import g, request
            
            # Talisman almacena el nonce en g.csp_nonce
            nonce = g.get('csp_nonce', '')
            
            # Si no está en g, intenta obtenerlo de la respuesta headers
            if not nonce and hasattr(request, 'environ'):
                # Obtener del contexto local de Talisman
                nonce = g.get('csp_nonce', '')
            
            return nonce
        
        return {'csp_nonce': csp_nonce}

    with app.app_context():
        # --- Inyección de Dependencias (sin cambios) ---
        usuario_repo = SqlServerUsuarioRepository()
        personal_repo = SqlServerPersonalRepository()
        audit_repo = SqlServerAuditoriaRepository()
        backup_repo = SqlServerBackupRepository() 
        solicitud_repo = SqlServerSolicitudRepository()
        
        app.config['USUARIO_REPOSITORY'] = usuario_repo
        app.config['PERSONAL_REPOSITORY'] = personal_repo
        app.config['AUDIT_REPOSITORY'] = audit_repo
        
        email_service = EmailService(mail)
        audit_service = AuditService(audit_repo)
        
        app.config['BACKUP_SERVICE'] = BackupService(backup_repo, app.config, audit_service)
        app.config['SOLICITUDES_SERVICE'] = SolicitudService(solicitud_repo)
        
        app.config['USUARIO_SERVICE'] = UsuarioService(usuario_repo, email_service)
        app.config['AUDIT_SERVICE'] = audit_service
        app.config['LEGAJO_SERVICE'] = LegajoService(personal_repo, audit_service, app.config['USUARIO_SERVICE'])
        app.config['MONITORING_SERVICE'] = MonitoringService(personal_repo)

        # Seguridad: Mover la importación de blueprints aquí para evitar importaciones circulares
        from .presentation.routes.auth_routes import auth_bp
        from .presentation.routes.legajo_routes import legajo_bp
        from .presentation.routes.sistemas_routes import sistemas_bp
        from .presentation.routes.rrhh_routes import rrhh_bp
        from .presentation.routes.error_routes import error_bp
        from .presentation.routes.personal_routes import personal_bp # <-- Nuevo blueprint para empleados
        from .presentation.routes.pdf_upload_routes import pdf_bp # <-- Nuevo blueprint para PDF
        from .presentation.routes.admin_catalogo_routes import admin_catalogo_bp # <-- Nuevo blueprint para catálogos
        # Registrar Blueprints
        app.register_blueprint(auth_bp)
        app.register_blueprint(legajo_bp)
        app.register_blueprint(sistemas_bp)
        app.register_blueprint(rrhh_bp)
        app.register_blueprint(error_bp)
        app.register_blueprint(personal_bp) # <-- Registrar blueprint de empleados
        app.register_blueprint(pdf_bp) # <-- Registrar blueprint de PDF
        app.register_blueprint(admin_catalogo_bp) # <-- Registrar blueprint de catálogos


        @app.route('/')
        def index():
            # Si no está autenticado, redirige a login
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Si está autenticado, redirige según su rol
            if current_user.rol == 'Sistemas':
                return redirect(url_for('sistemas.dashboard'))
            elif current_user.rol == 'RRHH':
                return redirect(url_for('rrhh.inicio_rrhh'))
            elif current_user.rol == 'AdministradorLegajos':
                return redirect(url_for('legajo.dashboard'))
            else:
                # Sin rol reconocido, desloguea por seguridad
                logout_user()
                flash("Su rol de usuario no tiene una página de inicio asignada.", "warning")
                return redirect(url_for('auth.login'))

        @app.route('/health')
        def health():
            """Endpoint de salud para verificar que el servidor está activo"""
            from flask import jsonify
            return jsonify({'status': 'ok', 'message': 'Servidor activo'})

        # Se elimina la ruta /dashboard conflictiva.
        # La lógica de redirección ahora está centralizada en la ruta raíz ('/').
        
    return app


    
