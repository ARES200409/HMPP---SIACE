document.addEventListener('DOMContentLoaded', function() {
    console.log("✅ Script externo cargado correctamente");

    // 1. Obtener Token y URL base desde los inputs ocultos que pondremos en el HTML
    const tokenInput = document.getElementById('csrf_token_hmpp');
    const token = tokenInput ? tokenInput.value : '';
    
    // Obtenemos la URL base desde un atributo data o input oculto
    const urlInput = document.getElementById('url_reset_base');
    const urlResetBase = urlInput ? urlInput.value.slice(0, -1) : ''; // Quitamos el '0' del final

    // =========================================================
    // DELEGACIÓN DE EVENTOS
    // =========================================================
    document.body.addEventListener('click', function(e) {
        
        const btnReset = e.target.closest('.btn-reset-hmpp');
        
        if (btnReset) {
            e.preventDefault();
            console.log("🔑 Clic en reset detectado");

            const id = btnReset.dataset.id;
            const user = btnReset.dataset.nombre;

            Swal.fire({
                title: '¿Restablecer Contraseña?',
                html: `La contraseña del usuario <b>${user}</b> volverá a ser su DNI.<br><br><span class="text-danger small fw-bold">Esta acción es irreversible.</span>`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, resetear',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    mostrarCargando();
                    
                    fetch(urlResetBase + id, {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json', 
                            'X-CSRFToken': token 
                        }
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            Swal.fire({ icon: 'success', title: '¡Éxito!', text: data.message, timer: 2000, showConfirmButton: false });
                        } else {
                            Swal.fire('Error', data.message, 'error');
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire('Error', 'Fallo de conexión.', 'error');
                    });
                }
            });
        }
    });

    function mostrarCargando() {
        Swal.fire({
            title: 'Procesando...',
            allowOutsideClick: false,
            didOpen: () => Swal.showLoading()
        });
    }
});