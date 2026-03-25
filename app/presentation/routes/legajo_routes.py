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
import zlib


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
            
            # Ejecutamos el proceso de carga masiva
            resultado = legajo_service.process_bulk_upload(file_storage, current_user.id)
            
            # 🛡️ BLOQUE DE AUDITORÍA: Registro de Importación Masiva
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    # Capturamos el nombre del archivo subido
                    nombre_archivo = file_storage.filename
                    exitos = resultado.get('exitosos', 0)
                    fallos = resultado.get('fallidos', 0)
                    
                    # Mensaje descriptivo para la bitácora
                    msj_auditoria = (f"Carga Masiva desde Excel: '{nombre_archivo}'. "
                                     f"Resultado: {exitos} exitosos, {fallos} fallidos.")
                    
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Carga Masiva',
                        accion='IMPORTAR_EXCEL',
                        descripcion=msj_auditoria
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error silencioso en auditoría (Carga Masiva): {audit_err}")

            # Mensajes de retroalimentación al usuario
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
    
    # 1. Se obtienen las unidades para las validaciones de datos en Excel.
    unidades = legajo_service.get_unidades_for_select()
    
    # 2. Se genera el flujo del archivo Excel
    excel_stream = legajo_service.generate_bulk_upload_template(unidades)
    
    # 🛡️ BLOQUE DE AUDITORÍA: Registro de descarga de herramienta de carga
    try:
        audit_service = current_app.config.get('AUDIT_SERVICE')
        if audit_service:
            audit_service.log(
                id_usuario=current_user.id,
                modulo='Carga Masiva',
                accion='DESCARGAR_PLANTILLA',
                descripcion=f"El usuario {current_user.username} descargó la plantilla oficial para carga masiva de personal."
            )
    except Exception as audit_err:
        current_app.logger.error(f"Error silencioso en auditoría (Descarga Plantilla): {audit_err}")

    # 3. Retorno del archivo al navegador
    return send_file(
        excel_stream,
        download_name="plantilla_carga_masiva_personal.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

from app.infrastructure.persistence.planilla_repository import PlanillaRepository
@legajo_bp.route('/seguridad/rotar_clave', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def rotar_clave_seguridad():
    # Asumimos que PlanillaRepository ya está importado en el archivo
    repo = PlanillaRepository() 
    
    try:
        # 1. Ejecutar la lógica de negocio para generar la nueva clave
        nueva_clave = repo.generar_nueva_clave_dinamica()
        
        if nueva_clave:
            # 🛡️ BLOQUE DE AUDITORÍA: Rotación de Clave de Seguridad
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    # Registramos quién hizo el cambio y sobre qué módulo sensible
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Seguridad',
                        accion='ROTAR_CLAVE',
                        descripcion=f"El usuario {current_user.username} generó una NUEVA clave dinámica de seguridad para el acceso a planillas históricas."
                    )
            except Exception as audit_err:
                # Log de error interno para el desarrollador, no bloquea al usuario
                current_app.logger.error(f"Error silencioso en auditoría (Rotar Clave): {audit_err}")

            flash(f'Clave de seguridad actualizada: {nueva_clave}', 'success')
        else:
            flash('Error al generar clave en la base de datos.', 'danger')
            
    except Exception as e:
        current_app.logger.error(f"Error crítico al rotar clave de seguridad: {e}")
        flash('Ocurrió un fallo técnico al intentar rotar la clave.', 'danger')

    return redirect(url_for('legajo.gestionar_token'))


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
    
    # Validamos que el legajo exista antes de auditar y renderizar
    if not legajo_completo or not legajo_completo.get('personal'):
        flash('El legajo solicitado no existe.', 'danger')
        return redirect(url_for('legajo.listar_personal'))

    # 🛡️ BLOQUE DE AUDITORÍA: Registro de Acceso al Expediente
    try:
        audit_service = current_app.config.get('AUDIT_SERVICE')
        if audit_service:
            persona = legajo_completo['personal']
            nombre_full = f"{persona.get('nombres', '')} {persona.get('apellidos', '')}"
            dni_persona = persona.get('dni', 'N/A')
            
            # Registramos quién miró el expediente de quién
            audit_service.log(
                id_usuario=current_user.id,
                modulo='Personal',
                accion='CONSULTA_DETALLE',
                descripcion=f"Consultó el expediente detallado de {nombre_full} (DNI: {dni_persona}). ID: {personal_id}"
            )
    except Exception as audit_err:
        current_app.logger.error(f"Error silencioso en auditoría (Ver Legajo): {audit_err}")
        
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
    # Cargamos las unidades para el combo select
    form.id_unidad.choices = [('0', '-- Seleccione Unidad --')] + legajo_service.get_unidades_for_select()
    
    if form.validate_on_submit():
        try:
            # 1. Crear Personal y Usuario en la Base de Datos
            new_personal_id = legajo_service.register_new_personal(form.data, current_user.id)
            
            # 🛡️ BLOQUE DE AUDITORÍA INYECTADO
            try:
                # Recuperamos el repositorio de auditoría desde la configuración
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    dni_nuevo = form.dni.data
                    nombre_completo = f"{form.nombres.data} {form.apellidos.data}"
                    
                    audit_service.log_event(
                        id_usuario=current_user.id,
                        modulo='Legajos',
                        accion='CREAR_PERSONAL',
                        descripcion=f"El usuario {current_user.username} registró un nuevo legajo: {nombre_completo} (DNI: {dni_nuevo}). ID de Sistema: {new_personal_id}",
                        detalle_json=None # Opcional: podrías pasar json.dumps(form.data) si quieres guardar todo
                    )
            except Exception as audit_err:
                # Si falla la auditoría, solo lo anotamos en el log del servidor (consola)
                current_app.logger.error(f"Error silencioso en auditoría: {audit_err}")

            # Mensajes de éxito al usuario
            flash('Paso 1 completado: Datos personales registrados.', 'success')
            flash('Legajo registrado exitosamente. Ahora RRHH debe asignar el contrato inicial.', 'success')
            
            return redirect(url_for('legajo.listar_personal'))
            
        except Exception as e:
            current_app.logger.error(f"Error crítico al crear personal: {e}")
            flash(f'Error al crear personal: {str(e)}', 'danger')
            
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
        form.id_unidad.data = str(persona.id_unidad) 

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
            
            acceso_creado = False
            if not usuario_existente:
                from werkzeug.security import generate_password_hash
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
                acceso_creado = True
            
            # 🛡️ BLOQUE DE AUDITORÍA: Registro de Activación de Legajo
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    nombre_full = f"{persona.nombres} {persona.apellidos}"
                    # Detallamos si se creó acceso o solo se asignó contrato
                    detalle_acceso = "con creación de acceso al sistema" if acceso_creado else " (acceso ya existía)"
                    
                    msj_auditoria = (f"Completó legajo (Paso 2) de {nombre_full} (DNI: {dni_empleado}). "
                                     f"Se asignó cargo y contrato {detalle_acceso}. ID: {personal_id}")
                    
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Personal',
                        accion='COMPLETAR_LEGAJO',
                        descripcion=msj_auditoria
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error silencioso en auditoría (Paso 2): {audit_err}")

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
    
    # Cargar opciones para los select
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
            
            # 1. Obtener nombre del trabajador para una auditoría de calidad
            datos_p = legajo_service.get_personal_details(personal_id, current_user)
            nombre_trabajador = "Desconocido"
            if datos_p and 'personal' in datos_p:
                p = datos_p['personal']
                nombre_trabajador = f"{p.get('nombres', '')} {p.get('apellidos', '')}"

            # 2. Procesar la subida del documento
            form_data = form.data
            form_data['id_personal'] = personal_id
            legajo_service.upload_document_to_personal(form_data, archivo, current_user.id)
            
            # 🛡️ BLOQUE DE AUDITORÍA: Registro de Subida de Archivo
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    # Log detallado con nombre del archivo y del trabajador
                    msj_auditoria = f"Subió el archivo '{archivo.filename}' al legajo de {nombre_trabajador} (ID: {personal_id})"
                    
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Documentos',
                        accion='SUBIR',
                        descripcion=msj_auditoria
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error en auditoría (Subir Doc): {audit_err}")

            flash('Documento subido correctamente.', 'success')

        except ValueError as ve:
            current_app.logger.warning(f"Error de validación al subir documento para personal {personal_id}: {ve}")
            flash(str(ve), 'danger')
        except Exception as e:
            from app.utils.error_handler import registrar_error_automatico
            registrar_error_automatico(e)
            current_app.logger.error(f"Error inesperado al subir documento para personal {personal_id}: {e}")
            flash(f'Ocurrió un error inesperado al subir el documento.', 'danger')
            
    else:
        # Manejo de fallos de validación del formulario
        error_str = "; ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
        current_app.logger.warning(f"Fallo de validación al subir documento para personal {personal_id}: {error_str}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error en el campo '{getattr(form, field).label.text}': {error}", 'danger')
                break 

    return redirect(url_for('legajo.ver_legajo', personal_id=personal_id))



@legajo_bp.route('/personal/<int:personal_id>/eliminar', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def eliminar_personal(personal_id):
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    try:
        # 1. Obtenemos los datos antes de desactivar para el reporte de auditoría
        # Usamos current_user para que el repositorio sepa quién consulta
        datos_previos = legajo_service.get_personal_details(personal_id, current_user)
        nombre_persona = "Desconocido"
        
        if datos_previos and 'personal' in datos_previos:
            p = datos_previos['personal']
            nombre_persona = f"{p.get('nombres', '')} {p.get('apellidos', '')} (DNI: {p.get('dni', 'N/A')})"

        # 2. Ejecutamos la desactivación (Sincroniza con Sistemas e Inactiva)
        success, msg = legajo_service.cambiar_estado_personal(personal_id, 'Inactivo')
        
        if success:
            # 🛡️ BLOQUE DE AUDITORÍA: Registro de Baja
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Personal',
                        accion='ELIMINAR', # O 'DAR_DE_BAJA'
                        descripcion=f"Se dio de BAJA al legajo de {nombre_persona}. Acceso al sistema bloqueado. ID: {personal_id}"
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error en auditoría (Baja): {audit_err}")

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
        # 1. Obtenemos datos antes de reactivar para que el log sea "bacán"
        datos_previos = legajo_service.get_personal_details(personal_id, current_user)
        nombre_persona = "Desconocido"
        
        if datos_previos and 'personal' in datos_previos:
            p = datos_previos['personal']
            nombre_persona = f"{p.get('nombres', '')} {p.get('apellidos', '')} (DNI: {p.get('dni', 'N/A')})"

        # 2. CORRECCIÓN CRÍTICA: Usamos la misma función BLINDADA
        # Enviamos 'Activo' para que el sistema detecte la palabra clave y ponga al usuario en VERDE (1)
        success, msg = legajo_service.cambiar_estado_personal(personal_id, 'Activo')
        
        if success:
            # 🛡️ BLOQUE DE AUDITORÍA: Registro de Reactivación
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    # Mensaje detallado para la bitácora
                    msj_auditoria = f"Se REACTIVÓ el legajo de {nombre_persona}. Acceso al sistema habilitado nuevamente. ID: {personal_id}"
                    
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Personal',
                        accion='REACTIVAR',
                        descripcion=msj_auditoria
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error en auditoría (Reactivar): {audit_err}")

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
            if legajo_service._personal_repo.existe_dni_en_otros(nuevo_dni, personal_id):
                flash(f'¡BLOQUEO DE INTEGRIDAD! El DNI {nuevo_dni} ya está registrado a nombre de otro trabajador.', 'danger')
                return render_template('admin/editar_personal.html', form=form, persona=persona_data, titulo="Editar Legajo")

            # 2. Si pasa la validación, procedemos a actualizar en la BD
            legajo_service.update_personal_details(personal_id, form.data, current_user.id)
            
            # 🛡️ BLOQUE DE AUDITORÍA: Registro de Modificación DETALLADO
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    # Extraemos los nombres actualizados directamente del formulario
                    nombre_editado = f"{form.nombres.data} {form.apellidos.data}"
                    
                    # 💡 DESCRIPCIÓN DINÁMICA: Ahora con nombre y DNI
                    nueva_descripcion = f"Se actualizaron los datos del legajo de {nombre_editado} (DNI: {nuevo_dni}) (ID: {personal_id})"
                    
                    # Llamamos a .log() que es el método de tu AuditService
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Personal',
                        accion='ACTUALIZAR',
                        descripcion=nueva_descripcion,
                        detalle_dict=None
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error silencioso en auditoría (Editar): {audit_err}")

            flash('Legajo actualizado correctamente en la base de datos.', 'success')
            return redirect(url_for('legajo.ver_legajo', personal_id=personal_id))
            
        except Exception as e:
            # 🚀 REGISTRO AUTOMÁTICO DE ERROR TÉCNICO
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
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas', 'Personal') 
def ver_documento(documento_id):
    """
    Gestiona la solicitud para ver un archivo (Descarga/Vista previa).
    AHORA CON AUDITORÍA VINCULADA AL TRABAJADOR Y DESCOMPRESIÓN ZLIB.
    """
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    # --- 1. VALIDACIÓN DE SEGURIDAD ---
    if not legajo_service.verify_document_access(documento_id, current_user):
        flash('No tiene permiso para acceder a este documento.', 'danger')
        return redirect(url_for('personal.inicio') if current_user.rol == 'Personal' else url_for('main_dashboard'))

    try:
        # --- 2. OBTENER DATOS DEL DOCUMENTO ---
        document = legajo_service.get_document_for_download(documento_id)
        
        if not document or not document.get('data'):
            flash('El documento no fue encontrado.', 'danger')
            return redirect(request.referrer or url_for('index'))

        # 🛡️ BLOQUE DE AUDITORÍA: Identificación del Propietario (Tabla 'documentos')
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                conn = get_db_read()
                cursor = conn.cursor()
                # Usamos la tabla 'documentos' que confirmamos en SSMS
                sql = """
                    SELECT p.id_personal, p.nombres + ' ' + p.apellidos 
                    FROM documentos d
                    INNER JOIN personal p ON d.id_personal = p.id_personal
                    WHERE d.id_documento = ?
                """
                cursor.execute(sql, (documento_id,))
                res = cursor.fetchone()
                
                id_p = res[0] if res else "N/A"
                nombre_p = res[1] if res else "Desconocido"
                nombre_archivo = document.get('filename', 'Archivo')

                # Detectamos si es descarga o vista previa para el log
                tipo_accion = "DESCARGÓ" if request.args.get('download') == '1' else "VISUALIZÓ"
                
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Documentos',
                    accion='VER_ARCHIVO',
                    descripcion=f"{tipo_accion} '{nombre_archivo}' (ID Doc: {documento_id}). Dueño: {nombre_p} (ID: {id_p})"
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (ver_documento): {audit_err}")

        # --- 3. 🔥 MAGIA DE DESCOMPRESIÓN (El Inflador) ---
        archivo_binario = document['data']
        try:
            data_final = zlib.decompress(archivo_binario)
        except zlib.error:
            # Si el archivo es antiguo (antes de implementar zlib), lo pasa directo
            data_final = archivo_binario

        # --- 4. DETECCIÓN DE FORMATO ---
        mimetype, _ = mimetypes.guess_type(document['filename'])
        if not mimetype:
            mimetype = 'application/octet-stream'

        SAFE_INLINE_MIMETYPES = [
            'application/pdf', 'image/jpeg', 'image/png', 
            'image/gif', 'image/webp', 'text/plain'
        ]

        # ¿Se descarga o se ve en el navegador?
        force_download = request.args.get('download') == '1'
        should_be_attachment = force_download or (mimetype not in SAFE_INLINE_MIMETYPES)

        return send_file(
            io.BytesIO(data_final),
            mimetype=mimetype,
            as_attachment=should_be_attachment,
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
        # 🛡️ OBTENCIÓN DE DATOS PARA AUDITORÍA (Antes de eliminar)
        # Intentamos obtener info del documento para que el log no sea solo un ID frío
        info_doc = "Desconocido"
        try:
            # Asumimos que el service tiene un método para ver el detalle del doc
            # Si no lo tiene, el bloque catch evitará que la ruta falle
            detalles = legajo_service.get_document_details(documento_id)
            if detalles:
                info_doc = f"'{detalles.get('nombre_archivo', 'Sin nombre')}' (Tipo: {detalles.get('tipo_documento', 'N/A')})"
        except:
            info_doc = f"con ID {documento_id}"

        # Ejecutar la eliminación en la base de datos
        legajo_service.delete_document_by_id(documento_id, current_user.id)
        
        # 🛡️ BLOQUE DE AUDITORÍA: Registro de Eliminación de Documento
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Documentos',
                    accion='ELIMINAR',
                    descripcion=f"El usuario eliminó el documento {info_doc}. ID Documento: {documento_id}"
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Eliminar Doc): {audit_err}")
            
        flash('Documento eliminado correctamente.', 'success')

    except Exception as e:
        current_app.logger.error(f"Error al eliminar documento {documento_id}: {e}")
        flash(f'Error al intentar eliminar el documento: {str(e)}', 'danger')
    
    # Redirige al usuario a la página anterior
    print("DEBUG: Redirigiendo al usuario.")
    return redirect(request.referrer or url_for('index'))



@legajo_bp.route('/documento/<int:documento_id>/visualizar')
@login_required
@role_required('AdministradorLegajos', 'RRHH', 'Sistemas', 'Personal')
def visualizar_documento(documento_id):
    """
    Visualización en línea inteligente con auditoría garantizada.
    Soporta PDF/Imágenes en navegador y descarga automática para otros tipos.
    """
    legajo_service = current_app.config['LEGAJO_SERVICE']

    # 1. VALIDACIÓN DE SEGURIDAD (Verificar si tiene permiso de acceso)
    if not legajo_service.verify_document_access(documento_id, current_user):
        flash('No tiene permiso para acceder a este documento.', 'danger')
        if current_user.rol == 'Personal':
            return redirect(url_for('personal.inicio'))
        return redirect(url_for('main_dashboard'))

    try:
        # 2. OBTENER DATOS DEL ARCHIVO DESDE LA BD
        document = legajo_service.get_document_for_download(documento_id)
        
        if not document or not document.get('data'):
            flash('El documento no fue encontrado o está vacío.', 'danger')
            return redirect(request.referrer or url_for('index'))

        # 🛡️ BLOQUE DE AUDITORÍA REFORZADO (Consulta SQL Directa con tabla corregida)
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                # Usamos el nombre de tabla 'documentos' confirmado por SSMS
                conn = get_db_read()
                cursor = conn.cursor()
                sql = """
                    SELECT p.id_personal, p.nombres + ' ' + p.apellidos 
                    FROM documentos d
                    INNER JOIN personal p ON d.id_personal = p.id_personal
                    WHERE d.id_documento = ?
                """
                cursor.execute(sql, (documento_id,))
                res = cursor.fetchone()
                
                # Extraemos datos del legajo si existen
                id_p = res[0] if res else "N/A"
                nombre_p = res[1] if res else "Desconocido"
                nombre_archivo = document.get('filename', 'Archivo')

                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Documentos',
                    accion='VISUALIZAR',
                    descripcion=f"Visualizó '{nombre_archivo}' (ID Doc: {documento_id}). Legajo: {nombre_p} (ID: {id_p})"
                )
        except Exception as audit_err:
            # Error silencioso: no bloqueamos la visualización si falla el log
            current_app.logger.error(f"Error en log de auditoría (Visualizar): {audit_err}")

        # 3. 🔥 DESCOMPRESIÓN INTELIGENTE (ZLIB)
        archivo_binario = document['data']
        try:
            data_final = zlib.decompress(archivo_binario)
        except Exception:
            # Archivo antiguo o no comprimido
            data_final = archivo_binario

        # 4. DETECCIÓN DE FORMATO (MIME TYPE)
        mimetype, _ = mimetypes.guess_type(document['filename'])
        if not mimetype:
            mimetype = 'application/octet-stream'

        # Formatos que el navegador puede abrir sin descargar
        SAFE_INLINE_MIMETYPES = [
            'application/pdf', 'image/jpeg', 'image/png', 
            'image/gif', 'image/webp', 'text/plain'
        ]

        # Si no es un formato "seguro", forzar descarga (ej: Word, Excel)
        should_be_attachment = mimetype not in SAFE_INLINE_MIMETYPES

        # 5. ENVIAR EL ARCHIVO AL NAVEGADOR
        return send_file(
            io.BytesIO(data_final),
            mimetype=mimetype,
            as_attachment=should_be_attachment,
            download_name=document['filename']
        )

    except Exception as e:
        current_app.logger.error(f"Error crítico al visualizar documento {documento_id}: {e}")
        flash('Ocurrió un error al intentar procesar el archivo.', 'danger')
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
    Descomprime el archivo binario antes de forzar la descarga.
    """
    import zlib
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        # Recuperamos el binario desde la tabla record_laboral
        document = legajo_service._personal_repo.get_record_file_by_id(id_record)
        
        if not document:
            flash('La boleta de pago no existe.', 'danger')
            return redirect(request.referrer)

        # ---------------------------------------------------------
        # 🛡️ BLOQUE DE AUDITORÍA (Descargar Récord Laboral)
        # ---------------------------------------------------------
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                nombre_archivo = document.get('nombre_archivo', 'archivo_desconocido')
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Récord Laboral',
                    accion='DESCARGAR',
                    descripcion=f"Descargó el archivo de récord laboral: '{nombre_archivo}' (ID: {id_record})."
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Descargar Récord): {audit_err}")
        # ---------------------------------------------------------

        # ==========================================================
        # 🔥 MAGIA DE DESCOMPRESIÓN
        # ==========================================================
        bytes_finales = document['contenido']
        try:
            # Intentamos inflar el archivo
            bytes_finales = zlib.decompress(bytes_finales)
        except zlib.error:
            # Si el archivo es antiguo y no estaba comprimido, 
            # zlib dará error, así que ignoramos y usamos los bytes originales
            pass
        # ==========================================================

        return send_file(
            io.BytesIO(bytes_finales), # <-- AHORA USAMOS LOS BYTES INFLADOS
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
    🚀 ACTUALIZACIÓN: Envía las dos listas separadas (Modernos e Históricos) al HTML.
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

        # ---------------------------------------------------------
        # 🛡️ BLOQUE DE AUDITORÍA (Consulta de Récord Laboral)
        # ---------------------------------------------------------
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                nombre_trabajador = f"{persona.get('nombres', '')} {persona.get('apellidos', '')}".strip()
                dni_trabajador = persona.get('dni', 'N/A')
                
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Récord Laboral',
                    accion='CONSULTA_DETALLE',
                    descripcion=f"Consultó el historial de pagos y planillas de {nombre_trabajador} (DNI: {dni_trabajador}). ID: {personal_id}"
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Ver Récord Laboral): {audit_err}")
        # ---------------------------------------------------------

        return render_template(
            'admin/ver_record_laboral_detalle.html',
            persona=persona,
            pagos=legajo_completo.get('record_laboral', []), # Lista 1: Modernos (RRHH)
            historicos=legajo_completo.get('historico_laboral', []) # 🚀 Lista 2: Bóveda (Escalafón)
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
    Descomprime el archivo binario si fue guardado con zlib.
    """
    import zlib
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        document = legajo_service._personal_repo.get_record_file_by_id(id_record)
        
        if not document or not document.get('contenido'):
            flash('La boleta no fue encontrada en el servidor.', 'danger')
            return redirect(request.referrer)

        filename = document.get('nombre_archivo', 'archivo_boleta')

        # ---------------------------------------------------------
        # 🛡️ BLOQUE DE AUDITORÍA (Ver/Descargar Boleta)
        # ---------------------------------------------------------
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Récord Laboral',
                    accion='VER_BOLETA',
                    descripcion=f"Visualizó o descargó la boleta de pago: '{filename}' (ID Récord: {id_record})."
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Ver Boleta): {audit_err}")
        # ---------------------------------------------------------

        # ==========================================================
        # 🔥 MAGIA DE DESCOMPRESIÓN
        # ==========================================================
        bytes_finales = document['contenido']
        try:
            # Intentamos inflar el archivo
            bytes_finales = zlib.decompress(bytes_finales)
        except zlib.error:
            # Si el archivo es antiguo y no estaba comprimido, 
            # zlib dará error, así que ignoramos y usamos los bytes originales
            pass
        # ==========================================================

        # 🚀 DETECCIÓN DE TIPO: Usamos mimetypes para saber qué es el archivo
        mimetype, _ = mimetypes.guess_type(filename)
        if not mimetype:
            mimetype = 'application/octet-stream'

        # 🚀 LÓGICA DE DESCARGA: Solo visualizamos si es PDF; todo lo demás se descarga
        is_pdf = mimetype == 'application/pdf'
        
        return send_file(
            io.BytesIO(bytes_finales),  # <-- AHORA USAMOS LOS BYTES INFLADOS
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
    # ✅ CORRECCIÓN 3: Agregamos 'AdministradorEscalafon'
    roles_permitidos = ['Administrador', 'Sistemas', 'Legajos', 'RRHH', 'AdministradorLegajos', 'AdministradorEscalafon']

    if current_user.rol not in roles_permitidos:
        flash('No tienes permisos para ejecutar esta acción.', 'danger')
        return redirect(url_for('auth.login'))

    conn = get_db_read()
    cursor = conn.cursor()

    try:
        # Obtener datos de la solicitud para saber a quién afecta
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
                # Ejecutamos el borrado (Derecho de Cancelación)
                sql = f"UPDATE personal SET {', '.join(sets)} WHERE id_personal = ?"
                cursor.execute(sql, (id_personal,))
            
            # Actualizar estado de la solicitud
            cursor.execute("UPDATE solicitudes_arco SET estado = 'ATENDIDO', fecha_atencion = GETDATE() WHERE id_solicitud = ?", (id_solicitud,))
            
            # 🛡️ BLOQUE DE AUDITORÍA: Aprobación ARCO
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Seguridad ARCO',
                        accion='APROBAR_ARCO',
                        descripcion=f"APROBADA: Solicitud ID {id_solicitud}. Se eliminaron los datos ({datos_texto}) del legajo ID {id_personal} por derecho ARCO."
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error en auditoría ARCO (Aprobar): {audit_err}")

            flash('Solicitud APROBADA. Datos eliminados correctamente.', 'success')

        elif accion == 'RECHAZAR':
            cursor.execute("UPDATE solicitudes_arco SET estado = 'RECHAZADO', fecha_atencion = GETDATE() WHERE id_solicitud = ?", (id_solicitud,))
            
            # 🛡️ BLOQUE DE AUDITORÍA: Rechazo ARCO
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Seguridad ARCO',
                        accion='RECHAZAR_ARCO',
                        descripcion=f"RECHAZADA: Solicitud ID {id_solicitud} para el legajo ID {id_personal}. Acción ejecutada por {current_user.username}."
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error en auditoría ARCO (Rechazar): {audit_err}")

            flash('Solicitud rechazada.', 'info')

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Error crítico en proceso ARCO: {e}")
        flash('Error al procesar la solicitud.', 'danger')
    
    return redirect(url_for('legajo.gestionar_solicitudes_arco'))



@legajo_bp.route('/papelera/planillas')
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def papelera_planillas():
    """
    Carga la vista de la papelera unificada.
    Muestra registros eliminados tanto de RRHH como de la Bóveda Histórica.
    """
    repo = PlanillaRepository()
    
    try:
        # 🚀 Llamamos al método híbrido que hace el UNION ALL en el SQL
        planillas_borradas = repo.obtener_planillas_eliminadas()
        
        # DEBUG: Esto te permite ver en la terminal negra cuántos registros llegan
        print(f"---[PAPELERA]--- Se enviaron {len(planillas_borradas)} registros al HTML.")
        
    except Exception as e:
        # Si algo falla en el repositorio, evitamos que la página explote (Error 500)
        current_app.logger.error(f"Error al cargar papelera de planillas: {str(e)}")
        planillas_borradas = []
        flash('Ocurrió un inconveniente al conectar con la base de datos de la papelera.', 'danger')

    # El nombre de la variable 'planillas' debe coincidir con el 'for p in planillas' de tu HTML
    return render_template('admin/papelera_planillas.html', planillas=planillas_borradas)

@legajo_bp.route('/papelera/planillas/restaurar/<int:id>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def restaurar_planilla(id):
    """
    Saca una planilla de la papelera y la devuelve al estado activo.
    Identifica automáticamente si es de RRHH (Moderna) o de Escalafón (Histórica).
    """
    repo = PlanillaRepository()
    
    # 🚀 CAPTURAMOS EL ORIGEN: Viene del parámetro en la URL del botón
    # Si no se especifica, por seguridad asumimos 'MODERNA'
    origen = request.args.get('origen', 'MODERNA')

    try:
        # Llamamos al método híbrido que actualizamos en el repositorio
        if repo.restaurar_planilla_logica(id, origen):
            
            # 🛡️ REGISTRO EN AUDITORÍA
            # Guardamos quién devolvió el registro a la vida
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    audit_service.log(
                        current_user.id, 
                        'Papelera', 
                        'RESTAURAR_REGISTRO', 
                        f"El usuario {current_user.username} restauró la planilla ID #{id} ({origen})."
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error registrando auditoría de restauración: {audit_err}")

            flash(f'✅ Planilla {origen} restaurada con éxito. Ya es visible en su módulo correspondiente.', 'success')
        else:
            flash(f'❌ No se pudo encontrar la planilla #{id} en {origen} para restaurar.', 'warning')

    except Exception as e:
        current_app.logger.error(f"Error crítico al restaurar planilla: {str(e)}")
        flash(f'⚠️ Error técnico al intentar restaurar: {str(e)}', 'danger')

    return redirect(url_for('legajo.papelera_planillas'))

@legajo_bp.route('/papelera/planillas/eliminar_permanente/<int:id>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def eliminar_permanente_planilla(id):
    """
    Elimina físicamente una planilla y sus detalles/conceptos.
    Soporta registros de RRHH y la Bóveda Histórica de Escalafón.
    """
    repo = PlanillaRepository()
    
    # 🚀 CAPTURAMOS EL ORIGEN: Viene del parámetro enviado en el URL del HTML
    # Si por algún motivo no viene, por defecto asumimos 'MODERNA'
    origen = request.args.get('origen', 'MODERNA')

    try:
        # Ejecutamos el borrado físico en el repositorio (Híbrido)
        if repo.eliminar_planilla_permanente(id, origen):
            
            # 🛡️ REGISTRO EN AUDITORÍA
            # Es obligatorio registrar quién destruyó un dato permanentemente
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    audit_service.log(
                        current_user.id, 
                        'Papelera', 
                        'ELIMINACION_FISICA', 
                        f"Usuario {current_user.username} eliminó permanentemente la planilla ID #{id} de origen {origen}."
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error auditoría eliminación física: {audit_err}")

            flash(f'🗑️ Registro ({origen}) eliminado permanentemente del sistema.', 'success')
        else:
            flash(f'⚠️ No se encontró el registro #{id} en la tabla {origen} para eliminar.', 'warning')

    except Exception as e:
        # Manejo de errores de base de datos (ej: errores de Foreign Key)
        current_app.logger.error(f"Error crítico en eliminación permanente: {str(e)}")
        flash(f'❌ Error técnico: {str(e)}', 'danger')

    return redirect(url_for('legajo.papelera_planillas'))

@legajo_bp.route('/papelera/planillas/vaciar', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def vaciar_papelera_planillas():
    """
    Ruta para la eliminación definitiva de todos los registros en la papelera.
    Limpia tanto el módulo de RRHH como el histórico de Escalafón.
    """
    repo = PlanillaRepository()
    
    try:
        # Ejecutamos la limpieza masiva en el repositorio
        if repo.vaciar_papelera_planillas():
            
            # 🛡️ REGISTRO EN AUDITORÍA (Opcional, según tu implementación)
            # Es vital saber quién borró permanentemente los datos.
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    audit_service.log(
                        current_user.id, 
                        'Planillas', 
                        'VACIAR_PAPELERA', 
                        f"El usuario {current_user.username} vació la papelera de planillas unificada."
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error al registrar auditoría de vaciado: {audit_err}")

            flash('🔥 La papelera de planillas ha sido vaciada por completo (RRHH e Históricos).', 'success')
        else:
            flash('⚠️ No se encontraron registros para eliminar o el proceso fue interrumpido.', 'warning')
            
    except Exception as e:
        # En caso de un fallo en la base de datos (ej. bloqueo de tablas)
        current_app.logger.error(f"Error crítico al vaciar papelera: {str(e)}")
        flash(f'❌ Error técnico al intentar vaciar la papelera: {str(e)}', 'danger')

    return redirect(url_for('legajo.papelera_planillas'))

# ==============================================================================
# MÓDULO: PLANILLAS HISTÓRICAS (Acceso Exclusivo: Escalafón / AdministradorLegajos)
# ==============================================================================
import os
import base64
import traceback
from datetime import datetime
from io import BytesIO
from xhtml2pdf import pisa
from werkzeug.utils import secure_filename
from app.database import get_db_read, get_db_write 
from flask import request, jsonify, render_template, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
# ... (Asegúrate de tener tus importaciones previas aquí)

# 1. LISTADO PRINCIPAL
@legajo_bp.route('/planillas-historicas/buscar', methods=['GET'])
@login_required
@role_required('AdministradorLegajos')
def listar_personal_historico():
    form = FiltroPersonalForm(request.args)
    page = request.args.get('page', 1, type=int)
    
    filters = {
        'dni': form.dni.data, 
        'nombres': form.nombres.data
    }
    legajo_service = current_app.config['LEGAJO_SERVICE']
    try:
        pagination = legajo_service.get_personal_historico_paginated(page, 15, filters)
        return render_template('admin/listar_personal_historico.html', form=form, pagination=pagination)
    except Exception as e:
        current_app.logger.error(f"Error en buscador histórico: {str(e)}")
        flash("Error al cargar la lista de personal histórico.", "danger")
        return redirect(url_for('legajo.dashboard'))


# 2. DESIGNAR PERSONAL
@legajo_bp.route('/designar-historico', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def designar_personal_historico():
    dni = request.form.get('dni_busqueda')
    if not dni:
        flash('Debe ingresar un DNI válido.', 'warning')
        return redirect(url_for('legajo.listar_personal_historico'))
    try:
        conexion = get_db_write()
        cursor = conexion.cursor()
        sql = "UPDATE personal SET tipo_registro = 1 WHERE dni = ?"
        cursor.execute(sql, (dni,))
        if cursor.rowcount > 0:
            conexion.commit()
            flash(f'Éxito: El trabajador con DNI {dni} ha sido habilitado para registro histórico.', 'success')
        else:
            flash(f'Error: El DNI {dni} no existe en la base de datos general.', 'danger')
        cursor.close()
    except Exception as e:
        flash(f'Error al procesar la designación: {str(e)}', 'danger')
    return redirect(url_for('legajo.listar_personal_historico'))


# 3. GUARDAR LOS DATOS DINÁMICOS (TRANSCRIPCIÓN MANUAL)
@legajo_bp.route('/guardar_planilla_historica', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def guardar_planilla_historica():
    datos = request.get_json()
    if not datos:
        return jsonify({"estado": "error", "mensaje": "No se recibieron datos"}), 400

    try:
        conexion = get_db_write() 
        cursor = conexion.cursor()
        
        # 🚀 A. Guardar Cabecera (AHORA CON TODOS LOS DATOS NUEVOS)
        sql_cabecera = """
            INSERT INTO Planillas_Historicas 
            (id_personal, anio, mes, tipo_moneda, total_ingresos, total_descuentos, monto_neto, bloqueado,
             cargo_historico, unidad_historica, nivel_historico, regimen_historico, condicion_historica, 
             pension_historica, dias_laborados, faltas, observaciones)
            OUTPUT INSERTED.id_planilla_historica
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql_cabecera, (
            datos['id_personal'], datos['anio'], datos['mes'], datos['moneda'],
            datos['total_ingresos'], datos['total_descuentos'], datos['monto_neto'],
            datos.get('cargo'), datos.get('unidad'), datos.get('nivel'), 
            datos.get('regimen'), datos.get('condicion'), datos.get('pension'),
            datos.get('dias_laborados', 30), datos.get('faltas', 0), datos.get('observaciones')
        ))
        id_planilla = cursor.fetchone()[0]
        
        # B. Guardar Conceptos Dinámicos
        sql_detalle = """
            INSERT INTO Planillas_Historicas_Conceptos
            (id_planilla_historica, tipo_concepto, descripcion_concepto, monto)
            VALUES (?, ?, ?, ?)
        """
        for concepto in datos['conceptos']:
            cursor.execute(sql_detalle, (
                id_planilla, concepto['tipo'], concepto['descripcion'], concepto['monto']
            ))
            
        # 🛡️ BLOQUE DE AUDITORÍA: Registro de Transacción Financiera
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                # Obtenemos el nombre del trabajador para un log profesional
                cursor.execute("SELECT nombres + ' ' + apellidos FROM personal WHERE id_personal = ?", (datos['id_personal'],))
                nombre_trabajador = cursor.fetchone()
                nombre_p = nombre_trabajador[0] if nombre_trabajador else "Desconocido"
                
                msj = (f"Registró planilla histórica manual de {nombre_p} (ID: {datos['id_personal']}) "
                       f"correspondiente a {datos['mes']}/{datos['anio']}. Monto Neto: {datos['monto_neto']}")
                
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Planillas',
                    accion='REGISTRAR_PLANILLA_HISTORICA',
                    descripcion=msj
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Planilla Histórica): {audit_err}")

        conexion.commit()
        cursor.close()
        return jsonify({"estado": "ok", "mensaje": "Planilla histórica guardada exitosamente", "id": id_planilla}), 200

    except Exception as e:
        if 'conexion' in locals():
            conexion.rollback()
        current_app.logger.error(f"Error al guardar planilla histórica: {str(e)}")
        return jsonify({"estado": "error", "mensaje": str(e)}), 500


# 3B. SUBIR ARCHIVO DE PLANILLA HISTÓRICA (El Escaneo Original)
@legajo_bp.route('/subir_archivo_historico', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def subir_archivo_historico():
    try:
        id_personal = request.form.get('id_personal')
        periodo = request.form.get('periodo') 
        archivo = request.files.get('archivo')
        
        if not archivo or archivo.filename == '':
            return jsonify({"estado": "error", "mensaje": "No se seleccionó archivo."}), 400
            
        anio, mes_num = periodo.split('-')
        nombres_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_texto = nombres_meses[int(mes_num) - 1]

        directorio_destino = os.path.join(current_app.root_path, 'presentation', 'static', 'uploads', 'historicos')
        os.makedirs(directorio_destino, exist_ok=True)
        nombre_seguro = secure_filename(f"SCAN_{id_personal}_{anio}_{mes_num}_{archivo.filename}")
        archivo.save(os.path.join(directorio_destino, nombre_seguro))
        ruta_bd = f"uploads/historicos/{nombre_seguro}"

        conexion = get_db_write()
        cursor = conexion.cursor()
        sql = """
            INSERT INTO Planillas_Historicas 
            (id_personal, anio, mes, tipo_moneda, total_ingresos, total_descuentos, monto_neto, ruta_escaneado, bloqueado)
            VALUES (?, ?, ?, 'Documento Escaneado', 0, 0, 0, ?, 0)
        """
        cursor.execute(sql, (id_personal, anio, mes_texto, ruta_bd))
        conexion.commit()
        cursor.close()
        
        return jsonify({"estado": "ok", "mensaje": "Escaneo guardado correctamente."})
    except Exception as e:
        return jsonify({"estado": "error", "mensaje": str(e)}), 500


# 4. OBTENER EL HISTORIAL
@legajo_bp.route('/obtener_planillas_historicas/<int:id_personal>', methods=['GET'])
@login_required
@role_required('AdministradorLegajos', 'RRHH')
def obtener_planillas_historicas(id_personal):
    conexion = None
    try:
        conexion = get_db_read()
        cursor = conexion.cursor()
        
        # 🚀 AQUÍ ESTÁ LA CORRECCIÓN: Agregamos "AND (activo = 1 OR activo IS NULL)"
        # Esto obliga a la tabla a ocultar los archivos que están en la papelera.
        sql = """
            SELECT id_planilla_historica, anio, mes, tipo_moneda, 
                   total_ingresos, total_descuentos, monto_neto, 
                   ruta_escaneado, ruta_generado, ISNULL(bloqueado, 0) as bloqueado
            FROM Planillas_Historicas 
            WHERE id_personal = ? AND (activo = 1 OR activo IS NULL)
            ORDER BY anio DESC, 
                     CASE mes 
                        WHEN 'Enero' THEN 1 WHEN 'Febrero' THEN 2 WHEN 'Marzo' THEN 3 
                        WHEN 'Abril' THEN 4 WHEN 'Mayo' THEN 5 WHEN 'Junio' THEN 6 
                        WHEN 'Julio' THEN 7 WHEN 'Agosto' THEN 8 WHEN 'Septiembre' THEN 9 
                        WHEN 'Octubre' THEN 10 WHEN 'Noviembre' THEN 11 WHEN 'Diciembre' THEN 12 
                     END ASC
        """
        cursor.execute(sql, (id_personal,))
        filas = cursor.fetchall()
        
        planillas = [{
            "id": f[0], "anio": f[1], "mes": f[2], "moneda": f[3],
            "ingresos": float(f[4] or 0), "descuentos": float(f[5] or 0), "neto": float(f[6] or 0),
            "ruta_escaneado": f[7], "ruta_generado": f[8], "bloqueado": bool(f[9])
        } for f in filas]
            
        cursor.close()
        return jsonify({"estado": "ok", "data": planillas})
    except Exception as e:
        return jsonify({"estado": "error", "mensaje": str(e)}), 500
    finally:
        if conexion:
            conexion.close()

# 5, 6, 7 y Revertir
@legajo_bp.route('/planillas-historicas/gestionar/<int:personal_id>', methods=['GET'])
@login_required
@role_required('AdministradorLegajos')
def gestionar_historico_personal(personal_id):
    legajo_service = current_app.config['LEGAJO_SERVICE']
    legajo_data = legajo_service.get_personal_details(personal_id, current_user)
    if not legajo_data or not legajo_data.get('personal'):
        flash('El trabajador no existe.', 'danger')
        return redirect(url_for('legajo.listar_personal_historico'))
    return render_template('admin/gestionar_historico.html', persona=legajo_data['personal'])

@legajo_bp.route('/eliminar_planilla_historica/<int:id_planilla>', methods=['DELETE'])
@login_required
@role_required('AdministradorLegajos')
def eliminar_planilla_historica(id_planilla):
    conexion = None
    try:
        conexion = get_db_write()
        cursor = conexion.cursor()

        # 1. Obtenemos datos para la auditoría y chequeamos bloqueo
        cursor.execute("""
            SELECT ph.bloqueado, p.nombres + ' ' + p.apellidos, ph.mes, ph.anio
            FROM Planillas_Historicas ph
            INNER JOIN personal p ON ph.id_personal = p.id_personal
            WHERE ph.id_planilla_historica = ?
        """, (id_planilla,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"estado": "error", "mensaje": "Planilla no encontrada."}), 404

        bloqueado, nombre_p, mes_p, anio_p = row

        if bloqueado:
            return jsonify({"estado": "error", "mensaje": "Planilla bloqueada."}), 403

        # 🚀 2. "BORRADO" ESTILO WINDOWS (Apagamos el activo y ponemos fecha)
        cursor.execute("""
            UPDATE Planillas_Historicas 
            SET activo = 0, fecha_eliminacion = GETDATE()
            WHERE id_planilla_historica = ?
        """, (id_planilla,))

        # 🛡️ 3. AUDITORÍA
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                msj = f"Envió a papelera la planilla histórica ID {id_planilla} de {nombre_p} ({mes_p}/{anio_p})."
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Planillas',
                    accion='MOVER_A_PAPELERA',
                    descripcion=msj
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error en auditoría: {audit_err}")

        conexion.commit()
        return jsonify({"estado": "ok", "mensaje": "Planilla movida a la papelera."})

    except Exception as e:
        if conexion: conexion.rollback()
        return jsonify({"estado": "error", "mensaje": str(e)}), 500
    finally:
        if conexion:
            cursor.close()
            conexion.close()

# ==============================================================================
# 🔐 GESTIÓN DE SEGURIDAD: DESBLOQUEO CON TOKEN REAL
# ==============================================================================

@legajo_bp.route('/toggle_candado_historico/<int:id_planilla>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def toggle_candado_historico(id_planilla):
    datos = request.get_json() or {}
    token_ingresado = datos.get('token_seguridad', '').strip()

    try:
        conexion = get_db_write()
        cursor = conexion.cursor()
        
        # 1. Verificamos el estado actual de la planilla histórica
        cursor.execute("SELECT ISNULL(bloqueado, 0) FROM Planillas_Historicas WHERE id_planilla_historica = ?", (id_planilla,))
        row_planilla = cursor.fetchone()
        
        if not row_planilla:
            return jsonify({"estado": "error", "mensaje": "La planilla no existe."}), 404
            
        estado_actual = row_planilla[0]

        # 2. LÓGICA DE PROTECCIÓN (SI LA QUIEREN ABRIR)
        if estado_actual == 1:
            
            # 🚀 SOLUCIÓN DEFINITIVA: Usamos tu propia función del repositorio de RRHH
            from app.infrastructure.persistence.planilla_repository import PlanillaRepository
            repo = PlanillaRepository()
            
            clave_real = repo.obtener_clave_dinamica()
            
            if not clave_real:
                return jsonify({"estado": "error", "mensaje": "Error: No se encontró una clave de seguridad activa en el sistema."}), 403

            # 🛡️ VALIDACIÓN ESTRICTA
            if token_ingresado.upper() != clave_real.upper():
                return jsonify({
                    "estado": "error", 
                    "mensaje": "CLAVE INCORRECTA. El código ingresado no coincide con la seguridad del sistema."
                }), 403
            
            nuevo_estado = 0
            mensaje_final = "Planilla histórica desbloqueada correctamente."

        # 3. SI ESTÁ ABIERTA Y LA QUIEREN CERRAR (Directo, sin clave)
        else:
            nuevo_estado = 1
            mensaje_final = "Planilla cerrada y protegida."

        # 4. EJECUTAMOS EL CAMBIO EN LA BASE DE DATOS
        sql_update = "UPDATE Planillas_Historicas SET bloqueado = ? WHERE id_planilla_historica = ?"
        cursor.execute(sql_update, (nuevo_estado, id_planilla))

        # ---------------------------------------------------------
        # 🛡️ BLOQUE DE AUDITORÍA (Inyectado sin alterar tu lógica)
        # ---------------------------------------------------------
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                # Buscamos rápido a quién le pertenece para que el log quede bien detallado
                cursor.execute("""
                    SELECT p.nombres + ' ' + p.apellidos, ph.mes, ph.anio
                    FROM Planillas_Historicas ph
                    INNER JOIN personal p ON ph.id_personal = p.id_personal
                    WHERE ph.id_planilla_historica = ?
                """, (id_planilla,))
                info = cursor.fetchone()
                
                if info:
                    nombre_p, mes_p, anio_p = info
                    # Determinamos las palabras exactas para el log
                    accion_log = 'DESBLOQUEAR' if nuevo_estado == 0 else 'BLOQUEAR'
                    verbo = 'Desbloqueó' if nuevo_estado == 0 else 'Cerró con candado'
                    
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Seguridad Planillas',
                        accion=f'{accion_log}_HISTORICA',
                        descripcion=f"{verbo} la planilla histórica ID {id_planilla} de {nombre_p} ({mes_p}/{anio_p})."
                    )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Candado Histórico): {audit_err}")
        # ---------------------------------------------------------

        conexion.commit()
        cursor.close()
        
        return jsonify({"estado": "ok", "mensaje": mensaje_final})
        
    except Exception as e:
        current_app.logger.error(f"🔥 Error en seguridad de planilla histórica: {str(e)}")
        return jsonify({"estado": "error", "mensaje": f"Fallo técnico: {str(e)}"}), 500

@legajo_bp.route('/revertir-historico/<int:id_personal>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos')
def revertir_personal_historico(id_personal):
    try:
        conexion = get_db_write()
        cursor = conexion.cursor()
        sql = "UPDATE personal SET tipo_registro = 2 WHERE id_personal = ?"
        cursor.execute(sql, (id_personal,))
        if cursor.rowcount > 0:
            conexion.commit()
            flash('Trabajador retirado de la lista histórica exitosamente.', 'success')
        else:
            flash('No se pudo encontrar al trabajador para actualizarlo.', 'warning')
        cursor.close()
    except Exception as e:
        flash(f'Error al procesar la reversión: {str(e)}', 'danger')
    return redirect(url_for('legajo.listar_personal_historico'))


# 8. OBTENER DETALLE DE UNA SOLA PLANILLA (PARA EDITAR)
@legajo_bp.route('/obtener_detalle_planilla_historica/<int:id_planilla>', methods=['GET'])
@login_required
@role_required('AdministradorLegajos')
def obtener_detalle_planilla_historica(id_planilla):
    try:
        conexion = get_db_read()
        cursor = conexion.cursor()
        
        # 🚀 1. Traer Cabecera con TODOS los datos nuevos
        sql_cabecera = """
            SELECT anio, mes, tipo_moneda, ruta_archivo,
                   cargo_historico, unidad_historica, nivel_historico, regimen_historico,
                   condicion_historica, pension_historica, dias_laborados, faltas, observaciones
            FROM Planillas_Historicas 
            WHERE id_planilla_historica = ?
        """
        cursor.execute(sql_cabecera, (id_planilla,))
        c = cursor.fetchone()
        
        if not c:
            return jsonify({"estado": "error", "mensaje": "Planilla no encontrada"}), 404
            
        # 2. Traer Conceptos
        sql_conceptos = "SELECT tipo_concepto, descripcion_concepto, monto FROM Planillas_Historicas_Conceptos WHERE id_planilla_historica = ?"
        cursor.execute(sql_conceptos, (id_planilla,))
        conceptos = [{"tipo": x[0], "descripcion": x[1], "monto": float(x[2])} for x in cursor.fetchall()]
        cursor.close()
        
        return jsonify({
            "estado": "ok",
            "cabecera": {
                "anio": c[0], "mes": c[1], "moneda": c[2], "es_archivo": True if c[3] else False,
                "cargo": c[4], "unidad": c[5], "nivel": c[6], "regimen": c[7],
                "condicion": c[8], "pension": c[9], "dias_laborados": c[10], "faltas": c[11], "observaciones": c[12]
            },
            "conceptos": conceptos
        })
    except Exception as e:
        return jsonify({"estado": "error", "mensaje": str(e)}), 500


# 9. ACTUALIZAR PLANILLA HISTÓRICA EXISTENTE (EDITAR)
@legajo_bp.route('/actualizar_planilla_historica/<int:id_planilla>', methods=['PUT'])
@login_required
@role_required('AdministradorLegajos')
def actualizar_planilla_historica(id_planilla):
    datos = request.get_json()
    if not datos: 
        return jsonify({"estado": "error", "mensaje": "No se recibieron datos para actualizar."}), 400

    conexion = None
    try:
        conexion = get_db_write()
        cursor = conexion.cursor()
        
        # 0. Verificación de Bloqueo e Identificación del Trabajador (para Auditoría)
        sql_check = """
            SELECT ph.bloqueado, p.id_personal, p.nombres + ' ' + p.apellidos 
            FROM Planillas_Historicas ph
            INNER JOIN personal p ON ph.id_personal = p.id_personal
            WHERE ph.id_planilla_historica = ?
        """
        cursor.execute(sql_check, (id_planilla,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"estado": "error", "mensaje": "Planilla no encontrada."}), 404
        
        bloqueado, id_personal_audit, nombre_trabajador = row
        
        if bloqueado:
            return jsonify({"estado": "error", "mensaje": "La planilla está bloqueada y no puede editarse."}), 403

        # 🚀 1. Actualizamos la Cabecera con datos nuevos
        # Nota: ruta_generado = NULL es clave para que el PDF se actualice luego
        sql_update_cabecera = """
            UPDATE Planillas_Historicas 
            SET anio = ?, mes = ?, tipo_moneda = ?, total_ingresos = ?, total_descuentos = ?, monto_neto = ?,
                cargo_historico = ?, unidad_historica = ?, nivel_historico = ?, regimen_historico = ?,
                condicion_historica = ?, pension_historica = ?, dias_laborados = ?, faltas = ?, observaciones = ?,
                ruta_generado = NULL
            WHERE id_planilla_historica = ?
        """
        cursor.execute(sql_update_cabecera, (
            datos['anio'], datos['mes'], datos['moneda'], datos['total_ingresos'], datos['total_descuentos'], datos['monto_neto'],
            datos.get('cargo'), datos.get('unidad'), datos.get('nivel'), datos.get('regimen'),
            datos.get('condicion'), datos.get('pension'), datos.get('dias_laborados', 30), datos.get('faltas', 0), datos.get('observaciones'),
            id_planilla
        ))
        
        # 2. Reemplazo de Conceptos (Borrar y Volver a Insertar)
        cursor.execute("DELETE FROM Planillas_Historicas_Conceptos WHERE id_planilla_historica = ?", (id_planilla,))
        
        sql_insert_conceptos = """
            INSERT INTO Planillas_Historicas_Conceptos (id_planilla_historica, tipo_concepto, descripcion_concepto, monto) 
            VALUES (?, ?, ?, ?)
        """
        for c in datos.get('conceptos', []):
            monto_valor = float(c.get('monto') or 0)
            cursor.execute(sql_insert_conceptos, (id_planilla, c['tipo'], c['descripcion'], monto_valor))

        # 🛡️ BLOQUE DE AUDITORÍA: Registro de la Modificación
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                msj = (f"Actualizó planilla histórica ID: {id_planilla} de {nombre_trabajador} "
                       f"(Periodo: {datos['mes']}/{datos['anio']}). Nuevo Neto: {datos['monto_neto']}")
                
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Planillas',
                    accion='ACTUALIZAR_PLANILLA_HISTORICA',
                    descripcion=msj
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Actualizar Planilla): {audit_err}")
            
        conexion.commit()
        return jsonify({"estado": "ok", "mensaje": "Cambios guardados y auditoría registrada."})

    except Exception as e:
        if conexion: conexion.rollback()
        current_app.logger.error(f"Error crítico al actualizar planilla {id_planilla}: {str(e)}")
        return jsonify({"estado": "error", "mensaje": f"Falla al actualizar: {str(e)}"}), 500
    finally:
        if conexion:
            cursor.close()
            conexion.close()


# 10. GENERAR RECONSTRUCCIÓN DIGITAL (El PDF Moderno)
from flask import Response, current_app, render_template, request, jsonify
from io import BytesIO
from xhtml2pdf import pisa
import base64
import os
import traceback
from datetime import datetime

@legajo_bp.route('/generar_pdf_historico/<int:id_planilla>', methods=['GET', 'POST']) # 🚀 CAMBIO: Acepta ambos
@login_required
@role_required('AdministradorLegajos', 'Sistemas')
def generar_pdf_historico(id_planilla):
    conn_r = None
    conn_w = None
    try:
        conn_r = get_db_read()
        cursor_r = conn_r.cursor()
        
        # 1. OBTENER DATOS DE LA CABECERA
        sql_cabecera = """
            SELECT p.dni, p.nombres, p.apellidos, 
                   h.anio, h.mes, h.tipo_moneda, h.total_ingresos, h.total_descuentos, h.monto_neto,
                   h.cargo_historico, h.unidad_historica, h.nivel_historico, h.regimen_historico,
                   h.condicion_historica, h.pension_historica, h.dias_laborados, h.faltas, h.observaciones
            FROM Planillas_Historicas h
            INNER JOIN personal p ON h.id_personal = p.id_personal
            WHERE h.id_planilla_historica = ?
        """
        cursor_r.execute(sql_cabecera, (id_planilla,))
        row = cursor_r.fetchone()
        if not row: 
            return jsonify({"estado": "error", "mensaje": "Planilla no encontrada"}), 404
            
        dni, nom, ape, anio, mes, moneda, t_ing, t_desc, neto, cargo, unidad, nivel, regimen, condicion, pension, dias, faltas, obs = row

        # 2. OBTENER CONCEPTOS
        cursor_r.execute("SELECT tipo_concepto, descripcion_concepto, monto FROM Planillas_Historicas_Conceptos WHERE id_planilla_historica = ?", (id_planilla,))
        filas_conceptos = cursor_r.fetchall()
        
        ingresos_list = [{"descripcion": c[1], "monto": float(c[2] or 0)} for c in filas_conceptos if c[0] == 'INGRESO']
        descuentos_list = [{"descripcion": c[1], "monto": float(c[2] or 0)} for c in filas_conceptos if c[0] == 'DESCUENTO']
        aportes_list = [{"descripcion": c[1], "monto": float(c[2] or 0)} for c in filas_conceptos if c[0] == 'APORTE']
        excep_list = [{"descripcion": c[1], "monto": float(c[2] or 0)} for c in filas_conceptos if c[0] == 'EXCEPCIONAL']
        
        t_aportes = sum(item['monto'] for item in aportes_list)
        t_excep = sum(item['monto'] for item in excep_list)
        cursor_r.close()
        conn_r.close()

        # 3. PREPARAR LOGO
        ruta_logo = os.path.join(current_app.root_path, 'presentation', 'static', 'img', 'muni_logo.png')
        logo_b64 = ""
        if os.path.exists(ruta_logo):
            with open(ruta_logo, "rb") as f: 
                logo_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode('utf-8')

        simbolo = "S/." if moneda in ["Soles", "Nuevos Soles", "Soles de Oro"] else "I/."

        # 4. RENDERIZAR HTML PARA PDF
        html_pdf = render_template('admin/boleta_historica_pdf.html',
            d={
                'nombre_completo': f"{ape}, {nom}", 
                'dni_trabajador': dni, 
                'cargo_actual': cargo or '---', 
                'oficina_nombre': unidad or '---', 
                'nivel_remunerativo': nivel or '---',
                'fecha_ingreso_fmt': '---', 
                'sistema_pensionario': pension or '---', 
                'nocuenta': '---', 
                'condicion_laboral': condicion or '---', 
                'mes': str(mes).upper(), 
                'anio': anio, 
                'regimen_laboral': regimen or '---',
                'dias_laborados': dias if dias is not None else 30,
                'faltas': faltas if faltas is not None else 0,
                'observaciones': obs or ''
            },
            ingresos=ingresos_list, descuentos=descuentos_list, aportes=aportes_list, excepcionales=excep_list,
            t_ing=float(t_ing or 0), t_desc=float(t_desc or 0), t_aportes=t_aportes, t_excep=t_excep,
            neto=float(neto or 0), simbolo=simbolo, logo_path=logo_b64, 
            fecha_hoy=datetime.now().strftime("%d/%m/%Y")
        )

        # 5. GENERAR PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(src=html_pdf, dest=pdf_buffer)
        if pisa_status.err: return jsonify({"estado": "error"}), 500
        pdf_content = pdf_buffer.getvalue()

        # 6. GUARDAR COPIA FÍSICA (Necesario para el servidor)
        nombre_archivo = f"HISTORICO_{dni}_{anio}_{mes}.pdf"
        folder = os.path.join(current_app.root_path, 'presentation', 'static', 'uploads', 'historicos')
        os.makedirs(folder, exist_ok=True)
        ruta_fisica = os.path.join(folder, nombre_archivo)
        with open(ruta_fisica, 'wb') as f: f.write(pdf_content)

        # ACTUALIZAR RUTA EN BD
        conn_w = get_db_write()
        cursor_w = conn_w.cursor()
        cursor_w.execute("UPDATE Planillas_Historicas SET ruta_generado = ? WHERE id_planilla_historica = ?", 
                         (f"uploads/historicos/{nombre_archivo}", id_planilla))
        conn_w.commit()
        cursor_w.close()
        conn_w.close()

        # 🚀 7. LÓGICA DE RESPUESTA INTELIGENTE
        if request.method == 'POST':
            # Si es POST (desde el botón Guardar/Digitalizar), respondemos OK para que el spinner pare.
            return jsonify({"estado": "ok"})
        else:
            # Si es GET (desde el botón Extraer Copia), enviamos el archivo PDF a la pantalla.
            from flask import Response
            return Response(
                pdf_content,
                mimetype='application/pdf',
                headers={"Content-Disposition": f"inline; filename={nombre_archivo}"}
            )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"estado": "error", "mensaje": str(e)}), 500


# Asegúrate de importar el repositorio si no lo está:
from app.infrastructure.persistence.planilla_repository import PlanillaRepository
# (Asumo que ya tienes 'current_user' importado arriba: from flask_login import current_user)

@legajo_bp.route('/configuracion/catalogo-presupuestal', methods=['GET', 'POST'])
@login_required
@role_required('AdministradorLegajos', 'AdministradorEscalafon', 'Sistemas') 
def catalogo_presupuestal():
    repo = PlanillaRepository()
    
    if request.method == 'POST':
        # Capturamos los datos que manda el HTML
        nueva_config = {
            'np': request.form.get('np_codigo'),
            'actividad': request.form.get('actividad_nombre'),
            'meta': request.form.get('meta_codigo'),
            'anio': 2026 # Podrías sacarlo de un input también
        }
        
        # 🔥 EL CAMBIO CRÍTICO ESTÁ AQUÍ: Pasamos current_user.username para el Log de Auditoría
        if repo.guardar_presupuesto_config(nueva_config, current_user.username):
            
            # ---------------------------------------------------------
            # 🛡️ BLOQUE DE AUDITORÍA (Creación de Catálogo)
            # ---------------------------------------------------------
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    np_cod = nueva_config.get('np', 'N/A')
                    act = nueva_config.get('actividad', 'N/A')
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='Catálogo Presupuestal',
                        accion='NUEVA_CONFIGURACION',
                        descripcion=f"Añadió nueva configuración al catálogo: NP {np_cod} - {act}."
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error en auditoría (Crear Catálogo): {audit_err}")
            # ---------------------------------------------------------

            flash("✅ Configuración añadida al catálogo exitosamente.", "success")
        else:
            flash("❌ Hubo un error al intentar guardar la configuración.", "danger")
            
        return redirect(url_for('legajo.catalogo_presupuestal'))

    # Si es GET (solo entrar a ver), listamos los datos
    configs = repo.obtener_presupuesto_configs()
    return render_template('admin/config_presupuesto.html', configs=configs)

# --- Ruta para el botón Eliminar ---
# --- Ruta para el botón Eliminar ---
@legajo_bp.route('/configuracion/catalogo-presupuestal/eliminar/<int:id_config>', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'AdministradorEscalafon', 'Sistemas') 
def eliminar_catalogo_presupuestal(id_config):
    repo = PlanillaRepository()
    
    # 🔥 Le pasamos current_user.username a la función para la auditoría interna
    resultado = repo.eliminar_presupuesto_config(id_config, current_user.username)
    
    # 🚀 CORRECCIÓN: Registramos en auditoría tanto si se ELIMINÓ ('success') 
    # como si se OCULTÓ/INACTIVÓ por estar en uso ('warning')
    estado_res = resultado.get('estado')
    
    if estado_res in ['success', 'warning']:
        # ---------------------------------------------------------
        # 🛡️ BLOQUE DE AUDITORÍA (Eliminación o Baja de Catálogo)
        # ---------------------------------------------------------
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                # Dinamizamos la acción según lo que realmente pasó
                accion_auditoria = 'ELIMINAR_CONFIGURACION' if estado_res == 'success' else 'OCULTAR_CONFIGURACION'
                
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='Catálogo Presupuestal',
                    accion=accion_auditoria,
                    # Usamos el mismo mensaje inteligente que te devolvió el repositorio
                    descripcion=f"{resultado.get('mensaje')} (ID Config: {id_config})"
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error en auditoría (Eliminar Catálogo): {audit_err}")
        # ---------------------------------------------------------

    flash(resultado['mensaje'], resultado['estado'])
    return redirect(url_for('legajo.catalogo_presupuestal'))