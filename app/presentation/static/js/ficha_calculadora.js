document.addEventListener('DOMContentLoaded', function() {
    console.log("✅ Calculadora de Ficha Municipal ACTIVADA (Base 30 + Configuración de Afectación de Bonos)");

    // =========================================================
    // 1. TASAS DE PENSIONES
    // =========================================================
    const TASAS_PENSION = {
        'ONP': 0.1300,        // 13.00%
        'HABITAT': 0.1247,    // Variable
        'INTEGRA': 0.1244,
        'PROFUTURO': 0.1259,
        'PRIMA': 0.1248,
        'SIN REGIMEN': 0.00,
        '': 0.00
    };

    // =========================================================
    // 2. DETECTAR DÍAS REALES Y CONFIGURAR BASE
    // =========================================================
    const mes = parseInt(document.getElementById('mes_planilla')?.value) || 0;
    const anio = parseInt(document.getElementById('anio_planilla')?.value) || 0;
    
    function obtenerDiasDelMes(m, a) {
        if (m > 0 && a > 0) return new Date(a, m, 0).getDate();
        return 30; // Fallback
    }

    const diasTotalesMes = obtenerDiasDelMes(mes, anio);
    
    // 🔥 CONFIGURACIÓN DE BASE DE CÁLCULO
    const baseCalculo = 30; // Siempre 30 para matemática interna
    // const baseCalculo = diasTotalesMes; // Comenta la de arriba y descomenta esta para Días Reales

    // 🔥 CONFIGURACIÓN DE AFECTACIÓN: ¿La falta descuenta también de bonos y movilidad?
    // false = Solo descuenta del Sueldo Básico.
    // true  = Descuenta de (Sueldo + Bonos + Movilidad).
    const DESCUENTO_AFECTA_BONOS = false; 

    console.log(`📅 Mes: ${mes}/${anio}. Días Reales: ${diasTotalesMes}. Base Faltas: ${baseCalculo}. ¿Afecta bonos?: ${DESCUENTO_AFECTA_BONOS}`);

    // --- ACTUALIZACIÓN DE ELEMENTOS VISUALES (SUNAT / Header) ---
    const headerDias = document.getElementById('lbl_dias_mes_sunat_header');
    if (headerDias) headerDias.innerText = diasTotalesMes;

    const inputGuardarDias = document.getElementById('input_dias_laborados');
    if (inputGuardarDias && !inputGuardarDias.value) {
        inputGuardarDias.value = diasTotalesMes; 
    }
    
    const formulaLabel = document.getElementById('lbl_dias_mes_sunat');
    if (formulaLabel) formulaLabel.innerText = diasTotalesMes;

    // =========================================================
    // 3. OBTENER ELEMENTOS DEL DOM
    // =========================================================
    const getEl = (id) => document.getElementById(id);
    const getVal = (id) => {
        const el = document.getElementById(id);
        return el ? (parseFloat(el.value) || 0) : 0;
    };

    const elSueldo = getEl('input_sueldo');
    const elMontoFalta = getEl('output_monto_falta');
    const elSistema = getEl('select_sistema');
    const elPensionInput = getEl('input_pension');
    const elEssaludPatronal = getEl('output_essalud_patronal');
    const elMonAseg = getEl('total_mon_aseg'); 
    const txtTotalDesc = getEl('txt_total_descuentos'); 
    const txtNeto = getEl('txt_neto_cobrar'); 

    const elTasaSctr = getEl('input_tasa_sctr');
    const elSctrMonto = getEl('input_sctr');
    const chkSindicato = getEl('chk_sindicalizado');
    const inputSindicato = getEl('input_sindicato');
    
    const inputDiasFalta = document.querySelector('input[name="dias_falta"]');
    const inputDiasSubsidio = document.querySelector('input[name="dias_subsidiados"]');
    const inputDiasComputables = document.querySelector('input[name="dias_computables"]');

    // =========================================================
    // 4. FUNCIÓN MAESTRA DE CÁLCULO
    // =========================================================
    function recalcularTodo() {
        if (!elSueldo) return;

        const sueldo = getVal('input_sueldo');
        const asigFam = getVal('input_asig_familiar'); 
        const viatico = getVal('input_viatico'); 
        const reintegros = getVal('input_reintegros');
        const bonos = getVal('input_bonos');
        
        const diasFalta = inputDiasFalta ? (parseFloat(inputDiasFalta.value) || 0) : 0;
        const diasSubsidio = inputDiasSubsidio ? (parseFloat(inputDiasSubsidio.value) || 0) : 0;

        // 1. CÁLCULO DE DÍAS COMPUTABLES AUTOMÁTICO
        if (inputDiasComputables) {
            // 🔥 Cálculo basado en baseCalculo (30)
            let diasComputablesCalculados = baseCalculo - diasFalta - diasSubsidio;
            // --- Comentado original: let diasComputablesCalculados = diasTotalesMes - diasFalta - diasSubsidio; ---
            
            if (diasComputablesCalculados < 0) diasComputablesCalculados = 0; 
            inputDiasComputables.value = diasComputablesCalculados;
        }

        // 2. Calcular Descuento por Faltas (Dinero)
        let montoDescuentoFalta = 0;
        if (diasFalta > 0) {
            // 🔥 Lógica de afectación de bonos
            let baseMontoParaDescuento = sueldo;
            if (DESCUENTO_AFECTA_BONOS) {
                baseMontoParaDescuento = sueldo + bonos + viatico;
            }

            // 🔥 División por baseCalculo (30)
            montoDescuentoFalta = (baseMontoParaDescuento / baseCalculo) * diasFalta;
            
            // --- Comentado original: montoDescuentoFalta = (sueldo / diasTotalesMes) * diasFalta; ---
        }
        if (elMontoFalta) elMontoFalta.value = montoDescuentoFalta.toFixed(2);

        // 3. Calcular Monto Asegurado (Base Imponible)
        let sueldoEfectivo = sueldo - montoDescuentoFalta;
        if (sueldoEfectivo < 0) sueldoEfectivo = 0;
        let montoAsegurado = sueldoEfectivo + asigFam + viatico + reintegros + bonos; 
        
        if (elMonAseg) elMonAseg.value = montoAsegurado.toFixed(2);

        // 4. Cálculo Automático de Pensión
        if (elSistema && elPensionInput) {
            let sistemaKey = elSistema.value.toUpperCase().trim();
            let tasa = TASAS_PENSION[sistemaKey] !== undefined ? TASAS_PENSION[sistemaKey] : 0;
            let pensionCalculada = montoAsegurado * tasa;
            
            if (tasa > 0 || sistemaKey === 'SIN REGIMEN') {
                 elPensionInput.value = pensionCalculada.toFixed(2);
            }
        }

        // 5. Aportes Empleador (9% Essalud)
        if (elEssaludPatronal) {
            let essalud = montoAsegurado * 0.09;
            elEssaludPatronal.value = essalud.toFixed(2);
        }

        // 5.1 Cálculo Automático del SCTR
        if (elTasaSctr && elSctrMonto) {
            let tasaSctrValue = parseFloat(elTasaSctr.value) || 0;
            if (tasaSctrValue > 0) {
                let montoCalculadoSctr = montoAsegurado * (tasaSctrValue / 100);
                elSctrMonto.value = montoCalculadoSctr.toFixed(2);
            } else {
                elSctrMonto.value = "0.00";
            }
        }

        // 6. Totales Finales
        let valPension = getVal('input_pension');
        let valFalta = parseFloat(elMontoFalta ? elMontoFalta.value : 0) || 0;
        let valRenta = getVal('input_renta');
        let valEssaludVida = getVal('input_essaludv');
        let valJudicial = getVal('input_judiciales');
        let valOtros = getVal('input_otros');
        
        let valSindicato = 0;
        if (chkSindicato && chkSindicato.checked) {
            valSindicato = getVal('input_sindicato');
        }

        let totalDescuentos = valPension + valFalta + valRenta + valEssaludVida + valJudicial + valOtros + valSindicato;
        
        let totalIngresosBrutos = sueldo + asigFam + viatico + reintegros + bonos; 
        let neto = totalIngresosBrutos - totalDescuentos;
        if (neto < 0) neto = 0;

        if (txtTotalDesc) txtTotalDesc.innerText = totalDescuentos.toFixed(2);
        if (txtNeto) txtNeto.innerText = neto.toFixed(2);
    }

    // =========================================================
    // 4.5. LÓGICA DEL SWITCH DEL SINDICATO
    // =========================================================
    if (chkSindicato && inputSindicato) {
        const toggleSindicato = () => {
            if (chkSindicato.checked) {
                inputSindicato.removeAttribute('readonly');
                inputSindicato.classList.remove('bg-light', 'text-muted');
            } else {
                inputSindicato.setAttribute('readonly', 'true');
                inputSindicato.classList.add('bg-light', 'text-muted');
                inputSindicato.value = '0.00';
            }
            recalcularTodo(); 
        };
        chkSindicato.addEventListener('change', toggleSindicato);
        toggleSindicato();
    }

    // =========================================================
    // 5. LISTENERS BÁSICOS DE CÁLCULO
    // =========================================================
    const idsEscuchados = [
        'input_sueldo', 'input_asig_familiar', 'input_viatico', 'input_reintegros', 'input_bonos', 
        'input_pension', 'input_essaludv', 'input_renta', 'input_judiciales', 'input_otros', 
        'input_sctr', 'input_sctr_onp', 'input_cts', 'input_tasa_sctr', 'input_sindicato'
    ];

    idsEscuchados.forEach(id => {
        let el = getEl(id);
        if (el) {
            el.addEventListener('input', recalcularTodo);
            el.addEventListener('change', recalcularTodo);
        }
    });

    if (inputDiasFalta) inputDiasFalta.addEventListener('input', recalcularTodo);
    if (inputDiasSubsidio) inputDiasSubsidio.addEventListener('input', recalcularTodo);

    if (elSistema) {
        elSistema.addEventListener('change', function() {
            recalcularTodo();
            if(elPensionInput) {
                elPensionInput.style.backgroundColor = "#fff3cd"; 
                setTimeout(() => elPensionInput.style.backgroundColor = "", 300);
            }
        });
    }

    // =========================================================
    // 6. MAGIA DINÁMICA: EMPAQUETADO DE DATOS (JSON)
    // =========================================================
    const btnAddIngreso = document.getElementById('btn-add-ingreso');
    const inputBonos = document.getElementById('input_bonos');
    const glosaBonos = document.getElementById('glosa_bonos');
    const templateIngreso = document.querySelector('#template-ingreso-row tr');

    const btnAddDescuento = document.getElementById('btn-add-descuento');
    const inputOtros = document.getElementById('input_otros');
    const glosaOtros = document.getElementById('glosa_otros');
    const templateDescuento = document.querySelector('#template-descuento-row tr');

    const btnAddAguinaldo = document.getElementById('btn-add-aguinaldo');
    const templateAguinaldo = document.querySelector('#template-aguinaldo-row tr');

    if (btnAddIngreso && templateIngreso) {
        btnAddIngreso.addEventListener('click', function() {
            let newRow = templateIngreso.cloneNode(true);
            this.closest('tr').parentNode.insertBefore(newRow, this.closest('tr'));
            attachEvents(newRow);
        });
    }

    if (btnAddDescuento && templateDescuento) {
        btnAddDescuento.addEventListener('click', function() {
            let newRow = templateDescuento.cloneNode(true);
            this.closest('tr').parentNode.insertBefore(newRow, this.closest('tr'));
            attachEvents(newRow);
        });
    }

    if (btnAddAguinaldo && templateAguinaldo) {
        btnAddAguinaldo.addEventListener('click', function() {
            let newRow = templateAguinaldo.cloneNode(true);
            document.getElementById('tbody-aguinaldos').appendChild(newRow);
            attachEvents(newRow);
        });
    }

    document.querySelectorAll('.dinamico-row').forEach(row => attachEvents(row));

    function attachEvents(row) {
        row.querySelector('.btn-remove').addEventListener('click', function() {
            row.remove();
            recalcularDinamicos();
        });
        row.querySelector('select').addEventListener('change', () => recalcularDinamicos());
        row.querySelector('input').addEventListener('input', () => recalcularDinamicos());
    }

    function recalcularDinamicos() {
        let totalIngresos = 0;
        let glosasIngresos = [];
        let totalDescuentos = 0;
        let glosasDescuentos = [];
        let totalAguinaldos = 0;
        let glosasAguinaldos = [];
        let arrayConceptos = []; 

        document.querySelectorAll('.val-ingreso').forEach((inp, index) => {
            let select = document.querySelectorAll('.sel-concepto-ingreso')[index];
            let val = parseFloat(inp.value) || 0;
            if (val > 0 && select.value !== '' && inp.closest('.dinamico-row').offsetParent !== null) {
                totalIngresos += val;
                let idConcepto = select.value;
                let nombreConcepto = select.options[select.selectedIndex].getAttribute('data-nombre') || 'Bono';
                glosasIngresos.push(`${nombreConcepto}: ${val.toFixed(2)}`);
                arrayConceptos.push({ id_concepto: parseInt(idConcepto), tipo: 'INGRESO', monto: val });
            }
        });
        if(inputBonos) inputBonos.value = totalIngresos.toFixed(2);
        if(glosaBonos) glosaBonos.value = glosasIngresos.join(' + ');

        document.querySelectorAll('.val-descuento').forEach((inp, index) => {
            let select = document.querySelectorAll('.sel-concepto-descuento')[index];
            let val = parseFloat(inp.value) || 0;
            if (val > 0 && select.value !== '' && inp.closest('.dinamico-row').offsetParent !== null) {
                totalDescuentos += val;
                let idConcepto = select.value;
                let nombreConcepto = select.options[select.selectedIndex].getAttribute('data-nombre') || 'Deduccion';
                glosasDescuentos.push(`${nombreConcepto}: ${val.toFixed(2)}`);
                arrayConceptos.push({ id_concepto: parseInt(idConcepto), tipo: 'DESCUENTO', monto: val });
            }
        });
        if(inputOtros) inputOtros.value = totalDescuentos.toFixed(2);
        if(glosaOtros) glosaOtros.value = glosasDescuentos.join(' + ');

        document.querySelectorAll('.val-aguinaldo').forEach((inp, index) => {
            let select = document.querySelectorAll('.sel-concepto-aguinaldo')[index];
            let val = parseFloat(inp.value) || 0;
            if (val > 0 && select.value !== '' && inp.closest('.dinamico-row').offsetParent !== null) {
                totalAguinaldos += val;
                let idConcepto = select.value;
                let nombreConcepto = select.options[select.selectedIndex].getAttribute('data-nombre') || 'Aguinaldo';
                glosasAguinaldos.push(`${nombreConcepto}: ${val.toFixed(2)}`);
                arrayConceptos.push({ id_concepto: parseInt(idConcepto), tipo: 'AGUINALDO', monto: val });
            }
        });

        const inputAguiTotal = document.getElementById('input_aguinaldos_total');
        const glosaAgui = document.getElementById('glosa_aguinaldos');
        if(inputAguiTotal) inputAguiTotal.value = totalAguinaldos.toFixed(2);
        if(glosaAgui) glosaAgui.value = glosasAguinaldos.join(' + ');

        const hiddenJsonInput = document.getElementById('json_conceptos');
        if(hiddenJsonInput) hiddenJsonInput.value = JSON.stringify(arrayConceptos);

        recalcularTodo(); 
    }

    // =========================================================
    // 7. AUTO-RELLENO SIAF/S10
    // =========================================================
    const selectActividad = document.getElementById('select_actividad');
    const inputMeta = document.getElementById('input_meta');
    const inputNp = document.getElementById('input_np');

    if (selectActividad) {
        selectActividad.addEventListener('change', function() {
            const opcionSeleccionada = this.options[this.selectedIndex];
            if (this.value === "") {
                if (inputMeta) inputMeta.value = "";
                if (inputNp) inputNp.value = "";
                return;
            }
            if (inputMeta) inputMeta.value = opcionSeleccionada.getAttribute('data-meta') || '';
            if (inputNp) inputNp.value = opcionSeleccionada.getAttribute('data-np') || '';
        });
        if (selectActividad.value !== "") selectActividad.dispatchEvent(new Event('change'));
    }

    setTimeout(() => {
        recalcularDinamicos();
        recalcularTodo();
    }, 300);
});