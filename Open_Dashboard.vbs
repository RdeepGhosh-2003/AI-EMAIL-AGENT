Dim shell, fileSystem, folderPath, pythonwPath

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
folderPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
pythonwPath = folderPath & ".venv\Scripts\pythonw.exe"
shell.CurrentDirectory = folderPath

If fileSystem.FileExists(pythonwPath) Then
    shell.Run """" & pythonwPath & """ """ & folderPath & "launch_dashboard.py""", 0, False
Else
    ' First run: let start.bat create the environment, then it calls this launcher again.
    shell.Run """" & folderPath & "start.bat""", 1, False
End If

Set fileSystem = Nothing
Set shell = Nothing
