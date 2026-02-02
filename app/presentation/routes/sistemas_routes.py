from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, send_file, jsonify, abort
from flask_login import login_required, current_user
from app.decorators import role_required
from app.application.forms import UserManagementForm
import io
from datetime import datetime, timedelta
from app.infrastructure.persistence.error_repository import ErrorRepository 


# CORRECCIÓN DEFINITIVA DE LA BASE DE DATOS
# Importamos la conexión desde la ruta real que vimos en estructura_repository.py
from app.database.connector import get_db_write as db 

# Importamos los repositorios necesarios
from app.infrastructure.persistence.sqlserver_repository import SqlServerBackupRepository, SqlServerPersonalRepository

sistemas_bp = Blueprint('sistemas', __name__) 

# ------------------------------------------------------------------------
# 1. VISTAS PRINCIPALES DEL DASHBOARD
# ------------------------------------------------------------------------

@sistemas_bp.route('/dashboard')
@login_required
@role_required('Sistemas')
def dashboard():
    return render_template('sistemas/sistemas_inicio.html') 

@sistemas_bp.route('/auditoria')
@login_required
@role_required('Sistemas')
def auditoria():
    page = request.args.get('page', 1, type=int)
    audit_service = current_app.config['AUDIT_SERVICE']
    pagination = audit_service.get_logs(page, 20)
    audit_service.log(current_user.id, 'Auditoria', 'CONSULTA', f'El usuario consultó la página {page} de la bitácora.')
    return render_template('sistemas/auditoria.html', pagination=pagination)


# ------------------------------------------------------------------------
# 2. GESTIÓN DE USUARIOS
# ------------------------------------------------------------------------

@sistemas_bp.route('/usuarios')
@login_required
@role_required('Sistemas')
def gestionar_usuarios():
    usuario_service = current_app.config['USUARIO_SERVICE']
    usuarios = usuario_service.get_all_users_with_roles() 
    
    # Ajuste para que '15:32' baje a '12:32' (Hora Real Pasco)
    for user in usuarios:
        if hasattr(user, 'last_login') and user.last_login:
            user.last_login = user.last_login - timedelta(hours=5)
            
    return render_template('sistemas/gestionar_usuarios.html', usuarios=usuarios)


@sistemas_bp.route('/usuarios/crear', methods=['GET', 'POST'])
@login_required
@role_required('Sistemas')
def crear_usuario():
    form = UserManagementForm() 
    
    # Carga de roles para el selector del formulario
    try:
        repo = current_app.config['USUARIO_REPOSITORY']
        roles = repo.get_all_roles()
        form.id_rol.choices = [(r.id_rol, r.nombre_rol) for r in roles]
    except Exception as e:
        current_app.logger.warning(f"Error al cargar roles: {e}")
    
    if form.validate_on_submit():
        # --- VALIDACIONES DE SEGURIDAD ---
        if not form.username.data or not form.username.data.strip():
            form.username.errors = ('El nombre de usuario es requerido.',)
            return render_template('sistemas/crear_usuario.html', form=form)
        
        if not form.email.data or not form.email.data.strip():
            form.email.errors = ('El correo electrónico es requerido.',)
            return render_template('sistemas/crear_usuario.html', form=form)
            
        if not form.id_rol.data or form.id_rol.data == 0:
            form.id_rol.errors = ('Debe seleccionar un rol.',)
            return render_template('sistemas/crear_usuario.html', form=form)

        try:
            usuario_service = current_app.config['USUARIO_SERVICE']
            
            # 1. PREPARACIÓN DE DATOS (Diccionario editable)
            # Extraemos los datos del formulario para poder manipularlos antes de guardar
            datos_usuario = form.data.copy()
            
            # 2. TRANSFORMACIÓN A MINÚSCULAS
            # Aseguramos que el usuario se guarde como 'junior_1' y no 'Junior_1'
            datos_usuario['username'] = datos_usuario['username'].lower().strip()
            
            # 3. VERIFICACIÓN DE NOMBRE COMPLETO
            # 'nombre_completo' ya viaja en datos_usuario porque lo añadimos al Form
            if not datos_usuario.get('nombre_completo'):
                current_app.logger.warning("Intento de crear usuario sin nombre completo.")

            # 4. EJECUCIÓN DEL SERVICIO
            # Pasamos el diccionario procesado al servicio de la municipalidad
            mensaje, tipo = usuario_service.create_user(datos_usuario)
            
            flash(mensaje, tipo)
            
            if tipo == 'success':
                # Redirección exitosa al panel de gestión
                return redirect(url_for('sistemas.gestionar_usuarios'))
            else:
                return render_template('sistemas/crear_usuario.html', form=form)

        except Exception as e:
            current_app.logger.error(f"Error crítico al crear usuario: {str(e)}")
            flash(f'Error al crear usuario: {str(e)}', 'danger')

    return render_template('sistemas/crear_usuario.html', form=form)


@sistemas_bp.route('/usuarios/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('Sistemas')
def editar_usuario(user_id):
    try:
        usuario_service = current_app.config['USUARIO_SERVICE']
        user = usuario_service.get_user_by_id_for_editing(user_id)
        if not user:
            flash('Usuario no encontrado.', 'danger')
            return redirect(url_for('sistemas.gestionar_usuarios'))
        
        form = UserManagementForm(obj=user)
        
        if form.validate_on_submit():
            try:
                cambios_realizados = []
                cambios_fallidos = []
                
                if form.nueva_username.data:
                    resultado, categoria = usuario_service.update_username(user_id, form.nueva_username.data)
                    if categoria == 'success':
                        cambios_realizados.append('usuario')
                    else:
                        cambios_fallidos.append(resultado)
                
                if form.nuevo_email.data:
                    resultado, categoria = usuario_service.update_email(user_id, form.nuevo_email.data)
                    if categoria == 'success':
                        cambios_realizados.append('correo')
                    else:
                        cambios_fallidos.append(resultado)
                
                if form.nueva_password.data:
                    resultado, categoria = usuario_service.update_user_password(user_id, form.nueva_password.data)
                    if categoria == 'success':
                        cambios_realizados.append('contraseña')
                    else:
                        cambios_fallidos.append(resultado)
                
                if cambios_fallidos:
                    for error in cambios_fallidos:
                        flash(error, 'warning')
                
                if cambios_realizados:
                    items = ' y '.join(cambios_realizados)
                    flash(f'Se actualizaron correctamente: {items}.', 'success')
                elif not cambios_fallidos:
                    flash('No se realizaron cambios.', 'info')
                
                if cambios_realizados or cambios_fallidos:
                    return redirect(url_for('sistemas.gestionar_usuarios'))
            except Exception as e:
                current_app.logger.error(f"Error al actualizar usuario {user_id}: {e}")
                flash(f'Error al actualizar el usuario: {e}', 'danger')
        
        return render_template('sistemas/editar_usuario.html', form=form, user=user)

    except Exception as e:
        current_app.logger.error(f"ERROR EN EDITAR_USUARIO: {e}")
        flash(f"Ocurrió un error al editar el usuario. Por favor intenta de nuevo.", 'danger')
        return redirect(url_for('sistemas.gestionar_usuarios'))


@sistemas_bp.route('/usuarios/reset_password/<int:user_id>', methods=['POST'])
@login_required
@role_required('Sistemas')
def reset_password(user_id):
    try:
        usuario_service = current_app.config['USUARIO_SERVICE']
        mensaje, tipo = usuario_service.reset_user_password(user_id)
        flash(mensaje, tipo)
    except Exception as e:
        current_app.logger.error(f"Error al resetear contraseña del usuario {user_id}: {e}")
        flash('Ocurrió un error técnico al resetear la contraseña.', 'danger')
    return redirect(url_for('sistemas.gestionar_usuarios'))



@sistemas_bp.route('/usuarios/cambiar_estado/<int:personal_id>', methods=['POST'])
@login_required
# Acceso total para los tres roles institucionales
@role_required('Sistemas', 'RRHH', 'AdministradorLegajos')
def cambiar_estado_desde_sistemas(personal_id):
    data = request.get_json()
    nuevo_estado = data.get('estado')

    try:
        conn = db() # get_db_write as db
        cursor = conn.cursor()
        # Sincronización por ID (evita fallos de DNI)
        cursor.execute("EXEC sp_cambiar_estado_laboral ?, ?", (personal_id, nuevo_estado))
        conn.commit()
        return jsonify({'success': True, 'message': 'Sincronización completada.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ------------------------------------------------------------------------
# 3. MANTENIMIENTO TÉCNICO Y BACKUPS
# ------------------------------------------------------------------------

@sistemas_bp.route('/mantenimiento/backups')
@login_required
@role_required('Sistemas')
def gestion_backups():
    try:
        backup_service = current_app.config['BACKUP_SERVICE']
        historial_data = backup_service.get_backup_history() 
    except Exception as e:
        current_app.logger.error(f"Error al cargar historial de backups: {e}")
        historial_data = []
    return render_template('sistemas/gestion_backups.html', historial=historial_data) 

@sistemas_bp.route('/mantenimiento/run_backup', methods=['POST'])
@login_required
@role_required('Sistemas')
def run_backup():
    try:
        if 'BACKUP_SERVICE' not in current_app.config:
            raise Exception("El servicio de backup no está inicializado.")
        current_app.config['BACKUP_SERVICE'].execute_full_backup()
        flash('Copia de seguridad iniciada y completada con éxito.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error al ejecutar backup manual: {e}")
        flash(f'Error al ejecutar la copia de seguridad. Detalle: {e}', 'danger')
    return redirect(url_for('sistemas.gestion_backups'))


@sistemas_bp.route('/mantenimiento/estado_servidor')
@login_required
@role_required('Sistemas')
def estado_servidor():
    monitoring_service = current_app.config.get('MONITORING_SERVICE')
    
    # Obtener métricas del sistema
    system_metrics = monitoring_service.get_system_metrics()
    
    # Obtener métricas de la base de datos
    db_metrics = monitoring_service.get_database_metrics()
    
    # Combinar todas las métricas
    metrics = {**system_metrics, **db_metrics}
    
    return render_template('sistemas/estado_servidor.html', **metrics)


@sistemas_bp.route('/errores')
@login_required
@role_required('Sistemas') # Mantenlo si ya tienes el decorador funcionando
def errores():
    """
    Carga el historial real de fallos técnicos desde la instancia OSCAR.
    """
    try:
        # 🚀 Usamos el repositorio específico de errores para obtener los datos REALES
        repo = ErrorRepository() 
        lista_de_errores = repo.obtener_todos() # Este método debe devolver archivo, linea, etc.
        
        return render_template('sistemas/registro_errores.html', errores=lista_de_errores)
    
    except Exception as e:
        # Si algo falla al cargar la lista, usamos el logger de Flask
        current_app.logger.error(f"Error al cargar bitácora de fallos: {e}")
        flash("No se pudo conectar con la tabla de errores en SQL Server.", "danger")
        return render_template('sistemas/registro_errores.html', errores=[])

@sistemas_bp.route('/test-error')
@login_required
@role_required('Sistemas')
def generar_error_prueba():
    """
    Ruta de prueba profesional: Forza un error y usa el Handler Automático.
    """
    try:
        # 🚀 Provocamos el error de división por cero
        error_forzado = 10 / 0 
        
    except Exception as e:
        # 🚀 LLAMADA CLAVE: Usamos tu nueva utilidad automática
        # Esto guardará: Archivo, Línea, Stacktrace y Usuario sin que tú escribas nada más.
        from app.utils.error_handler import registrar_error_automatico
        registrar_error_automatico(e)
        
        flash('¡Éxito! El error de prueba fue capturado y registrado con su ADN técnico.', 'success')
    
    # Redirigimos de vuelta para ver el nuevo registro en la tabla
    return redirect(url_for('sistemas.errores'))


# ------------------------------------------------------------------------
# 4. REPORTES Y SOLICITUDES
# ------------------------------------------------------------------------

@sistemas_bp.route('/reportes')
@login_required
@role_required('Sistemas')
def reportes():
    return render_template('sistemas/reportes.html')


# DESACTIVADO: Esta funcionalidad ya no se utiliza
# @sistemas_bp.route('/solicitudes')
# @login_required
# @role_required('Sistemas')
# def solicitudes_pendientes():
#     solicitudes_service = current_app.config.get('SOLICITUDES_SERVICE')
#     solicitudes = solicitudes_service.get_all_pending() if solicitudes_service else []
#     return render_template('sistemas/solicitudes_pendientes.html', requests=solicitudes)


# @sistemas_bp.route('/solicitudes/procesar/<int:request_id>', methods=['POST'])
# @login_required
# @role_required('Sistemas')
# def procesar_solicitud(request_id):
#     action = request.form.get('action')
#     if action in ['aprobar', 'rechazar']:
#         solicitud_service = current_app.config['SOLICITUDES_SERVICE']
#         solicitud_service.process_request(request_id, action)
#         flash(f'Solicitud {action}da con éxito.', 'success')
#     else:
#         flash('Acción no válida.', 'danger')
#     return redirect(url_for('sistemas.solicitudes_pendientes'))


# ------------------------------------------------------------------------
# 5. GESTIÓN DE DOCUMENTOS ELIMINADOS
# ------------------------------------------------------------------------

@sistemas_bp.route('/documentos/eliminados')
@login_required
@role_required('Sistemas')
def documentos_eliminados():
    """
    Vista para gestionar documentos marcados como eliminados.
    """
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        audit_service = current_app.config['AUDIT_SERVICE']
        
        # 1. OBTENER DATOS CRUDOS
        raw_docs = legajo_service.get_deleted_documents()
        
        # 2. CONVERSIÓN EXPLÍCITA A DICCIONARIOS
        # Convertimos cada fila (Row) a un diccionario de Python puro.
        documentos_lista = [dict(row) for row in raw_docs] if raw_docs else []
        
        audit_service.log(
            current_user.id,
            'Documentos',
            'CONSULTA',
            'Consultó la lista de documentos eliminados'
        )
        
        # 3. Enviar la lista al template
        return render_template('sistemas/documentos_eliminados.html', documentos=documentos_lista)

    except Exception as e:
        current_app.logger.error(f"Error al obtener documentos eliminados: {e}")
        flash(
            '❌ Error al cargar los documentos eliminados.',
            'danger'
        )
        return redirect(url_for('sistemas.dashboard'))


@sistemas_bp.route('/documentos/recuperar/<int:documento_id>', methods=['POST'])
@login_required
@role_required('Sistemas')
def recuperar_documento(documento_id):
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        audit_service = current_app.config['AUDIT_SERVICE']
        
        legajo_service.recover_document(documento_id)
        
        audit_service.log(
            current_user.id,
            'Documentos',
            'RECUPERAR',
            f'Recuperó el documento con ID {documento_id}'
        )
        flash('Documento recuperado exitosamente.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error al recuperar documento {documento_id}: {e}")
        flash(f'Error al recuperar el documento: {e}', 'danger')
    
    return redirect(url_for('sistemas.documentos_eliminados'))


@sistemas_bp.route('/documentos/eliminar-permanente/<int:documento_id>', methods=['POST'])
@login_required
@role_required('Sistemas')
def eliminar_documento_permanente(documento_id):
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        audit_service = current_app.config['AUDIT_SERVICE']
        
        legajo_service.permanently_delete_document(documento_id)
        
        audit_service.log(
            current_user.id,
            'Documentos',
            'ELIMINAR PERMANENTEMENTE',
            f'Eliminó permanentemente el documento ID: {documento_id}'
        )
        flash('Documento eliminado permanentemente de la base de datos.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error al eliminar permanentemente documento {documento_id}: {e}")
        flash(f'Error al eliminar el documento: {e}', 'danger')
    
    return redirect(url_for('sistemas.documentos_eliminados'))

@sistemas_bp.route('/documentos/diagnostico')
@login_required
@role_required('Sistemas')
def documentos_eliminados_diagnostico():
    results = {'timestamp': str(datetime.now()), 'status': 'running'}
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        docs = list(legajo_service.get_deleted_documents())
        results['count'] = len(docs)
        results['first_item'] = str(docs[0]) if docs else "None"
        results['status'] = 'success'
    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)
    return jsonify(results)

# app/presentation/routes/sistemas_routes.py

@sistemas_bp.route('/documentos/eliminados/restaurar-todo', methods=['POST'])
@login_required
def restaurar_todo():
    """Restaura todos los archivos de la papelera unificada de la HMPP."""
    if current_user.id_rol != 1: 
        return abort(403)
        
    repo = SqlServerPersonalRepository()
    if repo.recover_all_documents():
        flash("Se han restaurado todos los documentos exitosamente.", "success")
    else:
        flash("Hubo un error al intentar restaurar los documentos.", "danger")
        
    # Asegúrate de que el endpoint sea el correcto (probablemente 'sistemas.get_deleted_documents')
    return redirect(url_for('sistemas.documentos_eliminados')) # CORREGIDO

@sistemas_bp.route('/documentos/eliminados/vaciar', methods=['POST'])
@login_required
def vaciar_papelera():
    """Elimina permanentemente todos los archivos de la papelera."""
    if current_user.id_rol != 1:
        return abort(403)
        
    repo = SqlServerPersonalRepository()
    if repo.empty_recycle_bin():
        flash("La papelera ha sido vaciada permanentemente.", "info")
    else:
        flash("Error al intentar vaciar la papelera.", "danger")
        
    return redirect(url_for('sistemas.documentos_eliminados')) # CORREGIDO
