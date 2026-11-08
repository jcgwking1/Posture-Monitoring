@echo off
cd /d "%~dp0"
echo Starting Posture & Ergonomics Monitor...
python -m streamlit run app.py
pause
