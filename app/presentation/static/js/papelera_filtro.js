document.addEventListener('DOMContentLoaded', function() {
    const btnBuscar = document.getElementById('btn_buscar_hmpp');
    const btnLimpiar = document.getElementById('btn_limpiar_hmpp');
    const inputBusqueda = document.getElementById('input_hmpp');
    const labelTotal = document.getElementById('label_total'); 
    const tabla = document.querySelector('.table tbody');

    function realizarFiltrado() {
        const termino = inputBusqueda.value.toLowerCase().trim();
        const filas = tabla.querySelectorAll('tr');
        let contador = 0;

        filas.forEach(fila => {
            const contenido = fila.textContent.toLowerCase();
            if (contenido.includes(termino)) {
                fila.style.display = '';
                contador++;
            } else {
                fila.style.display = 'none';
            }
        });

        if (labelTotal) labelTotal.textContent = contador;
    }

    // Escuchadores de eventos (sin usar onclick en el HTML)
    if (btnBuscar) btnBuscar.addEventListener('click', realizarFiltrado);
    
    if (inputBusqueda) {
        inputBusqueda.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') realizarFiltrado();
        });
    }

    if (btnLimpiar) {
        btnLimpiar.addEventListener('click', function() {
            inputBusqueda.value = '';
            realizarFiltrado();
        });
    }
});