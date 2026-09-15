import os
import sys
import webbrowser
from threading import Timer

# Agregar el directorio actual al path para asegurar que los módulos se encuentren
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# -----------------------------------------------------------------------
# CORRECCIÓN WEASYPRINT: Forzar uso de DLLs de MSYS2 (Pango >= 1.44)
# El GTK-Runtime instalado en el sistema tiene Pango 1.43 (demasiado viejo)
# y causa el error 'pango_context_set_round_glyph_positions not found'.
# Solución: poner MSYS2 ucrt64 PRIMERO en el PATH del proceso y registrar
# el directorio con os.add_dll_directory() antes de importar weasyprint.
# -----------------------------------------------------------------------
MSYS2_BIN = r'C:\msys64\ucrt64\bin'

if os.path.isdir(MSYS2_BIN):
    # 1. Registrar el directorio para la resolución de DLLs (Python 3.8+)
    os.add_dll_directory(MSYS2_BIN)

    # 2. Poner MSYS2 AL INICIO del PATH para que tome precedencia sobre GTK-Runtime
    current_path = os.environ.get('PATH', '')
    if MSYS2_BIN not in current_path:
        os.environ['PATH'] = MSYS2_BIN + os.pathsep + current_path

# 3. Indicar a WeasyPrint el directorio de DLLs
os.environ['WEASYPRINT_DLL_DIRECTORIES'] = MSYS2_BIN

from app import create_app

app = create_app()

def open_browser():
    """Abre el navegador predeterminado en la dirección local."""
    # Usamos localhost en lugar de 0.0.0.0 para el navegador
    webbrowser.open_new("http://127.0.0.1:5001")

if __name__ == '__main__':
    # Timer para abrir el navegador después de 1.5 segundos (dando tiempo a que Flask inicie)
    # IMPORTANTE: Solo abrir el navegador en el proceso principal, no en el reloader
    # Cuando debug=True, Flask crea dos procesos (padre y hijo con reloader)
    # Solo el proceso hijo tiene la variable WERKZEUG_RUN_MAIN definida
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        Timer(1.5, open_browser).start()
    
    # Ejecutar la aplicación
    # debug=True activa el reloader automático (útil en desarrollo)
    # debug=False es CRÍTICO para producción y para que PyInstaller funcione bien sin consola
    app.run(host='0.0.0.0', port=5001, debug=True)
