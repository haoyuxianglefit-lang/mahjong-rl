@echo off
set PATH=C:\Users\admin\miniconda3;C:\Users\admin\mingw64\bin;D:\Mahjong AI\.toolchain\cargo\bin;D:\Mahjong AI\third_party\Mortal\.venv\Scripts;D:\Mahjong AI\.toolchain\rustup\toolchains\stable-x86_64-pc-windows-gnu\lib\rustlib\x86_64-pc-windows-gnu\bin\self-contained;%PATH%
set RUSTUP_HOME=D:\Mahjong AI\.toolchain\rustup
set CARGO_HOME=D:\Mahjong AI\.toolchain\cargo
set PYO3_PYTHON=D:\Mahjong AI\third_party\Mortal\.venv\Scripts\python.exe
set CC=C:\Users\admin\mingw64\bin\gcc.exe
set CXX=C:\Users\admin\mingw64\bin\g++.exe
cd /d "D:\Mahjong AI\third_party\Mortal"
cargo test --workspace --no-default-features --features flate2/zlib 1> "D:\Mahjong AI\cargo_test.log" 2>&1
echo exit: %ERRORLEVEL%
