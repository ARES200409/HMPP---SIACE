"""
Script de Verificación del Sistema
Sistema de Legajo Digital - DIRESA Pasco

Este script verifica que todos los componentes del sistema estén correctamente instalados.
"""

import os
import sys
import importlib.util

class Colors:
    """Colores para la consola"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Imprime un encabezado con estilo"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    """Imprime un mensaje de éxito"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    """Imprime un mensaje de error"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_warning(text):
    """Imprime un mensaje de advertencia"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_info(text):
    """Imprime un mensaje informativo"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def check_python_version():
    """Verifica la versión de Python"""
    print(f"{Colors.BOLD}Verificando versión de Python...{Colors.ENDC}")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} (Requerido: 3.8+)")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor}.{version.micro} (Requerido: 3.8+)")
        return False

def check_package(package_name, display_name=None):
    """Verifica si un paquete de Python está instalado"""
    if display_name is None:
        display_name = package_name
    
    spec = importlib.util.find_spec(package_name)
    if spec is not None:
        print_success(f"{display_name} instalado")
        return True
    else:
        print_error(f"{display_name} NO instalado")
        return False

def check_dependencies():
    """Verifica las dependencias principales"""
    print(f"\n{Colors.BOLD}Verificando dependencias de Python...{Colors.ENDC}")
    
    packages = [
        ('flask', 'Flask'),
        ('flask_login', 'Flask-Login'),
        ('flask_wtf', 'Flask-WTF'),
        ('flask_mail', 'Flask-Mail'),
        ('flask_talisman', 'Flask-Talisman'),
        ('flask_limiter', 'Flask-Limiter'),
        ('pyodbc', 'pyodbc'),
        ('dotenv', 'python-dotenv'),
        ('werkzeug', 'Werkzeug'),
    ]
    
    all_installed = True
    for package, display in packages:
        if not check_package(package, display):
            all_installed = False
    
    return all_installed

def check_env_file():
    """Verifica la existencia y contenido del archivo .env"""
    print(f"\n{Colors.BOLD}Verificando archivo .env...{Colors.ENDC}")
    
    if not os.path.exists('.env'):
        print_error("Archivo .env NO encontrado")
        print_info("Ejecute 'python installer.py' para crear el archivo .env")
        return False
    
    print_success("Archivo .env encontrado")
    
    # Verificar variables requeridas
    required_vars = [
        'SECRET_KEY',
        'DB_DRIVER',
        'DB_SERVER',
        'DB_DATABASE',
        'DB_USERNAME_WRITE',
        'DB_PASSWORD_WRITE',
        'DB_USERNAME_SYSTEMS_ADMIN',
        'DB_PASSWORD_SYSTEMS_ADMIN'
    ]
    
    from dotenv import dotenv_values
    config = dotenv_values('.env')
    
    missing_vars = []
    for var in required_vars:
        if var not in config or not config[var]:
            missing_vars.append(var)
    
    if missing_vars:
        print_warning(f"Variables faltantes o vacías: {', '.join(missing_vars)}")
        return False
    else:
        print_success("Todas las variables requeridas están configuradas")
        return True

def check_database_connection():
    """Verifica la conexión a la base de datos"""
    print(f"\n{Colors.BOLD}Verificando conexión a la base de datos...{Colors.ENDC}")
    
    try:
        import pyodbc
        from dotenv import load_dotenv
        load_dotenv()
        
        conn_str = (
            f"DRIVER={{{os.getenv('DB_DRIVER')}}};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_DATABASE')};"
            f"UID={os.getenv('DB_USERNAME_WRITE')};"
            f"PWD={os.getenv('DB_PASSWORD_WRITE')};"
        )
        
        conn = pyodbc.connect(conn_str, timeout=5)
        cursor = conn.cursor()
        
        # Verificar que las tablas existan
        tables = ['Personal', 'Usuarios', 'Documentos', 'Auditoria', 'Solicitudes', 'Backups']
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = [table for table in tables if table not in existing_tables]
        
        if missing_tables:
            print_warning(f"Tablas faltantes: {', '.join(missing_tables)}")
            print_info("Ejecute 'python installer.py' para crear las tablas")
            conn.close()
            return False
        
        print_success(f"Conexión exitosa a {os.getenv('DB_DATABASE')}")
        print_success(f"Todas las tablas principales existen ({len(tables)} tablas)")
        
        # Verificar si hay usuarios
        cursor.execute("SELECT COUNT(*) FROM Usuarios")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            print_warning("No hay usuarios en el sistema")
            print_info("Ejecute 'python crear_admin.py' para crear el primer usuario")
        else:
            print_success(f"Sistema tiene {user_count} usuario(s) registrado(s)")
        
        conn.close()
        return True
        
    except ImportError:
        print_error("pyodbc no está instalado")
        return False
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        print_info("Verifique las credenciales en el archivo .env")
        return False

def check_directory_structure():
    """Verifica la estructura de directorios"""
    print(f"\n{Colors.BOLD}Verificando estructura de directorios...{Colors.ENDC}")
    
    required_dirs = [
        'app',
        'app/application',
        'app/database',
        'app/domain',
        'app/infrastructure',
        'app/presentation',
        'logs',
        'temp_pdfs',
        'temp_uploads'
    ]
    
    all_exist = True
    for directory in required_dirs:
        if os.path.exists(directory):
            print_success(f"Directorio '{directory}' existe")
        else:
            print_warning(f"Directorio '{directory}' NO existe")
            all_exist = False
    
    return all_exist

def check_critical_files():
    """Verifica archivos críticos del sistema"""
    print(f"\n{Colors.BOLD}Verificando archivos críticos...{Colors.ENDC}")
    
    critical_files = [
        'run.py',
        'app/__init__.py',
        'app/config.py',
        'app/database/connector.py',
        'requirements.txt',
        '.env.example'
    ]
    
    all_exist = True
    for file in critical_files:
        if os.path.exists(file):
            print_success(f"Archivo '{file}' existe")
        else:
            print_error(f"Archivo '{file}' NO existe")
            all_exist = False
    
    return all_exist

def main():
    """Función principal"""
    print_header("VERIFICACIÓN DEL SISTEMA")
    print(f"{Colors.BOLD}Sistema de Legajo Digital - DIRESA Pasco{Colors.ENDC}\n")
    
    results = {
        'Python': check_python_version(),
        'Dependencias': check_dependencies(),
        'Archivo .env': check_env_file(),
        'Estructura de directorios': check_directory_structure(),
        'Archivos críticos': check_critical_files(),
        'Base de datos': check_database_connection()
    }
    
    # Resumen
    print_header("RESUMEN DE VERIFICACIÓN")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        if result:
            print_success(f"{check}: OK")
        else:
            print_error(f"{check}: FALLO")
    
    print(f"\n{Colors.BOLD}Resultado: {passed}/{total} verificaciones pasadas{Colors.ENDC}")
    
    if passed == total:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ El sistema está correctamente instalado y listo para usar{Colors.ENDC}")
        print(f"\n{Colors.BOLD}Para iniciar la aplicación, ejecute:{Colors.ENDC}")
        print(f"  python run.py")
        return True
    else:
        print(f"\n{Colors.WARNING}{Colors.BOLD}⚠ El sistema tiene problemas de configuración{Colors.ENDC}")
        print(f"\n{Colors.BOLD}Acciones recomendadas:{Colors.ENDC}")
        
        if not results['Dependencias']:
            print("  1. Instale las dependencias: pip install -r requirements.txt")
        
        if not results['Archivo .env']:
            print("  2. Configure el sistema: python installer.py")
        
        if not results['Base de datos']:
            print("  3. Verifique la conexión a SQL Server")
            print("  4. Ejecute el instalador: python installer.py")
        
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Verificación cancelada por el usuario{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        sys.exit(1)
