@echo off
chcp 65001 >nul
echo ========================================
echo 开始打包桌面应用...
echo ========================================

echo.
echo [1/3] 检查依赖...
pip install pywebview pyinstaller

echo.
echo [2/3] 执行打包（这需要几分钟）...
python -m PyInstaller build.spec --clean

echo.
echo [修复] 复制正确的exe文件...
copy /Y "build\build\字幕编辑器.exe" "dist\字幕编辑器\字幕编辑器.exe" >nul
echo 图标修复完成！

echo.
echo [3/3] 打包完成！
echo.
echo 可执行文件位置: dist\字幕编辑器\字幕编辑器.exe
echo.
echo ========================================
echo 双击运行 exe 即可使用
echo ========================================
pause
