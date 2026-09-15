/**
 * SIACE-IA Chatbot Widget
 * Sistema de chat con Google Gemini Flash
 * Honorable Municipalidad Provincial de Pasco (HMPP)
 */
(function () {
    'use strict';

    // ----------------------------------------------------------------
    // Configuración
    // ----------------------------------------------------------------
    const CHAT_API_URL    = '/api/chat';
    const CLEAR_API_URL   = '/api/chat/limpiar';
    const AVISO_PRIVACIDAD_KEY = 'siace_chat_aviso_visto';

    // ----------------------------------------------------------------
    // Referencias DOM
    // ----------------------------------------------------------------
    const fab        = document.getElementById('siace-chat-fab');
    const chatWindow = document.getElementById('siace-chat-window');
    const messages   = document.getElementById('siace-chat-messages');
    const input      = document.getElementById('siace-chat-input');
    const sendBtn    = document.getElementById('siace-chat-send');
    const clearBtn   = document.getElementById('siace-chat-clear');
    const privacyBar = document.getElementById('siace-privacy-notice');

    if (!fab || !chatWindow) return; // Seguridad: no está en la página

    // Obtener CSRF token del meta-tag
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // ----------------------------------------------------------------
    // Estado del widget
    // ----------------------------------------------------------------
    let isOpen    = false;
    let isLoading = false;

    // ----------------------------------------------------------------
    // Abrir / cerrar
    // ----------------------------------------------------------------
    fab.addEventListener('click', toggleChat);

    function toggleChat() {
        isOpen = !isOpen;
        fab.classList.toggle('open', isOpen);
        chatWindow.classList.toggle('visible', isOpen);

        if (isOpen) {
            // Mostrar aviso de privacidad la primera vez
            if (!localStorage.getItem(AVISO_PRIVACIDAD_KEY)) {
                privacyBar && (privacyBar.style.display = 'flex');
            } else {
                privacyBar && (privacyBar.style.display = 'none');
            }

            // Mensaje de bienvenida si el chat está vacío
            if (messages.children.length === 0) {
                appendBotMessage(
                    '¡Hola! 👋 Soy **SIACE-IA**, el asistente inteligente del sistema. ' +
                    '¿En qué puedo ayudarte hoy?\n\n' +
                    'Puedes preguntarme sobre:\n' +
                    '• Cómo usar el sistema\n' +
                    '• Legajos y documentos\n' +
                    '• Planillas y cálculos\n' +
                    '• Trámites y solicitudes'
                );
                // Marcar aviso como visto
                localStorage.setItem(AVISO_PRIVACIDAD_KEY, '1');
            }

            setTimeout(() => input && input.focus(), 300);
            scrollToBottom();
        }
    }

    // ----------------------------------------------------------------
    // Limpiar historial
    // ----------------------------------------------------------------
    clearBtn && clearBtn.addEventListener('click', async () => {
        try {
            await fetch(CLEAR_API_URL, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });
        } catch (_) {}

        messages.innerHTML = '';
        localStorage.removeItem(AVISO_PRIVACIDAD_KEY);
        appendBotMessage(
            '🗑️ Historial borrado. ¿En qué más puedo ayudarte?'
        );
    });

    // ----------------------------------------------------------------
    // Envío de mensajes
    // ----------------------------------------------------------------
    sendBtn && sendBtn.addEventListener('click', enviarMensaje);

    input && input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            enviarMensaje();
        }
    });

    // Auto-resize del textarea
    input && input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 90) + 'px';
    });

    async function enviarMensaje() {
        if (isLoading) return;
        const texto = input ? input.value.trim() : '';
        if (!texto) return;

        // Mostrar burbuja del usuario
        appendUserMessage(texto);
        input.value = '';
        input.style.height = 'auto';

        // Indicador de escritura
        const typingEl = appendTyping();
        isLoading = true;
        sendBtn && (sendBtn.disabled = true);

        try {
            const res = await fetch(CHAT_API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({ mensaje: texto }),
            });

            typingEl && typingEl.remove();

            if (!res.ok) {
                if (res.status === 401) {
                    appendBotMessage(
                        '⚠️ Tu sesión ha expirado. Por favor, **recarga la página** e inicia sesión nuevamente.',
                        true
                    );
                } else {
                    appendBotMessage(
                        '⚠️ Ocurrió un error al conectar con el asistente. Inténtalo de nuevo.',
                        true
                    );
                }
                return;
            }

            const data = await res.json();

            if (data.error) {
                appendBotMessage('⚠️ ' + (data.respuesta || 'Error desconocido.'), true);
            } else {
                appendBotMessage(data.respuesta, data.bloqueado);
            }

        } catch (err) {
            typingEl && typingEl.remove();
            appendBotMessage(
                '⚠️ No se pudo conectar con el asistente. Verifica tu conexión.',
                true
            );
        } finally {
            isLoading = false;
            sendBtn && (sendBtn.disabled = false);
            input && input.focus();
        }
    }

    // ----------------------------------------------------------------
    // Renderizado de burbujas
    // ----------------------------------------------------------------
    function appendUserMessage(text) {
        const wrap = document.createElement('div');
        wrap.style.display = 'flex';
        wrap.style.flexDirection = 'column';
        wrap.style.alignItems = 'flex-end';

        const label = document.createElement('div');
        label.className = 'chat-bubble-label';
        label.style.textAlign = 'right';
        label.style.color = '#64748b';
        label.textContent = 'Tú';

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble user';
        bubble.textContent = text;

        wrap.appendChild(label);
        wrap.appendChild(bubble);
        messages.appendChild(wrap);
        scrollToBottom();
    }

    function appendBotMessage(text, isBlocked = false) {
        const wrap = document.createElement('div');
        wrap.style.display = 'flex';
        wrap.style.flexDirection = 'column';
        wrap.style.alignItems = 'flex-start';

        const label = document.createElement('div');
        label.className = 'chat-bubble-label';
        label.style.color = '#1a4f8a';
        label.textContent = 'SIACE-IA';

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble bot' + (isBlocked ? ' blocked' : '');
        bubble.innerHTML = renderMarkdown(text);

        wrap.appendChild(label);
        wrap.appendChild(bubble);
        messages.appendChild(wrap);
        scrollToBottom();
        return wrap;
    }

    function appendTyping() {
        const typing = document.createElement('div');
        typing.className = 'chat-typing';
        typing.innerHTML = '<span></span><span></span><span></span>';
        messages.appendChild(typing);
        scrollToBottom();
        return typing;
    }

    // ----------------------------------------------------------------
    // Markdown básico (negrita, cursiva, código, saltos de línea)
    // ----------------------------------------------------------------
    function renderMarkdown(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`(.+?)`/g, '<code>$1</code>')
            .replace(/\n•/g, '<br>•')
            .replace(/\n/g, '<br>');
    }

    // ----------------------------------------------------------------
    // Scroll al fondo
    // ----------------------------------------------------------------
    function scrollToBottom() {
        setTimeout(() => {
            messages && (messages.scrollTop = messages.scrollHeight);
        }, 50);
    }

})();
