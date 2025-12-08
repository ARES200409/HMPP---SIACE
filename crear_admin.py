"""
Script para crear el primer usuario administrador
Sistema de Legajo Digital - DIRESA Pasco
"""

import os
import sys
import pyodbc
from getpass import getpass
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

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

def print_info(text):
    """Imprime un mensaje informativo"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def get_db_connection():
    """Obtiene una conexión a la base de datos"""
    try:
        conn_str = (
            f"DRIVER={{{os.getenv('DB_DRIVER')}}};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_DATABASE')};"
            f"UID={os.getenv('DB_USERNAME_SYSTEMS_ADMIN')};"
            f"PWD={os.getenv('DB_PASSWORD_SYSTEMS_ADMIN')};"
        )
        return pyodbc.connect(conn_str)
    except Exception as e:
        print_error(f"Error al conectar a la base de datos: {e}")
        print_info("Verifique que el archivo .env esté configurado correctamente")
        return None

def validar_email(email):
    """Valida el formato del email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validar_dni(dni):
    """Valida que el DNI tenga 8 dígitos"""
    return dni.isdigit() and len(dni) == 8

def crear_usuario_admin():
    """Crea el primer usuario administrador del sistema"""
    print_header("CREAR USUARIO ADMINISTRADOR")
    
    print(f"{Colors.BOLD}Este script creará el primer usuario administrador del sistema.{Colors.ENDC}\n")
    
    # Verificar conexión
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # Verificar si ya existen usuarios
        cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE rol = 'Sistemas'")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print_info(f"Ya existen {count} usuario(s) con rol 'Sistemas' en el sistema.")
            respuesta = input("¿Desea crear otro usuario administrador? (s/n): ").lower()
            if respuesta != 's':
                print_info("Operación cancelada")
                return False
        
        # Recopilar datos del personal
        print(f"\n{Colors.BOLD}Datos del Personal:{Colors.ENDC}")
        
        while True:
            dni = input("DNI (8 dígitos): ").strip()
            if validar_dni(dni):
                # Verificar si el DNI ya existe
                cursor.execute("SELECT id_personal FROM Personal WHERE dni = ?", dni)
                if cursor.fetchone():
                    print_error("Este DNI ya está registrado en el sistema")
                    continue
                break
            else:
                print_error("DNI inválido. Debe tener 8 dígitos numéricos")
        
        nombres = input("Nombres: ").strip()
        apellido_paterno = input("Apellido Paterno: ").strip()
        apellido_materno = input("Apellido Materno: ").strip()
        
        while True:
            email = input("Email: ").strip()
            if validar_email(email):
                break
            else:
                print_error("Email inválido")
        
        telefono = input("Teléfono (opcional): ").strip() or None
        cargo = input("Cargo [Administrador de Sistemas]: ").strip() or "Administrador de Sistemas"
        area = input("Área [Sistemas]: ").strip() or "Sistemas"
        
        # Insertar en tabla Personal
        print_info("Creando registro de personal...")
        cursor.execute("""
            INSERT INTO Personal (dni, nombres, apellido_paterno, apellido_materno, 
                                 email, telefono, cargo, area, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Activo')
        """, dni, nombres, apellido_paterno, apellido_materno, email, telefono, cargo, area)
        
        # Obtener el ID del personal recién creado
        cursor.execute("SELECT @@IDENTITY")
        id_personal = cursor.fetchone()[0]
        print_success(f"Registro de personal creado (ID: {id_personal})")
        
        # Recopilar datos del usuario
        print(f"\n{Colors.BOLD}Datos del Usuario:{Colors.ENDC}")
        
        while True:
            username = input("Nombre de usuario: ").strip()
            if len(username) >= 4:
                # Verificar si el username ya existe
                cursor.execute("SELECT id_usuario FROM Usuarios WHERE username = ?", username)
                if cursor.fetchone():
                    print_error("Este nombre de usuario ya existe")
                    continue
                break
            else:
                print_error("El nombre de usuario debe tener al menos 4 caracteres")
        
        while True:
            password = getpass("Contraseña (mínimo 8 caracteres): ")
            if len(password) >= 8:
                password_confirm = getpass("Confirmar contraseña: ")
                if password == password_confirm:
                    break
                else:
                    print_error("Las contraseñas no coinciden")
            else:
                print_error("La contraseña debe tener al menos 8 caracteres")
        
        # Generar hash de la contraseña
        password_hash = generate_password_hash(password)
        
        # Insertar en tabla Usuarios
        print_info("Creando usuario...")
        cursor.execute("""
            INSERT INTO Usuarios (username, email, password_hash, rol, activo, id_personal)
            VALUES (?, ?, ?, 'Sistemas', 1, ?)
        """, username, email, password_hash, id_personal)
        
        # Confirmar cambios
        conn.commit()
        
        print_success("Usuario administrador creado exitosamente")
        
        # Mostrar resumen
        print(f"\n{Colors.BOLD}Resumen:{Colors.ENDC}")
        print(f"Nombre completo: {nombres} {apellido_paterno} {apellido_materno}")
        print(f"DNI: {dni}")
        print(f"Email: {email}")
        print(f"Usuario: {username}")
        print(f"Rol: Sistemas (Administrador)")
        print(f"\n{Colors.OKGREEN}Ya puede iniciar sesión en el sistema con estas credenciales.{Colors.ENDC}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print_error(f"Error al crear el usuario: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def main():
    """Función principal"""
    try:
        # Verificar que exista el archivo .env
        if not os.path.exists('.env'):
            print_error("No se encontró el archivo .env")
            print_info("Ejecute primero el instalador: python installer.py")
            return
        
        crear_usuario_admin()
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Operación cancelada por el usuario{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
