@echo off
title Firebase Login - varsha.a.042006@gmail.com
echo ===================================================================
echo [Firebase Authentication]
echo Authorizing Firebase CLI for: varsha.a.042006@gmail.com
echo A Google Sign-In window will open in your browser.
echo Please select: varsha.a.042006@gmail.com
echo ===================================================================
call npx firebase login:add varsha.a.042006@gmail.com
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Trying standard re-authentication...
    call npx firebase login --reauth
)
echo.
echo Setting active account to varsha.a.042006@gmail.com...
call npx firebase login:use varsha.a.042006@gmail.com
echo.
echo ===================================================================
echo Authentication complete! Return to chat to proceed with deploy.
echo ===================================================================
pause
