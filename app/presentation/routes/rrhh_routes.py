from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, jsonify, send_file
from flask_login import current_user, login_required
from app.decorators import role_required
from datetime import datetime
from app.application.forms import FiltroPersonalForm, DocumentoForm
from app.application.forms import ContratoInicialForm
# CORRECCIÓN VITAL: Importamos 'db' que es el alias de get_db_write definido en __init__.py
from app.database import db
from app.infrastructure.persistence.planilla_repository import PlanillaRepository
from io import BytesIO
try:
    from weasyprint import HTML  # Requisito: pip install weasyprint + GTK3 runtime
    WEASYPRINT_AVAILABLE = True
except Exception:
    HTML = None
    WEASYPRINT_AVAILABLE = False
from app.infrastructure.persistence.sqlserver_repository import SqlServerPersonalRepository
import zlib
# Creamos el Blueprint para el rol de RRHH
rrhh_bp = Blueprint('rrhh', __name__, url_prefix='/rrhh')

@rrhh_bp.route('/inicio_rrhh')
@login_required
@role_required('RRHH')
def inicio_rrhh():
    """Dashboard principal para el rol de Recursos Humanos."""
    # Instanciamos el repo para obtener el conteo de alertas
    repo = PlanillaRepository()
    num_alertas = repo.obtener_conteo_sin_contrato() # <--- Llamada al nuevo método
    
    return render_template(
        'rrhh/inicio_rrhh.html', 
        user=current_user,
        alertas_contrato=num_alertas # <--- Pasamos el dato al HTML
    )

@rrhh_bp.route('/personal')
@login_required
@role_required('RRHH')
def listar_personal():
    """Listado de legajos para RRHH."""
    form = FiltroPersonalForm(request.args)
    page = request.args.get('page', 1, type=int)
    filters = {'dni': form.dni.data, 'nombres': form.nombres.data}

    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        pagination = legajo_service.get_all_personal_paginated(page, 15, filters)
        document_status = legajo_service.check_document_status_for_all_personal()

        return render_template(
            'rrhh/listar_personal.html',
            form=form,
            pagination=pagination,
            document_status=document_status
        )
    except Exception as e:
        # ❌ NUNCA HAGAS: return e
        # ✅ HAZ ESTO:
        current_app.logger.error(f"Error en lista: {str(e)}")
        flash(f"Error al cargar la lista: {str(e)}", "danger")
        return redirect(url_for('rrhh.inicio_rrhh')) # Te manda al inicio en lugar de romper la app

@rrhh_bp.route('/personal/<int:personal_id>')
@login_required
@role_required('RRHH')
def ver_legajo(personal_id):
    """Vista de detalle de legajo para RRHH corrigiendo el ciclo de vida de conexión."""
    legajo_service = current_app.config['LEGAJO_SERVICE']
    
    try:
        # 1. Obtener los detalles del personal (Contratos, estudios, etc.)
        legajo_completo = legajo_service.get_personal_details(personal_id, current_user)
        
        # 2. Obtener las secciones AQUÍ en la ruta, no en el HTML
        secciones_list = legajo_service.get_secciones_for_select() or []
        
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

    # 3. Preparar el formulario de documentos
    form_documento = DocumentoForm()
    # Mapeamos las opciones del select
    form_choices = [('0', '-- Seleccione Sección --')] + secciones_list
    form_documento.id_seccion.choices = form_choices
    form_documento.id_tipo.choices = [('0', '-- Seleccione Tipo --')]

    # 4. Renderizamos enviando todo lo que el HTML necesita
    return render_template(
        'rrhh/ver_legajo_completo.html',
        legajo=legajo_completo,
        form_documento=form_documento,
        secciones=secciones_list,       # Pasamos la lista ya cargada
        legajo_service=legajo_service,  # <--- ¡CORRECCIÓN AÑADIDA AQUÍ!
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
        
        # ---------------------------------------------------------
        # 🛡️ BLOQUE DE AUDITORÍA (Cambio de Estado Laboral)
        # ---------------------------------------------------------
        try:
            audit_service = current_app.config.get('AUDIT_SERVICE')
            if audit_service:
                audit_service.log(
                    id_usuario=current_user.id,
                    modulo='RRHH',
                    accion='CAMBIAR_ESTADO',
                    descripcion=f"Actualizó el estado laboral del trabajador ID {personal_id} a: '{nuevo_estado}'."
                )
        except Exception as audit_err:
            current_app.logger.error(f"Error silencioso en auditoría (Cambiar Estado RRHH): {audit_err}")
        # ---------------------------------------------------------
        
        return jsonify({'success': True, 'message': 'Estado actualizado en la HMPP.'})
    except Exception as e:
        current_app.logger.error(f"Error al cambiar estado: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# app/presentation/routes/rrhh_routes.py

@rrhh_bp.route('/contrataciones/nuevo/<int:personal_id>', methods=['GET', 'POST'])
@login_required
@role_required('RRHH')
def ingresar_contratacion(personal_id):
    """
    Gestiona el registro de contratación inicial capturando obligatoriamente 
    el archivo PDF de la resolución y sincronizando la ficha maestra del personal.
    """
    from werkzeug.utils import secure_filename 
    
    legajo_service = current_app.config['LEGAJO_SERVICE']
    repo = legajo_service._personal_repo
    
    # 1. Buscar al trabajador para verificar existencia
    persona = repo.find_by_id(personal_id)
    if not persona:
        flash("Error: El trabajador no existe en el sistema.", "danger")
        return redirect(url_for('rrhh.listar_personal'))

    form = ContratoInicialForm()
    
    # 2. Carga dinámica de opciones para los selectores
    form.id_tipo_contrato.choices = [('', '-- Seleccione Tipo --')] + repo.get_tipos_contrato_for_select()
    form.id_cargo.choices = [('', '-- Seleccione Puesto --')] + repo.get_cargos_for_select()
    form.id_unidad.choices = [('', '-- Seleccione Unidad --')] + repo.get_unidades_for_select()

    # 3. Pre-cargar datos en GET
    if request.method == 'GET':
        if hasattr(persona, 'id_unidad') and persona.id_unidad:
            form.id_unidad.data = str(persona.id_unidad)

    # 4. Procesar el Formulario (POST)
    if form.validate_on_submit():
        archivo = request.files.get('archivo_resolucion')
        
        if not archivo or archivo.filename == '':
            flash("La Resolución en formato PDF es obligatoria para activar el contrato.", "warning")
        else:
            try:
                # A. Procesar el archivo PDF
                filename = secure_filename(archivo.filename)
                file_bytes = archivo.read()

                # B. Preparar datos para el repositorio
                data = form.data
                data['id_personal'] = personal_id

                # C. GUARDAR EN HISTORIAL (Lo que ves en Escalafón)
                if repo.registrar_contrato_inicial(data, file_bytes, filename):
                    
                    # === SOLUCIÓN A LA DESINCRONIZACIÓN: ACTUALIZAR TABLA PERSONAL ===
                    try:
                        # Obtenemos la conexión directamente para asegurar el cambio maestro
                        conn = db() 
                        cursor = conn.cursor()
                        
                        # Actualizamos la ficha maestra 'personal' con los nuevos IDs
                        # Esto cambia el recuadro azul de la web y el cargo estructural
                        query_update = """
                            UPDATE personal 
                            SET id_cargo = ?, 
                                id_tipo_contrato = ?, 
                                id_unidad = ?,
                                sueldo = ?
                            WHERE id_personal = ?
                        """
                        cursor.execute(query_update, (
                            form.id_cargo.data, 
                            form.id_tipo_contrato.data, 
                            form.id_unidad.data, 
                            form.sueldo.data,
                            personal_id
                        ))
                        conn.commit()
                        current_app.logger.info(f"Sincronización exitosa de ficha maestra para ID: {personal_id}")
                    
                    except Exception as ex:
                        current_app.logger.error(f"Error en sincronización maestra: {ex}")
                        # No bloqueamos el éxito del contrato si solo falla la sincronización visual
                    
                    # ---------------------------------------------------------
                    # 🛡️ BLOQUE DE AUDITORÍA (Ingreso de Contratación)
                    # ---------------------------------------------------------
                    try:
                        audit_service = current_app.config.get('AUDIT_SERVICE')
                        if audit_service:
                            nombres_trabajador = getattr(persona, 'nombres', 'Trabajador')
                            apellidos_trabajador = getattr(persona, 'apellidos', '')
                            audit_service.log(
                                id_usuario=current_user.id,
                                modulo='RRHH',
                                accion='NUEVO_CONTRATO',
                                descripcion=f"Registró una nueva contratación y actualizó la ficha maestra de: {nombres_trabajador} {apellidos_trabajador} (ID: {personal_id})."
                            )
                    except Exception as audit_err:
                        current_app.logger.error(f"Error silencioso en auditoría (Nuevo Contrato): {audit_err}")
                    # ---------------------------------------------------------

                    flash(f'¡Éxito! Contratación registrada y ficha maestra de {persona.nombres} actualizada.', 'success')
                    return redirect(url_for('rrhh.listar_personal'))
                else:
                    flash("Error técnico: El repositorio no pudo confirmar el guardado.", "danger")
            
            except Exception as e:
                current_app.logger.error(f"Error crítico en contratación: {str(e)}")
                flash(f'Error crítico durante el proceso: {str(e)}', 'danger')

    return render_template('rrhh/ingresar_contratacion.html', form=form, persona=persona)


# 1. AGREGAR ESTAS IMPORTACIONES AL INICIO DEL ARCHIVO

from app.infrastructure.persistence.planilla_repository import PlanillaRepository # <--- TU NUEVO REPO


# ... (resto de imports) ..

@rrhh_bp.route('/planillas')
@login_required
@role_required('RRHH')
def gestionar_planillas():
    """
    Vista principal: Lista las planillas creadas en la BD con alertas detalladas.
    """
    repo = PlanillaRepository()
    
    # 1. Intentamos cargar las planillas
    try:
        planillas = repo.get_all_planillas()
    except Exception as e:
        current_app.logger.error(f"Error listando planillas: {e}")
        planillas = [] 

    # 2. Intentamos cargar la LISTA de trabajadores sin contrato
    # 🚀 AQUÍ ESTÁ LA CORRECCIÓN: Usamos 'obtener_pendientes_contrato'
    try:
        # Traemos la lista completa (nombres, DNI...)
        lista_pendientes = repo.obtener_pendientes_contrato()
        
        # El número de alertas es el tamaño de esa lista
        num_alertas = len(lista_pendientes)
        
    except AttributeError:
        # Si te sale este error, es porque falta la función en el repositorio.
        # Por seguridad, definimos 0 para que no rompa la página.
        current_app.logger.error("Falta la función obtener_pendientes_contrato en el repositorio.")
        lista_pendientes = []
        num_alertas = 0
    except Exception as e:
        current_app.logger.error(f"Error en alertas de contrato: {e}")
        lista_pendientes = []
        num_alertas = 0
    
    today = datetime.now()
    
    return render_template(
        'rrhh/gestionar_planillas.html', 
        planillas=planillas, 
        today=today,
        alertas_contrato=num_alertas,      # El número (ej: 5) para el banner
        lista_pendientes=lista_pendientes  # La lista para la ventana modal
    )

# 3. AGREGAR LA NUEVA RUTA PARA PROCESAR LA CREACIÓN
@rrhh_bp.route('/planillas/crear', methods=['POST'])
@login_required
@role_required('RRHH')
def crear_nueva_planilla():
    """
    Recibe los datos del Modal y crea la carpeta del mes.
    """
    repo = PlanillaRepository()
    
    # Obtener datos del formulario HTML
    # El input type="month" devuelve formato 'YYYY-MM' (ej: 2026-04)
    periodo = request.form.get('periodo') 
    tipo_personal = request.form.get('tipo_personal')
    
    if not periodo or not tipo_personal:
        flash('Error: Debe seleccionar un periodo y un tipo de personal.', 'warning')
        return redirect(url_for('rrhh.gestionar_planillas'))

    # Separar Año y Mes
    anio, mes = periodo.split('-')
    
    try:
        # Llamamos a la función mágica del repositorio
        id_planilla, mensaje = repo.crear_planilla_mensual(int(anio), int(mes), tipo_personal)
        
        flash(f'¡Éxito! {mensaje}', 'success')
        
        # 🚀 OJO: Aquí redirigiremos a la "Calculadora" (siguiente paso). 
        # Por ahora volvemos a la lista para ver que se creó.
        return redirect(url_for('rrhh.gestionar_planillas'))
        
    except Exception as e:
        current_app.logger.error(f"Error creando planilla: {e}")
        flash(f'Error al crear planilla: {str(e)}', 'danger')
        return redirect(url_for('rrhh.gestionar_planillas'))
    

    
@rrhh_bp.route('/planillas/editar/<int:id_planilla>')
@login_required
@role_required('RRHH')
def editar_planilla_grilla(id_planilla):
    try:
        repo = PlanillaRepository()
        
        # 1. Fetch the header
        planilla_obj = repo.obtener_planilla_por_id(id_planilla)
        
        if not planilla_obj:
            flash("La planilla solicitada no existe.", "warning")
            return redirect(url_for('rrhh.gestionar_planillas'))

        # 2. Fetch the worker details
        # Ensure get_detalle_planilla also uses its own fresh connection internally
        detalles = repo.get_detalle_planilla(id_planilla)
        
        return render_template('rrhh/editar_planilla.html', 
                               planilla=planilla_obj, 
                               detalles=detalles, 
                               id_planilla=id_planilla)
    except Exception as e:
        # This captures the "Attempt to use a closed connection" seen in your logs
        print(f"🔥 ERROR EN RUTA EDITAR: {e}")
        return "Error interno del servidor", 500




# Agregar en app/presentation/routes/rrhh_routes.py

from flask import jsonify

# 1. Asegúrate de tener este import al principio del archivo:
from app.database import get_db_read # <--- IMPORTANTE

# ... (resto del código) ...

@rrhh_bp.route('/planillas/api/actualizar_monto', methods=['POST'])
@login_required
@role_required('RRHH')
def actualizar_detalle_planilla_api():
    """
    Recibe los cambios de una fila (faltas, bonos, etc.) vía AJAX,
    recalcula todo en el servidor y devuelve los nuevos totales.
    """
    repo = PlanillaRepository()
    data = request.get_json()
    
    id_detalle = data.get('id_detalle')
    
    try:
        # Validamos números (si vienen vacíos o texto, ponemos 0)
        faltas = float(data.get('faltas', 0) or 0)
        judiciales = float(data.get('judiciales', 0) or 0)
        otros = float(data.get('otros', 0) or 0)
        bonos = float(data.get('bonos', 0) or 0)
        
        # 1. Guardamos y Recalculamos (Esto actualiza la BD)
        repo.actualizar_montos_detalle(id_detalle, faltas, judiciales, otros, bonos)
        
        # 2. Leemos los datos actualizados para devolverlos a la pantalla
        # CORRECCIÓN: Usamos get_db_read() directamente (no repo.get_db_read)
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT neto_pagar, total_ingresos, total_descuentos, monto_pension, aporte_essalud FROM detalle_planilla WHERE id_detalle = ?", (id_detalle,))
        row = cursor.fetchone()
        
        
        if row:
            # CORRECCIÓN JSON: Convertimos Decimal a float para que no falle al enviar
            return jsonify({
                'success': True,
                'neto': float(row[0]),       # <--- float() es vital aquí
                'ingresos': float(row[1]),
                'descuentos': float(row[2]),
                'pension': float(row[3]),
                'essalud': float(row[4])
            })
        else:
            return jsonify({'success': False, 'error': 'Registro no encontrado'}), 404
        
    except Exception as e:
        print(f"ERROR API PLANILLA: {e}") # Esto imprimirá el error real en tu terminal negra
        return jsonify({'success': False, 'error': str(e)}), 500
    



@rrhh_bp.route('/planillas/ficha/<int:id_detalle>', methods=['GET', 'POST'])
@login_required
@role_required('RRHH')
def editar_ficha_individual(id_detalle):
    repo = PlanillaRepository()
    
    if request.method == 'POST':
        # --- GUARDAR CAMBIOS ---
        try:
            # Convertimos el formulario (request.form) a un diccionario para reusar tu función del repo
            data = request.form.to_dict()
            
            # La función del repo ahora procesará también el 'id_config' que viene del select
            repo.actualizar_montos_detalle(id_detalle, data)
            
            flash('✅ Ficha actualizada correctamente.', 'success')
            
            # Redirigir de vuelta a la lista general
            detalle = repo.get_detalle_por_id(id_detalle)
            return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=detalle['id_planilla']))
            
        except Exception as e:
            current_app.logger.error(f"Error al guardar ficha {id_detalle}: {str(e)}")
            flash(f'Error al guardar: {str(e)}', 'danger')
            return redirect(url_for('rrhh.editar_ficha_individual', id_detalle=id_detalle))

    # --- VER FICHA (GET) ---
    detalle = repo.get_detalle_por_id(id_detalle)
    if not detalle:
        flash('Trabajador no encontrado en esta planilla.', 'warning')
        return redirect(url_for('rrhh.gestionar_planillas'))
        
    # Traemos los catálogos de conceptos (Bonos/Descuentos)
    catalogos = repo.obtener_catalogo_conceptos()
    conceptos_trabajador = repo.obtener_conceptos_trabajador(id_detalle)

    # 🚀 CORRECCIÓN VITAL: Traemos el catálogo de Presupuesto (S10/SIAF)
    # Sin esta línea, el menú desplegable de "Actividad" sale vacío.
    catalogo_presupuestal = repo.obtener_presupuesto_configs()
        
    # Pasamos todo al HTML
    return render_template('rrhh/editar_ficha.html', 
                           d=detalle,
                           catalogos=catalogos,
                           conceptos_trabajador=conceptos_trabajador,
                           catalogo_s10=catalogo_presupuestal) # <-- Se envía al HTML aquí


@rrhh_bp.route('/planillas/eliminar/<int:id_planilla>', methods=['POST'])
@login_required
@role_required('RRHH', 'Sistemas') # Se recomienda incluir Sistemas para supervisión
def eliminar_planilla(id_planilla):
    """
    Ruta para mover una planilla a la papelera en lugar de eliminarla físicamente.
    """
    repo = PlanillaRepository()
    try:
        # 1. Llamamos a la nueva función de borrado lógico
        # 2. Pasamos el ID del usuario actual para el registro de auditoría interna del repo
        exito = repo.eliminar_planilla_logico(id_planilla, current_user.id)
        
        if exito:
            # ---------------------------------------------------------
            # 🛡️ BLOQUE DE AUDITORÍA (Mover Planilla a Papelera)
            # ---------------------------------------------------------
            try:
                audit_service = current_app.config.get('AUDIT_SERVICE')
                if audit_service:
                    audit_service.log(
                        id_usuario=current_user.id,
                        modulo='RRHH - Planillas',
                        accion='MOVER_A_PAPELERA',
                        descripcion=f"El usuario {current_user.username} movió la planilla ID #{id_planilla} a la papelera de reciclaje."
                    )
            except Exception as audit_err:
                current_app.logger.error(f"Error silencioso en auditoría (Eliminar Planilla RRHH): {audit_err}")
            # ---------------------------------------------------------

            # Usamos categoría 'warning' para indicar que no es un borrado permanente
            flash('⚠️ Planilla movida a la papelera correctamente. El Administrador de Escalafón puede restaurarla si es necesario.', 'warning')
        else:
            flash('❌ No se pudo mover la planilla a la papelera. Verifique los permisos.', 'danger')
            
    except Exception as e:
        # Registramos el error y avisamos al usuario
        current_app.logger.error(f"Error en ruta eliminar_planilla: {e}")
        flash(f'Ocurrió un error inesperado al procesar la solicitud.', 'danger')
    
    return redirect(url_for('rrhh.gestionar_planillas'))


from flask import  make_response
from xhtml2pdf import pisa
from io import BytesIO
import os  # <--- IMPORTANTE: Agrega esto arriba


@rrhh_bp.route('/planillas/ficha/<int:id_detalle>/pdf')
def descargar_boleta_pdf(id_detalle):
    # 1. Obtener datos
    repo = PlanillaRepository()
    d = repo.get_detalle_por_id(id_detalle)
    
    if not d:
        return "Ficha no encontrada", 404

    # 🔥 NUEVO: Obtener los conceptos dinámicos (Aguinaldos) de la BD
    conceptos = repo.obtener_conceptos_trabajador(id_detalle)
    aguinaldos = conceptos.get('aguinaldos', [])

    # 2. Ruta del logo
    ruta_logo = os.path.join(current_app.root_path, 'presentation', 'static', 'img', 'muni_logo.png')

    # 3. Renderizar HTML
    html = render_template(
        'rrhh/boleta_pago_horizontal.html', 
        d=d,
        aguinaldos_boleta=aguinaldos,  # 🔥 AQUÍ PASAMOS LOS AGUINALDOS AL HTML
        fecha_hoy=datetime.now().strftime("%d/%m/%Y %H:%M"),
        usuario_actual="Admin RRHH",
        logo_path=ruta_logo
    )

    # 4. Generar PDF en Memoria
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=pdf_buffer)

    if pisa_status.err:
        return "Error al generar PDF", 500

    # ======================================================
    # GUARDAR EN BASE DE DATOS
    # ======================================================
    # Obtenemos los bytes crudos del buffer
    pdf_bytes = pdf_buffer.getvalue()
    
    # Llamamos al repositorio para guardar
    guardado_ok = repo.guardar_pdf_boleta(id_detalle, pdf_bytes)
    
    if guardado_ok:
        print(f"✅ Boleta guardada exitosamente para ID: {id_detalle}")
    else:
        print(f"⚠️ Alerta: La boleta se generó pero NO se guardó en BD.")

    # ======================================================
    # PREPARAR DESCARGA
    # ======================================================
    # Rebobinamos el buffer al inicio para leerlo de nuevo
    pdf_buffer.seek(0)
    
    response = make_response(pdf_buffer.read())
    filename = f"BOLETA_{d['dni_trabajador']}_{d['mes']}_{d['anio']}.pdf"
    
    response.headers['Content-Type'] = 'application/pdf'
    # 'inline' para ver, 'attachment' para bajar
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    
    return response

@rrhh_bp.route('/planillas/ver_boleta/<int:id_detalle>')
def ver_boleta_archivada(id_detalle):
    repo = PlanillaRepository()
    
    # 1. Buscamos solo el archivo PDF de ese trabajador
    pdf_bytes = repo.obtener_pdf_guardado(id_detalle)
    
    if not pdf_bytes:
        return "No hay boleta guardada para este trabajador.", 404

    # 2. Creamos la respuesta para el navegador
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    # 'inline' hace que se abra en el navegador en lugar de descargar
    response.headers['Content-Disposition'] = 'inline; filename=boleta_archivada.pdf'
    
    return response


# En rrhh_routes.py

@rrhh_bp.route('/planillas/cerrar/<int:id_planilla>', methods=['POST'])
@login_required
@role_required('RRHH')
def cerrar_planilla(id_planilla):
    repo = PlanillaRepository()
    # Llamamos al método que cambia el estado a 'CERRADA' en la base de datos
    if repo.cerrar_planilla(id_planilla):
        flash('Planilla CERRADA exitosamente. Ya no se podrán realizar cambios.', 'success')
    else:
        flash('Error al cerrar la planilla.', 'danger')
    return redirect(url_for('rrhh.gestionar_planillas'))


@rrhh_bp.route('/planillas/abrir/<int:id_planilla>', methods=['POST'])
@login_required
@role_required('RRHH')
def abrir_planilla(id_planilla):
    repo = PlanillaRepository()
    
    # 1. OBTENER LA CLAVE REAL DE LA BASE DE DATOS
    clave_real = repo.obtener_clave_dinamica()

    # 2. Obtener lo que escribió el usuario
    clave_ingresada = request.form.get('clave_seguridad')

    # 3. Comparar
    if not clave_ingresada or clave_ingresada.strip().upper() != clave_real:
        flash('CLAVE INCORRECTA: La autorización ha fallado o la clave ha caducado.', 'danger')
        return redirect(url_for('rrhh.gestionar_planillas'))

    # 4. Abrir si es correcto
    if repo.abrir_planilla(id_planilla):
        flash('AUTORIZADO: Planilla desbloqueada con token de seguridad.', 'success')
    else:
        flash('Error técnico al abrir.', 'danger')
        
    return redirect(url_for('rrhh.gestionar_planillas'))


# ==============================================================================
# SECCIÓN DE REPORTES PDF (PLANILLA GENERAL - SÁBANA)
# ==============================================================================

# 1. RUTA PARA "IMPRIMIR LISTA OFICIAL" (Botón Rojo en Edición)
# -------------------------------------------------------------
# Esta ruta hace dos cosas:
# A) Marca en la base de datos que el PDF oficial ya se generó (pdf_generado = 1).
# B) Genera y muestra el PDF para imprimir.
@rrhh_bp.route('/planillas/imprimir_oficial/<int:id_planilla>')
@login_required
@role_required('RRHH')
def imprimir_planilla_oficial(id_planilla):
    from weasyprint import HTML, CSS
    import zlib
    repo = PlanillaRepository()
    
    # [PASO CLAVE] Actualizamos la bandera en la BD para habilitar el "Ojo" en el listado
    exito = repo.marcar_planilla_como_impresa(id_planilla)
    if not exito:
        flash("Advertencia: No se pudo actualizar el estado de impresión, pero se generará el PDF.", "warning")

    # 1. Obtener Datos
    cabecera = repo.get_planilla_header(id_planilla)
    if not cabecera:
        flash("Planilla no encontrada", "danger")
        return redirect(url_for('rrhh.gestionar_planillas'))

    detalles = repo.get_reporte_general_data(id_planilla)

    # 2. Calcular Totales BLINDADOS (Evita el choque Decimal vs Float y nulos)
    def safe_float(val):
        if val is None:
            return 0.0
        return float(val)

    totales = {
        'ingresos': sum(safe_float(d.get('total_remuneracion')) for d in detalles),
        'descuentos': sum(safe_float(d.get('total_descuentos')) for d in detalles),
        'neto': sum(safe_float(d.get('neto_pagar')) for d in detalles),
        'pension': sum(safe_float(d.get('sistema_pension')) for d in detalles),
        'renta5ta': sum(safe_float(d.get('renta_5ta')) for d in detalles),
        'essalud': sum(safe_float(d.get('essalud_9')) for d in detalles),
        'aportes': sum(safe_float(d.get('total_aportes')) for d in detalles),
        
        # Agregamos sumas de desglose para que cuadren con las columnas
        'sueldos_base': sum(safe_float(d.get('remuneracion_mensual')) for d in detalles),
        'asig_familiar': sum(safe_float(d.get('asig_familiar')) for d in detalles),
        'reintegros': sum(safe_float(d.get('reintegros')) for d in detalles),
        'otros_ingresos': sum(safe_float(d.get('otros_ingresos')) for d in detalles),
        
        'essalud_vida': sum(safe_float(d.get('essalud_vida')) for d in detalles),
        'judicial': sum(safe_float(d.get('judicial')) for d in detalles),
        'otros_descuentos': sum(safe_float(d.get('prestamos')) for d in detalles),
        'faltas_total': sum(safe_float(d.get('dscto_tardanza')) for d in detalles),
        'sctr_salud': sum(safe_float(d.get('sctr_salud')) for d in detalles),
        'sctr_pension': sum(safe_float(d.get('sctr_pension')) for d in detalles),
        'cts': sum(safe_float(d.get('cts')) for d in detalles),
        
        # Nuevos campos de Viáticos, Sindicato y Aguinaldos
        'viaticos': sum(safe_float(d.get('d_viatico')) for d in detalles),
        'sindicato': sum(safe_float(d.get('desc_sindicato')) for d in detalles),
        'aguinaldos': sum(safe_float(d.get('tot_aguinaldos')) for d in detalles)
    }

    # 3. Renderizar HTML
    html_str = render_template(
        'rrhh/pdf_planilla_general.html',
        cabecera=cabecera,
        detalles=detalles,
        totales=totales,
        today=datetime.now()
    )

    # 4. Generar PDF
    try:
        # Forzar CSS Landscape
        css = CSS(string='@page { size: A4 landscape; }')
        pdf_file = HTML(string=html_str, base_url=current_app.static_folder).write_pdf(stylesheets=[css])

        # ==========================================================
        # 🔥 NUEVO: GUARDAR EN LA BASE DE DATOS
        # ==========================================================
        # Opción A: Guardado simple
        # repo.guardar_pdf_planilla_oficial(id_planilla, pdf_file)
        
        # Opción B: Guardado con COMPRESIÓN (Recomendado para sábanas grandes)
        
        pdf_comprimido = zlib.compress(pdf_file, 6)
        repo.guardar_pdf_planilla_oficial(id_planilla, pdf_comprimido)
        # ==========================================================

        response = make_response(pdf_file)
        response.headers['Content-Type'] = 'application/pdf'
        # Inline para que se abra en el navegador y el usuario imprima
        filename = f"OFICIAL_{cabecera['mes_nombre']}_{cabecera['anio']}.pdf"
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response

    except Exception as e:
        current_app.logger.error(f"🔥 ERROR WEASYPRINT: {e}")
        flash(f"Error generando PDF: {str(e)}", "danger")
        return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))


# 2. RUTA PARA "VISUALIZAR PDF" (Botón Ojo Verde en Listado)
# ----------------------------------------------------------
# Esta ruta SOLO LEE. No cambia el estado en la base de datos.
# Se usa para consultas posteriores una vez que ya es oficial.
@rrhh_bp.route('/planillas/ver_pdf/<int:id>')
@login_required
@role_required('RRHH')
def ver_planilla_pdf(id):
    from weasyprint import HTML, CSS
    
    repo = PlanillaRepository()
    
    # 1. Obtener Datos (Misma lógica)
    cabecera = repo.get_planilla_header(id)
    if not cabecera:
        return "Planilla no encontrada", 404

    detalles = repo.get_reporte_general_data(id)

    # 2. Totales (Misma lógica)
    totales = {
        'ingresos': sum(d['total_remuneracion'] for d in detalles),
        'descuentos': sum(d['total_descuentos'] for d in detalles),
        'neto': sum(d['neto_pagar'] for d in detalles),
        'pension': sum(d['sistema_pension'] for d in detalles),
        'renta5ta': sum(d['renta_5ta'] for d in detalles),
        'essalud': sum(d['essalud_9'] for d in detalles),
        'aportes': sum(d['total_aportes'] for d in detalles),
        
        'sueldos_base': sum(d['remuneracion_mensual'] for d in detalles),
        'asig_familiar': sum(d['asig_familiar'] for d in detalles),
        'reintegros': sum(d['reintegros'] for d in detalles),
        'otros_ingresos': sum(d['otros_ingresos'] for d in detalles),
        
        'essalud_vida': sum(d['essalud_vida'] for d in detalles),
        'judicial': sum(d['judicial'] for d in detalles),
        'otros_descuentos': sum(d['prestamos'] for d in detalles),
        'faltas_total': sum(d['dscto_tardanza'] for d in detalles),
        'sctr_salud': sum(d['sctr_salud'] for d in detalles),
        'sctr_pension': sum(d['sctr_pension'] for d in detalles),
        'cts': sum(d['cts'] for d in detalles)
    }

    # 3. Renderizar HTML
    html_str = render_template(
        'rrhh/pdf_planilla_general.html',
        cabecera=cabecera,
        detalles=detalles,
        totales=totales,
        today=datetime.now()
    )

    # 4. Generar PDF
    try:
        css = CSS(string='@page { size: A4 landscape; }')
        pdf_file = HTML(string=html_str, base_url=current_app.static_folder).write_pdf(stylesheets=[css])

        response = make_response(pdf_file)
        response.headers['Content-Type'] = 'application/pdf'
        # Inline para visualización rápida
        filename = f"COPIA_{cabecera['mes_nombre']}_{cabecera['anio']}.pdf"
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response

    except Exception as e:
        current_app.logger.error(f"🔥 ERROR WEASYPRINT VIEW: {e}")
        return f"Error generando PDF: {str(e)}", 500
    
def marcar_planilla_como_impresa(self, id_planilla):
    try:
        conn = self.get_db_connection() # O tu función de conexión
        cursor = conn.cursor()
        # Actualizamos la bandera a 1 (True)
        cursor.execute("UPDATE planillas SET pdf_generado = 1 WHERE id_planilla = ?", (id_planilla,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al marcar planilla: {e}")
        return False
    

@rrhh_bp.route('/reporte/anual/<int:id_personal>/<int:anio>')
@login_required
@role_required('RRHH', 'AdministradorLegajos', 'Sistemas')
def generar_reporte_anual(id_personal, anio):
    from weasyprint import HTML
    import io
    import re  
    from app.database import get_db_read
    from datetime import datetime
    
    repo_personal = SqlServerPersonalRepository()
    repo_planilla = PlanillaRepository() 
    
    conn = get_db_read()
    cursor = conn.cursor()
    
    # Extrae el texto entre paréntesis (Ej: "Bono Especial (BONESP)" -> "BONESP")
    def obtener_abreviatura(nombre_completo):
        match = re.search(r'\((.*?)\)', nombre_completo)
        return match.group(1) if match else nombre_completo
    
    try:
        # 1. OBTENER DATOS PERSONALES Y EL DNI GLOBAL (Sin ID de contrato)
        cursor.execute("""
            SELECT TOP 1 
                dp.nombre_completo, dp.cargo_actual, dp.sistema_pensionario, 
                dp.dni_trabajador, dp.nivel, dp.condicion_laboral, 
                p.fecha_ingreso, dp.observaciones
            FROM detalle_planilla dp
            INNER JOIN planillas pl ON dp.id_planilla = pl.id_planilla
            INNER JOIN personal p ON dp.id_personal = p.id_personal
            WHERE dp.id_personal = ? AND pl.anio = ? AND pl.eliminado = 0
            ORDER BY pl.mes DESC
        """, (id_personal, anio))
        
        row_emp = cursor.fetchone()
        # 🔥 VALIDACIÓN PARA EL JAVASCRIPT (No consume el Flash)
        if request.args.get('check') == '1':
            if not row_emp:
                return jsonify({"status": "error"}), 404
            return jsonify({"status": "ok"}), 200

        # ❌ FLUJO NORMAL: SI NO HAY DATOS (Aquí sí usamos el Flash)
        if not row_emp:
            flash('No hay datos en planilla para este trabajador en el año seleccionado.', 'danger')
            return redirect(request.referrer or url_for('rrhh.listar_personal'))
            
        dni_target = row_emp[3] 
        
        personal_dict = {
            'apellidos': row_emp[0],
            'nombres': '', 
            'cargo_actual': row_emp[1],
            'sistema_pensionario': row_emp[2] or 'ONP',
            'dni': dni_target,
            'nivel': row_emp[4] if row_emp[4] else '-',
            'regimen_laboral': row_emp[5] or 'CAS / NOMBRADO', # 🔥 Toma el texto exacto de la caja
            'fecha_ingreso': row_emp[6].strftime('%d/%m/%Y') if row_emp[6] else '-',
        }
        
        cargos_anio = repo_planilla.obtener_cargos_anio(id_personal, anio)

        # 2. 🔥 OBTENER COLUMNAS DINÁMICAS (Ingresos, Descuentos y Aguinaldos)
        cursor.execute("""
            SELECT DISTINCT c.nombre_concepto, c.tipo
            FROM detalle_conceptos_trabajador dc
            INNER JOIN catalogo_conceptos c ON dc.id_concepto = c.id_concepto
            INNER JOIN detalle_planilla dp ON dc.id_detalle = dp.id_detalle
            INNER JOIN planillas pl ON dp.id_planilla = pl.id_planilla
            WHERE dp.dni_trabajador = ? AND pl.anio = ?
        """, (dni_target, anio)) 
        
        conceptos = cursor.fetchall()
        bonos_unicos = []
        descuentos_unicos = []
        aguinaldos_unicos = [] # 🔥 LISTA PARA LOS AGUINALDOS DINÁMICOS
        
        for c_nom, c_tipo in conceptos:
            abrev = obtener_abreviatura(c_nom)
            
            if c_tipo == 'INGRESO' and abrev not in bonos_unicos:
                bonos_unicos.append(abrev)
            elif c_tipo == 'DESCUENTO' and abrev not in descuentos_unicos:
                descuentos_unicos.append(abrev)
            elif c_tipo == 'AGUINALDO' and abrev not in aguinaldos_unicos:
                aguinaldos_unicos.append(abrev)
        
        if not bonos_unicos: bonos_unicos = ['BONESP', 'BONODIF']

        # 3. CONSTRUIR LA TABLA MES A MES RECOPILANDO TODO (INCLUSO INASISTENCIAS)
        pagos_anuales = []
        
        for i in range(1, 13):
            # Añadidas las 5 columnas de inasistencias a la consulta principal
            sql_mes = """
                SELECT 
                    dp.dias_computables, dp.dias_falta, dp.sueldo_basico, dp.reintegros,
                    dp.asignacion_familiar, dp.total_ingresos, dp.monto_pension,
                    dp.renta_4ta_5ta, dp.judiciales, dp.faltas_tardanzas,
                    dp.total_descuentos, dp.neto_pagar, dp.aporte_essalud,
                    dp.id_detalle, dp.observaciones,
                    dp.d_viatico, dp.desc_sindicato, dp.essalud_vida,
                    dp.sctr, dp.sctr_onp, dp.cts, dp.rps, dp.bonificaciones, dp.otros_descuentos,
                    dp.d_medico, dp.d_vacaciones, dp.d_permisos, dp.d_suspensiones, dp.d_otros_inasis
                FROM detalle_planilla dp
                INNER JOIN planillas pl ON dp.id_planilla = pl.id_planilla
                WHERE dp.dni_trabajador = ? AND pl.anio = ? AND pl.mes = ?
            """
            cursor.execute(sql_mes, (dni_target, anio, i))
            filas_mes = cursor.fetchall() 
            
            pago = {
                'mes': i, 'vacio': True, 'd_lab': 0, 'd_fal': 0, 'basica': 0.0, 'reintegro': 0.0,
                'bonif': 0.0, 'asig_fam': 0.0, 'otros_ing': 0.0, 'ing_bruto': 0.0, 
                's_pens': 0.0, 'renta': 0.0, 'judic': 0.0, 'tardanza': 0.0, 'otros_dscto': 0.0, 
                'tot_dscto': 0.0, 'neto': 0.0, 'rps': 0.0, 'essalud_9': 0.0, 'sctr_salud': 0.0, 
                'sctr_pension': 0.0, 'cts': 0.0, 'dict_bonos': {}, 'dict_descuentos': {},
                'dict_aguinaldos': {}, 'tot_aguinaldos': 0.0, # 🔥 Preparado para Aguinaldos
                'medic': 0, 'vacac': 0, 'permis': 0, 'susp': 0, 'otros_inasis': 0, # 🔥 Preparado para Inasistencias
                'observaciones': ''
            }
            
            if filas_mes:
                pago['vacio'] = False
                obs_list = []
                
                for r in filas_mes:
                    pago['d_lab'] += float(r[0] or 0)
                    pago['d_fal'] += float(r[1] or 0)
                    pago['basica'] += float(r[2] or 0)
                    pago['reintegro'] += float(r[3] or 0)
                    pago['asig_fam'] += float(r[4] or 0)
                    pago['ing_bruto'] += float(r[5] or 0)
                    pago['s_pens'] += float(r[6] or 0)
                    pago['renta'] += float(r[7] or 0)
                    pago['judic'] += float(r[8] or 0)
                    pago['tardanza'] += float(r[9] or 0)
                    pago['tot_dscto'] += float(r[10] or 0)
                    pago['neto'] += float(r[11] or 0)
                    pago['essalud_9'] += float(r[12] or 0)
                    
                    id_det = r[13]
                    if r[14]: obs_list.append(r[14])
                    
                    viatico = float(r[15] or 0)
                    sindicato = float(r[16] or 0)
                    vida = float(r[17] or 0)
                    
                    pago['sctr_salud'] += float(r[18] or 0)
                    pago['sctr_pension'] += float(r[19] or 0)
                    pago['cts'] += float(r[20] or 0)
                    pago['rps'] += float(r[21] or 0)
                    pago['bonif'] += float(r[22] or 0)
                    
                    # 🔥 SUMA DE INASISTENCIAS
                    pago['medic'] += int(r[24] or 0)
                    pago['vacac'] += int(r[25] or 0)
                    pago['permis'] += int(r[26] or 0)
                    pago['susp'] += int(r[27] or 0)
                    pago['otros_inasis'] += int(r[28] or 0)
                    
                    # Extraemos y sumamos conceptos (Ingresos, Descuentos y Aguinaldos)
                    cursor.execute("""
                        SELECT c.nombre_concepto, c.tipo, dc.monto 
                        FROM detalle_conceptos_trabajador dc
                        INNER JOIN catalogo_conceptos c ON dc.id_concepto = c.id_concepto
                        WHERE dc.id_detalle = ?
                    """, (id_det,))
                    
                    for c_nom, c_tipo, c_monto in cursor.fetchall():
                        monto_flt = float(c_monto or 0)
                        abrev = obtener_abreviatura(c_nom)
                            
                        if c_tipo == 'INGRESO':
                            pago['dict_bonos'][abrev] = pago['dict_bonos'].get(abrev, 0.0) + monto_flt
                        elif c_tipo == 'DESCUENTO':
                            pago['dict_descuentos'][abrev] = pago['dict_descuentos'].get(abrev, 0.0) + monto_flt
                        elif c_tipo == 'AGUINALDO': # 🔥 LLENADO DE AGUINALDOS
                            pago['dict_aguinaldos'][abrev] = pago['dict_aguinaldos'].get(abrev, 0.0) + monto_flt
                            pago['tot_aguinaldos'] += monto_flt

                    # Se mantienen las fijas separadas de los dinámicos
                    if sindicato > 0: pago['dict_descuentos']['Cuota Sindical'] = pago['dict_descuentos'].get('Cuota Sindical', 0.0) + sindicato
                    if vida > 0: pago['dict_descuentos']['Essalud Vida'] = pago['dict_descuentos'].get('Essalud Vida', 0.0) + vida

                    pago['otros_ing'] += viatico
                    pago['otros_dscto'] += float(r[23] or 0) + sindicato + vida
                
                pago['observaciones'] = " | ".join(filter(None, obs_list))

            pagos_anuales.append(pago)

        if any(float(p['dict_descuentos'].get('Cuota Sindical', 0)) > 0 for p in pagos_anuales) and 'Cuota Sindical' not in descuentos_unicos: descuentos_unicos.append('Cuota Sindical')
        if any(float(p['dict_descuentos'].get('Essalud Vida', 0)) > 0 for p in pagos_anuales) and 'Essalud Vida' not in descuentos_unicos: descuentos_unicos.append('Essalud Vida')

        # 4. RENDERIZAR EL HTML 
        html_content = render_template(
            'record_laboral/pdf_record_anual.html', 
            personal=personal_dict, 
            cargos_anio=cargos_anio, 
            pagos=pagos_anuales, 
            anio=anio,
            bonos_unicos=bonos_unicos,           
            descuentos_unicos=descuentos_unicos, 
            aguinaldos_unicos=aguinaldos_unicos, # 🔥 ENVIAMOS LOS AGUINALDOS AL HTML
            fecha_hoy=datetime.now()
        )

        pdf_bytes = HTML(string=html_content, base_url=request.base_url).write_pdf()

        nombre_archivo = f"RECORD_ANUAL_{anio}_{personal_dict['dni']}.pdf"
        datos_record = {
            'id_personal': id_personal,
            'nombre_archivo': nombre_archivo,
            'descripcion': f"Récord Laboral Anual - Consolidado {anio}",
            'fecha_inicio': f"{anio}-01-01",
            'fecha_fin_vencimiento': f"{anio}-12-31"
        }
        # ==========================================================
        # 🔥 AQUI APLICAMOS LA MAGIA DE LA COMPRESIÓN
        # ==========================================================
        import zlib
        pdf_comprimido = zlib.compress(pdf_bytes, 9)
        
        # 1. Guardamos la versión COMPRIMIDA en la base de datos (Escalafón)
        repo_personal.add_record_laboral(datos_record, pdf_comprimido)

        # 2. Al navegador le mandamos la versión NORMAL (pdf_bytes) para que se vea de inmediato
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=False, download_name=nombre_archivo)

    except Exception as e:
        print(f"🔥 Error Crítico en Récord: {str(e)}", 'danger')
        flash(f'Error técnico: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('rrhh.listar_personal'))
    
        


@rrhh_bp.route('/planillas/<int:id_planilla>/importar-excel', methods=['POST'])
@login_required
@role_required('AdministradorLegajos', 'AdministradorEscalafon', 'Sistemas', 'RRHH')
def importar_excel_planilla(id_planilla):
    import pandas as pd
    from app.infrastructure.persistence.planilla_repository import PlanillaRepository
    from markupsafe import Markup
    
    if 'archivo_excel' not in request.files:
        flash("No se encontró el archivo Excel.", "warning")
        return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))

    file = request.files['archivo_excel']
    if file.filename == '':
        flash("No seleccionó ningún archivo.", "warning")
        return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))

    filtro_condicion = request.form.get('filtro_condicion', 'TODOS').upper()
    filtro_periodo = request.form.get('filtro_periodo', '').strip()

    try:
        # 1. Leemos el Excel gigante
        df = pd.read_excel(file)
        
        # Limpiamos los nombres de las columnas
        df.columns = [str(c).strip().upper() for c in df.columns]

        # =========================================================================
        # 🔥 FIX: REPARACIÓN DE CEROS A LA IZQUIERDA PARA EL DNI
        # =========================================================================
        # Nota: Cambia 'DNI' por el nombre de la columna si en tu Excel se llama distinto (ej. 'NUM_DOC')
        if 'DNI' in df.columns:
            df['DNI'] = df['DNI'].fillna('') \
                                 .astype(str) \
                                 .str.replace('.0', '', regex=False) \
                                 .str.strip() \
                                 .str.zfill(8)  # Esto le pone los ceros faltantes hasta llegar a 8

        # 2. 🔥 FILTRO POR PERIODO
        if filtro_periodo:
            if 'PERIODO' in df.columns:
                df['PERIODO'] = df['PERIODO'].fillna('').astype(str).str.replace('.0', '', regex=False).str.strip()
                df = df[df['PERIODO'] == filtro_periodo]
            else:
                flash("❌ El Excel no tiene la columna 'PERIODO'. Asegúrese de usar el formato correcto.", "danger")
                return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))

        # 3. 🔥 FILTRO INTELIGENTE POR CONDICIÓN O TIPO DE TRABAJADOR
        if filtro_condicion != 'TODOS':
            # Verificamos si existen las columnas
            tiene_condicion = 'CONDICION' in df.columns
            tiene_tipotrab = 'TIPOTRAB' in df.columns

            if tiene_condicion or tiene_tipotrab:
                # Llenamos los vacíos con texto para que no se rompa la búsqueda
                if tiene_condicion: 
                    df['CONDICION'] = df['CONDICION'].fillna('').astype(str).str.upper()
                if tiene_tipotrab: 
                    df['TIPOTRAB'] = df['TIPOTRAB'].fillna('').astype(str).str.upper()

                # A. Creamos la máscara de búsqueda principal
                if tiene_condicion and tiene_tipotrab:
                    mask = df['CONDICION'].str.contains(filtro_condicion) | df['TIPOTRAB'].str.contains(filtro_condicion)
                elif tiene_condicion:
                    mask = df['CONDICION'].str.contains(filtro_condicion)
                elif tiene_tipotrab:
                    mask = df['TIPOTRAB'].str.contains(filtro_condicion)
                
                # B. 🔥 BLINDAJE ANTI-CONFUSIÓN (El parche para CAS vs CAS CONFIANZA)
                if filtro_condicion == 'CAS':
                    # Si buscamos CAS Regular, le RESTAMOS (~) todos los que digan CONFIANZA
                    if tiene_condicion:
                        mask = mask & ~df['CONDICION'].str.contains('CONFIANZA')
                    if tiene_tipotrab:
                        mask = mask & ~df['TIPOTRAB'].str.contains('CONFIANZA')

                # C. Aplicamos el filtro definitivo al Excel
                df = df[mask]

            else:
                flash("❌ El Excel no tiene la columna 'CONDICION' ni 'TIPOTRAB'.", "danger")
                return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))

        if df.empty:
            flash(Markup(f"❌ No se encontraron trabajadores con Periodo: <b>{filtro_periodo}</b> y Condición: <b>{filtro_condicion}</b>."), "warning")
            return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))

        # =========================================================================
        # 🔥 EL "CEREBRO": RECÁLCULO DINÁMICO, APLICACIÓN DE LEY Y DETECTIVE SCTR
        # =========================================================================
        try:
            # A. Detectamos rangos de Ingresos y Descuentos
            idx_basica = df.columns.get_loc('BASICA')
            idx_totalbru = df.columns.get_loc('TOTALBRU')
            ing_presentes = df.columns[idx_basica : idx_totalbru]
            
            idx_dcafae = df.columns.get_loc('DCAFAE')
            idx_tdescuen = df.columns.get_loc('TDESCUEN')
            desc_presentes = df.columns[idx_dcafae : idx_tdescuen]

            # Limpiamos nulos
            for col in list(ing_presentes) + list(desc_presentes):
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # 🕵️‍♂️ PASO CLAVE PARA EL DETECTIVE: Guardamos el Total Bruto viejo del Excel
            # Reemplazamos 0 por 1 para evitar errores matemáticos de división entre cero
            df['TOTALBRU_VIEJO'] = pd.to_numeric(df['TOTALBRU'], errors='coerce').replace(0, 1).fillna(1)

            # B. Calculamos el Total Bruto REAL sumando los ingresos
            df['TOTALBRU'] = df[ing_presentes].sum(axis=1)

            # C. BLINDAJE DE ESSALUD (9% del Total Bruto Real)
            if 'RPS' in df.columns:
                df['RPS'] = (df['TOTALBRU'] * 0.09).round(2)

            # D. 🔥 NUEVO: DETECTIVE DE SCTR SALUD
            if 'SCTR' in df.columns:
                df['SCTR'] = pd.to_numeric(df['SCTR'], errors='coerce').fillna(0)
                tiene_sctr = df['SCTR'] > 0
                
                # Descubrimos la tasa: (Monto viejo del Excel / Total Bruto viejo del Excel)
                # Ej: 2.65 / 3180.50 = 0.00083... redondeado a 4 decimales = 0.0009
                tasa_descubierta = (df.loc[tiene_sctr, 'SCTR'] / df.loc[tiene_sctr, 'TOTALBRU_VIEJO']).round(4)
                
                # Aplicamos la tasa descubierta al Total Bruto REAL (Ej: 3102.50 * 0.0009 = 2.79)
                df.loc[tiene_sctr, 'SCTR'] = (df.loc[tiene_sctr, 'TOTALBRU'] * tasa_descubierta).round(2)

            # E. BLINDAJE DE PENSIONES
            tasas_pension = {
                'ONP': 0.1300,
                'HABITAT': 0.1247,
                'INTEGRA': 0.1244,
                'PROFUTURO': 0.1259,
                'PRIMA': 0.1248
            }
            columnas_pension = {
                'ONP': 'DONP', 'HABITAT': 'DHABITAT', 'INTEGRA': 'DINTEGRA', 
                'PROFUTURO': 'DPROFU', 'PRIMA': 'DPRIMA'
            }

            if 'REGPENS' in df.columns:
                # Ponemos en 0 todas las columnas de pensión primero
                for col in columnas_pension.values():
                    if col in df.columns:
                        df[col] = 0.00

                # Calculamos la pensión correcta
                for index, row in df.iterrows():
                    regimen = str(row['REGPENS']).strip().upper()
                    if regimen in tasas_pension and columnas_pension[regimen] in df.columns:
                        tasa = tasas_pension[regimen]
                        columna_destino = columnas_pension[regimen]
                        df.at[index, columna_destino] = round(row['TOTALBRU'] * tasa, 2)

            # F. Recalculamos el Total de Descuentos
            df['TDESCUEN'] = df[desc_presentes].sum(axis=1)

            # G. Calculamos el Neto real y evitamos que sea negativo
            df['NCOBRAR'] = df['TOTALBRU'] - df['TDESCUEN']
            df['NCOBRAR'] = df['NCOBRAR'].clip(lower=0)
            
        except KeyError as e:
            flash(f"❌ Error en la estructura del Excel. Falta la columna clave: {str(e)}", "danger")
            return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))

        # =========================================================================
        # 🔥 FIN DEL RECÁLCULO DINÁMICO
        # =========================================================================

        # 4. Enviamos el Excel filtrado y RECALCULADO a tu función del Repositorio
        repo = PlanillaRepository()
        
        if repo.procesar_carga_masiva_completa(id_planilla, df):
            flash(f"✅ ¡Éxito! Se procesaron {len(df)} trabajadores con montos validados.", "success")
        else:
            flash("❌ Hubo un error interno al guardar los datos en la base de datos.", "danger")

    except ValueError as ve:
        flash(Markup(str(ve)), "danger")
        
    except Exception as e:
        flash(f"❌ Error al procesar el archivo: {str(e)}", "danger")

    return redirect(url_for('rrhh.editar_planilla_grilla', id_planilla=id_planilla))

@rrhh_bp.route('/planillas/descargar-plantilla')
@login_required
@role_required('RRHH', 'AdministradorLegajos', 'AdministradorEscalafon', 'Sistemas')
def descargar_plantilla_excel():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation # 🔥 Para las listas desplegables

    # 1. Definición de Columnas
    columnas = [
        "PERIODO", "NP", "ACTIVIDAD", "META", "NUM", "PATERNO", "MATERNO", "NOMBRES",
        "DNI", "FNAC", "NCUENTA", "NCTACTS", "AUTOG", "REGPENS", "AFPCUPPS", "INGRAFP",
        "CFOTOCHE", "SINDIC", "FINGR", "CONDICION", "NIVEL", "TIPOTRAB", "CARGO", "UBICACION",
        "SCTR", "DIASCONT", "DIASTRAB", "FALTAS", "DIASSUBSI", "HORAS", "TARDANZAS",
        "BASICA", "REUNIF", "TPH-COSVID", "PERSON", "FAMILI", "BONESP", "REFMOV", "BONODIF",
        "DS276", "DU03794", "INCFONV", "D.L.26504", "DS 326-2025-EF", "INCAFP", "DL268-EF", "Encarg",
        "TOTALBRU", "SUELDOBASE", "DCAFAE", "DONP", "DPROFU", "DHABITAT", "DINTEGRA", "DPRIMA",
        "DESSAVI", "DQUINTACAT", "DJUDIC", "DSINDIC", "DAREQUIPA", "DA/SOLID", "DCENTROCOOP",
        "DCOOPAC", "DLIMENTOS", "DSMILAGROS", "DMILPOCOOP", "DMAYNAS", "RIMAC", "DE-SIN",
        "TDESCUEN", "RPS", "SCTR ONP", "CTS", "TOTALAPORT", "NCOBRAR"
    ]

    df = pd.DataFrame(columns=columnas)

    # 2. Inyección de Fórmulas (Fila 2)
    # TOTALBRU(AV): suma AF a AU
    # DONP(AY): Si REGPENS(N) es ONP -> TOTALBRU * 0.13
    # DPROFU(AZ): Si REGPENS(N) es PROFUTURO -> TOTALBRU * 0.1259
    # DHABITAT(BA): Si REGPENS(N) es HABITAT -> TOTALBRU * 0.1247
    # DINTEGRA(BB): Si REGPENS(N) es INTEGRA -> TOTALBRU * 0.1244
    # DPRIMA(BC): Si REGPENS(N) es PRIMA -> TOTALBRU * 0.1248
    # TDESCUEN(BR): suma AX a BQ
    # NCOBRAR(BW): AV - BR
    
    df.loc[0] = {
        "NP": "P - 1", "PATERNO": "PEREZ", "MATERNO": "GOMEZ", "NOMBRES": "JUAN", 
        "DNI": "12345678", "CONDICION": "CAS", "REGPENS": "ONP", "SINDIC": "NO",
        "BASICA": 1500.00, "DIASTRAB": 30, 
        "TOTALBRU": "=SUM(AF2:AU2)",
        "DONP": "=IF(N2=\"ONP\", AV2*0.13, 0)",
        "DPROFU": "=IF(N2=\"PROFUTURO\", AV2*0.1259, 0)",
        "DHABITAT": "=IF(N2=\"HABITAT\", AV2*0.1247, 0)",
        "DINTEGRA": "=IF(N2=\"INTEGRA\", AV2*0.1244, 0)",
        "DPRIMA": "=IF(N2=\"PRIMA\", AV2*0.1248, 0)",
        "TDESCUEN": "=SUM(AX2:BQ2)",
        "NCOBRAR": "=AV2-BR2"
    }

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla_Oficial')
        workbook = writer.book
        worksheet = writer.sheets['Plantilla_Oficial']

        # 3. Listas Desplegables (Seleccionadores)
        # Lista para Régimen Pensionario
        dv_pension = DataValidation(type="list", formula1='"ONP,HABITAT,INTEGRA,PROFUTURO,PRIMA,SIN REGIMEN"', allow_blank=True)
        worksheet.add_data_validation(dv_pension)
        dv_pension.add("N2:N1000") # Columna REGPENS

        # Lista para Sindicato
        dv_sindic = DataValidation(type="list", formula1='"SI,NO"', allow_blank=True)
        worksheet.add_data_validation(dv_sindic)
        dv_sindic.add("R2:R1000") # Columna SINDIC

        # 4. Formato de Tabla
        letra_ultima_col = get_column_letter(len(columnas))
        rango_tabla = f"A1:{letra_ultima_col}2" 
        tabla = Table(displayName="TablaHMPP", ref=rango_tabla)
        estilo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
        tabla.tableStyleInfo = estilo
        worksheet.add_table(tabla)

        # 5. Estética de Columnas
        column_widths = {'A': 12, 'F': 15, 'G': 15, 'H': 20, 'I': 12, 'N': 15, 'W': 30}
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width

    output.seek(0)
    return send_file(
        output,
        download_name="Plantilla_Inteligente_HMPP.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



from flask import request, flash, redirect, send_file
import io
import pandas as pd
# Asegúrate de importar tu blueprint, que asumo se llama rrhh_bp

# =========================================================================
# 🔥 NUEVA RUTA: CONVERTIDOR DE EXCEL DE LA MUNICIPALIDAD A FORMATO SISTEMA
# =========================================================================
@rrhh_bp.route('/planillas/convertir-formato', methods=['POST'])
# @login_required  <-- Descomenta esto si usas protección de rutas
# @role_required('AdministradorLegajos', 'RRHH') <-- Y esto también si usas roles
def convertir_excel_muni():
    if 'archivo_muni' not in request.files:
        flash("No se subió ningún archivo.", "warning")
        return redirect(request.referrer)
        
    file = request.files['archivo_muni']
    if file.filename == '':
        flash("No seleccionó ningún archivo.", "warning")
        return redirect(request.referrer)

    try:
        # 1. Leemos el Excel "resumido" de la Municipalidad
        df_muni = pd.read_excel(file)
        
        # Limpiamos los nombres de las columnas (quitamos espacios ocultos)
        df_muni.columns = [str(c).strip().upper() for c in df_muni.columns]

        # 2. Tu lista OFICIAL y exacta de 76 columnas de tu sistema
        columnas_oficiales = [
            'PERIODO', 'NP', 'ACTIVIDAD', 'META', 'NUM', 'PATERNO', 'MATERNO', 'NOMBRES', 'DNI', 
            'FNAC', 'NCUENTA', 'NCTACTS', 'AUTOG', 'REGPENS', 'AFPCUPPS', 'INGRAFP', 'CFOTOCHE', 
            'SINDIC', 'FINGR', 'CONDICION', 'NIVEL', 'TIPOTRAB', 'CARGO', 'UBICACION', 'SCTR', 
            'DIASCONT', 'DIASTRAB', 'FALTAS', 'DIASSUBSI', 'HORAS', 'TARDANZAS', 'BASICA', 
            'REUNIF', 'TPH-COSVID', 'PERSON', 'FAMILI', 'BONESP', 'REFMOV', 'BONODIF', 'DS276', 
            'DU03794', 'INCFONV', 'D.L.26504', 'DS 326-2025-EF', 'INCAFP', 'DL268-EF', 'Encarg', 
            'TOTALBRU', 'SUELDOBASE', 'DCAFAE', 'DONP', 'DPROFU', 'DHABITAT', 'DINTEGRA', 
            'DPRIMA', 'DESSAVI', 'DQUINTACAT', 'DJUDIC', 'DSINDIC', 'DAREQUIPA', 'DA/SOLID', 
            'DCENTROCOOP', 'DCOOPAC', 'DLIMENTOS', 'DSMILAGROS', 'DMILPOCOOP', 'DMAYNAS', 
            'RIMAC', 'DE-SIN', 'TDESCUEN', 'RPS', 'SCTR ONP', 'CTS', 'TOTALAPORT', 'NCOBRAR'
        ]

        # 3. Creamos un nuevo DataFrame vacío solo con tus columnas oficiales
        df_sistema = pd.DataFrame(columns=columnas_oficiales)

        # 4. Magia: Copiamos los datos que coinciden de la Muni a tu Sistema
        for col in df_muni.columns:
            if col in columnas_oficiales:
                df_sistema[col] = df_muni[col]

        # =========================================================================
        # 🔥 FIX 1: Mantener los ceros a la izquierda del DNI
        # =========================================================================
        if 'DNI' in df_sistema.columns:
            df_sistema['DNI'] = df_sistema['DNI'].fillna('').astype(str).str.replace('.0', '', regex=False).str.strip().str.zfill(8)

        # =========================================================================
        # 🔥 FIX 2: Limpieza de Fechas (Evitar NaT y horas 00:00:00)
        # =========================================================================
        columnas_fechas = ['FINGR', 'FNAC'] # Puedes agregar más columnas de fecha aquí si lo necesitas
        for col_fecha in columnas_fechas:
            if col_fecha in df_sistema.columns and col_fecha in df_muni.columns:
                # Convierte a formato fecha real, luego a texto DD/MM/YYYY. Los vacíos se vuelven ''
                df_sistema[col_fecha] = pd.to_datetime(df_muni[col_fecha], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')

        # =========================================================================
        # 🔥 FIX 3: ELIMINAR FILAS BASURA (Totales, subtotales, celdas vacías)
        # =========================================================================
        # 1. Eliminamos cualquier fila donde el DNI sea '00000000' o esté totalmente vacío
        if 'DNI' in df_sistema.columns:
            df_sistema = df_sistema[df_sistema['DNI'] != '00000000']
            df_sistema = df_sistema[df_sistema['DNI'] != '']
        
        # 2. Eliminamos filas donde no haya datos esenciales (Ej: si no hay PATERNO ni NOMBRES, no es trabajador)
        # Usamos dropna para borrar la fila solo si AMBOS están vacíos (NaN o NaT)
        if 'PATERNO' in df_sistema.columns and 'NOMBRES' in df_sistema.columns:
            # Primero reemplazamos posibles strings vacíos por NaN para que dropna los detecte
            import numpy as np
            df_sistema['PATERNO'] = df_sistema['PATERNO'].replace('', np.nan)
            df_sistema['NOMBRES'] = df_sistema['NOMBRES'].replace('', np.nan)
            df_sistema = df_sistema.dropna(subset=['PATERNO', 'NOMBRES'], how='all')
            # Devolvemos los posibles NaN sobrantes a string vacío por seguridad
            df_sistema['PATERNO'] = df_sistema['PATERNO'].fillna('')
            df_sistema['NOMBRES'] = df_sistema['NOMBRES'].fillna('')

        # 5. Generamos el nuevo Excel directamente en la Memoria RAM (sin gastar disco duro)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_sistema.to_excel(writer, index=False, sheet_name='PLANILLA_OFICIAL')
        
        output.seek(0)

        # 6. Forzamos la descarga automática del archivo convertido
        nombre_descarga = "PLANILLA_SISTEMA_HMPP.xlsx"
        return send_file(output, download_name=nombre_descarga, as_attachment=True)

    except Exception as e:
        flash(f"Error al convertir el archivo: {str(e)}", "danger")
        return redirect(request.referrer)