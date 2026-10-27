# GitHub-Best-Practices Design

## Ziel

Das Repository soll ohne Review-Pflicht geschützt, sicherer betrieben und
leichter wartbar werden. Bestehende CI-Prüfungen bleiben die maßgebliche
Qualitätsbarriere.

## Umfang

- `main` erhält verpflichtende Pull Requests, aber null erforderliche Reviews.
- Die bestehenden CI-Kontexte werden als Pflicht-Checks aktiviert.
- Veraltete Review-Conversations müssen vor dem Merge gelöst sein.
- Squash-Merges werden als einziger Merge-Modus zugelassen.
- Actions behalten minimale Rechte und SHA-gepinnte Abhängigkeiten.
- `SECURITY.md`, `CODEOWNERS` und eine Pull-Request-Vorlage dokumentieren den
  erwarteten Prozess.
- Secret-Scanning wird um Nicht-Provider-Muster ergänzt.
- Nicht verwendete Wiki-/Projects-Funktionen werden deaktiviert.

## Bewusste Nicht-Ziele

- Keine Review-Pflicht und keine Code-Owner-Freigabe.
- Keine neue CodeQL-/Scorecard-Pipeline in diesem Durchlauf.
- Keine Änderung der Anwendungslogik oder des Release-Ablaufs.

## Merge- und Prüfmodell

Die Branch Protection verlangt:

- Pull-Request vor Änderungen an `main`
- alle aktuellen Pflicht-Checks
- gelöste Review-Conversations
- lineare Historie
- keine Force-Pushes oder Branch-Löschungen

Die GitHub-API wird für Repository-Einstellungen und Branch Protection
verwendet; versionierte Dateien werden im Repository geprüft und committed.
