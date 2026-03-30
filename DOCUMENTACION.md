# Documentación Técnica del Sistema SIACE - HMPP Pasco 🏛️💻

Este documento proporciona una descripción detallada de la arquitectura, componentes y flujos de trabajo del sistema **SIACE (Sistema Integral de Administración de Contratos y Escalafón)**. Está diseñado para servir como guía de referencia completa para los desarrolladores, arquitectos de software y el equipo de TI de la Honorable Municipalidad Provincial de Pasco.

## Tabla de Contenidos

1. [Arquitectura General](#1-arquitectura-general)
2. [Capa de Dominio (`app/domain`)](#2-capa-de-dominio-appdomain)
3. [Capa de Aplicación (`app/application`)](#3-capa-de-aplicación-appapplication)
4. [Capa de Infraestructura (`app/infrastructure`)](#4-capa-de-infraestructura-appinfrastructure)
5. [Capa de Presentación (`app/presentation`)](#5-capa-de-presentación-apppresentation)
6. [Configuración y Arranque](#6-configuración-y-arranque)
7. [Flujo de una Solicitud](#7-flujo-de-una-solicitud)
8. [Módulos de RRHH y Legajos](#92-módulos-de-rrhh-y-legajos)
9. [Módulo de Autenticación](#93-módulo-de-autenticación)
10. [Configuración y Variables de Entorno](#10-configuración-y-variables-de-entorno)
11. [Componentes Principales y Utilidades](#11-componentes-principales-y-utilidades)
12. [Estructura del Frontend](#12-estructura-del-frontend)
13. [Estrategia de Manejo de Errores y Logging](#13-estrategia-de-manejo-de-errores-y-logging)
14. [Consideraciones para Despliegue en Producción](#14-consideraciones-para-despliegue-en-producción)
15. [Mantenimiento y Recuperación de Datos](#15-mantenimiento-y-recuperación-de-datos)

---

## 1. Arquitectura General

El sistema SIACE está construido siguiendo una **Arquitectura en Capas (Layered Architecture)**, un diseño que promueve la **Separación de Responsabilidades (Separation of Concerns)**. Esta arquitectura está fuertemente influenciada por los principios de **Domain-Driven Design (DDD)** y **Clean Architecture**.

El objetivo principal es aislar la lógica de negocio (el dominio) de las tecnologías externas (como la base de datos o la interfaz de usuario). Esto hace que el sistema sea más fácil de mantener, probar y escalar ante los cambios institucionales de la HMPP.

La estructura se puede visualizar como una serie de capas concéntricas, donde las dependencias fluyen hacia adentro:


- **Capa de Presentación**: La interfaz de usuario (UI) que maneja la interacción con el personal municipal.
- **Capa de Aplicación**: Orquesta los casos de uso específicos del sistema de escalafón.
- **Capa de Dominio**: El corazón de la lógica de negocio, reglas de escalafón y contratos.
- **Capa de Infraestructura**: Implementaciones técnicas como SQL Server, servicios de correo y backups.

### Principios Clave:

- **Regla de Dependencia**: El código fuente solo puede tener dependencias que apunten hacia adentro. Nada en una capa interna puede saber nada sobre una capa externa. Por ejemplo, el dominio no sabe qué base de datos se está utilizando.
- **Abstracción**: Las capas externas implementan interfaces (contratos) definidas en las capas internas. Esto permite intercambiar implementaciones sin afectar la lógica de negocio.

---

## 2. Capa de Dominio (`app/domain`)

Esta capa es el **corazón de la aplicación**. Contiene toda la lógica de negocio, las reglas y las entidades que son independientes de cualquier tecnología externa. No sabe nada sobre la base de datos, la web o cualquier otro detalle de implementación.

### 2.1. Modelos (`app/domain/models`)

Este directorio contiene las **Entidades de Negocio**. Son clases de Python que representan los conceptos fundamentales del sistema.

- `usuario.py`: Representa a un usuario del sistema, con sus credenciales, roles y estado.
- `personal.py`: Modela a un empleado de la organización, conteniendo toda su información personal.
- `contrato.py`: Define la relación contractual de un empleado, incluyendo tipo, fechas y condiciones.
- `documento.py`: Representa un documento físico o digital asociado a un legajo.
- `legajo_seccion.py`: Modela la estructura y secciones que componen el legajo de un empleado.
- `rol.py`: Define los roles y permisos dentro de la aplicación (ej. RRHH, Sistemas).
- `solicitud_modificacion.py`: Representa una solicitud de un usuario para cambiar un dato en un legajo, que requiere aprobación.
- *(y otros modelos que definen conceptos como capacitacion, estudio, licencia, etc.)*

### 2.2. Repositorios (`app/domain/repositories`)

Este directorio contiene las **Interfaces de Repositorio**. Una interfaz es un "contrato" que define qué operaciones de datos se pueden realizar con los modelos del dominio, pero no cómo se realizan. Esto es clave para la abstracción.

- `i_usuario_repository.py`: Define métodos como `buscar_por_username`, `crear_usuario`, `actualizar_rol`, etc.
- `i_personal_repository.py`: Define métodos para buscar, crear y actualizar la información del personal.
- `i_auditoria_repository.py`: Define cómo se deben registrar los eventos de auditoría en el sistema.

Estas interfaces aseguran que la capa de aplicación pueda solicitar datos sin conocer los detalles de la base de datos subyacente.

---

## 3. Capa de Aplicación (`app/application`)

Esta capa actúa como un **orquestador**. No contiene lógica de negocio, sino que dirige a los objetos del dominio para que la ejecuten en respuesta a las solicitudes de la capa de presentación. Es el puente entre la UI y el Dominio.

### 3.1. Servicios (`app/application/services`)

Los servicios de aplicación implementan los **casos de uso** del sistema. Cada servicio encapsula una funcionalidad específica.

- `usuario_service.py`: Maneja la lógica relacionada con la autenticación, 2FA (Two-Factor Authentication) y la gestión de sesiones de usuario.
- `user_management_service.py`: Se encarga de los casos de uso administrativos sobre usuarios, como la creación, actualización de roles y cambio de estado.
- `legajo_service.py`: Orquesta las operaciones sobre los legajos del personal, como la obtención de datos completos, la adición de documentos, etc.
- `audit_service.py`: Proporciona una interfaz sencilla para que el resto de la aplicación pueda registrar eventos de auditoría importantes.
- `email_service.py`: Abstrae el envío de correos electrónicos, como los códigos de 2FA o notificaciones.
- `backup_service.py`: Contiene la lógica para ejecutar y registrar las copias de seguridad de la base de datos.
- `solicitud_service.py`: Gestiona la creación y procesamiento de solicitudes de modificación de datos.
- `workflow_service.py`: Maneja la lógica de los flujos de aprobación para las solicitudes.

### 3.2. Formularios (`app/application/forms.py`)

Este archivo define las clases de formularios utilizando la librería `Flask-WTF`. Su responsabilidad es:

1. **Definir los campos** que se mostrarán en la interfaz de usuario.
2. **Validar los datos** enviados por el usuario (ej. que un email tenga el formato correcto, que un campo requerido no esté vacío).

Esto asegura que los datos que llegan a los servicios de aplicación ya han sido limpiados y validados, evitando que lógica de validación de UI contamine las capas internas.

---

## 4. Capa de Infraestructura (`app/infrastructure` y `app/database`)

Esta capa contiene las **implementaciones concretas** de las tecnologías externas. Es el "cómo" se hacen las cosas que las capas internas solo definen.

### 4.1. Persistencia (`app/infrastructure/persistence`)

Aquí es donde se implementan las interfaces de repositorio definidas en el dominio.

- `sqlserver_repository.py`: Esta clase contiene el código **específico para SQL Server**. Implementa las interfaces como `IUsuarioRepository` y traduce sus métodos (`buscar_por_username`) a consultas SQL (`SELECT * FROM Usuario WHERE username = ?`) o llamadas a procedimientos almacenados.

### 4.2. Conector de Base de Datos (`app/database/connector.py`)

Este componente se encarga de una única responsabilidad: **gestionar la conexión con la base de datos**.

- Lee la cadena de conexión desde la configuración de la aplicación.
- Utiliza la librería `pyodbc` para establecer y mantener un pool de conexiones con el servidor `OSCAR\SQLEXPRESS`.
- Proporciona métodos para obtener una conexión activa y ejecutar consultas, gestionando transacciones (commit, rollback) y el cierre de conexiones.

Abstrae el manejo de la conexión para que los repositorios no tengan que preocuparse por los detalles de bajo nivel de `pyodbc`.

---

## 5. Capa de Presentación (`app/presentation`)

Esta es la capa más externa, responsable de interactuar con el usuario final. En esta aplicación web, se encarga de manejar las peticiones HTTP y renderizar las plantillas HTML.

### 5.1. Rutas (`app/presentation/routes`)

Las rutas definen los endpoints (URLs) de la aplicación. El código está organizado en **Blueprints** de Flask, que permiten agrupar rutas por funcionalidad, manteniendo el código ordenado.

- `auth_routes.py`: Maneja las URLs de autenticación, como `/login`, `/logout` y `/verify_2fa`.
- `sistemas_routes.py`: Contiene los endpoints para el panel de administración del sistema (gestión de usuarios, auditoría, backups, etc.).
- `rrhh_routes.py`: Define las rutas para el personal de Recursos Humanos, como la visualización de legajos y la gestión de personal.
- `legajo_routes.py`: Rutas relacionadas con la gestión específica del contenido de un legajo.
- `report_routes.py`: Endpoints para la generación de reportes.

Las funciones dentro de estos archivos actúan como **controladores**: reciben la petición, la delegan al servicio de aplicación correspondiente y, con el resultado, seleccionan y renderizan la plantilla adecuada.

### 5.2. Plantillas (`app/presentation/templates`)

Este directorio contiene los archivos HTML que conforman la interfaz de usuario. Se utiliza el motor de plantillas **Jinja2**, que permite:

- **Herencia de plantillas**: Se define una `base.html` o `dashboard.html` con la estructura común (header, footer, sidebar), y las páginas específicas heredan de ella.
- **Lógica simple**: Permite usar bucles (`for`), condicionales (`if`) y mostrar variables pasadas desde el controlador.
- **Reutilización de componentes**: Se pueden crear componentes pequeños e incluirlos en varias páginas.

### 5.3. Archivos Estáticos (`app/presentation/static`)

Contiene los archivos que no cambian, como:
- `css`: Hojas de estilo para dar formato y diseño a la aplicación.
- `js`: Archivos JavaScript para la interactividad en el lado del cliente.
- `img`: Imágenes y otros recursos gráficos institucionales de la HMPP.

### 5.4. Seguridad en el Frontend (CSRF)

Para proteger la aplicación contra ataques de Falsificación de Peticiones en Sitios Cruzados (CSRF), se utiliza la extensión `Flask-WTF`.

- **Inclusión del Token**: Todos los formularios que realizan una acción de modificación de datos (`POST`, `PUT`, `DELETE`) deben incluir un token CSRF. Esto se logra añadiendo `{{ form.hidden_tag() }}`.
- **Modales y JavaScript**: Se debe prestar especial atención a los formularios dentro de modales que se envían mediante JavaScript. Es fundamental que el token CSRF esté presente. La ausencia de este token resultará en un error `400 Bad Request`.

---

## 6. Configuración y Arranque

Estos archivos son responsables de inicializar y configurar la aplicación Flask, así como de ensamblar todas las capas.

- `run.py`: Es el **punto de entrada** para ejecutar la aplicación. Su única responsabilidad es importar la función `create_app` y poner en marcha el servidor de desarrollo.
- `run_production.py`: Punto de entrada para el entorno de producción usando **Waitress** para garantizar estabilidad multi-usuario.
- `config.py`: Define una clase `Config` que contiene todas las variables de configuración de la aplicación, como las claves secretas y la cadena de conexión. Carga variables sensibles desde un archivo `.env`.
- `app/__init__.py`: Contiene la función `create_app()`, que actúa como una **fábrica de la aplicación**. Sus responsabilidades son:
    1. Crear la instancia principal de la aplicación Flask.
    2. Cargar la configuración desde el objeto `Config`.
    3. Inicializar las extensiones de Flask (como `LoginManager`).
    4. **Realizar la Inyección de Dependencias**: Se crean las instancias de los repositorios y servicios, inyectando las dependencias necesarias en cada uno.
    5. Registrar los **Blueprints** de las rutas.

---

## 7. Flujo de una Solicitud

Para consolidar la comprensión de la arquitectura, sigamos el viaje de una petición a través del sistema.

**Caso de Uso**: Un usuario de RRHH solicita ver el legajo completo de un empleado con un DNI específico.

1. **Petición HTTP (Navegador)**: El usuario hace clic en un enlace, generando una petición `GET` a la URL `/rrhh/ver_legajo/12345678`.
2. **Capa de Presentación (Rutas)**: Flask recibe la petición y el blueprint de RRHH captura esta URL, ejecutando la función controladora `ver_legajo(dni)`.
3. **Capa de Aplicación (Servicios)**: El controlador delega inmediatamente la tarea a un servicio de aplicación: `legajo_service.obtener_legajo_completo(dni)`.
4. **Capa de Dominio (Interfaces de Repositorio)**: El `legajo_service` invoca un método de la **interfaz** de repositorio que tiene inyectada: `self.personal_repo.buscar_por_dni(dni)`.
5. **Capa de Infraestructura (Implementación del Repositorio)**: El motor de inyección de dependencias determinó que `self.personal_repo` es una instancia de `SqlServerRepository`. Se ejecuta el método que construye la consulta SQL o llama al SP correspondiente.
6. **Retorno de Datos y Modelado (Dominio)**: La base de datos devuelve los datos crudos. El repositorio utiliza estos datos para construir una instancia del modelo de dominio `Personal`.
7. **Flujo de Retorno**: El objeto `Personal` viaja de vuelta a través de las capas: Infraestructura -> Aplicación -> Presentación.
8. **Renderizado (Presentación)**: La función controladora recibe el objeto `Personal` y llama a `render_template`, pasando el objeto a la plantilla.
9. **Respuesta HTTP (Navegador)**: El servidor envía el HTML renderizado de vuelta al navegador del usuario.

Este flujo asegura que todas las solicitudes sean manejadas de manera consistente y que la lógica de negocio esté centralizada en los servicios de aplicación y el dominio.

---

## 9.2. Módulos de RRHH y Legajos (`rrhh_routes.py` y `legajo_routes.py`)

Estos dos módulos forman el núcleo funcional de la gestión de legajos.

#### 9.2.1. Listado y Consulta de Personal (Rol: RRHH, AdminLegajos, Sistemas)

- **Ruta Principal**: `/personal`
- **Función**: `listar_personal()`
- **Descripción**: Muestra una lista paginada de todo el personal registrado. Permite filtrar por DNI y nombres. Muestra el estado de los documentos de cada empleado (vencidos o por vencer).
- **Flujo de Datos**:
    1. El controlador llama a `legajo_service.get_all_personal_paginated()`.
    2. También llama a `legajo_service.check_document_status_for_all_personal()`.
    3. Ambos métodos llaman a procedimientos almacenados (`sp_listar_personal_paginado` y `sp_listar_documentos_con_vencimiento`).
    4. La plantilla renderiza la tabla.

#### 9.2.2. Creación de un Nuevo Legajo (Rol: AdminLegajos)

- **Ruta Principal**: `/personal/nuevo`
- **Función**: `crear_personal()`
- **Descripción**: Presenta un formulario (`PersonalForm`) para registrar a un nuevo empleado.
- **Flujo de Datos**:
    1. Al cargar, se puebla el menú desplegable de unidades administrativas.
    2. Tras enviar, el controlador llama a `legajo_service.register_new_personal()`.
    3. El servicio invoca `sp_registrar_personal` y registra la acción en la bitácora.

#### 9.2.3. Visualización de un Legajo Completo (Rol: RRHH, AdminLegajos, Sistemas)

- **Ruta Principal**: `/personal/<id>`
- **Función**: `ver_legajo()`
- **Descripción**: Muestra una vista detallada de toda la información de un empleado.
- **Flujo de Datos**:
    1. El controlador llama a `legajo_service.get_personal_details()`, pasando el `personal_id` y el objeto `current_user`.
    2. El servicio obtiene los datos (usando `sp_obtener_legajo_completo_por_personal`).
    3. Realiza una validación de permisos basada en el rol del `current_user`.
    4. La plantilla organiza y muestra la información.

#### 9.2.4. Gestión de Documentos (Rol: AdminLegajos)

- **Ruta Principal**: `/personal/<id>/documento/subir`
- **Función**: `subir_documento()`, `eliminar_documento()`, `visualizar_documento()`
- **Descripción**: Permite añadir, eliminar lógicamente y visualizar los archivos adjuntos.
- **Flujo de Datos (Subida)**:
    1. El formulario `DocumentoForm` se procesa.
    2. Se llama a `legajo_service.upload_document_to_personal()`, que valida el archivo y calcula su hash.
    3. El repositorio ejecuta `sp_subir_documento` para guardar el archivo en la base de datos.

#### 9.2.5. Exportación a Excel (Rol: RRHH, AdminLegajos, Sistemas)

- **Ruta Principal**: `/personal/exportar/general`
- **Función**: `exportar_lista_general_excel()`
- **Descripción**: Genera un reporte Excel completo del personal.
- **Flujo de Datos**:
    1. El controlador llama a `legajo_service.generate_general_report_excel()`.
    2. El servicio obtiene datos mediante `sp_generar_reporte_general_personal` y usa `openpyxl`.
    3. Se audita la acción y se envía el archivo al navegador.

---

## 9.3. Módulo de Autenticación (`auth_routes.py`)

#### 9.3.1. Inicio de Sesión
Presenta el formulario y procesa credenciales. Si son correctas, genera un código 2FA enviado por correo.

#### 9.3.2. Verificación en Dos Pasos (2FA)
Pide el código de 6 dígitos. El servicio verifica el código y, si es correcto, completa el inicio de sesión actualizando `ultimo_login` e iniciando `login_user()`.

#### 9.3.3. Enrutamiento Post-Login
Actúa como un enrutador inteligente redirigiendo según el rol (`Sistemas` al dashboard, `RRHH` a su inicio).

#### 9.3.4. Cierre de Sesión
Elimina los datos del usuario de la sesión y redirige al login.

---

## 10. Configuración y Variables de Envornot

La configuración se gestiona a través de un archivo `.env` cargado por `config.py`.
- `SECRET_KEY`: Cadena para firmar sesiones criptográficamente.
- `DB_DRIVER`: Driver ODBC (SQL Server).
- `DB_SERVER`: `OSCAR\SQLEXPRESS`.
- `DB_DATABASE`: `BaseDatosHMPP`.
- `MAIL_*`: Configuración SMTP para el envío de códigos 2FA.

---

## 11. Componentes Principales y Utilidades

#### 11.1. Decoradores (`app/decorators.py`)
- `@role_required(*roles)`: Restringe el acceso según los roles especificados.
- `@limiter.limit`: Protege rutas sensibles contra ataques de fuerza bruta.

#### 11.2. Conector de Base de Datos
Abstrae la gestión de la conexión y provee un pool funcional a los repositorios.

#### 11.3. Paginación (`app/utils/pagination.py`)
Clase `SimplePagination` que encapsula la lógica para navegar grandes volúmenes de datos en las tablas.

#### 11.4. Filtros de Plantilla Personalizados
Filtro `| localtime`: Convierte objetos de fecha de la BD a la zona horaria de Perú (UTC-5).

---

## 12. Estructura del Frontend

#### 12.1. Herencia de Plantillas
`base.html` define la estructura raíz y `dashboard.html` la estructura visual común interna.

#### 12.2. Activos Estáticos
Estilos personalizados en `prototipo_style.css` y archivos JS para interactividad.

#### 12.3. Seguridad en el Frontend (CSRF)
Inclusión obligatoria del token en todos los formularios para prevenir ataques CSRF.

---

## 13. Estrategia de Manejo de Errores y Logging

- **Validación de Formularios**: Captura de errores de entrada vía `Flask-WTF`.
- **Excepciones de Negocio**: Feedback mediante mensajes `flash`.
- **Manejadores Globales**: Rutas específicas para errores 404 y 500 con plantillas personalizadas.
- **Logging**: Registro de errores técnicos en `logs/app.log` usando un `RotatingFileHandler`.

---

## 14. Consideraciones para Despliegue en Producción

- **Servidor WSGI**: Uso de **Waitress** para estabilidad en Windows.
- **Variables de Entorno**: Configuración directa en el servidor, no en el repositorio.
- **Modo Debug**: Establecido en `False` para seguridad.
- **Seguridad de la Base de Datos**: Uso de permisos mínimos y ejecución solo vía Procedimientos Almacenados.

---

## 15. Mantenimiento de Base de Datos (Backups)

El sistema SIACE incluye un protocolo de mantenimiento preventivo para asegurar la continuidad de los datos.

### 15.1. Guía de Restauración de Backup (SQL Server)

```sql
-- =============================================================================
-- GUÍA DE MANTENIMIENTO: RESTAURACIÓN DE BACKUP (HMPP-SIACE)
-- =============================================================================

USE [master];
GO

-- 1. RESTAURACIÓN EN BASE DE DATOS DE PRUEBA
RESTORE DATABASE [HMPP_Test]
FROM DISK = N'C:\Backups_Escalafon\HMPP_Backup_Archivo.bak' 
WITH 
    MOVE N'BaseDatosHMPP' 
    TO N'C:\Program Files\Microsoft SQL Server\MSSQL15.SQLEXPRESS\MSSQL\DATA\HMPP_Test.mdf',
    MOVE N'BaseDatosHMPP_log' 
    TO N'C:\Program Files\Microsoft SQL Server\MSSQL15.SQLEXPRESS\MSSQL\DATA\HMPP_Test_log.ldf',
    REPLACE, 
    STATS = 10;
GO

-- 2. VERIFICACIÓN DE DATOS
SELECT 'PRODUCCIÓN' AS Origen, COUNT(*) AS Total FROM BaseDatosHMPP.dbo.personal
UNION ALL
SELECT 'TEST (BACKUP)' AS Origen, COUNT(*) AS Total FROM HMPP_Test.dbo.personal;
GO

-- 3. ELIMINACIÓN DE LA BASE DE PRUEBA (LIMPIEZA)
ALTER DATABASE [HMPP_Test] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
GO
DROP DATABASE [HMPP_Test];
GO
PRINT '---[ÉXITO]: El proceso de verificación ha finalizado y el espacio ha sido liberado.';
```

---

## 👤 Autoría y Créditos
* **Desarrollador**: Jairo Francisco Santos Mandujano
* **Institución**: Universidad Nacional Daniel Alcides Carrión (UNDAC)
* **Facultad**: Ingeniería de Sistemas y Computación
* **Ubicación**: Pasco, Perú - 2026