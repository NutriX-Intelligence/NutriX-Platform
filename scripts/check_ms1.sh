#!/bin/bash
cd /home/harsh/Nutrix
source .venv/bin/activate
pip install -q -r ms1_cv/requirements.txt
PYTHONPATH=. python -c "from ms1_cv.main import app; print('MS1 imports OK')"
