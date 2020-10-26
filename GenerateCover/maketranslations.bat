cd translations
for %%f in (*.po) do (
    "C:\Program Files\Calibre2\calibre-debug.exe" -c "from calibre.translations.msgfmt import main; main()" %%~nf
)

cd ..
