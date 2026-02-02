# app/presentation/routes/pdf_upload_routes.py
"""
Rutas para carga masiva y separación de PDFs de legajos.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from app.application.services.pdf_split_service import PdfSplitService
from app.core.security import IDORProtection
from werkzeug.utils import secure_filename
import os
import logging

logger = logging.getLogger(__name__)

pdf_bp = Blueprint('pdf', __name__, url_prefix='/pdf')


@pdf_bp.route('/api/debug', methods=['GET'])
@login_required
def debug_info():
    """
    Endpoint de debugging para verificar estado de servicios
    """
    return jsonify({
        'user': current_user.username,
        'rol': current_user.rol,
        'legajo_service': 'OK' if current_app.config.get('LEGAJO_SERVICE') else 'MISSING',
        'personal_repository': 'OK' if current_app.config.get('PERSONAL_REPOSITORY') else 'MISSING',
    })


@pdf_bp.route('/api/personal-list', methods=['GET'])
@login_required
def get_personal_list():
    """
    API endpoint que retorna lista de personal disponible para asociar al PDF.
    Retorna JSON con estructura: [{'id': ..., 'nombre': '...', 'dni': '...'}]
    """
    try:
        from app.database.connector import get_db_read
        from app.infrastructure.persistence.sqlserver_repository import _row_to_dict
        
        # Obtener conexión directa para consulta simple
        conn = get_db_read()
        cursor = conn.cursor()
        
        # Consulta SQL simple para traer personal activo
        query = """
            SELECT 
                id_personal,
                nombres,
                apellidos,
                dni
            FROM personal
            WHERE activo = 1
            ORDER BY apellidos, nombres
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            logger.info(f"Lista de personal vacía para usuario: {current_user.username}")
            return jsonify([])
        
        # Formatear para el frontend
        result = []
        for row in rows:
            try:
                row_dict = _row_to_dict(cursor, row)
                
                p_id = row_dict.get('id_personal')
                p_nombres = row_dict.get('nombres', '')
                p_apellidos = row_dict.get('apellidos', '')
                p_dni = row_dict.get('dni', 'N/A')
                
                nombre_completo = f"{p_apellidos}, {p_nombres}".strip() if p_apellidos and p_nombres else p_nombres
                
                item = {
                    'id': p_id,
                    'nombre': nombre_completo if nombre_completo else 'N/A',
                    'dni': p_dni if p_dni else 'N/A'
                }
                
                if item['id']:  # Solo agregar si tiene ID válido
                    result.append(item)
                    
            except Exception as item_err:
                logger.warning(f"Error procesando personal: {item_err}")
                continue
        
        logger.info(f"Retornando {len(result)} personal para carga de PDF (usuario: {current_user.username})")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error obteniendo lista de personal: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@pdf_bp.route('/api/estructura-personal/<int:id_personal>', methods=['GET'])
@login_required
def get_estructura_personal(id_personal):
    """
    API endpoint que retorna la estructura de legajo personalizada para un personal.
    Primero intenta obtener estructura personalizada, si no existe retorna la por defecto.
    Retorna JSON con estructura: {'estructura': {'nombre_doc': [pagina_inicio, pagina_fin], ...}}
    """
    try:
        personal_repo = current_app.config.get('PERSONAL_REPOSITORY')
        
        if not personal_repo:
            # Retornar estructura por defecto si no hay repositorio
            return jsonify({'estructura': ESTRUCTURA_LEGAJO_DEFAULT})
        
        response_data = {
            'exito': True,  # <--- IMPORTANTE: El JS espera este campo
            'estructura': ESTRUCTURA_LEGAJO_DEFAULT
        }
        # Intentar obtener estructura personalizada si existe el método
        if not personal_repo:
            return jsonify(response_data)
        
        # Intentar obtener estructura personalizada
        estructura_personalizada = None
        if hasattr(personal_repo, 'get_estructura_legajo'):
            try:
                estructura_personalizada = personal_repo.get_estructura_legajo(id_personal)
            except Exception as e:
                logger.warning(f"No se pudo obtener estructura personalizada: {e}")
        
        if estructura_personalizada:
            logger.info(f"Usando estructura personalizada para personal {id_personal}")
            response_data['estructura'] = estructura_personalizada
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error obteniendo estructura de personal: {e}", exc_info=True)
        # En caso de error, devolvemos default pero con éxito para que el front no falle
        return jsonify({
            'exito': True, 
            'estructura': ESTRUCTURA_LEGAJO_DEFAULT,
            'error': str(e)
        })


# Estructura por defecto para legajos
ESTRUCTURA_LEGAJO_DEFAULT = {
    "01": {
        "id_seccion": 1,
        "tipo_documento": "DNI",
        "descripcion": "Cédula de Identidad",
        "pagina_inicio": 1,
        "pagina_fin": 1,
    },
    "02": {
        "id_seccion": 2,
        "tipo_documento": "Curriculum",
        "descripcion": "Currículum Vitae",
        "pagina_inicio": 2,
        "pagina_fin": 5,
    },
    "03": {
        "id_seccion": 3,
        "tipo_documento": "Titulo",
        "descripcion": "Título Universitario",
        "pagina_inicio": 6,
        "pagina_fin": 6,
    },
    "04": {
        "id_seccion": 4,
        "tipo_documento": "Contrato",
        "descripcion": "Contrato Laboral",
        "pagina_inicio": 7,
        "pagina_fin": 12,
    },
    "05": {
        "id_seccion": 5,
        "tipo_documento": "Antecedentes",
        "descripcion": "Antecedentes Penales",
        "pagina_inicio": 13,
        "pagina_fin": 14,
    },
    "06": {
        "id_seccion": 6,
        "tipo_documento": "Carnet",
        "descripcion": "Carnet Sanitario",
        "pagina_inicio": 15,
        "pagina_fin": 15,
    },
    "07": {
        "id_seccion": 7,
        "tipo_documento": "Licencias",
        "descripcion": "Licencias Profesionales",
        "pagina_inicio": 16,
        "pagina_fin": 20,
    },
}


@pdf_bp.route('/upload', methods=['GET', 'POST'])
@pdf_bp.route('/upload/<int:personal_id>', methods=['GET', 'POST'])
@login_required
def upload_legajo_pdf(personal_id=None):
    """
    Permite cargar un PDF completo de legajo y separarlo automáticamente
    en documentos individuales, asociándolos a un personal específico.
    """
    # Solo AdministradorLegajos y Sistemas pueden hacer esto
    if current_user.rol not in ('AdministradorLegajos', 'Sistemas'):
        flash('No tienes permiso para acceder a esta función.', 'danger')
        return redirect(url_for('rrhh.inicio_rrhh'))

    # Si intenta acceder sin personal_id, redirije a "Consultar Legajo"
    if not personal_id:
        flash('Accede a esta función desde la página del legajo.', 'info')
        return redirect(url_for('legajo.listar_personal'))
    
    # SEGURIDAD: Validar IDOR
    if not IDORProtection.can_access_personal(current_user.id, personal_id, current_user.rol):
        logger.warning(f"SEGURIDAD: Intento IDOR detectado - Usuario {current_user.id} intenta acceder a personal {personal_id}")
        flash('No tienes permiso para acceder a este personal.', 'danger')
        return redirect(url_for('legajo.listar_personal'))

    legajo_service = current_app.config.get('LEGAJO_SERVICE')
    personal_repo = current_app.config.get('PERSONAL_REPOSITORY')

    if request.method == 'POST':
        try:
            # Verificar que se envió un archivo
            if 'archivo_pdf' not in request.files:
                flash('No se seleccionó ningún archivo.', 'warning')
                return redirect(request.url)

            file = request.files['archivo_pdf']
            if file.filename == '':
                flash('No se seleccionó ningún archivo.', 'warning')
                return redirect(request.url)

            # Obtener el ID del personal
            id_personal = personal_id
            if not id_personal:
                flash('Debes seleccionar un personal.', 'warning')
                return redirect(request.url)

            # Validar que sea un PDF
            if not file.filename.lower().endswith('.pdf'):
                from app.utils.error_handler import registrar_error_automatico
                try:
                    raise ValueError(f"SEGURIDAD PDF: Intento de cargar {file.filename} (No es PDF)")
                except ValueError as ve:
                    registrar_error_automatico(ve)
                flash('Solo se aceptan archivos PDF.', 'danger')
                return redirect(request.url)

            # Guardar el archivo temporalmente
            filename = secure_filename(file.filename)
            temp_dir = current_app.config.get('TEMP_UPLOADS_DIR', 'temp_uploads')
            temp_path = os.path.join(temp_dir, filename)
            os.makedirs(temp_dir, exist_ok=True)
            file.save(temp_path)

            logger.info(f"PDF cargado: {temp_path} para personal ID {id_personal}")

            # Obtener la estructura personalizada
            estructura_a_usar = ESTRUCTURA_LEGAJO_DEFAULT
            
            # PRIMERO: intentar obtener la estructura enviada en el formulario
            estructura_enviada = request.form.get('estructura_json')
            
            if estructura_enviada and estructura_enviada != '{}':
                try:
                    import json
                    estructura_a_usar = json.loads(estructura_enviada)
                    if not isinstance(estructura_a_usar, dict):
                        raise ValueError("Estructura debe ser un objeto JSON")
                    logger.info(f"Usando estructura personalizada recibida del cliente para personal {id_personal}")
                except Exception as e:
                    logger.warning(f"Error validando estructura enviada: {e}, usando por defecto")
                    estructura_a_usar = ESTRUCTURA_LEGAJO_DEFAULT
            
            # SEGUNDA OPCIÓN: Si no vino en el formulario, obtener de la BD
            if not estructura_a_usar or estructura_a_usar == ESTRUCTURA_LEGAJO_DEFAULT:
                try:
                    from app.infrastructure.persistence.estructura_repository import EstructuraRepository
                    estructura_bd = EstructuraRepository.obtener_estructura_json(id_personal)
                    if estructura_bd:
                        estructura_a_usar = estructura_bd
                except Exception as e:
                    logger.warning(f"Error obteniendo estructura de BD: {e}, usando por defecto")
                    estructura_a_usar = ESTRUCTURA_LEGAJO_DEFAULT

            # Usar el servicio de separación
            temp_pdfs_dir = current_app.config.get('TEMP_PDFS_DIR', 'temp_pdfs')
            pdf_service = PdfSplitService(temp_pdfs_dir)
            resultados = pdf_service.separar_legajo(
                temp_path, 
                estructura_a_usar, 
                id_personal
            )

            if 'error' in resultados:
                flash(f"Error al procesar PDF: {resultados['error']}", 'danger')
                return redirect(request.url)

            # Obtener la fecha de emisión del formulario
            fecha_emision_str = request.form.get('fecha_emision')
            fecha_emision = None
            if fecha_emision_str:
                try:
                    from datetime import datetime
                    fecha_emision = datetime.strptime(fecha_emision_str, '%Y-%m-%d').date()
                    logger.info(f"Usando fecha de emisión del formulario: {fecha_emision}")
                except ValueError:
                    logger.warning(f"Fecha inválida: {fecha_emision_str}, se usará fecha actual")
                    fecha_emision = None

            documentos_guardados = 0
            
            for nombre_doc, info in resultados.items():
                # Verificar que el documento se separó exitosamente
                if isinstance(info, dict) and info.get('exito') == True:
                    archivo_path = info.get('archivo')
                    nombre_archivo = info.get('nombre_archivo')
                    
                    # --- CORRECCIÓN DE DESCRIPCIÓN ---
                    tipo_documento = None
                    id_seccion = None
                    descripcion_real = None

                    # Buscar en estructura personalizada
                    for doc_key, doc_info in estructura_a_usar.items():
                        if doc_key == nombre_doc:
                            if isinstance(doc_info, dict):
                                tipo_documento = doc_info.get('tipo_documento', nombre_doc)
                                id_seccion = doc_info.get('id_seccion')
                                descripcion_real = doc_info.get('descripcion') # Capturamos descripción
                            break
                    
                    # Fallback a estructura por defecto
                    if not tipo_documento:
                        for doc_key, doc_info in ESTRUCTURA_LEGAJO_DEFAULT.items():
                            if doc_key == nombre_doc:
                                tipo_documento = doc_info.get('tipo_documento', nombre_doc)
                                id_seccion = doc_info.get('id_seccion')
                                descripcion_real = doc_info.get('descripcion')
                                break
                    
                    if not tipo_documento:
                        tipo_documento = nombre_doc
                        
                    # Si no se encontró descripción, usar una genérica
                    if not descripcion_real:
                        descripcion_real = f"Documento: {nombre_doc}"

                    try:
                        with open(archivo_path, 'rb') as f:
                            archivo_binario = f.read()
                        
                        # Buscar ID del tipo de documento
                        id_tipo_documento = None
                        try:
                            tipos_disponibles = personal_repo.get_tipos_documento_for_select() if personal_repo else []
                            
                            # 1. Búsqueda exacta
                            for tipo_id, tipo_nombre in tipos_disponibles:
                                if tipo_nombre.lower() == tipo_documento.lower():
                                    id_tipo_documento = tipo_id
                                    break
                            
                            # 2. Búsqueda parcial
                            if not id_tipo_documento:
                                for tipo_id, tipo_nombre in tipos_disponibles:
                                    if tipo_documento.lower() in tipo_nombre.lower() or tipo_nombre.lower() in tipo_documento.lower():
                                        id_tipo_documento = tipo_id
                                        break
                                        
                            # 3. Default
                            if not id_tipo_documento and tipos_disponibles:
                                id_tipo_documento = tipos_disponibles[0][0]
                        
                        except Exception as e:
                            logger.error(f"Error buscando tipo doc: {e}")

                        if not id_tipo_documento:
                            # Valor fallback seguro si falla todo
                            id_tipo_documento = 1 

                        # Guardar en BD con la descripción correcta
                        form_data = {
                            'id_personal': id_personal,
                            'id_tipo': id_tipo_documento,
                            'id_seccion': id_seccion if id_seccion else 1,
                            'nombre_archivo': nombre_archivo,
                            'fecha_emision': fecha_emision,  # Usa la fecha del formulario
                            'fecha_vencimiento': None,
                            'descripcion': descripcion_real,
                            'hash_archivo': None,
                        }
                        
                        # Wrapper para simular FileStorage
                        class FileStreamWrapper:
                            def __init__(self, filename, stream):
                                self.filename = filename
                                self.stream = stream
                            def read(self): return self.stream
                            def seek(self, pos): pass
                        
                        file_obj = FileStreamWrapper(nombre_archivo, archivo_binario)
                        
                        if legajo_service:
                            legajo_service.upload_document_to_personal(form_data, file_obj, current_user.id)
                            documentos_guardados += 1
                        
                    except Exception as e:
                        logger.error(f"Error guardando documento {nombre_doc}: {e}")

            # Limpiar temporal
            if os.path.exists(temp_path):
                os.remove(temp_path)

            flash(f'PDF procesado exitosamente. {documentos_guardados} documentos separados y guardados.', 'success')
            return redirect(url_for('legajo.listar_personal'))

        except Exception as e:
            logger.error(f"Error en upload_legajo_pdf: {e}", exc_info=True)
            flash('Error al procesar el PDF.', 'danger')
            return redirect(request.url)

    # GET: Redirije si no es POST
    if personal_id:
        return redirect(url_for('legajo.ver_legajo', personal_id=personal_id))
    else:
        return redirect(url_for('legajo.listar_personal'))


@pdf_bp.route('/api/procesar', methods=['POST'])
@login_required
def procesar_pdf_api():
    """
    Endpoint API para procesar un PDF y retornar JSON con los resultados.
    """
    if current_user.rol not in ['Sistemas', 'RRHH', 'AdministradorLegajos']:
        return jsonify({'error': 'Permiso denegado'}), 403

    try:
        # Verificar que se envió un archivo
        if 'pdf_file' not in request.files:
            return jsonify({'error': 'No se seleccionó archivo'}), 400

        file = request.files['pdf_file']
        id_personal = request.form.get('id_personal')

        if not file or not id_personal:
            return jsonify({'error': 'Archivo o personal no especificado'}), 400

        # Guardar temporalmente
        filename = secure_filename(file.filename)
        temp_dir = current_app.config.get('TEMP_UPLOADS_DIR', 'temp_uploads')
        temp_path = os.path.join(temp_dir, filename)
        os.makedirs(temp_dir, exist_ok=True)
        file.save(temp_path)

        # Procesar
        temp_pdfs_dir = current_app.config.get('TEMP_PDFS_DIR', 'temp_pdfs')
        pdf_service = PdfSplitService(temp_pdfs_dir)
        resultados = pdf_service.separar_legajo(
            temp_path,
            ESTRUCTURA_LEGAJO_DEFAULT,
            id_personal
        )

        # Limpiar
        os.remove(temp_path)

        # Retornar JSON
        return jsonify({
            'success': True,
            'documentos': resultados,
            'total': len([r for r in resultados.values() if r.get('exito')])
        })

    except Exception as e:
        logger.error(f"Error en procesar_pdf_api: {e}")
        return jsonify({'error': str(e)}), 500
