if (window.historicoIniciado) {
    console.warn("historico.js bloqueado por seguridad (singleton).");
} else {
    window.historicoIniciado = true;

    document.addEventListener('DOMContentLoaded', function() {
        const configDiv = document.getElementById('historico-config');
        if (!configDiv) return;

        const config = {
            csrf: configDiv.getAttribute('data-csrf') || '',
            urlGuardar: configDiv.getAttribute('data-url-guardar') || '',
            urlSubir: configDiv.getAttribute('data-url-subir') || '',
            urlObtener: configDiv.getAttribute('data-url-obtener') || '',
            urlEliminar: configDiv.getAttribute('data-url-eliminar') || '',
            urlCandado: configDiv.getAttribute('data-url-candado') || '',
            urlGenerarPdf: configDiv.getAttribute('data-url-generar-pdf') || '',
            idPersonal: configDiv.getAttribute('data-id-personal')
        };

        const divFormulario = document.getElementById('divFormularioHistorico');
        const tablaConceptos = document.getElementById('tablaConceptosHistoricos');
        let modoEdicionId = null;

        // ==========================================
        // 🚀 CALCULADORA EN TIEMPO REAL
        // ==========================================
        function calcularTotalesHistoricos() {
            let ingresos = 0, descuentos = 0, excepcionales = 0;
            
            tablaConceptos.querySelectorAll('tr').forEach(tr => {
                let v = parseFloat(tr.querySelector('.ph-monto').value) || 0;
                let tipo = tr.querySelector('.ph-tipo').value;
                
                if (tipo === 'INGRESO') ingresos += v; 
                else if (tipo === 'DESCUENTO') descuentos += v;
                else if (tipo === 'EXCEPCIONAL') excepcionales += v;
            });
            
            let totalBolsillo = ingresos + excepcionales;
            
            document.getElementById('ph_lbl_ingresos').innerText = totalBolsillo.toFixed(2);
            document.getElementById('ph_lbl_descuentos').innerText = descuentos.toFixed(2);
            document.getElementById('ph_lbl_neto').innerText = (totalBolsillo - descuentos).toFixed(2);
        }

        tablaConceptos.addEventListener('input', calcularTotalesHistoricos);
        tablaConceptos.addEventListener('change', (e) => {
            if (e.target.classList.contains('ph-tipo')) calcularTotalesHistoricos();
        });

        // ==========================================
        // 🖱️ GESTIÓN DE CLICKS (EVENT DELEGATION)
        // ==========================================
        document.addEventListener('click', function(e) {
            
            if(e.target.closest('#btnMostrarForm')) {
                e.preventDefault();
                modoEdicionId = null; 
                limpiarFormularioManual();
                document.getElementById('pills-tab').parentElement.style.display = 'inline-flex';
                document.getElementById('pills-manual-tab').click(); 
                divFormulario.style.display = 'block';
                agregarFilaConcepto('INGRESO', 'Remuneración Básica / Principal');
                agregarFilaConcepto('DESCUENTO', 'Descuento de Ley (Pensión)');
                divFormulario.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            
            if(e.target.closest('.btnOcultarForm')) {
                e.preventDefault();
                divFormulario.style.display = 'none';
                modoEdicionId = null;
            }

            if(e.target.closest('#btnAgregarConcepto')) {
                e.preventDefault();
                agregarFilaConcepto('INGRESO', '');
            }

            if(e.target.closest('.btn-eliminar-fila')) {
                e.preventDefault();
                e.target.closest('tr').remove();
                calcularTotalesHistoricos();
            }

            if(e.target.closest('#btnGuardarPlanilla')) {
                e.preventDefault();
                guardarPlanillaManual(e.target.closest('#btnGuardarPlanilla'));
            }

            if(e.target.closest('#btnSubirArchivo')) {
                e.preventDefault();
                subirArchivoDocumento(e.target.closest('#btnSubirArchivo'));
            }

            const btnDelete = e.target.closest('.btn-borrar-planilla');
            if(btnDelete) {
                e.preventDefault();
                Swal.fire({
                    title: '¿Estás seguro?',
                    text: "¡Se borrará el registro histórico! No hay vuelta atrás.",
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#dc3545',
                    cancelButtonColor: '#6c757d',
                    confirmButtonText: '<i class="bi bi-trash-fill"></i> Sí, eliminar',
                    cancelButtonText: 'Cancelar'
                }).then((result) => {
                    if (result.isConfirmed) {
                        ejecutarAccion(btnDelete, config.urlEliminar.replace('0', btnDelete.dataset.id), 'DELETE');
                    }
                });
            }

            // 🚀 NUEVA LÓGICA DE CANDADO CON SWEETALERT2 (ESTILO RRHH)
            const btnCandado = e.target.closest('.btn-candado-planilla');
            if(btnCandado) {
                e.preventDefault();
                
                let estaBloqueada = btnCandado.classList.contains('btn-danger');

                if(estaBloqueada) {
                    // PEDIR CONTRASEÑA PARA ABRIR
                    Swal.fire({
                        title: '🔒 Autorización Requerida',
                        html: 'Esta planilla está cerrada por seguridad.<br>Ingrese la <b>Clave de Escalafón</b> para desbloquearla:',
                        input: 'password', // Oculta el texto
                        inputAttributes: {
                            autocapitalize: 'off',
                            placeholder: 'Ingrese clave de autorización',
                            style: 'text-align: center; letter-spacing: 5px; font-size: 1.5rem;'
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
                            procesarCandadoEnServidor(btnCandado, result.value);
                        }
                    });
                } else {
                    // CONFIRMAR PARA CERRAR
                    Swal.fire({
                        title: '¿Cerrar Planilla?',
                        text: "Se bloqueará la edición para proteger los datos históricos.",
                        icon: 'info',
                        showCancelButton: true,
                        confirmButtonColor: '#343a40',
                        cancelButtonColor: '#6c757d',
                        confirmButtonText: '<i class="bi bi-lock-fill"></i> Sí, cerrar',
                        cancelButtonText: 'Cancelar'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            procesarCandadoEnServidor(btnCandado, "");
                        }
                    });
                }
            }

            const btnEdit = e.target.closest('.btn-editar-planilla');
            if(btnEdit) {
                e.preventDefault();
                cargarDatosEdicion(btnEdit);
            }

            if(e.target.closest('.btn-generar-pdf')) {
                e.preventDefault();
                generarPDF(e.target.closest('.btn-generar-pdf'));
            }
        });

        // ==========================================
        // 🔐 FUNCIÓN AJAX PARA EL CANDADO
        // ==========================================
        function procesarCandadoEnServidor(btn, token) {
            btn.disabled = true;
            fetch(config.urlCandado.replace('0', btn.dataset.id), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': config.csrf },
                body: JSON.stringify({ token_seguridad: token })
            })
            .then(res => res.json())
            .then(data => {
                if(data.estado === 'ok') {
                    // Mensaje de éxito flotante
                    Swal.fire({
                        toast: true,
                        position: 'top-end',
                        icon: 'success',
                        title: data.mensaje || 'Operación exitosa',
                        showConfirmButton: false,
                        timer: 3000
                    });
                    cargarPlanillasGuardadas();
                } else {
                    Swal.fire('Acceso Denegado', data.mensaje, 'error');
                    btn.disabled = false;
                }
            })
            .catch(err => {
                Swal.fire('Error', 'No se pudo conectar con el servidor.', 'error');
                btn.disabled = false;
            });
        }

        // ==========================================
        // 🛠️ RENDERIZADO Y DASHBOARD GERENCIAL
        // ==========================================
        function cargarPlanillasGuardadas() {
            const tbody = document.getElementById('tablaPlanillasGuardadas');
            const divResumenMulti = document.getElementById('resumen-totales');
            const divMetricas = document.getElementById('metricas-generales');
            
            fetch(config.urlObtener).then(res => res.json()).then(data => {
                tbody.innerHTML = '';
                divResumenMulti.innerHTML = '';
                
                if(data.data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-muted">Sin registros históricos.</td></tr>';
                    divResumenMulti.classList.add('d-none');
                    divMetricas.classList.add('d-none');
                    return;
                }

                let totalesPorMoneda = {};
                let aniosUnicos = new Set();
                let countCerradas = 0;
                let countSinScan = 0;

                data.data.forEach(p => {
                    aniosUnicos.add(p.anio);
                    if (p.bloqueado) countCerradas++;
                    if (!p.ruta_escaneado) countSinScan++;

                    let simbolo = 'S/';
                    let badgeColor = 'bg-primary';
                    if (p.moneda === 'Intis') { simbolo = 'I/.'; badgeColor = 'bg-warning text-dark'; }
                    if (p.moneda === 'Nuevos Soles') { simbolo = 'S/.'; badgeColor = 'bg-info text-dark'; }
                    if (p.moneda === 'Soles de Oro') { simbolo = 'S/. (Oro)'; badgeColor = 'bg-secondary'; }
                    if (p.moneda === 'Documento Escaneado') { simbolo = '-'; badgeColor = 'bg-light text-muted border'; }

                    if (p.moneda !== 'Documento Escaneado') {
                        if (!totalesPorMoneda[p.moneda]) {
                            totalesPorMoneda[p.moneda] = { simbolo: simbolo, ingresos: 0, descuentos: 0, neto: 0 };
                        }
                        totalesPorMoneda[p.moneda].ingresos += parseFloat(p.ingresos || 0);
                        totalesPorMoneda[p.moneda].descuentos += parseFloat(p.descuentos || 0);
                        totalesPorMoneda[p.moneda].neto += parseFloat(p.neto || 0);
                    }

                    let btnEscaneo = p.ruta_escaneado 
                        ? `<a href="/static/${p.ruta_escaneado}" target="_blank" class="btn btn-sm btn-info rounded-pill px-3 shadow-sm"><i class="bi bi-file-earmark-pdf"></i> Original</a>`
                        : `<span class="badge bg-light text-muted border">Sin Escaneo</span>`;

                    let btnModerno = p.ruta_generado
                        ? `<a href="/static/${p.ruta_generado}?v=${new Date().getTime()}" target="_blank" class="btn btn-sm btn-primary rounded-pill px-3 shadow-sm"><i class="bi bi-eye"></i> Digital</a>`
                        : `<button class="btn btn-sm btn-outline-secondary rounded-pill px-3 btn-generar-pdf" data-id="${p.id}"><i class="bi bi-gear-fill"></i> Generar</button>`;
                    
                    tbody.innerHTML += `
                        <tr class="${p.bloqueado ? 'bg-light bg-opacity-50' : ''}">
                            <td class="ps-4 fw-bold text-dark">${p.anio}</td>
                            <td>${p.mes}</td>
                            <td class="text-center"><span class="badge ${badgeColor}">${p.moneda}</span></td>
                            <td class="text-center">${btnEscaneo}</td>
                            <td class="text-center">${btnModerno}</td>
                            <td class="text-end text-success">${simbolo} ${parseFloat(p.ingresos || 0).toFixed(2)}</td>
                            <td class="text-end text-danger">${simbolo} ${parseFloat(p.descuentos || 0).toFixed(2)}</td>
                            <td class="text-end fw-bold text-dark">${simbolo} ${parseFloat(p.neto || 0).toFixed(2)}</td>
                            <td class="text-center pe-4">
                                <div class="d-flex justify-content-center gap-1">
                                    <button class="btn btn-sm ${p.bloqueado?'btn-danger':'btn-dark'} rounded-pill px-3 btn-candado-planilla" data-id="${p.id}">
                                        <i class="bi bi-${p.bloqueado?'lock-fill':'unlock-fill'}"></i>
                                    </button>
                                    ${!p.bloqueado ? `
                                        <button class="btn btn-sm btn-outline-primary rounded-pill px-3 btn-editar-planilla" data-id="${p.id}"><i class="bi bi-pencil"></i></button>
                                        <button class="btn btn-sm btn-outline-danger rounded-pill px-3 btn-borrar-planilla" data-id="${p.id}"><i class="bi bi-trash"></i></button>
                                    ` : ''}
                                </div>
                            </td>
                        </tr>`;
                });

                document.getElementById('lbl_tot_planillas').innerText = data.data.length;
                document.getElementById('lbl_tot_anios').innerText = aniosUnicos.size;
                document.getElementById('lbl_tot_cerradas').innerText = countCerradas;
                document.getElementById('lbl_tot_sinscan').innerText = countSinScan;
                divMetricas.classList.remove('d-none');

                let htmlCajas = '';
                for (const [moneda, datos] of Object.entries(totalesPorMoneda)) {
                    htmlCajas += `
                        <div class="col-md-4">
                            <div class="card bg-white border-0 shadow-sm rounded-4 border-top border-4 border-primary h-100">
                                <div class="card-body p-4">
                                    <h6 class="text-uppercase fw-bolder text-secondary mb-3">Historial en ${moneda}</h6>
                                    <div class="d-flex justify-content-between mb-2">
                                        <span class="text-muted fw-semibold">Total Ingresos:</span>
                                        <span class="text-success fw-bold">${datos.simbolo} ${datos.ingresos.toFixed(2)}</span>
                                    </div>
                                    <div class="d-flex justify-content-between mb-2">
                                        <span class="text-muted fw-semibold">Total Descuentos:</span>
                                        <span class="text-danger fw-bold">${datos.simbolo} ${datos.descuentos.toFixed(2)}</span>
                                    </div>
                                    <hr class="my-2 opacity-25">
                                    <div class="d-flex justify-content-between align-items-center mt-2">
                                        <span class="text-dark fw-bolder">TOTAL NETO:</span>
                                        <span class="fs-5 fw-bolder text-primary">${datos.simbolo} ${datos.neto.toFixed(2)}</span>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                }
                
                if (htmlCajas !== '') {
                    divResumenMulti.innerHTML = htmlCajas;
                    divResumenMulti.classList.remove('d-none');
                }
            });
        }

        // ==========================================
        // 💾 MOTORES DE PERSISTENCIA
        // ==========================================
        function cargarDatosEdicion(btn) {
            const id = btn.dataset.id;
            modoEdicionId = id;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            
            fetch(`/legajo/obtener_detalle_planilla_historica/${id}`)
            .then(res => res.json()).then(data => {
                btn.innerHTML = '<i class="bi bi-pencil"></i>';
                if(data.estado !== 'ok') return;

                limpiarFormularioManual();
                document.getElementById('pills-tab').parentElement.style.display = 'none'; 
                document.getElementById('pills-manual-tab').click();

                const mesesMap = {"Enero":"01", "Febrero":"02", "Marzo":"03", "Abril":"04", "Mayo":"05", "Junio":"06", "Julio":"07", "Agosto":"08", "Septiembre":"09", "Octubre":"10", "Noviembre":"11", "Diciembre":"12"};
                document.getElementById('ph_periodo').value = `${data.cabecera.anio}-${mesesMap[data.cabecera.mes]}`;
                document.getElementById('ph_moneda').value = (data.cabecera.moneda === 'Documento Escaneado') ? "Soles" : data.cabecera.moneda;
                
                document.getElementById('ph_cargo').value = data.cabecera.cargo || '';
                document.getElementById('ph_unidad').value = data.cabecera.unidad || '';
                document.getElementById('ph_nivel').value = data.cabecera.nivel || '';
                document.getElementById('ph_regimen').value = data.cabecera.regimen || '';
                document.getElementById('ph_condicion').value = data.cabecera.condicion || '';
                document.getElementById('ph_pension').value = data.cabecera.pension || '';
                document.getElementById('ph_dias').value = data.cabecera.dias_laborados || 30;
                document.getElementById('ph_faltas').value = data.cabecera.faltas || 0;
                document.getElementById('ph_observaciones').value = data.cabecera.observaciones || '';

                data.conceptos.forEach(c => agregarFilaConcepto(c.tipo, c.descripcion, c.monto));
                divFormulario.style.display = 'block';
                divFormulario.scrollIntoView({ behavior: 'smooth' });
                calcularTotalesHistoricos();
            });
        }

        function guardarPlanillaManual(btn) {
            const periodo = document.getElementById('ph_periodo').value;
            if(!periodo) { alert("Indique Mes/Año"); return; }
            const [anio, mesNum] = periodo.split('-');
            const meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

            const datos = {
                id_personal: config.idPersonal, 
                anio: anio, 
                mes: meses[parseInt(mesNum)-1],
                moneda: document.getElementById('ph_moneda').value,
                cargo: document.getElementById('ph_cargo').value,
                unidad: document.getElementById('ph_unidad').value,
                nivel: document.getElementById('ph_nivel').value,
                regimen: document.getElementById('ph_regimen').value,
                condicion: document.getElementById('ph_condicion').value,
                pension: document.getElementById('ph_pension').value,
                dias_laborados: document.getElementById('ph_dias').value,
                faltas: document.getElementById('ph_faltas').value,
                observaciones: document.getElementById('ph_observaciones').value,
                total_ingresos: document.getElementById('ph_lbl_ingresos').innerText,
                total_descuentos: document.getElementById('ph_lbl_descuentos').innerText,
                monto_neto: document.getElementById('ph_lbl_neto').innerText,
                conceptos: []
            };

            tablaConceptos.querySelectorAll('tr').forEach(tr => {
                datos.conceptos.push({
                    tipo: tr.querySelector('.ph-tipo').value,
                    descripcion: tr.querySelector('.ph-desc').value,
                    monto: parseFloat(tr.querySelector('.ph-monto').value) || 0
                });
            });

            btn.disabled = true;
            let url = modoEdicionId ? `/legajo/actualizar_planilla_historica/${modoEdicionId}` : config.urlGuardar;
            let method = modoEdicionId ? 'PUT' : 'POST';

            fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': config.csrf },
                body: JSON.stringify(datos)
            }).then(res => res.json()).then(data => {
                if(data.estado === 'ok') { 
                    Swal.fire('Guardado', 'Planilla histórica guardada correctamente.', 'success');
                    divFormulario.style.display = 'none'; 
                    modoEdicionId = null; 
                    cargarPlanillasGuardadas(); 
                } else {
                    Swal.fire('Error', data.mensaje, 'error');
                }
            }).finally(() => btn.disabled = false);
        }

        function subirArchivoDocumento(btn) {
            const periodo = document.getElementById('file_periodo').value;
            const archivoInput = document.getElementById('file_documento');
            if(!periodo || archivoInput.files.length === 0) { 
                Swal.fire('Atención', 'Debe seleccionar un periodo y un archivo PDF.', 'warning');
                return; 
            }

            const formData = new FormData();
            formData.append('id_personal', config.idPersonal);
            formData.append('periodo', periodo);
            formData.append('archivo', archivoInput.files[0]);

            btn.disabled = true;
            fetch(config.urlSubir, { method: 'POST', headers: { 'X-CSRFToken': config.csrf }, body: formData })
            .then(res => res.json()).then(data => {
                if(data.estado === 'ok') { 
                    Swal.fire('Subido', 'Archivo original anexado al historial.', 'success');
                    divFormulario.style.display = 'none'; 
                    cargarPlanillasGuardadas(); 
                } else {
                    Swal.fire('Error', data.mensaje, 'error');
                }
            }).finally(() => btn.disabled = false);
        }

        function generarPDF(btn) {
            const id = btn.dataset.id;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
            fetch(config.urlGenerarPdf.replace('0', id), { method: 'POST', headers: { 'X-CSRFToken': config.csrf }})
            .then(res => res.json()).then(data => {
                if(data.estado === 'ok') {
                    Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: 'Boleta digital regenerada.', showConfirmButton: false, timer: 2000});
                    cargarPlanillasGuardadas();
                } else {
                    Swal.fire('Error', data.mensaje, 'error');
                }
            });
        }

        function ejecutarAccion(btn, url, metodo) {
            btn.disabled = true;
            fetch(url, { method: metodo, headers: { 'X-CSRFToken': config.csrf }})
            .then(res => res.json())
            .then(data => {
                if (data.estado === 'ok') {
                    Swal.fire('Eliminado', 'El registro fue borrado.', 'success');
                } else {
                    Swal.fire('Atención', data.mensaje, 'warning');
                }
                cargarPlanillasGuardadas();
            }).catch(err => {
                cargarPlanillasGuardadas();
            });
        }

        function agregarFilaConcepto(tipo, desc = '', monto = 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>
                    <select class="form-select form-select-sm ph-tipo fw-bold text-secondary">
                        <option value="INGRESO" ${tipo==='INGRESO'?'selected':''}>Ingreso (+)</option>
                        <option value="DESCUENTO" ${tipo==='DESCUENTO'?'selected':''}>Descuento (-)</option>
                        <option value="EXCEPCIONAL" ${tipo==='EXCEPCIONAL'?'selected':''}>Excepcional (+)</option>
                        <option value="APORTE" ${tipo==='APORTE'?'selected':''}>Aporte Muni (No afecta Neto)</option>
                    </select>
                </td>
                <td><input type="text" class="form-control form-control-sm ph-desc" value="${desc}"></td>
                <td><input type="number" step="0.01" class="form-control form-control-sm ph-monto text-end fw-bold" value="${parseFloat(monto).toFixed(2)}"></td>
                <td class="text-center"><button class="btn btn-sm btn-outline-danger btn-eliminar-fila"><i class="bi bi-trash"></i></button></td>`;
            tablaConceptos.appendChild(tr);
            calcularTotalesHistoricos();
        }

        function limpiarFormularioManual() {
            tablaConceptos.innerHTML = '';
            document.getElementById('ph_periodo').value = '';
            document.getElementById('ph_cargo').value = '';
            document.getElementById('ph_unidad').value = '';
            document.getElementById('ph_nivel').value = '';
            document.getElementById('ph_regimen').value = '';
            document.getElementById('ph_condicion').value = '';
            document.getElementById('ph_pension').value = '';
            document.getElementById('ph_dias').value = '30';
            document.getElementById('ph_faltas').value = '0';
            document.getElementById('ph_observaciones').value = '';
            document.getElementById('ph_lbl_ingresos').innerText = '0.00';
            document.getElementById('ph_lbl_descuentos').innerText = '0.00';
            document.getElementById('ph_lbl_neto').innerText = '0.00';
        }

        cargarPlanillasGuardadas();
    });
}