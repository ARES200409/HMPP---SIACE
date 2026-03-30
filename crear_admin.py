"""
Script Multi-Creador de Usuarios Principales (Todo en Uno)
SIACE - H. Municipalidad Provincial de Pasco 2026
"""

import os
import pyodbc
from getpass import getpass
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

class Colors:
    HEADER = '\033[95m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_error(text): print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def get_db_connection():
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
        print_error(f"Error de conexión: {e}")
        return None

def crear_usuario_admin():
    print_header("CREAR USUARIOS INSTITUCIONALES - SIACE HMPP")
    
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    
    try:
        # --- 1. SELECCIÓN DEL ROL EXACTO ---
        print(f"{Colors.BOLD}Seleccione el perfil institucional:{Colors.ENDC}")
        print("1. Sistemas              (ID Rol: 1)")
        print("2. RRHH                  (ID Rol: 2)")
        print("3. AdministradorLegajos  (ID Rol: 3)")
        
        while True:
            opcion = input("\nIngrese el número (1/2/3): ").strip()
            if opcion in ['1', '2', '3']:
                id_rol = int(opcion)
                # Asumimos que el ID de la unidad es el mismo que el rol para los jefes
                id_unidad = int(opcion) 
                break
            print_error("Opción inválida.")

        # --- 2. CREACIÓN EN TABLA: PERSONAL ---
        print(f"\n{Colors.BOLD}--- Datos del Trabajador (Tabla Personal) ---{Colors.ENDC}")
        dni = input("DNI (8 dígitos): ").strip()
        nombres = input("Nombres: ").strip().upper()
        apellidos = input("Apellidos (Paterno y Materno): ").strip().upper()
        sexo = input("Sexo (M/F): ").strip().upper()
        email = input("Email Institucional: ").strip().lower()
        
        # Guardamos en Personal y pedimos que nos devuelva el ID exacto
        cursor.execute("""
            INSERT INTO Personal (dni, nombres, apellidos, sexo, email, id_unidad, activo)
            OUTPUT INSERTED.id_personal
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, dni, nombres, apellidos, sexo, email, id_unidad)
        
        # Atrapamos el ID que la base de datos le asignó a este trabajador
        id_personal = int(cursor.fetchone()[0])
        
        # --- 3. CREACIÓN EN TABLA: USUARIOS ---
        print(f"\n{Colors.BOLD}--- Credenciales de Acceso (Tabla Usuarios) ---{Colors.ENDC}")
        username = input("Nombre de usuario (ej. admin_sistemas): ").strip().lower()
        
        while True:
            password = getpass("Contraseña (no se verá al escribir): ")
            if password == getpass("Confirme la contraseña: "): 
                break
            print_error("Las contraseñas no coinciden. Intente de nuevo.")

        # Encriptamos la clave para que Flask la acepte
        pass_hash = generate_password_hash(password)
        
        # Guardamos el usuario, pasándole el ID del trabajador que atrapamos antes
        cursor.execute("""
            INSERT INTO Usuarios (username, email, password_hash, id_rol, id_personal, activo)
            VALUES (?, ?, ?, ?, ?, 1)
        """, username, email, pass_hash, id_rol, id_personal)
        
        # Confirmamos los cambios en la BD
        conn.commit()
        print(f"\n{Colors.OKGREEN}✓ ¡Usuario '{username}' creado exitosamente! Ya puede iniciar sesión.{Colors.ENDC}")
        return True
        
    except Exception as e:
        conn.rollback()
        print_error(f"Error al guardar en la base de datos: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        while True:
            crear_usuario_admin()
            if input(f"\n{Colors.WARNING}¿Crear otro perfil? (s/n): {Colors.ENDC}").lower() != 's':
                break
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Cancelado.{Colors.ENDC}")