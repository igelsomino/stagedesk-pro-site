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
  { slug: 'il-malato-immaginario', title: 'Il malato immaginario', author: 'Molière · StageDesk Pro', subtitle: 'Versione integrale originale per la prova', description: 'Una riscrittura originale integrale ispirata alla commedia di Molière, con tre atti, sedici scene, personaggi, battute e note di regia.', actors: 11, scenes: 16, minutes: 90, rights: 'Testo originale', tags: ['Formato StageDesk', 'Note di regia'], package: 'il-malato-immaginario-riscrittura.stagedesk', cover: 'il-malato-immaginario.jpg' },
  { slug: 'il-servitore-di-due-padroni', title: 'Il servitore di due padroni', author: 'Carlo Goldoni · StageDesk Pro', subtitle: 'Adattamento originale integrale per la prova', description: 'Una riscrittura originale integrale della commedia goldoniana: equivoci, lettere, fame e identità nascoste.', actors: 10, scenes: 12, minutes: 105, rights: 'Adattamento originale', tags: ['Commedia', 'Formato StageDesk'], package: 'il-servitore-di-due-padroni.stagedesk', cover: 'il-servitore-di-due-padroni.jpg' },
  { slug: 'romeo-e-giulietta', title: 'Romeo e Giulietta', author: 'William Shakespeare · StageDesk Pro', subtitle: 'Adattamento originale integrale per la prova', description: 'Una riscrittura originale integrale della tragedia di Verona: due giovani cercano una lingua comune mentre le famiglie difendono confini vuoti.', actors: 10, scenes: 11, minutes: 115, rights: 'Adattamento originale', tags: ['Tragedia', 'Formato StageDesk'], package: 'romeo-e-giulietta.stagedesk', cover: 'romeo-e-giulietta.jpg' },
  { slug: 'amleto', title: 'Amleto', author: 'William Shakespeare · StageDesk Pro', subtitle: 'Adattamento originale integrale per la prova', description: 'Una riscrittura originale integrale della tragedia danese: memoria, potere e teatro cercano la verità senza perdere se stessi.', actors: 10, scenes: 11, minutes: 125, rights: 'Adattamento originale', tags: ['Tragedia', 'Teatro nel teatro'], package: 'amleto.stagedesk', cover: 'amleto.jpg' },
  { slug: 'la-tempesta', title: 'La tempesta', author: 'William Shakespeare · StageDesk Pro', subtitle: 'Adattamento originale integrale per la prova', description: 'Una riscrittura originale integrale della fiaba politica sull’isola: potere, libertà e perdono si incontrano in una prova di teatro.', actors: 11, scenes: 11, minutes: 110, rights: 'Adattamento originale', tags: ['Fiaba politica', 'Formato StageDesk'], package: 'la-tempesta.stagedesk', cover: 'la-tempesta.jpg' },
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
    act_count: 3,
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
