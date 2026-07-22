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

## StageDesk Store

Il percorso `/store/` è un catalogo responsive in stile libreria digitale. La pagina legge i copioni pubblicati
da Supabase, permette di cercare e filtrare per autore, genere, lingua, numero di attori, atti, scene e durata,
mostra copertina e metadati, registra i download e consente agli utenti autenticati di lasciare una valutazione.

I copioni vengono conservati nel bucket pubblico `store-packages`, mentre le copertine vengono conservate nel bucket
pubblico `store-covers`. Le policy limitano caricamento, modifica e cancellazione alla cartella dell'utente autenticato.
Il catalogo e le valutazioni restano protetti da Row Level Security; i download vengono incrementati tramite la
funzione SQL `increment_store_download` e le valutazioni tramite `rate_store_script`.

Per attivare il catalogo, eseguire nel SQL Editor di Supabase:

```text
studio-copione/docs/supabase-store.sql
```

La Pages Function `/store-config` espone alla pagina solo `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY`, configurati
come variabili/segreti dell'ambiente Cloudflare Pages. Non inserire mai una service-role key nel repository o nel
frontend. L'importazione diretta è mostrata solo quando lo Store è aperto dentro StageDesk Pro; in un browser normale
restano disponibili consultazione, ricerca e download.

### Inizializzazione del catalogo demo

Lo script `scripts/seed-store-demo.mjs` pubblica nel catalogo cinque copioni completi in formato StageDesk:
`Il malato immaginario`, `Il servitore di due padroni`, `Romeo e Giulietta`, `Amleto` e `La tempesta`.
Per ciascun titolo vengono caricati il pacchetto del copione, la copertina originale e i metadati di catalogo.
I testi dei quattro classici aggiuntivi sono adattamenti originali ispirati a opere di pubblico dominio e non
copiano traduzioni moderne protette.

Il catalogo viene caricato nel bucket con lo script
`scripts/seed-store-demo.mjs`. I pacchetti `.stagedesk` devono essere disponibili solo nella cartella locale indicata da
`STORE_PACKAGE_DIR`: non vengono inclusi nel deploy Cloudflare e vengono serviti esclusivamente dal bucket Supabase.
Eseguire dalla root del repository con variabili d'ambiente temporanee:

```sh
STORE_PACKAGE_DIR="/percorso/locale/ai/pacchetti" \\
SUPABASE_URL="https://<project>.supabase.co" \\
SUPABASE_SERVICE_ROLE_KEY="<chiave solo nell'ambiente locale>" \\
node scripts/seed-store-demo.mjs
```

La chiave di servizio non deve essere committata, inserita nel frontend o configurata come variabile pubblica di
Cloudflare Pages. Lo script è idempotente: aggiorna il record se il percorso del pacchetto esiste già.

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
