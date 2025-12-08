Set WshShell = CreateObject("WScript.Shell")
' Usamos pythonw directamente ya que el instalador asegura que Python esta en el sistema
' y las dependencias se instalan globalmente.
WshShell.Run "pythonw run_production.py", 0
Set WshShell = Nothing
