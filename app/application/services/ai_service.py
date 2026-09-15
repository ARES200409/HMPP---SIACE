# app/application/services/ai_service.py
# Servicio de IA con Google Gemini Flash
# Cumple con la Ley N° 29733 - Ley de Protección de Datos Personales del Perú
# Control de acceso basado en roles (RBAC)

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# SYSTEM PROMPTS POR ROL (Principio de proporcionalidad - Art. 10°)
# ------------------------------------------------------------------

_CONTEXTO_BASE = """
Eres SIACE-IA, el asistente inteligente del Sistema Integral de Administración
de Contratos y Escalafón (SIACE) de la Honorable Municipalidad Provincial de
Pasco (HMPP), Perú.

Respondes SIEMPRE en español, de forma clara, profesional y concisa.
Si no sabes algo con certeza, dilo honestamente.
No inventes datos de empleados, fechas ni montos que no se te hayan proporcionado.
"""

_AVISO_LEY_29733 = """
NORMATIVA DE PRIVACIDAD (OBLIGATORIO):
Estás sujeto a la Ley N° 29733 - Ley de Protección de Datos Personales del Perú
y su Reglamento (D.S. 003-2013-JUS).
- Principio de legalidad (Art. 8°): Solo procesas datos con base legal.
- Principio de finalidad (Art. 9°): Solo para soporte institucional del sistema.
- Principio de proporcionalidad (Art. 10°): Solo la información necesaria.
- Principio de seguridad (Art. 11°): No reveles datos sin autorización del rol.
- Principio de confidencialidad (Art. 17°): Discreción absoluta.
"""

SYSTEM_PROMPTS = {
    'Personal': f"""
{_CONTEXTO_BASE}

ROL ACTUAL: Personal / Empleado Municipal

PERMISOS:
- Puedes ayudar con preguntas sobre CÓMO usar el sistema SIACE (navegación, funciones).
- Puedes responder preguntas generales del usuario sobre SUS PROPIOS datos si te los comparte.
- Puedes explicar conceptos de planillas, descuentos, días laborales, etc.
- Puedes dar orientación sobre trámites de la HMPP.

RESTRICCIONES ABSOLUTAS (por Ley N° 29733):
- NUNCA proporciones información personal, laboral o salarial de OTROS trabajadores.
- Si alguien pregunta por datos de otra persona (aunque sea un familiar), responde:
  "No puedo proporcionar datos de terceros. Esto está protegido por la Ley N° 29733
  de Protección de Datos Personales del Perú. Si necesitas información de otro
  trabajador, consulta directamente con el área de RRHH."
- NUNCA reveles información del sistema de usuarios, auditoría o backups.
{_AVISO_LEY_29733}
""",

    'RRHH': f"""
{_CONTEXTO_BASE}

ROL ACTUAL: Recursos Humanos (RRHH)

PERMISOS:
- Puedes asistir con consultas de legajos, planillas y datos del personal.
- Puedes ayudar con procesos de contratación, escalafón y gestión de personal.
- Puedes orientar sobre cálculos de días laborales, planillas y boletas.
- Puedes dar información estadística del personal cuando se te consulte.

RESTRICCIONES:
- No tienes acceso ni debes comentar sobre configuraciones del sistema, auditorías
  técnicas, backups o gestión de usuarios del sistema.
- Si preguntan por eso, indica: "Esa área corresponde al módulo de Sistemas."
{_AVISO_LEY_29733}
""",

    'AdministradorLegajos': f"""
{_CONTEXTO_BASE}

ROL ACTUAL: Administrador de Escalafón / Legajos

PERMISOS:
- Puedes asistir con gestión completa de legajos, documentos y escalafón.
- Puedes orientar sobre solicitudes de modificación (ARCO), aprobaciones y flujos.
- Puedes ayudar con planillas históricas, récord laboral y reportes.

RESTRICCIONES:
- No tienes acceso ni debes comentar sobre gestión de usuarios del sistema,
  auditorías técnicas ni backups.
{_AVISO_LEY_29733}
""",

    'Sistemas': f"""
{_CONTEXTO_BASE}

ROL ACTUAL: Administrador de Sistemas (acceso completo)

PERMISOS TOTALES:
- Puedes asistir con cualquier aspecto del sistema SIACE.
- Gestión de usuarios, auditoría, backups, monitoreo del servidor.
- Diagnóstico técnico, errores del sistema y configuración.
- Soporte a todos los módulos: RRHH, Legajos, Personal.
{_AVISO_LEY_29733}
""",
}

# Prompt por defecto si el rol no está en el mapa
SYSTEM_PROMPTS['default'] = SYSTEM_PROMPTS['Personal']


# ------------------------------------------------------------------
# PALABRAS CLAVE BLOQUEADAS POR ROL (Sanitización de prompt)
# ------------------------------------------------------------------

# Patrones que el rol Personal NO puede consultar sobre terceros
_PATRONES_BLOQUEADOS_PERSONAL = [
    'legajo de ', 'planilla de ', 'sueldo de ', 'salario de ',
    'contrato de ', 'dni de ', 'datos de ', 'información de ',
    'trabajador ', 'empleado ', 'compañero ', 'colega ',
]


def _sanitizar_mensaje(mensaje: str, rol: str, nombre_usuario: str) -> tuple[bool, str]:
    """
    Verifica si el mensaje intenta saltarse las restricciones del rol.
    Retorna (bloqueado: bool, razon: str)
    """
    if rol != 'Personal':
        return False, ""

    mensaje_lower = mensaje.lower()
    for patron in _PATRONES_BLOQUEADOS_PERSONAL:
        if patron in mensaje_lower:
            # Verificar si se refiere a sí mismo (permitido)
            nombre_lower = nombre_usuario.lower() if nombre_usuario else ""
            if nombre_lower and nombre_lower in mensaje_lower:
                continue  # Se refiere a sí mismo, permitido
            return True, (
                "Detecté que estás preguntando por información de otra persona. "
                "Según la **Ley N° 29733 de Protección de Datos Personales del Perú**, "
                "no puedo proporcionar esa información. "
                "Si necesitas datos de otro trabajador, acércate al área de **RRHH**."
            )
    return False, ""


# ------------------------------------------------------------------
# CLASE PRINCIPAL DEL SERVICIO
# ------------------------------------------------------------------

class GeminiAIService:
    """
    Servicio de IA basado en Google Gemini Flash.
    Implementa control de acceso por roles (RBAC) y cumple
    con la Ley N° 29733 de Protección de Datos Personales del Perú.
    """

    def __init__(self, api_key: str):
        try:
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=api_key)
            self._types = types
            self._disponible = True
            logger.info("GeminiAIService inicializado correctamente (google.genai).")
        except Exception as e:
            logger.error(f"Error al inicializar GeminiAIService: {e}")
            self._disponible = False

    def esta_disponible(self) -> bool:
        return self._disponible

    def chat(self, mensaje_usuario: str, historial: list, contexto_usuario: dict) -> dict:
        """
        Envía un mensaje a Gemini y retorna la respuesta.

        Args:
            mensaje_usuario: Texto enviado por el usuario.
            historial: Lista de turnos anteriores [{'role': 'user'/'model', 'parts': [str]}]
            contexto_usuario: Dict con {rol, nombre, username, id_personal}

        Returns:
            Dict con {respuesta, historial_actualizado, bloqueado}
        """
        if not self._disponible:
            return {
                'respuesta': 'El servicio de IA no está disponible en este momento.',
                'historial': historial,
                'bloqueado': False,
            }

        rol = contexto_usuario.get('rol', 'Personal')
        nombre = contexto_usuario.get('nombre', contexto_usuario.get('username', ''))

        # --- NIVEL 1: Sanitización del mensaje ---
        bloqueado, razon_bloqueo = _sanitizar_mensaje(mensaje_usuario, rol, nombre)
        if bloqueado:
            logger.warning(
                f"[CHAT-BLOQUEADO] Usuario={contexto_usuario.get('username')} "
                f"Rol={rol} Mensaje='{mensaje_usuario[:80]}'"
            )
            return {
                'respuesta': razon_bloqueo,
                'historial': historial,
                'bloqueado': True,
            }

        # --- NIVEL 2: System prompt dinámico por rol ---
        system_prompt = SYSTEM_PROMPTS.get(rol, SYSTEM_PROMPTS['default'])

        # Enriquecer el prompt con el contexto del usuario actual
        contexto_personalizado = (
            f"\nCONTEXTO DEL USUARIO ACTUAL: "
            f"Nombre: {nombre}, "
            f"Usuario: {contexto_usuario.get('username', 'N/A')}, "
            f"Rol: {rol}."
        )
        system_prompt_completo = system_prompt + contexto_personalizado

        try:
            from google.genai import types

            # Construir el historial para la API nueva
            contents = []
            for turno in historial[-8:]:
                role = turno['role']  # 'user' o 'model'
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=turno['content'])]
                    )
                )

            # Añadir el mensaje actual del usuario
            contents.append(
                types.Content(
                    role='user',
                    parts=[types.Part(text=mensaje_usuario)]
                )
            )

            response = self._client.models.generate_content(
                model='gemini-2.0-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt_completo,
                    temperature=0.7,
                    max_output_tokens=1024,
                ),
            )
            respuesta_texto = response.text

            # --- NIVEL 3: Auditoría de la conversación ---
            logger.info(
                f"[CHAT-IA] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Usuario={contexto_usuario.get('username')} | Rol={rol} | "
                f"Pregunta='{mensaje_usuario[:60]}...'"
            )

            # Actualizar historial
            historial_actualizado = list(historial)
            historial_actualizado.append({'role': 'user', 'content': mensaje_usuario})
            historial_actualizado.append({'role': 'model', 'content': respuesta_texto})

            # Limitar historial a 20 turnos (10 intercambios)
            if len(historial_actualizado) > 20:
                historial_actualizado = historial_actualizado[-20:]

            return {
                'respuesta': respuesta_texto,
                'historial': historial_actualizado,
                'bloqueado': False,
            }

        except Exception as e:
            logger.error(f"Error en Gemini API: {e}")
            return {
                'respuesta': (
                    'Ocurrió un error al procesar tu consulta. '
                    'Por favor, intenta de nuevo en unos momentos.'
                ),
                'historial': historial,
                'bloqueado': False,
            }
