// RUTA: app/presentation/static/js/dashboard.js
// Script para la funcionalidad del dashboard (sidebar toggle y tooltips)

document.addEventListener('DOMContentLoaded', function () {
    // Toggle del sidebar
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function (event) {
            event.preventDefault();
            const wrapper = document.getElementById('wrapper');
            if (wrapper) {
                wrapper.classList.toggle('toggled');
            }
        });
    }

    // Inicializar tooltips de Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
