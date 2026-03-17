Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Obtener la ruta exacta de donde se instalo el programa
currentDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

' Ejecutamos el archivo .bat. 
' El 1 asegura que la ventana sea visible para que el usuario pueda "apagar" el servidor cerrandola.
WshShell.Run Chr(34) & currentDir & "\iniciar_aplicacion.bat" & Chr(34), 1, False

Set WshShell = Nothing