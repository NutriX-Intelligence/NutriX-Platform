# Workspace Rule: WSL Environment Mandate

Every time you execute a command, view a file, or modify code in this project:
1. The real codebase is in WSL2 Ubuntu at `/home/harsh/Nutrix` (UNC: `\\wsl.localhost\Ubuntu\home\harsh\Nutrix`).
2. Never treat `C:\` or `C:\MAIN\Project\CalCount` as the primary workspace.
3. Every shell command must run inside WSL using `wsl.exe -d Ubuntu -- bash -c "cd /home/harsh/Nutrix && source .venv/bin/activate && ..."`.
4. Always activate `/home/harsh/Nutrix/.venv` and set `PYTHONPATH=.`.
5. See `docs/DEV_ENVIRONMENT_RULES.md` for full system architecture and execution guidelines.
