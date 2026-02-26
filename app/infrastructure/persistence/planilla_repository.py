from app.database import get_db_read, get_db_write
from datetime import datetime

class PlanillaRepository:
    
    def get_all_planillas(self):
        """Lista todas las carpetas de planillas creadas, incluyendo totales financieros."""
        # Asegúrate de que get_db_read esté importado al inicio del archivo
        # from app.database import get_db_read
        
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
                SELECT 
                    p.id_planilla, 
                    p.anio, 
                    p.mes, 
                    p.tipo_planilla, 
                    p.estado, 
                    p.fecha_apertura,
                    p.pdf_generado,  -- <--- ¡IMPORTANTE! Agregado para habilitar el Ojo Verde
                    
                    -- 1. Total de Trabajadores
                    (SELECT COUNT(*) FROM detalle_planilla d WHERE d.id_planilla = p.id_planilla) as total_trabajadores,
                    
                    -- 2. Total Neto (Lo que reciben los trabajadores)
                    (SELECT SUM(ISNULL(neto_pagar, 0)) FROM detalle_planilla d WHERE d.id_planilla = p.id_planilla) as total_monto,

                    -- 3. Total Aportes HMPP (Essalud + SCTR + CTS)
                    (SELECT SUM(ISNULL(aporte_essalud, 0) + ISNULL(sctr_onp, 0) + ISNULL(sctr, 0) + ISNULL(cts, 0)) 
                     FROM detalle_planilla d WHERE d.id_planilla = p.id_planilla) as total_aportes

                FROM planillas p
                WHERE p.eliminado = 0
                ORDER BY p.anio DESC, p.mes DESC
            """
            cursor.execute(query)
            
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                # Creamos el diccionario con los datos crudos
                row_dict = dict(zip(columns, row))
                
                # Conversión de seguridad: Aseguramos que pdf_generado sea True/False para Jinja
                # (A veces SQL devuelve 1 o 0, y Python necesita evaluar el booleano explícito)
                if 'pdf_generado' in row_dict:
                    row_dict['pdf_generado'] = bool(row_dict['pdf_generado'])
                
                results.append(row_dict)
            
            return results
            
        except Exception as e:
            print(f"Error en get_all_planillas: {e}")
            return []
        finally:
            cursor.close()
            # conn.close()  <-- ELIMINADO: Dejamos la conexión abierta para evitar errores en middlewares

    def crear_planilla_mensual(self, anio, mes, tipo_texto):
        """
        AUTOMATIZACIÓN TOTAL: Crea la planilla jalando el ÚLTIMO sueldo 
        registrado por ID de contrato. 
        Evita errores si faltan columnas nuevas en la tabla personal insertando NULLs temporales.
        """
        from app.database import get_db_write
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # 1. TRADUCTOR BLINDADO (Acepta variaciones de texto y evita el error de "Cargar Todos")
            tipo_limpio = str(tipo_texto).strip().upper()
            
            mapa_tipos = {
                'D.L. 1057 (CAS)': 1,
                'CAS': 1,
                'D.L. 276 (NOMBRADO)': 2,
                'NOMBRADO': 2,
                'D.L. 728': 3,
                '728': 3,
                'LOCACIÓN DE SERVICIOS (TERCEROS)': 4,
                'TERCERO': 4,
                'TERCEROS': 4,
                'CAS_CONFIANZA': 5,
                'CAS CONF.': 5,
                'TODOS': 0
            }
            
            id_tipo_contrato_filtro = mapa_tipos.get(tipo_limpio, -1)
            
            if id_tipo_contrato_filtro == -1 and tipo_limpio != 'TODOS':
                raise Exception(f"El tipo de personal '{tipo_texto}' no está reconocido en el sistema.")
            
            # 2. Crear Cabecera de Planilla
            sql_header = """
                INSERT INTO planillas (anio, mes, tipo_planilla, estado)
                OUTPUT INSERTED.id_planilla
                VALUES (?, ?, ?, 'ABIERTA')
            """
            cursor.execute(sql_header, (anio, mes, tipo_texto))
            row = cursor.fetchone()
            if not row:
                raise Exception("No se pudo crear la cabecera de la planilla.")
            
            id_planilla = row[0]
            print(f"--- Generando Planilla {id_planilla} para {tipo_texto} ---")

            # 3. INSERTAR DETALLE (Blindado contra columnas faltantes en la BD)
            sql_detalle = """
                WITH UltimosContratos AS (
                    SELECT 
                        id_personal, sueldo, id_tipo_contrato,
                        ROW_NUMBER() OVER (
                            PARTITION BY id_personal 
                            ORDER BY id_contrato DESC 
                        ) as ranking
                    FROM contratos
                )
                
                INSERT INTO detalle_planilla (
                    id_planilla, id_personal, dni_trabajador, nombre_completo, 
                    cargo_actual, sueldo_basico, total_ingresos, neto_pagar,
                    sistema_pensionario, id_tipo_contrato,
                    
                    -- Campos extendidos de la ficha
                    meta, nivel, condicion_laboral, tipo_trabajador, ubicacion,
                    cuspp, cuenta_cts, autogenerado, fecha_ingreso_afp, fotocheck,
                    es_sindicalizado
                )
                SELECT 
                    ? AS id_planilla,
                    p.id_personal, 
                    p.dni, 
                    (p.apellidos + ' ' + p.nombres) AS nombre_completo,
                    ISNULL(c.nombre_cargo, 'Sin Cargo') AS cargo_actual,
                    
                    ISNULL(ct.sueldo, 0) AS sueldo_basico,
                    ISNULL(ct.sueldo, 0) AS total_ingresos,
                    ISNULL(ct.sueldo, 0) AS neto_pagar,
                    'ONP' AS sistema_pensionario,
                    P.id_tipo_contrato,
                    
                    -- Se insertan en NULL para llenarlos luego desde la web
                    NULL AS meta,
                    NULL AS nivel,
                    NULL AS condicion_laboral,
                    NULL AS tipo_trabajador,
                    (SELECT TOP 1 nombre FROM unidad_administrativa WHERE id_unidad = p.id_unidad) AS ubicacion,
                    NULL AS cuspp,
                    NULL AS cuenta_cts,
                    NULL AS autogenerado,
                    NULL AS fecha_ingreso_afp,
                    NULL AS fotocheck,
                    0 AS es_sindicalizado

                FROM personal p
                LEFT JOIN cargos c ON p.id_cargo = c.id_cargo
                INNER JOIN UltimosContratos ct ON p.id_personal = ct.id_personal AND ct.ranking = 1
                
                WHERE p.activo = 1 
                  AND (p.id_tipo_contrato = ? OR ? = 0)
            """
            
            cursor.execute(sql_detalle, (id_planilla, id_tipo_contrato_filtro, id_tipo_contrato_filtro))
            count = cursor.rowcount
            
            conn.commit()
            return id_planilla, f"Planilla generada con {count} trabajadores sincronizados correctamente."

        except Exception as e:
            conn.rollback()
            print(f"⚠️ ERROR al crear planilla: {e}")
            raise e
        finally:
            conn.close()

    def get_detalle_planilla(self, id_planilla):
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # We use ISNULL to force zeros at the database level
            query = """
                SELECT 
                    id_detalle, id_planilla, dni_trabajador, 
                    UPPER(nombre_completo) as nombre_completo,
                    ISNULL(cargo_actual, '-') as cargo_actual,
                    ISNULL(sistema_pensionario, '-') as sistema_pensionario,
                    ISNULL(dias_laborados, 30) as dias_laborados,
                    
                    -- INCOMES (Force 0.0)
                    ISNULL(sueldo_basico, 0) as sueldo_basico,
                    ISNULL(reintegros, 0) as reintegros,
                    ISNULL(bonificaciones, 0) as bonificaciones,
                    ISNULL(asignacion_familiar, 0) as asignacion_familiar,
                    ISNULL(total_ingresos, 0) as total_ingresos,
                    
                    -- DISCOUNTS (Force 0.0)
                    ISNULL(monto_pension, 0) as monto_pension,
                    ISNULL(faltas_tardanzas, 0) as faltas_tardanzas,
                    ISNULL(judiciales, 0) as judiciales,
                    ISNULL(otros_descuentos, 0) as otros_descuentos,
                    ISNULL(renta_4ta_5ta, 0) as renta_4ta_5ta,
                    ISNULL(essalud_vida, 0) as essalud_vida,
                    ISNULL(total_descuentos, 0) as total_descuentos,
                    
                    -- CONTRIBUTIONS (Force 0.0)
                    ISNULL(aporte_essalud, 0) as aporte_essalud,
                    ISNULL(sctr_onp, 0) as sctr_onp,
                    ISNULL(sctr, 0) as sctr,
                    ISNULL(cts, 0) as cts,
                    
                    -- NET (Force 0.0)
                    ISNULL(neto_pagar, 0) as neto_pagar,
                    
                    fecha_generacion_boleta
                FROM detalle_planilla 
                WHERE id_planilla = ? 
                ORDER BY nombre_completo ASC
            """
            cursor.execute(query, (id_planilla,))
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ SQL ERROR: {e}")
            return []
        finally:
            cursor.close()

    def actualizar_montos_detalle(self, id_detalle, data):
        """
        Actualiza los montos y las descripciones (glosas) de una boleta específica,
        incluyendo los nuevos campos (Nivel, Meta, Ubicación, Sindicato, Viáticos,
        Inasistencias Justificadas) y GUARDA EL DESGLOSE DINÁMICO para el Récord Laboral.
        """
        import json  # Importante para leer el paquete de bonos dinámicos
        from app.database import get_db_write
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # --- 1. RECIBIR DATOS DEL FORMULARIO ---
            
            # TEXTOS FIJOS Y METADATOS HMPP
            nivel = data.get('nivel', '')
            meta = data.get('meta', '')
            cuspp = data.get('cuspp', '')
            cuenta_cts = data.get('cuenta_cts', '')
            ubicacion = data.get('ubicacion', '')
            tipo_trabajador = data.get('tipo_trabajador', '')
            autogenerado = data.get('autogenerado', '')
            actividad = data.get('actividad', '')
            condicion_laboral = data.get('condicion_laboral', '')
            fotocheck = data.get('fotocheck', '')
            
            # TEXTOS ANTIGUOS
            glosa_bonos = data.get('glosa_bonos', '')      
            glosa_otros = data.get('glosa_otros', '')      
            observaciones = data.get('observaciones', '')  
            sistema_pensionario = data.get('sistema_pensionario', '')
            nocuenta = data.get('nocuenta', '')

            # NÚMEROS DE ASISTENCIA Y SCTR
            dias_laborados = int(data.get('dias_laborados', 30) or 30)
            dias_falta = int(data.get('dias_falta', 0) or 0)
            dias_subsidiados = int(data.get('dias_subsidiados', 0) or 0)
            horas_laboradas = int(data.get('horas_laboradas', 176) or 176)
            dias_computables = int(data.get('dias_computables', 30) or 30)
            tasa_sctr = float(data.get('tasa_sctr', 0) or 0)
            
            # 🔥 INASISTENCIAS JUSTIFICADAS
            d_medico = int(data.get('d_medico', 0) or 0)
            d_vacaciones = int(data.get('d_vacaciones', 0) or 0)
            d_permisos = int(data.get('d_permisos', 0) or 0)
            d_suspensiones = int(data.get('d_suspensiones', 0) or 0)
            d_otros_inasis = int(data.get('d_otros_inasis', 0) or 0)
            
            # INGRESOS
            d_viatico = float(data.get('d_viatico', 0) or 0)
            reintegros = float(data.get('reintegros', 0) or 0)
            bonos = float(data.get('bonos', 0) or 0)
            asignacion_familiar = float(data.get('asig_familiar', 0) or 0)
            
            # DESCUENTOS Y APORTES
            monto_pension = float(data.get('monto_pension', 0) or 0)
            essalud_vida = float(data.get('essalud_vida', 0) or 0)
            renta_4ta = float(data.get('renta_4ta', 0) or 0)
            faltas_monto = float(data.get('faltas_monto', 0) or 0) 
            judiciales = float(data.get('judiciales', 0) or 0)
            otros_desc = float(data.get('otros', 0) or 0)
            
            rps = float(data.get('rps', 0) or 0)
            sctr_onp = float(data.get('sctr_onp', 0) or 0)
            sctr = float(data.get('sctr', 0) or 0)
            cts = float(data.get('cts', 0) or 0)
            mon_aseg = float(data.get('mon_aseg', 0) or 0)
            
            # SINDICATO 
            es_sindicalizado = 1 if str(data.get('es_sindicalizado')).upper() == 'SI' else 0
            desc_sindicato = float(data.get('desc_sindicato', 0) or 0)

            # 🔥 LEER EL DESGLOSE DINÁMICO (Ingresos, Descuentos y Aguinaldos)
            json_conceptos_str = data.get('json_conceptos', '[]')
            try:
                lista_conceptos = json.loads(json_conceptos_str)
            except Exception:
                lista_conceptos = []

            # --- 2. CÁLCULOS MATEMÁTICOS ---
            cursor.execute("SELECT sueldo_basico FROM detalle_planilla WHERE id_detalle = ?", (id_detalle,))
            row = cursor.fetchone()
            if not row:
                return False 
            
            sueldo = float(row[0])

            # Recálculo de Totales (Añadimos Viático a la suma Bruta)
            total_ingresos = sueldo + asignacion_familiar + d_viatico + reintegros + bonos
            
            # Sumamos el sindicato al total de descuentos
            total_descuentos = (monto_pension + essalud_vida + renta_4ta + 
                                faltas_monto + judiciales + otros_desc + desc_sindicato)
            
            neto_pagar = total_ingresos - total_descuentos
            if neto_pagar < 0:
                neto_pagar = 0
            
            base_calculo = mon_aseg if mon_aseg > 0 else sueldo
            aporte_essalud = base_calculo * 0.09

            # --- 3. ACTUALIZAR BASE DE DATOS (TABLA PRINCIPAL) ---
            sql = """
                UPDATE detalle_planilla SET 
                    nivel = ?, meta = ?, cuspp = ?, cuenta_cts = ?, tasa_sctr = ?,
                    ubicacion = ?, tipo_trabajador = ?, autogenerado = ?,
                    dias_subsidiados = ?, horas_laboradas = ?, dias_computables = ?,
                    es_sindicalizado = ?, desc_sindicato = ?,
                    actividad = ?, condicion_laboral = ?, fotocheck = ?,
                
                    dias_laborados = ?, sistema_pensionario = ?, nocuenta = ?, mon_aseg = ?,

                    -- Ingresos
                    d_viatico = ?, reintegros = ?, bonificaciones = ?, asignacion_familiar = ?, 
                    total_ingresos = ?, glosa_bonos = ?,
                    
                    -- Descuentos
                    monto_pension = ?, essalud_vida = ?, renta_4ta_5ta = ?, 
                    dias_falta = ?, faltas_tardanzas = ?, 
                    judiciales = ?, otros_descuentos = ?, total_descuentos = ?,
                    glosa_otros = ?,  
                    
                    -- Aportes
                    rps = ?, sctr_onp = ?, sctr = ?, cts = ?, aporte_essalud = ?,
                    
                    -- Finales
                    neto_pagar = ?, observaciones = ?,
                    
                    -- Inasistencias Justificadas
                    d_medico = ?, d_vacaciones = ?, d_permisos = ?, d_suspensiones = ?, d_otros_inasis = ?
                    
                WHERE id_detalle = ?
            """
            
            cursor.execute(sql, (
                # Nuevos y Metadatos
                nivel, meta, cuspp, cuenta_cts, tasa_sctr,
                ubicacion, tipo_trabajador, autogenerado,
                dias_subsidiados, horas_laboradas, dias_computables,
                es_sindicalizado, desc_sindicato,
                actividad, condicion_laboral, fotocheck,
                
                # Datos Generales
                dias_laborados, sistema_pensionario, nocuenta, mon_aseg,
                
                # Ingresos
                d_viatico, reintegros, bonos, asignacion_familiar,
                total_ingresos, glosa_bonos, 
                
                # Descuentos
                monto_pension, essalud_vida, renta_4ta,
                dias_falta, faltas_monto,
                judiciales, otros_desc, total_descuentos,
                glosa_otros, 
                
                # Aportes
                rps, sctr_onp, sctr, cts, aporte_essalud,
                
                # Finales
                neto_pagar, observaciones,
                
                # Inasistencias Justificadas
                d_medico, d_vacaciones, d_permisos, d_suspensiones, d_otros_inasis,
                
                # ID (WHERE)
                id_detalle
            ))
            
            # --- 4. MAGIA: GUARDAR EL DESGLOSE DINÁMICO ---
            # 4.1 Limpiamos los conceptos anteriores de este trabajador
            cursor.execute("DELETE FROM detalle_conceptos_trabajador WHERE id_detalle = ?", (id_detalle,))
            
            # 4.2 Insertamos uno por uno los conceptos que llegaron en el JSON
            if len(lista_conceptos) > 0:
                sql_insert_desglose = """
                    INSERT INTO detalle_conceptos_trabajador (id_detalle, id_concepto, monto)
                    VALUES (?, ?, ?)
                """
                for concepto in lista_conceptos:
                    cursor.execute(sql_insert_desglose, (id_detalle, concepto['id_concepto'], concepto['monto']))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error al guardar ficha: {e}")
            raise e

    # ... (resto del código igual) ...

    def get_detalle_por_id(self, id_detalle):
        """
        Busca la información de UN trabajador para la pantalla de edición/PDF.
        CORREGIDO: El 'regimen_laboral' se lee directamente de la tabla detalle_planilla (dp)
        para respetar el tipo de contrato con el que se generó la planilla.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # 🚀 LÓGICA BLINDADA:
            # 1. Obtenemos el régimen (tc.nombre_tipo) usando dp.id_tipo_contrato.
            #    Esto garantiza que si la planilla es NOMBRADO, diga NOMBRADO.
            # 2. Mantenemos el JOIN a contratos SOLO para sacar la fecha de ingreso (informativo).
            query = """
                SELECT 
                    dp.*, 
                    pl.mes,
                    pl.anio,
                    p.direccion,
                    p.telefono,
                    -- Formato de fecha para mostrar ingreso (DD/MM/AAAA)
                    CONVERT(VARCHAR, ct.fecha_inicio, 103) as fecha_ingreso_fmt,
                    ISNULL(ua.nombre, 'Sin Asignar') as oficina_nombre,
                    
                    -- CORRECCIÓN CLAVE: El nombre del régimen viene de la planilla, no del historial
                    tc.nombre_tipo as regimen_laboral

                FROM detalle_planilla dp
                INNER JOIN planillas pl ON dp.id_planilla = pl.id_planilla
                INNER JOIN personal p ON dp.id_personal = p.id_personal
                
                -- 1. JOIN CORRECTO: Usamos el ID guardado en el detalle de la planilla (SNAPSHOT)
                LEFT JOIN tipos_contrato tc ON dp.id_tipo_contrato = tc.id_tipo_contrato
                
                -- 2. JOIN A CONTRATOS (Solo para obtener la fecha de inicio histórica)
                -- Usamos TOP 1 o lógica de fechas para evitar duplicados que rompan la query
                LEFT JOIN contratos ct ON p.id_personal = ct.id_personal 
                                      AND (ct.fecha_fin IS NULL OR ct.fecha_fin >= GETDATE())
                
                LEFT JOIN cargos c ON p.id_cargo = c.id_cargo
                LEFT JOIN unidad_administrativa ua ON p.id_unidad = ua.id_unidad
                
                WHERE dp.id_detalle = ?
            """
            cursor.execute(query, (id_detalle,))
            
            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()
            
            cursor.close() 

            if row:
                return dict(zip(columns, row))
            return None

        except Exception as e:
            print(f"⚠️ Error en get_detalle_por_id: {e}")
            return None
        # IMPORTANTE: Ya NO cerramos 'conn' aquí. 
        # connector.py lo hará automáticamente al terminar la petición.

    def eliminar_planilla_logico(self, id_planilla, id_usuario):
        """Mueve la planilla a la papelera en lugar de borrarla físicamente."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # Solo actualizamos la cabecera. 
            # El detalle se mantiene intacto en la BD pero 'oculto' al usuario.
            query = """
                UPDATE planillas 
                SET eliminado = 1, 
                    fecha_eliminacion = GETDATE(), 
                    usuario_eliminacion_id = ?
                WHERE id_planilla = ?
            """
            cursor.execute(query, (id_usuario, id_planilla))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"🔥 Error al mover a papelera: {e}")
            return False
        finally:
            conn.close()

    def guardar_pdf_boleta(self, id_detalle, pdf_bytes):
        """
        Guarda el binario del PDF en la base de datos.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            sql = """
                UPDATE detalle_planilla 
                SET archivo_boleta = ?, 
                    fecha_generacion_boleta = GETDATE()
                WHERE id_detalle = ?
            """
            # pyodbc maneja automáticamente los bytes para VARBINARY
            cursor.execute(sql, (pdf_bytes, id_detalle))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Error guardando PDF en BD: {e}")
            return False
        # Nota: No cerramos conn aquí porque usas connector.py con Flask

    def obtener_pdf_guardado(self, id_detalle):
        """Devuelve los bytes del PDF guardado en BD."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = "SELECT archivo_boleta FROM detalle_planilla WHERE id_detalle = ?"
            cursor.execute(query, (id_detalle,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0] # Retorna los bytes
            return None
        finally:
            conn.close()


    def cerrar_planilla(self, id_planilla):
        """Cambia el estado de la planilla a CERRADA."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            query = "UPDATE planillas SET estado = 'CERRADA' WHERE id_planilla = ?"
            cursor.execute(query, (id_planilla,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error cerrando planilla: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


    def abrir_planilla(self, id_planilla):
        """Re-abre una planilla cerrada (permite volver a editar)."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            query = "UPDATE planillas SET estado = 'ABIERTA' WHERE id_planilla = ?"
            cursor.execute(query, (id_planilla,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error abriendo planilla: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def obtener_planilla_por_id(self, id_planilla):
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id_planilla, mes, anio, tipo_planilla, estado FROM planillas WHERE id_planilla = ?", (id_planilla,))
            row = cursor.fetchone()
            if row:
                # Blindaje contra None en mes y año
                mes_idx = row[1] if row[1] is not None else 0
                anio_val = row[2] if row[2] is not None else datetime.now().year
                
                meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                
                return {
                    'id_planilla': row[0],
                    'mes': mes_idx,
                    'anio': anio_val,
                    'mes_nombre': meses[mes_idx] if 0 < mes_idx < 13 else 'S/N',
                    'tipo_planilla': row[3] or 'GENERAL',
                    'estado': row[4] or 'ABIERTA'
                }
            return None
        finally:
            cursor.close()

    def obtener_conteo_sin_contrato(self):
        """Cuenta trabajadores activos que no tienen registros en la tabla contratos."""
        # 🚀 CLAVE: Usamos get_db_read() siempre para tener una conexión nueva
        from app.database import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
                SELECT COUNT(*) 
                FROM personal p 
                WHERE p.activo = 1 
                AND NOT EXISTS (SELECT 1 FROM contratos WHERE id_personal = p.id_personal)
            """
            cursor.execute(query)
            resultado = cursor.fetchone()
            return resultado[0] if resultado else 0
        except Exception as e:
            # Este es el error que ves en tu terminal negra
            print(f"⚠️ Error silencioso en contador: {e}") 
            return 0
        finally:
            # Cerramos solo después de haber guardado el resultado en la variable
            cursor.close()
            conn.close()

    def obtener_pendientes_contrato(self):
        """Devuelve la lista detallada de trabajadores activos sin contrato."""
        from app.database import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # ✅ CORREGIDO: Usamos 'apellidos' porque así se llama en tu base de datos
            query = """
                SELECT id_personal, dni, nombres, apellidos 
                FROM personal p 
                WHERE p.activo = 1 
                  AND NOT EXISTS (SELECT 1 FROM contratos WHERE id_personal = p.id_personal)
            """
            cursor.execute(query)
            
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
                
            return results
        except Exception as e:
            print(f"⚠️ Error obteniendo lista de pendientes: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_reporte_general_data(self, id_planilla):
        """Obtiene TODOS los datos detallados para el reporte PDF (Sábana de Planilla)."""
        from app.database import get_db_read
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
                SELECT 
                    -- 1. IDENTIFICACIÓN Y CARGO
                    ROW_NUMBER() OVER(ORDER BY p.apellidos) as item,
                    p.dni,
                    p.apellidos + ', ' + p.nombres as nombre_completo,
                    ISNULL(c.nombre_cargo, dp.cargo_actual) as cargo,
                    dp.sistema_pensionario as regimen_pensionario, 
                    ISNULL(dp.nocuenta, '-') as cuenta_bancaria,
                    p.fecha_ingreso,

                    -- 2. DÍAS LABORADOS Y CONCEPTOS REMUNERATIVOS
                    ISNULL(dp.dias_laborados, 30) as dias_laborados,
                    ISNULL(dp.sueldo_basico, 0) as remuneracion_mensual,
                    ISNULL(dp.asignacion_familiar, 0) as asig_familiar,
                    
                    -- 🔥 NUEVO: MOVILIDAD / VIÁTICOS
                    ISNULL(dp.d_viatico, 0) as d_viatico,
                    
                    ISNULL(dp.reintegros, 0) as reintegros,           
                    ISNULL(dp.bonificaciones, 0) as otros_ingresos,   
                    ISNULL(dp.total_ingresos, 0) as total_remuneracion,

                    -- 3. DESCUENTOS AL TRABAJADOR
                    ISNULL(dp.dias_falta, 0) as dias_falta,
                    ISNULL(dp.faltas_tardanzas, 0) as dscto_tardanza, 
                    ISNULL(dp.monto_pension, 0) as sistema_pension, 
                    
                    -- 🔥 NUEVO: CUOTA SINDICAL
                    ISNULL(dp.desc_sindicato, 0) as desc_sindicato,
                    
                    ISNULL(dp.renta_4ta_5ta, 0) as renta_5ta,            
                    ISNULL(dp.essalud_vida, 0) as essalud_vida,      
                    ISNULL(dp.judiciales, 0) as judicial,    
                    ISNULL(dp.otros_descuentos, 0) as prestamos,     
                    ISNULL(dp.total_descuentos, 0) as total_descuentos,                            

                    -- 4. NETO A PAGAR Y AGUINALDOS
                    -- 🔥 NUEVO: SUMATORIA DINÁMICA DE AGUINALDOS
                    ISNULL((
                        SELECT SUM(monto) 
                        FROM detalle_conceptos_trabajador dct 
                        INNER JOIN catalogo_conceptos cc ON dct.id_concepto = cc.id_concepto 
                        WHERE dct.id_detalle = dp.id_detalle AND cc.tipo = 'AGUINALDO'
                    ), 0) as tot_aguinaldos,
                    
                    -- 🔥 NUEVO: TEXTO DESGLOSADO DEL AGUINALDO
                    ISNULL((
                        SELECT STUFF((
                            SELECT ' + ' + cc.nombre_concepto + ': ' + CAST(CAST(dct.monto AS DECIMAL(10,2)) AS VARCHAR)
                            FROM detalle_conceptos_trabajador dct 
                            INNER JOIN catalogo_conceptos cc ON dct.id_concepto = cc.id_concepto 
                            WHERE dct.id_detalle = dp.id_detalle AND cc.tipo = 'AGUINALDO'
                            FOR XML PATH('')
                        ), 1, 3, '')
                    ), '') as glosa_aguinaldos,
                    
                    ISNULL(dp.neto_pagar, 0) as neto_pagar,                                  

                    -- 5. APORTES DEL EMPLEADOR (HMPP)
                    ISNULL(dp.aporte_essalud, 0) as essalud_9,       
                    ISNULL(dp.sctr, 0) as sctr_salud,          
                    ISNULL(dp.sctr_onp, 0) as sctr_pension,
                    ISNULL(dp.cts, 0) as cts,                        
                    (ISNULL(dp.aporte_essalud, 0) + ISNULL(dp.sctr, 0) + ISNULL(dp.sctr_onp, 0) + ISNULL(dp.cts, 0)) as total_aportes,

                    -- 6. EXTRAS (Glosas y Observaciones)
                    dp.glosa_bonos,
                    dp.glosa_otros,
                    dp.observaciones

                FROM detalle_planilla dp
                INNER JOIN personal p ON dp.id_personal = p.id_personal
                LEFT JOIN cargos c ON p.id_cargo = c.id_cargo
                WHERE dp.id_planilla = ?
                ORDER BY p.apellidos ASC
            """
            cursor.execute(query, (id_planilla,))
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error reporte general: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_planilla_header(self, id_planilla):
        """
        Obtiene la cabecera (datos generales: mes, año, tipo) 
        de la planilla para mostrar en el título del PDF.
        """
        # Reutilizamos la función que ya existe para no duplicar código
        return self.obtener_planilla_por_id(id_planilla)
    

    def marcar_planilla_como_impresa(self, id_planilla):
        """
        Actualiza el campo 'pdf_generado' a 1 (True) para indicar
        que la planilla oficial ya fue impresa y activar el modo lectura.
        """
        try:
            # Usamos self.db (o como tengas definida tu conexión en el repo)
            # Si usas get_db_write(), asegúrate de importarla o usar self.get_connection()
            from app.database import get_db_write 
            conn = get_db_write()
            cursor = conn.cursor()
            
            query = "UPDATE planillas SET pdf_generado = 1 WHERE id_planilla = ?"
            cursor.execute(query, (id_planilla,))
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            print(f"🔥 Error al marcar planilla como impresa: {e}")
            return False
        
    # --- MÉTODOS DE SEGURIDAD DINÁMICA ---

    def obtener_clave_dinamica(self):
        """Obtiene la clave actual desde la base de datos."""
        try:
            from app.database import get_db_read
            conn = get_db_read()
            cursor = conn.cursor()
            cursor.execute("SELECT TOP 1 clave_actual FROM configuracion_seguridad ORDER BY id DESC")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "ERROR-CLAVE"
        except Exception as e:
            print(f"Error obteniendo clave: {e}")
            return None

    def generar_nueva_clave_dinamica(self):
        """Genera una nueva clave aleatoria y la guarda."""
        import secrets
        import string
        try:
            # 1. Generar código de 6 caracteres (Mayúsculas y Números)
            alfabeto = string.ascii_uppercase + string.digits
            nueva_clave = ''.join(secrets.choice(alfabeto) for i in range(6))
            
            # Formato estilo: "A1B-2C3" para que sea fácil de leer
            clave_formateada = f"{nueva_clave[:3]}-{nueva_clave[3:]}"

            # 2. Guardar en BD
            from app.database import get_db_write
            conn = get_db_write()
            cursor = conn.cursor()
            
            # Opción A: Actualizar la misma fila siempre (más limpio)
            # Primero borramos todo y luego insertamos, o hacemos UPDATE si solo hay una fila.
            # Para este ejemplo, insertaremos una nueva para tener historial
            cursor.execute("INSERT INTO configuracion_seguridad (clave_actual) VALUES (?)", (clave_formateada,))
            
            conn.commit()
            conn.close()
            return clave_formateada
        except Exception as e:
            print(f"Error generando clave: {e}")
            return None
        

    def restaurar_planilla_logica(self, id_planilla):
        """Saca la planilla de la papelera y la devuelve al estado activo."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # Simplemente regresamos el flag a 0
            query = "UPDATE planillas SET eliminado = 0 WHERE id_planilla = ?"
            cursor.execute(query, (id_planilla,))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def obtener_planillas_eliminadas(self):
        """Trae planillas de la papelera calculando sus montos al vuelo."""
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            query = """
                SELECT 
                    p.id_planilla, p.mes, p.anio, p.tipo_planilla, 
                    p.fecha_eliminacion,
                    (SELECT SUM(ISNULL(neto_pagar, 0)) FROM detalle_planilla d WHERE d.id_planilla = p.id_planilla) as monto_total
                FROM planillas p 
                WHERE p.eliminado = 1
                ORDER BY p.fecha_eliminacion DESC
            """
            cursor.execute(query)
            # Mapeamos a diccionario para que Jinja lo lea fácil
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def eliminar_planilla_permanente(self, id_planilla):
        """Borra definitivamente una planilla y sus detalles de la base de datos."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # 1. Borramos los detalles de los trabajadores primero
            cursor.execute("DELETE FROM detalle_planilla WHERE id_planilla = ?", (id_planilla,))
            
            # 2. Borramos la cabecera de la planilla
            cursor.execute("DELETE FROM planillas WHERE id_planilla = ? AND eliminado = 1", (id_planilla,))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"🔥 Error en eliminación permanente: {e}")
            return False
        finally:
            conn.close()

    def vaciar_papelera_planillas(self):
        """Borra permanentemente todas las planillas que están en la papelera."""
        conn = get_db_write()
        cursor = conn.cursor()
        try:
            # Borramos detalles de todas las planillas marcadas como eliminadas
            cursor.execute("""
                DELETE FROM detalle_planilla 
                WHERE id_planilla IN (SELECT id_planilla FROM planillas WHERE eliminado = 1)
            """)
            
            # Borramos las cabeceras
            cursor.execute("DELETE FROM planillas WHERE eliminado = 1")
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()


    def obtener_resumen_pagos_anual(self, id_personal, anio):
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            # ✅ CORRECCIÓN: Se cambió 'faltas_tardanza' por 'faltas_tardanzas' (Plural)
            query = """
                SELECT 
                    p.mes,
                    ISNULL(dp.dias_laborados, 30) as d_lab, ISNULL(dp.dias_falta, 0) as d_fal,
                    ISNULL(dp.sueldo_basico, 0) as basica, ISNULL(dp.reintegros, 0) as reintegro, 
                    ISNULL(dp.bonificaciones, 0) as bonif, ISNULL(dp.asignacion_familiar, 0) as asig_fam,
                    ISNULL(dp.total_ingresos, 0) as ing_bruto,
                    ISNULL(dp.monto_pension, 0) as s_pens, ISNULL(dp.renta_4ta_5ta, 0) as renta,
                    ISNULL(dp.judiciales, 0) as judic, 
                    ISNULL(dp.faltas_tardanzas, 0) as tardanza, -- <--- NOMBRE CORREGIDO
                    ISNULL(dp.otros_descuentos, 0) + ISNULL(dp.essalud_vida, 0) as otros_dscto,
                    ISNULL(dp.total_descuentos, 0) as tot_dscto, ISNULL(dp.neto_pagar, 0) as neto,
                    ISNULL(dp.rps, 0) as rps, ISNULL(dp.sctr, 0) as sctr, ISNULL(dp.cts, 0) as cts,
                    ISNULL(dp.aporte_essalud, 0) as essalud_9,
                    dp.observaciones,
                    0 as medic, 0 as vacac, 0 as permis, 0 as susp,
                    CASE WHEN p.mes = 7 THEN ISNULL(dp.bonificaciones, 0) ELSE 0 END as f_patrias,
                    CASE WHEN p.mes = 12 THEN ISNULL(dp.bonificaciones, 0) ELSE 0 END as navidad,
                    CASE WHEN p.mes IN (1, 2) THEN ISNULL(dp.reintegros, 0) ELSE 0 END as escolar
                FROM detalle_planilla dp
                INNER JOIN planillas p ON dp.id_planilla = p.id_planilla
                WHERE dp.id_personal = ? AND p.anio = ? AND p.eliminado = 0
                ORDER BY p.mes ASC
            """
            cursor.execute(query, (id_personal, anio))
            columns = [column[0] for column in cursor.description]
            pagos_db = []
            
            from decimal import Decimal
            
            for row in cursor.fetchall():
                pago = dict(zip(columns, row))
                # Normalización de Decimal a Float para evitar errores de suma en el HTML
                for key, value in pago.items():
                    if isinstance(value, Decimal):
                        pago[key] = float(value)
                pagos_db.append(pago)
            
            # Asegurar los 12 meses exactos en la rejilla del PDF (HMPP Standard)
            meses_completos = []
            for m in range(1, 13):
                pago_mes = next((p for p in pagos_db if p['mes'] == m), None)
                if not pago_mes:
                    pago_mes = {col: 0.0 for col in columns if col not in ['observaciones', 'mes']}
                    pago_mes['mes'] = m
                    pago_mes['observaciones'] = ""
                meses_completos.append(pago_mes)
                
            return meses_completos
        except Exception as e:
            print(f"❌ Error en query anual: {e}")
            return []
        finally:
            conn.close()

    # ... (tu código anterior hasta obtener_resumen_pagos_anual) ...
    # PEGA ESTO JUSTO DESPUÉS DE obtener_resumen_pagos_anual

    def obtener_datos_personales_pdf(self, id_personal, anio):
        """
        Obtiene los datos reales y actualizados del trabajador para el encabezado del PDF,
        buscando en la última planilla del año solicitado.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT TOP 1
                    p.apellidos, 
                    p.nombres, 
                    p.dni, 
                    CONVERT(VARCHAR, p.fecha_ingreso, 103) as fecha_ingreso, -- Formato DD/MM/AAAA
                    dp.sistema_pensionario,
                    tc.nombre_tipo AS regimen_laboral
                FROM personal p
                LEFT JOIN detalle_planilla dp ON p.id_personal = dp.id_personal
                LEFT JOIN planillas pl ON dp.id_planilla = pl.id_planilla
                LEFT JOIN tipos_contrato tc ON dp.id_tipo_contrato = tc.id_tipo_contrato
                WHERE p.id_personal = ? AND pl.anio = ? AND pl.eliminado = 0
                ORDER BY pl.mes DESC;
            """
            cursor.execute(sql, (id_personal, anio))
            row = cursor.fetchone()
            
            if row:
                return {
                    'apellidos': row.apellidos,
                    'nombres': row.nombres,
                    'dni': row.dni,
                    'fecha_ingreso': row.fecha_ingreso,
                    'sistema_pensionario': row.sistema_pensionario or 'NO REGISTRADO',
                    'regimen_laboral': row.regimen_laboral or 'NO REGISTRADO'
                }
            
            # Fallback en caso de que no tenga planillas ese año, traemos sus datos básicos
            cursor.execute("SELECT apellidos, nombres, dni, CONVERT(VARCHAR, fecha_ingreso, 103) as fecha_ingreso FROM personal WHERE id_personal = ?", (id_personal,))
            row_basico = cursor.fetchone()
            if row_basico:
                 return {
                    'apellidos': row_basico.apellidos,
                    'nombres': row_basico.nombres,
                    'dni': row_basico.dni,
                    'fecha_ingreso': row_basico.fecha_ingreso,
                    'sistema_pensionario': 'S/D',
                    'regimen_laboral': 'S/D'
                }
            return None
            
        except Exception as e:
            print(f"❌ Error en obtener_datos_personales_pdf: {e}")
            return None
        finally:
            cursor.close()
            #conn.close()

    def obtener_cargos_anio(self, id_personal, anio):
        """
        Agrupa los cargos que tuvo el trabajador en el año especificado, 
        indicando los meses de inicio y fin para la tabla derecha del PDF.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT 
                    dp.cargo_actual,
                    MIN(pl.mes) AS mes_inicio,
                    MAX(pl.mes) AS mes_fin
                FROM detalle_planilla dp
                INNER JOIN planillas pl ON dp.id_planilla = pl.id_planilla
                WHERE dp.id_personal = ? AND pl.anio = ? AND pl.eliminado = 0
                GROUP BY dp.cargo_actual
                ORDER BY mes_inicio ASC;
            """
            cursor.execute(sql, (id_personal, anio))
            filas = cursor.fetchall()
            
            nombres_meses = ['', 'Ene.', 'Feb.', 'Mar.', 'Abr.', 'May.', 'Jun.', 'Jul.', 'Ago.', 'Set.', 'Oct.', 'Nov.', 'Dic.']
            
            lista_cargos = []
            for fila in filas:
                mes_ini_str = nombres_meses[fila.mes_inicio]
                mes_fin_str = nombres_meses[fila.mes_fin]
                
                # Si inicio y fin son el mismo mes, mostramos solo un mes
                if fila.mes_inicio == fila.mes_fin:
                     periodo = f"{mes_ini_str}"
                else:
                     periodo = f"{mes_ini_str} - {mes_fin_str}" 
                
                lista_cargos.append({
                    'cargo': fila.cargo_actual or 'SERVIDOR',
                    'periodo': periodo
                })
                
            return lista_cargos
        except Exception as e:
            print(f"❌ Error en obtener_cargos_anio: {e}")
            return []
        finally:
            cursor.close()
            #conn.close()

    def obtener_catalogo_conceptos(self):
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            sql = "SELECT id_concepto, tipo, nombre_concepto FROM catalogo_conceptos WHERE activo = 1 ORDER BY tipo, nombre_concepto"
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            conceptos = [dict(zip(columns, row)) for row in cursor.fetchall()]

            ingresos = [c for c in conceptos if c['tipo'] == 'INGRESO']
            descuentos = [c for c in conceptos if c['tipo'] == 'DESCUENTO']
            # 🔥 NUEVO: Enviar la lista de aguinaldos al HTML
            aguinaldos = [c for c in conceptos if c['tipo'] == 'AGUINALDO']

            return {'ingresos': ingresos, 'descuentos': descuentos, 'aguinaldos': aguinaldos}
        except Exception as e:
            print(f"❌ Error en obtener_catalogo_conceptos: {e}")
            return {'ingresos': [], 'descuentos': [], 'aguinaldos': []}
        finally:
            cursor.close()

    def obtener_conceptos_trabajador(self, id_detalle):
        conn = get_db_read()
        cursor = conn.cursor()
        try:
            sql = """
                SELECT dt.id_movimiento, dt.id_concepto, c.tipo, c.nombre_concepto, dt.monto
                FROM detalle_conceptos_trabajador dt
                INNER JOIN catalogo_conceptos c ON dt.id_concepto = c.id_concepto
                WHERE dt.id_detalle = ?
            """
            cursor.execute(sql, (id_detalle,))
            columns = [col[0] for col in cursor.description]
            movimientos = [dict(zip(columns, row)) for row in cursor.fetchall()]

            ingresos = [m for m in movimientos if m['tipo'] == 'INGRESO']
            descuentos = [m for m in movimientos if m['tipo'] == 'DESCUENTO']
            # 🔥 NUEVO: Recuperar aguinaldos guardados
            aguinaldos = [m for m in movimientos if m['tipo'] == 'AGUINALDO']

            return {'ingresos': ingresos, 'descuentos': descuentos, 'aguinaldos': aguinaldos}
        except Exception as e:
            print(f"❌ Error en obtener_conceptos_trabajador: {e}")
            return {'ingresos': [], 'descuentos': [], 'aguinaldos': []}
        finally:
            cursor.close()