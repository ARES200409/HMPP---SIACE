// RUTA: app/presentation/static/js/catalogos-handlers.js
// Scripts para gestión de catálogos (secciones y tipos de documento)

document.addEventListener('DOMContentLoaded', function () {
    // Event listener para botones de eliminar sección
    document.querySelectorAll('.btn-eliminar-seccion').forEach(btn => {
        btn.addEventListener('click', function () {
            const id = this.getAttribute('data-id');
            const nombre = this.getAttribute('data-nombre');

            Swal.fire({
                title: '¿Eliminar sección?',
                html: `¿Está seguro de eliminar la sección <strong>"${nombre}"</strong>?<br><br>` +
                    `<span class="text-danger">⚠️ Si hay documentos asociados a esta sección, la eliminación fallará.</span>`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    const form = document.getElementById('deleteForm');
                    // ✅ CORRECCIÓN: URL correcta según el blueprint '/legajo/catalogos'
                    const baseUrl = window.location.origin + '/legajo/catalogos/secciones/eliminar/';
                    form.action = baseUrl + id;
                    form.submit();
                }
            });
        });
    });

    // Event listener para botones de eliminar tipo de documento
    document.querySelectorAll('.btn-eliminar-tipo').forEach(btn => {
        btn.addEventListener('click', function () {
            const id = this.getAttribute('data-id');
            const nombre = this.getAttribute('data-nombre');

            Swal.fire({
                title: '¿Eliminar tipo de documento?',
                html: `¿Está seguro de eliminar el tipo <strong>"${nombre}"</strong>?<br><br>` +
                    `<span class="text-danger">⚠️ Si hay documentos de este tipo, la eliminación fallará.</span>`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {
                    const form = document.getElementById('deleteForm');
                    // ✅ CORRECCIÓN: URL correcta según el blueprint '/legajo/catalogos'
                    const baseUrl = window.location.origin + '/legajo/catalogos/tipos-documento/eliminar/';
                    form.action = baseUrl + id;
                    form.submit();
                }
            });
        });
    });
});
