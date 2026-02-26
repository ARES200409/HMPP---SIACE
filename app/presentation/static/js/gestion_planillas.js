/* * ARCHIVO: app/static/js/gestion_planillas.js
 * Descripción: Maneja filtros, alertas y AHORA pide contraseña para desbloqueos.
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log("✅ Gestor de Planillas: Cargado con seguridad.");

    // =========================================================
    // 1. LÓGICA DE FILTRADO (BUSCADOR)
    // =========================================================
    const inputFecha = document.getElementById('filtroFecha');
    const inputTipo = document.getElementById('filtroTipo');
    const btnBuscar = document.getElementById('btnBuscar');
    const btnLimpiar = document.getElementById('btnLimpiar');
    const filas = document.querySelectorAll('.fila-planilla');
    const contador = document.getElementById('contadorFilas');
    const msgVacio = document.getElementById('mensajeSinResultados');

    function aplicarFiltros() {
        const fechaBuscada = inputFecha ? inputFecha.value : ""; 
        const tipoBuscado = inputTipo ? inputTipo.value : "";   
        let visibles = 0;

        filas.forEach(fila => {
            const fechaFila = fila.getAttribute('data-fecha');
            const tipoFila = fila.getAttribute('data-tipo');
            
            const coincideFecha = (fechaBuscada === "") || (fechaFila === fechaBuscada);
            const coincideTipo = (tipoBuscado === "") || (tipoFila === tipoBuscado);

            if (coincideFecha && coincideTipo) {
                fila.style.display = ""; 
                visibles++;
            } else {
                fila.style.display = "none"; 
            }
        });

        if (contador) contador.innerText = "Mostrando: " + visibles;
        if (msgVacio) msgVacio.style.display = (visibles === 0) ? "block" : "none";
    }

    function limpiarFiltros() {
        if (inputFecha) inputFecha.value = "";
        if (inputTipo) inputTipo.value = "";
        aplicarFiltros();
    }

    if(btnBuscar) btnBuscar.addEventListener('click', aplicarFiltros);
    if(btnLimpiar) btnLimpiar.addEventListener('click', limpiarFiltros);


    // =========================================================
    // 2. LÓGICA DE ALERTAS Y SEGURIDAD (SWEETALERT2)
    // =========================================================

    document.body.addEventListener('submit', function(e) {
        
        // A) ELIMINAR (Rojo)
        if (e.target.classList.contains('form-eliminar-alerta')) {
            e.preventDefault();
            const form = e.target;

            Swal.fire({
                title: '¿Estás seguro?',
                text: "¡Se borrarán todos los datos! No hay vuelta atrás.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: '<i class="bi bi-trash-fill"></i> Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) form.submit();
            });
        }

        // B) CERRAR PLANILLA (Negro)
        if (e.target.classList.contains('form-cerrar-alerta')) {
            e.preventDefault();
            const form = e.target;

            Swal.fire({
                title: '¿Cerrar Planilla?',
                text: "Se bloqueará la edición para proteger los datos.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#343a40',
                cancelButtonColor: '#6c757d',
                confirmButtonText: '<i class="bi bi-lock-fill"></i> Sí, cerrar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) form.submit();
            });
        }

        // C) RE-ABRIR PLANILLA (CON CONTRASEÑA DE SEGURIDAD)
        if (e.target.classList.contains('form-abrir-alerta')) {
            e.preventDefault();
            const form = e.target;

            Swal.fire({
                title: '🔒 Autorización Requerida',
                html: 'Esta planilla está cerrada por seguridad.<br>Ingrese la <b>Clave de Escalafón</b> para desbloquearla:',
                input: 'password', // <--- ESTO PONE EL CAMPO DE CONTRASEÑA
                inputAttributes: {
                    autocapitalize: 'off',
                    placeholder: 'Ingrese clave de autorización'
                },
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#ffc107',
                cancelButtonColor: '#6c757d',
                confirmButtonText: '<i class="bi bi-unlock-fill"></i> Desbloquear',
                cancelButtonText: 'Cancelar',
                customClass: { confirmButton: 'text-dark fw-bold' },
                preConfirm: (clave) => {
                    if (!clave) {
                        Swal.showValidationMessage('⚠️ Debe ingresar la clave para continuar');
                    }
                    return clave;
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    // Si el usuario puso una clave, la inyectamos en el formulario
                    // Creamos un input oculto al vuelo
                    const inputHidden = document.createElement('input');
                    inputHidden.type = 'hidden';
                    inputHidden.name = 'clave_seguridad'; // Este nombre debe coincidir con Python
                    inputHidden.value = result.value;
                    form.appendChild(inputHidden);
                    
                    // Enviamos el formulario con la clave dentro
                    form.submit();
                }
            });
        }
    });
});