; Script de Inno Setup para Sistema de Legajo Digital HMPP
; Este script crea un instalador profesional .exe para Windows

#define MyAppName "Sistema Digital Escalafon HMPP"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "HMPP"
#define MyAppURL "https://github.com/carlosDaniel2004/Legajo-Digital-Diresa"
#define MyAppExeName "iniciar_aplicacion.bat"

[Setup]
; Información básica de la aplicación
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName=C:\LegajoDigitalHMPP
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
InfoBeforeFile=REQUISITOS_SISTEMA.md
OutputDir=instalador
OutputBaseFilename=LegajoDigital_HMPP_Setup_v{#MyAppVersion}
SetupIconFile=app\presentation\static\muni_logo.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Configuración de idioma
ShowLanguageDialog=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Archivos principales de la aplicación
Source: "*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "venv,__pycache__,.git,*.pyc,*.pyo,logs,temp_pdfs,temp_uploads,instalador,.env"
Source: "launcher.vbs"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Accesos directos en el menú inicio
; Usamos wscript.exe para ejecutar el VBS sin ventana
Name: "{group}\{#MyAppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\app\presentation\static\muni_logo.ico"

Name: "{group}\Verificar Sistema"; Filename: "{app}\verificar_sistema.py"; WorkingDir: "{app}"; IconFilename: "{sys}\shell32.dll"; IconIndex: 23
Name: "{group}\Documentación"; Filename: "{app}\README.md"; IconFilename: "{sys}\shell32.dll"; IconIndex: 70
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Accesos directos en el escritorio (opcional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\app\presentation\static\muni_logo.ico"

[Run]
; Verificar si Python está instalado
Filename: "python"; Parameters: "--version"; Flags: runhidden waituntilterminated; StatusMsg: "Verificando Python..."; Check: CheckPython

; Instalar dependencias de Python
Filename: "python"; Parameters: "-m pip install --upgrade pip"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Actualizando pip..."; Check: CheckPython
Filename: "python"; Parameters: "-m pip install -r requirements.txt"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Instalando dependencias de Python..."; Check: CheckPython

; Abrir documentación
Filename: "{app}\GUIA_RAPIDA.md"; Description: "Ver guía rápida de instalación"; Flags: postinstall skipifsilent shellexec nowait

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\temp_pdfs"
Type: filesandordirs; Name: "{app}\temp_uploads"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\*.pyc"
Type: files; Name: "{app}\*.log"

[Code]
var
  // Páginas de configuración
  DBConfigPage: TInputQueryWizardPage;
  UsersConfigPage: TInputQueryWizardPage;
  EmailConfigPage: TInputQueryWizardPage;

function CheckPython: Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function CheckSQLServer: Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('sc', 'query MSSQLSERVER', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or
            Exec('sc', 'query MSSQL$SQLEXPRESS', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function CheckODBC: Boolean;
var
  RegKey17: string;
  RegKey18: string;
begin
  RegKey17 := 'SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 17 for SQL Server';
  RegKey18 := 'SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server';
  Result := RegKeyExists(HKEY_LOCAL_MACHINE, RegKey17) or 
            RegKeyExists(HKEY_LOCAL_MACHINE_64, RegKey17) or
            RegKeyExists(HKEY_LOCAL_MACHINE, RegKey18) or
            RegKeyExists(HKEY_LOCAL_MACHINE_64, RegKey18);
end;

procedure InitializeWizard;
begin
  // Página 1: Configuración de Base de Datos
  DBConfigPage := CreateInputQueryPage(wpWelcome,
    'Configuración de Base de Datos',
    'Ingrese la información de conexión a SQL Server',
    'Esta información se usará para conectar la aplicación a la base de datos.');
  
  DBConfigPage.Add('Servidor SQL Server:', False);
  DBConfigPage.Add('Nombre de la Base de Datos:', False);
  DBConfigPage.Add('Usuario Administrador SQL (para crear BD):', False);
  DBConfigPage.Add('Contraseña del Administrador:', True);
  
  // Valores por defecto
  DBConfigPage.Values[0] := 'localhost';
  DBConfigPage.Values[1] := 'BaseDatosHMPP';
  DBConfigPage.Values[2] := 'sa';
  
  // Página 2: Usuarios de la Aplicación
  UsersConfigPage := CreateInputQueryPage(DBConfigPage.ID,
    'Usuarios de la Aplicación',
    'Configure los usuarios para la aplicación',
    'Se crearán dos usuarios: uno para operaciones normales y otro para administración.');
  
  UsersConfigPage.Add('Usuario de Aplicación:', False);
  UsersConfigPage.Add('Contraseña del Usuario de Aplicación:', True);
  UsersConfigPage.Add('Usuario Administrador de Sistemas:', False);
  UsersConfigPage.Add('Contraseña del Admin de Sistemas:', True);
  
  // Valores por defecto
  UsersConfigPage.Values[0] := 'app_legajo';
  UsersConfigPage.Values[2] := 'sistemas_admin';
  
  // Página 3: Configuración de Email (Opcional)
  EmailConfigPage := CreateInputQueryPage(UsersConfigPage.ID,
    'Configuración de Email (Opcional)',
    'Configure el servidor de correo para notificaciones',
    'Puede dejar estos campos vacíos si no desea configurar email ahora.');
  
  EmailConfigPage.Add('Servidor SMTP:', False);
  EmailConfigPage.Add('Puerto SMTP:', False);
  EmailConfigPage.Add('Email de la Aplicación:', False);
  EmailConfigPage.Add('Contraseña del Email:', True);
  
  // Valores por defecto
  EmailConfigPage.Values[0] := 'smtp.gmail.com';
  EmailConfigPage.Values[1] := '587';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ErrorMsg: string;
begin
  Result := True;
  
  // Verificar requisitos en la página de bienvenida
  if CurPageID = wpWelcome then
  begin
    ErrorMsg := '';
    
    if not CheckPython then
      ErrorMsg := ErrorMsg + '- Python 3.8 o superior' + #13#10;
    
    if not CheckSQLServer then
      ErrorMsg := ErrorMsg + '- SQL Server (Express o superior)' + #13#10;
    
    if not CheckODBC then
      ErrorMsg := ErrorMsg + '- ODBC Driver 17 for SQL Server' + #13#10;
    
    if ErrorMsg <> '' then
    begin
      if MsgBox('Atención: El sistema no detectó automáticamente los siguientes componentes:' + #13#10#13#10 + ErrorMsg + #13#10 +
             'Si está seguro de que ya los tiene instalados, puede continuar.' + #13#10#13#10 +
             '¿Desea continuar con la instalación de todos modos?',
             mbConfirmation, MB_YESNO) = idNo then
      begin
        Result := False;
      end;
    end;
  end;
  
  // Validar configuración de base de datos
  if CurPageID = DBConfigPage.ID then
  begin
    if (Trim(DBConfigPage.Values[0]) = '') or 
       (Trim(DBConfigPage.Values[1]) = '') or
       (Trim(DBConfigPage.Values[2]) = '') or
       (Trim(DBConfigPage.Values[3]) = '') then
    begin
      MsgBox('Por favor complete todos los campos de configuración de base de datos.', mbError, MB_OK);
      Result := False;
    end;
  end;
  
  // Validar usuarios de la aplicación
  if CurPageID = UsersConfigPage.ID then
  begin
    if (Trim(UsersConfigPage.Values[0]) = '') or 
       (Trim(UsersConfigPage.Values[1]) = '') or
       (Trim(UsersConfigPage.Values[2]) = '') or
       (Trim(UsersConfigPage.Values[3]) = '') then
    begin
      MsgBox('Por favor complete todos los campos de usuarios.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvContent: string;
  SecretKey: string;
  MailUseTLS: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Generar clave secreta basada en timestamp de instalación
    SecretKey := 'legajo_' + GetDateTimeString('yyyymmddhhnnss', '-', ':') + '_hmpp_secret_key_2026';
    
    // Determinar si usar TLS para email
    if Trim(EmailConfigPage.Values[0]) <> '' then
      MailUseTLS := 'True'
    else
      MailUseTLS := 'True';
    
    // Crear contenido del archivo .env
    EnvContent := '# Configuracion de Flask' + #13#10 +
                  'SECRET_KEY=' + SecretKey + #13#10 +
                  'FLASK_DEBUG=False' + #13#10 + #13#10 +
                  '# Configuracion de la Base de Datos' + #13#10 +
                  'DB_DRIVER=ODBC Driver 18 for SQL Server' + #13#10 +
                  'DB_SERVER=' + DBConfigPage.Values[0] + #13#10 +
                  'DB_DATABASE=' + DBConfigPage.Values[1] + #13#10 +
                  'DB_USERNAME_WRITE=' + UsersConfigPage.Values[0] + #13#10 +
                  'DB_PASSWORD_WRITE=' + UsersConfigPage.Values[1] + #13#10 +
                  'DB_USERNAME_SYSTEMS_ADMIN=' + UsersConfigPage.Values[2] + #13#10 +
                  'DB_PASSWORD_SYSTEMS_ADMIN=' + UsersConfigPage.Values[3] + #13#10 + #13#10 +
                  '# Configuracion de Email' + #13#10 +
                  'MAIL_SERVER=' + EmailConfigPage.Values[0] + #13#10 +
                  'MAIL_PORT=' + EmailConfigPage.Values[1] + #13#10 +
                  'MAIL_USE_TLS=' + MailUseTLS + #13#10 +
                  'MAIL_USERNAME=' + EmailConfigPage.Values[2] + #13#10 +
                  'MAIL_PASSWORD=' + EmailConfigPage.Values[3] + #13#10 +
                  'MAIL_DEFAULT_SENDER=' + EmailConfigPage.Values[2] + #13#10;
    
    // Guardar el archivo .env en LOCALAPPDATA para que sea editable por el usuario
    // Asegurarse de que el directorio existe (aunque [Dirs] debería crearlo)
    ForceDirectories(ExpandConstant('{localappdata}\LegajoDigitalHMPP'));
    SaveStringToFile(ExpandConstant('{localappdata}\LegajoDigitalHMPP\.env'), EnvContent, False);
  end;
end;

[Dirs]
; Crear directorio de datos en LOCALAPPDATA
Name: "{localappdata}\LegajoDigitalHMPP"; Permissions: users-modify

[Messages]
WelcomeLabel2=Este asistente instalará [name/ver] en su computadora.%n%nSe recomienda que cierre todas las demás aplicaciones antes de continuar.%n%nNOTA: Asegúrese de tener instalado Python 3.8+, SQL Server y ODBC Driver 17 antes de continuar.
FinishedHeadingLabel=Completando el Asistente de Instalación de [name]
FinishedLabel=La aplicación ha sido instalada en su computadora.%n%nPróximos pasos:%n1. Ejecutar "Configurar Sistema" desde el menú inicio%n2. Crear el primer usuario administrador%n3. Iniciar la aplicación