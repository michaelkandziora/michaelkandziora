# ASCII Profile Implementation Plan

> Umsetzung in einer neuen, isolierten Sandbox; keine Änderungen an einem Remote-Repository.

**Goal:** Ein vollständiges Profilrepo für michaelkandziora mit ASCII-Layout, JSON-Editor, wiederholbaren Stats und ZIP.
**Architecture:** JSON plus unverändertes ASCII-Asset -> Markdown-Template -> aufgelöste README. REST/GraphQL und optional Git/cloc liefern validierte Cache-Metriken.
**Tech Stack:** Python >=3.10 Standardbibliothek, unittest, git, optionale cloc-CLI, GitHub Actions.
**Spec:** DESIGN.md

## Global Constraints
Keine SVGs, keine erfundenen Statistiken, keine Secrets im Paket, keine privaten Datenveröffentlichungen, keine Remote-Writes.

## Tasks
- [x] Renderer: zuerst Tests für Originalbild, Spaltenstabilität, wiederholtes Rendern, Unicode und unbekannte Tokens; dann Implementierung in profile_tool/render.py und profile_tool/model.py.
- [x] Editor: zuerst echte CLI-Tests in temporären Repos für add/set/rename/remove/move und Abschnittsänderungen; dann profile_tool/cli.py und profile.py.
- [x] API: Fake-Transporttests für Pagination, private Filter, 365-Tage-Queries, HTTP-/GraphQL-Fehler, Null und Cache-Staleness; dann profile_tool/github.py und profile_tool/stats.py.
- [x] Code-Analyse: Tests mit temporärem Git-Repo für Numstat, Dateinamen und Ausschlüsse, Scope-Guards; dann profile_tool/code_stats.py.
- [x] Workflow: Actions-Schema und Shell syntax prüfen; Tests vor Generierung/Commit, explizite Write-Permission, keine Force-Pushes, Push-/Cron-/manuelle Trigger, SHA-pinned offizielle Actions.
- [x] Verifikation: `python3 -m unittest discover -s tests -v`, `python3 profile.py render`, `python3 profile.py check`, CLI-Smoke-Tests, ZIP-Integrität und erneut entpackten Stand testen.
