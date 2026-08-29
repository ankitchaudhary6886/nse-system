@echo off
cd /d C:\Users\Ankit\Desktop\nse_system
call env\Scripts\activate.bat
python daily_update.py run >> data\daily_log.txt 2>&1