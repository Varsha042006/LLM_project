@echo off
title Firebase Deployment - varsha.a.042006@gmail.com
cls
echo ===================================================================
echo [1/3] Log in to Firebase for varsha.a.042006@gmail.com
echo ===================================================================
echo When prompted in your browser, please select:
echo varsha.a.042006@gmail.com
echo ===================================================================
echo.
cd /d "e:\projects\llm"
call npx firebase login
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Firebase login was not completed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================================
echo [2/3] Building Next.js static export for Firebase Hosting...
echo ===================================================================
cd /d "e:\projects\llm\frontend"
set "NEXT_EXPORT=true"
call "C:\Users\pc\Downloads\node-bin\node-v24.14.0-win-x64\node.exe" node_modules\next\dist\bin\next build
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Frontend build failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================================
echo [3/3] Deploying to Firebase Hosting...
echo ===================================================================
cd /d "e:\projects\llm"
call npx firebase deploy --only hosting
echo.
echo ===================================================================
echo Deployment completed!
echo ===================================================================
pause
