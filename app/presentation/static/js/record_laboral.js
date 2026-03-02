document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('btnGenerarReporteFinal');
    
    if (btn) {
        btn.addEventListener('click', async function() {
            const dropdown = document.getElementById('inputAnioReporte');
            const anio = dropdown.value;
            
            // ✅ VALIDACIÓN "BONITA" CON SWEETALERT2
            if (!anio) {
                Swal.fire({
                    title: '¡Falta el año!',
                    text: 'Por favor, selecciona un año de la lista para poder generar el récord.',
                    icon: 'warning',
                    confirmButtonColor: '#335a9a', // Color azul de tu sistema
                    confirmButtonText: 'Entendido',
                    background: '#ffffff',
                    backdrop: `rgba(0, 0, 0, 0.4)`
                });
                return;
            }

            const urlBase = btn.getAttribute('data-url-base');
            const urlFinal = urlBase.replace('99999', anio);
            
            // Estado de carga visual en el botón
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Verificando...';
            btn.disabled = true;

            try {
                // ✅ PASO 1: Verificación silenciosa (para no gastar el Flash de Python)
                const checkRes = await fetch(`${urlFinal}?check=1`);

                if (checkRes.ok) {
                    // ✅ PASO 2: Si hay datos, abrimos en PESTAÑA NUEVA tal como pediste
                    window.open(urlFinal, '_blank');
                    
                    // Recargamos la tabla de abajo tras un momento para que aparezca el nuevo PDF
                    setTimeout(() => window.location.reload(), 2000);
                } else {
                    // ❌ PASO 3: Si NO hay datos, redirigimos la ventana principal
                    // Esto hace que Python ejecute el FLASH y el REDIRECT en tu App
                    window.location.href = urlFinal;
                }
            } catch (error) {
                console.error("Error al verificar datos:", error);
                window.location.href = urlFinal;
            } finally {
                // Restauramos el botón
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        });
    }
});