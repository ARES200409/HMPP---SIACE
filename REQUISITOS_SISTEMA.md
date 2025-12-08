# 💻 Requisitos del Sistema - Legajo Digital DIRESA

## ✅ Compatibilidad

Este sistema **SÍ se puede instalar en cualquier PC con Windows**, siempre que cumpla con los requisitos mínimos.

### Sistemas Operativos Compatibles:
- ✅ Windows 10 (32-bit y 64-bit)
- ✅ Windows 11
- ✅ Windows Server 2016 o superior
- ⚠️ Windows 8.1 (compatible pero no recomendado)
- ❌ Windows 7 o anterior (no soportado)

---

## 📋 Requisitos Previos (OBLIGATORIOS)

Antes de ejecutar el instalador, la PC debe tener instalado:

### 1. **Python 3.8 o superior** ⭐
   - **¿Qué es?**: Lenguaje de programación necesario para ejecutar la aplicación
   - **Descargar**: https://www.python.org/downloads/
   - **Tamaño**: ~30 MB
   - **Instalación**: 
     - ⚠️ **IMPORTANTE**: Durante la instalación, marcar la casilla **"Add Python to PATH"**
     - Esto permite ejecutar Python desde cualquier ubicación
   - **Verificar instalación**:
     ```cmd
     python --version
     ```
     Debe mostrar algo como: `Python 3.11.x`

### 2. **SQL Server** ⭐⭐⭐
   - **¿Qué es?**: Sistema de gestión de base de datos donde se almacenan todos los datos
   - **Versiones compatibles**: SQL Server 2016, 2017, 2019, 2022, 2025
   - **Opciones**:
     - **SQL Server 2025 Express** (GRATIS, versión más reciente)
     - **SQL Server Express** (GRATIS, recomendado para instalaciones pequeñas)
       - Descargar: https://www.microsoft.com/es-es/sql-server/sql-server-downloads
       - Tamaño: ~1.5 GB
       - Límites: Hasta 10 GB de base de datos (suficiente para la mayoría de casos)
     - **SQL Server Developer** (GRATIS, para desarrollo)
     - **SQL Server Standard/Enterprise** (PAGO, para producción grande)
   
   - **Instalación**:
     - Elegir "Instalación básica"
     - Anotar el nombre de la instancia (ejemplo: `.\SQLEXPRESS` o `localhost`)
     - Configurar autenticación mixta (Windows + SQL Server)
     - Crear usuario `sa` con contraseña segura
   
   - **Verificar instalación**:
     - Abrir "SQL Server Configuration Manager"
     - Verificar que el servicio esté en ejecución

### 3. **ODBC Driver 17 o 18 for SQL Server** ⭐⭐
   - **¿Qué es?**: Driver que permite a Python comunicarse con SQL Server
   - **Versiones compatibles**: ODBC Driver 17 o 18 (ambas funcionan)
   - **Descargar**: 
     - ODBC Driver 18 (más reciente): https://go.microsoft.com/fwlink/?linkid=2249004
     - ODBC Driver 17: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
   - **Tamaño**: ~10 MB
   - **Instalación**: Ejecutar el instalador y seguir los pasos
   - **Verificar instalación**:
     - Panel de Control → Herramientas administrativas → Orígenes de datos ODBC
     - En la pestaña "Controladores", buscar "ODBC Driver 17 for SQL Server"

### 4. **Git** (Opcional)
   - **¿Qué es?**: Sistema de control de versiones para clonar el repositorio
   - **Descargar**: https://git-scm.com/downloads
   - **Tamaño**: ~50 MB
   - **Alternativa**: Puedes descargar el proyecto como ZIP sin necesidad de Git

---

## 🖥️ Requisitos de Hardware

### Mínimos (Para pruebas o uso ligero):
- **Procesador**: Intel Core i3 o equivalente
- **RAM**: 4 GB (con SQL Server Express)
- **Disco Duro**: 10 GB de espacio libre
- **Conexión a Internet**: Para descargar dependencias (solo durante instalación)

### Recomendados (Para uso en producción):
- **Procesador**: Intel Core i5 o superior
- **RAM**: 8 GB o más
- **Disco Duro**: 20 GB de espacio libre (SSD recomendado)
- **Conexión a Internet**: Para envío de emails y actualizaciones

---

## 📦 ¿Qué se instala automáticamente?

El instalador (`INSTALAR.bat` o `installer.py`) se encarga de:

✅ **Dependencias de Python** (automático):
- Flask (framework web)
- pyodbc (conexión a SQL Server)
- Flask-Login (autenticación)
- Flask-Mail (envío de emails)
- Y muchas más... (ver `requirements.txt`)

✅ **Base de datos** (automático):
- Crea la base de datos `BaseDatosDiresa`
- Crea todas las tablas
- Crea procedimientos almacenados
- Crea índices
- Configura usuarios y permisos

✅ **Configuración** (automático):
- Genera archivo `.env` con credenciales
- Configura claves de seguridad

---

## 🚫 ¿Qué NO se instala automáticamente?

❌ **Python** - Debes instalarlo manualmente antes
❌ **SQL Server** - Debes instalarlo manualmente antes
❌ **ODBC Driver** - Debes instalarlo manualmente antes

---

## 📝 Checklist de Instalación

Usa este checklist para verificar que tienes todo listo:

### Antes de ejecutar el instalador:
- [ ] Windows 10 o superior
- [ ] Python 3.8+ instalado y en PATH
- [ ] SQL Server instalado y en ejecución
- [ ] ODBC Driver 17 instalado
- [ ] Conoces el nombre del servidor SQL (ej: `localhost`, `.\SQLEXPRESS`)
- [ ] Tienes credenciales de administrador de SQL Server (usuario `sa`)
- [ ] Tienes al menos 10 GB de espacio libre en disco

### Durante la instalación:
- [ ] Ejecutar `INSTALAR.bat` o `python installer.py`
- [ ] Proporcionar credenciales de SQL Server
- [ ] Configurar usuarios de la aplicación
- [ ] (Opcional) Configurar email

### Después de la instalación:
- [ ] Ejecutar `python crear_admin.py` para crear primer usuario
- [ ] Ejecutar `python verificar_sistema.py` para verificar
- [ ] Ejecutar `python run.py` para iniciar la aplicación
- [ ] Acceder a http://localhost:5001

---

## 🌐 Escenarios de Instalación

### Escenario 1: PC Individual (Desarrollo/Pruebas)
**Configuración**:
- Python 3.11
- SQL Server Express (instalado localmente)
- Servidor: `localhost` o `.\SQLEXPRESS`

**Uso**: Un solo usuario en la misma PC

### Escenario 2: Servidor Dedicado (Producción)
**Configuración**:
- Python 3.11
- SQL Server Standard/Enterprise
- Servidor: IP del servidor (ej: `192.168.1.100`)

**Uso**: Múltiples usuarios accediendo desde diferentes PCs en la red

### Escenario 3: Servidor Remoto (Nube)
**Configuración**:
- Python 3.11
- SQL Server en Azure o AWS
- Servidor: URL del servidor remoto

**Uso**: Acceso desde cualquier lugar con internet

---

## 🔒 Consideraciones de Seguridad

### Para instalación en PC individual:
- ✅ Firewall de Windows puede estar activo
- ✅ Acceso solo desde localhost

### Para instalación en servidor:
- ⚠️ Configurar firewall para permitir puerto 5001 (o el que uses)
- ⚠️ Usar HTTPS en producción
- ⚠️ Configurar SQL Server para aceptar conexiones remotas
- ⚠️ Usar contraseñas seguras para todos los usuarios

---

## 🆘 Problemas Comunes

### "Python no se reconoce como comando"
**Solución**: Reinstalar Python marcando "Add to PATH" o agregar manualmente a las variables de entorno

### "No se puede conectar a SQL Server"
**Solución**: 
- Verificar que el servicio SQL Server esté en ejecución
- Verificar el nombre del servidor
- Habilitar TCP/IP en SQL Server Configuration Manager

### "ODBC Driver not found"
**Solución**: Instalar ODBC Driver 17 for SQL Server

### "Error de permisos al crear base de datos"
**Solución**: Usar un usuario con permisos de administrador (como `sa`)

---

## 📞 Soporte

Si tienes problemas durante la instalación:

1. Ejecuta `python verificar_sistema.py` para diagnóstico
2. Revisa los logs en la carpeta `logs/`
3. Consulta la sección de solución de problemas en `INSTALACION.md`
4. Contacta al equipo de desarrollo

---

## ✅ Resumen

**SÍ, se puede instalar en cualquier PC con Windows 10**, siempre que:

1. ✅ Tenga Windows 10 o superior
2. ✅ Instales Python 3.8+
3. ✅ Instales SQL Server (Express es suficiente)
4. ✅ Instales ODBC Driver 17
5. ✅ Ejecutes el instalador

**El proceso completo toma aproximadamente 30-60 minutos** (incluyendo descargas e instalación de requisitos).

---

**¡El sistema está diseñado para ser fácil de instalar en cualquier PC Windows!** 🎉
