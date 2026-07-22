import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const IMPORT_MESSAGE = 'stagedesk-store-import'
const CONTEXT_MESSAGE = 'stagedesk-store-context'
const CONFIG_URL = '/store-config'
const state = {
  client: null,
  session: null,
  books: [],
  filtered: [],
  canImport: false,
  selectedBook: null,
  configError: '',
}

const $ = (selector) => document.querySelector(selector)
const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char])
const asNumber = (value) => Number.isFinite(Number(value)) ? Number(value) : 0
const demoBook = {
  id: 'demo-il-malato-immaginario',
  title: 'Il malato immaginario',
  subtitle: 'Edizione integrale con note di regia originali',
  description: 'La commedia integrale in tre atti e sedici scene, con il testo della fonte storica, le didascalie e note originali per la preparazione della prova.',
  authorName: 'Molière · traduzione storica Niccolò di Castelli',
  language: 'Italiano',
  genre: 'Teatro',
  rightsLabel: 'Edizione storica in pubblico dominio; fonte digitale UB Paderborn',
  actorCount: 11,
  actCount: 3,
  sceneCount: 16,
  estimatedMinutes: 90,
  tags: ['Formato StageDesk', 'Note di regia'],
  downloadCount: 0,
  averageRating: 0,
  ratingCount: 0,
  packageUrl: 'https://insoqzhjmrbrgfrsmlnj.supabase.co/storage/v1/object/public/store-packages/official/il-malato-immaginario-riscrittura.stagedesk',
  coverUrl: '',
  isDemo: true,
}

function normaliseBook(row) {
  const publicUrl = (bucket, path) => {
    if (!state.client || !path) return ''
    return state.client.storage.from(bucket).getPublicUrl(path).data.publicUrl || ''
  }
  return {
    id: row.id,
    title: row.title || 'Copione senza titolo',
    subtitle: row.subtitle || '',
    description: row.description || '',
    authorName: row.author_name || 'Autore non indicato',
    language: row.language || 'Italiano',
    genre: row.genre || 'Teatro',
    rightsLabel: row.rights_label || 'Diritti non indicati',
    actorCount: asNumber(row.actor_count),
    actCount: asNumber(row.act_count),
    sceneCount: asNumber(row.scene_count),
    estimatedMinutes: asNumber(row.estimated_minutes),
    tags: Array.isArray(row.tags) ? row.tags : [],
    downloadCount: asNumber(row.download_count),
    averageRating: asNumber(row.average_rating),
    ratingCount: asNumber(row.rating_count),
    packageUrl: publicUrl('store-packages', row.package_path),
    coverUrl: publicUrl('store-covers', row.cover_path),
    createdAt: row.created_at || '',
    isDemo: false,
  }
}

function coverMarkup(book, className = 'store-book-cover') {
  if (book.coverUrl) return `<div class="${className}"><img src="${escapeHtml(book.coverUrl)}" alt="Copertina di ${escapeHtml(book.title)}" loading="lazy" /></div>`
  return `<div class="${className}"><div class="store-book-cover-fallback"><strong>${escapeHtml(book.title)}</strong><small>${escapeHtml(book.authorName)}</small></div></div>`
}

function bookCard(book) {
  const importButton = state.canImport && book.packageUrl
    ? `<button type="button" class="store-button store-button-quiet store-card-import" data-import-card="${escapeHtml(book.id)}">Importa</button>`
    : ''
  return `<article class="store-book-card">
    <button type="button" class="store-book-cover-button" data-detail="${escapeHtml(book.id)}" aria-label="Apri ${escapeHtml(book.title)}">${coverMarkup(book)}</button>
    <div class="store-book-meta">
      <h4>${escapeHtml(book.title)}</h4>
      <p class="store-book-author">${escapeHtml(book.authorName)}</p>
      <div class="store-book-facts">
        <span>${book.actorCount || '—'} attori</span>
        <span>${book.estimatedMinutes || '—'} min</span>
      </div>
      ${importButton ? `<div class="store-card-actions">${importButton}</div>` : ''}
    </div>
  </article>`
}

function carouselShelf(key, title, items, note) {
  return `<section class="store-shelf store-carousel-shelf">
    <div class="store-shelf-heading"><div><h3>${title}</h3><span>${note}</span></div><div class="store-carousel-controls"><button type="button" class="store-carousel-button" data-carousel-prev="${key}" aria-label="${title} precedenti">‹</button><button type="button" class="store-carousel-button" data-carousel-next="${key}" aria-label="${title} successivi">›</button></div></div>
    <div class="store-carousel-viewport"><div class="store-carousel-track" data-carousel-track="${key}">${items.map(bookCard).join('')}</div></div>
  </section>`
}

function renderSections() {
  const target = $('#catalog-sections')
  if (!target) return
  const books = state.filtered
  if (!books.length) {
    target.innerHTML = '<p class="store-empty">Nessun copione corrisponde ai filtri selezionati.</p>'
    return
  }
  const newest = [...books].sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
  const downloaded = [...books].sort((a, b) => b.downloadCount - a.downloadCount)
  const rated = [...books].sort((a, b) => b.averageRating - a.averageRating)
  const shelf = (title, items, note) => `<section class="store-shelf"><div class="store-shelf-heading"><h3>${title}</h3><span>${note}</span></div><div class="store-book-grid">${items.slice(0, 4).map(bookCard).join('')}</div></section>`
  target.innerHTML = [
    carouselShelf('featured', 'In evidenza', books, 'Una selezione per iniziare'),
    books.length > 1 ? carouselShelf('downloads', 'Più richiesti', downloaded, 'I testi più scelti') : '',
    books.length > 1 ? carouselShelf('newest', 'Nuovi arrivi', newest, 'Appena pubblicati') : '',
    books.length > 1 ? carouselShelf('rated', 'Più votati', rated, 'Le valutazioni della community') : '',
  ].join('')
}

function updateFilters() {
  const genre = $('#filter-genre').value
  const language = $('#filter-language').value
  const actors = $('#filter-actors').value
  const query = ($('#catalog-search').value || '').trim().toLocaleLowerCase('it-IT')
  const sort = $('#filter-sort').value
  state.filtered = state.books.filter((book) => {
    const matchesQuery = !query || [book.title, book.authorName, book.description, book.genre, ...book.tags].join(' ').toLocaleLowerCase('it-IT').includes(query)
    const matchesGenre = !genre || book.genre === genre
    const matchesLanguage = !language || book.language === language
    const count = book.actorCount
    const matchesActors = !actors || (actors === '1-3' && count >= 1 && count <= 3) || (actors === '4-8' && count >= 4 && count <= 8) || (actors === '9-15' && count >= 9 && count <= 15) || (actors === '16+' && count >= 16)
    return matchesQuery && matchesGenre && matchesLanguage && matchesActors
  })
  state.filtered.sort((a, b) => sort === 'downloads' ? b.downloadCount - a.downloadCount : sort === 'rating' ? b.averageRating - a.averageRating : sort === 'newest' ? String(b.createdAt).localeCompare(String(a.createdAt)) : 0)
  $('#catalog-status').textContent = `${state.filtered.length} ${state.filtered.length === 1 ? 'copione disponibile' : 'copioni disponibili'}`
  renderSections()
}

function populateFilterOptions() {
  const unique = (key) => [...new Set(state.books.map((book) => book[key]).filter(Boolean))].sort()
  $('#filter-genre').innerHTML = '<option value="">Tutti</option>' + unique('genre').map((value) => `<option>${escapeHtml(value)}</option>`).join('')
  $('#filter-language').innerHTML = '<option value="">Tutte</option>' + unique('language').map((value) => `<option>${escapeHtml(value)}</option>`).join('')
}

function setFormStatus(selector, message, isError = false) {
  const element = $(selector)
  if (!element) return
  element.textContent = message
  element.style.color = isError ? '#ff8e72' : ''
}

function showUpload() {
  if (!state.session) return
  const metadata = state.session.user.user_metadata || {}
  const authorField = $('#upload-form [name="author_name"]')
  if (authorField && !authorField.value) authorField.value = metadata.full_name || metadata.name || metadata.display_name || state.session.user.email?.split('@')[0] || ''
  $('#upload-dialog')?.showModal()
}

function updateAccountUi() {
  const publish = $('#publish-action')
  if (publish) publish.hidden = !state.session
}

async function loadCatalog() {
  if (!state.client) {
    state.books = [demoBook]
    state.configError = 'Configurazione Store non disponibile: mostra il catalogo locale di esempio.'
  } else {
    const { data, error } = await state.client.from('store_scripts').select('*').eq('is_published', true).order('created_at', { ascending: false }).limit(100)
    if (error) {
      state.books = [demoBook]
      state.configError = `Catalogo non disponibile: ${error.message}`
    } else {
      state.books = (data || []).map(normaliseBook)
      if (!state.books.length) state.books = [demoBook]
      state.configError = ''
    }
  }
  populateFilterOptions()
  updateFilters()
  if (state.configError) $('#catalog-status').textContent = state.configError
}

function sendImport(book) {
  if (!state.canImport || !book.packageUrl) return
  window.parent.postMessage({
    type: IMPORT_MESSAGE,
    url: book.packageUrl,
    title: book.title,
    scriptId: book.isDemo ? undefined : book.id,
  }, '*')
}

function detailMarkup(book) {
  return `<button class="store-dialog-close" data-close-detail aria-label="Chiudi">×</button>
    <div class="store-detail-layout">
      <div>${coverMarkup(book, 'store-detail-cover')}</div>
      <div class="store-detail-copy">
        <p class="store-eyebrow">${escapeHtml(book.genre)} · ${escapeHtml(book.rightsLabel)}</p>
        <h2>${escapeHtml(book.title)}</h2>
        <p class="store-detail-subtitle">${escapeHtml(book.subtitle)}</p>
        <p class="store-book-author">di ${escapeHtml(book.authorName)}</p>
        <p class="store-detail-description">${escapeHtml(book.description)}</p>
        <div class="store-detail-facts"><span>${book.actorCount || '—'} attori</span><span>${book.actCount || '—'} atti</span><span>${book.sceneCount || '—'} scene</span><span>${book.estimatedMinutes || '—'} min</span><span>${escapeHtml(book.language)}</span></div>
        <div class="store-detail-actions">
          <button class="store-button store-button-accent" type="button" data-import-book="${escapeHtml(book.id)}" ${state.canImport ? '' : 'hidden'}>Importa</button>
        </div>
      </div>
    </div>`
}

function showDetail(book) {
  state.selectedBook = book
  $('#detail-content').innerHTML = detailMarkup(book)
  $('#detail-dialog')?.showModal()
}

async function submitUpload(event) {
  event.preventDefault()
  if (!state.client || !state.session) return setFormStatus('#upload-status', 'Autenticazione richiesta.', true)
  const form = event.currentTarget
  const data = new FormData(form)
  const packageFile = data.get('package')
  const coverFile = data.get('cover')
  if (!(packageFile instanceof File) || !packageFile.name.toLowerCase().endsWith('.stagedesk')) return setFormStatus('#upload-status', 'Seleziona un pacchetto .stagedesk valido.', true)
  setFormStatus('#upload-status', 'Caricamento del copione…')
  const id = crypto.randomUUID()
  const packagePath = `${state.session.user.id}/${id}.stagedesk`
  const packageUpload = await state.client.storage.from('store-packages').upload(packagePath, packageFile, { contentType: 'application/vnd.stagedesk.script', upsert: false })
  if (packageUpload.error) return setFormStatus('#upload-status', packageUpload.error.message, true)
  let coverPath = null
  if (coverFile instanceof File && coverFile.size) {
    const extension = coverFile.name.split('.').pop()?.toLowerCase() || 'jpg'
    coverPath = `${state.session.user.id}/${id}.${extension}`
    const coverUpload = await state.client.storage.from('store-covers').upload(coverPath, coverFile, { contentType: coverFile.type || 'image/jpeg', upsert: false })
    if (coverUpload.error) {
      await state.client.storage.from('store-packages').remove([packagePath])
      return setFormStatus('#upload-status', coverUpload.error.message, true)
    }
  }
  const row = {
    author_id: state.session.user.id,
    title: data.get('title'),
    subtitle: data.get('subtitle') || '',
    description: data.get('description'),
    author_name: data.get('author_name'),
    genre: data.get('genre') || 'Teatro',
    language: data.get('language') || 'Italiano',
    actor_count: asNumber(data.get('actor_count')),
    act_count: asNumber(data.get('act_count')),
    scene_count: asNumber(data.get('scene_count')),
    estimated_minutes: asNumber(data.get('estimated_minutes')),
    rights_label: data.get('rights_label') || 'Testo originale',
    tags: String(data.get('tags') || '').split(',').map((tag) => tag.trim()).filter(Boolean),
    package_path: packagePath,
    package_name: packageFile.name,
    cover_path: coverPath,
    is_published: true,
  }
  const inserted = await state.client.from('store_scripts').insert(row).select().single()
  if (inserted.error) {
    await state.client.storage.from('store-packages').remove([packagePath])
    if (coverPath) await state.client.storage.from('store-covers').remove([coverPath])
    return setFormStatus('#upload-status', inserted.error.message, true)
  }
  $('#upload-dialog')?.close()
  form.reset()
  await loadCatalog()
}

async function initSupabase() {
  try {
    const configResponse = await fetch(CONFIG_URL, { cache: 'no-store' })
    const config = await configResponse.json()
    if (!config.url || !config.publishableKey) return
    state.client = createClient(config.url, config.publishableKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' } })
    state.session = (await state.client.auth.getSession()).data.session
    state.client.auth.onAuthStateChange((_event, session) => { state.session = session; updateAccountUi() })
  } catch {
    state.client = null
  }
}

window.addEventListener('message', (event) => {
  if (event.source !== window.parent || event.data?.type !== CONTEXT_MESSAGE) return
  state.canImport = event.data.canImport === true
  updateAccountUi()
  renderSections()
  if (state.selectedBook && $('#detail-dialog')?.open) {
    $('#detail-content').innerHTML = detailMarkup(state.selectedBook)
  }
})

$('#publish-action')?.addEventListener('click', showUpload)
$('#upload-form').addEventListener('submit', submitUpload)
$('#catalog-search').addEventListener('input', updateFilters)
document.querySelectorAll('.store-filters select').forEach((select) => select.addEventListener('change', updateFilters))
$('#catalog-sections').addEventListener('click', (event) => {
  const carouselButton = event.target.closest('[data-carousel-prev], [data-carousel-next]')
  if (carouselButton) {
    const key = carouselButton.dataset.carouselNext || carouselButton.dataset.carouselPrev
    const track = document.querySelector(`[data-carousel-track="${CSS.escape(key)}"]`)
    if (track) track.scrollBy({ left: (carouselButton.hasAttribute('data-carousel-next') ? 1 : -1) * track.clientWidth * 0.86, behavior: 'smooth' })
    return
  }
  const importer = event.target.closest('[data-import-card]')
  if (importer) {
    const book = state.books.find((item) => item.id === importer.dataset.importCard)
    if (book) sendImport(book)
    return
  }
  const detailButton = event.target.closest('[data-detail]')
  if (detailButton) {
    const book = state.books.find((item) => item.id === detailButton.dataset.detail)
    if (book) showDetail(book)
  }
})
$('#detail-content').addEventListener('click', async (event) => {
  if (event.target.closest('[data-close-detail]')) return $('#detail-dialog')?.close()
  const importer = event.target.closest('[data-import-book]')
  if (importer) {
    const book = state.books.find((item) => item.id === importer.dataset.importBook)
    if (book) sendImport(book)
  }
})

await initSupabase()
updateAccountUi()
await loadCatalog()
window.parent.postMessage({ type: 'stagedesk-store-ready' }, '*')
