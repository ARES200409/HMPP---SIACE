// RUTA: app/presentation/static/js/confirmacion-usuario.js
// Scripts para la página de confirmación de usuario creado

// Copiar al portapapeles
document.querySelectorAll('[data-copy-to-clipboard]').forEach(btn => {
    btn.addEventListener('click', function () {
        const elementId = this.getAttribute('data-copy-to-clipboard');
        const elemento = document.getElementById(elementId);

        if (elemento) {
            elemento.select();
            document.execCommand("copy");

            // Mostrar feedback
            const textOriginal = this.innerHTML;
            this.innerHTML = '<i class="bi bi-check me-1"></i>¡Copiado!';
            setTimeout(() => {
                this.innerHTML = textOriginal;
            }, 2000);
        }
    });
});

// Mostrar/Ocultar password
document.querySelectorAll('[data-toggle-password]').forEach(btn => {
    btn.addEventListener('click', function () {
        const passwordId = this.getAttribute('data-toggle-password');
        const passwordInput = document.getElementById(passwordId);
        const iconOjo = this.querySelector('i');

        if (passwordInput && iconOjo) {
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                iconOjo.classList.remove('bi-eye');
                iconOjo.classList.add('bi-eye-slash');
            } else {
                passwordInput.type = 'password';
                iconOjo.classList.remove('bi-eye-slash');
                iconOjo.classList.add('bi-eye');
            }
        }
    });
});

// Función para imprimir (accesible globalmente para onclick inline)
function imprimirDatos() {
    window.print();
}

// Advertencia antes de salir
window.addEventListener('beforeunload', function (e) {
    // Solo mostrar si el usuario intenta navegar
    if (document.referrer.includes('confirmacion_usuario_creado')) {
        e.preventDefault();
        e.returnValue = 'Has generado credenciales. Asegúrate de haberlas guardado de forma segura.';
    }
});
