// Memoria principal
let ESTRUCTURA_DEFAULT = {};

// Función segura para escapar HTML y prevenir XSS
function escapeHtml(text) {
  if (!text) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Cache de secciones de la Base de Datos
let seccionesCache = null;

document.addEventListener('DOMContentLoaded', function () {
  cargarSecciones().then(async () => {
    // 1. Intentamos cargar de la Base de Datos
    await cargarEstructuraDesdeServidor();
    // 2. Intentamos cargar de LocalStorage por si dejó algo a medias
    cargarEstructuraGuardada();

    // 🚀 3. EL LIMPIADOR Y EL EJEMPLO DINÁMICO
    // Si no hay estructura, o si la que cargó solo tiene filas vacías (basura del caché), cargamos el ejemplo.
    if (Object.keys(ESTRUCTURA_DEFAULT).length === 0 || tieneSoloBasura(ESTRUCTURA_DEFAULT)) {
        ESTRUCTURA_DEFAULT = generarEstructuraEjemplo();
    }

    actualizarCampoOcultoJSON();
    cargarEstructura(); 
    generarFormularioEstructura(); 
    setupEventListeners();
  });
});

// Verifica si la estructura guardada está corrupta o vacía
function tieneSoloBasura(estructura) {
    let soloBasura = true;
    Object.values(estructura).forEach(val => {
        if (val.id_seccion && parseInt(val.id_seccion) !== 0) {
            soloBasura = false;
        }
    });
    return soloBasura;
}

// 💡 ESTRUCTURA DE EJEMPLO INTELIGENTE Y EXTENSA
// Simula el escaneo de un legajo nuevo de 20 páginas para guiar al usuario.
function generarEstructuraEjemplo() {
    // Función ultra-segura para extraer IDs. 
    // Si tu BD solo tiene 2 secciones, usará la última disponible para rellenar el resto del ejemplo.
    const s = (index) => {
        if (!seccionesCache || seccionesCache.length === 0) return 1; // Fallback por defecto
        const safeIndex = Math.min(index, seccionesCache.length - 1);
        return parseInt(seccionesCache[safeIndex].id);
    };

    return {
      "01": { 
          id_seccion: s(0), 
          tipo_documento: "DNI", 
          descripcion: "EJEMPLO: Copia de DNI y Carnet de Extranjería", 
          pagina_inicio: 1, 
          pagina_fin: 1 
      },
      "02": { 
          id_seccion: s(0), 
          tipo_documento: "Partida de Nacimiento", 
          descripcion: "EJEMPLO: Partida de Nacimiento / Matrimonio", 
          pagina_inicio: 2, 
          pagina_fin: 2 
      },
      "03": { 
          id_seccion: s(1), 
          tipo_documento: "Currículum Vitae", 
          descripcion: "EJEMPLO: CV documentado y actualizado", 
          pagina_inicio: 3, 
          pagina_fin: 8 
      },
      "04": { 
          id_seccion: s(1), 
          tipo_documento: "Título Universitario", 
          descripcion: "EJEMPLO: Título Profesional y Colegiatura", 
          pagina_inicio: 9, 
          pagina_fin: 10 
      },
      "05": { 
          id_seccion: s(2), 
          tipo_documento: "Contrato Laboral", 
          descripcion: "EJEMPLO: Contrato CAS inicial / Nombramiento", 
          pagina_inicio: 11, 
          pagina_fin: 15 
      },
      "06": { 
          id_seccion: s(3), 
          tipo_documento: "Declaración Jurada", 
          descripcion: "EJEMPLO: DJ de Nepotismo e Incompatibilidades", 
          pagina_inicio: 16, 
          pagina_fin: 18 
      },
      "07": { 
          id_seccion: s(4), 
          tipo_documento: "Antecedentes Penales", 
          descripcion: "EJEMPLO: Certificados Policiales, Penales y Judiciales", 
          pagina_inicio: 19, 
          pagina_fin: 20 
      }
    };
}


function actualizarCampoOcultoJSON() {
  const estructuraJsonField = document.getElementById('estructura_json');
  if (estructuraJsonField) {
    estructuraJsonField.value = JSON.stringify(ESTRUCTURA_DEFAULT);
  }
}

function cargarEstructuraDesdeServidor() {
  return new Promise((resolve) => {
    try {
      const formCargarPDF = document.getElementById('formCargarPDF');
      if (!formCargarPDF) return resolve();
      const id_personal = formCargarPDF.getAttribute('data-personal-id');
      if (!id_personal) return resolve();

      fetch(`/pdf/api/estructura-personal/${id_personal}`)
        .then(response => {
          if (!response.ok) return {};
          return response.json();
        })
        .then(data => {
          if (data && Object.keys(data).length > 0 && !data.error) {
            ESTRUCTURA_DEFAULT = data; 
          }
          resolve();
        })
        .catch(() => resolve());
    } catch (error) { resolve(); }
  });
}

function cargarEstructuraGuardada() {
  try {
    const formCargarPDF = document.getElementById('formCargarPDF');
    if (!formCargarPDF) return;
    const id_personal = formCargarPDF.getAttribute('data-personal-id');
    if (!id_personal) return;

    const storageName = `estructura_${id_personal}`;
    const estructuraGuardada = localStorage.getItem(storageName);

    if (estructuraGuardada) {
      const parsed = JSON.parse(estructuraGuardada);
      if (Object.keys(parsed).length > 0 && parsed[Object.keys(parsed)[0]].hasOwnProperty('id_seccion')) {
         ESTRUCTURA_DEFAULT = parsed;
      }
    }
  } catch (error) {}
}

async function cargarSecciones() {
  if (!seccionesCache) {
    try {
      const response = await fetch('/legajo/api/secciones');
      seccionesCache = await response.json();
    } catch (error) { seccionesCache = []; }
  }
  return seccionesCache;
}

function setupEventListeners() {
  const btnPersonalizar = document.getElementById('btnPersonalizar');
  const btnCancelarPersonalizacion = document.getElementById('btnCancelarPersonalizacion');
  const btnGuardarPersonalizacion = document.getElementById('btnGuardarPersonalizacion');
  const editarEstructura = document.getElementById('editarEstructura');

  if (btnPersonalizar) {
    btnPersonalizar.addEventListener('click', function (e) {
      e.preventDefault();
      editarEstructura.classList.toggle('d-none');
      btnPersonalizar.innerHTML = editarEstructura.classList.contains('d-none')
        ? '<i class="bi bi-pencil me-1"></i>Ocultar Edición'
        : '<i class="bi bi-gear me-1"></i>Personalizar Estructura';
    });
  }

  if (btnCancelarPersonalizacion) {
    btnCancelarPersonalizacion.addEventListener('click', function (e) {
      e.preventDefault();
      editarEstructura.classList.add('d-none');
      btnPersonalizar.innerHTML = '<i class="bi bi-gear me-1"></i>Personalizar Estructura';
      cargarEstructura(); 
      generarFormularioEstructura();
    });
  }

  if (btnGuardarPersonalizacion) {
    btnGuardarPersonalizacion.addEventListener('click', function (e) {
      e.preventDefault();
      guardarEstructuraLocalmente();
    });
  }
}

// ✨ MENSAJES CON SWEETALERT2
function mostrarMensajeBonito(mensaje, tipo = 'success') {
    const iconType = tipo === 'danger' ? 'error' : tipo; 
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            icon: iconType,
            title: tipo === 'success' ? '¡Excelente!' : 'Atención',
            text: mensaje,
            confirmButtonColor: '#0d6efd',
            confirmButtonText: 'Aceptar'
        });
    } else {
        alert(mensaje);
    }
}

function guardarEstructuraLocalmente() {
  try {
    let hayErrores = false;
    ESTRUCTURA_DEFAULT = {}; 

    const tarjetas = document.querySelectorAll('#formularioEstructura .card');
    
    tarjetas.forEach(card => {
        const idFila = card.getAttribute('data-seccion');
        const idSeccion = parseInt(card.querySelector('.seccion-select').value);
        const tipoSelect = card.querySelector('.tipo-documento');
        const tipoDocumentoTexto = tipoSelect.value !== "0" ? tipoSelect.value : "";
        const descripcion = card.querySelector('.descripcion').value;
        const pageStart = parseInt(card.querySelector('.page-start').value);
        const pageEnd = parseInt(card.querySelector('.page-end').value);

        // Si la fila no tiene sección ni tipo, la ignoramos completamente
        if (idSeccion === 0 || !tipoDocumentoTexto) {
            return; 
        }
        
        // Validación de páginas
        if (isNaN(pageStart) || isNaN(pageEnd) || pageStart < 1 || pageEnd < pageStart) {
            card.classList.add('border-danger'); 
            hayErrores = true;
            return;
        } else {
            card.classList.remove('border-danger');
        }

        ESTRUCTURA_DEFAULT[idFila] = {
            id_seccion: idSeccion,
            tipo_documento: tipoDocumentoTexto,
            descripcion: descripcion,
            pagina_inicio: pageStart,
            pagina_fin: pageEnd
        };
    });

    if (hayErrores) {
        mostrarMensajeBonito('Hay errores en los rangos de páginas (marcados en rojo). Corrígelos antes de guardar.', 'danger');
        return; 
    }

    if (Object.keys(ESTRUCTURA_DEFAULT).length === 0) {
        mostrarMensajeBonito('No has configurado ningún documento válido. Selecciona al menos una Sección y un Tipo.', 'warning');
        ESTRUCTURA_DEFAULT = generarEstructuraEjemplo();
        generarFormularioEstructura();
        return;
    }

    const formCargarPDF = document.getElementById('formCargarPDF');
    if (formCargarPDF) {
        const id_personal = formCargarPDF.getAttribute('data-personal-id');
        if (id_personal) {
            localStorage.setItem(`estructura_${id_personal}`, JSON.stringify(ESTRUCTURA_DEFAULT));
        }
    }

    actualizarCampoOcultoJSON();
    cargarEstructura();
    generarFormularioEstructura();

    const editarEstructura = document.getElementById('editarEstructura');
    const btnPersonalizar = document.getElementById('btnPersonalizar');
    if (editarEstructura) editarEstructura.classList.add('d-none');
    if (btnPersonalizar) btnPersonalizar.innerHTML = '<i class="bi bi-gear me-1"></i>Personalizar Estructura';

    mostrarMensajeBonito('Estructura guardada correctamente. El PDF se dividirá según esta configuración.', 'success');

  } catch (error) {
    mostrarMensajeBonito('Error técnico al guardar: ' + error.message, 'danger');
  }
}

function cargarEstructura() {
  const tbody = document.getElementById('estructuraBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  Object.entries(ESTRUCTURA_DEFAULT).forEach(([idFila, datos]) => {
    // 🛡️ Filtro estricto: Si por algún motivo tiene ID 0, no lo dibuja.
    if (!datos.id_seccion || parseInt(datos.id_seccion) === 0) return; 

    let nombreSeccion = `Sección Desconocida`;
    if (seccionesCache && seccionesCache.length > 0) {
      const seccionEncontrada = seccionesCache.find(s => parseInt(s.id) === parseInt(datos.id_seccion));
      if (seccionEncontrada) nombreSeccion = seccionEncontrada.nombre;
    }

    const paginas = datos.pagina_inicio === datos.pagina_fin ? datos.pagina_inicio : `${datos.pagina_inicio}-${datos.pagina_fin}`;
    
    tbody.innerHTML += `
        <tr data-seccion="${escapeHtml(idFila)}">
            <td class="fw-medium text-dark">${escapeHtml(nombreSeccion)}</td>
            <td><span class="badge bg-secondary">${escapeHtml(datos.tipo_documento)}</span></td>
            <td class="text-muted">${escapeHtml(datos.descripcion)}</td>
            <td class="text-center fw-bold text-primary">${escapeHtml(paginas)}</td>
        </tr>`;
  });
}

function generarFormularioEstructura() {
  const formulario = document.getElementById('formularioEstructura');
  if (!formulario) return;
  formulario.innerHTML = '';
  
  Object.entries(ESTRUCTURA_DEFAULT).forEach(([idFila, datos]) => {
      generarCardSeccion(idFila, datos, formulario);
  });

  const btnAgregar = document.createElement('button');
  btnAgregar.type = 'button';
  btnAgregar.className = 'btn btn-sm btn-success mt-3';
  btnAgregar.innerHTML = '<i class="bi bi-plus-lg me-1"></i>Agregar Nuevo Bloque';
  btnAgregar.addEventListener('click', () => {
    const newIdFila = Date.now().toString().slice(-6); 
    
    ESTRUCTURA_DEFAULT[newIdFila] = { 
        "id_seccion": 0, "tipo_documento": "", "descripcion": "", "pagina_inicio": "", "pagina_fin": "" 
    };

    generarCardSeccion(newIdFila, ESTRUCTURA_DEFAULT[newIdFila], formulario);
    formulario.appendChild(btnAgregar); 
  });
  
  formulario.appendChild(btnAgregar);
}

function generarCardSeccion(idFila, datos, formulario) {
  const card = document.createElement('div');
  card.className = 'card mb-3 shadow-sm border bg-white';
  card.setAttribute('data-seccion', idFila);

  const urlTipos = document.querySelector('#seccion_select') ? 
                   document.querySelector('#seccion_select').getAttribute('data-tipos-url') : 
                   '/legajo/api/tipos_documento/por_seccion/0';

  card.innerHTML = `
    <div class="card-body p-3">
      <div class="row g-2 align-items-end">
        <div class="col-12 col-md-3">
            <label class="form-label small fw-bold text-primary">Sección del Legajo</label>
            <select class="form-select form-select-sm seccion-select" data-tipos-url="${urlTipos}">
                <option value="0">-- Seleccionar Sección --</option>
            </select>
        </div>
        <div class="col-12 col-md-3">
            <label class="form-label small fw-bold text-primary">Tipo Documento</label>
            <select class="form-select form-select-sm tipo-documento">
                <option value="${datos.tipo_documento || '0'}">${datos.tipo_documento || '-- Seleccione sección --'}</option>
            </select>
        </div>
        <div class="col-12 col-md-3">
            <label class="form-label small fw-bold text-secondary">Descripción Breve</label>
            <input type="text" class="form-control form-control-sm descripcion" value="${escapeHtml(datos.descripcion)}" placeholder="Opcional...">
        </div>
        <div class="col-12 col-md-1">
            <label class="form-label small fw-bold text-secondary">Pág. Inicio</label>
            <input type="number" class="form-control form-control-sm page-start text-center" value="${datos.pagina_inicio}" min="1">
        </div>
        <div class="col-12 col-md-1">
            <label class="form-label small fw-bold text-secondary">Pág. Fin</label>
            <input type="number" class="form-control form-control-sm page-end text-center" value="${datos.pagina_fin}" min="1">
        </div>
        <div class="col-12 col-md-1 d-flex justify-content-center">
            <button type="button" class="btn btn-sm btn-outline-danger btn-eliminar-fila w-100" title="Remover Bloque"><i class="bi bi-trash"></i></button>
        </div>
      </div>
    </div>
  `;

  const seccionSelect = card.querySelector('.seccion-select');
  if (seccionesCache) {
    seccionesCache.forEach(sec => {
      const opt = document.createElement('option');
      opt.value = sec.id;
      opt.textContent = sec.nombre;
      if (parseInt(sec.id) === parseInt(datos.id_seccion)) opt.selected = true;
      seccionSelect.appendChild(opt);
    });
  }

  const btnEliminar = card.querySelector('.btn-eliminar-fila');
  btnEliminar.addEventListener('click', () => eliminarFila(card));
  
  seccionSelect.addEventListener('change', () => actualizarTiposDocumento(seccionSelect, null));

  if (datos.id_seccion && parseInt(datos.id_seccion) !== 0) {
    actualizarTiposDocumento(seccionSelect, datos.tipo_documento);
  }

  formulario.appendChild(card);
}

function actualizarTiposDocumento(selectElement, valorSeleccionadoPrevio) {
  const card = selectElement.closest('.card');
  const seccionId = selectElement.value;
  const tipoSelect = card.querySelector('.tipo-documento');

  tipoSelect.innerHTML = '<option value="0">Cargando...</option>';
  tipoSelect.disabled = true;

  if (seccionId && seccionId !== '0') {
    const baseUrl = selectElement.getAttribute('data-tipos-url');
    const url = baseUrl ? baseUrl.replace('/0', `/${seccionId}`) : `/legajo/api/tipos_documento/por_seccion/${seccionId}`;

    if (card.fetchTimeout) clearTimeout(card.fetchTimeout);
    card.fetchTimeout = setTimeout(() => {
      fetch(url)
        .then(r => r.json())
        .then(data => {
          tipoSelect.innerHTML = '<option value="0">-- Seleccione Tipo --</option>';
          if (data && data.length > 0) {
            data.forEach(tipo => {
              const opt = document.createElement('option');
              opt.value = tipo.nombre; 
              opt.textContent = tipo.nombre;
              if (valorSeleccionadoPrevio && (tipo.nombre === valorSeleccionadoPrevio)) opt.selected = true;
              tipoSelect.appendChild(opt);
            });
            tipoSelect.disabled = false;
          } else {
            tipoSelect.innerHTML = '<option value="0">No hay tipos registrados</option>';
          }
        }).catch(e => {
          tipoSelect.innerHTML = '<option value="0">Error de conexión</option>';
          tipoSelect.disabled = false;
        });
    }, 300);
  } else {
    tipoSelect.innerHTML = '<option value="0">-- Seleccione sección primero --</option>';
    tipoSelect.disabled = true;
  }
}

// 🚀 SWEETALERT2 PARA ELIMINAR FILAS
function eliminarFila(card) {
  const idFila = card.getAttribute('data-seccion');

  if (typeof Swal !== 'undefined') {
      Swal.fire({
          title: '¿Remover bloque?',
          text: '¿Está seguro de remover este bloque de páginas del PDF?',
          icon: 'warning',
          showCancelButton: true,
          confirmButtonColor: '#dc3545', 
          cancelButtonColor: '#0d6efd', 
          confirmButtonText: 'Sí, remover',
          cancelButtonText: 'Cancelar'
      }).then((result) => {
          if (result.isConfirmed) {
              delete ESTRUCTURA_DEFAULT[idFila];
              card.remove();
          }
      });
  } else {
      if (confirm('¿Está seguro de remover este bloque de páginas del PDF?')) {
          delete ESTRUCTURA_DEFAULT[idFila];
          card.remove();
      }
  }
}