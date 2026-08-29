@echo off
cd /d "%~dp0"

echo STARTUP

echo. > .\temp\UDID.txt

rem start pwsh -Command "Start-Transcript -Path .\temp\UDID.txt ;  ios list"

rem if exist .\temp\UDID.txt (echo Capturing UDID) else (goto something_went_wrong)

rem timeout /t 4 >nul

rem for /f "tokens=2 delims=:" %%a in ('findstr /c:"deviceList" .\temp\UDID.txt') do set "raw=%%a"
rem set "deviceID=%raw:[=%"
rem set "deviceID=%deviceID:]=%"
rem set "deviceID=%deviceID:"=%"
rem set "deviceID=%deviceID:}=%"

set "deviceID=00008140-001130441A2A801C"

echo UDID Captured
echo This is your Device ID: %deviceID%
if "%deviceID%" == "" (goto something_went_wrong)
echo.

set /a tunnel_TO_times=0

:tunnel_start
if %tunnel_TO_times% geq 2 goto something_went_wrong
echo STARTING TUNNEL

del .\temp\tunnel_log.txt 2>nul
del .\temp\tunnel_pspid.txt 2>nul

start pwsh -NoExit -WindowStyle Hidden -ExecutionPolicy Bypass -Command "& { $PID | Out-File .\temp\tunnel_pspid.txt -Encoding ascii ; ios tunnel start } *>&1 | Tee-Object -FilePath .\temp\tunnel_log.txt -Encoding ascii"

timeout /t 1 >nul

set /a tunnel_tries=0

:wait_for_tunnel
findstr /c:"Removed orphaned adapter" .\temp\tunnel_log.txt >nul 2>&1
if not errorlevel 1 goto tunnel_ready 
set /a tunnel_tries+=1
if %tunnel_tries% geq 5 goto tunnel_timed_out
echo Waiting...
timeout /t 2 /nobreak >nul
goto wait_for_tunnel

:tunnel_timed_out
echo Tunnel Timed Out
timeout /t 2 /nobreak >nul
echo Trying Again
timeout /t 2 /nobreak >nul
set /p tunnel_psPID=<.\temp\tunnel_pspid.txt
taskkill /PID %tunnel_psPID% /F /T >nul
set /a tunnel_TO_times+=1
goto tunnel_start

:tunnel_ready
echo TUNNEL STARTED

echo.

set /a WDA_tries = 0

:WDA_start

echo STARTING WDA
if %WDA_tries% geq 3 goto something_went_wrong

del .\temp\runwda_log.txt 2>nul
del .\temp\runwda_pspid.txt 2>nul

start pwsh -NoExit -WindowStyle Hidden -Command "& { $PID | Out-File .\temp\runwda_pspid.txt -Encoding ascii ; ios runwda --bundleid=com.lithum.WebDriverAgent.xctrunner --testrunnerbundleid=com.lithum.WebDriverAgent.xctrunner --xctestconfig=WebDriverAgentRunner.xctest --udid=%deviceIDd% } *>&1 | Tee-Object -FilePath .\temp\runwda_log.txt -Encoding ascii"

timeout /t 5 >nul

for /f "tokens=7 delims=," %%a in ('findstr /c:"authorized" .\temp\runwda_log.txt') do set "raw=%%a"
if errorlevel 1 (
    goto something_went_wrong
)
set "authorization=%raw::=%"
set "authorization=%authorization:"=%"
set "authorization=%authorization:}=%"
set "authorization=%authorization:authorized=%"

echo WDA has been authroized? %authorization%

if /i "%authorization%"=="true" (goto WDA_running) else (goto try_WDA_again)

:try_WDA_again
set /a WDA_tries += 1
set /p runwda_psPID=<.\temp\runwda_pspid.txt
taskkill /PID %runwda_psPID% /F /T

echo WDA didn't start, Trying Again

timeout /t 5 >nul

goto WDA_start

:WDA_running
echo WDA is Runnning

echo.
timeout /t 5 >nul

:port_forward

echo PORT FORWARDING WDA

start pwsh -NoExit -WindowStyle Hidden -Command "& { $PID | Out-File .\temp\localhost_pspid.txt -Encoding ascii ; ios forward 8100 8100 --udid=%deviceIDd% } *>&1 | Tee-Object -FilePath .\temp\localhost_log.txt -Encoding ascii"

timeout /t 5 >nul

rem pwsh -NoProfile -WindowStyle Hidden -Command "exit [int](-not (Test-Connection -TargetName localhost -TcpPort 8100 -Quiet))"
rem if errorlevel 0 (goto forwarded) else (goto something_went_wrong)

:forwarded
echo FORWARDED WDA @ http://localhost:8100/status

timeout /t 5 >nul

:appium_start
echo STARTING APPIUM

start pwsh -NoExit -Command "& { $PID | Out-File .\temp\appium_pspid.txt -Encoding ascii ; $PSStyle.OutputRendering = 'Ansi'; appium --use-plugins=inspector } *>&1 | Tee-Object -FilePath .\temp\appium_log.txt -Encoding ascii"

echo APPIUM STARTED @ http://localhost:4723

:terminate
echo Press Enter to terminate

pause >nul

echo Terminating.
set /p tunnel_psPID=<.\temp\tunnel_pspid.txt
set /p runwda_psPID=<.\temp\runwda_pspid.txt
set /p localhost_psPID=<.\temp\localhost_pspid.txt
set /p appium_psPID=<.\temp\appium_pspid.txt
taskkill /PID %tunnel_psPID% /F /T
taskkill /PID %runwda_psPID% /F /T
taskkill /PID %localhost_psPID% /F /T
taskkill /PID %appium_psPID% /F /T
if errorlevel 1 (
    echo Something went wrong!
    goto end_exit
)

goto jump

:something_went_wrong
echo something has gone terribly wrong
pause

goto terminate

:jump

exit
