# SIACE - Sistema Integral de Administración de Contratos y Escalafón 🏛️💻
### 🏫 Proyecto de Ingeniería de Sistemas - HMPP Pasco 2026

**SIACE** es una plataforma web de alto rendimiento diseñada específicamente para la **Honorable Municipalidad Provincial de Pasco (HMPP)**. Su objetivo es liderar la transformación digital del área de Recursos Humanos, sustituyendo los legajos físicos por un ecosistema digital centralizado que garantiza la integridad, seguridad y rapidez en la gestión del personal municipal.

---

## 🌟 Funcionalidades Destacadas

* **Gestión de Legajos Digitales:** Digitalización completa de expedientes, permitiendo la carga y consulta inmediata de resoluciones, contratos y documentos personales.
* **Motor Automatizado de Planillas:** Algoritmo dinámico que calcula remuneraciones, descuentos y beneficios sociales, minimizando el error humano.
* **Seguridad Basada en Roles:** Acceso restringido mediante niveles (Administrador de Sistemas, RRHH, Escalafón) para proteger la confidencialidad de la información.
* **Generación de Reportes PDF:** Creación instantánea de boletas de pago y reportes de escalafón con estándares institucionales.
* **Trazabilidad y Auditoría:** Registro detallado (bitácora) de todas las acciones realizadas en el sistema para un control administrativo total.

---

## 🛠️ 1. Infraestructura y Requisitos Previos

Para garantizar la estabilidad del SIACE, el servidor debe cumplir con los siguientes requisitos técnicos:

* **Python 3.8 o Superior:** El núcleo del sistema que procesa toda la lógica de negocio.
* **Microsoft ODBC Driver (17 o 18):** El componente esencial para que la aplicación se comunique de forma estable y rápida con la base de datos SQL Server.
* **GTK3 Runtime (Vital para Reportes):** El motor gráfico necesario para que la librería **WeasyPrint** pueda convertir los datos de planillas a archivos PDF profesionales.
    * *Instrucción:* Instalar `gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe` y, **sin falta**, marcar la casilla **"Add to PATH"** en el instalador.
* **SQL Server Express o Superior:** Motor de base de datos robusto para el almacenamiento seguro de los registros de escalafón.

---

## 🚀 2. Guía de Instalación y Despliegue

Siga estos pasos descriptivos para montar el sistema en un servidor o entorno local:

### 2.1. Clonación del Proyecto
Obtenga la última versión oficial del código fuente directamente desde el repositorio:
```bash
git clone [https://github.com/JairoSa/HMPP-SIACE.git](https://github.com/JairoSa/HMPP-SIACE.git)
cd HMPP-SIACE
```

### 2.2. Aislamiento del Entorno (Virtualización)
Creamos un entorno virtual (`venv`) para que las librerías del SIACE no interfieran con otros programas del servidor:
```bash
# Crear el entorno venv
python -m venv venv

# Activar el entorno (En Windows)
.\venv\Scripts\Activate.ps1
```

### 2.3. Instalación de Dependencias Críticas
Instalamos todos los módulos (Flask, SQLAlchemy, pyodbc, etc.) necesarios para el funcionamiento:
```bash
pip install -r requirements.txt
```

### 2.4. Configuración del Archivo de Identidad (.env)
Este archivo es el cerebro de la configuración. Debe crearse en la raíz del proyecto y editarse con cuidado:

```dotenv
# --- SEGURIDAD DE FLASK ---
# Clave maestra para encriptar las sesiones de usuario
SECRET_KEY=hmpp_pasco_2026_secreto_final
FLASK_DEBUG=False

# --- CONEXIÓN A BASE DE DATOS ---
# Define el driver, el servidor local (ej. OSCAR\SQLEXPRESS) y la BD del sistema
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=OSCAR\SQLEXPRESS
DB_DATABASE=BaseDatosHMPP
DB_USERNAME_WRITE=sa
DB_PASSWORD_WRITE=tu_contraseña_sql

# --- CREDENCIALES DE ADMINISTRACIÓN ---
DB_USERNAME_SYSTEMS_ADMIN=sa
DB_PASSWORD_SYSTEMS_ADMIN=tu_contraseña_sql

# --- CONFIGURACIÓN DE CORREO INSTITUCIONAL ---
# Para el envío de alertas y notificaciones automáticas
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=jairomandujano25@gmail.com
MAIL_PASSWORD=tu_clave_de_aplicacion_gmail
MAIL_DEFAULT_SENDER=jairomandujano25@gmail.com

# --- RESPALDOS DE SEGURIDAD ---
# Ruta física donde se guardarán los archivos de backup (.bak)
BACKUP_PATH=C:\Backups_Escalafon
```

---

## ⚙️ 3. Configuración del Sistema y Ejecución

### 3.1. Arquitectura de Datos
Antes de arrancar, se debe ejecutar el archivo **`BaseDatosHMPP.sql`** en SQL Server Management Studio para crear las tablas, relaciones, disparadores (triggers) y procedimientos almacenados.

### 3.2. Creación del Usuario Maestro
Para el primer inicio de sesión, ejecute el script administrativo:
```bash
python crear_admin.py
```
Este paso registrará al primer personal en la base de datos y le otorgará el rol de **Sistemas**.

### 3.3. Puesta en Marcha (Ejecución)
Para el uso diario en la Municipalidad de Pasco, se debe utilizar el servidor de producción:
```bash
# Servidor Waitress: Soporta múltiples usuarios al mismo tiempo de forma estable
python run_production.py
```
El sistema será accesible desde cualquier navegador en la red interna a través de: **`http://localhost:5001`**

---

## 📂 4. Mantenimiento y Documentación
* **`run_production.py`**: El script de ejecución oficial para servidores.
* **`DOCUMENTACION.md`**: Guía detallada para administradores de bases de datos sobre cómo restaurar backups en caso de desastres.
* **`REQUISITOS_SISTEMA.md`**: Listado completo de hardware y software compatible.

---

## 👨‍💻 Créditos y Autoría
* **Desarrollador:** Jairo Francisco Santos Mandujano
* **Institución:** Universidad Nacional Daniel Alcides Carrión (UNDAC)
* **Facultad:** Ingeniería de Sistemas y Computación
* **Ubicación:** Cerro de Pasco, Perú - 2026