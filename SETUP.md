# michaelkandziora: Profil veröffentlichen und bearbeiten

Dieses Repository erzeugt eine klassische README mit deinem echten ASCII-Porträt links und editierbaren Angaben rechts. Kein SVG, keine Stats-Card, kein externer Bildservice. Das Porträt stammt aus der ersten Webarchive; die Profilwerte aus deiner zuletzt bearbeiteten README. Die vollständige Originalgrafik einschließlich der dort fehlenden unteren Zeilen ist enthalten.

## 1. Voraussetzungen

Lokal: Python **3.10 oder neuer**, `git`, GitHub CLI `gh` und zum Entpacken `unzip`. Keine Python-Pakete, keine venv und kein pip erforderlich. Für die optionale Code-Auswertung zusätzlich `cloc`.

Debian/Ubuntu, als root (sonst `sudo` vor die beiden Befehle):

```bash
apt-get update
apt-get install -y git gh python3 unzip
```

Befehle unten sind für Bash/zsh. Unter Windows `python` statt `python3` verwenden und die ZIP normal entpacken; der Editor ist plattformunabhängig. Der Git/cloc-Scan wird vorzugsweise auf Linux oder im GitHub-Runner ausgeführt.

## 2. ZIP entpacken und lokal ansehen

```bash
unzip michaelkandziora-profile.zip
cd michaelkandziora
python3 profile.py show
python3 profile.py preview
python3 -m unittest discover -s tests -v
```

Die mitgelieferte README enthält noch keine behaupteten Live-Zahlen: `n/a` bedeutet „nicht abgefragt/nicht verfügbar“. Die Platzhalter `<DISCORD>` und der leere Website-Wert stammen aus deiner Vorlage. Deine eingetragene E-Mail wird beim Push in ein öffentliches Repository öffentlich; prüfe die Profilangaben vor dem Veröffentlichen.

## 3. GitHub anmelden

```bash
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
gh auth setup-git
gh auth status
gh api user --jq .login
```

Die letzte Ausgabe muss `michaelkandziora` sein. Bei einem anderen bereits angemeldeten Account:

```bash
gh auth switch --hostname github.com --user michaelkandziora
```

Wenn bereits angemeldet, aber die Workflow-Berechtigung fehlt:

```bash
gh auth refresh --hostname github.com --scopes workflow
```

Die OAuth-Berechtigung `workflow` betrifft deinen initialen Push von Workflow-Dateien. Sie ist nicht dasselbe wie die `contents: write`-Berechtigung des späteren Actions-Tokens.

## 4. Neues Profilrepo erstellen und pushen

Nur benutzen, wenn `michaelkandziora/michaelkandziora` noch nicht existiert. Die ZIP enthält absichtlich kein `.git` und keinen Remote.

```bash
git init -b main
git config user.name 'michaelkandziora'
git config user.email "$(gh api user --jq '.id | tostring')+michaelkandziora@users.noreply.github.com"

python3 profile.py render
python3 profile.py check

git add .
git commit -m 'feat: ASCII profile with automated GitHub stats'

gh repo create michaelkandziora/michaelkandziora \
  --public \
  --source=. \
  --remote=origin \
  --description 'ASCII profile with automated public GitHub statistics' \
  --push

gh repo edit michaelkandziora/michaelkandziora --default-branch main
```

GitHub zeigt die README als Profil an, weil das **öffentliche** Repository exakt wie der Benutzer heißt und eine nichtleere `README.md` im Root enthält. Der Updater ist hier auf `main` konfiguriert.

### Bereits existierendes Repository

Nicht löschen und nicht mit `--force` überschreiben. Stattdessen klonen und die Dateien aus dem entpackten Paket auf einem Arbeitsbranch übernehmen. Beispiel, wenn die ZIP im aktuellen Verzeichnis liegt:

```bash
unzip michaelkandziora-profile.zip -d profile-package
gh repo clone michaelkandziora/michaelkandziora existing-profile
cd existing-profile
git switch -c profile-readme-setup
cp -a ../profile-package/michaelkandziora/. ./
python3 -m unittest discover -s tests -v
python3 profile.py render
git status --short
git diff --stat
git add .
git commit -m 'feat: ASCII profile with automated stats'
git push -u origin profile-readme-setup
gh pr create --title 'ASCII profile with automated stats' --body 'Adds the editable ASCII profile and public statistics updater.'
```

Die Kopie ersetzt gleichnamige lokale Dateien, aber nicht die Git-Historie. Vor Commit/Merge den Diff prüfen. Bei anderem Default-Branch als `main` **vor dem Merge** die Branch-Angaben in `.github/workflows/update-readme.yml` und `test.yml` entsprechend ändern. Den ZIP-Root nur in einem sauberen Arbeitsverzeichnis übernehmen, nicht über ungesicherte lokale Änderungen kopieren.

## 5. Actions starten und beobachten

Der erste Push nach `main` startet den Updater bereits. Zusätzlicher manueller Start:

```bash
gh workflow run update-readme.yml --repo michaelkandziora/michaelkandziora --ref main
gh run list --repo michaelkandziora/michaelkandziora --workflow update-readme.yml --limit 5
gh run watch --repo michaelkandziora/michaelkandziora --exit-status
```

`gh run watch` bietet die vorhandenen Runs zur Auswahl an. Bei einem Fehler die Run-ID aus der Liste verwenden:

```bash
gh run view RUN_ID --repo michaelkandziora/michaelkandziora --log-failed
```

Der Updater läuft zusätzlich täglich um **03:17 UTC** sowie bei Pushes relevanter Konfigurations-/Quelldateien nach `main`. Der Schedule ist nicht minutengenau garantiert. Die Scheduled-Workflow-Datei muss auf dem Default-Branch liegen. GitHub kann Schedules öffentlicher Repos nach 60 Tagen ohne Repository-Aktivität deaktivieren; dann unter Actions oder mit `gh workflow enable update-readme.yml` aktivieren.

Die Action verwendet automatisch `GITHUB_TOKEN` und beantragt ausschließlich `contents: write` für den Update-Job. Für den normalen öffentlichen Betrieb ist **kein manuell angelegtes Secret vorgesehen**. Restriktive Account-/Organisationsrichtlinien oder Branch-Regeln können direkte Bot-Pushes trotzdem blockieren. Dann eine gezielte Policy für dieses Profilrepo oder einen PR-basierten Update-Prozess verwenden, nicht pauschal Sicherheitsregeln deaktivieren.

Optional kann ein eigener API-Token als `PROFILE_STATS_TOKEN` hinterlegt werden, falls die GraphQL-Abfrage mit dem Standardtoken im konkreten Account nicht zugelassen ist. Dazu in GitHub einen passend beschränkten Read-Token erzeugen und interaktiv hinterlegen:

```bash
gh secret set PROFILE_STATS_TOKEN --repo michaelkandziora/michaelkandziora
```

Der Token wird verdeckt abgefragt, nicht in eine Datei geschrieben. Der Collector filtert weiterhin auf öffentliche Daten. Der API-Token ersetzt **nicht** den Schreibtoken des Checkout-/Push-Schritts. Ein eigener API-Token ist keine automatische Lösung für Branch-Protection.

## 6. Profil bearbeiten

**Vor neuen Änderungen den letzten Bot-Commit holen:**

```bash
git pull --ff-only
python3 profile.py edit
```

Der interaktive Editor zeigt die stabilen IDs. Mögliche Befehle: `show`, `set`, `rename`, `add`, `remove`, `move`, `section`, `preview`, `quit`. Jede gültige Änderung wird sofort gespeichert und in beide Markdown-Dateien gerendert. `quit` verwirft vorherige Änderungen nicht.

### Direkte CLI-Befehle

Wert ändern, sichtbaren Key umbenennen:

```bash
python3 profile.py set ide --value 'VS Code + Neovim'
python3 profile.py rename ide --key 'Editors'
```

Die ID bleibt `ide`, obwohl rechts jetzt „Editors“ angezeigt wird.

Zeile hinzufügen, verschieben und entfernen:

```bash
python3 profile.py add --section languages --id frameworks --key Frameworks --value 'React, FastAPI, Node.js'
python3 profile.py move frameworks --section languages --before human
python3 profile.py remove frameworks
```

Neuen Abschnitt ergänzen und umbenennen:

```bash
python3 profile.py section-add projects --title 'Current Projects'
python3 profile.py add --section projects --id domtec --key DOMTEC --value 'Automation and smart home'
python3 profile.py section-rename projects --title Projects
python3 profile.py section-move projects --before github
```

Zusätzliche dynamische Stat-Zeile:

```bash
python3 profile.py add --section github --id following --key Following --value '{{stats.following}}'
```

Die einfachen Shell-Anführungszeichen halten die geschweiften Klammern unverändert. Labels und statische Werte können in JSON auch manuell bearbeitet werden. Danach `python3 profile.py render` ausführen. Weder `README.md` noch `README.template.md` dauerhaft von Hand ändern: Beide werden generiert.

Abstände und Vorschau:

```bash
python3 profile.py layout --gap 5 --label-width 20 --rule-width 52
python3 profile.py preview
python3 profile.py preview --template
python3 profile.py metrics
python3 profile.py check
```

Lange Werte werden **nicht** abgeschnitten oder automatisch in neue Bildzeilen umgebrochen. Die linke ASCII-Spalte bleibt vollständig erhalten; auf schmalen Ansichten wird der große Codeblock horizontal gescrollt. ASCII hat keine mobile responsive Zweispaltenfunktion.

Änderungen veröffentlichen:

```bash
git add profile.json README.template.md README.md
git commit -m 'docs: update profile details'
git push
```

Bei einem Bot-Commit zwischen Pull und Push wird der Push möglicherweise abgewiesen. Erst `git pull --rebase` ausführen, eventuelle Konflikte sauber lösen, anschließend `python3 profile.py render` und erneut committen/pushen. **Kein Force-Push.**

## 7. Stats lokal aktualisieren

`render` und der Editor funktionieren offline. `update` nutzt die API:

```bash
GH_TOKEN="$(gh auth token --hostname github.com)" python3 profile.py update
python3 profile.py check
```

Ohne Token funktionieren die öffentlichen REST-Abfragen, die GraphQL-Commit-Metriken jedoch nicht. Teilfehler ergeben `n/a` oder einen mit `*` markierten letzten erfolgreichen Wert. Bei einem vollständigen Ausfall bleiben Dateien unverändert. Für Abbruch bei jedem einzelnen fehlgeschlagenen aktiven Collector:

```bash
GH_TOKEN="$(gh auth token --hostname github.com)" python3 profile.py update --strict
```

`--strict` betrifft nur die ausgewählten aktiven Collector; deaktiviertes LOC gilt nicht als Fehler.

## 8. Optional: LOC und Added/Removed aktivieren

Die gesamte öffentliche Git-Historie jedes Repos täglich neu zu klonen kann teuer und langsam sein. Deshalb ist der Code-Scan initial deaktiviert und LOC/Churn stehen auf `n/a`; die anderen Stats funktionieren unabhängig davon. Eine explizite kleine Repo-Auswahl ist meist sinnvoller als „alles“.

```bash
# Den Namen durch einen echten eigenen öffentlichen Nicht-Fork ersetzen:
python3 profile.py code enable --repo michaelkandziora/DEIN_REPO

# Mehrere Repos: --repo wiederholen.
# Ohne --repo bleibt eine bestehende Auswahl erhalten;
# die initial leere Auswahl bedeutet alle geeigneten eigenen öffentlichen Repos.
python3 profile.py code show
```

Danach Konfiguration und generierte Dateien committen/pushen. Die Action installiert `cloc` dann automatisch. Lokal vorher `apt-get install -y cloc` (als root), dann den normalen `update`-Befehl verwenden. Ausschalten:

```bash
python3 profile.py code disable
```

Die Einstellungen in `profile.json` begrenzen den Scan standardmäßig auf höchstens 40 Repositories, höchstens 200000 KiB GitHub-Reposize pro Repo und 180 Sekunden je Git-/cloc-Aufruf; der gesamte Workflow hat ein 30-Minuten-Limit. Diese Schranken liefern im Grenzfall einen Fehler bzw. `n/a`/`*`, **keine still gekürzte Gesamtsumme**. Es wird kein Code der geklonten Projekte ausgeführt. Das Profilrepo selbst, Forks, private Repos und standardmäßig archivierte Repos werden ausgeschlossen. `repositories: []` setzt die Auswahl auf alle geeigneten Repos zurück.

Siehe **[docs/METRICS.md](docs/METRICS.md)** für die exakten Unterschiede zwischen aktuellem Codeumfang, historischen Textänderungen und persönlichen Contributions.

## Dateien und Zuständigkeiten

```text
profile.json               Deine Abschnitte, Zeilen-IDs, Keys, Values und Einstellungen
assets/portrait.txt        Unveränderte Original-ASCII-Textquelle
profile.py                 Einstieg für den CLI-Editor
profile_tool/              Renderer, Konfiguration, API und optionaler Code-Scan
README.template.md         Generierter kompletter ASCII-Block mit dynamischen Tokens
README.md                  Generierter kompletter ASCII-Block mit letzten Stats
.profile/stats.json        Öffentliche Zahlen, Status und Datum erfolgreicher Abfragen
.github/workflows/         Automatischer Updater und Offline-Tests
.github/dependabot.yml     Monatliche Vorschläge für Action-Pin-Updates
tests/                     unittest-Suite einschließlich realer Git-Fixtures
```

## Offizielle Referenzen

- [GitHub Profil-README](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/managing-your-profile-readme)
- [gh repo create](https://cli.github.com/manual/gh_repo_create), [gh auth login](https://cli.github.com/manual/gh_auth_login), [gh workflow run](https://cli.github.com/manual/gh_workflow_run)
- [GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token), [Workflow-Ereignisse und Schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [REST: Public User Repositories](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user)
- [GraphQL: ContributionsCollection](https://docs.github.com/en/graphql/reference/users#contributionscollection)
- [cloc](https://github.com/AlDanial/cloc)

Stand des Pakets: 2026-09-08. Action-SHAs wurden gegen die offiziellen Tag-Referenzen geprüft. Ein vollständiger authentifizierter Workflow-Run im Benutzeraccount ist vor der Veröffentlichung der ZIP nicht erfolgt.
