# Verifikation des ausgelieferten Pakets

Stand: 2026-09-08.

## Ausgeführt

- `python -m unittest discover -s tests -v`: **44 Tests, 0 Fehler**, unter Python 3.13.5.
- Kompletter Update-/Render-Ablauf mit kontrollierten REST-/GraphQL-Antworten, einschließlich zweier aufeinanderfolgender Updates, Nullwerten, fehlenden Werten, Stale-Status und Strict-Abbruch.
- Reale temporäre Git-Repositories für Added/Removed, inklusive Initial-Commit und gelöschter Zeile.
- Echte CLI-Subprozesse für Editieren, Hinzufügen, Umbenennen, Verschieben, Löschen, neue Abschnitte und interaktives Editieren.
- `profile.py render` und `profile.py check`: konsistent.
- Syntax der 14 Python-Quelldateien mit Python-3.10-Grammatik geprüft. Dies ersetzt keinen Runtime-Test unter Python 3.10.
- YAML eingelesen und sieben eingebettete Shell-Schritte mit `bash -n` geprüft. Offizielle Actions sind auf 40-stellige Commit-SHAs gepinnt. Kein vollständiger Actions-Schema-/Runner-Test.
- Original-ASCII-Asset per SHA-256 geprüft. Nur die äußeren Leerränder werden beim Rendern entfernt.
- Tests verwenden separate Fixtures; Änderungen an deinen echten Profilzeilen müssen keine Testannahmen erfüllen.

## Nicht ausgeführt

Ein authentifizierter GitHub-Actions-Run in deinem Account wurde nicht durchgeführt. Es wurde kein Remote-Repository angelegt oder verändert und kein Token des Benutzers verwendet. Die API-Tests nutzen simulierte Antworten; die Container-Netzwerkumgebung erlaubte keine direkten GitHub-Netzwerktests.

`cloc` war lokal nicht verfügbar. Der cloc-Aufruf und sein Rückgabe-/Fehlerverhalten wurden mit kontrollierten Prozessantworten geprüft, nicht mit einem realen cloc-Vollscan. Git-History-Auswertung wurde dagegen an echten lokalen Git-Repositories getestet. Für den optionalen Vollscan ist der erste aktivierte Actions-Run der Integrationstest.

Die ZIP enthält absichtlich keine Live-Statistikwerte. `n/a` bleibt bis zum erfolgreichen Abruf sichtbar.
