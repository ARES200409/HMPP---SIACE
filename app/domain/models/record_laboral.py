class RecordLaboral:
    def __init__(self, id_personal, anio, mes, basica=0, reunif=0, tph=0, familiar=0, movilidad=0, onp=0, tardanzas=0):
        self.id_personal = id_personal
        self.anio = anio
        self.mes = mes
        
        # --- INGRESOS (Según tu foto) ---
        self.basica = float(basica)
        self.reunif = float(reunif)
        self.tph = float(tph)
        self.familiar = float(familiar)
        self.movilidad = float(movilidad)
        
        # --- DESCUENTOS (Según tu foto) ---
        self.onp = float(onp)
        self.tardanzas = float(tardanzas)

    def calcular_total_ingresos(self):
        # Suma de la fila 'ING. BRUTO' del Excel
        return self.basica + self.reunif + self.tph + self.familiar + self.movilidad

    def calcular_total_descuentos(self):
        # Suma de la columna 'TOTAL DSCTOS'
        return self.onp + self.tardanzas

    def calcular_pago_neto(self):
        # Resultado final que se ve en 'NETO A PAGAR'
        return self.calcular_total_ingresos() - self.calcular_total_descuentos()