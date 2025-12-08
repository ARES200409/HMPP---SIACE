// RUTA: app/presentation/static/js/ver-legajo-handlers.js
// Scripts específicos para la página de ver_legajo_completo.html

// Función para configurar el submit del formulario de carga de PDF
function setupFormSubmit() {
    console.log('[DEBUG] setupFormSubmit() REGISTRANDO evento submit');
    const formCargarPDF = document.getElementById('formCargarPDF');
    if (!formCargarPDF) {
        console.error('[DEBUG] formCargarPDF no encontrado');
        return;
    }

    // REMOVER listeners anteriores para evitar duplicados
    const newForm = formCargarPDF.cloneNode(true);
    formCargarPDF.parentNode.replaceChild(newForm, formCargarPDF);

    // Registrar nuevo listener
    newForm.addEventListener('submit', function (e) {
        console.log('[DEBUG] ===== EVENTO SUBMIT CAPTURADO =====');
        const estructuraJson = document.getElementById('estructura_json');

        console.log('[DEBUG] typeof ESTRUCTURA_DEFAULT:', typeof ESTRUCTURA_DEFAULT);
        if (typeof ESTRUCTURA_DEFAULT === 'undefined') {
            console.error('[DEBUG] ESTRUCTURA_DEFAULT no está definida');
            alert('Error: Estructura no cargada. Por favor, recarga la página.');
            e.preventDefault();
            return;
        }

        // SIEMPRE serializar ESTRUCTURA_DEFAULT actual, no confiar en valor previo
        const estructuraSerializada = JSON.stringify(ESTRUCTURA_DEFAULT);

        console.log('[DEBUG] Estado de ESTRUCTURA_DEFAULT:');
        console.log('[DEBUG]   Elementos:', Object.keys(ESTRUCTURA_DEFAULT));
        console.log('[DEBUG]   JSON completo:', estructuraSerializada);
        console.log('[DEBUG]   Tamaño:', estructuraSerializada.length, 'bytes');

        // Mostrar cada sección y su id_seccion
        Object.entries(ESTRUCTURA_DEFAULT).forEach(([key, val]) => {
            console.log(`[DEBUG]   ${key}: id_seccion=${val.id_seccion}`);
        });

        if (!estructuraSerializada || estructuraSerializada === '{}') {
            console.error('[DEBUG] ESTRUCTURA_DEFAULT está vacía o inválida');
            alert('Error: La estructura está vacía');
            e.preventDefault();
            return;
        }

        // ACTUALIZAR el campo JUSTO ANTES de enviar
        estructuraJson.value = estructuraSerializada;
        console.log('[DEBUG] Campo estructura_json ACTUALIZADO JUSTO AHORA');
        console.log('[DEBUG] Valor final a enviar:', estruturaJson.value.substring(0, 100) + '...');
        console.log('[DEBUG] ===== ENVIANDO FORMULARIO AHORA =====');
        // Permitir que el formulario se envíe normalmente
    });
}

// Ejecutar después de que todo se haya cargado
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupFormSubmit);
} else {
    setupFormSubmit();
}
