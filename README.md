
<<<<<<< HEAD
# Sistema de Escalafón Digital - HMPP Pasco

# Sistema de Esacalafón Digital - HMPP Pasco
2f7550f (Migración HMPP: Calculadora dinámica, importación Excel inteligente con SCTR y gestión de histórico)

Este es un sistema de gestión de legajos digitales desarrollado en Python con el framework Flask, siguiendo una arquitectura en capas para asegurar su mantenibilidad y escalabilidad.

## 💻 Compatibilidad

**✅ Este sistema se puede instalar en cualquier PC con Windows 10 o superior**

Para más detalles sobre requisitos y compatibilidad:
- 📖 **[GUIA_RAPIDA.md](GUIA_RAPIDA.md)** - Guía rápida de instalación paso a paso
- 📋 **[REQUISITOS_SISTEMA.md](REQUISITOS_SISTEMA.md)** - Requisitos detallados y escenarios de uso

## 1. Requisitos Previos

Antes de comenzar, asegúrate de tener instalado lo siguiente en tu sistema:

-   **Python 3.8+**: [Descargar Python](https://www.python.org/downloads/)
-   **Microsoft ODBC Driver for SQL Server**: Necesario para que la librería `pyodbc` pueda comunicarse con la base de datos. [Descargar ODBC Driver](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
-   **Git**: Para clonar el repositorio. [Descargar Git](https://git-scm.com/downloads)
-   **SQL Server**: Una instancia de SQL Server (puede ser Express, Developer o una versión completa).

## 2. Guía de Instalación

Tienes dos opciones para instalar el sistema:

### 🚀 Opción A: Instalación Automática (Recomendada)

El sistema incluye un instalador automático que configura todo por ti.

#### En Windows:
1. Haz doble clic en el archivo `INSTALAR.bat`
2. Sigue las instrucciones en pantalla

#### Usando Python directamente:
```bash
# 1. Instalar dependencias mínimas
pip install pyodbc python-dotenv

# 2. Ejecutar el instalador
python installer.py
```

El instalador automáticamente:
- ✅ Genera el archivo `.env` con una clave secreta segura
- ✅ Crea la base de datos SQL Server
- ✅ Crea todas las tablas necesarias
- ✅ Configura usuarios y permisos de SQL Server
- ✅ Instala las dependencias de Python

**📖 Para más detalles, consulta [INSTALACION.md](INSTALACION.md)**

### 🔧 Opción B: Instalación Manual

Si prefieres configurar manualmente, sigue estos pasos:

#### 2.1. Clonar el Repositorio

Abre una terminal y clona el repositorio desde GitHub:

```bash
git clone https://github.com/carlosDaniel2004/LEGAJO-DIGITAL.git
cd LEGAJO-DIGITAL
```

#### 2.2. Crear y Activar el Entorno Virtual

Es una buena práctica aislar las dependencias del proyecto en un entorno virtual.

```bash
# Crear el entorno virtual
python -m venv venv

# Activar el entorno virtual (en Windows con PowerShell)
.\venv\Scripts\Activate.ps1
```

#### 2.3. Instalar Dependencias

Con el entorno virtual activado, instala todas las librerías de Python necesarias:

```bash
pip install -r requirements.txt
```

#### 2.4. Configurar las Variables de Entorno

La aplicación se configura mediante un archivo `.env`.

1.  En la raíz del proyecto, crea un archivo llamado `.env`.
2.  Copia el contenido de `.env.example` y ajusta los valores a tu configuración local.

    ```dotenv
    # Configuración de Flask
    SECRET_KEY=tu-clave-secreta-aqui
    FLASK_DEBUG=False

    # Configuración de la Base de Datos
    DB_DRIVER=ODBC Driver 17 for SQL Server
    DB_SERVER=localhost
    DB_DATABASE=BaseDatosDiresa
    DB_USERNAME_WRITE=app_legajo
    DB_PASSWORD_WRITE=tu-contraseña
    DB_USERNAME_SYSTEMS_ADMIN=sistemas_admin
    DB_PASSWORD_SYSTEMS_ADMIN=tu-contraseña-admin

    # Configuración de Email
    MAIL_SERVER=smtp.gmail.com
    MAIL_PORT=587
    MAIL_USE_TLS=True
    MAIL_USERNAME=tu-correo@gmail.com
    MAIL_PASSWORD=tu-contraseña-de-aplicacion
    MAIL_DEFAULT_SENDER=tu-correo@gmail.com
    ```

#### 2.5. Configurar la Base de Datos

Crea la base de datos manualmente usando SQL Server Management Studio o ejecuta el instalador solo para la base de datos.

## 4. Crear el Primer Usuario Administrador

Después de instalar el sistema, necesitas crear el primer usuario administrador:

```bash
python crear_admin.py
```

Este script te guiará para crear:
- Un registro de personal
- Un usuario con rol de "Sistemas" (administrador)

## 5. Ejecutar la Aplicación

Una vez que todo está configurado, puedes iniciar el servidor de desarrollo de Flask:

```bash
python run.py
```

La aplicación estará disponible en tu navegador en la dirección `http://localhost:5001`.

## 6. Scripts de Utilidad

El proyecto incluye varios scripts útiles en la raíz:

-   **`installer.py`**: Instalador automático del sistema (configura todo)
-   **`crear_admin.py`**: Crea el primer usuario administrador
-   **`resetearEmail.py`**: Cambia el email de un usuario
-   **`reset_password_direct.py`**: Resetea la contraseña de un usuario

Para ejecutarlos, asegúrate de tener el entorno virtual activado y usa:

```bash
python nombre_del_script.py
```

