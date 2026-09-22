Dim shell, fileSystem, folderPath, pythonwPath

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
folderPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
pythonwPath = folderPath & ".venv\Scripts\pythonw.exe"
shell.CurrentDirectory = folderPath

If fileSystem.FileExists(pythonwPath) Then
    shell.Run """" & pythonwPath & """ """ & folderPath & "create_share_package.py""", 0, False
Else
    MsgBox "Run Open_Dashboard once before creating a sharing package.", 48, "AI Email Agent"
End If

Set fileSystem = Nothing
Set shell = Nothing
