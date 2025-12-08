import os
import sys
import webbrowser
from threading import Timer

# Agregar el directorio actual al path para asegurar que los módulos se encuentren
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
