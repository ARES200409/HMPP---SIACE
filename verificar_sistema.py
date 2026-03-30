import sys
import os
import importlib.util
import pyodbc
from dotenv import load_dotenv

# Cargamos el archivo .env
load_dotenv()

def check_python():
    print(f"[+] Versión de Python: {sys.version.split()[0]}")
    return True

def check_dependencies():
    dependencies = {
        'flask': 'flask',
        'pyodbc': 'pyodbc',
        'weasyprint': 'weasyprint',
        'flask_sqlalchemy': 'flask_sqlalchemy',
        'python-dotenv': 'dotenv',
        'openpyxl': 'openpyxl'
    }
    missing = []
    print("[+] Verificando librerías...")
    for pkg, module in dependencies.items():
        spec = importlib.util.find_spec(module)
        if spec is None:
            missing.append(pkg)
    if missing:
        print(f"    [❌] Faltan: {', '.join(missing)}")
        return False
    print("    [✅] Todas las dependencias están instaladas.")
    return True

def check_env_file():
    if os.path.exists('.env'):
        print("[✅] Archivo .env detectado.")
        return True
    print("[❌] No se encuentra el archivo .env.")
    return False

def check_database():
    # Jalamos los datos tal cual están en tu .env
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_DATABASE')
    user = os.getenv('DB_USERNAME_WRITE') or os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD_WRITE') or os.getenv('DB_PASS')
    driver = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')

    print(f"[+] Intentando conectar a: {server} | BD: {database} (Usuario: {user})")
    
    try:
        # Intentamos conexión usando el usuario SA y password del .env
        conn_str = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={user};PWD={password};'
        conn = pyodbc.connect(conn_str, timeout=3)
        conn.close()
        print("    [✅] Conexión a la Base de Datos exitosa.")
        return True
    except Exception as e:
        print(f"    [❌] Error: No se pudo conectar.")
        print(f"    [!] Detalle: {str(e).split('] ')[-1]}")
        return False

def check_gtk():
    print("[+] Verificando motor de reportes (GTK3)...")
    path = os.environ.get('PATH', '').upper()
    if 'GTK' in path:
        print("    [✅] GTK detectado en el PATH.")
        return True
    print("    [⚠️] ADVERTENCIA: No se detectó GTK en el PATH.")
    return False

if __name__ == "__main__":
    print("\n" + "="*52)
    print("      DIAGNÓSTICO DE SISTEMA - SIACE HMPP")
    print("="*52 + "\n")
    
    results = [
        check_python(),
        check_dependencies(),
        check_env_file(),
        check_database(),
        check_gtk()
    ]
    
    print("\n" + "="*52)
    if all(results):
        print("   🚀 [ESTADO]: SISTEMA LISTO PARA PRODUCCIÓN")
    else:
        print("   ⚠️ [ESTADO]: REVISAR ERRORES ANTES DE INICIAR")
    print("="*52 + "\n")