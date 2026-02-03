from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from datetime import datetime
from app.application.forms import DocumentoForm
# IMPORTACIÓN FALTANTE:
from flask_login import login_required
from app.infrastructure.persistence.sqlserver_repository import SqlServerPersonalRepository
from werkzeug.utils import secure_filename
from io import BytesIO
from flask import send_file

# Configuración del Blueprint con el prefijo de URL correcto
record_laboral_bp = Blueprint('record_laboral', __name__, url_prefix='/record-laboral')
repo = SqlServerPersonalRepository()

@record_laboral_bp.route('/nuevo/<int:id_personal>', methods=['GET', 'POST'])
@login_required # Ahora sí funcionará porque ya está importado arriba
def registrar_record(id_personal):
    """
    Gestiona la subida y visualización del Récord Laboral.
    Permite consulta de cesados pero bloquea nuevos registros.
    """
    form = DocumentoForm()
    
    # El repo debe estar corregido para no filtrar por 'activo=1'
    personal = repo.get_personal_by_id(id_personal)
    
    if not personal:
        flash("Trabajador no encontrado en el sistema de la HMPP.", "danger")
        return redirect(url_for('rrhh.listar_personal'))

    if request.method == 'POST':
        # Validación de seguridad: no subir documentos a cesados
        if not personal.get('activo'):
            flash("No se pueden registrar nuevos pagos a un trabajador en estado CESADO.", "warning")
            return redirect(url_for('record_laboral.registrar_record', id_personal=id_personal))
            
        if form.validate_on_submit():
            archivo = form.archivo.data
            if archivo:
                filename = secure_filename(archivo.filename)
                file_bytes = archivo.read()
                
                doc_data = {
                    'id_personal': id_personal,
                    'id_tipo': form.id_tipo.data,
                    'nombre_archivo': filename,
                    'descripcion': form.descripcion.data or "Sin descripción",
                    'fecha_inicio': form.fecha_emision.data,
                    'fecha_fin': request.form.get('fecha_fin_vencimiento')
                }

                if repo.add_record_laboral(doc_data, file_bytes):
                    flash("Documento de Récord Laboral guardado exitosamente.", "success")
                else:
                    flash("Error crítico al intentar guardar en SQL Server.", "danger")
                
                return redirect(url_for('record_laboral.registrar_record', id_personal=id_personal))

    # Consulta de historial
    documentos_tabla = repo.get_records_by_personal(id_personal)
    hoy = datetime.now().date()

    return render_template(
        'record_laboral/formulario.html',
        form=form,
        personal=personal,
        documentos=documentos_tabla,
        hoy=hoy,
        titulo=f"Récord Laboral: {personal['nombres']} {personal['apellidos']}"
    )

@record_laboral_bp.route('/eliminar/<int:id_record>/<int:id_personal>', methods=['POST'])
@login_required
def eliminar_record(id_record, id_personal):
    """Permite dar de baja un registro exclusivamente de la tabla record_laboral."""
    if repo.delete_record_laboral(id_record):
        flash("Registro eliminado de la bitácora de RRHH.", "info")
    else:
        flash("No se pudo eliminar el registro seleccionado.", "danger")
    return redirect(url_for('record_laboral.registrar_record', id_personal=id_personal))


@record_laboral_bp.route('/ver-archivo/<int:id_record>')
@login_required
def visualizar_archivo(id_record):
    """Busca el archivo en la tabla independiente y lo muestra en el navegador."""
    try:
        archivo = repo.get_record_file_by_id(id_record)
        
        if not archivo or not archivo['contenido']:
            flash("El archivo no se encuentra en el servidor de la HMPP.", "warning")
            return redirect(request.referrer)

        # Enviamos el contenido binario como un archivo para el navegador
        return send_file(
            BytesIO(archivo['contenido']),
            download_name=archivo['nombre_archivo'],
            as_attachment=False # Permite abrir PDF/Imágenes directamente
        )
    except Exception as e:
        # Ahora current_app está definido y registrará el error correctamente
        current_app.logger.error(f"Error en visualización de récord: {str(e)}")
        flash("Error interno al cargar el documento.", "danger")
        return redirect(request.referrer)