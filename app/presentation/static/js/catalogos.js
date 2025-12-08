document.addEventListener('DOMContentLoaded', function() {
    console.log('Script de gestión de catálogos iniciado');

    // ==========================================
    // GESTIÓN DE SECCIONES EN TIPOS DE DOCUMENTO
    // ==========================================
    
    const formAgregar = document.getElementById('formAgregarSeccion');
    if (formAgregar) {
        console.log('Formulario de agregar sección encontrado');
        formAgregar.addEventListener('submit', function(event) {
            event.preventDefault();
            console.log('Intento de agregar sección');
            
            const selectSeccion = document.getElementById('selectSeccion');
            const idSeccion = selectSeccion.value;
            const idTipo = this.getAttribute('data-id-tipo');
            const csrfToken = this.querySelector('input[name="csrf_token"]').value;
            
            if (!idSeccion) {
                Swal.fire('Error', 'Debe seleccionar una sección', 'error');
                return;
            }
            
            // Mostrar loading
            Swal.fire({
                title: 'Procesando...',
                text: 'Agregando sección al tipo de documento',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
            // Crear FormData con CSRF token
            const formData = new FormData();
            formData.append('id_seccion', idSeccion);
            formData.append('csrf_token', csrfToken);
            
            fetch(`/legajo/catalogos/api/tipos-documento/${idTipo}/agregar-seccion`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('Respuesta recibida:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Datos:', data);
                if (data.success) {
                    Swal.fire('Éxito', data.message, 'success').then(() => {
                        location.reload();
                    });
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            })
            .catch(error => {
                console.error('Error en fetch:', error);
                Swal.fire('Error', 'Ocurrió un error al agregar la sección: ' + error, 'error');
            });
        });
    }

    // Manejar botones de remover sección
    document.querySelectorAll('.btn-remover-seccion').forEach(button => {
        button.addEventListener('click', function() {
            const idTipo = this.getAttribute('data-id-tipo');
            const idSeccion = this.getAttribute('data-id-seccion');
            const nombreSeccion = this.getAttribute('data-nombre-seccion');
            // Necesitamos obtener el token CSRF de algún lugar. 
            // Lo buscaremos en el formulario de agregar sección que sabemos que está en la página
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            
            Swal.fire({
                title: '¿Remover asociación?',
                html: `¿Está seguro de remover la asociación con la sección <strong>"${nombreSeccion}"</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Sí, remover',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    Swal.fire({
                        title: 'Procesando...',
                        allowOutsideClick: false,
                        didOpen: () => { Swal.showLoading(); }
                    });

                    const formData = new FormData();
                    formData.append('csrf_token', csrfToken);
                    
                    fetch(`/legajo/catalogos/api/tipos-documento/${idTipo}/remover-seccion/${idSeccion}`, {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            Swal.fire('Éxito', data.message, 'success').then(() => {
                                location.reload();
                            });
                        } else {
                            Swal.fire('Error', data.message, 'error');
                        }
                    })
                    .catch(error => {
                        Swal.fire('Error', 'Ocurrió un error al remover la asociación', 'error');
                        console.error('Error:', error);
                    });
                }
            });
        });
    });
});
