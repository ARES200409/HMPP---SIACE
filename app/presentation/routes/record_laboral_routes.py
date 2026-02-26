from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from datetime import datetime
from app.application.forms import DocumentoForm
from flask_login import login_required
from app.infrastructure.persistence.sqlserver_repository import SqlServerPersonalRepository
from werkzeug.utils import secure_filename
from io import BytesIO
from app.database import get_db_read, get_db_write

record_laboral_bp = Blueprint('record_laboral', __name__, url_prefix='/record-laboral')
repo = SqlServerPersonalRepository()

@record_laboral_bp.route('/nuevo/<int:id_personal>', methods=['GET', 'POST'])
@login_required 
def registrar_record(id_personal):
    """
    Gestiona el Récord Laboral. 
    Se eliminaron los cierres manuales de conexión para evitar el error 'closed connection'.
    """
    form = DocumentoForm()
    personal = repo.get_personal_by_id(id_personal)
    
    if not personal:
        flash("Trabajador no encontrado en el sistema.", "danger")
        return redirect(url_for('rrhh.listar_personal'))

    # --- REGISTRO DE DOCUMENTOS (POST) ---
    if request.method == 'POST' and form.validate_on_submit():
        if not personal.get('activo'):
            flash("No se pueden registrar datos a un trabajador CESADO.", "warning")
            return redirect(url_for('record_laboral.registrar_record', id_personal=id_personal))
            
        archivo = form.archivo.data
        if archivo:
            filename = secure_filename(archivo.filename)
            file_bytes = archivo.read()
            
            doc_data = {
                'id_personal': id_personal,
                'id_tipo': form.id_tipo.data,
                'nombre_archivo': filename, 
                'descripcion': form.descripcion.data or "Actualización de Contrato",
                'fecha_inicio': form.fecha_emision.data,
                'fecha_fin': request.form.get('fecha_fin_vencimiento'),
                'fecha_registro': datetime.now() 
            }
            if repo.add_record_laboral(doc_data, file_bytes):
                flash("Documento guardado exitosamente.", "success")
                return redirect(url_for('record_laboral.registrar_record', id_personal=id_personal))

    # =========================================================
    # 3. CONSULTA DE CONTRATOS (USANDO TUS COLUMNAS REALES)
    # =========================================================
    contratos_lista = []
    try:
        conn = get_db_read()
        cursor = conn.cursor()
        
        # Usamos tus nombres de columna reales según la tabla proporcionada
        cursor.execute("""
            SELECT 
                id_contrato, 
                fecha_inicio, 
                fecha_fin, 
                sueldo, 
                resolucion,
                nombre_archivo_real as nombre_archivo, 
                fecha_registro_auditoria as fecha_registro 
            FROM contratos 
            WHERE id_personal = ? 
            ORDER BY ISNULL(fecha_registro_auditoria, fecha_inicio) DESC
        """, (id_personal,))
        
        columns = [column[0] for column in cursor.description]
        contratos_lista = [dict(zip(columns, row)) for row in cursor.fetchall()]
        # ❌ ELIMINADO: conn.close() - Dejamos que Flask lo maneje al final del request
            
    except Exception as e:
        print(f"🔥 ERROR SQL EN CONTRATOS: {e}") 
        current_app.logger.error(f"Error cargando contratos: {e}")

    # =========================================================
    # 4. RÉGIMEN LABORAL (HARDCODED PARA EVITAR ERRORES DE TABLA)
    # =========================================================
    id_tipo = int(personal.get('id_tipo_contrato') or 0)
    
    regimenes = {
        1: "D.L. 1057 (CAS)", 
        2: "D.L. 276 (Nombrado)", 
        3: "D.L. 728", 
        4: "Locación de Servicios", 
        5: "CAS Confianza"
    }
    personal['regimen_laboral'] = regimenes.get(id_tipo, "Sin asignar")

    return render_template(
        'record_laboral/formulario.html',
        form=form,
        personal=personal,
        documentos=repo.get_records_by_personal(id_personal),
        contratos=contratos_lista,
        hoy=datetime.now().date(),
        titulo=f"Récord Laboral: {personal['apellidos']} {personal['nombres']}"
    )

@record_laboral_bp.route('/eliminar/<int:id_record>/<int:id_personal>', methods=['POST'])
@login_required
def eliminar_record(id_record, id_personal):
    if repo.delete_record_laboral(id_record):
        flash("Registro eliminado de la bitácora de RRHH.", "info")
    else:
        flash("No se pudo eliminar el registro seleccionado.", "danger")
    return redirect(url_for('record_laboral.registrar_record', id_personal=id_personal))

@record_laboral_bp.route('/ver-archivo/<int:id_record>')
@login_required
def visualizar_archivo(id_record):
    try:
        archivo = repo.get_record_file_by_id(id_record)
        if not archivo or not archivo['contenido']:
            flash("El archivo no se encuentra en el servidor de la HMPP.", "warning")
            return redirect(request.referrer)

        # SOLUCIÓN PDF: Añadir mimetype='application/pdf'
        return send_file(
            BytesIO(archivo['contenido']),
            download_name=archivo['nombre_archivo'] or 'documento.pdf',
            as_attachment=False,
            mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Error en visualización de récord: {str(e)}")
        flash("Error interno al cargar el documento.", "danger")
        return redirect(request.referrer)

@record_laboral_bp.route('/eliminar-contrato/<int:id_contrato>/<int:id_personal>', methods=['POST'])
@login_required
def eliminar_contrato(id_contrato, id_personal):
    try:
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contratos WHERE id_contrato = ?", (id_contrato,))
        conn.commit()
        conn.close()
        flash("Contrato eliminado correctamente del historial.", "success")
    except Exception as e:
        current_app.logger.error(f"Error al eliminar contrato: {e}")
        flash("Error al intentar eliminar el contrato. Puede estar vinculado a otros registros.", "danger")
    return redirect(url_for('record_laboral.registrar_record', id_personal=id_personal))

@record_laboral_bp.route('/ver-contrato/<int:id_contrato>')
@login_required
def visualizar_contrato(id_contrato):
    """
    Recupera el archivo binario de la tabla contratos y lo muestra en el navegador.
    Corregido typo de 'id_contato' a 'id_contrato' y columnas de SQL.
    """
    try:
        conn = get_db_read()
        cursor = conn.cursor()
        
        # ✅ USAMOS TUS COLUMNAS REALES: nombre_archivo_real y archivo_binario
        # Si tu columna de PDF se llama diferente (ej: archivo_resolucion), cámbiala aquí:
        cursor.execute("""
            SELECT nombre_archivo_real, resolucion, archivo_binario 
            FROM contratos 
            WHERE id_contrato = ?
        """, (id_contrato,))
        
        row = cursor.fetchone()
        
        # Nota: No cerramos conn manualmente aquí para evitar 'closed connection'

        if not row:
            flash("❌ No se encontró el registro del contrato.", "warning")
            return redirect(request.referrer)

        pdf_data = row[2] # Columna 'archivo_binario'
        if not pdf_data:
            flash("❌ Este contrato no tiene un archivo PDF adjunto.", "info")
            return redirect(request.referrer)

        # Nombre del archivo para el navegador
        nombre_display = row[0] if row[0] else f"Resolucion_{row[1]}.pdf"

        return send_file(
            BytesIO(pdf_data),
            download_name=nombre_display,
            as_attachment=False,
            mimetype='application/pdf'
        )

    except Exception as e:
        # Imprime el error real en la terminal para que lo veas
        print(f"🔥 ERROR EN VISUALIZAR: {e}")
        flash("Error de Base de Datos al intentar abrir el archivo.", "danger")
        return redirect(request.referrer)