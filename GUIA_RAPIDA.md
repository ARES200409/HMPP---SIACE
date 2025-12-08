# 🎯 Guía Rápida de Instalación en Windows 10

## ¿Puedo instalar este sistema en mi PC?

### ✅ SÍ, si tu PC tiene:
```
┌─────────────────────────────────────────┐
│  ✓ Windows 10 o Windows 11              │
│  ✓ 4 GB de RAM (8 GB recomendado)       │
│  ✓ 10 GB de espacio libre en disco      │
│  ✓ Conexión a Internet (para instalar)  │
└─────────────────────────────────────────┘
```

---

## 📥 Paso 1: Instalar Requisitos (Solo la primera vez)

### A. Instalar Python 🐍
1. Ir a: https://www.python.org/downloads/
2. Descargar Python 3.11 o superior
3. **⚠️ IMPORTANTE**: Marcar "Add Python to PATH"
4. Hacer clic en "Install Now"
5. Esperar ~5 minutos

### B. Instalar SQL Server 🗄️
1. Ir a: https://www.microsoft.com/sql-server/sql-server-downloads
2. Descargar "SQL Server 2025 Express" o "SQL Server Express" (GRATIS)
3. Elegir "Instalación básica"
4. Anotar el nombre del servidor (ejemplo: `.\SQLEXPRESS`)
5. Esperar ~15 minutos

**Nota**: Compatible con SQL Server 2016, 2017, 2019, 2022, 2025

### C. Instalar ODBC Driver 🔌
1. Ir a: https://go.microsoft.com/fwlink/?linkid=2249004
2. Descargar "ODBC Driver 17 for SQL Server"
3. Ejecutar el instalador
4. Esperar ~2 minutos

---

## 🚀 Paso 2: Instalar el Sistema

### Opción Fácil (Recomendada):
```
1. Abrir la carpeta del proyecto
2. Hacer doble clic en: INSTALAR.bat
3. Seguir las instrucciones en pantalla
4. ¡Listo!
```

### Opción Manual:
```cmd
# 1. Abrir PowerShell o CMD en la carpeta del proyecto
# 2. Ejecutar:
python installer.py

# 3. Seguir las instrucciones
```

---

## 🎮 Paso 3: Usar el Sistema

```cmd
# 1. Crear el primer usuario administrador
python crear_admin.py

# 2. Iniciar la aplicación
python run.py

# 3. Abrir navegador en:
http://localhost:5001
```

---

## ⏱️ Tiempo Total de Instalación

```
┌────────────────────────────────────────────┐
│  Python:          ~5 minutos               │
│  SQL Server:      ~15 minutos              │
│  ODBC Driver:     ~2 minutos               │
│  Sistema:         ~5 minutos               │
│  ─────────────────────────────────────     │
│  TOTAL:           ~30 minutos              │
└────────────────────────────────────────────┘
```

---

## 💾 Espacio en Disco Necesario

```
┌────────────────────────────────────────────┐
│  Python:          ~100 MB                  │
│  SQL Server:      ~1.5 GB                  │
│  ODBC Driver:     ~10 MB                   │
│  Sistema:         ~50 MB                   │
│  Base de Datos:   ~100 MB (inicial)        │
│  ─────────────────────────────────────     │
│  TOTAL:           ~2 GB                    │
└────────────────────────────────────────────┘
```

---

## 🔍 Verificar que Todo Está Instalado

```cmd
# Verificar Python
python --version
# Debe mostrar: Python 3.x.x

# Verificar pip
pip --version
# Debe mostrar: pip x.x.x

# Verificar el sistema completo
python verificar_sistema.py
# Debe mostrar: ✓ El sistema está correctamente instalado
```

---

## 🌐 Escenarios de Uso

### 🏠 Uso Individual (1 PC)
```
Tu PC
├── Python ✓
├── SQL Server Express ✓
└── Sistema Legajo Digital ✓

Acceso: Solo desde tu PC
URL: http://localhost:5001
```

### 🏢 Uso en Red Local (Múltiples PCs)
```
Servidor (1 PC con todo instalado)
├── Python ✓
├── SQL Server ✓
└── Sistema Legajo Digital ✓

Clientes (Otras PCs)
└── Solo necesitan navegador web

Acceso: Desde cualquier PC en la red
URL: http://IP-DEL-SERVIDOR:5001
```

### ☁️ Uso en Internet (Acceso Remoto)
```
Servidor en la Nube
├── Python ✓
├── SQL Server ✓
└── Sistema Legajo Digital ✓

Usuarios
└── Solo necesitan navegador web e internet

Acceso: Desde cualquier lugar
URL: https://tu-dominio.com
```

---

## ❓ Preguntas Frecuentes

### ¿Necesito ser administrador de la PC?
**Sí**, para instalar Python, SQL Server y ODBC Driver necesitas permisos de administrador.

### ¿Funciona en Windows 7?
**No**, se requiere Windows 10 o superior.

### ¿Necesito internet todo el tiempo?
**No**, solo para la instalación inicial. Después funciona sin internet (excepto para envío de emails).

### ¿Puedo instalar en una laptop?
**Sí**, funciona perfectamente en laptops con Windows 10/11.

### ¿Cuántos usuarios pueden usar el sistema?
- **SQL Server Express**: Hasta ~10 usuarios simultáneos
- **SQL Server Standard**: Hasta ~100 usuarios simultáneos
- **SQL Server Enterprise**: Sin límite

### ¿Necesito pagar por algo?
**No**, todo es gratuito:
- ✅ Python: GRATIS
- ✅ SQL Server Express: GRATIS
- ✅ ODBC Driver: GRATIS
- ✅ Sistema Legajo Digital: GRATIS

### ¿Qué pasa si algo falla?
1. Ejecuta `python verificar_sistema.py`
2. Lee el archivo `REQUISITOS_SISTEMA.md`
3. Consulta la sección de problemas comunes
4. Contacta al equipo de soporte

---

## 📋 Checklist Rápido

Antes de instalar, verifica:
- [ ] Tengo Windows 10 o 11
- [ ] Tengo permisos de administrador
- [ ] Tengo al menos 10 GB libres
- [ ] Tengo conexión a internet

Durante la instalación:
- [ ] Instalé Python (con "Add to PATH")
- [ ] Instalé SQL Server Express
- [ ] Instalé ODBC Driver 17
- [ ] Ejecuté INSTALAR.bat

Después de instalar:
- [ ] Ejecuté crear_admin.py
- [ ] Ejecuté verificar_sistema.py
- [ ] Puedo acceder a http://localhost:5001

---

## ✅ Resumen

**SÍ, puedes instalar el sistema en cualquier PC con Windows 10** siguiendo estos pasos:

1. **Instalar requisitos** (Python, SQL Server, ODBC Driver) - Una sola vez
2. **Ejecutar INSTALAR.bat** - Configura todo automáticamente
3. **Crear usuario admin** - Con crear_admin.py
4. **¡Usar el sistema!** - Acceder a http://localhost:5001

**Tiempo total: ~30 minutos**  
**Costo: $0 (todo es gratis)**  
**Dificultad: Fácil (instalador automático)**

---

**¿Listo para instalar? ¡Comienza con el Paso 1!** 🚀
