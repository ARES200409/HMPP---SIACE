"""
Routes para que los empleados accedan y gestionen sus propios datos personales.
Cumple con la Ley 29733 de Protección de Datos Personales del Perú.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from app.application.forms import ActualizarPersonalForm
from app.application.services.file_validation_service import FileValidationService # Importación clave
import logging
from datetime import datetime
from flask import make_response
from xhtml2pdf import pisa
from io import BytesIO
import os  # <--- IMPORTANTE: Agrega esto arriba con los otros imports

# Asegúrate de importar esto al inicio
from app.database import get_db_read


# Definición del Blueprint
personal_bp = Blueprint('personal', __name__, url_prefix='/personal')
logger = logging.getLogger(__name__)

@personal_bp.before_request
def check_personal_role():
    """Verifica que el usuario tenga permiso para acceder a sus rutas personales."""
    if current_user.is_authenticated:
        # Obtenemos el nombre del rol del usuario
        rol_nombre = current_user.rol if hasattr(current_user, 'rol') else ''
        
        # 1. LISTA VIP: Todos estos roles son trabajadores y tienen derecho a ver su propio legajo
        roles_permitidos = [
            'Personal', 
            'Empleado', 
            'Sistemas', 
            'RRHH', 
            'AdministradorEscalafon', 
            'AdministradorLegajos'
        ]
        
        # Si el rol del usuario está en la lista permitida, lo dejamos pasar sin interrumpirlo
        if rol_nombre in roles_permitidos:
            return None  # En Flask, retornar None en un before_request significa "Todo bien, déjalo pasar a la ruta que pidió"
            
        # 2. Si tiene un rol que no está en la lista, le bloqueamos el paso
        flash('No tienes permiso para acceder a la sección de Personal.', 'danger')
        return redirect(url_for('auth.login'))

from app.core.security import role_required  # (La ruta exacta depende de cómo esté estructurado tu proyecto)
@personal_bp.route('/inicio')
@login_required
@role_required('Personal', 'Sistemas', 'RRHH', 'AdministradorEscalafon', 'AdministradorLegajos') 
def inicio():
    """
    Dashboard principal del empleado.
    Muestra resumen y accesos directos.
    """
    try:
        logger.info(f"INIT: Accediendo a dashboard de Personal. Usuario: {current_user.username}")
        logger.info("-" * 40)
        logger.info(f"AUDITORIA: current_user.id: {current_user.id}")
        logger.info(f"AUDITORIA: current_user.username: {current_user.username}")
        logger.info(f"AUDITORIA: current_user.rol: {current_user.rol}")
        
        # Este es el dato clave que estaba fallando:
        logger.info(f"AUDITORIA: current_user.id_personal: {getattr(current_user, 'id_personal', 'NO EXISTE')}")
        logger.info("-" * 40)



        # 💡 CORRECCIÓN UNBOUNDLOCALERROR: Inicializar la variable
        persona = None 
        
        # Verificamos si el usuario tiene un personal_id asociado
        if not getattr(current_user, 'id_personal', None):
            logger.warning(f"FLOW: Usuario {current_user.username} (ID: {current_user.id}) no tiene id_personal asociado.")
            flash('Su usuario no está vinculado a ningún legajo de personal. Contacte a RRHH.', 'warning')
            
            # 💡 CORRECCIÓN 1: Usar el template de contenido (inicio_personal.html)
            return render_template('personal/inicio_personal.html', 
                                   usuario=current_user, 
                                   persona=persona) 

        # Si tiene id_personal, procedemos a obtener los datos
        legajo_service = current_app.config['LEGAJO_SERVICE']
        personal_repo = legajo_service._personal_repo
        
        # Obtenemos la información básica de la persona
        persona = personal_repo.find_by_id(current_user.id_personal)
        
        if persona:
            logger.info(f"SUCCESS: Datos de persona encontrados. DNI: {persona.dni if hasattr(persona, 'dni') else 'N/A'}")
        else:
            logger.error(f"FAIL: No se encontró el legajo para id_personal: {current_user.id_personal}")
            flash('Error: Legajo no encontrado a pesar de tener id_personal asociado. Contacte a RRHH.', 'danger')
            
        # 💡 CORRECCIÓN 2: Usar el template de contenido (inicio_personal.html)
        return render_template('personal/inicio_personal.html', 
                             usuario=current_user, 
                             persona=persona)
                             
    except Exception as e:
        logger.error(f"FATAL: Error en dashboard personal para usuario {current_user.username}: {e}", exc_info=True)
        flash('Error al cargar el panel principal.', 'danger')
        return redirect(url_for('auth.login'))




@personal_bp.route('/mi-legajo', methods=['GET'])
@login_required
def ver_mi_legajo():
    """Vista completa del legajo con diseño integrado (Estilo RRHH)."""
    try:
        id_personal = getattr(current_user, 'id_personal', None)
        if not id_personal:
            flash('No tiene un legajo asociado.', 'warning')
            return redirect(url_for('personal.inicio'))

        legajo_service = current_app.config['LEGAJO_SERVICE']
        
        # 1. Obtener legajo completo
        legajo_completo = legajo_service._personal_repo.get_full_legajo_by_id(id_personal)
        
        # 2. Obtener lista de secciones para el acordeón (igual que en RRHH)
        secciones = legajo_service.get_secciones_for_select()
        
        # 3. Pasar 'today' para calcular vencimientos en la vista
        return render_template('personal/ver_legajo_propio.html', 
                               legajo=legajo_completo,
                               secciones=secciones,
                               today=datetime.now().date())
                               
    except Exception as e:
        logger.error(f"Error al cargar mi legajo: {e}")
        flash('Error al cargar el legajo.', 'danger')
        return redirect(url_for('personal.inicio'))

@personal_bp.route('/actualizar-datos', methods=['GET', 'POST'])
@login_required
def actualizar_datos():
    """
    Ruta CORREGIDA: Separa totalmente el Email Corporativo del Personal.
    - 'email': Se mantiene el original (Corporativo).
    - 'email_personal': Se actualiza con el formulario (Privado).
    """
    try:
        personal_id = getattr(current_user, 'id_personal', None)
        if not personal_id:
            flash('No se encontró el ID de personal.', 'warning')
            return redirect(url_for('personal.inicio'))

        legajo_service = current_app.config['LEGAJO_SERVICE']
        
        # 1. Cargar datos actuales
        full_data = legajo_service.get_personal_details(personal_id, current_user)
        current_p = full_data.get('personal', {})
        
        if request.method == 'POST':
            
            form_data = {
                # --- A. DATOS CORPORATIVOS E INTOCABLES (Se preservan) ---
                'dni': current_p.get('dni'),
                'nombres': current_p.get('nombres'),
                'apellidos': current_p.get('apellidos'),
                'sexo': current_p.get('sexo'),
                'fecha_nacimiento': current_p.get('fecha_nacimiento'),
                'nacionalidad': current_p.get('nacionalidad') or 'Peruana',
                'id_unidad': current_p.get('id_unidad') or 19, 
                'fecha_ingreso': current_p.get('fecha_ingreso'),
                
                # 🛡️ AQUÍ ESTÁ LA CLAVE: El 'email' para el SP es el CORPORATIVO original
                # Así aseguramos que el SP no lo borre ni lo cambie.
                'email': current_p.get('email'), 

                # --- B. DATOS EDITABLES POR EL TRABAJADOR ---
                'direccion': request.form.get('direccion'),
                'estado_civil': request.form.get('estado_civil'),
                'telefono': request.form.get('telefono'), 
                
                # ✅ AQUÍ GUARDAMOS EL EMAIL PERSONAL EN SU PROPIA LLAVE
                'email_personal': request.form.get('email_personal') 
            }
            
            exito = legajo_service.update_personal_details(personal_id, form_data, current_user.id_usuario)
            
            if exito is not False: 
                flash('¡Datos actualizados correctamente!', 'success')
                return redirect(url_for('personal.ver_datos_personales'))
            else:
                flash('Error al guardar cambios.', 'danger')

        return render_template('personal/actualizar_datos.html', personal=current_p)

    except Exception as e:
        logger.error(f"Error actualizando datos: {str(e)}", exc_info=True)
        return redirect(url_for('personal.inicio'))

# RUTA: app/presentation/routes/personal_routes.py

from app.database import get_db_write # Asegúrate de importar esto arriba

@personal_bp.route('/solicitar-cancelacion', methods=['GET', 'POST'])
@login_required
def solicitar_cancelacion():
    """Formulario para solicitar cancelación de datos (ARCO)."""
    
    if request.method == 'POST':
        # 1. CAPTURAR LOS DATOS DEL FORMULARIO
        # Verificamos uno por uno los checkboxes (según tu HTML anterior)
        datos_seleccionados = []
        
        if request.form.get('check_email'): 
            datos_seleccionados.append('Email Personal')
        if request.form.get('check_telefono'): 
            datos_seleccionados.append('Telefono')
        if request.form.get('check_direccion'): 
            datos_seleccionados.append('Direccion')
        if request.form.get('check_sensibles'): 
            datos_seleccionados.append('Datos Sensibles')
        
        # También intentamos con 'datos_cancelar' por si cambiaste el HTML
        lista_extra = request.form.getlist('datos_cancelar')
        if lista_extra:
            datos_seleccionados.extend(lista_extra)

        # Convertimos la lista a texto (ej: "Email Personal, Direccion")
        datos_str = ", ".join(datos_seleccionados)
        
        # Capturamos el motivo (puede llamarse 'razon' o 'motivo' en tu HTML)
        motivo = request.form.get('razon') or request.form.get('motivo') or ''

        # 2. VALIDACIÓN
        if not datos_str:
            flash('Debe seleccionar al menos un dato para cancelar.', 'warning')
            return render_template('personal/solicitar_cancelacion.html')

        # 3. GUARDAR EN BASE DE DATOS (Lo que faltaba)
        conn = get_db_write()
        cursor = conn.cursor()
        
        try:
            query = """
                INSERT INTO solicitudes_arco 
                (id_personal, tipo_solicitud, datos_afectados, motivo_solicitud, estado, fecha_solicitud)
                VALUES (?, 'CANCELACION', ?, ?, 'PENDIENTE', GETDATE())
            """
            cursor.execute(query, (current_user.id_personal, datos_str, motivo))
            
            # ¡IMPORTANTE! Confirmar los cambios
            conn.commit()
            
            # Auditoría (Opcional, pero recomendado)
            audit_service = current_app.config['AUDIT_SERVICE']
            audit_service.log(current_user.id, 'PersonalData', 'SOLICITUD_CANCELACION', f"Solicitó cancelar: {datos_str}")

            flash('Solicitud registrada correctamente. RRHH responderá en 5 días hábiles.', 'success')
            return redirect(url_for('personal.inicio'))
            
        except Exception as e:
            conn.rollback() # Si falla, deshacemos
            current_app.logger.error(f"Error guardando solicitud: {e}")
            flash('Ocurrió un error al procesar la solicitud en la base de datos.', 'danger')
        #finally:
            #conn.close()

    return render_template('personal/solicitar_cancelacion.html')

@personal_bp.route('/derecho-oposicion', methods=['GET', 'POST'])
@login_required
def derecho_oposicion():
    """Formulario de oposición."""
    audit_service = current_app.config['AUDIT_SERVICE']
    
    if request.method == 'POST':
        try:
            motivo = request.form.get('motivo', '')
            tipo = request.form.get('tipo_procesamiento', '')
            
            audit_service.log(current_user.id, 'PersonalData', 'OPOSICION', f"Oposición a {tipo}")
            flash('Solicitud de oposición registrada.', 'success')
            return redirect(url_for('personal.inicio'))
            
        except Exception as e:
            logger.error(f"Error oposicion: {e}")
            flash('Error al procesar.', 'danger')

    return render_template('personal/derecho_oposicion.html')

import os  # <--- IMPORTANTE: Agrega esto arriba con los otros imports


# ==============================================================================
# RUTA DE DESCARGA DE PDF (CORREGIDA Y COMPLETA)
# ==============================================================================
@personal_bp.route('/descargar-datos')
@login_required
def descargar_datos():
    try:
        # 1. Validación de usuario
        personal_id = getattr(current_user, 'id_personal', None)
        dni_usuario = current_user.username

        if not personal_id:
            flash('Error de identificación.', 'danger')
            return redirect(url_for('personal.inicio'))

        legajo_service = current_app.config['LEGAJO_SERVICE']
        
        # 2. Obtenemos datos básicos (Personal)
        data_full = legajo_service.get_personal_details(personal_id, current_user)
        p_origen = data_full.get('personal', {}) if data_full else {}

        # 3. CONSULTA MAESTRA SQL (Para llenar la Parte III Laboral)
        cargo_real = "SIN ASIGNACION"
        unidad_real = "ADMINISTRACION"
        sueldo_real = 0.00
        contrato_real = "CAS Confianza"
        fecha_contrato_str = "No registrada"

        conn = None
        try:
            conn = get_db_read() # <--- Ahora esto funcionará gracias al import corregido
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    c.nombre_cargo,
                    ua.nombre AS nombre_unidad,
                    (SELECT TOP 1 sueldo FROM contratos WHERE id_personal = p.id_personal ORDER BY id_contrato DESC) as sueldo,
                    (SELECT TOP 1 fecha_inicio FROM contratos WHERE id_personal = p.id_personal ORDER BY id_contrato DESC) as fecha_inicio,
                    (SELECT TOP 1 tc.nombre_tipo 
                     FROM contratos con 
                     LEFT JOIN tipos_contrato tc ON con.id_tipo_contrato = tc.id_tipo_contrato
                     WHERE con.id_personal = p.id_personal 
                     ORDER BY con.id_contrato DESC) as nombre_tipo_contrato
                FROM personal p
                LEFT JOIN cargos c ON p.id_cargo = c.id_cargo
                LEFT JOIN unidad_administrativa ua ON p.id_unidad = ua.id_unidad
                WHERE p.id_personal = ?
            """
            cursor.execute(query, (personal_id,))
            row = cursor.fetchone()
            
            if row:
                if row[0]: cargo_real = row[0]
                if row[1]: unidad_real = row[1]
                if row[2]: sueldo_real = float(row[2])
                
                # Procesamiento de fecha seguro
                if row[3]:
                    raw_fecha = row[3]
                    if isinstance(raw_fecha, (date, datetime)):
                        fecha_contrato_str = raw_fecha.strftime('%Y-%m-%d')
                    else:
                        fecha_contrato_str = str(raw_fecha)
                
                if row[4]: contrato_real = row[4]

        except Exception as e:
            logger.error(f"Error en Consulta SQL PDF: {e}")
        finally:
            if conn: conn.close()

        # Fecha Institucional
        fecha_inst_str = (p_origen.get('fecha_ingreso') or 
                          p_origen.get('FechaIngreso') or 
                          "No registrada")

        # 4. PREPARAR DATOS PARA LA PLANTILLA
        persona = {
            'nombres': p_origen.get('nombres'),
            'apellidos': p_origen.get('apellidos'),
            'dni': p_origen.get('dni') or dni_usuario,
            'sexo': p_origen.get('sexo') or 'M',
            'fecha_nacimiento': p_origen.get('fecha_nacimiento'),
            'estado_civil': p_origen.get('estado_civil') or 'Soltero',
            'direccion': p_origen.get('direccion') or 'Sin dirección',
            'telefono': p_origen.get('telefono'),
            'email': p_origen.get('email'), # Corporativo
            'email_personal': p_origen.get('email_personal')
        }

        legajo = {
            'cargo': cargo_real,
            'unidad': unidad_real,
            'tipo_contrato': contrato_real,
            'sueldo': sueldo_real,
            'fecha_institucional': fecha_inst_str,
            'fecha_contrato': fecha_contrato_str
        }

        fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")

        # 5. LOGOS
        logo_path = os.path.join(current_app.root_path, 'presentation', 'static', 'img', 'muni_logo.png')
        if not os.path.exists(logo_path): logo_path = None

        logo_path_right = os.path.join(current_app.root_path, 'presentation', 'static', 'img', 'hmppasco.png')
        if not os.path.exists(logo_path_right): logo_path_right = None

        # 6. GENERAR PDF
        html_content = render_template('personal/ficha_pdf.html', 
                                     persona=persona, 
                                     legajo=legajo, 
                                     fecha_hoy=fecha_hoy,
                                     logo_path=logo_path,
                                     logo_path_right=logo_path_right)

        pdf_output = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_output)

        if pisa_status.err:
            return "Error al generar PDF", 500

        pdf_output.seek(0)
        response = make_response(pdf_output.read())
        response.headers['Content-Type'] = 'application/pdf'
        filename = f"Ficha_Datos_{persona.get('dni', 'Personal')}.pdf"
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response

    except Exception as e:
        logger.error(f"Error crítico PDF: {str(e)}", exc_info=True)
        return redirect(url_for('personal.ver_datos_personales'))

# 🚀 CORRECCIÓN CRÍTICA: Añadimos 'date' aquí para que no falle la fecha
from datetime import date, datetime
from app.database.connector import get_db_read 


@personal_bp.route('/mis-datos', methods=['GET'])
@login_required
def ver_datos_personales():
    """
    Versión 'Super Nuclear Corregida': 
    Ignora repositorios y servicios para la parte laboral.
    Hace una consulta SQL directa uniendo Personal + Cargo + Unidad + Último Contrato.
    """
    try:
        # 1. Validación de usuario
        personal_id = getattr(current_user, 'id_personal', None)
        dni_usuario = current_user.username
        
        if not personal_id:
            flash('Su usuario no tiene un ID de personal vinculado.', 'warning')
            return redirect(url_for('personal.inicio'))

        legajo_service = current_app.config['LEGAJO_SERVICE']
        
        # =========================================================================
        # FUENTE A: Datos Personales Básicos (Nombres, DNI, etc.)
        # =========================================================================
        data_full = legajo_service.get_personal_details(personal_id, current_user)
        p_origen = data_full.get('personal', {}) if data_full else {}

        # =========================================================================
        # 🚀 CONSULTA MAESTRA (SQL DIRECTO)
        # =========================================================================
        cargo_real = "SIN ASIGNACION"
        unidad_real = "ADMINISTRACION"
        sueldo_real = 0.00
        contrato_real = "CAS Confianza"
        fecha_contrato_str = "No registrada"

        conn = None
        try:
            conn = get_db_read()
            cursor = conn.cursor()
            
            # Esta consulta une TODO manualmente sin pedir la columna 'activo'
            query = """
                SELECT 
                    c.nombre_cargo,
                    ua.nombre AS nombre_unidad,
                    (SELECT TOP 1 sueldo FROM contratos WHERE id_personal = p.id_personal ORDER BY id_contrato DESC) as sueldo,
                    (SELECT TOP 1 fecha_inicio FROM contratos WHERE id_personal = p.id_personal ORDER BY id_contrato DESC) as fecha_inicio,
                    (SELECT TOP 1 tc.nombre_tipo 
                     FROM contratos con 
                     LEFT JOIN tipos_contrato tc ON con.id_tipo_contrato = tc.id_tipo_contrato
                     WHERE con.id_personal = p.id_personal 
                     ORDER BY con.id_contrato DESC) as nombre_tipo_contrato
                FROM personal p
                LEFT JOIN cargos c ON p.id_cargo = c.id_cargo
                LEFT JOIN unidad_administrativa ua ON p.id_unidad = ua.id_unidad
                WHERE p.id_personal = ?
            """
            cursor.execute(query, (personal_id,))
            row = cursor.fetchone()
            
            if row:
                if row[0]: cargo_real = row[0]          # Cargo
                if row[1]: unidad_real = row[1]         # Unidad
                if row[2]: sueldo_real = float(row[2])  # Sueldo
                
                # Procesamiento de FECHA (Aquí era donde fallaba por falta de 'date')
                if row[3]:
                    raw_fecha = row[3]
                    if isinstance(raw_fecha, (date, datetime)):
                        fecha_contrato_str = raw_fecha.strftime('%Y-%m-%d')
                    else:
                        fecha_contrato_str = str(raw_fecha)
                
                if row[4]: contrato_real = row[4]       # Tipo Contrato

        except Exception as e:
            logger.error(f"Error en Consulta Maestra SQL: {e}")
        finally:
            if conn:
                conn.close()

        # Fecha Institucional (Histórica)
        fecha_inst_str = (p_origen.get('fecha_ingreso') or 
                          p_origen.get('FechaIngreso') or 
                          "No registrada")

        # =========================================================================
        # MAPEO FINAL
        # =========================================================================
        
        persona = {
            'nombres': p_origen.get('nombres'),
            'apellidos': p_origen.get('apellidos'),
            'dni': p_origen.get('dni') or dni_usuario,
            'sexo': p_origen.get('sexo') or 'M',
            'fecha_nacimiento': p_origen.get('fecha_nacimiento'),
            'estado_civil': p_origen.get('estado_civil') or 'Soltero',
            'direccion': p_origen.get('direccion') or 'Sin dirección',
            'telefono': p_origen.get('telefono'),
            'email_corporativo': p_origen.get('email'),
            'email_personal': p_origen.get('email_personal') or 'No registrado'
        }

        legajo = {
            'cargo': cargo_real,
            'unidad': unidad_real,
            'tipo_contrato': contrato_real,
            'sueldo': sueldo_real,
            'fecha_institucional': fecha_inst_str,
            'fecha_contrato': fecha_contrato_str,

            # Respaldos
            'fecha_ingreso': fecha_inst_str,
            'fecha_inicio': fecha_contrato_str
        }

        return render_template('personal/ver_datos_personales.html', 
                               persona=persona, 
                               legajo=legajo)

    except Exception as e:
        logger.error(f"Error crítico en mis-datos: {str(e)}", exc_info=True)
        return redirect(url_for('personal.inicio'))
    
@personal_bp.route('/solicitar-cambio-documento', methods=['GET', 'POST'])
@login_required
def solicitar_cambio_documento():
    """
    Formulario para solicitar la modificación o reemplazo de un documento existente.
    """
    try:
        # Servicios necesarios
        audit_service = current_app.config.get('AUDIT_SERVICE')
        legajo_service = current_app.config['LEGAJO_SERVICE']
        solicitud_service = current_app.config.get('SOLICITUDES_SERVICE')

        # 1. Obtener ID del documento
        documento_id = request.args.get('documento_id') or request.form.get('documento_id')
        
        # DEFINIMOS LA RUTA DE RETORNO CORRECTA (Asegúrate que se llame así en tu archivo)
        ruta_retorno = 'personal.ver_mi_legajo'

        if not documento_id:
            flash('Error: No se especificó el documento a modificar.', 'warning')
            return redirect(url_for(ruta_retorno))

        # 2. Obtener datos del documento
        documento = legajo_service.get_document_by_id(documento_id)
        
        if not documento:
            flash('Error: El documento solicitado no existe.', 'danger')
            return redirect(url_for(ruta_retorno))

        if request.method == 'POST':
            razon = request.form.get('razon', '').strip()
            archivo_nuevo = request.files.get('archivo_nuevo')

            if not razon:
                flash('Debe especificar un motivo para el cambio.', 'warning')
            elif not archivo_nuevo or archivo_nuevo.filename == '':
                flash('Debe adjuntar el nuevo documento.', 'warning')
            else:
                try:
                    if solicitud_service:
                        # 1. Registrar la solicitud
                        solicitud_service.registrar_solicitud_cambio(
                            id_usuario=current_user.id_usuario, 
                            id_documento=documento_id,
                            motivo=razon,
                            archivo=archivo_nuevo
                        )

                        # 2. Auditoría (Protegida)
                        if audit_service:
                            try:
                                audit_service.log(
                                    current_user.id_usuario, 'Personal', 'SOLICITUD_CAMBIO_DOC', 
                                    f"Solicitó cambio para documento ID: {documento_id}"
                                )
                            except:
                                pass # Si falla el log, no importa, seguimos.

                        flash('Solicitud enviada correctamente. Adminstrador de Legajo revisará el cambio.', 'success')
                        
                        # --- AQUÍ ESTABA EL ERROR ---
                        # Usamos la variable ruta_retorno para no equivocarnos
                        return redirect(url_for(ruta_retorno))
                    else:
                        flash('Error interno: Servicio no disponible.', 'danger')

                except ValueError as ve:
                    flash(str(ve), 'warning')
                except Exception as e:
                    current_app.logger.error(f"Error solicitud cambio documento: {e}", exc_info=True)
                    flash('Ocurrió un error al procesar su solicitud.', 'danger')

        # 3. Renderizar vista
        return render_template('personal/solicitar_cambio_documento.html', documento=documento, documento_id=documento_id)

    except Exception as e:
        current_app.logger.error(f"Error crítico en ruta solicitar cambio: {e}")
        flash('Error inesperado en el sistema.', 'danger')
        return redirect(url_for('personal.inicio'))
    


# --- AGREGAR ESTO EN: app/presentation/routes/personal_routes.py ---

@personal_bp.route('/mi-record-laboral')
@login_required
def ver_mi_record():
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        
        # CAMBIO CLAVE: Usamos 'id_personal' directamente si existe en current_user
        # Si no existe, usamos un valor por defecto o intentamos buscarlo
        id_personal = getattr(current_user, 'id_personal', None)

        # Si por alguna razón es None, intentamos obtenerlo de la sesión o del usuario
        if not id_personal:
            flash('Error: No se pudo identificar su legajo personal.', 'warning')
            return redirect(url_for('personal.inicio'))

        print(f"--- ROUTE: Solicitando récord para ID Personal: {id_personal} ---")

        # Llamamos al servicio pasando el ID PERSONAL (no el de usuario)
        historial = legajo_service.get_record_laboral(id_personal)
        
        return render_template('personal/ver_record_laboral.html', historial=historial)

    except Exception as e:
        current_app.logger.error(f"Error cargando récord: {e}")
        # Muestra el error real en pantalla para que sepamos qué pasa si falla
        flash(f'Error de sistema: {str(e)}', 'danger')
        return redirect(url_for('personal.inicio'))
    
from flask import send_file # Asegúrate de importar esto arriba
import io

# Asegúrate de importar esto arriba
import mimetypes 

@personal_bp.route('/mi-record-laboral/archivo/<int:id_record>')
@login_required
def ver_archivo_record(id_record):
    """
    Descarga INTELIGENTE: Detecta si es PDF, Excel o Imagen.
    """
    try:
        legajo_service = current_app.config['LEGAJO_SERVICE']
        
        # 1. Buscar archivo en BD
        resultado = legajo_service.get_archivo_record_laboral(id_record)
        
        if not resultado or not resultado[1]:
            flash('El documento no tiene archivo adjunto.', 'warning')
            return redirect(url_for('personal.ver_mi_record'))

        nombre_archivo = resultado[0]
        contenido_binario = resultado[1]

        # 2. Detectar el tipo MIME real según la extensión (.pdf, .xlsx, .jpg)
        tipo_mime, _ = mimetypes.guess_type(nombre_archivo)
        
        # Si no detecta nada, usamos genérico
        if not tipo_mime:
            tipo_mime = 'application/octet-stream'

        # 3. Enviar archivo
        return send_file(
            io.BytesIO(contenido_binario),
            mimetype=tipo_mime, 
            as_attachment=False, # Intenta abrir en navegador
            download_name=nombre_archivo
        )

    except Exception as e:
        current_app.logger.error(f"Error abriendo archivo: {e}")
        flash('No se pudo abrir el archivo.', 'danger')
        return redirect(url_for('personal.ver_mi_record'))