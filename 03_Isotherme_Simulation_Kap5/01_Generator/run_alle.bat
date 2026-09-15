@echo off
rem ===========================================================================
rem  Startet alle isothermen Laeufe mit der jeweils richtigen Wetterdatei.
rem  Erzeugt aus make_isotherm_varianten.py - die Zuordnung kann nicht
rem  auseinanderlaufen, weil sie aus derselben Variantentabelle stammt.
rem
rem  Varianten 1-3: Anstroemung 247,5 Grad (WSW)
rem  Varianten 4-6: Anstroemung 157,5 Grad (SSE)
rem
rem  Aufruf:  run_alle.bat
rem  Ergebnis je Datei in out\<Dateiname>\
rem ===========================================================================
setlocal
set EPLUS=energyplus
set WSW=DEU_Munich.108660_Isotherm-WSW2475-u5072.epw
set SSE=DEU_Munich.108660_Isotherm-SSE1575-u5072.epw
if not exist out mkdir out

rem --- Variante 1: Tore 2 + 5 gegenueberliegend, keine Barriere, schraege Anstroemung ---
echo === AFN_E+_1 ===
if not exist "out\AFN_E+_1" mkdir "out\AFN_E+_1"
%EPLUS% -w "%WSW%" -r -d "out\AFN_E+_1" -p AFN_E+_1 "AFN_E+_1.idf"
echo === WSOA_1 ===
if not exist "out\WSOA_1" mkdir "out\WSOA_1"
%EPLUS% -w "%WSW%" -r -d "out\WSOA_1" -p WSOA_1 "WSOA_1.idf"
echo === DFR_DEFAULT_1 ===
if not exist "out\DFR_DEFAULT_1" mkdir "out\DFR_DEFAULT_1"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DEFAULT_1" -p DFR_DEFAULT_1 "DFR_DEFAULT_1.idf"
echo === DFR_BLAST_1 ===
if not exist "out\DFR_BLAST_1" mkdir "out\DFR_BLAST_1"
%EPLUS% -w "%WSW%" -r -d "out\DFR_BLAST_1" -p DFR_BLAST_1 "DFR_BLAST_1.idf"
echo === DFR_DOE-2_1 ===
if not exist "out\DFR_DOE-2_1" mkdir "out\DFR_DOE-2_1"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DOE-2_1" -p DFR_DOE-2_1 "DFR_DOE-2_1.idf"

rem --- Variante 2: Tore 2 + 5 gegenueberliegend, innere Barriere mit Spalt, schraege Anstroemung ---
echo === AFN_E+_2 ===
if not exist "out\AFN_E+_2" mkdir "out\AFN_E+_2"
%EPLUS% -w "%WSW%" -r -d "out\AFN_E+_2" -p AFN_E+_2 "AFN_E+_2.idf"
echo === WSOA_2 ===
if not exist "out\WSOA_2" mkdir "out\WSOA_2"
%EPLUS% -w "%WSW%" -r -d "out\WSOA_2" -p WSOA_2 "WSOA_2.idf"
echo === WSOA_2_1Zone ===
if not exist "out\WSOA_2_1Zone" mkdir "out\WSOA_2_1Zone"
%EPLUS% -w "%WSW%" -r -d "out\WSOA_2_1Zone" -p WSOA_2_1Zone "WSOA_2_1Zone.idf"
echo === DFR_DEFAULT_2 ===
if not exist "out\DFR_DEFAULT_2" mkdir "out\DFR_DEFAULT_2"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DEFAULT_2" -p DFR_DEFAULT_2 "DFR_DEFAULT_2.idf"
echo === DFR_DEFAULT_2_1Zone ===
if not exist "out\DFR_DEFAULT_2_1Zone" mkdir "out\DFR_DEFAULT_2_1Zone"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DEFAULT_2_1Zone" -p DFR_DEFAULT_2_1Zone "DFR_DEFAULT_2_1Zone.idf"
echo === DFR_BLAST_2 ===
if not exist "out\DFR_BLAST_2" mkdir "out\DFR_BLAST_2"
%EPLUS% -w "%WSW%" -r -d "out\DFR_BLAST_2" -p DFR_BLAST_2 "DFR_BLAST_2.idf"
echo === DFR_BLAST_2_1Zone ===
if not exist "out\DFR_BLAST_2_1Zone" mkdir "out\DFR_BLAST_2_1Zone"
%EPLUS% -w "%WSW%" -r -d "out\DFR_BLAST_2_1Zone" -p DFR_BLAST_2_1Zone "DFR_BLAST_2_1Zone.idf"
echo === DFR_DOE-2_2 ===
if not exist "out\DFR_DOE-2_2" mkdir "out\DFR_DOE-2_2"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DOE-2_2" -p DFR_DOE-2_2 "DFR_DOE-2_2.idf"
echo === DFR_DOE-2_2_1Zone ===
if not exist "out\DFR_DOE-2_2_1Zone" mkdir "out\DFR_DOE-2_2_1Zone"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DOE-2_2_1Zone" -p DFR_DOE-2_2_1Zone "DFR_DOE-2_2_1Zone.idf"

rem --- Variante 3: Tore 2 + 4 diagonal, keine Barriere, schraege Anstroemung ---
echo === AFN_E+_3 ===
if not exist "out\AFN_E+_3" mkdir "out\AFN_E+_3"
%EPLUS% -w "%WSW%" -r -d "out\AFN_E+_3" -p AFN_E+_3 "AFN_E+_3.idf"
echo === WSOA_3 ===
if not exist "out\WSOA_3" mkdir "out\WSOA_3"
%EPLUS% -w "%WSW%" -r -d "out\WSOA_3" -p WSOA_3 "WSOA_3.idf"
echo === DFR_DEFAULT_3 ===
if not exist "out\DFR_DEFAULT_3" mkdir "out\DFR_DEFAULT_3"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DEFAULT_3" -p DFR_DEFAULT_3 "DFR_DEFAULT_3.idf"
echo === DFR_BLAST_3 ===
if not exist "out\DFR_BLAST_3" mkdir "out\DFR_BLAST_3"
%EPLUS% -w "%WSW%" -r -d "out\DFR_BLAST_3" -p DFR_BLAST_3 "DFR_BLAST_3.idf"
echo === DFR_DOE-2_3 ===
if not exist "out\DFR_DOE-2_3" mkdir "out\DFR_DOE-2_3"
%EPLUS% -w "%WSW%" -r -d "out\DFR_DOE-2_3" -p DFR_DOE-2_3 "DFR_DOE-2_3.idf"

rem --- Variante 4: Tore 2 + 5 gegenueberliegend, keine Barriere, frontale Anstroemung ---
echo === AFN_E+_4 ===
if not exist "out\AFN_E+_4" mkdir "out\AFN_E+_4"
%EPLUS% -w "%SSE%" -r -d "out\AFN_E+_4" -p AFN_E+_4 "AFN_E+_4.idf"
echo === WSOA_4 ===
if not exist "out\WSOA_4" mkdir "out\WSOA_4"
%EPLUS% -w "%SSE%" -r -d "out\WSOA_4" -p WSOA_4 "WSOA_4.idf"
echo === DFR_DEFAULT_4 ===
if not exist "out\DFR_DEFAULT_4" mkdir "out\DFR_DEFAULT_4"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DEFAULT_4" -p DFR_DEFAULT_4 "DFR_DEFAULT_4.idf"
echo === DFR_BLAST_4 ===
if not exist "out\DFR_BLAST_4" mkdir "out\DFR_BLAST_4"
%EPLUS% -w "%SSE%" -r -d "out\DFR_BLAST_4" -p DFR_BLAST_4 "DFR_BLAST_4.idf"
echo === DFR_DOE-2_4 ===
if not exist "out\DFR_DOE-2_4" mkdir "out\DFR_DOE-2_4"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DOE-2_4" -p DFR_DOE-2_4 "DFR_DOE-2_4.idf"

rem --- Variante 5: Tore 2 + 5 gegenueberliegend, innere Barriere mit Spalt, frontale Anstroemung ---
echo === AFN_E+_5 ===
if not exist "out\AFN_E+_5" mkdir "out\AFN_E+_5"
%EPLUS% -w "%SSE%" -r -d "out\AFN_E+_5" -p AFN_E+_5 "AFN_E+_5.idf"
echo === WSOA_5 ===
if not exist "out\WSOA_5" mkdir "out\WSOA_5"
%EPLUS% -w "%SSE%" -r -d "out\WSOA_5" -p WSOA_5 "WSOA_5.idf"
echo === WSOA_5_1Zone ===
if not exist "out\WSOA_5_1Zone" mkdir "out\WSOA_5_1Zone"
%EPLUS% -w "%SSE%" -r -d "out\WSOA_5_1Zone" -p WSOA_5_1Zone "WSOA_5_1Zone.idf"
echo === DFR_DEFAULT_5 ===
if not exist "out\DFR_DEFAULT_5" mkdir "out\DFR_DEFAULT_5"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DEFAULT_5" -p DFR_DEFAULT_5 "DFR_DEFAULT_5.idf"
echo === DFR_DEFAULT_5_1Zone ===
if not exist "out\DFR_DEFAULT_5_1Zone" mkdir "out\DFR_DEFAULT_5_1Zone"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DEFAULT_5_1Zone" -p DFR_DEFAULT_5_1Zone "DFR_DEFAULT_5_1Zone.idf"
echo === DFR_BLAST_5 ===
if not exist "out\DFR_BLAST_5" mkdir "out\DFR_BLAST_5"
%EPLUS% -w "%SSE%" -r -d "out\DFR_BLAST_5" -p DFR_BLAST_5 "DFR_BLAST_5.idf"
echo === DFR_BLAST_5_1Zone ===
if not exist "out\DFR_BLAST_5_1Zone" mkdir "out\DFR_BLAST_5_1Zone"
%EPLUS% -w "%SSE%" -r -d "out\DFR_BLAST_5_1Zone" -p DFR_BLAST_5_1Zone "DFR_BLAST_5_1Zone.idf"
echo === DFR_DOE-2_5 ===
if not exist "out\DFR_DOE-2_5" mkdir "out\DFR_DOE-2_5"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DOE-2_5" -p DFR_DOE-2_5 "DFR_DOE-2_5.idf"
echo === DFR_DOE-2_5_1Zone ===
if not exist "out\DFR_DOE-2_5_1Zone" mkdir "out\DFR_DOE-2_5_1Zone"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DOE-2_5_1Zone" -p DFR_DOE-2_5_1Zone "DFR_DOE-2_5_1Zone.idf"

rem --- Variante 6: Tore 2 + 4 diagonal, keine Barriere, frontale Anstroemung ---
echo === AFN_E+_6 ===
if not exist "out\AFN_E+_6" mkdir "out\AFN_E+_6"
%EPLUS% -w "%SSE%" -r -d "out\AFN_E+_6" -p AFN_E+_6 "AFN_E+_6.idf"
echo === WSOA_6 ===
if not exist "out\WSOA_6" mkdir "out\WSOA_6"
%EPLUS% -w "%SSE%" -r -d "out\WSOA_6" -p WSOA_6 "WSOA_6.idf"
echo === DFR_DEFAULT_6 ===
if not exist "out\DFR_DEFAULT_6" mkdir "out\DFR_DEFAULT_6"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DEFAULT_6" -p DFR_DEFAULT_6 "DFR_DEFAULT_6.idf"
echo === DFR_BLAST_6 ===
if not exist "out\DFR_BLAST_6" mkdir "out\DFR_BLAST_6"
%EPLUS% -w "%SSE%" -r -d "out\DFR_BLAST_6" -p DFR_BLAST_6 "DFR_BLAST_6.idf"
echo === DFR_DOE-2_6 ===
if not exist "out\DFR_DOE-2_6" mkdir "out\DFR_DOE-2_6"
%EPLUS% -w "%SSE%" -r -d "out\DFR_DOE-2_6" -p DFR_DOE-2_6 "DFR_DOE-2_6.idf"

echo.
echo Fertig. Kontrolle je Lauf:
echo   1) eplusout.err auf Severe/Fatal pruefen
echo   2) Site Wind Direction gegen den Wert im IDF-Kopf pruefen
echo   3) Zone Mean Air Temperature minus Site Outdoor Air Drybulb = 0
echo   4) Volumenstrom gegen Sollwerte_Isotherm.csv
endlocal
