"""Tor-Schedule-Erweiterung fuer EnergyPlus (AirflowNetwork).

Erzeugt aus den bestehenden Ankunfts- und Abfahrtsereignissen der
Crossdocking-Simulation torbezogene Toeroeffnungs-Schedules.

Konsumiert ausschliesslich JSON-Artefakte des bestehenden Pakets
``crossdocking_simulation`` (ergebnis_zeitachse.json, ergebnis_warenausgang.json).
Keine Aenderung an ``crossdocking_simulation`` selbst.
"""

__version__ = "0.1.0"
