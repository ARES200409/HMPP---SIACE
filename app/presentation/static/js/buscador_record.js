/* * ARCHIVO: app/static/js/buscador_record.js
 * Descripción: Generador dinámico de años basado en el tiempo real y registros históricos.
 */

document.addEventListener('DOMContentLoaded', function() {
    const filtroAnio = document.getElementById('filtroAnio');
    const filtroMes = document.getElementById('filtroMes');
    const filas = document.querySelectorAll('.fila-busqueda');

    if (!filtroAnio || !filtroMes) return;

    // =======================================================
    // 1. GENERADOR DINÁMICO DE RANGO DE AÑOS
    // =======================================================
    const aniosUnicos = new Set();
    const anioActual = new Date().getFullYear();
    
    // RANGO FUTURO: Año actual + 10 años (para que nunca caduque)
    const limiteFuturo = anioActual + 10;
    
    // RANGO BASE: Del futuro hasta un pasado razonable (ej: 1940)
    for(let i = limiteFuturo; i >= 1940; i--) {
        aniosUnicos.add(i.toString());
    }

    // RESCATE HISTÓRICO: Buscamos en la tabla años más antiguos que 1940 (ej. 1800, 1720)
    filas.forEach(fila => {
        const anio = fila.getAttribute('data-anio');
        if (anio && anio.trim() !== '') {
            aniosUnicos.add(anio.trim());
        }
    });

    // 🧹 LIMPIEZA Y LLENADO
    filtroAnio.innerHTML = '<option value="">-- Todos los Años --</option>';

    // Convertimos a array, ordenamos numéricamente de mayor a menor y llenamos el select
    const listaOrdenada = Array.from(aniosUnicos).sort((a, b) => b - a);
    
    listaOrdenada.forEach(anio => {
        const opcion = document.createElement('option');
        opcion.value = anio;
        opcion.textContent = anio;
        filtroAnio.appendChild(opcion);
    });


    // =======================================================
    // 2. LÓGICA DE FILTRADO (Diccionario Meses)
    // =======================================================
    const mapaMesesInverso = {
        '01': 'enero', '02': 'febrero', '03': 'marzo', '04': 'abril',
        '05': 'mayo', '06': 'junio', '07': 'julio', '08': 'agosto',
        '09': 'septiembre', '10': 'octubre', '11': 'noviembre', '12': 'diciembre'
    };

    function aplicarFiltros() {
        const anioBuscado = filtroAnio.value; 
        const mesBuscado = filtroMes.value;   

        filas.forEach(fila => {
            const filaAnio = fila.getAttribute('data-anio') || '';
            let filaMes = fila.getAttribute('data-mes') || '';
            
            if (mapaMesesInverso[filaMes]) {
                filaMes = mapaMesesInverso[filaMes];
            }

            const coincideAnio = (anioBuscado === "") || (filaAnio === anioBuscado);
            const coincideMes = (mesBuscado === "") || (filaMes === mesBuscado);

            if (coincideAnio && coincideMes) {
                fila.style.display = '';
            } else {
                fila.style.display = 'none';
            }
        });
    }

    filtroAnio.addEventListener('change', aplicarFiltros);
    filtroMes.addEventListener('change', aplicarFiltros);
});