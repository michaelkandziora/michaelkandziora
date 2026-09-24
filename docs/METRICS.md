# Definitionen der Profilstatistiken

Das README ist öffentlich. Private Repository-Namen und private Repository-Inhalte werden deshalb nie ausgegeben. Profilbezogene Zähler, die GitHub bei privater Aktivität gegenüber fremden Tokens ausblendet, werden nur mit einem als Profilinhaber authentifizierten `PROFILE_STATS_TOKEN` akzeptiert. Ohne diesen Token steht dort `n/a` statt eines scheinbar erfolgreichen falschen `0`. „Commits“ wird nicht als undefinierte all-time-Zahl ausgegeben. Der Cache enthält pro Kennzahl Wert, Status und Datum der letzten erfolgreichen Abfrage; Zeitangaben sind UTC.

| Token | Bedeutung |
|---|---|
| `{{stats.repos}}` | Anzahl deiner öffentlichen eigenen Repos. Standardmäßig ohne Forks; archivierte eigene Repos sind dabei. Nicht die Repos deiner Organisationen. |
| `{{stats.stars_received}}` | Summe der aktuellen `stargazers_count` der gezählten eigenen öffentlichen Repos. |
| `{{stats.stars}}` | Rückwärtskompatibler Alias für `stars_received`; im mitgelieferten Profil nicht mehr verwendet. |
| `{{stats.starred}}` | Anzahl öffentlicher Repositories, die du selbst mit einem Stern markiert hast. Erfordert `PROFILE_STATS_TOKEN`, damit private Profilaktivität nicht fälschlich als 0 erscheint. |
| `{{stats.followers}}` | Aktuelle Followerzahl aus der owner-authentifizierten Profilansicht. Erfordert `PROFILE_STATS_TOKEN`. |
| `{{stats.following}}` | Zahl der Accounts, denen du folgst. Erfordert `PROFILE_STATS_TOKEN`. |
| `{{stats.public_gists}}` | Öffentliche Gists laut Profil-API. |
| `{{stats.pull_requests}}` | Öffentlich indexierte, von dir eröffnete PRs, über alle verfügbaren Zeiträume und Zustände. Die REST-Suche läuft absichtlich **ohne Authentifizierung**, damit private PRs weder mitgezählt noch indirekt veröffentlicht werden. |
| `{{stats.commits_365d}}` | Öffentliche Commit-Contributions im rollierenden 365-Tage-Fenster bis zum Abrufzeitpunkt laut GitHub ContributionsCollection. **Nicht** alle lokalen Commits aller Branches und **nicht** Lifetime-Commits. |
| `{{stats.contributed_repos_365d}}` | Anzahl öffentlicher Repos mit deinen Commit-Contributions im selben Fenster, eigene und fremde. Kein vollständiger Zähler aller Issue-/Review-/PR-Aktivitäten. |
| `{{stats.loc}}` | Optional: Summe der von `cloc` als Code erkannten physischen Zeilen im aktuellen Default-Branch-Snapshot der ausgewählten Repos; ohne die von cloc erkannten Kommentar-/Leerzeilen. |
| `{{stats.added}}` / `{{stats.removed}}` | Optional: aufsummierte hinzugefügte/gelöschte **Textzeilen** aller Autoren in der vom aktuellen Default-Branch erreichbaren Nicht-Merge-Historie der ausgewählten Repos. Keine persönlichen LOC. |

Zusätzlich funktionieren `{{username}}`, `{{date}}` (UTC-Datum) und `{{days_since:YYYY-MM-DD}}`. Letzteres berechnet vergangene Tage ab einem **explizit eingetragenen** Datum. Es wird aus deiner bisherigen Uptime kein Geburtsdatum rekonstruiert. Die mitgelieferte Uptime bleibt statisch, bis du ihren Wert selbst änderst.

## GitHub-Zählregeln und Grenzen

GitHub-Contributions sind an GitHubs eigene Zuordnungs- und Branch-Regeln gebunden. Der Collector akzeptiert diese Abfrage nur, wenn der API-Token über `GET /user` tatsächlich als konfigurierte Profilidentität verifiziert wurde. Das verhindert den bisherigen Fehler, bei dem ein repository-scoped Actions-`GITHUB_TOKEN` bei privater Aktivität einen plausibel aussehenden Nullwert lieferte. Anschließend werden weiterhin ausschließlich Repository-Gruppen mit `isPrivate == false` summiert; private Commit-Zahlen und private Repository-Namen werden nicht veröffentlicht.

Die Commit-Abfrage fordert maximal 100 Repo-Gruppen an und vergleicht die Anzahl mit dem API-Gesamtzähler. Bei Abweichung wird die Kennzahl verworfen und `n/a` oder der letzte erfolgreiche Stand mit `*` angezeigt. Sie wird nicht als vollständige Zahl ausgegeben. Für mehr als 100 Commit-Repos im 365-Tage-Fenster wäre eine zeitlich partitionierte Erweiterung des Collectors erforderlich; das Paket behauptet diese Grenze nicht zu umgehen.

REST-Repository-Listen werden vollständig paginiert. Ein `incomplete_results` der PR-Suche wird als Fehler behandelt. Gruppenfehler sind getrennt: fehlende Commit-Berechtigung verhindert beispielsweise nicht die Veröffentlichung erfolgreich geladener Follower-/Starzahlen.

## Code-Auswertung

Standardmäßig deaktiviert. Die optionale Auswertung berücksichtigt nur eigene öffentliche Nicht-Forks, nicht das Profilrepo selbst, und standardmäßig keine archivierten Repos. Über `code.repositories` kann eine explizite Teilmenge gewählt werden. Damit bedeutet LOC nicht automatisch „alle Zeilen auf ganz GitHub“.

Jeder Repo-Clone enthält die Historie des Default-Branches, ohne andere Branches/Tags, Submodule oder ausgecheckte Git-LFS-Nutzdaten. Repository-/Größen-/Zeitlimits verhindern unbegrenzte Scans. Die Größenangabe der GitHub-API ist ein vorgelagerter Plausibilitätsfilter, keine harte Netzwerk-Byte-Quota. Ein Fehler verwirft den vollständigen LOC/Churn-Collector-Durchlauf, statt teilweise Ergebnisse zu addieren.

cloc nutzt `--vcs=git`. Nicht getrackte Dateien und die konfigurierten Dependency-/Buildverzeichnisse bzw. Lock-Dateien werden ausgeschlossen. cloc erkennt viele Dateitypen einschließlich mancher Konfigurations-/Markup-Sprachen; der Wert ist kein Qualitäts- oder Produktivitätsmaß.

Der historische Churn nutzt `git log --numstat -z --no-merges --no-renames` über `HEAD`, ohne externe Diff-Treiber/Textconv. Binärdiffs werden ausgelassen. Directory-/Filename-Ausschlüsse gelten ebenfalls. Churn umfasst auch Kommentare, Dokumentation und später gelöschte Textdateien. Renames zählen als Entfernen/Hinzufügen. Merge-Resolution-Änderungen aus ausgeschlossenen Merge-Commits werden nicht zusätzlich gezählt. Forks/Mirrors oder identische Inhalte in mehreren eigenen Repos sind keine automatische globale Deduplizierung.

**Wichtig: `LOC` ist nicht `ADDED - REMOVED`.** Snapshot-Codezeilen und historischer Text-Churn sind unterschiedliche Messgrößen; sie werden nur kompakt in derselben Anzeige zusammengefasst.

## Fehlerstatus

`n/a` bedeutet, dass noch kein verlässlicher Wert vorliegt oder ein Collector deaktiviert ist. `0` ist ausschließlich ein erfolgreich gelesener/berechneter Nullwert. `123*` bedeutet: letzter erfolgreicher Wert, der aktuelle Abruf ist fehlgeschlagen. Das zugehörige Datum steht in `.profile/stats.json`.

Ein geänderter Code-Scope invalidiert den bisherigen LOC-/Churn-Stand; ein alter Wert eines anderen Scopes wird nicht als neuer angezeigt. Deaktivierter Code-Scan blendet alte Zahlen aus. Der Cache darf nicht unter einem anderen Benutzernamen weiterverwendet werden.

Ohne `--strict` werden erfolgreiche Collector neben fehlgeschlagenen veröffentlicht. Bei vollständigem Ausfall wird nichts geändert. Mit `--strict` verhindert jeder Fehler eines aktiven Collectors sämtliche Schreibvorgänge. Das ist keine automatische Garantie, dass ein von GitHub als erfolgreich ausgegebener Wert bereits alle sehr neuen Aktivitäten enthält.

## Quellen

- [REST repositories](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user)
- [GraphQL Users / ContributionsCollection](https://docs.github.com/en/graphql/reference/users#contributionscollection)
- [GitHub Profile Contributions](https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference)
- [cloc](https://github.com/AlDanial/cloc)
- [git log](https://git-scm.com/docs/git-log)

## Workflow-Authentifizierung

Für die owner-sensitiven Kennzahlen wird im Repository-Secret `PROFILE_STATS_TOKEN` ein GitHub Personal Access Token erwartet, der als `michaelkandziora` authentifiziert ist. Der Workflow verwendet diesen Token **nur für Statistikabfragen**; der Checkout-/Push-Credential bleibt das separate Actions-`GITHUB_TOKEN`. Ein fehlender, falscher oder als GitHub-App/Installation authentifizierter Token erzeugt für Followers, Following, Starred und Contribution-Zähler `n/a`/stale statt `0`.
