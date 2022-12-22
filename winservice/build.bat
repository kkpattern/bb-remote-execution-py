pyinstaller winservice.py -F --hidden-import=win32timezone -n bbworker_service --additional-hooks-dir pyinstaller_hooks
