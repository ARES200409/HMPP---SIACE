import os
from werkzeug.utils import secure_filename
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class SolicitudService:
    def __init__(self, solicitud_repository):
        self.solicitud_repo = solicitud_repository

    def get_all_pending(self):
        return self.solicitud_repo.get_pending_requests()

    def process_request(self, request_id, action):
        return self.solicitud_repo.process_request(request_id, action)

    def registrar_solicitud_cambio(self, id_usuario, id_documento, motivo, archivo):
        """
        Guarda el archivo y registra la solicitud reutilizando las columnas existentes.
        """
        try:
            # 1. Validar y Guardar archivo físico
            if not archivo:
                raise ValueError("El archivo es requerido")

            filename = secure_filename(archivo.filename)
            upload_folder = os.path.join(current_app.root_path, 'presentation/static/uploads/temp_requests')
            os.makedirs(upload_folder, exist_ok=True)
            
            ruta_guardado = os.path.join(upload_folder, filename)
            archivo.save(ruta_guardado)
            
            # Ruta relativa para guardar en BD
            ruta_relativa = f"uploads/temp_requests/{filename}"

            # 2. Obtener id_personal asociado al documento (Requerido por la tabla)
            # Usamos el repositorio para hacer una consulta directa ya que el SP no devuelve id_personal
            id_personal = self.solicitud_repo.obtener_id_personal_por_documento(id_documento)
            
            if not id_personal:
                raise ValueError(f"No se encontró el personal asociado al documento {id_documento}")

            # 3. Mapeo de datos para ajustarse a la tabla existente sin crear columnas nuevas:
            # campo_modificado -> Guardamos el ID del documento
            # valor_anterior   -> Guardamos el MOTIVO
            # valor_nuevo      -> Guardamos la RUTA DEL ARCHIVO
            data = {
                'id_personal': id_personal,
                'id_usuario_solicitante': id_usuario,
                'campo_modificado': str(id_documento), # Guardamos ID Documento aquí
                'valor_anterior': motivo,              # Guardamos Motivo aquí
                'valor_nuevo': ruta_relativa           # Guardamos Ruta aquí
            }
            
            return self.solicitud_repo.crear_solicitud(data)

        except Exception as e:
            logger.error(f"Error en servicio registrar_solicitud_cambio: {e}")
            raise

    def registrar_solicitud_documento(self, id_usuario, id_personal, id_documento, motivo, archivo):
        """
        Guarda el archivo en una carpeta temporal y llama al SP de base de datos.
        """
        import os
        from werkzeug.utils import secure_filename
        from flask import current_app

        # 1. Guardar archivo físico
        filename = secure_filename(archivo.filename)
        # Definir ruta temporal (asegúrate de crear esta carpeta)
        upload_folder = os.path.join(current_app.root_path, 'presentation', 'static', 'uploads', 'temp_solicitudes')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Generar nombre único para evitar colisiones
        nombre_unico = f"{id_documento}_{id_usuario}_{filename}"
        ruta_fisica = os.path.join(upload_folder, nombre_unico)
        ruta_relativa = f"uploads/temp_solicitudes/{nombre_unico}" # Ruta para guardar en BD
        
        archivo.save(ruta_fisica)

        # 2. Llamar al repositorio para ejecutar el SP
        # Mapeamos los datos a los parámetros del SP sp_solicitar_modificacion_personal
        data = {
            'id_personal': id_personal,
            'id_usuario_solicitante': id_usuario,
            'campo_modificado': f'Documento ID: {id_documento}', # Referencia al documento
            'valor_anterior': motivo,          # Usamos este campo para el MOTIVO
            'valor_nuevo': ruta_relativa       # Usamos este campo para la RUTA DEL ARCHIVO
        }
        
        return self.solicitud_repo.crear_solicitud_modificacion(data)
    



    def registrar_solicitud_cancelacion(self, id_usuario, datos_cancelar, motivo):
        """
        Registra una solicitud de cancelación de datos personales.
        """
        try:
            # 1. Obtener id_personal (asumiendo que el usuario tiene un personal_id)
            id_personal = self.solicitud_repo.obtener_id_personal_por_usuario(id_usuario)
            
            # 2. Mapeo para la tabla de solicitudes
            # Usamos 'campo_modificado' para indicar qué datos se quieren borrar
            data = {
                'id_personal': id_personal,
                'id_usuario_solicitante': id_usuario,
                'campo_modificado': f"CANCELACIÓN: {', '.join(datos_cancelar)}",
                'valor_anterior': 'Dato actual en sistema',
                'valor_nuevo': f"MOTIVO: {motivo}" 
            }
            
            # 3. Guardar en la tabla general de solicitudes
            return self.solicitud_repo.crear_solicitud_modificacion(data)

        except Exception as e:
            logger.error(f"Error en registrar_solicitud_cancelacion: {e}")
            raise