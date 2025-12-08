/**
 * Handlers específicos para perfil.html
 */

document.addEventListener('DOMContentLoaded', function () {
  // Cancelar formulario de email
  document.querySelectorAll('[data-cancel-email-form]').forEach(btn => {
    btn.addEventListener('click', function () {
      const emailForm = document.getElementById('email-form');
      if (emailForm) {
        emailForm.style.display = 'none';
      }
    });
  });

  // Cancelar cambio de contraseña
  document.querySelectorAll('[data-cancel-password-form]').forEach(btn => {
    btn.addEventListener('click', function () {
      window.history.back();
    });
  });

  // Botón para subir foto (activar input file oculto)
  document.querySelectorAll('[data-trigger-file-input]').forEach(btn => {
    btn.addEventListener('click', function () {
      const inputId = this.getAttribute('data-trigger-file-input');
      const inputElement = document.getElementById(inputId);
      if (inputElement) {
        inputElement.click();
      }
    });
  });

  // Volver atrás
  document.querySelectorAll('[data-go-back]').forEach(btn => {
    btn.addEventListener('click', function () {
      window.history.back();
    });
  });

  // Toggle password visibility
  document.querySelectorAll('[data-toggle-password]').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const fieldId = this.getAttribute('data-toggle-password');
      const field = document.getElementById(fieldId);
      const icon = this.querySelector('i');

      if (field.type === 'password') {
        field.type = 'text';
        if (icon) icon.className = 'bi bi-eye-slash';
      } else {
        field.type = 'password';
        if (icon) icon.className = 'bi bi-eye';
      }
    });
  });

  // Mostrar nombre del archivo seleccionado
  const fotoCarnetInput = document.getElementById('foto_carnet');
  if (fotoCarnetInput) {
    fotoCarnetInput.addEventListener('change', function () {
      const fileName = this.files[0] ? this.files[0].name : '';
      const label = document.getElementById('file-label');
      if (fileName && label) {
        label.innerHTML = '<i class="bi bi-check-circle me-1" style="color: #16a34a;"></i> Archivo: <strong>' + fileName + '</strong>';
      }
    });
  }

  // Validación de coincidencia de contraseñas
  const passwordNueva = document.getElementById('password_nueva');
  const passwordConfirmacion = document.getElementById('password_confirmacion');

  if (passwordConfirmacion && passwordNueva) {
    passwordConfirmacion.addEventListener('input', function () {
      if (passwordNueva.value && passwordConfirmacion.value) {
        if (passwordNueva.value === passwordConfirmacion.value) {
          passwordConfirmacion.style.borderColor = '#16a34a'; // Verde si coinciden
        } else {
          passwordConfirmacion.style.borderColor = '#dc2626'; // Rojo si no coinciden
        }
      }
    });
  }
});
