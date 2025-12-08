# RUTA: app/application/forms.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Length, Regexp, Optional, Email, NumberRange, EqualTo, ValidationError
from wtforms import DecimalField, StringField, PasswordField, SubmitField, SelectField, DateField, TextAreaField, FileField, BooleanField
from datetime import datetime, timedelta

# ===== VALIDADORES PERSONALIZADOS (ANTES DE LAS CLASES) =====

def validate_password_not_username(form, field):
    """Valida que la contraseña NO sea igual al nombre de usuario."""
    if field.data and form.username.data and field.data.lower() == form.username.data.lower():
        raise ValidationError('La contraseña no puede ser igual al nombre de usuario.')

def validate_password_not_new_username(form, field):
    """Valida que la nueva contraseña NO sea igual al nuevo nombre de usuario."""
    if field.data:
        if form.nueva_username.data and field.data.lower() == form.nueva_username.data.lower():
            raise ValidationError('La contraseña no puede ser igual al nombre de usuario.')
        elif not form.nueva_username.data and form.username.data and field.data.lower() == form.username.data.lower():
            raise ValidationError('La contraseña no puede ser igual al nombre de usuario.')

def validate_fecha_nacimiento(form, field):
    """Valida que la fecha de nacimiento sea válida: no en el futuro y edad mínima de 18 años."""
    if field.data:
        hoy = datetime.now().date()
        
        # Validar que no sea en el futuro
        if field.data > hoy:
            raise ValidationError('La fecha de nacimiento no puede ser en el futuro.')
        
        # Validar que tenga al menos 18 años
        edad_minima = hoy - timedelta(days=18*365.25)
        if field.data > edad_minima:
            raise ValidationError('El empleado debe tener al menos 18 años de edad.')
        
        # Validar que no sea demasiado antiguo (más de 100 años)
        edad_maxima = hoy - timedelta(days=100*365.25)
        if field.data < edad_maxima:
            raise ValidationError('La fecha de nacimiento no puede ser hace más de 100 años.')

def validate_fecha_ingreso(form, field):
    """Valida que la fecha de ingreso sea válida respecto a la fecha de nacimiento e hoy."""
    if field.data:
        hoy = datetime.now().date()
        
        # Validar que no sea en el futuro
        if field.data > hoy:
            raise ValidationError('La fecha de ingreso no puede ser en el futuro.')
        
        # Validar que sea después de la fecha de nacimiento
        if form.fecha_nacimiento.data and field.data < form.fecha_nacimiento.data:
            raise ValidationError('La fecha de ingreso no puede ser anterior a la fecha de nacimiento.')
        
        # Validar que no sea antes de 1950
        if field.data.year < 1950:
            raise ValidationError('La fecha de ingreso parece ser demasiado antigua.')

def validate_dni_formato(form, field):
    """Valida el formato del DNI peruano (8 dígitos)."""
    if field.data:
        if not field.data.isdigit() or len(field.data) != 8:
            raise ValidationError('El DNI debe contener exactamente 8 dígitos numéricos.')

def validate_telefono(form, field):
    """Valida el formato del teléfono."""
    if field.data:
        telefono_limpio = field.data.replace(" ", "").replace("-", "")
        
        if not telefono_limpio.isdigit():
            raise ValidationError('El teléfono solo debe contener números, espacios y guiones.')
        
        if len(telefono_limpio) < 7 or len(telefono_limpio) > 15:
            raise ValidationError('El teléfono debe tener entre 7 y 15 dígitos.')

# ===== FIN DE VALIDADORES PERSONALIZADOS =====


class LoginForm(FlaskForm):
    # 1. Agregamos el campo de selección de Rol
    role = SelectField('Tipo de Usuario', choices=[
        ('', '-- Seleccionar Rol --'),
        ('Sistemas', 'Sistemas'),
        ('RRHH', 'Recursos Humanos'),
        ('AdministradorLegajos', 'Administrador de Legajos'),
        ('Personal', 'Personal / Empleado')
    ], validators=[DataRequired(message="Debe seleccionar un rol.")])

    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Mantenerme conectado')
    submit = SubmitField('Iniciar Sesión')

class TwoFactorForm(FlaskForm):
    code = StringField('Código de 6 dígitos', validators=[
        DataRequired(),
        Length(min=6, max=6, message="El código debe tener 6 dígitos."),
        Regexp('^[0-9]*$', message="El código solo debe contener números.")
    ])
    submit = SubmitField('Verificar y Entrar')

class FiltroPersonalForm(FlaskForm):
    dni = StringField('Buscar por DNI', validators=[Optional(), Length(max=8)])
    nombres = StringField('Buscar por Nombre o Apellidos', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Buscar')

class PersonalForm(FlaskForm):
    """Formulario para crear y editar los datos de una persona."""
    dni = StringField('DNI', validators=[
        DataRequired(message="El DNI es obligatorio."),
        Length(min=8, max=8, message="El DNI debe tener 8 dígitos."),
        validate_dni_formato
    ])
    nombres = StringField('Nombres', validators=[
        DataRequired(message="Los nombres son obligatorios."),
        Length(min=2, max=50, message="Los nombres deben tener entre 2 y 50 caracteres.")
    ])
    apellidos = StringField('Apellidos', validators=[
        DataRequired(message="Los apellidos son obligatorios."),
        Length(min=2, max=50, message="Los apellidos deben tener entre 2 y 50 caracteres.")
    ])
    
    sexo = SelectField('Sexo', choices=[('', '-- Seleccione --'), ('M', 'Masculino'), ('F', 'Femenino')], 
                      validators=[DataRequired(message="Debe seleccionar el sexo.")],
                      default='')
    
    fecha_nacimiento = DateField('Fecha de Nacimiento', format='%Y-%m-%d', 
                                validators=[
                                    DataRequired(message="La fecha de nacimiento es obligatoria."),
                                    validate_fecha_nacimiento
                                ])
    
    telefono = StringField('Teléfono', validators=[
        Optional(),
        Length(max=20, message="El teléfono no debe exceder 20 caracteres."),
        validate_telefono
    ])
    
    email = StringField('Correo Electrónico', validators=[
        Optional(),
        Email(message="Por favor ingrese un correo electrónico válido."),
        Length(max=100, message="El correo no debe exceder 100 caracteres.")
    ])
    
    direccion = StringField('Dirección', validators=[
        Optional(),
        Length(max=200, message="La dirección no debe exceder 200 caracteres.")
    ])
    
    estado_civil = SelectField('Estado Civil', 
                              choices=[
                                  ('', '-- Selecciona un estado civil --'),
                                  ('Soltero', 'Soltero'),
                                  ('Casado', 'Casado'),
                                  ('Divorciado', 'Divorciado'),
                                  ('Viudo', 'Viudo')
                              ],
                              validators=[Optional()])
    
    nacionalidad = StringField('Nacionalidad', validators=[
        DataRequired(message="La nacionalidad es obligatoria."),
        Length(min=2, max=50, message="La nacionalidad debe tener entre 2 y 50 caracteres.")
    ], default='Peruana')
    
    id_unidad = SelectField('Unidad Administrativa', coerce=str, 
                           validators=[Optional()],
                           default='0')
    
    fecha_ingreso = DateField('Fecha de Ingreso', format='%Y-%m-%d', 
                             validators=[
                                 Optional(),
                                 validate_fecha_ingreso
                             ])
    
    submit = SubmitField('Registrar Personal')

    # def validate_id_unidad(self, field):
    #     """Valida que se haya seleccionado una unidad válida."""
    #     if field.data == '0' or not field.data:
    #         raise ValidationError('Debe seleccionar una unidad administrativa válida.')

class DocumentoForm(FlaskForm):
    id_seccion = SelectField('Sección del Legajo', coerce=int, validators=[NumberRange(min=1, message="Debe seleccionar una sección.")])
    id_tipo = SelectField('Tipo de Documento', coerce=int, validators=[NumberRange(min=1, message="Debe seleccionar un tipo de documento.")])
    descripcion = TextAreaField('Descripción (Opcional)', validators=[Optional(), Length(max=500)])
    fecha_emision = DateField('Fecha de Emisión', format='%Y-%m-%d', validators=[Optional()],
                              description='Fecha del documento. Si no se especifica, se usará la fecha de hoy.')
    archivo = FileField('Seleccionar Archivo', validators=[
        DataRequired(message="Debe seleccionar un archivo."),
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx'], '¡Solo se permiten archivos PDF, de imagen (PNG, JPG) o de Office (DOCX, XLSX)!')
    ])
    submit = SubmitField('Subir Documento')


# 🚨 CLASE AÑADIDA PARA EL MÓDULO DE SISTEMAS (Gestión de Usuarios) 🚨
class UserManagementForm(FlaskForm):
    """
    Formulario para la creación y edición de usuarios por el Encargado de Sistemas.
    Incluye campos para el rol, la activación y cambio de contraseña.
    """
    # Campos básicos - en creación son requeridos, en edición se usan los nuevos_*
    username = StringField('Nombre de Usuario', validators=[Optional(), Length(min=4, max=50)])
    email = StringField('Correo Electrónico', validators=[Optional(), Email(), Length(max=100)])
    
    # Campo para el Rol (los IDs 1, 3, etc. que verificamos en la BD)
    # Los choices se deben cargar dinámicamente en la ruta 'crear_usuario'
    # En edición este campo no se usa
    id_rol = SelectField('Rol de Acceso', coerce=int, validators=[Optional()], choices=[]) 
    
    # Campo de Contraseña para CREAR usuario
    password = PasswordField('Contraseña (Solo para Nuevo Usuario)', validators=[
        Optional(), 
        Length(min=6, message='La contraseña debe tener al menos 6 caracteres.'),
        EqualTo('confirm', message='Las contraseñas deben coincidir.'),
        validate_password_not_username
    ])
    confirm = PasswordField('Confirmar Contraseña')
    
    # Campos para EDITAR usuario
    nueva_username = StringField('Nuevo Nombre de Usuario (Opcional)', validators=[
        Optional(),
        Length(min=4, max=50, message='El usuario debe tener entre 4 y 50 caracteres.')
    ])
    
    nuevo_email = StringField('Nuevo Correo Electrónico (Opcional)', validators=[
        Optional(),
        Email(message='Por favor ingresa un correo electrónico válido.'),
        Length(max=100)
    ])
    
    # Campo de Nueva Contraseña para EDITAR usuario
    nueva_password = PasswordField('Nueva Contraseña (Opcional)', validators=[
        Optional(),
        Length(min=6, message='La contraseña debe tener al menos 6 caracteres.'),
        EqualTo('nueva_confirm', message='Las nuevas contraseñas deben coincidir.'),
        validate_password_not_new_username
    ])
    nueva_confirm = PasswordField('Confirmar Nueva Contraseña')
    
    # Campo Activo/Inactivo
    activo = BooleanField('Usuario Activo') 
    
    submit = SubmitField('Guardar Cambios')

class ActualizarPersonalForm(FlaskForm):
    """
    Formulario para que los empleados actualicen sus propios datos personales.
    Cumple con Ley 29733 - Art. 9 (Derecho de Rectificación).
    
    Solo permite modificar datos no críticos que el empleado puede cambiar.
    """
    telefono = StringField('Teléfono de Contacto', validators=[
        Optional(),
        Length(min=7, max=15, message="El teléfono debe tener entre 7 y 15 caracteres.")
    ])
    
    estado_civil = SelectField('Estado Civil', choices=[
        ('', '-- Selecciona un estado civil --'),
        ('Soltero', 'Soltero'),
        ('Casado', 'Casado'),
        ('Divorciado', 'Divorciado'),
        ('Viudo', 'Viudo')
    ], validators=[Optional()])
    
    email_personal = StringField('Email Personal', validators=[
        Optional(),
        Email(message="Por favor, introduce un email válido.")
    ])
    
    direccion = StringField('Dirección', validators=[
        Optional(),
        Length(max=200, message="La dirección no puede superar 200 caracteres.")
    ])
    
    submit = SubmitField('Guardar Cambios')

class BulkUploadForm(FlaskForm):
    """Formulario para la subida masiva de personal desde un archivo Excel."""
    excel_file = FileField('Archivo Excel (.xlsx)', validators=[
        DataRequired(message="Por favor, seleccione un archivo."),
        FileAllowed(['xlsx'], '¡Solo se permiten archivos de Excel (.xlsx)!')
    ])
    submit = SubmitField('Procesar Archivo')

class ContratoInicialForm(FlaskForm):
    """Formulario para registrar el primer contrato y cargo."""
    # Datos del Contrato
    id_tipo_contrato = SelectField('Tipo de Contrato', validators=[DataRequired()])
    fecha_inicio = DateField('Fecha de Inicio', format='%Y-%m-%d', validators=[DataRequired()])
    fecha_fin = DateField('Fecha de Fin (Opcional)', format='%Y-%m-%d', validators=[Optional()])
    sueldo = DecimalField('Sueldo Mensual (S/.)', places=2, validators=[DataRequired()])
    resolucion = StringField('N° Resolución / Documento', validators=[DataRequired(), Length(max=300)])
    
    # Datos del Cargo/Puesto
    id_cargo = SelectField('Cargo / Puesto', validators=[DataRequired()])
    id_unidad = SelectField('Unidad Administrativa', validators=[DataRequired()])
    
    submit = SubmitField('Guardar y Finalizar')