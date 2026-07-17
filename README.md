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
