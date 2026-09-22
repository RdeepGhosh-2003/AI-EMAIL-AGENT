Dim shell, fileSystem, folderPath, setupPath
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
folderPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
setupPath = folderPath & "scripts\setup.ps1"
shell.CurrentDirectory = folderPath

If fileSystem.FileExists(setupPath) Then
    shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & setupPath & """", 1, False
Else
    MsgBox "Setup files are incomplete. Extract the full ZIP before installing.", 16, "AI Email Agent"
End If

Set fileSystem = Nothing
Set shell = Nothing
