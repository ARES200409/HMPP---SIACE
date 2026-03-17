# app/application/services/legajo_service.py
# Importa la librería para calcular hashes de archivos.
import hashlib
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import io
from flask import current_app
from datetime import datetime, timedelta
import secrets
import string
import logging
from app.database import get_db_read, get_db_write
logger = logging.getLogger(__name__)


# Define el servicio que contiene la lógica de negocio para los legajos.
class LegajoService:
    # El constructor inyecta las dependencias del repositorio de personal y el servicio de auditoría.
    def __init__(self, personal_repository, audit_service, usuario_service=None):
        self._personal_repo = personal_repository
        self._audit_service = audit_service
        self._usuario_service = usuario_service

    # --- MÉTODOS DE CONSULTA (GETTERS) ---

    def get_tipos_documento_by_seccion(self, seccion_id):
        """Orquesta la obtención de tipos de documento filtrados por sección."""
        return self._personal_repo.get_tipos_documento_by_seccion(seccion_id)

    def get_document_for_download(self, document_id):
        """Recupera un documento de la base de datos y lo prepara para la descarga."""
        document_row = self._personal_repo.find_document_by_id(document_id)
        if not document_row:
            return None
        # El SP devuelve una fila con (nombre_archivo, archivo_binario)
        return {"filename": document_row[0], "data": document_row[1]}

    def check_if_dni_exists(self, dni):
        """Orquesta la verificación de la existencia de un DNI."""
        return self._personal_repo.check_dni_exists(dni)

    # ---------------------------------------------------------
    # 1. FUNCIÓN ORIGINAL INTACTA (Para que RRHH vuelva a la normalidad)
    # ---------------------------------------------------------
    def get_all_personal_paginated(self, page, per_page, filters=None):
        """Obtiene una lista paginada y filtrada de personal para RRHH."""
        return self._personal_repo.get_all_paginated(page, per_page, filters)


    # ---------------------------------------------------------
    # 2. NUEVA FUNCIÓN EXCLUSIVA PARA HISTÓRICOS (Soles de Oro, Intis)
    # ---------------------------------------------------------
    def get_personal_historico_paginated(self, page, per_page, filters=None):
        """
        Obtiene personal filtrado exclusivamente para el módulo histórico.
        Extrae datos a memoria y no cierra conexión (previene error 500).
        """
        from app.database import get_db_read
        conn = get_db_read() 
        cursor = conn.cursor()
        try:
            offset = (page - 1) * per_page
            where_clauses = ["tipo_registro = 1"] # 🚀 FILTRO HISTÓRICO OBLIGATORIO
            params = []
            
            if filters and filters.get('dni'):
                where_clauses.append("dni LIKE ?")
                params.append(f"%{filters['dni']}%")
                
            if filters and filters.get('nombres'):
                where_clauses.append("(nombres LIKE ? OR apellidos LIKE ?)")
                params.append(f"%{filters['nombres']}%")
                params.append(f"%{filters['nombres']}%")

            where_sql = " WHERE " + " AND ".join(where_clauses)

            query = f"""
                SELECT id_personal, dni, nombres, apellidos, activo as estado, tipo_registro 
                FROM personal {where_sql}
                ORDER BY apellidos ASC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            cursor.execute(query, params + [offset, per_page])
            
            columns = [column[0] for column in cursor.description]
            items = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            cursor.execute(f"SELECT COUNT(*) FROM personal {where_sql}", params)
            total = cursor.fetchone()[0]
            cursor.close()

            from app.presentation.routes.legajo_routes import RecordPagination
            return RecordPagination(items, page, per_page, total)
        except Exception as e:
            print(f"Error en listado histórico: {e}")
            return None
        # Flask cerrará la conexión automáticamente
    
    def designar_personal_historico(self, dni):
        """
        CREADO: Marca a un trabajador como 'Histórico' (1) en la BD.
        """
        conn = get_db_write() # Usando tu conexión de escritura
        cursor = conn.cursor()
        try:
            # Cambiamos tipo_registro a 1 para el DNI ingresado
            cursor.execute("UPDATE personal SET tipo_registro = 1 WHERE dni = ?", (dni,))
            rows = cursor.rowcount
            conn.commit()
            return rows > 0
        except Exception as e:
            conn.rollback()
            logger.error(f"Error designando histórico: {e}")
            return False
        finally:
            conn.close()

    def get_personal_details(self, personal_id, current_user):
        """
        Obtiene todos los detalles de un legajo y verifica permisos (IDOR).
        🚀 ACTUALIZACIÓN: Trae Récords Modernos y Planillas Históricas por separado.
        """
        # 1. VERIFICACIÓN DE SEGURIDAD (IDOR)
        if current_user.rol == 'Personal':
            if current_user.id_personal != personal_id:
                self.audit_repo.log_event(
                    current_user.id, 
                    'Seguridad', 
                    'INTENTO_IDOR_BLOQUEADO', 
                    f"Intento de acceso no autorizado al legajo {personal_id}"
                )
                raise PermissionError("Acceso denegado. Solo puede ver su propio legajo.")

        # 2. OBTENER LEGAJO BÁSICO (Esto ya trae los modernos en 'record_laboral')
        legajo = self._personal_repo.get_full_legajo_by_id(personal_id)
        if not legajo:
            return None

        # 3. OBTENER PLANILLAS HISTÓRICAS CERRADAS (Bóveda de Escalafón)
        from app.database.connector import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query_historicos = """
                SELECT 
                    id_planilla_historica as id_record, 
                    anio, mes, tipo_moneda,
                    ISNULL(ruta_generado, ruta_escaneado) as archivo_ruta,
                    'Planilla Histórica (Sustento)' as descripcion,
                    'HISTÓRICO_' + CAST(anio AS VARCHAR) + '_' + mes + '.pdf' as nombre_archivo,
                    cargo_historico, monto_neto
                FROM Planillas_Historicas
                WHERE id_personal = ? 
                ORDER BY anio DESC, 
                         CASE mes 
                            WHEN 'Diciembre' THEN 12 WHEN 'Noviembre' THEN 11 WHEN 'Octubre' THEN 10
                            WHEN 'Septiembre' THEN 9 WHEN 'Agosto' THEN 8 WHEN 'Julio' THEN 7
                            WHEN 'Junio' THEN 6 WHEN 'Mayo' THEN 5 WHEN 'Abril' THEN 4
                            WHEN 'Marzo' THEN 3 WHEN 'Febrero' THEN 2 WHEN 'Enero' THEN 1
                         END DESC
            """
            cursor.execute(query_historicos, (personal_id,))
            cols = [column[0] for column in cursor.description]
            legajo['historico_laboral'] = [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error extrayendo históricos: {e}")
            legajo['historico_laboral'] = []
        finally:
            cursor.close()
            conn.close()

        return legajo

    def get_documents_by_personal_id(self, personal_id):
        """Obtiene los documentos de un empleado."""
        return self._personal_repo.find_documents_by_personal_id(personal_id)

    # --- MÉTODOS PARA POBLAR FORMULARIOS ---

    def get_unidades_for_select(self):
        return self._personal_repo.get_unidades_for_select()

    def get_secciones_for_select(self):
        return self._personal_repo.get_secciones_for_select()

    def get_tipos_documento_for_select(self):
        return self._personal_repo.get_tipos_documento_for_select()

    # --- MÉTODOS DE OPERACIONES (CUD) ---

    def register_new_personal(self, form_data, creating_user_id):
        """
        Registra un nuevo empleado y audita la acción.
        Genera automáticamente un usuario con rol 'Personal' (ID 5).
        Soluciona la inconsistencia de nombres detectada en los logs.
        """
        try:
            # 1. Crear el registro en la tabla 'personal'
            # Se asume que form_data ya contiene DNI, Nombres, Apellidos, Sexo, etc.
            new_personal_id = self._personal_repo.create(form_data)
            
            # 2. Extraer y limpiar datos para el acceso web
            dni = form_data.get('dni', '').strip()
            nombres = form_data.get('nombres', '').strip()
            apellidos = form_data.get('apellidos', '').strip()

            if not dni:
                raise ValueError("El DNI es requerido para crear el usuario")
            
            # --- SOLUCIÓN AL ERROR DE LOGS: Unificar el nombre completo ---
            # Esto evita el error: 'El nombre completo es requerido' en UsuarioService
            nombre_completo = f"{nombres} {apellidos}"
            
            # 3. Obtener ID del rol "Personal" (ID 5)
            id_rol_personal = self._get_personal_role_id()
            
            if not id_rol_personal:
                logger.error("No se encontró ningún rol disponible en la base de datos")
                raise Exception("Error de configuración: No hay roles disponibles en el sistema")
            
            # 4. Crear usuario con los datos generados
            if self._usuario_service:
                user_data = {
                    'username': dni,                # El DNI es su nombre de usuario
                    'nombre_completo': nombre_completo, # <--- ENVIADO PARA EVITAR ERROR
                    'email': form_data.get('email') or f"{dni}@legajo.hmpp.gob.pe",
                    'password': dni,                # La contraseña inicial es su DNI
                    'id_rol': id_rol_personal,
                    'id_personal': new_personal_id  # Vínculo directo al legajo
                }

                # Llamamos a create_user y verificamos el resultado (mensaje, tipo)
                result = self._usuario_service.create_user(user_data)
                
                # Manejo del retorno (mensaje, tipo) o objeto string
                if isinstance(result, tuple) and len(result) >= 2:
                    mensaje, tipo = result[0], result[1]
                else:
                    mensaje, tipo = str(result), 'unknown'

                if tipo != 'success':
                    logger.error(f"Error creando usuario automáticamente: {mensaje}")
                    # Revertir: Si falla el usuario, lanzamos excepción para que el registro de personal no sea válido
                    raise Exception(f"No se pudo crear el usuario automáticamente: {mensaje}")

                logger.info(f"Usuario '{dni}' vinculado exitosamente al personal ID {new_personal_id}")
            else:
                logger.warning("UsuarioService no inyectado - El legajo se creó sin cuenta de acceso")
            
            # 5. Auditar la acción en el sistema
            self._audit_service.log(
                creating_user_id, 
                'Personal', 
                'CREAR', 
                f"Se creó el legajo y usuario para {nombre_completo} (DNI: {dni})", 
                form_data
            )
            
            return new_personal_id
            
        except Exception as e:
            logger.error(f"Error en register_new_personal: {str(e)}")
            raise

    def _generate_username(self, nombres: str, apellidos: str) -> str:
        """
        Genera un username único a partir del nombre y apellido.
        Formato: primeraletra_apellido (ej: c_hernandez)
        """
        try:
            # Obtener primer nombre y primer apellido, sin espacios
            primer_nombre = nombres.strip().split()[0].lower() if nombres else "user"
            primer_apellido = apellidos.strip().split()[0].lower() if apellidos else "personal"
            
            base_username = f"{primer_nombre[0]}_{primer_apellido}"
            username = base_username
            
            # Si el username ya existe, agregar números
            counter = 1
            while self._usuario_service and self._usuario_service._usuario_repo.find_by_username(username):
                username = f"{base_username}{counter}"
                counter += 1
            
            return username
            
        except Exception as e:
            logger.error(f"Error generando username: {e}")
            # Fallback: generar username aleatorio
            return f"user_{secrets.token_hex(4)}"

    def _generate_password(self, length: int = 12) -> str:
        """
        Genera una contraseña segura aleatoria.
        Incluye mayúsculas, minúsculas, números y símbolos.
        """
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        symbols = "!@#$%^&*-_=+"
        
        # Asegurar que haya al menos uno de cada tipo
        password_chars = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(digits),
            secrets.choice(symbols)
        ]
        
        # Llenar el resto de caracteres aleatoriamente
        all_chars = uppercase + lowercase + digits + symbols
        password_chars += [secrets.choice(all_chars) for _ in range(length - 4)]
        
        # Mezclar la contraseña
        random_password = ''.join(secrets.SystemRandom().sample(password_chars, len(password_chars)))
        
        return random_password

    def _get_personal_role_id(self) -> int:
        """
        Obtiene el ID del rol 'Personal' de la BD.
        Si no existe, busca un rol alternativo válido.
        """
        try:
            from app.database.connector import get_db_read
            conn = get_db_read()
            cursor = conn.cursor()
            
            # Primero intentar obtener el rol 'Personal'
            cursor.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'Personal'")
            row = cursor.fetchone()
            
            if row:
                logger.info(f"Rol 'Personal' encontrado con ID: {row[0]}")
                return row[0]
            
            # Si no existe, usar el rol alternativo 'RRHH' (válido para empleados)
            logger.warning("Rol 'Personal' no encontrado en la BD, usando 'RRHH' como alternativa")
            cursor.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'RRHH'")
            row = cursor.fetchone()
            
            if row:
                logger.info(f"Usando rol alternativo 'RRHH' con ID: {row[0]}")
                return row[0]
            
            # Si tampoco existe RRHH, obtener cualquier rol disponible
            logger.warning("Rol 'RRHH' tampoco encontrado, obteniendo primer rol disponible")
            cursor.execute("SELECT TOP 1 id_rol FROM roles ORDER BY id_rol")
            row = cursor.fetchone()
            
            if row:
                logger.info(f"Usando primer rol disponible con ID: {row[0]}")
                return row[0]
            
            logger.error("No hay ningún rol disponible en la base de datos")
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo ID del rol: {e}")
            return None

    def upload_document_to_personal(self, form_data, file_storage, current_user_id):
        """Gestiona la validación y subida de un nuevo documento."""
        if not file_storage or not file_storage.filename:
            raise ValueError("No se proporcionó ningún archivo para subir.")

        filename = file_storage.filename
        
        allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']
        if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            raise ValueError(f"Tipo de archivo no permitido. Solo se aceptan: {', '.join(allowed_extensions)}")

        file_bytes = file_storage.read()
        if len(file_bytes) > current_app.config['MAX_CONTENT_LENGTH']:
            max_size_mb = current_app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
            raise ValueError(f"El archivo es demasiado grande. El tamaño máximo es de {max_size_mb:.0f} MB.")
        
        file_storage.seek(0)
        
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        
        doc_data = form_data.copy()
        doc_data['nombre_archivo'] = filename
        doc_data['hash_archivo'] = file_hash
        id_personal = doc_data.get('id_personal')
        
        # Si no se proporciona fecha de emisión, usar la fecha actual
        if not doc_data.get('fecha_emision'):
            doc_data['fecha_emision'] = datetime.now().date()

        self._personal_repo.add_document(doc_data, file_bytes)
        
        self._audit_service.log(
            current_user_id,
            'Documentos',
            'SUBIR',
            f"Subió el archivo '{filename}' al legajo del personal ID {id_personal}"
        )

    def delete_personal_by_id(self, personal_id, deleting_user_id):
        """Orquesta la baja sincronizada y registra la auditoría para RRHH."""
        try:
            # Llamamos al repo que ahora hace la doble actualización automáticamente
            self._personal_repo.delete_by_id(personal_id)
            
            # Auditoría integral para los reportes de RRHH
            self._audit_service.log(
                deleting_user_id, 'SISTEMA', 'BAJA_TOTAL',
                f"Se desactivó completamente al personal y su acceso (ID: {personal_id})"
            )
            return True
        except Exception as e:
            logger.error(f"Fallo en la operación de baja: {e}")
            raise

    def activate_personal_by_id(self, personal_id, activating_user_id):
        """Reactiva un legajo de personal, su usuario asociado (si existe), y audita la acción."""
        persona = self._personal_repo.find_by_id(personal_id)
        if not persona:
            raise ValueError("La persona que intenta activar no existe.")

        self._personal_repo.activate_by_id(personal_id)
        
        # Si existe un usuario asociado a este personal, reactivarlo también
        if self._usuario_service:
            try:
                # Buscar usuario por DNI o email
                usuario = self._usuario_service._usuario_repo.find_by_email(persona.email) if hasattr(persona, 'email') and persona.email else None
                if usuario:
                    self._usuario_service._usuario_repo.activate_user(usuario.id)
                    self._audit_service.log(
                        activating_user_id,
                        'Usuario',
                        'ACTIVAR (Cascada)',
                        f"Usuario asociado a personal DNI {persona.dni} fue reactivado automáticamente"
                    )
            except Exception as e:
                # Log del error pero no detiene la reactivación del personal
                self._audit_service.log(
                    activating_user_id,
                    'Usuario',
                    'ERROR_REACTIVACION',
                    f"Error al reactivar usuario de personal DNI {persona.dni}: {str(e)}"
                )
        
        self._audit_service.log(
            activating_user_id,
            'Personal',
            'ACTIVAR (Reactivar)',
            f"Se reactivó el legajo del personal con DNI {persona.dni}"
        )
    def delete_document_by_id(self, document_id, deleting_user_id):
        """Orquesta la eliminación lógica de un documento y lo audita."""
        self._personal_repo.delete_document_by_id(document_id)
        self._audit_service.log(
            deleting_user_id,
            'Documentos',
            'ELIMINAR (Lógico)',
            f"Se marcó como eliminado el documento con ID {document_id}"
        )

    def process_bulk_upload(self, file_storage, creating_user_id):
        """
        Procesa un archivo Excel para la carga masiva de personal.
        Valida cada fila y registra a los nuevos empleados.
        """
        import openpyxl
        from app.utils.error_handler import registrar_error_automatico
        
        workbook = openpyxl.load_workbook(file_storage)
        sheet = workbook.active
        
        # Se asume que la primera fila es el encabezado.
        headers = [cell.value for cell in sheet[1]]
        
        # Columnas esperadas en la plantilla.
        expected_headers = [
            "DNI", "Nombres", "Apellidos", "Sexo", "FechaNacimiento", "Telefono",
            "Email", "Direccion", "EstadoCivil", "Nacionalidad", "UnidadAdministrativa",
            "FechaIngreso"
        ]

        # Validación simple de encabezados.
        if headers[:len(expected_headers)] != expected_headers:
            raise ValueError("El formato del archivo Excel es incorrecto. Las columnas no coinciden con la plantilla.")

        unidades_map = {nombre: id_ for id_, nombre in self._personal_repo.get_unidades_for_select()}

        registros_exitosos = 0
        registros_fallidos = 0
        errores = []

        # Itera sobre las filas, omitiendo el encabezado.
        for row_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            row_data = dict(zip(headers, row))
            
            try:
                # --- Validación de Datos ---
                if not all([row_data.get('DNI'), row_data.get('Nombres'), row_data.get('Apellidos')]):
                    raise ValueError("DNI, Nombres y Apellidos son obligatorios.")
                
                unidad_nombre = row_data.get('UnidadAdministrativa')
                if not unidad_nombre or unidad_nombre not in unidades_map:
                    raise ValueError(f"La unidad administrativa '{unidad_nombre}' no es válida.")

                # --- Mapeo de Datos para el Formulario ---
                form_data = {
                    'dni': str(row_data['DNI']),
                    'nombres': row_data['Nombres'],
                    'apellidos': row_data['Apellidos'],
                    'sexo': row_data.get('Sexo'),
                    'fecha_nacimiento': row_data.get('FechaNacimiento'),
                    'telefono': row_data.get('Telefono'),
                    'email': row_data.get('Email'),
                    'direccion': row_data.get('Direccion'),
                    'estado_civil': row_data.get('EstadoCivil'),
                    'nacionalidad': row_data.get('Nacionalidad', 'Peruana'),
                    'id_unidad': unidades_map[unidad_nombre],
                    'fecha_ingreso': row_data.get('FechaIngreso')
                }
                
                # Llama al método de registro existente.
                self.register_new_personal(form_data, creating_user_id)
                registros_exitosos += 1

            except Exception as e:
                registrar_error_automatico(e)
                registros_fallidos += 1
                errores.append(f"Fila {row_index}: {e}")
        
        return {"exitosos": registros_exitosos, "fallidos": registros_fallidos, "errores": errores}

    def generate_bulk_upload_template(self, unidades):
        """
        Genera una plantilla de Excel con las columnas necesarias y validaciones de datos.
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Plantilla de Carga de Personal"

        headers = [
            "DNI", "Nombres", "Apellidos", "Sexo", "FechaNacimiento", "Telefono",
            "Email", "Direccion", "EstadoCivil", "Nacionalidad", "UnidadAdministrativa",
            "FechaIngreso"
        ]
        ws.append(headers)

        # Estilo para el encabezado.
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0D47A1", end_color="0D47A1", fill_type="solid")
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill

        # --- Validación de Datos en Excel ---
        # Validación para la columna de Sexo (D).
        dv_sexo = DataValidation(type="list", formula1='"M,F"', allow_blank=True)
        dv_sexo.error = "Por favor, ingrese 'M' para Masculino o 'F' para Femenino."
        dv_sexo.errorTitle = "Valor no válido"
        ws.add_data_validation(dv_sexo)
        dv_sexo.add('D2:D1000')

        # Validación para la columna de Unidad Administrativa (K).
        nombres_unidades = [nombre for _, nombre in unidades]
        formula_unidades = f'"{",".join(nombres_unidades)}"'
        dv_unidad = DataValidation(type="list", formula1=formula_unidades, allow_blank=False)
        dv_unidad.error = "Por favor, seleccione una unidad de la lista."
        dv_unidad.errorTitle = "Unidad no válida"
        ws.add_data_validation(dv_unidad)
        dv_unidad.add('K2:K1000')

        # Ajustar ancho de columnas.
        for i, header in enumerate(headers, 1):
            ws.column_dimensions[get_column_letter(i)].width = len(header) + 5

        excel_stream = io.BytesIO()
        wb.save(excel_stream)
        excel_stream.seek(0)
        
        return excel_stream

    # --- MÉTODOS DE REPORTES Y ESTADO ---
    
    def generate_general_report_excel(self):
        """Genera un reporte general de personal en un archivo Excel."""
        personal_data = self._personal_repo.get_all_for_report()
        wb = Workbook()
        ws = wb.active
        ws.title = "Reporte General de Personal"

        # ✅ 1. Cabeceras actualizadas con los dos nuevos campos
        headers = [
            "DNI", "Apellidos", "Nombres", "Sexo", "Fecha de Nacimiento", "Email",
            "Teléfono", "Unidad Administrativa", "Fecha de Ingreso", "Estado",
            "Último Cargo", "Último Tipo de Contrato", "Modalidad", "Sueldo", "Resolución",
            "Fecha Fin Contrato", "Sistema Pensionario" # <-- Nuevas columnas aquí
        ]
        ws.append(headers)

        # Estilos de la cabecera (Fondo azul y letra blanca)
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0D47A1", end_color="0D47A1", fill_type="solid")
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # ✅ 2. Llenado de datos fila por fila
        for persona in personal_data:
            row_data = [
                persona.get('dni'), persona.get('apellidos'), persona.get('nombres'),
                persona.get('sexo'), persona.get('fecha_nacimiento'), persona.get('email'),
                persona.get('telefono'), persona.get('nombre_unidad'),
                persona.get('fecha_ingreso'), 'Activo' if persona.get('activo') else 'Inactivo',
                persona.get('cargo'), persona.get('tipo_contrato'), persona.get('modalidad'),
                persona.get('sueldo'), persona.get('resolucion'),
                persona.get('fecha_fin'), persona.get('sistema_pensionario') # <-- Extracción de los nuevos datos
            ]
            ws.append(row_data)

        # Ajuste automático del ancho de las columnas para que se vea ordenado
        for column_cells in ws.columns:
            length = max(len(str(cell.value or "")) for cell in column_cells)
            ws.column_dimensions[get_column_letter(column_cells[0].column)].width = length + 2

        # Guardado en memoria y envío del archivo
        excel_stream = io.BytesIO()
        wb.save(excel_stream)
        excel_stream.seek(0)
        
        return excel_stream

    def check_document_status_for_all_personal(self, days_to_expire=30):
        """Revisa documentos con fecha de vencimiento y resume el estado por persona."""
        all_docs = self._personal_repo.get_all_documents_with_expiration()
        status_summary = {}
        today = datetime.now().date()
        expiration_threshold = today + timedelta(days=days_to_expire)

        for doc in all_docs:
            personal_id = doc['id_personal']
            vencimiento = doc['fecha_vencimiento']

            if personal_id not in status_summary:
                status_summary[personal_id] = {'expired': 0, 'expiring_soon': 0}

            if vencimiento < today:
                status_summary[personal_id]['expired'] += 1
            elif vencimiento <= expiration_threshold:
                status_summary[personal_id]['expiring_soon'] += 1
        
        return status_summary

    def get_expiring_documents_notifications(self, days_threshold=30):
        """
        Orquesta la obtención de una lista de notificaciones sobre documentos que están por vencer.
        """
        return self._personal_repo.find_expiring_documents(days_threshold)

    def get_empleados_por_unidad(self):
        """
        Orquesta la obtención del conteo de empleados por cada unidad administrativa.
        Este método es utilizado por el panel de RRHH para generar gráficos.
        """
        return self._personal_repo.count_empleados_por_unidad()

    def get_empleados_activos_inactivos(self):
        """Orquesta la obtención del conteo de empleados por estado (activo/inactivo)."""
        return self._personal_repo.count_empleados_por_estado()

    def get_empleados_por_sexo(self):
        """Orquesta la obtención del conteo de empleados por sexo."""
        return self._personal_repo.count_empleados_por_sexo()

    def update_personal_details(self, personal_id, form_data, updating_user_id):
        """Actualiza los detalles de un legajo de personal y audita la acción."""
        self._personal_repo.update(personal_id, form_data)
        self._audit_service.log(
            updating_user_id, 
            'Personal', 
            'ACTUALIZAR', 
            f"Se actualizaron los datos del legajo para el personal ID {personal_id}", 
            form_data
        )

    def get_deleted_documents(self):
        """Obtiene todos los documentos marcados como eliminados (activo = 0)."""
        return self._personal_repo.get_deleted_documents()

    def get_document_by_id(self, document_id):
        """Obtiene los detalles de un documento específico."""
        return self._personal_repo.find_document_by_id(document_id)

    def recover_document(self, document_id):
        """Reactiva un documento marcado como eliminado."""
        self._personal_repo.recover_document(document_id)

    def permanently_delete_document(self, document_id):
        """Elimina permanentemente un documento de la base de datos."""
        self._personal_repo.permanently_delete_document(document_id)

    def verify_document_access(self, document_id, user):
        """
        Verifica si un usuario tiene permiso para ver un documento.
        Retorna True si es admin/rrhh o si es el dueño del documento.
        """
        # Roles administrativos tienen acceso total
        if user.rol in ['AdministradorLegajos', 'RRHH', 'Sistemas']:
            return True
            
        # Para personal, verificar propiedad
        if user.rol == 'Personal':
            owner_id = self._personal_repo.get_document_owner(document_id)
            user_personal_id = getattr(user, 'id_personal', None)
            
            # Si el documento existe y pertenece al usuario actual
            return owner_id is not None and owner_id == user_personal_id
            
        return False

    # --- MÉTODOS PARA EL PASO 2 (CONTRATOS Y USUARIOS) ---

    def get_usuario_por_username(self, username):
        """
        Busca un usuario por su DNI (username) para verificar su cuenta.
        """
        try:
            if self._usuario_service:
                # Usamos el servicio de usuario inyectado
                return self._usuario_service.get_usuario_by_username(username)
            return None
        except Exception as e:
            logger.error(f"Error al buscar usuario {username}: {str(e)}")
            return None

    def crear_contrato_inicial(self, contrato_data):
        """
        Registra el primer contrato del trabajador para activar su ficha laboral.
        Esto llena los campos de 'Cargo' y 'Unidad' en la vista de Mis Datos.
        """
        try:
            # 1. Validaciones básicas
            if not contrato_data.get('id_personal'):
                raise ValueError("El ID del personal es obligatorio para el contrato.")

            # 2. Llamada al repositorio para insertar en dbo.contratos
            # Asegúrate de que tu repo tenga el método add_contract
            success = self._personal_repo.add_contract(contrato_data)
            
            if success:
                logger.info(f"Contrato inicial creado para personal ID {contrato_data['id_personal']}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error en crear_contrato_inicial: {str(e)}")
            raise
        
    # 🚀 NUEVOS MÉTODOS PARA EL PASO 2
    
    def get_usuario_por_username(self, username):
        """Busca si el DNI ya tiene un usuario creado para evitar duplicados."""
        if self._usuario_service:
            # Buscamos en el repositorio de usuarios inyectado
            return self._usuario_service._usuario_repo.find_by_username(username)
        return None

    def crear_usuario_acceso(self, usuario_obj):
        """Guarda el objeto Usuario en la base de datos."""
        if self._usuario_service:
            # Usamos el repositorio de usuarios para persistir el objeto Usuario
            return self._usuario_service._usuario_repo.save(usuario_obj)
        return False

    def search_documents(self, query=None, id_seccion=None, id_tipo=None):
        """
        Orquesta la búsqueda de documentos por descripción, tipo o sección.
        """
        return self._personal_repo.search_documents(query, id_seccion, id_tipo)


    # Reemplaza la función get_record_laboral con esto:
    def get_record_laboral(self, id_personal):
        """
        Recibe DIRECTAMENTE el id_personal (ej: 7) y busca sus documentos.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            print(f"--- DEBUG: Buscando Récord para Personal ID: {id_personal} ---")
            
            # Consulta directa a record_laboral
            # Usamos COALESCE para que no falle si alguna fecha está vacía
            query = """
                SELECT 
                    id_record,
                    descripcion,
                    fecha_inicio,
                    fecha_fin_vencimiento,
                    nombre_archivo,
                    activo
                FROM record_laboral
                WHERE id_personal = ?
                ORDER BY id_record DESC
            """
            cursor.execute(query, (id_personal,))
            
            # Convertir resultados a diccionario
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            print(f"--- DEBUG: Encontrados {len(results)} registros ---")
            return results

        except Exception as e:
            print(f"--- ERROR en get_record_laboral: {e} ---")
            return []
        finally:
            conn.close()

    # 2. Función NUEVA para DESCARGAR EL PDF (Binario)
    def get_archivo_record_laboral(self, id_record):
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # Traemos el nombre y el BINARIO (blob)
            query = "SELECT nombre_archivo, archivo_binario FROM record_laboral WHERE id_record = ?"
            cursor.execute(query, (id_record,))
            return cursor.fetchone()
        except Exception as e:
            print(f"Error obteniendo binario récord: {e}")
            return None
        finally:
            conn.close()


    def get_info_perfil_por_usuario(self, id_usuario, dni_usuario=None):
        """
        Busca datos del personal. 
        Intenta primero por id_usuario. Si falla, intenta por DNI (asumiendo que username es DNI).
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            print(f"--- BUSCANDO PERFIL: ID={id_usuario}, DNI_POSIBLE={dni_usuario} ---")
            
            # Consultamos por id_usuario O por dni
            query = """
                SELECT 
                    nombres, 
                    apellidos, 
                    dni, 
                    email_institucional, 
                    email_personal,
                    telefono, 
                    unidad_organica as unidad_administrativa, 
                    cargo, 
                    fecha_inicio as fecha_ingreso
                FROM personal 
                WHERE id_usuario = ? OR dni = ?
            """
            # Pasamos los parámetros dos veces (uno para cada ?)
            cursor.execute(query, (id_usuario, dni_usuario))
            row = cursor.fetchone()
            
            if row:
                print("--- ¡PERFIL ENCONTRADO! ---")
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, row))
            
            print("--- NO SE ENCONTRÓ PERFIL ---")
            return None
        except Exception as e:
            print(f"Error buscando perfil: {e}")
            return None
        finally:
            conn.close()

    # En app/application/services/legajo_service.py

    def cambiar_estado_personal(self, id_personal, nuevo_estado):
        """
        Cambia el campo 'activo' en PERSONAL y sincroniza ÚNICAMENTE con el USUARIO correspondiente.
        """
        conn = get_db_write() 
        cursor = conn.cursor()
        
        try:
            logger.info(f"--- PROCESANDO: ID {id_personal} -> Estado solicitado: {nuevo_estado} ---")

            # 1. Definir valor numérico (1 o 0)
            estados_positivos = ['Activo', 'ACTIVO', 'activo', '1', 1, True, 'Habilitado']
            es_activo_bit = 1 if nuevo_estado in estados_positivos else 0

            # 2. Actualizar PERSONAL (Solo este ID)
            query_rrhh = "UPDATE personal SET activo = ? WHERE id_personal = ?"
            cursor.execute(query_rrhh, (es_activo_bit, id_personal))

            # 3. Actualizar USUARIO (Solo el vinculado a este ID)
            # VERIFICACIÓN DOBLE: Usamos una subconsulta exacta
            query_sistemas = """
                UPDATE usuarios 
                SET activo = ? 
                WHERE id_personal = ?  -- Usamos id_personal directamente si existe la FK, es más seguro
            """
            
            # Si no tienes la columna id_personal en la tabla usuarios, usa esta versión:
            # query_sistemas = "UPDATE usuarios SET activo = ? WHERE id_usuario = (SELECT id_usuario FROM personal WHERE id_personal = ?)"

            cursor.execute(query_sistemas, (es_activo_bit, id_personal))
            
            if cursor.rowcount > 1:
                # Si afectó a más de 1, algo anda muy mal -> Rollback
                conn.rollback()
                return False, "Error de seguridad: La actualización iba a afectar a múltiples usuarios. Operación cancelada."

            conn.commit()
            return True, f"Estado actualizado a {'Activo' if es_activo_bit else 'Inactivo'} correctamente."

        except Exception as e:
            conn.rollback()
            logger.error(f"Error en sincronización: {e}")
            return False, f"Error técnico: {str(e)}"
        finally:
            conn.close()