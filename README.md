# StageDesk Pro Site

Single page descrittiva di StageDesk Pro, pensata per Cloudflare Pages.

La pagina recupera automaticamente l'ultima release pubblicata su GitHub:

- macOS: DMG Apple Silicon e Intel;
- Windows: EXE e MSI;
- Linux: AppImage, DEB e RPM.

In caso di errore sulla GitHub API usa un fallback statico alla release `v1.0.13`.

## Deploy Cloudflare Pages

```bash
wrangler pages deploy . --project-name stagedesk-pro-site
```

Repository sorgente applicazione:

https://github.com/igelsomino/stagedesk-pro
