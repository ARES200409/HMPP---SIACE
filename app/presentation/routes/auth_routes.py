# RUTA: app/presentation/routes/auth_routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app.application.forms import LoginForm, TwoFactorForm
from app import limiter
from app.application.services.usuario_service import UsuarioService
from app.core.security import AccountLockoutManager
from app.application.services.file_validation_service import FileValidationService
import os

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
# Seguridad: Aplicar un límite de intentos para prevenir ataques de fuerza bruta.
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            username = form.username.data
            selected_role = form.role.data  # <--- 1. Capturamos el rol seleccionado del formulario
            
            # ✅ SEGURIDAD: Verificar si cuenta está bloqueada
            is_locked, minutos_restantes = AccountLockoutManager.is_account_locked(username)
            if is_locked:
                mensaje = f"Cuenta bloqueada temporalmente por múltiples intentos fallidos. Intenta en {minutos_restantes} minutos."
                flash(mensaje, 'warning')
                current_app.logger.warning(f"SEGURIDAD: Intento de login en cuenta bloqueada: {username}")
                return redirect(url_for('auth.login'))
            
            usuario_service = current_app.config['USUARIO_SERVICE']
            result = usuario_service.attempt_login(username, form.password.data)

            # Verificar si result es una tupla (error de email)
            if isinstance(result, tuple) and result[0] == 'email_error':
                flash(f'⚠️ {result[1]}', 'warning')
                return redirect(url_for('auth.login'))
            
            # Si result es un ID de usuario (login exitoso de credenciales)
            if result:
                # <--- 2. VALIDACIÓN DE ROL (NUEVO) --->
                # Obtenemos el usuario temporalmente para verificar que coincida con el rol seleccionado
                user_temp = usuario_service.get_user_by_id(result)
                
                if user_temp and user_temp.rol != selected_role:
                    # Si el rol en base de datos no coincide con el seleccionado
                    current_app.logger.warning(f"SEGURIDAD: Intento de login con rol incorrecto. Usuario: {username}, Rol Real: {user_temp.rol}, Rol Seleccionado: {selected_role}")
                    flash(f'El usuario ingresado no pertenece al rol "{selected_role}".', 'warning')
                    return redirect(url_for('auth.login'))
                
                # <--- FIN VALIDACIÓN DE ROL --->

                # ✅ SEGURIDAD: Reiniciar contador en login exitoso
                AccountLockoutManager.reset_failed_attempts(username)
                
                session['2fa_user_id'] = result
                session['2fa_username'] = form.username.data
                # Guardar el estado de "Recordarme" en la sesión
                session['2fa_remember_me'] = form.remember_me.data
                return redirect(url_for('auth.verify_2fa'))
            else:
                # ✅ SEGURIDAD: Incrementar intentos fallidos e informar bloqueo
                fue_bloqueado = AccountLockoutManager.increment_failed_attempts(username)
                if fue_bloqueado:
                    flash('Cuenta bloqueada tras múltiples intentos fallidos.', 'danger')
                else:
                    flash('Usuario o contraseña incorrectos.', 'danger')
                current_app.logger.warning(f"SEGURIDAD: Intento fallido de login: {username}")
                return redirect(url_for('auth.login'))
        except Exception as e:
            current_app.logger.error(f"Error inesperado en login: {e}")
            flash("Ocurrió un error inesperado. Por favor, intente de nuevo.", 'danger')
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
    Muestra el perfil del usuario con información detallada y permite cambiar la contraseña.
    """
    usuario_service = current_app.config.get('USUARIO_SERVICE')
    legajo_service = current_app.config.get('LEGAJO_SERVICE')
    
    # Obtener datos adicionales del usuario
    user_data = {
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'rol': current_user.rol if hasattr(current_user, 'rol') else None,
        'estado': current_user.estado if hasattr(current_user, 'estado') else 'activo',
        'personal_info': None,
        'fecha_registro': current_user.fecha_registro if hasattr(current_user, 'fecha_registro') else None,
    }
    
    # Obtener información del personal asociado si existe
    try:
        if legajo_service and hasattr(current_user, 'personal_id'):
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
        # Verificar si es carga de foto de carnet
        if 'foto_carnet' in request.files:
            archivo = request.files['foto_carnet']
            
            if archivo and archivo.filename != '':
                # Validar archivo usando FileValidationService
                is_valid, error_message = FileValidationService.validate_file(
                    archivo, 
                    allowed_types=['jpg', 'jpeg', 'png']
                )
                
                if not is_valid:
                    current_app.logger.warning(f"SEGURIDAD: Intento de subir foto de carnet inválida - {current_user.username}")
                    flash(error_message or 'Tipo de archivo no permitido. Solo JPG, JPEG o PNG.', 'danger')
                    return redirect(url_for('auth.perfil'))
                
                try:
                    # Usar directorio de fotos de perfil desde config
                    fotos_dir = current_app.config.get('FOTOS_PERFIL_DIR')
                    
                    if not fotos_dir:
                        # Fallback en caso de que no esté configurado
                        fotos_dir = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            'presentation',
                            'static',
                            'uploads',
                            'fotos'
                        )
                        os.makedirs(fotos_dir,exist_ok=True)
                    
                    # Procesar imagen con PIL
                    from PIL import Image
                    import io
                    import time
                    
                    # Leer la imagen
                    imagen = Image.open(archivo.stream)
                    
                    # Convertir RGBA a RGB si es necesario
                    if imagen.mode in ('RGBA', 'LA', 'P'):
                        rgb_imagen = Image.new('RGB', imagen.size, (255, 255, 255))
                        if imagen.mode == 'P':
                            imagen = imagen.convert('RGBA')
                        rgb_imagen.paste(imagen, mask=imagen.split()[-1] if imagen.mode == 'RGBA' else None)
                        imagen = rgb_imagen
                    
                    # Redimensionar a 800x800 manteniendo proporción
                    max_size = (800, 800)
                    imagen.thumbnail(max_size, Image.Resampling.LANCZOS)
                    
                    # Crear nueva imagen cuadrada con fondo blanco
                    new_img = Image.new('RGB', (800, 800), (255, 255, 255))
                    # Centrar la imagen redimensionada
                    offset = ((800 - imagen.width) // 2, (800 - imagen.height) // 2)
                    new_img.paste(imagen, offset)
                    
                    # Guardar como JPG con nombre único
                    filename = f"foto_{current_user.id}_{int(time.time())}.jpg"
                    filepath = os.path.join(fotos_dir, filename)
                    
                    # Guardar con calidad optimizada
                    new_img.save(filepath, 'JPEG', quality=85, optimize=True)
                    
                    # Actualizar el campo foto_perfil del usuario en la base de datos
                    if usuario_service:
                        usuario_service.update_foto_perfil(current_user.id, filename)
                    
                    # Registrar en bitácora
                    audit_service = current_app.config.get('AUDIT_SERVICE')
                    if audit_service:
                        audit_service.log(
                            current_user.id,
                            'Usuario',
                            'ACTUALIZAR_FOTO',
                            f"Usuario {current_user.username} actualizó su foto de perfil"
                        )
                    
                    current_app.logger.info(f"AUDITORÍA: Usuario {current_user.username} subió foto de perfil a {fotos_dir}")
                    flash('¡Foto de perfil actualizada y optimizada correctamente!', 'success')
                    
                except Exception as e:
                    current_app.logger.error(f"Error al guardar foto de perfil: {str(e)}")
                    flash('Ocurrió un error al guardar la foto.', 'danger')
                
                return redirect(url_for('auth.perfil'))
        
        # Manejo de cambio de contraseña (existente)
        password_actual = request.form.get('password_actual')
        password_nueva = request.form.get('password_nueva')
        password_confirmacion = request.form.get('password_confirmacion')

        # Validaciones básicas
        if password_actual and password_nueva and password_confirmacion:
            if password_nueva != password_confirmacion:
                flash('Las nuevas contraseñas no coinciden.', 'danger')
                return redirect(url_for('auth.perfil'))
            
            if len(password_nueva) < 8:
                flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
                return redirect(url_for('auth.perfil'))

            # Verificar contraseña actual
            if not current_user.check_password(password_actual):
                flash('La contraseña actual es incorrecta.', 'danger')
                return redirect(url_for('auth.perfil'))

            try:
                # Actualizar contraseña usando el servicio
                if usuario_service:
                    usuario_service.update_password(current_user.id, password_nueva) 
                else:
                    from werkzeug.security import generate_password_hash
                    current_user.password_hash = generate_password_hash(password_nueva)
                    from app import db
                    db.session.commit()

                flash('¡Contraseña actualizada correctamente!', 'success')
            except Exception as e:
                current_app.logger.error(f"Error al cambiar password: {str(e)}")
                flash('Ocurrió un error al actualizar la contraseña.', 'danger')

    return render_template('auth/perfil.html', user=current_user, user_data=user_data)