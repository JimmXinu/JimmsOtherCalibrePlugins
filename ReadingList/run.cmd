del "Reading List.zip"
"c:\Program Files\7-Zip\7z.exe" a "Reading List.zip" *.py *.txt images\* run.cmd 
mode 165,999
calibre-customize -a "Reading List.zip"
rem SET CALIBRE_DEVELOP_FROM=D:\Development\GitHub\calibre\src
calibre-debug  -s
calibre-debug  -g



