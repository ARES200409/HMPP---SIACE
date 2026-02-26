document.addEventListener('DOMContentLoaded', function() {
    console.log("--- Cargando Gráficos RRHH (Externo) ---");

    // Configuración global de fuentes
    if (typeof Chart !== 'undefined') {
        Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    } else {
        console.error("Chart.js no está cargado.");
        return;
    }

    // Función auxiliar para leer los datos JSON del HTML de forma segura
    const getChartData = (id) => {
        const element = document.getElementById(id);
        if (!element) return [];
        try {
            const content = element.textContent;
            return content ? JSON.parse(content) : [];
        } catch (e) {
            console.error(`Error al leer datos de ${id}:`, e);
            return [];
        }
    };

    // --- 1. GRÁFICO DE UNIDAD (FILTRADO) ---
    const rawUnidad = getChartData('data-unidad');
    // Filtramos para mostrar SOLO las oficinas que tienen personal (> 0)
    const dataUnidad = rawUnidad.filter(item => item.cantidad > 0);
    
    console.log("Unidades con personal activo:", dataUnidad);

    if (dataUnidad.length > 0) {
        new Chart(document.getElementById('empleadosUnidadChart'), {
            type: 'doughnut',
            data: {
                labels: dataUnidad.map(d => d.nombre_unidad),
                datasets: [{
                    data: dataUnidad.map(d => d.cantidad),
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', 
                        '#4BC0C0', '#9966FF', '#FF9F40',
                        '#FF6B9D', '#4ECDC4', '#45B7D1'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { 
                        position: 'right', // Leyenda a la derecha para que no aplaste el gráfico
                        labels: { boxWidth: 12, font: { size: 11 } }
                    }
                },
                layout: { padding: 10 }
            }
        });
    } else {
        // Mostrar mensaje si no hay nadie
        document.getElementById('empleadosUnidadChart').style.display = 'none';
        document.getElementById('noDataUnidad').classList.remove('d-none');
        document.getElementById('noDataUnidad').classList.add('d-flex');
    }

    // --- 2. GRÁFICO DE ESTADO ---
    const dataEstado = getChartData('data-estado');
    if (dataEstado.length > 0) {
        new Chart(document.getElementById('chartEstado'), {
            type: 'pie',
            data: {
                labels: dataEstado.map(d => d.estado),
                datasets: [{
                    data: dataEstado.map(d => d.cantidad),
                    backgroundColor: dataEstado.map(d => 
                        (d.estado === 'Activos' || d.estado === 'Activo') ? '#4BC0C0' : '#FF6384'
                    ),
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } }
            }
        });
    } else {
        document.getElementById('chartEstado').style.display = 'none';
        document.getElementById('noDataEstado').classList.remove('d-none');
        document.getElementById('noDataEstado').classList.add('d-flex');
    }

    // --- 3. GRÁFICO DE GÉNERO ---
    const dataSexo = getChartData('data-sexo');
    if (dataSexo.length > 0) {
        new Chart(document.getElementById('chartSexo'), {
            type: 'bar',
            data: {
                labels: dataSexo.map(d => d.sexo),
                datasets: [{
                    label: 'Personal',
                    data: dataSexo.map(d => d.cantidad),
                    backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { 
                    y: { beginAtZero: true, ticks: { stepSize: 1 } } 
                }
            }
        });
    } else {
        document.getElementById('chartSexo').style.display = 'none';
        document.getElementById('noDataSexo').classList.remove('d-none');
        document.getElementById('noDataSexo').classList.add('d-flex');
    }
});