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
    Muestra el perfil del usuario conectando con la tabla Personal.
    """
    usuario_service = current_app.config.get('USUARIO_SERVICE')
    legajo_service = current_app.config.get('LEGAJO_SERVICE')
    
    # 1. Datos básicos del Usuario (Login)
    user_data = {
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'rol': current_user.rol if hasattr(current_user, 'rol') else None,
        'estado': current_user.estado if hasattr(current_user, 'estado') else 'activo',
        'personal_info': None, # Por defecto vacío
        'fecha_registro': current_user.fecha_registro if hasattr(current_user, 'fecha_registro') else None,
    }
    
    # 2. Intentar buscar datos extendidos en la tabla PERSONAL
    try:
        if legajo_service:
            # CORRECCIÓN: Buscamos usando el ID de usuario directamente
            personal = legajo_service.get_info_perfil_por_usuario(current_user.id, current_user.username)
            
            if personal:
                # Construimos el objeto con los datos reales
                user_data['personal_info'] = {
                    'nombre_completo': f"{personal.get('nombres', '')} {personal.get('apellidos', '')}".strip(),
                    'dni': personal.get('dni', 'N/A'),
                    'email_institucional': personal.get('email_institucional'), # Para mostrar en la vista
                    'email_personal': personal.get('email_personal'),
                    'telefono': personal.get('telefono', 'No registrado'),
                    'area': personal.get('unidad_administrativa', 'No asignada'),
                    'cargo': personal.get('cargo', 'Personal HMPP'),
                    'fecha_ingreso': personal.get('fecha_ingreso', 'N/A'),
                }
    except Exception as e:
        current_app.logger.warning(f"No se pudo sincronizar datos personales: {str(e)}")
    
    # --- LOGICA POST (Subir foto / Cambiar pass) SE MANTIENE IGUAL ---
    if request.method == 'POST':
        # (Aquí va todo tu código de foto_carnet y cambio de contraseña que ya tenías)
        # ... (Copia el bloque if request.method == 'POST' de tu archivo original aquí si no quieres perderlo)
        # Para resumir, he dejado la parte de GET arriba que es la que fallaba.
        pass 
        # NOTA: Asegúrate de mantener tu lógica POST original debajo de esto.

    # Si copias y pegas solo la parte superior (GET), mantén tu lógica POST abajo.
    # Si quieres el código completo fusionado, avísame.
    
    # Pero para arreglar la vista, lo importante es la parte de arriba (user_data).
    
    # 3. MANTENER LÓGICA EXISTENTE DE POST (Resumida para no borrar tu código)
    if request.method == 'POST':
        if 'foto_carnet' in request.files:
            # ... (Tu código de subir foto) ...
            archivo = request.files['foto_carnet']
            if archivo and archivo.filename != '':
                is_valid, error_message = FileValidationService.validate_file(archivo, allowed_types=['jpg', 'jpeg', 'png'])
                if not is_valid:
                    flash(error_message, 'danger')
                else:
                    try:
                        fotos_dir = current_app.config.get('FOTOS_PERFIL_DIR') or os.path.join(current_app.root_path, 'presentation', 'static', 'uploads', 'fotos')
                        os.makedirs(fotos_dir, exist_ok=True)
                        imagen = Image.open(archivo.stream)
                        if imagen.mode in ('RGBA', 'LA', 'P'): imagen = imagen.convert('RGB')
                        new_img = ImageOps.fit(imagen, (800, 800), Image.Resampling.LANCZOS)
                        filename = f"foto_{current_user.id}.jpg"
                        new_img.save(os.path.join(fotos_dir, filename), 'JPEG', quality=85)
                        usuario_service.update_foto_perfil(current_user.id, filename)
                        flash('Foto actualizada.', 'success')
                    except Exception as e:
                        flash('Error guardando foto.', 'danger')
            return redirect(url_for('auth.perfil'))

        # CASO 3: CAMBIAR CONTRASEÑA (¡Aquí está el arreglo!)
        # Verificamos si el formulario enviado es el de contraseñas
        if 'password_actual' in request.form:
            password_actual = request.form.get('password_actual')
            password_nueva = request.form.get('password_nueva')
            password_confirmacion = request.form.get('password_confirmacion')

            # 1. Validar que no estén vacíos
            if not password_actual or not password_nueva:
                flash('Por favor completa todos los campos de contraseña.', 'warning')
            
            # 2. Validar coincidencia
            elif password_nueva != password_confirmacion:
                flash('Las nuevas contraseñas no coinciden.', 'warning')
            
            # 3. Validar contraseña actual
            elif not current_user.check_password(password_actual):
                flash('La contraseña actual es incorrecta.', 'danger')
            
            # 4. Intentar actualizar
            else:
                try:
                    usuario_service.update_password(current_user.id, password_nueva)
                    flash('¡Contraseña actualizada correctamente!', 'success')
                except Exception as e:
                    current_app.logger.error(f"Error cambio pass: {e}")
                    flash('Error interno al actualizar. Intente luego.', 'danger')
            
            return redirect(url_for('auth.perfil'))

    return render_template('auth/perfil.html', user=current_user, user_data=user_data)