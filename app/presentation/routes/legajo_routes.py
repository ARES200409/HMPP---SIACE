# RUTA: app/presentation/routes/legajo_routes.py
# RUTA: app/presentation/routes/legajo_routes.py

import io
import mimetypes
import os
import pyodbc
from flask import Blueprint, jsonify, render_template, redirect, send_file, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.decorators import role_required
from app.application.forms import PersonalForm, DocumentoForm, FiltroPersonalForm, BulkUploadForm, ContratoInicialForm
from app.application.services.file_validation_service import FileValidationService
from app.domain.models.personal import Personal
from app.domain.models.usuario import Usuario
from app.core.security import IDORProtection
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from app.database import get_db_read


legajo_bp = Blueprint('legajo', __name__, url_prefix='/legajo')


# --- CLASE AUXILIAR PARA PAGINACIÓN (Sincronizada con el HTML) ---
class RecordPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = (total + per_page - 1) // per_page
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1

    def iter_pages(self, left_edge=1, left_current=2, right_current=2, right_edge=1):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and num < self.page + right_current + 1) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num

@legajo_bp.route('/personal/carga_masiva', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def carga_masiva_personal():
    form = BulkUploadForm()
    if form.validate_on_submit():
        file_storage = form.excel_file.data
        try:
            legajo_service = current_app.config['LEGAJO_SERVICE']
            resultado = legajo_service.process_bulk_upload(file_storage, current_user.id)
            
            flash(f"Proceso de carga masiva completado. Registros exitosos: {resultado['exitosos']}", 'success')
            if resultado['fallidos'] > 0:
                # Si hubo errores, se muestran en un mensaje separado.
                errores_str = "; ".join(resultado['errores'])
                flash(f"Registros fallidos: {resultado['fallidos']}. Detalles: {errores_str}", 'danger')

            return redirect(url_for('legajo.listar_personal'))
        except Exception as e:
            from app.utils.error_handler import registrar_error_automatico
            registrar_error_automatico(e)
            current_app.logger.error(f"Error crítico en carga masiva: {e}")
            flash(f"Ocurrió un error inesperado al procesar el archivo: {e}", 'danger')

    return render_template('admin/carga_masiva.html', form=form)

@legajo_bp.route('/personal/plantilla_carga_masiva')
@login_required
@role_required('AdministradorLegajos')
def descargar_plantilla_carga_masiva():
    legajo_service = current_app.config['LEGAJO_SERVICE']
    # Se obtienen las unidades para las validaciones de datos en Excel.
    unidades = legajo_service.get_unidades_for_select()
    
    excel_stream = legajo_service.generate_bulk_upload_template(unidades)
    
    return send_file(
        excel_stream,
        download_name="plantilla_carga_masiva_personal.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

from app.infrastructure.persistence.planilla_repository import PlanillaRepository
@legajo_bp.route('/seguridad/rotar_clave', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'Sistemas') # Solo sistemas puede tocar esto
def rotar_clave_seguridad():
    repo = PlanillaRepository() # Importar repositorio si hace falta
    nueva_clave = repo.generar_nueva_clave_dinamica()
    if nueva_clave:
        flash(f'Clave de seguridad actualizada: {nueva_clave}', 'success')
    else:
        flash('Error al generar clave.', 'danger')
    return redirect(url_for('legajo.gestionar_token')) # Vuelve al inicio


@legajo_bp.route('/seguridad/token')
@login_required
@role_required('AdministradorLegajos', 'Sistemas') # Ajustado a tus roles actuales
def gestionar_token():
    """
    Ruta para la pantalla de gestión del Token Dinámico.
    Permite visualizar la clave actual antes de decidir rotarla.
    """
    try:
        # 1. Instanciamos el repositorio para conectar con la BD
        repo = PlanillaRepository()
        
        # 2. Obtenemos la clave dinámica activa de la tabla configuracion_seguridad
        # Esto evita que se visualice como '--- ---' en la interfaz
        clave = repo.obtener_clave_dinamica()
        
        # 3. Renderizamos la plantilla dedicada a la gestión del token
        # La ubicamos en la carpeta 'admin' para seguir tu estructura de archivos
        return render_template('admin/gestionar_token.html', clave_actual=clave)
        
    except Exception as e:
        # En caso de error, lo registramos en la bitácora que acabas de conectar
        print(f"Error al cargar gestión de token: {e}")
        flash('No se pudo cargar la información de seguridad.', 'danger')
        return redirect(url_for('legajo.dashboard'))



@legajo_bp.route('/api/tipos_documento/por_seccion/<int:id_seccion>')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas')
def api_tipos_documento_por_seccion(id_seccion):
    """
    API endpoint para obtener los tipos de documento filtrados por sección.
    """
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        tipos = legajo_service.get_tipos_documento_by_seccion(id_seccion)
        return jsonify(tipos)
    except Exception as e:
        current_app.logger.error(f"Error en API de tipos de documento: {e}")
        return jsonify({"error": "No se pudieron cargar los datos"}), 500


# --- API para obtener todas las secciones ---
@legajo_bp.route('/api/secciones', methods=['GET'])
@login_required
def get_secciones():
    legajo_service = current_app.config['LEGAJO_SERVICE']
    secciones = legajo_service.get_secciones_for_select()
    # Formatea la respuesta para que sea fácil de consumir por JavaScript
    return jsonify([{'id': id, 'nombre': nombre} for id, nombre in secciones])

# --- NUEVA RUTA API para obtener tipos de documento por sección ---
@legajo_bp.route('/api/tipos_documento/por_seccion/<int:seccion_id>', methods=['GET'])
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas') # Ajusta los roles si es necesario
def get_tipos_documento_by_seccion(seccion_id):
    legajo_service = current_app.config['LEGAJO_SERVICE']
    tipos_documento = legajo_service.get_tipos_documento_by_seccion(seccion_id)
    # Formatea la respuesta para que sea fácil de consumir por JavaScript
    return jsonify([{'id': id, 'nombre': nombre} for id, nombre in tipos_documento])

@legajo_bp.route('/documentos/buscar')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas')
def buscar_documentos():
    """
    Buscador de documentos que permite filtrar por texto, sección o tipo de documento.
    """
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    # Obtener parámetros de búsqueda
    query = request.args.get('q', '').strip()
    id_seccion = request.args.get('seccion', '0')
    id_tipo = request.args.get('tipo', '0')
    
    # Realizar búsqueda si hay filtros aplicados
    documentos = []
    if query or (id_seccion and id_seccion != '0') or (id_tipo and id_tipo != '0'):
        documentos = legajo_service.search_documents(query, id_seccion, id_tipo)
    
    # Obtener listas para los filtros
    secciones = legajo_service.get_secciones_for_select()
    tipos_documento = legajo_service.get_tipos_documento_for_select()
    
    return render_template(
        'admin/buscar_documentos.html',
        documentos=documentos,
        secciones=secciones,
        tipos_documento=tipos_documento,
        query=query,
        id_seccion=id_seccion,
        id_tipo=id_tipo
    )

@legajo_bp.route('/dashboard')
@login_required
@role_required('AdministradorLegajos', 'RRHH')
def dashboard():
    """
    Panel principal de Escalafón/Administración.
    Carga los datos del usuario y el token de seguridad activo.
    """
    # 1. Instanciamos el repositorio para obtener el token de la BD
    repo = PlanillaRepository()
    
    # 2. Consultamos la clave dinámica actual
    # Esto es vital para que la tarjeta de "Seguridad de Planillas" muestre el código real
    clave = repo.obtener_clave_dinamica()
    
    # 3. Renderizamos el template en la carpeta 'admin'
    # Usamos 'nombre_usuario' que es la columna real detectada en SQL
    return render_template(
        'admin/dashboard.html', 
        username=current_user.username, 
        clave_actual=clave
    )

@legajo_bp.route('/personal/<int:personal_id>')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas')
def ver_legajo(personal_id):
    try:
        # ✅ SEGURIDAD: Verificar permisos IDOR
        if not IDORProtection.can_access_personal(current_user.id, personal_id, current_user.rol):
            current_app.logger.warning(f"SEGURIDAD: Intento IDOR detectado - Usuario {current_user.username} intentó acceder a personal_id {personal_id}")
            flash('No tienes permiso para acceder a este legajo.', 'danger')
            return redirect(url_for('legajo.listar_personal'))
        
        legajo_service = current_app.config['LEGAJO_SERVICE']
        # Seguridad: Pasar el usuario actual al servicio para la validación de permisos (IDOR).
        legajo_completo = legajo_service.get_personal_details(personal_id, current_user)
    except PermissionError as e:
        # Seguridad: Capturar el error de permiso y mostrar un mensaje claro.
        flash(str(e), 'danger')
        return redirect(url_for('legajo.listar_personal'))
    except Exception as e:
        current_app.logger.error(f"Error inesperado al ver legajo {personal_id}: {e}")
        flash("Ocurrió un error al cargar el legajo.", "danger")
        return redirect(url_for('legajo.listar_personal'))
    
    if not legajo_completo or not legajo_completo.get('personal'):
        flash('El legajo solicitado no existe.', 'danger')
        return redirect(url_for('legajo.listar_personal'))
        
    form_documento = DocumentoForm()
    # Se asegura de que la lista de opciones no esté vacía antes de añadir
    secciones = legajo_service.get_secciones_for_select()
    if secciones:
        form_documento.id_seccion.choices = [('0', '-- Seleccione Sección --')] + secciones
    else:
        form_documento.id_seccion.choices = [('0', 'No hay secciones disponibles')]

    form_documento.id_tipo.choices = [('0', '-- Seleccione Tipo --')]
    
    return render_template(
        'admin/ver_legajo_completo.html', 
        legajo=legajo_completo, 
        form_documento=form_documento,
        legajo_service=legajo_service,
        today=datetime.now().date()
    )


@legajo_bp.route('/personal')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas')
def listar_personal():
    form = FiltroPersonalForm(request.args)
    page = request.args.get('page', 1, type=int)
    filters = {'dni': form.dni.data, 'nombres': form.nombres.data}
    
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    try:
        pagination = legajo_service.get_all_personal_paginated(page, 15, filters)
        document_status = legajo_service.check_document_status_for_all_personal()
        
        # 🚀 RETORNO SEGURO
        return render_template('admin/listar_personal.html', 
                               form=form, 
                               pagination=pagination,
                               document_status=document_status)

    except Exception as e:
        # Registramos el error pero NO redirigimos para no crear el bucle
        current_app.logger.error(f"Error en listar_personal: {str(e)}")
        # Devolvemos un mensaje de error directo en lugar de un redirect
        return f"Error crítico de renderizado: {str(e)}. Revisa los argumentos 'page' en el HTML.", 500

@legajo_bp.route('/personal/nuevo', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def crear_personal():
    form = PersonalForm()
    legajo_service = current_app.config['LEGAJO_SERVICE']
    form.id_unidad.choices = [('0', '-- Seleccione Unidad --')] + legajo_service.get_unidades_for_select()
    
    if form.validate_on_submit():
        try:
            # 1. Crear Personal y Usuario
            new_personal_id = legajo_service.register_new_personal(form.data, current_user.id)
            
            flash('Paso 1 completado: Datos personales registrados.', 'success')
            
            # 🚀 CAMBIO: Ya no va al 'completar_legajo'. 
            # Ahora regresa a la lista con un aviso de "Pendiente de Contrato".
            flash('Legajo registrado exitosamente. Ahora RRHH debe asignar el contrato inicial.', 'success')
            return redirect(url_for('legajo.listar_personal'))
            
        except Exception as e:
            # ... (manejo de errores igual que antes) ...
            current_app.logger.error(f"Error: {e}")
            flash('Error al crear personal.', 'danger')
            
    return render_template('admin/crear_personal.html', form=form, titulo="Nuevo Legajo - Paso 1: Datos Personales")

# app/presentation/routes/legajo_routes.py
# ... (imports existentes) ...
from app.domain.models.usuario import Usuario, ROL_ID_PERSONAL

@legajo_bp.route('/personal/completar/<int:personal_id>', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def completar_legajo(personal_id):
    legajo_service = current_app.config['LEGAJO_SERVICE']
    repo = legajo_service._personal_repo 
    
    persona = repo.find_by_id(personal_id)
    if not persona:
        flash('Error: El personal no existe.', 'danger')
        return redirect(url_for('legajo.listar_personal'))

    form = ContratoInicialForm()
    # Carga de catálogos
    form.id_tipo_contrato.choices = [('', '-- Seleccione Tipo --')] + repo.get_tipos_contrato_for_select()
    form.id_cargo.choices = [('', '-- Seleccione Cargo --')] + repo.get_cargos_for_select()
    form.id_unidad.choices = [('', '-- Seleccione Unidad --')] + repo.get_unidades_for_select()

    # 🚀 AUTOMATIZACIÓN: Pre-seleccionar la unidad de la persona (Paso 1)
    if request.method == 'GET':
        form.id_unidad.data = str(persona.id_unidad) # Esto quita la molestia de elegir de nuevo

    if form.validate_on_submit():
        try:
            # 1. Registrar contrato y cargo
            data = form.data
            data['id_personal'] = personal_id
            
            # 🚀 IMPORTANTE: Sincronizamos el nombre de la resolución
            data['resolucion'] = data.get('numero_resolucion') 
            
            repo.registrar_contrato_inicial(data)
            
            # 2. Creación de Acceso Automático
            dni_empleado = persona.dni.strip()
            usuario_existente = legajo_service.get_usuario_por_username(dni_empleado)
            
            if not usuario_existente:
                from werkzeug.security import generate_password_hash
                # Asumimos que ROL_ID_PERSONAL está definido como 5
                nuevo_acceso = Usuario(
                    id_usuario=None,
                    username=dni_empleado,
                    id_rol=5, 
                    email=persona.email,
                    password_hash=generate_password_hash(dni_empleado),
                    id_personal=personal_id,
                    activo=True,
                    nombre_rol='Personal'
                )
                legajo_service.crear_usuario_acceso(nuevo_acceso)
            
            flash('¡Legajo y contrato activados exitosamente!', 'success')
            return redirect(url_for('legajo.ver_legajo', personal_id=personal_id))
            
        except Exception as e:
            current_app.logger.error(f"Error crítico en Paso 2: {str(e)}")
            flash(f'Error al procesar: {str(e)}', 'danger')

    return render_template('admin/completar_legajo.html', form=form, persona=persona)


@legajo_bp.route('/personal/confirmacion/<int:personal_id>')
@login_required
@role_required('AdministradorLegajos')
def confirmacion_personal_creado(personal_id):
    """Muestra los datos del usuario creado automáticamente."""
    from flask import session
    
    # Obtener datos de la sesión
    nuevo_usuario = session.pop('nuevo_usuario', None)
    
    if not nuevo_usuario:
        flash('No hay datos de usuario para mostrar.', 'warning')
        return redirect(url_for('legajo.listar_personal'))
    
    legajo_service = current_app.config['LEGAJO_SERVICE']
    try:
        persona = legajo_service._personal_repo.find_by_id(personal_id)
        if not persona:
            flash('Personal no encontrado.', 'danger')
            return redirect(url_for('legajo.listar_personal'))
    except Exception as e:
        current_app.logger.error(f"Error al obtener datos del personal: {e}")
        flash('Error al cargar los datos del personal.', 'danger')
        return redirect(url_for('legajo.listar_personal'))
    
    return render_template(
        'admin/confirmacion_usuario_creado.html',
        persona=persona,
        usuario_info=nuevo_usuario
    )


@legajo_bp.route('/personal/<int:personal_id>/documento/subir', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def subir_documento(personal_id):
    form = DocumentoForm()
    legajo_service = current_app.config['LEGAJO_SERVICE']
    form.id_seccion.choices = [('0', '-- Seleccione Sección --')] + legajo_service.get_secciones_for_select()
    form.id_tipo.choices = [('0', '-- Seleccione Tipo --')] + legajo_service.get_tipos_documento_for_select()
    
    if form.validate_on_submit():
        try:
            # ✅ SEGURIDAD: Validar archivo antes de procesarlo
            archivo = form.archivo.data
            is_valid, error_message = FileValidationService.validate_file(archivo)
            if not is_valid:
                from app.utils.error_handler import registrar_error_automatico
                try:
                    raise ValueError(f"BLOQUEO DE SEGURIDAD: Intento de subir {archivo.filename} (Tipo no permitido)")
                except ValueError as ve:
                    registrar_error_automatico(ve)
                    current_app.logger.warning(f"SEGURIDAD: Intento de subir archivo inválido - {archivo.filename} - Error: {error_message} - Usuario: {current_user.username}")
                flash(error_message or 'El archivo no es válido o contiene código malicioso.', 'danger')
                return redirect(url_for('legajo.ver_legajo', personal_id=personal_id))
            
            form_data = form.data
            form_data['id_personal'] = personal_id
            legajo_service.upload_document_to_personal(form_data, archivo, current_user.id)
            flash('Documento subido correctamente.', 'success')
        except ValueError as ve:
            # Captura errores de validación específicos del servicio (ej. tamaño de archivo)
            current_app.logger.warning(f"Error de validación al subir documento para personal {personal_id}: {ve}")
            flash(str(ve), 'danger')
        except Exception as e:
            from app.utils.error_handler import registrar_error_automatico
            registrar_error_automatico(e)
            current_app.logger.error(f"Error inesperado al subir documento para personal {personal_id}: {e}")
            flash(f'Ocurrió un error inesperado al subir el documento.', 'danger')
    else:
        # Si la validación del formulario falla, registra el error y flashea los mensajes.
        error_str = "; ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
        current_app.logger.warning(f"Fallo de validación al subir documento para personal {personal_id}: {error_str}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en el campo '{getattr(form, field).label.text}': {error}", 'danger')
                break # Muestra solo el primer error por campo para no saturar
    return redirect(url_for('legajo.ver_legajo', personal_id=personal_id))



@legajo_bp.route('/personal/<int:personal_id>/eliminar', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def eliminar_personal(personal_id):
    legajo_service = current_app.config['LEGAJO_SERVICE']
    try:
        # CORRECCIÓN: Usamos la función BLINDADA que sincroniza con Sistemas
        # Enviamos 'Inactivo' para que el sistema ponga al usuario en ROJO (0)
        success, msg = legajo_service.cambiar_estado_personal(personal_id, 'Inactivo')
        
        if success:
            flash('El legajo ha sido desactivado y el acceso al sistema bloqueado.', 'success')
        else:
            flash(f'Advertencia: {msg}', 'warning')

    except Exception as e:
        current_app.logger.error(f"Error al eliminar legajo {personal_id}: {e}")
        flash(f'Ocurrió un error al desactivar el legajo: {e}', 'danger')
        
    return redirect(url_for('legajo.listar_personal'))

@legajo_bp.route('/personal/<int:personal_id>/reactivar', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def reactivar_personal(personal_id):
    legajo_service = current_app.config['LEGAJO_SERVICE']
    try:
        # CORRECCIÓN CRÍTICA: Usamos la misma función BLINDADA
        # Enviamos 'Activo' para que el sistema detecte la palabra clave y ponga al usuario en VERDE (1)
        success, msg = legajo_service.cambiar_estado_personal(personal_id, 'Activo')
        
        if success:
            flash('El legajo ha sido reactivado y el acceso al sistema habilitado.', 'success')
        else:
            flash(f'Advertencia: {msg}', 'warning')

    except Exception as e:
        current_app.logger.error(f"Error al reactivar legajo {personal_id}: {e}")
        flash(f'Ocurrió un error al reactivar el legajo: {e}', 'danger')
        
    return redirect(url_for('legajo.listar_personal'))



@legajo_bp.route('/personal/<int:personal_id>/editar', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos')
def editar_personal(personal_id):
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    # 1. Obtener datos actuales del personal
    legajo_data = legajo_service.get_personal_details(personal_id, current_user)
    if not legajo_data or not legajo_data.get('personal'):
        flash('El legajo que intenta editar no existe.', 'danger')
        return redirect(url_for('legajo.listar_personal'))

    persona_data = legajo_data['personal']

    form = PersonalForm(data=persona_data)
    form.id_unidad.choices = [('0', '-- Seleccione Unidad --')] + legajo_service.get_unidades_for_select()
    
    if request.method == 'GET':
        form.id_unidad.data = str(persona_data.get('id_unidad', '0'))

    if form.validate_on_submit():
        try:
            nuevo_dni = form.dni.data
            
            # 🚀 VALIDACIÓN CRÍTICA: ¿El DNI ya lo tiene otro trabajador?
            # Usamos el nuevo método del repositorio que ignora el ID actual
            if legajo_service._personal_repo.existe_dni_en_otros(nuevo_dni, personal_id):
                flash(f'¡BLOQUEO DE INTEGRIDAD! El DNI {nuevo_dni} ya está registrado a nombre de otro trabajador.', 'danger')
                return render_template('admin/editar_personal.html', form=form, persona=persona_data, titulo="Editar Legajo")

            # 2. Si pasa la validación, procedemos a actualizar
            legajo_service.update_personal_details(personal_id, form.data, current_user.id)
            
            flash('Legajo actualizado correctamente en la base de datos.', 'success')
            return redirect(url_for('legajo.ver_legajo', personal_id=personal_id))
            
        except Exception as e:
            # 🚀 REGISTRO AUTOMÁTICO: Para que aparezca en tu tabla de errores
            from app.utils.error_handler import registrar_error_automatico
            registrar_error_automatico(e)
            
            current_app.logger.error(f"Error al actualizar legajo {personal_id}: {e}")
            flash(f'Error técnico detectado: {str(e)}', 'danger')
    
    # Manejo de errores de validación del formulario (ej. campos vacíos)
    if request.method == 'POST' and not form.validate_on_submit():
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Campo '{getattr(form, field).label.text}': {error}", 'warning')
            
    return render_template('admin/editar_personal.html', form=form, persona=persona_data, titulo="Editar Legajo")



@legajo_bp.route('/documento/<int:documento_id>/ver')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas', 'Personal') # <--- AGREGADO 'Personal'
def ver_documento(documento_id):
    """
    Gestiona la solicitud para ver un archivo (Descarga/Vista previa).
    """
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    # --- NUEVA VALIDACIÓN DE SEGURIDAD ---
    if not legajo_service.verify_document_access(documento_id, current_user):
        flash('No tiene permiso para acceder a este documento.', 'danger')
        return redirect(url_for('personal.inicio') if current_user.rol == 'Personal' else url_for('main_dashboard'))
    # -------------------------------------

    try:
        document = legajo_service.get_document_for_download(documento_id)
        
        if not document or not document.get('data'):
            flash('El documento no fue encontrado.', 'danger')
            return redirect(request.referrer or url_for('index'))

        return send_file(
            io.BytesIO(document['data']),
            as_attachment=False,
            download_name=document['filename']
        )
    except Exception as e:
        current_app.logger.error(f"Error al visualizar documento {documento_id}: {e}")
        flash('Ocurrió un error al intentar mostrar el archivo.', 'danger')
        return redirect(request.referrer or url_for('index'))
    

@legajo_bp.route('/documento/<int:documento_id>/eliminar', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def eliminar_documento(documento_id):
    """
    Gestiona la solicitud de eliminación (lógica) de un documento.
    """
    # --- INICIO DEL CÓDIGO DE SEGUIMIENTO ---
    print(f"DEBUG: Iniciando eliminación para el documento ID: {documento_id}")
    # --- FIN DEL CÓDIGO DE SEGUIMIENTO ---
    
    legajo_service = current_app.config['LEGAJO_SERVICE']
    try:
        legajo_service.delete_document_by_id(documento_id, current_user.id)
        
        flash('Documento eliminado correctamente.', 'success')

    except Exception as e:
        current_app.logger.error(f"Error al eliminar documento {documento_id}: {e}")
    
    # Redirige al usuario a la página anterior
    print("DEBUG: Redirigiendo al usuario.")
    return redirect(request.referrer or url_for('index'))


@legajo_bp.route('/documento/<int:documento_id>/visualizar')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas', 'Personal') # <--- AGREGADO 'Personal'
def visualizar_documento(documento_id):
    """
    Visualización en línea inteligente (PDF/Imágenes en navegador, otros descarga).
    """
    legajo_service = current_app.config['LEGAJO_SERVICE']

    # --- NUEVA VALIDACIÓN DE SEGURIDAD ---
    if not legajo_service.verify_document_access(documento_id, current_user):
        flash('No tiene permiso para acceder a este documento.', 'danger')
        return redirect(url_for('personal.inicio') if current_user.rol == 'Personal' else url_for('main_dashboard'))
    # -------------------------------------

    try:
        document = legajo_service.get_document_for_download(documento_id)
        
        if not document or not document.get('data'):
            flash('El documento no fue encontrado.', 'danger')
            return redirect(request.referrer or url_for('index'))

        mimetype, _ = mimetypes.guess_type(document['filename'])
        if not mimetype:
            mimetype = 'application/octet-stream'

        SAFE_INLINE_MIMETYPES = [
            'application/pdf', 'image/jpeg', 'image/png', 
            'image/gif', 'image/webp', 'text/plain'
        ]

        should_be_attachment = mimetype not in SAFE_INLINE_MIMETYPES

        return send_file(
            io.BytesIO(document['data']),
            mimetype=mimetype,
            as_attachment=should_be_attachment,
            download_name=document['filename']
        )
    except Exception as e:
        current_app.logger.error(f"Error al visualizar documento {documento_id}: {e}")
        flash('Error visualizando archivo.', 'danger')
        return redirect(request.referrer or url_for('index'))    


@legajo_bp.route('/api/personal/check_dni/<string:dni>')
@login_required
def check_dni(dni):
    """
    API endpoint para verificar si un DNI ya existe.
    """
    legajo_service = current_app.config['LEGAJO_SERVICE']
    exists = legajo_service.check_if_dni_exists(dni)
    return jsonify({'exists': exists})


@legajo_bp.route('/personal/exportar/general')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas')
def exportar_lista_general_excel():
    """
    Genera y descarga un archivo Excel con el reporte general de todo el personal.
    """
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        
        # Llama al método existente que genera el reporte en memoria
        excel_stream = legajo_service.generate_general_report_excel()
        
        # Registrar en auditoría
        audit_service = current_app.config['AUDIT_SERVICE']
        audit_service.log(current_user.id, 'Reportes', 'EXPORTAR_GENERAL_EXCEL', "Exportó el reporte general de personal a Excel.")

        # Enviar el archivo al usuario
        return send_file(
            excel_stream,
            as_attachment=True,
            download_name='Reporte_General_Personal.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        current_app.logger.error(f"Error al exportar el reporte general a Excel: {e}")
        flash('Ocurrió un error al generar el reporte de Excel.', 'danger')
        return redirect(url_for('legajo.listar_personal'))
    
# ... imports existentes (asegúrate de tener 'os' y 'send_file') ...
import os 

# --- RUTAS DE GESTIÓN DE SOLICITUDES (AdministradorLegajos) ---

@legajo_bp.route('/solicitudes/documentos', methods=['GET'])
@login_required
@role_required('AdministradorLegajos')
def gestionar_solicitudes():
    """Bandeja de entrada de solicitudes para el Administrador de Legajos."""
    try:
        solicitud_service = current_app.config.get('SOLICITUDES_SERVICE')
        solicitudes = solicitud_service.get_all_pending()
        # Renderiza la plantilla ubicada en la carpeta 'admin'
        return render_template('admin/gestion_solicitudes.html', solicitudes=solicitudes)
    except Exception as e:
        current_app.logger.error(f"Error listando solicitudes: {e}")
        flash('Error al cargar las solicitudes pendientes.', 'danger')
        return redirect(url_for('legajo.dashboard'))

@legajo_bp.route('/solicitudes/procesar/<int:solicitud_id>/<accion>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def procesar_solicitud(solicitud_id, accion):
    """
    Procesa la aprobación o rechazo de una solicitud.
    Accion: 'aprobar' | 'rechazar'
    """
    try:
        solicitud_service = current_app.config.get('SOLICITUDES_SERVICE')
        audit_service = current_app.config['AUDIT_SERVICE']

        if accion not in ['aprobar', 'rechazar']:
            flash('Acción no válida.', 'warning')
            return redirect(url_for('legajo.gestionar_solicitudes'))

        resultado = solicitud_service.process_request(solicitud_id, accion)

        if resultado:
            msg = 'Documento actualizado correctamente.' if accion == 'aprobar' else 'Solicitud rechazada.'
            flash(msg, 'success')

            try:
                audit_service = current_app.config['AUDIT_SERVICE']
                audit_service.log(
                    current_user.id, 
                    'AdminLegajos', 
                    f'{accion.upper()}_SOLICITUD_CAMBIO', 
                    f"Procesó solicitud ID {solicitud_id}"
                )
            except:
                pass
        else:
            flash('No se pudo completar la operación en la base de datos.', 'danger')

        return redirect(url_for('legajo.gestionar_solicitudes'))

    except Exception as e:
        current_app.logger.error(f"Error procesando solicitud {solicitud_id}: {e}")
        flash('Ocurrió un error interno.', 'danger')
        return redirect(url_for('legajo.gestionar_solicitudes'))

@legajo_bp.route('/solicitudes/ver-nuevo/<int:solicitud_id>', methods=['GET'])
@login_required
@role_required('AdministradorLegajos')
def ver_archivo_propuesto(solicitud_id):
    """Permite visualizar el archivo temporal subido por el empleado."""
    try:
        solicitud_service = current_app.config.get('SOLICITUDES_SERVICE')
        # Usamos el método del repositorio directamente o a través del servicio si lo expusiste
        solicitud = solicitud_service.solicitud_repo.get_by_id(solicitud_id)
        
        if not solicitud or not solicitud.get('ruta_nuevo_archivo'):
            flash('El archivo temporal no se encuentra.', 'warning')
            return redirect(url_for('legajo.gestionar_solicitudes'))
            
        # Construye la ruta absoluta al archivo temporal
        # Nota: 'ruta_nuevo_archivo' ya viene como 'uploads/temp_requests/archivo.pdf'
        ruta_abs = os.path.join(current_app.root_path, 'presentation/static', solicitud['ruta_nuevo_archivo'])
        
        return send_file(ruta_abs, as_attachment=False)
    except Exception as e:
        current_app.logger.error(f"Error visualizando archivo propuesto: {e}")
        return "Error al visualizar archivo", 404
    


# --- 🚀 RUTA CORREGIDA: CONSULTA DE RÉCORD (MODO LECTURA) ---

@legajo_bp.route('/personal/consultar-record', methods=['GET'])
@login_required
@role_required('AdministradorLegajos')
def listar_personal_para_record():
    """
    Lista el personal con Cargo, Sueldo y Contrato para el Administrador de Escalafón.
    """
    form = FiltroPersonalForm(request.args)
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    legajo_service = current_app.config['LEGAJO_SERVICE']
    repo = legajo_service._personal_repo 
    
    try:
        # 1. Llamamos a la función que trae los datos completos (Sueldo, Cargo, Contrato)
        # 🚀 Esto elimina el 'S/N' y los campos vacíos
        items, total = repo.get_personal_para_escalafon(
            page=page, 
            per_page=per_page, 
            dni=form.dni.data, 
            nombres=form.nombres.data
        )
        
        # 2. Creamos el objeto de paginación corregido
        pagination = RecordPagination(items, page, per_page, total)
        
        # 3. Renderizamos la plantilla de Escalafón
        return render_template('admin/listar_record_escalafon.html',
                               form=form, 
                               pagination=pagination)

    except Exception as e:
        from app.utils.error_handler import registrar_error_automatico
        registrar_error_automatico(e)
        current_app.logger.error(f"Error en consulta de record escalafon: {str(e)}")
        flash(f"Error al cargar los datos: {str(e)}", "danger")
        return redirect(url_for('legajo.dashboard'))


@legajo_bp.route('/record-laboral/descargar/<int:id_record>')
@login_required
@role_required('AdministradorLegajos', 'RRHH') # <--- Ambos pueden descargar
def download_record(id_record):
    """
    Permite al Escalafón descargar las planillas cargadas por RRHH.
    """
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        # Recuperamos el binario desde la tabla record_laboral
        document = legajo_service._personal_repo.get_record_file_by_id(id_record)
        
        if not document:
            flash('La boleta de pago no existe.', 'danger')
            return redirect(request.referrer)

        return send_file(
            io.BytesIO(document['contenido']),
            as_attachment=True,
            download_name=document['nombre_archivo'],
            mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Error descargando record {id_record}: {e}")
        flash("Error al procesar la descarga.", "danger")
        return redirect(request.referrer)
    

# --- RUTA PARA VISUALIZAR EXCLUSIVAMENTE EL RÉCORD LABORAL ---

# --- RUTAS DE RÉCORD LABORAL (VERSIÓN FINAL) ---

@legajo_bp.route('/personal/record-laboral/ver/<int:personal_id>')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas')
def ver_record_laboral_detalle(personal_id):
    """
    Carga la ficha de pagos. 
    FIX: Sincroniza la Unidad Administrativa para evitar el 'None'.
    """
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        legajo_completo = legajo_service.get_personal_details(personal_id, current_user)
        
        if not legajo_completo or not legajo_completo.get('personal'):
            flash('No se encontró el registro del trabajador.', 'danger')
            return redirect(url_for('legajo.listar_personal_para_record'))

        persona = legajo_completo['personal']
        
        # 🚀 PARCHE UNIVERSAL: Buscamos el nombre de la unidad en todos los alias posibles
        # Si el SQL devuelve 'unidad_administrativa', 'nombre_unidad' o 'unidad', lo capturamos.
        unidad_nombre = persona.get('nombre_unidad') or persona.get('unidad_administrativa') or persona.get('unidad')
        
        # Lo guardamos en la llave que usa el HTML
        persona['nombre_unidad'] = unidad_nombre if unidad_nombre else "No especificada"

        return render_template(
            'admin/ver_record_laboral_detalle.html',
            persona=persona,
            pagos=legajo_completo.get('record_laboral', [])
        )
    except Exception as e:
        current_app.logger.error(f"Error al cargar historial de pagos para {personal_id}: {e}")
        flash("Ocurrió un error al cargar el récord laboral.", "danger")
        return redirect(url_for('legajo.listar_personal_para_record'))

# --- GESTIÓN DE DOCUMENTOS Y DESCARGAS ---



@legajo_bp.route('/record-laboral/visualizar/<int:id_record>')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Personal')
def visualizar_boleta_record(id_record):
    """
    Detecta automáticamente si es PDF (visualiza) o Excel (descarga).
    """
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        document = legajo_service._personal_repo.get_record_file_by_id(id_record)
        
        if not document or not document.get('contenido'):
            flash('La boleta no fue encontrada en el servidor.', 'danger')
            return redirect(request.referrer)

        filename = document.get('nombre_archivo', 'archivo_boleta')
        # 🚀 DETECCIÓN DE TIPO: Usamos mimetypes para saber qué es el archivo
        mimetype, _ = mimetypes.guess_type(filename)
        if not mimetype:
            mimetype = 'application/octet-stream'

        # 🚀 LÓGICA DE DESCARGA: Solo visualizamos si es PDF; todo lo demás se descarga
        is_pdf = mimetype == 'application/pdf'
        
        return send_file(
            io.BytesIO(document['contenido']),
            mimetype=mimetype,
            as_attachment=not is_pdf, # Si NO es PDF, as_attachment será True (Descarga)
            download_name=filename
        )
    except Exception as e:
        current_app.logger.error(f"Error procesando boleta {id_record}: {e}")
        return "Error al procesar el archivo", 404
    


@legajo_bp.route('/api/personal/check_dni/<dni>', methods=['GET'])
@login_required
def check_dni_api(dni):
    """API que responde si un DNI ya existe en la municipalidad."""
    legajo_service = current_app.config['LEGAJO_SERVICE']
    # Usamos tu método existente del repositorio
    existe = legajo_service._personal_repo.check_dni_exists(dni)
    return jsonify({'exists': existe})

# ==============================================================================
# GESTIÓN DE SOLICITUDES ARCO (CANCELACIÓN DE DATOS) - CORREGIDO
# ==============================================================================

# 1. RUTA PARA VER LA BANDEJA DE SOLICITUDES
@legajo_bp.route('/solicitudes/arco', methods=['GET'])
@login_required
def gestionar_solicitudes_arco():
    # ✅ CORRECCIÓN 1: Agregamos 'AdministradorEscalafon' a la lista
    # (También incluimos 'AdministradorLegajos' por si acaso usas ese otro rol)
    roles_permitidos = ['Administrador', 'Sistemas', 'Legajos', 'RRHH', 'AdministradorLegajos', 'AdministradorEscalafon']

    if current_user.rol not in roles_permitidos:
        flash(f'Acceso denegado. Tu rol ({current_user.rol}) no tiene permisos.', 'danger')
        return redirect(url_for('auth.login'))

    conn = get_db_read()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            s.id_solicitud,
            s.fecha_solicitud,
            p.nombres + ' ' + p.apellidos as nombre_completo,
            p.dni,
            s.datos_afectados,
            s.motivo_solicitud
        FROM solicitudes_arco s
        INNER JOIN personal p ON s.id_personal = p.id_personal
        WHERE s.estado = 'PENDIENTE'
        ORDER BY s.fecha_solicitud DESC
    """
    cursor.execute(query)
    solicitudes = cursor.fetchall()
    #conn.close()

    # ✅ CORRECCIÓN 2: Ruta del Template
    # Asegúrate de que el archivo 'gestion_arco.html' esté DENTRO de la carpeta 'templates/admin'
    return render_template('admin/gestion_arco.html', solicitudes=solicitudes)


# 2. RUTA MÁGICA: ELIMINA LOS DATOS O RECHAZA
@legajo_bp.route('/procesar-arco/<int:id_solicitud>/<accion>', methods=['GET', 'POST'])
@login_required
def procesar_arco(id_solicitud, accion):
    # ✅ CORRECCIÓN 3: Agregamos 'AdministradorEscalafon' AQUÍ TAMBIÉN
    # Si no lo pones aquí, el botón de aprobar te dará error.
    roles_permitidos = ['Administrador', 'Sistemas', 'Legajos', 'RRHH', 'AdministradorLegajos', 'AdministradorEscalafon']

    if current_user.rol not in roles_permitidos:
        flash('No tienes permisos para ejecutar esta acción.', 'danger')
        return redirect(url_for('auth.login'))

    conn = get_db_read()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id_personal, datos_afectados FROM solicitudes_arco WHERE id_solicitud = ?", (id_solicitud,))
        row = cursor.fetchone()
        
        if not row:
            flash('Solicitud no encontrada.', 'warning')
            return redirect(url_for('legajo.gestionar_solicitudes_arco'))

        id_personal = row[0]
        datos_texto = row[1]

        if accion == 'APROBAR':
            mapa = {
                'Email Personal': 'email_personal',
                'Telefono': 'telefono',
                'Direccion': 'direccion',
                'Datos Sensibles': 'datos_sensibles'
            }

            lista_borrar = datos_texto.split(',')
            sets = []
            
            for item in lista_borrar:
                clave = item.strip()
                if clave in mapa:
                    columna = mapa[clave]
                    sets.append(f"{columna} = NULL")

            if sets:
                sql = f"UPDATE personal SET {', '.join(sets)} WHERE id_personal = ?"
                cursor.execute(sql, (id_personal,))
            
            cursor.execute("UPDATE solicitudes_arco SET estado = 'ATENDIDO', fecha_atencion = GETDATE() WHERE id_solicitud = ?", (id_solicitud,))
            flash('Solicitud APROBADA. Datos eliminados correctamente.', 'success')

        elif accion == 'RECHAZAR':
            cursor.execute("UPDATE solicitudes_arco SET estado = 'RECHAZADO', fecha_atencion = GETDATE() WHERE id_solicitud = ?", (id_solicitud,))
            flash('Solicitud rechazada.', 'info')

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"Error ARCO: {e}")
        flash('Error al procesar la solicitud.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('legajo.gestionar_solicitudes_arco'))



@legajo_bp.route('/papelera/planillas')
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def papelera_planillas():
    repo = PlanillaRepository()
    
    # CORRECCIÓN: Usamos el nombre exacto que definimos en el repositorio
    planillas_borradas = repo.obtener_planillas_eliminadas() 
    
    return render_template('admin/papelera_planillas.html', planillas=planillas_borradas)

@legajo_bp.route('/papelera/planillas/restaurar/<int:id>', methods=['POST'])
@login_required
# RECOMENDACIÓN: Agregamos 'Sistemas' por si el administrador principal no está
@role_required('AdministradorLegajos', 'Sistemas')
def restaurar_planilla(id):
    repo = PlanillaRepository()
    
    # CORRECCIÓN: Usamos el nombre 'restaurar_planilla_logica' que está en tu repo
    if repo.restaurar_planilla_logica(id):
        flash('✅ Planilla restaurada con éxito. Ya es visible nuevamente en RRHH.', 'success')
    else:
        flash('❌ No se pudo restaurar la planilla. Inténtelo de nuevo.', 'danger')
        
    return redirect(url_for('legajo.papelera_planillas'))

@legajo_bp.route('/papelera/planillas/eliminar_permanente/<int:id>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def eliminar_permanente_planilla(id):
    repo = PlanillaRepository()
    if repo.eliminar_planilla_permanente(id):
        flash('🗑️ Planilla eliminada permanentemente del sistema.', 'success')
    else:
        flash('❌ Error al intentar eliminar permanentemente.', 'danger')
    return redirect(url_for('legajo.papelera_planillas'))

@legajo_bp.route('/papelera/planillas/vaciar', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def vaciar_papelera_planillas():
    repo = PlanillaRepository()
    if repo.vaciar_papelera_planillas():
        flash('🔥 La papelera de planillas ha sido vaciada por completo.', 'success')
    return redirect(url_for('legajo.papelera_planillas'))