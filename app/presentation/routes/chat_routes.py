# app/presentation/routes/chat_routes.py
# Blueprint del chatbot IA — SIACE HMPP
# Protegido por autenticación y rate limiting

from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
from app import limiter

chat_bp = Blueprint('chat', __name__, url_prefix='/api')


@chat_bp.route('/chat', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def chat():
    """
    Endpoint del chatbot IA.
    - Solo accesible con sesión activa (login_required).
    - Rate limiting: máx. 30 mensajes/minuto por IP.
    - El rol se toma del servidor (current_user), nunca del frontend.
    """
    ai_service = None
    try:
        from flask import current_app
        ai_service = current_app.config.get('AI_SERVICE')
    except Exception:
        pass

    if not ai_service or not ai_service.esta_disponible():
        return jsonify({
            'respuesta': 'El servicio de IA no está disponible en este momento.',
            'error': True
        }), 503

    data = request.get_json(silent=True)
    if not data or not data.get('mensaje'):
        return jsonify({'respuesta': 'Mensaje vacío.', 'error': True}), 400

    mensaje = str(data.get('mensaje', '')).strip()[:1000]  # Limitar a 1000 chars

    # --- CONTEXTO DEL USUARIO (desde el servidor, no del frontend) ---
    contexto_usuario = {
        'rol': current_user.rol if hasattr(current_user, 'rol') else 'Personal',
        'nombre': current_user.nombre_completo if hasattr(current_user, 'nombre_completo') else '',
        'username': current_user.username,
        'id_personal': current_user.id_personal if hasattr(current_user, 'id_personal') else None,
    }

    # Historial de la sesión actual
    historial = session.get('chat_historial', [])

    resultado = ai_service.chat(
        mensaje_usuario=mensaje,
        historial=historial,
        contexto_usuario=contexto_usuario,
    )

    # Guardar historial actualizado en la sesión
    session['chat_historial'] = resultado.get('historial', historial)
    session.modified = True

    return jsonify({
        'respuesta': resultado.get('respuesta', ''),
        'bloqueado': resultado.get('bloqueado', False),
        'error': False,
    })


@chat_bp.route('/chat/limpiar', methods=['POST'])
@login_required
def limpiar_historial():
    """Limpia el historial de conversación de la sesión actual."""
    session.pop('chat_historial', None)
    session.modified = True
    return jsonify({'ok': True})
