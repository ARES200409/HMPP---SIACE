// app/presentation/static/js/record_laboral.js
document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('btnGenerarReporteFinal');
    
    if (btn) {
        btn.addEventListener('click', function() {
            const dropdown = document.getElementById('inputAnioReporte');
            const anio = dropdown.value;
            
            if (!anio) {
                alert("⚠️ Por favor, seleccione un año de la lista.");
                return;
            }

            // Recuperamos los datos que inyectamos en el botón desde el HTML
            const urlBase = btn.getAttribute('data-url-base');
            const urlFinal = urlBase.replace('99999', anio);
            
            console.log("Generando reporte para el año:", anio);

            // 1. Abrir el PDF en pestaña nueva
            window.open(urlFinal, '_blank');

            // 2. Recarga automática de la página principal para ver el PDF en la tabla
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        });
    }
});