#!/usr/bin/env python3
"""Install an opt-in user service and launcher. Does not install discovery scheduling."""
from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parent
home=Path.home()
unit=home/'.config/systemd/user/ui-taste-lab.service'
launcher=home/'.local/share/applications/ui-taste-lab.desktop'
unit.parent.mkdir(parents=True,exist_ok=True);launcher.parent.mkdir(parents=True,exist_ok=True)
for path in (unit,launcher):
    if path.exists() and 'UI Taste Lab' not in path.read_text():raise SystemExit(f'Refusing to overwrite unrelated file: {path}')
unit.write_text(f'''[Unit]
Description=UI Taste Lab local reference review
After=default.target

[Service]
Type=simple
WorkingDirectory={root}
ExecStart={sys.executable} "{root}/tastelab.py" serve
Restart=on-failure
RestartSec=3
UMask=0077

[Install]
WantedBy=default.target
''')
launcher.write_text('''[Desktop Entry]
Type=Application
Name=UI Taste Lab
Comment=Your private design inspiration notebook
Exec=xdg-open http://127.0.0.1:7841
Icon=applications-graphics
Terminal=false
Categories=Graphics;Development;
''')
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','enable','--now','ui-taste-lab.service'],check=True)
subprocess.run(['systemctl','--user','is-active','ui-taste-lab.service'],check=True)
print('Launcher installed. Local URL: http://127.0.0.1:7841')
