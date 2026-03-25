// RUTA: app/presentation/static/js/ver-legajo-handlers.js
// Scripts específicos para la página de ver_legajo_completo.html

function setupFormSubmit() {
    console.log('[DEBUG] setupFormSubmit() REGISTRANDO evento submit');
    const formCargarPDF = document.getElementById('formCargarPDF');
    
    if (!formCargarPDF) {
        console.error('[DEBUG] formCargarPDF no encontrado en esta vista.');
        return;
    }

    // REMOVER listeners anteriores clonando el nodo (Previene envíos duplicados)
    const newForm = formCargarPDF.cloneNode(true);
    formCargarPDF.parentNode.replaceChild(newForm, formCargarPDF);

    // Registrar nuevo listener en el formulario limpio
    newForm.addEventListener('submit', function (e) {
        console.log('[DEBUG] ===== EVENTO SUBMIT CAPTURADO =====');
        const estructuraJson = document.getElementById('estructura_json');

        // 1. Validar que el campo oculto exista en el HTML
        if (!estructuraJson) {
            console.error('[DEBUG] Elemento input#estructura_json no encontrado.');
            alert('Error técnico: No se encontró el campo de estructura.');
            e.preventDefault();
            return;
        }

        // 2. Validar que la variable de memoria del otro archivo JS esté lista
        if (typeof ESTRUCTURA_DEFAULT === 'undefined') {
            console.error('[DEBUG] ESTRUCTURA_DEFAULT no está definida');
            alert('Error: Estructura no cargada. Por favor, recarga la página.');
            e.preventDefault();
            return;
        }

        // 3. Serializar la estructura actual (Transformar a Texto)
        const estructuraSerializada = JSON.stringify(ESTRUCTURA_DEFAULT);

        console.log('[DEBUG] Estado de ESTRUCTURA_DEFAULT:');
        console.log('[DEBUG]   Total de Bloques:', Object.keys(ESTRUCTURA_DEFAULT).length);
        
        // Mostrar cada sección para auditoría en consola
        Object.entries(ESTRUCTURA_DEFAULT).forEach(([key, val]) => {
            console.log(`[DEBUG]   Fila ${key}: id_seccion=${val.id_seccion}, tipo=${val.tipo_documento}`);
        });

        // 4. Evitar enviar si el usuario borró todas las filas
        if (!estructuraSerializada || estructuraSerializada === '{}' || Object.keys(ESTRUCTURA_DEFAULT).length === 0) {
            console.error('[DEBUG] ESTRUCTURA_DEFAULT está vacía');
            alert('Error: La estructura está vacía. Debes definir al menos un bloque para dividir el PDF.');
            e.preventDefault();
            return;
        }

        // 5. 🚀 INYECCIÓN FINAL AL INPUT OCULTO
        // Esto es lo que Flask leerá en request.form.get('estructura_json')
        estructuraJson.value = estructuraSerializada;
        
        console.log('[DEBUG] Campo estructura_json ACTUALIZADO JUSTO AHORA');
        // 🐛 ¡AQUÍ ESTABA EL TYPO! Corregido a "estructuraJson" con "c"
        console.log('[DEBUG] Valor final a enviar:', estructuraJson.value.substring(0, 150) + '...');
        
        // 6. 🛡️ BLOQUEO DE BOTÓN (UX)
        // Evita que el usuario haga clic 5 veces mientras el archivo pesado sube al servidor
        const btnSubmit = newForm.querySelector('button[type="submit"]');
        if (btnSubmit) {
            btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Subiendo y Procesando PDF...';
            btnSubmit.classList.add('disabled');
            // Nota: No usamos .disabled = true porque algunos navegadores evitan enviar el form si el submit button se desactiva antes del POST real.
            btnSubmit.style.pointerEvents = 'none'; 
        }

        console.log('[DEBUG] ===== ENVIANDO FORMULARIO AL BACKEND AHORA =====');
        // Al no hacer e.preventDefault() aquí abajo, el navegador envía el POST a Flask exitosamente.
    });
}

// Ejecutar de forma segura sin importar cómo cargue la página
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupFormSubmit);
} else {
    setupFormSubmit();
}