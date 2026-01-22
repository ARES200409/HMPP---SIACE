from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, jsonify, send_file
from flask_login import current_user, login_required
from app.decorators import role_required
from datetime import datetime
from app.application.forms import FiltroPersonalForm, DocumentoForm

# CORRECCIÓN VITAL: Importamos 'db' que es el alias de get_db_write definido en __init__.py
from app.database import db

# Creamos el Blueprint para el rol de RRHH
rrhh_bp = Blueprint('rrhh', __name__, url_prefix='/rrhh')

@rrhh_bp.route('/inicio_rrhh')
@login_required
@role_required('RRHH')
def inicio_rrhh():
    """Dashboard principal para el rol de Recursos Humanos."""
    return render_template('rrhh/inicio_rrhh.html', user=current_user)

@rrhh_bp.route('/personal')
@login_required
@role_required('RRHH')
def listar_personal():
    """Listado de legajos para RRHH."""
    form = FiltroPersonalForm(request.args)
    page = request.args.get('page', 1, type=int)
    filters = {'dni': form.dni.data, 'nombres': form.nombres.data}

    legajo_service = current_app.config['LEGAJO_SERVICE']
    pagination = legajo_service.get_all_personal_paginated(page, 15, filters)
    document_status = legajo_service.check_document_status_for_all_personal()

    return render_template(
        'rrhh/listar_personal.html',
        form=form,
        pagination=pagination,
        document_status=document_status
    )

@rrhh_bp.route('/personal/<int:personal_id>')
@login_required
@role_required('RRHH')
def ver_legajo(personal_id):
    """Vista de detalle de legajo para RRHH."""
    legajo_service = current_app.config['LEGAJO_SERVICE']
    try:
        legajo_completo = legajo_service.get_personal_details(personal_id, current_user)
    except PermissionError as e:
        flash(str(e), 'danger')
        return redirect(url_for('rrhh.listar_personal'))
    except Exception as e:
        current_app.logger.error(f"Error al ver legajo {personal_id}: {e}")
        flash("Ocurrió un error al cargar el legajo.", "danger")
        return redirect(url_for('rrhh.listar_personal'))

    if not legajo_completo or not legajo_completo.get('personal'):
        flash('El legajo solicitado no existe.', 'danger')
        return redirect(url_for('rrhh.listar_personal'))

    form_documento = DocumentoForm()
    secciones = legajo_service.get_secciones_for_select()
    form_documento.id_seccion.choices = [('0', '-- Seleccione Sección --')] + secciones if secciones else [('0', 'No hay secciones disponibles')]
    form_documento.id_tipo.choices = [('0', '-- Seleccione Tipo --')]

    return render_template(
        'rrhh/ver_legajo_completo.html',
        legajo=legajo_completo,
        form_documento=form_documento,
        legajo_service=legajo_service,
        today=datetime.now().date()
    )

@rrhh_bp.route('/reporte/empleados/excel')
@login_required
@role_required('RRHH')
def exportar_empleados_excel():
    """Exporta la lista de empleados a Excel."""
    legajo_service = current_app.config['LEGAJO_SERVICE']
    excel_stream = legajo_service.generate_general_report_excel()

    return send_file(
        excel_stream,
        download_name="reporte_empleados.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@rrhh_bp.route('/panel')
@login_required
def panel_rrhh():
    """Gráficos y estadísticas para RRHH."""
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        empleados_unidad = legajo_service.get_empleados_por_unidad() or []
        empleados_estado = legajo_service.get_empleados_activos_inactivos() or []
        empleados_sexo = legajo_service.get_empleados_por_sexo() or []
    except Exception as e:
        current_app.logger.error(f"Error en panel RRHH: {e}")
        empleados_unidad, empleados_estado, empleados_sexo = [], [], []
        flash('No se pudieron cargar las estadísticas.', 'warning')

    return render_template(
        'rrhh/panel.html',
        empleados_unidad=empleados_unidad,
        empleados_estado=empleados_estado,
        empleados_sexo=empleados_sexo
    )

@rrhh_bp.route('/personal/cambiar_estado/<int:personal_id>', methods=['POST'])
@login_required
@role_required('RRHH')
def cambiar_estado_laboral(personal_id):
    """Cambia el estado activo/inactivo usando el procedimiento sp_cambiar_estado_laboral."""
    data = request.get_json()
    nuevo_estado = data.get('estado')

    try:
        # Ahora 'db' está correctamente definido como la función de conexión
        conn = db() 
        cursor = conn.cursor()
        
        # Ejecutamos el procedimiento almacenado
        cursor.execute("EXEC sp_cambiar_estado_laboral ?, ?", (personal_id, nuevo_estado))
        conn.commit() 
        
        return jsonify({'success': True, 'message': 'Estado actualizado en la HMPP.'})
    except Exception as e:
        current_app.logger.error(f"Error al cambiar estado: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500