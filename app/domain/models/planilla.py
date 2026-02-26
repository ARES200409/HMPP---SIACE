class Planilla:
    def __init__(self, id_planilla, anio, mes, tipo_planilla, estado, fecha_apertura=None, total_trabajadores=0, total_monto=0):
        self.id_planilla = id_planilla
        self.anio = anio
        self.mes = mes
        self.tipo_planilla = tipo_planilla
        self.estado = estado
        self.fecha_apertura = fecha_apertura
        # Estos dos últimos son campos calculados para la vista
        self.total_trabajadores = total_trabajadores
        self.total_monto = total_monto

class DetallePlanilla:
    def __init__(self, id_detalle, id_personal, nombre_completo, dni, cargo, sistema_pensionario, sueldo_basico, faltas, onp_afp, neto):
        self.id_detalle = id_detalle
        self.id_personal = id_personal
        self.nombre_completo = nombre_completo
        self.dni = dni
        self.cargo = cargo
        self.sistema_pensionario = sistema_pensionario
        self.sueldo_basico = sueldo_basico
        self.faltas = faltas
        self.onp_afp = onp_afp
        self.neto = neto