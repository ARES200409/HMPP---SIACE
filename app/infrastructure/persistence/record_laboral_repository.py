from app.domain.models.record_laboral import RecordLaboral

class RecordLaboralRepository:
    def __init__(self, db_connection):
        self.db = db_connection

    def guardar(self, record):
        cursor = self.db.cursor()
        query = """
            INSERT INTO dbo.record_laboral 
            (id_personal, anio, mes, monto_basica, monto_reunif, monto_tph, 
             monto_familiar, monto_movilidad, desc_onp, desc_tardanzas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        valores = (
            record.id_personal, record.anio, record.mes,
            record.basica, record.reunif, record.tph,
            record.familiar, record.movilidad, record.onp, record.tardanzas
        )
        cursor.execute(query, valores)
        self.db.commit() # Vital para guardar en SQL Server
        cursor.close()