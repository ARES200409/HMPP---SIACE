import os
from datetime import datetime
from flask_login import current_user
from flask import current_app
from dotenv import load_dotenv

load_dotenv()

class BackupService:
    """
    Servicio profesional de backups para la HMPP.
    Lógica escalable probada y validada para KB, MB y GB.
    """
    def __init__(self, backup_repository, app_config, audit_service):
        self.backup_repo = backup_repository
        self.config = app_config
        self.audit_service = audit_service
        self.db_name = os.getenv('DB_DATABASE') or os.getenv('DB_NAME')
        self.base_backup_dir = os.getenv('BACKUP_PATH') or "C:\\Backups_Escalafon"

    def _get_human_readable_size(self, file_path):
        """
        Calcula el peso real y escala la unidad automáticamente (KB, MB, GB).
        """
        if not os.path.exists(file_path):
            return "0 KB"
        
        # Obtenemos el tamaño real del archivo en el disco C:
        size = float(os.path.getsize(file_path))
        
        for unit in ['Bytes', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                # Formato: 11,15 MB o 1,50 GB
                return f"{size:,.2f} {unit}".replace(",", "X").replace(".", ",").replace("X", ".")
            size /= 1024.0
        return f"{size:,.2f} PB"

    def execute_full_backup(self):
        """
        Ejecuta el backup real y registra el tamaño escalable en la bitácora.
        """
        if not self.db_name or not os.getenv('DB_SERVER'):
            raise Exception("Variables de BD no configuradas en .env.")

        if not os.path.exists(self.base_backup_dir):
            os.makedirs(self.base_backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = os.path.join(self.base_backup_dir, f"Legajo_{timestamp}.bak")
        
        # 1. Ejecución física del backup en SQL Server
        self.backup_repo.run_db_backup(self.db_name, backup_filename)
        
        # 2. MEDICIÓN REAL: Volvemos a medir el archivo físico
        # (Ya no usamos test_bytes, usamos el archivo recién creado)
        real_size = self._get_human_readable_size(backup_filename)

        # 3. Registro final en la Bitácora
        try:
            user_id = current_user.id if current_user.is_authenticated else None
            self.audit_service.log(
                user_id, 'MANTENIMIENTO', 'BACKUP', 
                f'Backup exitoso: {os.path.basename(backup_filename)}',
                detalle_dict={
                    'archivo': backup_filename,
                    'tamano': real_size, # Guardará el peso real (ej: 11,15 MB)
                    'tipo': 'FULL'
                }
            )
            current_app.logger.info(f"Backup real completado: {real_size}")
        except Exception as e:
            current_app.logger.error(f"Error en auditoría: {e}")

        return True
    
    def get_backup_history(self):
        return self.backup_repo.get_backup_history()