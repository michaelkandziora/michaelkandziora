# ASCII-Profil: Design und Umsetzung

## Auftrag
Die bereits besprochene Architektur `Template -> GitHub Action -> README` wird als herunterladbares Repository umgesetzt. Die Darstellung bleibt Markdown/ASCII. Der Nutzer hat die Umsetzung einschließlich dynamischem Python-CLI beauftragt.

## Datenfluss
`profile.json` (Abschnitte, stabile Zeilen-IDs, Labels, Werte) und `assets/portrait.txt` sind die editierbaren Quellen. `profile.py` bearbeitet die Konfiguration und rendert nach jeder Änderung `README.template.md` und `README.md`. Das Template enthält weiterhin `{{stats.*}}`-Tokens; die README enthält den letzten verifizierten Statistikstand aus `.profile/stats.json`. Die Action fragt REST und GraphQL ab und erzeugt beide Dateien erneut. Es gibt keine HTML-Marker im Codeblock und keine Tabulatoren.

## Layout
Beide Spalten werden zeilenweise mit `zip_longest` zusammengesetzt. Die linke Breite ergibt sich aus der sichtbaren Zeichenzahl des Porträts; rechts stehen Labels mit dynamischer Mindestbreite und Punktlinien. Zusätzliche Profilzeilen verlängern den Block, aber verschieben keine Bildzeichen. Lange Werte werden nicht abgeschnitten oder umgebrochen; GitHub kann den Codeblock horizontal scrollen.

## Metriken und Fehler
Nur öffentliche Repositories werden veröffentlicht. REST liefert Profil, paginierte eigene Repositories und öffentliche PR-Suche. GraphQL liefert auf öffentliche Repositories gefilterte Commit-Contributions der letzten 365 Tage. Unvollständige Antworten sind Fehler, keine vollständigen Nullwerte. Fehlende Werte werden `n/a`; nach einem Fehler bleiben zuvor erfolgreiche Werte mit `*` markiert. Ein optionaler, standardmäßig deaktivierter Git/cloc-Scan berechnet Snapshot-LOC und textuellen Churn im begrenzten Repository-Scope. Er führt keinen heruntergeladenen Projektcode aus. Keine privaten Reponamen oder Tokens werden persistiert.

## Auslieferung
ZIP ohne `.git`, Caches oder Secrets. Deutsches Setup-Handbuch, Metrikdefinitionen, CLI-Beispiele und automatisierte Tests. Die Veröffentlichung und erste authentifizierte Action führt der Nutzer aus. Lokale Tests ersetzen keinen echten Actions-Run.
