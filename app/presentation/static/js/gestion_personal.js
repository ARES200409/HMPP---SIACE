document.addEventListener('DOMContentLoaded', function() {
    const botonesEstado = document.querySelectorAll('.btn-cambiar-estado');
    const csrfToken = document.getElementById('csrf_token').value;

    botonesEstado.forEach(boton => {
        boton.addEventListener('click', function() {
            const personalId = this.getAttribute('data-id');
            const nuevoEstado = this.getAttribute('data-estado');
            const nombre = this.getAttribute('data-nombre');
            
            // Personalizamos los colores: Azul HMPP (#3b699b) y Rojo Peligro (#d33)
            const esActivacion = nuevoEstado === "1";
            const titulo = esActivacion ? '¿Confirmar Activación?' : '¿Confirmar Desactivación?';
            const colorBoton = esActivacion ? '#28a745' : '#d33';

            Swal.fire({
                title: `<span style="color: #3b699b">${titulo}</span>`,
                text: `¿Está seguro de que desea ${esActivacion ? 'ACTIVAR' : 'DESACTIVAR'} el estado laboral de ${nombre}?`,
                icon: esActivacion ? 'info' : 'warning',
                showCancelButton: true,
                confirmButtonColor: colorBoton,
                cancelButtonColor: '#6c757d',
                confirmButtonText: esActivacion ? 'Sí, activar' : 'Sí, desactivar',
                cancelButtonText: 'Cancelar',
                reverseButtons: true
            }).then((result) => {
                if (result.isConfirmed) {
                    // Si el usuario acepta, procedemos con el Fetch
                    procesarCambioEstado(personalId, nuevoEstado, csrfToken);
                }
            });
        });
    });
});

function procesarCambioEstado(id, estado, token) {
    fetch(`/rrhh/personal/cambiar_estado/${id}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': token
        },
        body: JSON.stringify({ estado: parseInt(estado) })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: 'Actualizado',
                text: 'El estado se cambió con éxito.',
                showConfirmButton: false,
                timer: 1500
            }).then(() => location.reload());
        } else {
            Swal.fire('Error', data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire('Error Crítico', 'No se pudo conectar con el servidor HMPP.', 'error');
    });
}