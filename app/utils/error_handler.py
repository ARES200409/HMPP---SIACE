import traceback
import sys
import os
from flask import request
from flask_login import current_user
from app.infrastructure.persistence.error_repository import ErrorRepository

error_repo = ErrorRepository()

def registrar_error_automatico(e):
    """Extrae el ADN del error para la HMPP."""
    exc_type, exc_value, exc_traceback = sys.exc_info()
    # Obtenemos la última línea donde realmente explotó el código
    tb = traceback.extract_tb(exc_traceback)[-1] 
    
    detalles = {
        'modulo': request.path,
        'tipo': exc_type.__name__,
        'mensaje': str(e),
        'archivo': os.path.basename(tb.filename),
        'linea': tb.lineno,
        'stacktrace': traceback.format_exc(),
        'usuario': current_user.id if current_user.is_authenticated else None
    }
    
    error_repo.save_error(detalles)
    return detalles