import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
const projectRoot = fileURLToPath(new URL('..', import.meta.url))
const packageDir = resolve(projectRoot, process.env.STORE_PACKAGE_DIR || '.store-assets/copioni')
const coverDir = resolve(projectRoot, process.env.STORE_COVER_DIR || '.store-assets/copertine')

if (!supabaseUrl || !serviceRoleKey) {
  throw new Error('Impostare SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY solo nell’ambiente di esecuzione.')
}

const headers = { apikey: serviceRoleKey, Authorization: `Bearer ${serviceRoleKey}` }
const catalog = [
  { slug: 'il-malato-immaginario', title: 'Il malato immaginario', author: 'Molière · traduzione storica Niccolò di Castelli', subtitle: 'Edizione integrale con note di regia originali', description: 'La commedia integrale in tre atti e sedici scene, con il testo della fonte storica, le didascalie e note originali per la preparazione della prova.', actors: 11, acts: 3, scenes: 16, minutes: 120, rights: 'Edizione storica in pubblico dominio; fonte digitale UB Paderborn', tags: ['Edizione integrale', 'Commedia', 'Note di regia'], package: 'il-malato-immaginario-riscrittura.stagedesk', cover: 'il-malato-immaginario.jpg' },
  { slug: 'il-servitore-di-due-padroni', title: 'Il servitore di due padroni', author: 'Carlo Goldoni · Progetto Manuzio', subtitle: 'Edizione integrale con note di regia originali', description: 'La commedia integrale in tre atti e cinquantanove scene, con battute, didascalie e note originali per lavorare su ritmo, entrate e intrecci.', actors: 12, acts: 3, scenes: 59, minutes: 180, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Commedia', 'Note di regia'], package: 'il-servitore-di-due-padroni.stagedesk', cover: 'il-servitore-di-due-padroni.jpg' },
  { slug: 'romeo-e-giulietta', title: 'Romeo e Giulietta', author: 'William Shakespeare · traduzione Goffredo Raponi', subtitle: 'Edizione integrale con note di regia originali', description: 'La tragedia integrale in cinque atti e ventiquattro scene, con la traduzione di Goffredo Raponi, le didascalie e note originali per la regia.', actors: 24, acts: 5, scenes: 24, minutes: 180, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Tragedia', 'Note di regia'], package: 'romeo-e-giulietta.stagedesk', cover: 'romeo-e-giulietta.jpg' },
  { slug: 'amleto', title: 'Amleto', author: 'William Shakespeare · traduzione Goffredo Raponi', subtitle: 'Edizione integrale con note di regia originali', description: 'La tragedia integrale in cinque atti e venti scene, con il testo della fonte, le didascalie e note originali per il lavoro sul teatro nel teatro.', actors: 20, acts: 5, scenes: 20, minutes: 210, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Tragedia', 'Teatro nel teatro'], package: 'amleto.stagedesk', cover: 'amleto.jpg' },
  { slug: 'la-tempesta', title: 'La tempesta', author: 'William Shakespeare · traduzione Goffredo Raponi', subtitle: 'Edizione integrale con note di regia originali', description: 'La commedia integrale in cinque atti e nove scene, con il testo della fonte, le didascalie e note originali su spazio, ritmo e coralità.', actors: 22, acts: 5, scenes: 9, minutes: 150, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Fiaba teatrale', 'Note di regia'], package: 'la-tempesta.stagedesk', cover: 'la-tempesta.jpg' },
  { slug: 'macbeth', title: 'Macbeth', author: 'William Shakespeare · traduzione Goffredo Raponi', subtitle: 'Edizione integrale con note di regia originali', description: 'La tragedia integrale in cinque atti e ventotto scene, con la traduzione di Goffredo Raponi, le didascalie e note originali per la costruzione della tensione.', actors: 20, acts: 5, scenes: 28, minutes: 180, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Tragedia', 'Note di regia'], package: 'macbeth.stagedesk', cover: 'macbeth.jpg' },
  { slug: 'l-avaro', title: "L'avaro", author: 'Carlo Goldoni · Progetto Manuzio', subtitle: 'Edizione integrale con note di regia originali', description: 'La commedia integrale in un atto e sedici scene, con il testo di Carlo Goldoni e note originali per il lavoro su ritmo, relazioni e oggetti di scena.', actors: 7, acts: 1, scenes: 16, minutes: 75, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Commedia', 'Note di regia'], package: 'l-avaro.stagedesk', cover: 'l-avaro.jpg' },
  { slug: 'casa-di-bambola', title: 'Casa di bambola', author: 'Henrik Ibsen · traduzione Pietro Galletti', subtitle: 'Edizione integrale con note di regia originali', description: 'Il dramma integrale in tre atti e trentuno scene, nell’edizione Treves del 1928, con le didascalie e note originali per il lavoro sulla casa e sui rapporti di potere.', actors: 10, acts: 3, scenes: 31, minutes: 150, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Dramma', 'Note di regia'], package: 'casa-di-bambola.stagedesk', cover: 'casa-di-bambola.jpg' },
  { slug: 'don-giovanni', title: 'Don Giovanni', author: 'Lorenzo Da Ponte', subtitle: 'Edizione integrale con note di regia originali', description: 'Il libretto integrale in due atti e diciannove scene, con battute, indicazioni sceniche e note originali per seguire la macchina teatrale e musicale.', actors: 12, acts: 2, scenes: 19, minutes: 180, rights: 'CC BY-SA 3.0 e GFDL · fonte Wikisource', tags: ['Edizione integrale', 'Libretto', 'Note di regia'], package: 'don-giovanni.stagedesk', cover: 'don-giovanni.jpg' },
  { slug: 'la-commedia-degli-equivoci', title: 'La commedia degli equivoci', author: 'William Shakespeare · traduzione Goffredo Raponi', subtitle: 'Edizione integrale con note di regia originali', description: 'La commedia integrale in cinque atti e undici scene, con la traduzione di Goffredo Raponi, le didascalie e note originali sul ritmo degli equivoci.', actors: 14, acts: 5, scenes: 11, minutes: 135, rights: 'CC BY-NC-SA 4.0 · fonte Liber Liber', tags: ['Edizione integrale', 'Commedia', 'Note di regia'], package: 'la-commedia-degli-equivoci.stagedesk', cover: 'la-commedia-degli-equivoci.jpg' },
]

async function upload(bucket, path, content, contentType) {
  const response = await fetch(`${supabaseUrl}/storage/v1/object/${bucket}/${path}`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': contentType, 'x-upsert': 'true' },
    body: content,
  })
  if (!response.ok) throw new Error(`Upload fallito per ${path} (${response.status}): ${await response.text()}`)
}

for (const entry of catalog) {
  const packagePath = `official/${entry.package}`
  const coverPath = `official/${entry.cover}`
  await upload('store-packages', packagePath, await readFile(resolve(packageDir, entry.package)), 'application/vnd.stagedesk.script')
  await upload('store-covers', coverPath, await readFile(resolve(coverDir, entry.cover)), 'image/jpeg')

  const query = new URL(`${supabaseUrl}/rest/v1/store_scripts`)
  query.searchParams.set('select', 'id')
  query.searchParams.set('package_path', `eq.${packagePath}`)
  query.searchParams.set('limit', '1')
  const existingResponse = await fetch(query, { headers })
  if (!existingResponse.ok) throw new Error(`Lettura catalogo fallita (${existingResponse.status}): ${await existingResponse.text()}`)
  const existing = await existingResponse.json()
  const metadata = {
    title: entry.title,
    subtitle: entry.subtitle,
    description: entry.description,
    author_name: entry.author,
    language: 'Italiano',
    genre: 'Teatro',
    rights_label: entry.rights,
    tags: entry.tags,
    actor_count: entry.actors,
    act_count: entry.acts,
    scene_count: entry.scenes,
    estimated_minutes: entry.minutes,
    cover_path: coverPath,
    package_path: packagePath,
    package_name: entry.package,
    format_version: '1',
    is_published: true,
  }
  const endpoint = existing[0]?.id
    ? `${supabaseUrl}/rest/v1/store_scripts?id=eq.${existing[0].id}`
    : `${supabaseUrl}/rest/v1/store_scripts`
  const response = await fetch(endpoint, {
    method: existing[0]?.id ? 'PATCH' : 'POST',
    headers: { ...headers, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
    body: JSON.stringify(metadata),
  })
  if (!response.ok) throw new Error(`Catalogo non aggiornato per ${entry.title} (${response.status}): ${await response.text()}`)
  console.log(`${existing[0]?.id ? 'Aggiornato' : 'Pubblicato'}: ${entry.title}`)
}
