# app/presentation/routes/error_routes.py
from flask import Blueprint, render_template, current_app, flash, redirect, request, url_for
from flask_login import login_required, current_user # 🚀 Importación necesaria para proteger la ruta
from app.decorators import role_required # 🚀 Importación necesaria para validar el rol 'Sistemas'

# Se utiliza un Blueprint para organizar las rutas de manejo de errores.
error_bp = Blueprint('error', __name__)

@error_bp.app_errorhandler(404)
def not_found_error(error):
    """
    Manejador para errores 404 (Página no encontrada).
    
    Esta función se activa cuando Flask no puede encontrar una ruta.
    Renderiza una plantilla HTML personalizada para informar al usuario.
    """
    current_app.logger.warning(f"Se accedió a una ruta no encontrada: {error}")
    return render_template('errors/404.html'), 404

@error_bp.app_errorhandler(500)
def internal_error(error):
    """
    Manejador para errores 500 (Error interno del servidor).
    
    Esta función se activa cuando ocurre una excepción no controlada en la aplicación.
    Registra el error completo en el log para depuración y muestra una página genérica al usuario.
    """
    # Es crucial registrar el traceback completo para poder diagnosticar el problema.
    current_app.logger.error(f"Error interno del servidor: {error}", exc_info=True)
    return render_template('errors/500.html'), 500

@error_bp.app_errorhandler(413)
def request_entity_too_large(error):
    """
    Manejador para errores 413 (Payload Too Large).
    
    Esta función se activa cuando un archivo subido excede el límite de MAX_CONTENT_LENGTH.
    En lugar de mostrar una página de error, muestra un mensaje flash y redirige
    a la página anterior.
    """
    current_app.logger.warning(f"Se intentó subir un archivo demasiado grande: {error}")
    max_size_mb = current_app.config.get('MAX_CONTENT_LENGTH', 0) / (1024 * 1024)
    flash(f"Error: El archivo es demasiado grande. El tamaño máximo permitido es de {max_size_mb:.0f} MB.", 'danger')
    
    # Redirige al usuario a la página desde la que vino.
    # Si no se puede determinar, lo envía a la página principal.
    return redirect(request.referrer or url_for('index'))


@error_bp.route('/errores/limpiar', methods=['POST'])
@login_required
@role_required('Sistemas')
def limpiar_logs():
    """Ruta para vaciar la tabla de errores."""
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        repo = legajo_service._personal_repo 
        
        if repo.limpiar_historial_errores():
            flash("Historial de errores eliminado correctamente.", "success")
        else:
            flash("No se pudo limpiar el historial.", "danger")
            
    except Exception as e:
        flash(f"Error técnico: {str(e)}", "danger")
    
    # 🚀 CORRECCIÓN 2: Ahora 'error.listar_errores' sí existe y el nombre coincide
    return redirect(url_for('error.listar_errores'))

@error_bp.route('/errores')
@login_required
@role_required('Sistemas')
def listar_errores():
    """
    Esta es la función que faltaba. Muestra la tabla de logs.
    """
    legajo_service = current_app.config['LEGAJO_SERVICE']
    # Supongamos que tu repo tiene un método para traer los errores
    errores = legajo_service._personal_repo.get_all_errors() 
    return render_template('admin/registro_errores.html', errores=errores)