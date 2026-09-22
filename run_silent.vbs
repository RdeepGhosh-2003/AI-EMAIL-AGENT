Dim WinScriptHost, strPath, strFolderPath
Set WinScriptHost = CreateObject("WScript.Shell")
strPath = WScript.ScriptFullName
strFolderPath = Left(strPath, InStrRev(strPath, "\"))
WinScriptHost.CurrentDirectory = strFolderPath
WinScriptHost.Run """" & strFolderPath & ".venv\Scripts\python.exe"" run.py", 0, False
Set WinScriptHost = Nothing
