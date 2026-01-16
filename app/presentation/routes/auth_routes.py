# RUTA: app/presentation/routes/auth_routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, send_from_directory
from flask_login import login_user, logout_user, current_user, login_required
from app.application.forms import LoginForm, TwoFactorForm
from app import limiter
from app.application.services.usuario_service import UsuarioService
from app.core.security import AccountLockoutManager
from app.application.services.file_validation_service import FileValidationService
from PIL import Image, ImageOps
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/fotos/<filename>')
def serve_foto_perfil(filename):
    """Sirve las fotos de perfil de los usuarios de forma segura."""
    try:
        fotos_dir = current_app.config.get('FOTOS_PERFIL_DIR')
        if not fotos_dir:
            # Fallback si no está configurado
            fotos_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'presentation',
                'static',
                'uploads',
                'fotos'
            )
        return send_from_directory(fotos_dir, filename)
    except Exception as e:
        current_app.logger.error(f"Error al servir foto de perfil: {e}")
        # Retornar imagen por defecto o error 404
        return '', 404


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def login():
    """Ruta de inicio de sesión optimizada para enviar el código real."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            username = form.username.data
            selected_role = form.role.data 
            
            # 1. SEGURIDAD: Verificar bloqueo de cuenta
            is_locked, minutos_restantes = AccountLockoutManager.is_account_locked(username)
            if is_locked:
                flash(f"Cuenta bloqueada temporalmente. Intenta en {minutos_restantes} minutos.", 'warning')
                return redirect(url_for('auth.login'))
            
            usuario_service = current_app.config['USUARIO_SERVICE']
            result = usuario_service.attempt_login(username, form.password.data)

            # Manejo de errores de email
            if isinstance(result, tuple) and result[0] == 'email_error':
                flash(f'⚠️ {result[1]}', 'warning')
                return redirect(url_for('auth.login'))
            
            # 2. PROCESAR ÉXITO (ID y Código Real)
            if result and isinstance(result, tuple):
                user_id, code_real = result  # <--- AQUÍ ESTÁ TU CÓDIGO DE 6 DÍGITOS
                user_temp = usuario_service.get_user_by_id(user_id)
                
                # VALIDACIÓN DE ROL
                if user_temp and user_temp.rol != selected_role:
                    flash(f'El usuario no pertenece al rol "{selected_role}".', 'warning')
                    return redirect(url_for('auth.login'))

                # 📧 3. ENVÍO DE CORREO (USANDO EL CÓDIGO REAL)
                email_service = current_app.config.get('EMAIL_SERVICE')
                
                if email_service and user_temp.email:
                    # 💡 CAMBIO CRÍTICO: Usamos 'code_real' directamente. 
                    # NO llames a get_current_2fa aquí porque eso te daría el hash.
                    email_service.send_2fa_code(
                        recipient_email=user_temp.email,
                        user_name=user_temp.username,
                        code=code_real # <--- LOS 6 DÍGITOS LIMPIOS
                    )
                    flash(f'Se ha enviado un código de seguridad a: {user_temp.email}', 'info')

                # 4. PREPARAR SESIÓN
                AccountLockoutManager.reset_failed_attempts(username)
                session['2fa_user_id'] = user_id # 💡 IMPORTANTE: Solo el ID, no la tupla
                session['2fa_username'] = username
                session['2fa_remember_me'] = form.remember_me.data
                
                return redirect(url_for('auth.verify_2fa'))
            
            else:
                AccountLockoutManager.increment_failed_attempts(username)
                flash('Usuario o contraseña incorrectos.', 'danger')
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            current_app.logger.error(f"Error inesperado en login: {e}")
            flash("Ocurrió un error inesperado.", 'danger')
            return redirect(url_for('auth.login'))
            
    return render_template('auth/login.html', form=form)

@auth_bp.route('/login/verify', methods=['GET', 'POST'])
# Seguridad: Aplicar un límite de intentos para prevenir el bombardeo de códigos.
@limiter.limit("5 per minute")
def verify_2fa():
    if '2fa_user_id' not in session:
        return redirect(url_for('auth.login'))

    form = TwoFactorForm()
    if form.validate_on_submit():
        user_id = session['2fa_user_id']
        usuario_service = current_app.config['USUARIO_SERVICE']
        user = usuario_service.verify_2fa_code(user_id, form.code.data)

        if user:
            usuario_service.update_last_login(user_id)
            # Recuperar el estado de "Recordarme" de la sesión
            remember = session.get('2fa_remember_me', False)
            login_user(user, remember=remember)
            
            # Limpiar toda la información de 2FA de la sesión
            session.pop('2fa_user_id', None)
            session.pop('2fa_username', None)
            session.pop('2fa_remember_me', None)
            
            flash(f'Bienvenido de nuevo, {user.nombre_completo or user.username}!', 'success')
            
            # ------------------------------------------------------------------
            # 🔑 CORRECCIÓN: Lógica de redirección basada en el rol
            # ------------------------------------------------------------------
            if user.rol == 'Sistemas':
                # Redirige al Dashboard de Sistemas (el de las 6 tarjetas)
                return redirect(url_for('sistemas.dashboard'))
            elif user.rol == 'RRHH':
                return redirect(url_for('rrhh.inicio_rrhh')) 
            elif user.rol == 'AdministradorLegajos':
                return redirect(url_for('legajo.dashboard'))
            elif user.rol == 'Personal':
                return redirect(url_for('personal.inicio'))
            else:
                # Redirige a una página de índice general si el rol no coincide
                return redirect(url_for('index'))
            # ------------------------------------------------------------------
            
        else:
            flash('Código de verificación incorrecto o expirado.', 'danger')

    return render_template('auth/verify_2fa.html', form=form, username=session.get('2fa_username'))

@auth_bp.route('/cambiar-email', methods=['POST'])
@login_required
def cambiar_email():
    """Ruta para cambiar el email del usuario actual"""
    email_nuevo = request.form.get('email_nuevo', '').strip()
    
    if not email_nuevo:
        flash('Por favor, ingresa un nuevo email.', 'danger')
        return redirect(url_for('auth.perfil'))
    
    if email_nuevo == current_user.email:
        flash('El nuevo email es igual al actual.', 'warning')
        return redirect(url_for('auth.perfil'))
    
    try:
        usuario_service = current_app.config['USUARIO_SERVICE']
        mensaje, tipo = usuario_service.update_email(current_user.id, email_nuevo)
        flash(mensaje, tipo)
    except Exception as e:
        current_app.logger.error(f"Error al cambiar email del usuario {current_user.id}: {e}")
        flash('Ocurrió un error al actualizar el email.', 'danger')
    
    return redirect(url_for('auth.perfil'))

@auth_bp.route('/logout')
def logout():
    # Limpia todos los mensajes flash pendientes de la sesión anterior
    session.clear() 
    logout_user()
    flash('Has cerrado la sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))

from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.application.services.usuario_service import UsuarioService # Asegúrate de importar el servicio
from werkzeug.security import generate_password_hash

@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    """
    Muestra el perfil del usuario y permite actualizar la foto (ahora con llenado total).
    """
    usuario_service = current_app.config.get('USUARIO_SERVICE')
    legajo_service = current_app.config.get('LEGAJO_SERVICE')
    
    # Obtener datos para la vista
    user_data = {
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'rol': current_user.rol if hasattr(current_user, 'rol') else None,
        'estado': current_user.estado if hasattr(current_user, 'estado') else 'activo',
        'personal_info': None,
        'fecha_registro': current_user.fecha_registro if hasattr(current_user, 'fecha_registro') else None,
    }
    
    try:
        if legajo_service and hasattr(current_user, 'personal_id') and current_user.personal_id:
            personal = legajo_service.get_personal_by_id(current_user.personal_id)
            if personal:
                user_data['personal_info'] = {
                    'nombres': f"{personal.get('nombres', '')} {personal.get('apellidos', '')}".strip(),
                    'dni': personal.get('dni', 'N/A'),
                    'email': personal.get('email', current_user.email),
                    'telefono': personal.get('telefono', 'N/A'),
                    'unidad_administrativa': personal.get('unidad_administrativa', 'N/A'),
                    'cargo': personal.get('cargo', 'N/A'),
                    'fecha_ingreso': personal.get('fecha_ingreso', 'N/A'),
                }
    except Exception as e:
        current_app.logger.warning(f"No se pudo obtener datos personales: {str(e)}")
    
    if request.method == 'POST':
        # --- CARGA DE FOTO DE PERFIL ---
        if 'foto_carnet' in request.files:
            archivo = request.files['foto_carnet']
            
            if archivo and archivo.filename != '':
                # 1. Validar archivo
                is_valid, error_message = FileValidationService.validate_file(
                    archivo, allowed_types=['jpg', 'jpeg', 'png']
                )
                
                if not is_valid:
                    flash(error_message or 'Archivo no permitido.', 'danger')
                    return redirect(url_for('auth.perfil'))
                
                try:
                    from PIL import Image, ImageOps # 🚀 IMPORTANTE: ImageOps para el recorte
                    fotos_dir = current_app.config.get('FOTOS_PERFIL_DIR')
                    if not fotos_dir:
                        fotos_dir = os.path.join(current_app.root_path, 'presentation', 'static', 'uploads', 'fotos')
                    os.makedirs(fotos_dir, exist_ok=True)
                    
                    # 2. Procesar imagen
                    imagen = Image.open(archivo.stream)
                    
                    # Convertir a RGB si tiene transparencia (PNG)
                    if imagen.mode in ('RGBA', 'LA', 'P'):
                        imagen = imagen.convert('RGB')
                    
                    # 🚀 LA MEJORA: ImageOps.fit recorta y rellena el cuadrado de 800x800
                    # Esto evita que la foto se vea pequeña con bordes blancos.
                    new_img = ImageOps.fit(imagen, (800, 800), Image.Resampling.LANCZOS)
                    
                    filename = f"foto_{current_user.id}.jpg"
                    filepath = os.path.join(fotos_dir, filename)
                    
                    # 3. Guardar optimizado
                    new_img.save(filepath, 'JPEG', quality=85, optimize=True)
                    
                    # 4. Actualizar BD y Auditoría
                    if usuario_service:
                        usuario_service.update_foto_perfil(current_user.id, filename)
                    
                    audit_service = current_app.config.get('AUDIT_SERVICE')
                    if audit_service:
                        audit_service.log(current_user.id, 'Usuario', 'ACTUALIZAR_FOTO', f"Foto actualizada")
                    
                    flash('¡Foto de perfil actualizada con éxito!', 'success')
                    return redirect(url_for('auth.perfil'))
                
                except Exception as e:
                    current_app.logger.error(f"Error al guardar foto: {str(e)}")
                    flash('Ocurrió un error al guardar la foto.', 'danger')
                    return redirect(url_for('auth.perfil'))

        # --- CAMBIO DE CONTRASEÑA ---
        password_actual = request.form.get('password_actual')
        password_nueva = request.form.get('password_nueva')
        password_confirmacion = request.form.get('password_confirmacion')

        if password_actual and password_nueva:
            if password_nueva != password_confirmacion:
                flash('Las contraseñas no coinciden.', 'danger')
            elif not current_user.check_password(password_actual):
                flash('Contraseña actual incorrecta.', 'danger')
            else:
                try:
                    usuario_service.update_password(current_user.id, password_nueva)
                    flash('¡Contraseña actualizada!', 'success')
                except Exception as e:
                    flash('Error al actualizar contraseña.', 'danger')
            return redirect(url_for('auth.perfil'))

    return render_template('auth/perfil.html', user=current_user, user_data=user_data)