# StageDesk Pro Site

Single page descrittiva di StageDesk Pro, pensata per Cloudflare Pages.

La pagina recupera automaticamente l'ultima release pubblicata su GitHub:

- macOS: DMG Apple Silicon e Intel;
- Windows: EXE e MSI;
- Linux: AppImage, DEB e RPM.

In caso di errore sulla GitHub API usa un fallback statico alla release `v1.0.13`.

La home contiene due caroselli distinti: `Anteprima` presenta le schermate reali dell'applicazione, mentre
`Funzionalità` descrive in dodici schede testuali il flusso di lavoro, dall'accesso e dalla gestione dei progetti
fino a cue, modalità spettacolo, export PDF, condivisione e aggiornamenti.

## Deploy Cloudflare Pages

```bash
wrangler pages deploy . --project-name stagedesk-pro-site
```

Repository sorgente applicazione:

https://github.com/igelsomino/stagedesk-pro

## Pagina attori condivisa

Il percorso `/share/[UID]` è una pagina responsive per l'apprendimento delle battute. Richiede autenticazione
con Google, GitHub, Azure oppure e-mail e password, quindi verifica il PIN di cinque cifre associato alla
condivisione.

La pagina usa la Pages Function `/share-config`, configurata con i secret Cloudflare Pages:

- `SUPABASE_URL`;
- `SUPABASE_PUBLISHABLE_KEY`.

Nel progetto Supabase devono essere eseguiti `docs/supabase-auth.sql` e `docs/supabase-sharing.sql` del repository
applicazione. La migrazione crea il bucket privato `published-scripts` e le policy per il caricamento dei file da parte del proprietario. Per i provider OAuth va aggiunto agli URL di redirect autorizzati anche:

```text
https://stagedesk-pro.aigconsulting.it/share/*
```
