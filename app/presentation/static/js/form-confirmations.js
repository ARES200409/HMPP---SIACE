// RUTA: app/presentation/static/js/form-confirmations.js
// Scripts para confirmaciones de formularios en diferentes páginas

document.addEventListener('DOMContentLoaded', function () {
    // Confirmación para solicitar cancelación
    const cancelacionForm = document.querySelector('form[action*="solicitar_cancelacion"]');
    if (cancelacionForm) {
        cancelacionForm.addEventListener('submit', function (e) {
            if (!confirm('¿Estás seguro de que deseas solicitar la cancelación de tus datos? Esta acción requiere aprobación.')) {
                e.preventDefault();
            }
        });
    }

    // Confirmación para derecho de oposición
    const oposicionForm = document.querySelector('form[action*="derecho_oposicion"]');
    if (oposicionForm) {
        oposicionForm.addEventListener('submit', function (e) {
            if (!confirm('¿Estás seguro de que deseas ejercer tu derecho de oposición? Esta solicitud será revisada por el administrador.')) {
                e.preventDefault();
            }
        });
    }

    // Confirmación para cambio de documento
    const cambioDocForm = document.querySelector('form[action*="solicitar_cambio_documento"]');
    if (cambioDocForm) {
        cambioDocForm.addEventListener('submit', function (event) {
            const archivo = document.getElementById('documento_nuevo');
            if (!archivo || !archivo.files[0]) {
                event.preventDefault();
                alert('Por favor, selecciona un archivo antes de enviar.');
                return false;
            }

            if (!confirm('¿Confirma que desea solicitar el cambio de este documento?')) {
                event.preventDefault();
            }
        });
    }

    // Confirmación para actualizar datos personales
    const actualizarDatosForm = document.querySelector('form[action*="actualizar_datos"]');
    if (actualizarDatosForm) {
        actualizarDatosForm.addEventListener('submit', function (event) {
            if (!confirm('¿Confirma que desea enviar esta solicitud de actualización de datos?')) {
                event.preventDefault();
            }
        });
    }
});
