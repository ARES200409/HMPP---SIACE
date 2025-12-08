// Estructura default con nuevos campos
let ESTRUCTURA_DEFAULT = {
  "01": { "id_seccion": 1, "tipo_documento": "DNI", "descripcion": "Cédula de Identidad", "pagina_inicio": 1, "pagina_fin": 1 },
  "02": { "id_seccion": 2, "tipo_documento": "Curriculum", "descripcion": "Currículum Vitae", "pagina_inicio": 2, "pagina_fin": 5 },
  "03": { "id_seccion": 3, "tipo_documento": "Titulo", "descripcion": "Título Universitario", "pagina_inicio": 6, "pagina_fin": 6 },
  "04": { "id_seccion": 4, "tipo_documento": "Contrato", "descripcion": "Contrato Laboral", "pagina_inicio": 7, "pagina_fin": 12 },
  "05": { "id_seccion": 5, "tipo_documento": "Antecedentes", "descripcion": "Antecedentes Penales", "pagina_inicio": 13, "pagina_fin": 14 },
  "06": { "id_seccion": 6, "tipo_documento": "Carnet", "descripcion": "Carnet Sanitario", "pagina_inicio": 15, "pagina_fin": 15 },
  "07": { "id_seccion": 7, "tipo_documento": "Licencias", "descripcion": "Licencias Profesionales", "pagina_inicio": 16, "pagina_fin": 20 }
};

// Función segura para escapar HTML y prevenir XSS
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Cache de secciones cargadas una sola vez
let seccionesCache = null;

document.addEventListener('DOMContentLoaded', function () {
  cargarSecciones().then(async () => {
    // Cargar estructura personalizada desde BD si existe
    await cargarEstructuraDesdeServidor();

    // IMPORTANTE: Actualizar el campo del formulario con la estructura
    const estructuraJsonField = document.getElementById('estructura_json');
    if (estructuraJsonField) {
      estructuraJsonField.value = JSON.stringify(ESTRUCTURA_DEFAULT);
    }

    cargarEstructura();
    setupEventListeners();
  });
});

function cargarEstructuraDesdeServidor() {
  return new Promise((resolve) => {
    try {
      // Obtener id_personal del atributo data del formulario
      const formCargarPDF = document.getElementById('formCargarPDF');
      if (!formCargarPDF) {
        resolve();
        return;
      }

      const id_personal = formCargarPDF.getAttribute('data-personal-id');

      if (!id_personal) {
        resolve();
        return;
      }

      // CORRECCIÓN: Ruta apuntando al Blueprint 'pdf_bp' correcto
      fetch(`/pdf/api/estructura-personal/${id_personal}`)
        .then(response => {
          if (!response.ok) {
            // Silencioso en caso de error 404 o 500
            return {};
          }
          return response.json();
        })
        .then(data => {
          if (data && data.estructura) {
            // Hacer MERGE con la estructura por defecto
            Object.assign(ESTRUCTURA_DEFAULT, data.estructura);
          }
          resolve();
        })
        .catch(error => {
          // Fallback silencioso a la estructura por defecto
          resolve();
        });

    } catch (error) {
      resolve();
    }
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
      try {
        const parsed = JSON.parse(estructuraGuardada);

        // Validar estructura antes de aplicar
        let estructuraValida = true;
        for (const [key, val] of Object.entries(parsed)) {
          if (typeof val !== 'object' || !val.hasOwnProperty('id_seccion')) {
            estructuraValida = false;
            break;
          }
        }

        if (!estructuraValida) {
          localStorage.removeItem(storageName);
          return;
        }

        Object.assign(ESTRUCTURA_DEFAULT, parsed);

      } catch (e) {
        localStorage.removeItem(storageName);
      }
    }
  } catch (error) {
    // Ignorar errores de localStorage
  }
}

async function cargarSecciones() {
  if (!seccionesCache) {
    try {
      const response = await fetch('/legajo/api/secciones');
      seccionesCache = await response.json();
    } catch (error) {
      seccionesCache = [];
    }
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
        ? '<i class="bi bi-pencil me-1"></i>Personalizar Estructura'
        : '<i class="bi bi-x me-1"></i>Ocultar Edición';
    });
  }

  if (btnCancelarPersonalizacion) {
    btnCancelarPersonalizacion.addEventListener('click', function (e) {
      e.preventDefault();
      editarEstructura.classList.add('d-none');
      btnPersonalizar.innerHTML = '<i class="bi bi-pencil me-1"></i>Personalizar Estructura';
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

function guardarEstructuraLocalmente() {
  try {
    const formCargarPDF = document.getElementById('formCargarPDF');
    if (!formCargarPDF) {
      alert('Error: No se encontró el formulario.');
      return;
    }

    const id_personal = formCargarPDF.getAttribute('data-personal-id');

    if (!id_personal) {
      alert('No se pudo determinar el personal. Por favor, recarga la página.');
      return;
    }

    const storageName = `estructura_${id_personal}`;
    const estructuraJSON = JSON.stringify(ESTRUCTURA_DEFAULT);

    localStorage.setItem(storageName, estructuraJSON);

    // ACTUALIZAR el campo del formulario INMEDIATAMENTE
    const estructuraJsonField = document.getElementById('estructura_json');
    if (estructuraJsonField) {
      estructuraJsonField.value = estructuraJSON;
    }

    alert('Estructura personalizada guardada correctamente');
    const editarEstructura = document.getElementById('editarEstructura');
    const btnPersonalizar = document.getElementById('btnPersonalizar');

    if (editarEstructura) editarEstructura.classList.add('d-none');
    if (btnPersonalizar) btnPersonalizar.innerHTML = '<i class="bi bi-pencil me-1"></i>Personalizar Estructura';

  } catch (error) {
    alert('Error al guardar: ' + error.message);
  }
}

function cargarEstructura() {
  const tbody = document.getElementById('estructuraBody');
  if (!tbody) return;
  tbody.innerHTML = '';
  Object.entries(ESTRUCTURA_DEFAULT).forEach(([seccion, datos]) => {
    let nombreSeccion = seccion;
    if (datos.id_seccion && seccionesCache && seccionesCache.length > 0) {
      const seccionEncontrada = seccionesCache.find(s => s.id === parseInt(datos.id_seccion));
      if (seccionEncontrada) {
        nombreSeccion = seccionEncontrada.nombre;
      }
    }

    const paginas = datos.pagina_inicio === datos.pagina_fin ? datos.pagina_inicio : `${datos.pagina_inicio}-${datos.pagina_fin}`;
    tbody.innerHTML += `<tr data-seccion="${escapeHtml(seccion)}"><td>${escapeHtml(nombreSeccion)}</td><td>${escapeHtml(datos.tipo_documento)}</td><td>${escapeHtml(datos.descripcion)}</td><td>${escapeHtml(paginas)}</td></tr>`;
  });
  generarFormularioEstructura();
}

function generarFormularioEstructura() {
  const formulario = document.getElementById('formularioEstructura');
  if (!formulario) return;
  formulario.innerHTML = '';
  Object.entries(ESTRUCTURA_DEFAULT).forEach(([seccion, datos]) => generarCardSeccion(seccion, datos, formulario));

  const btnAgregar = document.createElement('button');
  btnAgregar.type = 'button';
  btnAgregar.className = 'btn btn-sm btn-success mt-3';
  btnAgregar.innerHTML = '<i class="bi bi-plus-lg me-1"></i>Agregar Sección';
  btnAgregar.addEventListener('click', () => {
    const num = Object.keys(ESTRUCTURA_DEFAULT).length + 1;
    const newSeccion = String(num).padStart(2, '0');
    ESTRUCTURA_DEFAULT[newSeccion] = { "id_seccion": 0, "tipo_documento": "", "descripcion": "", "pagina_inicio": 1, "pagina_fin": 1 };

    const tbody = document.getElementById('estructuraBody');
    if (tbody) {
      tbody.innerHTML += `<tr data-seccion="${escapeHtml(newSeccion)}"><td>${escapeHtml(newSeccion)}</td><td></td><td></td><td>1</td></tr>`;
    }

    generarCardSeccion(newSeccion, ESTRUCTURA_DEFAULT[newSeccion], formulario);
    formulario.appendChild(btnAgregar);
  });
  formulario.appendChild(btnAgregar);
}

function generarCardSeccion(seccion, datos, formulario) {
  const card = document.createElement('div');
  card.className = 'card mb-3';
  card.setAttribute('data-seccion', seccion);

  card.innerHTML = `
    <div class="card-body p-2">
      <div class="row g-2">
        <div class="col-12 col-md-2"><label class="form-label small fw-bold">ID</label><input type="text" class="form-control form-control-sm" value="${seccion}" disabled></div>
        <div class="col-12 col-md-2"><label class="form-label small fw-bold">Sección</label><select class="form-select form-select-sm seccion-select" data-tipos-url="/legajo/api/tipos_documento/por_seccion/0"><option value="0">-- Seleccionar --</option></select></div>
        <div class="col-12 col-md-3"><label class="form-label small fw-bold">Tipo Documento</label><select class="form-select form-select-sm tipo-documento"><option value="0">-- Seleccione sección --</option></select></div>
        <div class="col-12 col-md-2"><label class="form-label small fw-bold">Descripción</label><input type="text" class="form-control form-control-sm descripcion" value="${datos.descripcion}"></div>
        <div class="col-12 col-md-1"><label class="form-label small fw-bold">Inicio</label><input type="number" class="form-control form-control-sm page-start" value="${datos.pagina_inicio}" min="1"></div>
        <div class="col-12 col-md-1"><label class="form-label small fw-bold">Fin</label><input type="number" class="form-control form-control-sm page-end" value="${datos.pagina_fin}" min="1"></div>
        <div class="col-12 col-md-1 d-flex align-items-end gap-1"><button type="button" class="btn btn-sm btn-outline-primary flex-grow-1 btn-actualizar-fila" title="Guardar"><i class="bi bi-check"></i></button><button type="button" class="btn btn-sm btn-outline-danger btn-eliminar-fila" title="Eliminar"><i class="bi bi-trash"></i></button></div>
      </div>
    </div>
  `;

  const seccionSelect = card.querySelector('.seccion-select');

  if (seccionesCache) {
    seccionesCache.forEach(sec => {
      const opt = document.createElement('option');
      opt.value = sec.id;
      opt.textContent = sec.nombre;
      if (sec.id === datos.id_seccion) opt.selected = true;
      seccionSelect.appendChild(opt);
    });
  }

  const btnActualizar = card.querySelector('.btn-actualizar-fila');
  const btnEliminar = card.querySelector('.btn-eliminar-fila');

  btnActualizar.addEventListener('click', () => actualizarFila(card));
  btnEliminar.addEventListener('click', () => eliminarFila(card));
  seccionSelect.addEventListener('change', () => actualizarTiposDocumento(seccionSelect));

  if (datos.id_seccion && datos.id_seccion !== 0) {
    actualizarTiposDocumento(seccionSelect);
  }

  formulario.appendChild(card);
}

function actualizarTiposDocumento(selectElement) {
  const card = selectElement.closest('.card');
  const seccionId = selectElement.value;
  const tipoSelect = card.querySelector('.tipo-documento');

  tipoSelect.innerHTML = '<option value="0">Cargando...</option>';
  tipoSelect.disabled = true;

  if (seccionId && seccionId !== '0') {
    const url = selectElement.getAttribute('data-tipos-url').replace('/0', `/${seccionId}`);

    if (card.fetchTimeout) clearTimeout(card.fetchTimeout);
    card.fetchTimeout = setTimeout(() => {
      fetch(url).then(r => r.json()).then(data => {
        tipoSelect.innerHTML = '<option value="0">-- Seleccionar --</option>';
        if (data && data.length > 0) {
          data.forEach(tipo => {
            const opt = document.createElement('option');
            opt.value = tipo.id;
            opt.textContent = tipo.nombre;
            tipoSelect.appendChild(opt);
          });
          tipoSelect.disabled = false;
        } else {
          tipoSelect.innerHTML = '<option value="0">Sin tipos</option>';
        }
      }).catch(e => {
        tipoSelect.innerHTML = '<option value="0">Error</option>';
        tipoSelect.disabled = false;
      });
    }, 300);
  } else {
    tipoSelect.innerHTML = '<option value="0">-- Seleccione sección --</option>';
    tipoSelect.disabled = true;
  }
}

function actualizarFila(card) {
  const seccion = card.getAttribute('data-seccion');

  const seccionSelect = card.querySelector('.seccion-select');
  const seccionNumero = seccionSelect.value;

  const seccionNombre = seccionSelect.options[seccionSelect.selectedIndex]?.text || seccionNumero;

  const tipoDocumentoSelect = card.querySelector('.tipo-documento');
  const tipoDocumentoId = tipoDocumentoSelect.value;
  const tipoDocumentoNombre = tipoDocumentoSelect.options[tipoDocumentoSelect.selectedIndex]?.text || tipoDocumentoSelect.value;

  const descripcion = card.querySelector('.descripcion').value;
  const pageStart = parseInt(card.querySelector('.page-start').value);
  const pageEnd = parseInt(card.querySelector('.page-end').value);

  if (!seccionNumero || seccionNumero === '0' || !tipoDocumentoId || tipoDocumentoId === '0') {
    alert('Por favor completa todos los campos');
    return;
  }

  if (isNaN(pageStart) || isNaN(pageEnd) || pageStart < 1 || pageEnd < 1) {
    alert('Las páginas deben ser números válidos mayores a 0');
    return;
  }

  ESTRUCTURA_DEFAULT[seccion] = {
    id_seccion: parseInt(seccionNumero),
    tipo_documento: tipoDocumentoNombre,
    descripcion: descripcion,
    pagina_inicio: pageStart,
    pagina_fin: pageEnd
  };

  const tbody = document.getElementById('estructuraBody');
  const tableRow = tbody.querySelector(`tr[data-seccion="${seccion}"]`);
  if (tableRow) {
    const celdas = tableRow.querySelectorAll('td');
    celdas[0].textContent = seccionNombre;
    celdas[1].textContent = tipoDocumentoNombre;
    celdas[2].textContent = descripcion;
    celdas[3].textContent = pageStart === pageEnd ? pageStart : `${pageStart}-${pageEnd}`;
  }

  const btn = card.querySelector('.btn-actualizar-fila');
  btn.classList.add('btn-success');
  btn.classList.remove('btn-outline-primary');
  setTimeout(() => {
    btn.classList.remove('btn-success');
    btn.classList.add('btn-outline-primary');
  }, 1000);
}

function eliminarFila(card) {
  if (confirm('¿Eliminar esta sección?')) {
    const seccion = card.getAttribute('data-seccion');
    delete ESTRUCTURA_DEFAULT[seccion];
    card.remove();
    const tr = document.querySelector(`tr[data-seccion="${seccion}"]`);
    if (tr) tr.remove();
  }
}