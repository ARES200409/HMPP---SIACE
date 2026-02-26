import os
import re
from werkzeug.utils import secure_filename
from flask import current_app
import logging
from app.database import get_db_write 

logger = logging.getLogger(__name__)

class SolicitudService:
    def __init__(self, solicitud_repository):
        self.solicitud_repo = solicitud_repository

    def get_all_pending(self):
        return self.solicitud_repo.get_pending_requests()

    def process_request(self, solicitud_id, accion):
        """
        Procesa la solicitud de CAMBIO DE DOCUMENTO.
        Lee el archivo físico y actualiza la columna BLOB 'archivo'.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        
        try:
            # 1. Configuración de Estados (Según tu Constraint SQL)
            ESTADO_APROBADO = 'aprobada'
            ESTADO_RECHAZADO = 'rechazada'
            
            accion_norm = accion.lower()
            nuevo_estado = ESTADO_APROBADO if accion_norm == 'aprobar' else ESTADO_RECHAZADO

            # -------------------------------------------------------------
            # LÓGICA DE APROBACIÓN (ACTUALIZACIÓN REAL DEL ARCHIVO)
            # -------------------------------------------------------------
            if accion_norm == 'aprobar':
                query_info = """
                    SELECT campo_modificado, valor_nuevo
                    FROM solicitudes_modificacion 
                    WHERE id_solicitud = ?
                """
                cursor.execute(query_info, (solicitud_id,))
                row = cursor.fetchone()

                if row:
                    texto_campo = row[0]  # Ej: "Documento ID: 1040"
                    ruta_relativa = row[1] # Ej: "uploads/temp_solicitudes/..."

                    # A. Extraer ID del documento
                    match = re.search(r'(\d+)', str(texto_campo))
                    
                    if match and ruta_relativa:
                        id_doc_original = int(match.group(1))
                        
                        # B. Construir ruta física para LEER el archivo nuevo
                        # Asumimos que la ruta guardada empieza con "uploads/..."
                        ruta_fisica = os.path.join(current_app.root_path, 'presentation/static', ruta_relativa)
                        
                        try:
                            # C. LEER EL ARCHIVO EN BINARIO (CRÍTICO)
                            # Esto convierte el archivo en bytes para guardarlo en la columna 'archivo'
                            with open(ruta_fisica, 'rb') as f:
                                file_data = f.read()
                                tamanio = len(file_data)
                            
                            # Obtenemos solo el nombre limpio del archivo (sin la ruta fea)
                            nombre_archivo_limpio = os.path.basename(ruta_relativa)

                            # D. ACTUALIZAR LA BASE DE DATOS (BLOB)
                            # Actualizamos 'archivo' (contenido), 'nombre_archivo' (texto), y 'tamanio_bytes'
                            query_update_doc = """
                                UPDATE documentos
                                SET 
                                    archivo = ?,            -- ¡AQUÍ VA LA FOTO NUEVA!
                                    nombre_archivo = ?,     -- Nombre limpio
                                    tamanio_bytes = ?,      -- Tamaño real
                                    fecha_subida = GETDATE(),
                                    descripcion = 'Documento Actualizado por Solicitud'
                                WHERE id_documento = ?
                            """
                            # Pasamos los datos binarios (file_data) al SQL
                            cursor.execute(query_update_doc, (file_data, nombre_archivo_limpio, tamanio, id_doc_original))
                            logger.info(f"Documento {id_doc_original} actualizado con éxito (Bytes inyectados).")
                            
                        except FileNotFoundError:
                            logger.error(f"No se encontró el archivo físico en: {ruta_fisica}")
                            # Podrías decidir si cancelar o seguir, aquí solo logueamos el error.
                        except Exception as e:
                            logger.error(f"Error leyendo/guardando binario: {e}")

            # -------------------------------------------------------------
            # 2. ACTUALIZAR ESTADO DE LA SOLICITUD
            # -------------------------------------------------------------
            query_estado = """
                UPDATE solicitudes_modificacion 
                SET estado = ?, 
                    fecha_revision = GETDATE() 
                WHERE id_solicitud = ?
            """
            cursor.execute(query_estado, (nuevo_estado, solicitud_id))
            
            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"Error CRÍTICO en process_request: {e}")
            return False
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # RESTO DE MÉTODOS (IGUAL QUE ANTES)
    # -------------------------------------------------------------------------
    def registrar_solicitud_cambio(self, id_usuario, id_documento, motivo, archivo):
        try:
            if not archivo: raise ValueError("Archivo requerido")
            filename = secure_filename(archivo.filename)
            
            # Guardamos en carpeta temporal
            upload_folder = os.path.join(current_app.root_path, 'presentation/static/uploads/temp_solicitudes')
            os.makedirs(upload_folder, exist_ok=True)
            
            nombre_unico = f"{id_documento}_{id_usuario}_{filename}"
            ruta_fisica = os.path.join(upload_folder, nombre_unico)
            # Guardamos ruta relativa para usarla luego
            ruta_relativa = f"uploads/temp_solicitudes/{nombre_unico}" 
            
            archivo.save(ruta_fisica)

            id_personal = self.solicitud_repo.obtener_id_personal_por_documento(id_documento)
            
            data = {
                'id_personal': id_personal if id_personal else 0,
                'id_usuario_solicitante': id_usuario,
                'campo_modificado': f"Documento ID: {id_documento}", 
                'valor_anterior': motivo,
                'valor_nuevo': ruta_relativa
            }
            
            if hasattr(self.solicitud_repo, 'crear_solicitud_modificacion'):
                return self.solicitud_repo.crear_solicitud_modificacion(data)
            else:
                return self.solicitud_repo.crear_solicitud(data)

        except Exception as e:
            logger.error(f"Error en registrar_solicitud_cambio: {e}")
            raise

    def registrar_solicitud_cancelacion(self, id_usuario, datos_cancelar, motivo):
        # (Sin cambios aquí)
        pass