"""
Script para crear el primer usuario administrador
SIACE - H. Municipalidad Provincial de Pasco 2026
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
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def get_db_connection():
    """Obtiene una conexión a la base de datos usando las credenciales del .env"""
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
        return None

def validar_email(email):
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def crear_usuario_admin():
    print_header("CREAR ADMINISTRADOR SIACE - HMPP")
    
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        # Verificar si ya existen administradores
        cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE id_rol = 1")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print_info(f"Ya existen {count} administrador(es) en el sistema.")
            if input("¿Desea crear otro? (s/n): ").lower() != 's':
                return False

        # --- DATOS DEL PERSONAL ---
        print(f"\n{Colors.BOLD}1. Datos del Personal:{Colors.ENDC}")
        
        while True:
            dni = input("DNI (8 dígitos): ").strip()
            if dni.isdigit() and len(dni) == 8:
                cursor.execute("SELECT id_personal FROM Personal WHERE dni = ?", dni)
                if cursor.fetchone():
                    print_error("Este DNI ya está registrado.")
                    continue
                break
            print_error("DNI inválido.")

        nombres = input("Nombres: ").strip().upper()
        ap_paterno = input("Apellido Paterno: ").strip().upper()
        ap_materno = input("Apellido Materno: ").strip().upper()
        
        while True:
            sexo = input("Sexo (M/F): ").strip().upper()
            if sexo in ['M', 'F']: break
            print_error("Use 'M' para masculino o 'F' para femenino.")

        while True:
            email = input("Email: ").strip().lower()
            if validar_email(email): break
            print_error("Email inválido.")

        telefono = input("Teléfono (opcional): ").strip() or None
        
        # Insertar en Personal
        print_info("Guardando registro de personal...")
        cursor.execute("""
            INSERT INTO Personal (dni, nombres, apellidos, sexo, email, telefono, id_unidad, activo)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1)
        """, dni, nombres, f"{ap_paterno} {ap_materno}", sexo, email, telefono)
        
        # Obtener el ID recién creado de forma segura
        cursor.execute("SELECT SCOPE_IDENTITY()")
        id_personal = int(cursor.fetchone()[0])
        
        # --- DATOS DEL USUARIO ---
        print(f"\n{Colors.BOLD}2. Datos del Usuario:{Colors.ENDC}")
        
        while True:
            username = input("Nombre de usuario (mín. 4 caracteres): ").strip().lower()
            if len(username) >= 4:
                cursor.execute("SELECT id_usuario FROM Usuarios WHERE username = ?", username)
                if cursor.fetchone():
                    print_error("El nombre de usuario ya existe.")
                    continue
                break
            print_error("Nombre de usuario demasiado corto.")

        while True:
            password = getpass("Contraseña (mín. 8 caracteres): ")
            if len(password) >= 8:
                if password == getpass("Confirme contraseña: "):
                    break
                print_error("Las contraseñas no coinciden.")
            else:
                print_error("Contraseña demasiado corta.")

        # Hasheo y guardado
        pass_hash = generate_password_hash(password)
        print_info("Configurando credenciales de acceso...")
        
        cursor.execute("""
            INSERT INTO Usuarios (username, email, password_hash, id_rol, activo, id_personal)
            VALUES (?, ?, ?, 1, 1, ?)
        """, username, email, pass_hash, id_personal)
        
        conn.commit()
        print_success(f"Usuario '{username}' creado exitosamente como Administrador.")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print_error(f"Error en la creación: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        crear_usuario_admin()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Proceso cancelado.{Colors.ENDC}")