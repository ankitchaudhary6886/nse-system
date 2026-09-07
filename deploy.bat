@echo off
cd /d C:\Users\Ankit\Desktop\nse_system

git add -A
git commit -m "update"
git push

echo.
echo DONE. Now SSH to VM and run:
echo cd ~/nse-system ^&^& git pull
pause