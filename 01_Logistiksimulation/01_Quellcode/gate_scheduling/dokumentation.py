"""Erzeugt die Methodenkapitel-Dokumentation (.docx) fuer die
Tor-Schedule-Erweiterung. Liest die tatsaechlichen Werte aus einer
GateScheduleConfig und der Pipeline-Zusammenfassung, damit Doku und
Ausfuehrung nicht auseinanderlaufen koennen.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .config import GateScheduleConfig

SCRIPT_VERSION = "0.1.0"


def _tabelle(doc: Document, kopf: list[str], zeilen: list[list[str]]) -> None:
    tabelle = doc.add_table(rows=1, cols=len(kopf))
    tabelle.style = "Light Grid Accent 1"
    for i, h in enumerate(kopf):
        tabelle.rows[0].cells[i].text = h
        tabelle.rows[0].cells[i].paragraphs[0].runs[0].bold = True
    for zeile in zeilen:
        cells = tabelle.add_row().cells
        for i, wert in enumerate(zeile):
            cells[i].text = str(wert)


def erstelle_dokumentation(
    pfad: str | Path, config: GateScheduleConfig, zusammenfassung: dict
) -> None:
    doc = Document()

    titel = doc.add_heading("Tor-Schedule-Erweiterung fuer EnergyPlus (AirflowNetwork)", level=0)
    doc.add_paragraph(
        "Methodenkapitel-Grundlage: Erzeugung torbezogener Toeroeffnungs-Schedules aus den "
        "bestehenden Ankunfts- und Abfahrtsereignissen der Crossdocking-Simulation."
    )

    # 1. Ausgangszustand
    doc.add_heading("1. Ausgangszustand des Skripts", level=1)
    doc.add_paragraph(
        "Vor dieser Erweiterung modelliert das Skript (Paket crossdocking_simulation, Projekt "
        "LUKIE) die Ankunft und Abfahrt von LKW an einem Crossdocking-Center: hierarchische "
        "Verteilung einer Jahres-LKW-Menge auf Monate, Wochen, Wochentage und Schichten "
        "(vollstaendig deterministisch, Kumaraswamy(2,2)-Quantilverteilung fuer Ankunfts- und "
        "Abfahrtszeiten innerhalb einer Schicht), Bestandsrechnung in Paletten sowie Constraint-"
        "Pruefung (Hallenkapazitaet, Same-Day-Clearing, Torkapazitaet). Ausgabeformat: "
        "verschachteltes JSON (Monat -> Woche -> Tag -> Schicht -> LKW-Liste), Zeitstempel als "
        "relative Tagesminute ohne echtes Kalenderdatum und ohne Zeitzone."
    )
    doc.add_paragraph(
        "Rechercheergebnis vor Implementierung: Im Repository wurde keine Ladungstemperatur- "
        "oder Waerme-/Kaelteabgabe-Logik gefunden (Volltextsuche ueber alle .py- und .md-Dateien). "
        "Der in der Aufgabenstellung beschriebene Ausgangszustand ('bisherige Auswertung betraf "
        "die Temperatur der Ladung') konnte im vorliegenden Code nicht bestaetigt werden. Es gibt "
        "daher keinen stillzulegenden Thermik-Code (siehe Abschnitt 6)."
    )

    # 2. Uebersicht der Erweiterungen
    doc.add_heading("2. Uebersicht der Erweiterungen", level=1)
    _tabelle(
        doc,
        ["Datei", "Art der Aenderung", "Zweck"],
        [
            ["crossdocking_simulation/beispiel_config.json", "geaendert",
             "n_jahr=3900, Mo-Fr-Arbeitsmatrix, anzahl_tore=6, Hallenmasse, echte Kalendergewichte 2026"],
            ["gate_scheduling/config.py", "neu", "Zentrale Konfiguration (Seed, Offsets, Statuswerte, Torzahl)"],
            ["gate_scheduling/gates.py", "neu", "Torbenennung (AN/AB), Statuswerte als Enum"],
            ["gate_scheduling/calendar_mapping.py", "neu", "Abbildung (Monat,Woche,Tag) -> echtes Kalenderdatum"],
            ["gate_scheduling/assignment.py", "neu", "LKW->Tor-Zuordnung, Kollisionsregel, Konfliktbericht"],
            ["gate_scheduling/state_model.py", "neu", "Zustandslisten je Tor aus dem Oeffnungsschema"],
            ["gate_scheduling/schedules.py", "neu", "EnergyPlus Schedule:Compact Export + Ruecklese-Validierung"],
            ["gate_scheduling/plausibility.py", "neu", "Plausibilitaetspruefung als eigener Pipeline-Schritt"],
            ["gate_scheduling/visualization.py", "neu", "6 Kontroll-Grafiken je Pipeline-Schritt"],
            ["gate_scheduling/pipeline.py", "neu", "Orchestrierung, versionierter Ausgabeordner, CLI"],
            ["gate_scheduling/tests/*", "neu", "21 Unit-Tests (Schema, Kollision, Reproduzierbarkeit, Plausibilitaet)"],
            ["crossdocking_simulation/* (alle bestehenden Module)", "unveraendert",
             "Keine Aenderung an Code oder Verhalten der bestehenden Simulation"],
        ],
    )

    # 3. Modul- und Pipeline-Beschreibung
    doc.add_heading("3. Modul- und Pipeline-Beschreibung", level=1)
    doc.add_paragraph(
        "Die Pipeline konsumiert ausschliesslich JSON-Artefakte der bestehenden Simulation "
        "(ergebnis_zeitachse.json fuer die AN-Seite, ergebnis_warenausgang.json fuer die AB-Seite) "
        "und schreibt alle Zwischenergebnisse in einen versionierten Ordner "
        "gate_scheduling/output/run_<Zeitstempel>/."
    )
    _tabelle(
        doc,
        ["Schritt", "Modul", "Eingabe", "Ausgabe"],
        [
            ["0. Laden", "pipeline.schritt_laden", "ergebnis_zeitachse.json, ergebnis_warenausgang.json",
             "Liste AndockEreignis (AN, AB) mit echtem Kalenderdatum"],
            ["1. Zuordnung", "assignment.zuordnen_alle", "AndockEreignis-Listen, Tore, Config",
             "Andockung-Liste, Konflikt-Liste -> konfliktbericht.csv"],
            ["2. Zustandsmodell", "state_model.alle_zustandslisten", "Andockung-Liste, Schema-Offsets",
             "Zustandsliste je Tor (Enum-Status, Zeitpunkt)"],
            ["3. Schedules", "schedules.schreibe_*", "Zustandslisten, Statuswerte",
             "6x <Tor>.idf + 1x alle_tore.idf"],
            ["4. Plausibilitaet", "plausibility.pruefe_plausibilitaet", "Andockungen, Zustandslisten",
             "PlausibilitaetsBericht (4 Invarianten)"],
            ["5. Visualisierung", "visualization.plot_*", "alle vorherigen Ergebnisse + geschriebene .idf",
             "6 PNG-Grafiken in plots/"],
        ],
    )

    # 4. Parameterliste
    doc.add_heading("4. Vollstaendige Parameterliste", level=1)
    s, f = config.schema, config.status_fractions
    _tabelle(
        doc,
        ["Parameter", "Default", "Einheit", "Bedeutung"],
        [
            ["seed", str(config.seed), "-", "Seed fuer numpy.random.Generator (Torzuordnung)"],
            ["gates_per_side", str(config.gates_per_side), "-", "Anzahl Tore je Seite (AN bzw. AB)"],
            ["choice_probabilities", "Gleichverteilung", "-", "Auswahlwahrscheinlichkeit je Tor einer Seite"],
            ["schema.oeffnen_min", str(s.oeffnen_min), "min", "Toeroeffnung relativ zum Andockzeitpunkt t"],
            ["schema.andock_min", str(s.andock_min), "min", "LKW dockt an (= t)"],
            ["schema.abdock_min", str(s.abdock_min), "min", "LKW dockt ab"],
            ["schema.schliessen_min", str(s.schliessen_min), "min", "Tor schliesst"],
            ["status_fractions.zu", str(f.zu), "Fraction [0..1]", "Schedule-Wert bei Status 'zu'"],
            ["status_fractions.offen", str(f.offen), "Fraction [0..1]", "Schedule-Wert bei Status 'offen'"],
            ["status_fractions.lkw", str(f.lkw), "Fraction [0..1]", "Schedule-Wert bei Status 'LKW' (AFN-Opening-Factor bzw. Ventilations-Multiplikator, siehe Abschnitt 7)"],
            ["min_abstand_min", str(config.min_abstand_min), "min", "Mindestabstand zweier Andockungen am selben Tor"],
            ["kalenderjahr", str(config.kalenderjahr), "-", "Zieljahr fuer die Kalenderabbildung"],
        ],
    )

    # 5. Annahmen
    doc.add_heading("5. Annahmen und Begruendung", level=1)
    for annahme in [
        "ANNAHME: 'zeit_min' in ergebnis_warenausgang.json wird als Andock-Zeitpunkt (t) "
        "interpretiert, nicht als Zeitpunkt der tatsaechlichen Abfahrt nach Beladung. "
        "Begruendung: Bestaetigung durch den Auftraggeber; ohne diese Interpretation waere "
        "kein Anker fuer das Oeffnungsschema (-2/0/+15/+20) auf der AB-Seite verfuegbar.",
        "ANNAHME: Eine Kalenderwoche (Montag-Sonntag) gehoert zu dem Monat, in dem ihr Montag "
        "liegt -- auch wenn die Woche ueber die Monatsgrenze hinausreicht. Begruendung: "
        "konsistent mit der Reihenfolge, in der wochengewichte_pro_monat in der bestehenden "
        "Simulation abgearbeitet wird.",
        "ANNAHME: anzahl_tore in der bestehenden HallenConfig wird als gates_per_side * 2 "
        "interpretiert (symmetrische AN/AB-Aufteilung). Begruendung: explizite Nutzervorgabe "
        "(anzahl_tore=6 fuer 3 AN- + 3 AB-Tore).",
        "ANNAHME: 'Gleichzeitig geoeffnet' (Abschnitt Gleichzeitigkeit) bezieht sich auf den "
        "physischen Tuerzustand: sowohl 'offen' als auch 'LKW' bedeuten geoeffnet, nur 'zu' "
        "bedeutet geschlossen. Begruendung: aus Sicht der AirflowNetwork-Modellierung ist die "
        "Tueroeffnung selbst massgeblich, nicht der Feinzustand LKW/offen.",
        "ANNAHME: Kalenderjahr 2026 als Zieljahr, sofern nicht anders konfiguriert. Begruendung: "
        "aktuelles Bezugsjahr zum Zeitpunkt der Erstellung, frei per Config-Parameter aenderbar.",
    ]:
        p = doc.add_paragraph(annahme, style="List Bullet")

    # 6. Artefakte
    doc.add_heading("6. Artefakte (stillgelegter, aber erhaltener Code)", level=1)
    doc.add_paragraph(
        "Es wurde kein stillzulegender Code identifiziert. Die Aufgabenstellung sah vor, "
        "bestehende Ladungstemperatur-/Waerme-Kaelte-Logik hinter einem Konfigurations-Flag "
        "(z. B. ENABLE_CARGO_THERMAL) zu erhalten. Eine Volltextsuche ueber das gesamte "
        "Repository (Code und Markdown-Dokumentation) ergab keine Treffer fuer Temperatur-, "
        "Waerme- oder Kaeltelogik. Es existiert daher kein Artefakt dieser Art, das stillgelegt "
        "werden muesste; ein Flag ohne Wirkung wurde bewusst nicht angelegt, um keinen toten "
        "Code einzufuehren."
    )
    doc.add_paragraph(
        "Unveraendert erhalten (kein Bestandteil dieser Erweiterung, aber weiterhin vorhanden): "
        "crossdocking_simulation/Verweildauer_entwurf.py und "
        "crossdocking_simulation/abfahrtzeiten_ausgang_entwurf.py -- bereits vor dieser "
        "Erweiterung als deprecated dokumentiert (implemention_ist.md), durch verweildauer.py "
        "bzw. warenausgang_zeitachse.py ersetzt."
    )

    # 7. Einschraenkungen
    doc.add_heading("7. Bekannte Einschraenkungen und Vorbehalte", level=1)
    doc.add_paragraph(
        "Timestep: Die Minutenauflösung der Schedules wirkt in EnergyPlus nur, wenn im "
        "IDF 'Timestep, 60;' gesetzt ist. Bei geringerer Zeitschrittzahl mittelt EnergyPlus die "
        "Werte innerhalb eines Zeitschritts, wodurch der Unterschied zwischen 1.0 (offen) und "
        "0.048 (LKW) verwischt. Im Projekt wurde keine IDF-Datei gefunden -- eine Pruefung des "
        "gesetzten Timestep-Werts ist nachzuholen, sobald eine IDF vorliegt.",
        style="List Bullet",
    )
    doc.add_paragraph(
        "Modellabhaengigkeit von 0.048: Der Fraction-Wert 0.048 ist nicht modellneutral. "
        "Als AirflowNetwork-Opening-Factor bedeutet er einen Teiloeffnungsgrad; als Multiplikator "
        "auf ZoneVentilation:DesignFlowRate bedeutet er einen Anteil des Nominal-Volumenstroms. "
        "Das Schedule ist technisch fuer beide Verwendungen nutzbar, die physikalische "
        "Kalibrierung des Werts 0.048 ist es nicht und muss verwendungsabhaengig gepruefte werden.",
        style="List Bullet",
    )
    doc.add_paragraph(
        "Kollisionsbehandlung: Da die Zeitstempel aus dem bestehenden Modell nicht veraendert "
        "werden duerfen, findet Kollisionsvermeidung ausschliesslich bei der Torzuordnung statt "
        "(Verschiebung auf die fruehste zulaessige Minute). Mit den in Abschnitt 2 genannten "
        f"Parametern (n_jahr=3900, 3 Tore/Seite, ~15 LKW/Werktag) traten in diesem Lauf "
        f"{zusammenfassung.get('konflikte_gesamt', 'n/a')} Konflikte auf "
        f"(maximale Verschiebung: {zusammenfassung.get('maximale_verschiebung_min', 'n/a')} min). "
        "Bei hoeherer LKW-Dichte oder weniger Toren waechst die Konfliktzahl entsprechend an "
        "(siehe fruehere Kapazitaetsrechnung: 3 Tore, 23 min Mindestabstand => ca. 62 Andockungen/"
        "Tor/Tag Maximalkapazitaet).",
        style="List Bullet",
    )

    # 8. Reproduktionsanleitung
    doc.add_heading("8. Reproduktionsanleitung", level=1)
    doc.add_paragraph("Schritt 1 -- Basissimulation ausfuehren (im Verzeichnis Crossdocking/):")
    doc.add_paragraph(
        "python main.py --config crossdocking_simulation/beispiel_config.json "
        "--distanz --zeitachse --warenausgang",
        style="Intense Quote",
    )
    doc.add_paragraph(
        "Erzeugt ergebnisse.json, ergebnis_distanz.json, ergebnis_zeitachse.json, "
        "ergebnis_warenausgang.json."
    )
    doc.add_paragraph("Schritt 2 -- Tor-Schedule-Pipeline ausfuehren:")
    doc.add_paragraph(
        "python -m gate_scheduling.pipeline --crossdocking-dir . --seed 42 --gates-per-side 3 "
        "--kalenderjahr 2026",
        style="Intense Quote",
    )
    doc.add_paragraph(
        f"Aktueller Lauf: {zusammenfassung.get('output_ordner', 'n/a')} "
        f"(Erzeugt: {zusammenfassung.get('erzeugungszeitpunkt', 'n/a')}, Seed: "
        f"{zusammenfassung.get('seed', 'n/a')}). Eingangsereignisse: "
        f"{zusammenfassung.get('eingangs_ereigniszahl', 'n/a')}, Andockungen gesamt: "
        f"{zusammenfassung.get('andockungen_gesamt', 'n/a')}, Plausibilitaet: "
        f"{'OK' if zusammenfassung.get('plausibilitaet_alles_ok') else 'FEHLER'}."
    )
    doc.add_paragraph("Schritt 3 -- Tests ausfuehren:")
    doc.add_paragraph("python -m pytest gate_scheduling/tests/ -v", style="Intense Quote")

    # 9. Aenderungshistorie
    doc.add_heading("9. Aenderungshistorie", level=1)
    _tabelle(
        doc,
        ["Version", "Datum", "Aenderung"],
        [
            ["0.1.0", "2026-08-06", "Erstversion: gates, assignment, state_model, schedules, "
             "plausibility, visualization, pipeline, 21 Unit-Tests, Basiskonfiguration auf "
             "n_jahr=3900 / Mo-Fr / 6 Tore / echte Kalendergewichte 2026 umgestellt."],
        ],
    )

    doc.add_paragraph()
    fusszeile = doc.add_paragraph(f"gate_scheduling Skriptversion {SCRIPT_VERSION} -- Dokumentation automatisch erzeugt.")
    fusszeile.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fusszeile.runs[0].font.size = Pt(8)
    fusszeile.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    Path(pfad).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(pfad))
