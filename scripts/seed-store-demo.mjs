import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
const projectRoot = fileURLToPath(new URL('..', import.meta.url))
const packagePath = 'official/il-malato-immaginario-riscrittura.stagedesk'
const packageFile = resolve(projectRoot, 'store/copioni/il-malato-immaginario-riscrittura.stagedesk')

if (!supabaseUrl || !serviceRoleKey) {
  throw new Error('Impostare SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY solo nell’ambiente di esecuzione.')
}

const title = 'Il malato immaginario'
const headers = { apikey: serviceRoleKey, Authorization: `Bearer ${serviceRoleKey}` }
const packageContent = await readFile(packageFile)
const uploadResponse = await fetch(`${supabaseUrl}/storage/v1/object/store-packages/${packagePath}`, {
  method: 'POST',
  headers: { ...headers, 'Content-Type': 'application/vnd.stagedesk.script', 'x-upsert': 'true' },
  body: packageContent,
})
if (!uploadResponse.ok) throw new Error(`Upload copione fallito (${uploadResponse.status}): ${await uploadResponse.text()}`)

const query = new URL(`${supabaseUrl}/rest/v1/store_scripts`)
query.searchParams.set('select', 'id')
query.searchParams.set('package_path', `eq.${packagePath}`)
query.searchParams.set('limit', '1')
const existingResponse = await fetch(query, { headers })
if (!existingResponse.ok) throw new Error(`Lettura catalogo fallita (${existingResponse.status}): ${await existingResponse.text()}`)
const existing = await existingResponse.json()

const metadata = {
  title,
  subtitle: 'Versione integrale originale per la prova',
  description: 'Una riscrittura originale integrale ispirata alla commedia di Molière, con tre atti, sedici scene, personaggi, battute e note di regia già organizzati per StageDesk Pro.',
  author_name: 'StageDesk Pro',
  language: 'Italiano',
  genre: 'Teatro',
  rights_label: 'Testo originale',
  tags: ['Formato StageDesk', 'Note di regia'],
  actor_count: 11,
  act_count: 3,
  scene_count: 16,
  estimated_minutes: 90,
  cover_path: null,
  package_path: packagePath,
  package_name: 'il-malato-immaginario-riscrittura.stagedesk',
  format_version: '1',
  is_published: true,
}

if (existing[0]?.id) {
  const updateResponse = await fetch(`${supabaseUrl}/rest/v1/store_scripts?id=eq.${existing[0].id}`, {
    method: 'PATCH',
    headers: { ...headers, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
    body: JSON.stringify(metadata),
  })
  if (!updateResponse.ok) throw new Error(`Aggiornamento catalogo fallito (${updateResponse.status}): ${await updateResponse.text()}`)
  console.log(`Copione demo aggiornato: ${packagePath}`)
} else {
  const insertResponse = await fetch(`${supabaseUrl}/rest/v1/store_scripts`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
    body: JSON.stringify(metadata),
  })
  if (!insertResponse.ok) throw new Error(`Inserimento catalogo fallito (${insertResponse.status}): ${await insertResponse.text()}`)
  console.log(`Copione demo pubblicato: ${packagePath}`)
}
