import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const IMPORT_MESSAGE = 'stagedesk-store-import'
const CONTEXT_MESSAGE = 'stagedesk-store-context'
const CONFIG_URL = '/store-config'
const COVER_ASSET_VERSION = '20260731-catalog-metadata-01'
// The Store is embedded only by StageDesk Pro; direct browser visits keep import disabled.
const embeddedInStageDesk = window.parent !== window
const state = {
  client: null,
  books: [],
  filtered: [],
  canImport: embeddedInStageDesk,
  selectedBook: null,
  pendingImport: null,
  configError: '',
}

const $ = (selector) => document.querySelector(selector)
const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char])
const asNumber = (value) => Number.isFinite(Number(value)) ? Number(value) : 0
const rightsLabels = {
  unknown: 'Da verificare',
  original: 'Opera originale',
  'public-domain': 'Pubblico dominio',
  'creative-commons': 'Creative Commons',
  siae: 'SIAE / diritti gestiti',
  licensed: 'Licenza specifica',
}
const demoBook = {
  id: 'demo-il-malato-immaginario',
  title: 'Il malato immaginario',
  subtitle: 'Edizione integrale con note di regia originali',
  description: 'La commedia integrale in tre atti e sedici scene, con il testo della fonte storica, le didascalie e note originali per la preparazione della prova.',
  authorName: 'Molière · traduzione storica Niccolò di Castelli',
  language: 'Italiano',
  genre: 'Commedia',
  rightsLabel: 'Edizione storica in pubblico dominio; fonte digitale UB Paderborn',
  rightsCode: 'public-domain',
  rightsHolder: 'Fonte storica UB Paderborn',
  setting: 'Casa borghese e ambienti domestici',
  castBreakdown: '6 donne, 5 uomini',
  ageBreakdown: 'Adulti',
  actorCount: 11,
  actCount: 3,
  sceneCount: 16,
  estimatedMinutes: 90,
  tags: ['Formato StageDesk', 'Note di regia'],
  downloadCount: 0,
  averageRating: 0,
  ratingCount: 0,
  versionNumber: 1,
  publishedAt: '',
  packageUrl: 'https://insoqzhjmrbrgfrsmlnj.supabase.co/storage/v1/object/public/store-packages/official/il-malato-immaginario-riscrittura.stagedesk',
  coverUrl: '',
  isDemo: true,
}

function normaliseBook(row) {
  const publicUrl = (bucket, path) => {
    if (!state.client || !path) return ''
    const url = state.client.storage.from(bucket).getPublicUrl(path).data.publicUrl || ''
    if (!url || bucket !== 'store-covers') return url
    const separator = url.includes('?') ? '&' : '?'
    return `${url}${separator}v=${COVER_ASSET_VERSION}`
  }
  return {
    id: row.id,
    title: row.title || 'Copione senza titolo',
    subtitle: row.subtitle || '',
    description: row.description || '',
    authorName: row.author_name || 'Autore non indicato',
    language: row.language || 'Italiano',
    genre: row.genre || 'Non classificato',
    rightsLabel: row.rights_label || rightsLabels[row.rights_code] || 'Diritti non indicati',
    rightsCode: row.rights_code || 'unknown',
    rightsHolder: row.rights_holder || '',
    licenseUrl: row.license_url || '',
    setting: row.setting || '',
    castBreakdown: row.cast_breakdown?.summary || '',
    ageBreakdown: row.age_breakdown?.summary || '',
    actorCount: asNumber(row.actor_count),
    actCount: asNumber(row.act_count),
    sceneCount: asNumber(row.scene_count),
    estimatedMinutes: asNumber(row.estimated_minutes),
    tags: Array.isArray(row.tags) ? row.tags : [],
    downloadCount: asNumber(row.download_count),
    averageRating: asNumber(row.average_rating),
    ratingCount: asNumber(row.rating_count),
    versionNumber: Math.max(0, asNumber(row.current_version)),
    publishedAt: row.published_at || row.updated_at || '',
    packageUrl: publicUrl('store-packages', row.package_path),
    coverUrl: publicUrl('store-covers', row.cover_path),
    createdAt: row.created_at || '',
    isDemo: false,
  }
}

function publicationLabel(book) {
  if (!book.versionNumber && !book.publishedAt) return ''
  const timestamp = book.publishedAt ? Date.parse(book.publishedAt) : NaN
  const date = Number.isNaN(timestamp)
    ? ''
    : new Intl.DateTimeFormat('it-IT', { dateStyle: 'medium' }).format(new Date(timestamp))
  return `Versione ${book.versionNumber || 1}${date ? ` · pubblicata il ${date}` : ''}`
}

function ratingMarkup(book, className = '') {
  const ratingCount = asNumber(book.ratingCount)
  const rating = asNumber(book.averageRating)
  const label = ratingCount
    ? `${rating.toLocaleString('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}/5 · ${ratingCount} ${ratingCount === 1 ? 'voto' : 'voti'}`
    : 'Nessun voto'
  const filledStars = Math.max(0, Math.min(5, Math.round(rating)))
  const stars = Array.from({ length: 5 }, (_, index) => `<span class="store-rating-star${index < filledStars ? ' is-filled' : ''}" aria-hidden="true">★</span>`).join('')
  return `<span class="store-book-rating ${className}" aria-label="${escapeHtml(label)}"><span class="store-rating-stars">${stars}</span><span class="store-rating-label">${escapeHtml(label)}</span></span>`
}

function coverMarkup(book, className = 'store-book-cover', withOverlay = false) {
  const overlay = withOverlay ? `<div class="store-book-cover-overlay">
    <strong>${escapeHtml(book.title)}</strong>
    <span class="store-book-cover-subtitle">${escapeHtml(book.subtitle)}</span>
    <small>${escapeHtml(book.authorName)}</small>
    <span class="store-book-cover-facts">${book.actorCount || '—'} attori · ${book.actCount || '—'} atti · ${book.sceneCount || '—'} scene</span>
    ${ratingMarkup(book, 'store-book-rating-on-cover')}
  </div>` : ''
  if (book.coverUrl) return `<div class="${className}"><img src="${escapeHtml(book.coverUrl)}" alt="Copertina di ${escapeHtml(book.title)}" loading="lazy" decoding="async" />${overlay}</div>`
  return `<div class="${className}"><div class="store-book-cover-fallback"></div>${overlay}</div>`
}

function bookCard(book) {
  return `<article class="store-book-card">
    <div class="store-book-cover-button" data-detail="${escapeHtml(book.id)}" role="button" tabindex="0" aria-label="Apri ${escapeHtml(book.title)}">${coverMarkup(book, 'store-book-cover', true)}</div>
  </article>`
}

function normalizeCoverImages(root) {
  root.querySelectorAll('.store-book-cover:not(.store-detail-cover) img').forEach((image) => {
    const applyFit = () => {
      const aspectRatio = image.naturalWidth / image.naturalHeight
      image.classList.toggle('store-book-cover-image--wide', Number.isFinite(aspectRatio) && aspectRatio >= (2 / 3))
    }
    if (image.complete) applyFit()
    else image.addEventListener('load', applyFit, { once: true })
  })
}

function initializeCarousels(root) {
  requestAnimationFrame(() => {
    root.querySelectorAll('[data-carousel-track]').forEach((track) => {
      const itemCount = Number(track.dataset.carouselCount)
      if (itemCount < 2) return
      const styles = getComputedStyle(track)
      const gap = parseFloat(styles.columnGap || styles.gap) || 0
      const loopWidth = (track.scrollWidth + gap) / 3
      if (!Number.isFinite(loopWidth) || loopWidth <= 0) return
      track.dataset.loopWidth = String(loopWidth)
      track.scrollLeft = loopWidth
      track.addEventListener('scroll', () => {
        const width = Number(track.dataset.loopWidth)
        if (!width || track.dataset.normalizing === 'true') return
        if (track.scrollLeft < width * 0.2) {
          track.dataset.normalizing = 'true'
          track.scrollLeft += width
          requestAnimationFrame(() => { delete track.dataset.normalizing })
        } else if (track.scrollLeft > width * 1.8) {
          track.dataset.normalizing = 'true'
          track.scrollLeft -= width
          requestAnimationFrame(() => { delete track.dataset.normalizing })
        }
      }, { passive: true })
    })
  })
}

function carouselShelf(key, title, items, note) {
  const cards = items.map(bookCard).join('')
  const loopedCards = items.length > 1 ? `${cards}${cards}${cards}` : cards
  return `<section class="store-shelf store-carousel-shelf">
    <div class="store-shelf-heading"><div><h3>${title}</h3><span>${note}</span></div><div class="store-carousel-controls"><button type="button" class="store-carousel-button" data-carousel-prev="${key}" aria-label="${title} precedenti"><span aria-hidden="true">‹</span></button><button type="button" class="store-carousel-button" data-carousel-next="${key}" aria-label="${title} successivi"><span aria-hidden="true">›</span></button></div></div>
    <div class="store-carousel-viewport"><div class="store-carousel-track" data-carousel-track="${key}" data-carousel-count="${items.length}">${loopedCards}</div></div>
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
  normalizeCoverImages(target)
  initializeCarousels(target)
}

function updateFilters() {
  const genre = $('#filter-genre').value
  const language = $('#filter-language').value
  const actors = $('#filter-actors').value
  const query = ($('#catalog-search').value || '').trim().toLocaleLowerCase('it-IT')
  const rights = $('#filter-rights').value
  const sort = $('#filter-sort').value
  state.filtered = state.books.filter((book) => {
    const matchesQuery = !query || [book.title, book.authorName, book.description, book.genre, book.setting, book.castBreakdown, book.ageBreakdown, ...book.tags].join(' ').toLocaleLowerCase('it-IT').includes(query)
    const matchesGenre = !genre || book.genre === genre
    const matchesLanguage = !language || book.language === language
    const matchesRights = !rights || book.rightsCode === rights
    const cast = $('#filter-cast').value
    const age = $('#filter-age').value
    const matchesCast = !cast || book.castBreakdown === cast
    const matchesAge = !age || book.ageBreakdown === age
    const count = book.actorCount
    const matchesActors = !actors || (actors === '1-3' && count >= 1 && count <= 3) || (actors === '4-8' && count >= 4 && count <= 8) || (actors === '9-15' && count >= 9 && count <= 15) || (actors === '16+' && count >= 16)
    return matchesQuery && matchesGenre && matchesLanguage && matchesActors && matchesCast && matchesAge && matchesRights
  })
  state.filtered.sort((a, b) => sort === 'downloads' ? b.downloadCount - a.downloadCount : sort === 'rating' ? b.averageRating - a.averageRating : sort === 'newest' ? String(b.createdAt).localeCompare(String(a.createdAt)) : 0)
  $('#catalog-status').textContent = `${state.filtered.length} ${state.filtered.length === 1 ? 'copione disponibile' : 'copioni disponibili'}`
  renderSections()
}

function populateFilterOptions() {
  const unique = (key) => [...new Set(state.books.map((book) => book[key]).filter(Boolean))].sort()
  $('#filter-genre').innerHTML = '<option value="">Tutti</option>' + unique('genre').map((value) => `<option>${escapeHtml(value)}</option>`).join('')
  $('#filter-language').innerHTML = '<option value="">Tutte</option>' + unique('language').map((value) => `<option>${escapeHtml(value)}</option>`).join('')
  $('#filter-cast').innerHTML = '<option value="">Qualsiasi composizione</option>' + unique('castBreakdown').map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('')
  $('#filter-age').innerHTML = '<option value="">Qualsiasi età</option>' + unique('ageBreakdown').map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('')
  $('#filter-rights').innerHTML = '<option value="">Tutti</option>' + unique('rightsCode').map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(rightsLabels[value] || value)}</option>`).join('')
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

function showImportConsent(book) {
  if (!state.canImport || !book.packageUrl) return
  state.pendingImport = book
  const intro = $('#import-consent-intro')
  const license = $('#import-consent-license')
  const checkbox = $('#import-consent-accepted')
  const status = $('#import-consent-status')
  if (intro) intro.innerHTML = `Stai per importare <strong>${escapeHtml(book.title)}</strong> nel tuo progetto StageDesk Pro.`
  if (license) license.textContent = book.rightsLabel || 'Non indicata nella scheda'
  if (checkbox) checkbox.checked = false
  if (status) status.textContent = ''
  $('#import-consent-dialog')?.showModal()
  requestAnimationFrame(() => checkbox?.focus())
}

function detailMarkup(book) {
  const importButton = state.canImport && book.packageUrl
    ? `<div class="store-detail-import-stack">
        <button class="store-button store-button-accent store-detail-import" type="button" data-import-book="${escapeHtml(book.id)}"><span class="store-import-icon" aria-hidden="true">↓</span><span>Importa</span></button>
      </div>`
    : ''
  const metadata = [
    book.setting ? `<span><strong>Ambientazione</strong>${escapeHtml(book.setting)}</span>` : '',
    book.castBreakdown ? `<span><strong>Cast</strong>${escapeHtml(book.castBreakdown)}</span>` : '',
    book.ageBreakdown ? `<span><strong>Età</strong>${escapeHtml(book.ageBreakdown)}</span>` : '',
    book.rightsHolder ? `<span><strong>Titolare o fonte</strong>${escapeHtml(book.rightsHolder)}</span>` : '',
  ].filter(Boolean).join('')
  return `<button class="store-dialog-close" data-close-detail aria-label="Chiudi">×</button>
    <div class="store-detail-layout">
      <div class="store-detail-cover-column">
        <div class="store-detail-cover-figure">
          ${coverMarkup(book, 'store-detail-cover')}
          ${importButton}
        </div>
        ${ratingMarkup(book, 'store-detail-rating')}
      </div>
      <div class="store-detail-copy">
        <p class="store-eyebrow">${escapeHtml(book.genre)} · ${escapeHtml(book.rightsLabel)}</p>
        <h2>${escapeHtml(book.title)}</h2>
        <p class="store-detail-subtitle">${escapeHtml(book.subtitle)}</p>
        <p class="store-book-author">di ${escapeHtml(book.authorName)}</p>
        <p class="store-detail-description">${escapeHtml(book.description)}</p>
        <div class="store-detail-facts"><span>${book.actorCount || '—'} attori</span><span>${book.actCount || '—'} atti</span><span>${book.sceneCount || '—'} scene</span><span>${book.estimatedMinutes || '—'} min</span><span>${escapeHtml(book.language)}</span></div>
        ${metadata ? `<div class="store-detail-metadata">${metadata}</div>` : ''}
        <p class="store-detail-publication">${escapeHtml(publicationLabel(book))}</p>
      </div>
    </div>`
}

function showDetail(book) {
  state.selectedBook = book
  $('#detail-content').innerHTML = detailMarkup(book)
  const dialog = $('#detail-dialog')
  dialog?.showModal()
  requestAnimationFrame(() => {
    const focusTarget = dialog?.querySelector('[data-import-book]') || dialog?.querySelector('[data-close-detail]')
    focusTarget?.focus()
  })
}

async function initSupabase() {
  try {
    const configResponse = await fetch(CONFIG_URL, { cache: 'no-store' })
    const config = await configResponse.json()
    if (!config.url || !config.publishableKey) return
    state.client = createClient(config.url, config.publishableKey)
  } catch {
    state.client = null
  }
}

window.addEventListener('message', (event) => {
  if (event.source !== window.parent || event.data?.type !== CONTEXT_MESSAGE) return
  state.canImport = event.data.canImport === true
  renderSections()
  if (state.selectedBook && $('#detail-dialog')?.open) {
    $('#detail-content').innerHTML = detailMarkup(state.selectedBook)
  }
})

$('#catalog-search').addEventListener('input', updateFilters)
$('#catalog-search-form').addEventListener('submit', (event) => {
  event.preventDefault()
  updateFilters()
})
document.querySelectorAll('.store-filters select').forEach((select) => select.addEventListener('change', updateFilters))
$('#catalog-sections').addEventListener('click', (event) => {
  const carouselButton = event.target.closest('[data-carousel-prev], [data-carousel-next]')
  if (carouselButton) {
    const key = carouselButton.dataset.carouselNext || carouselButton.dataset.carouselPrev
    const track = document.querySelector(`[data-carousel-track="${CSS.escape(key)}"]`)
    if (track) {
      const direction = carouselButton.hasAttribute('data-carousel-next') ? 1 : -1
      const distance = Math.max(1, Math.round(track.clientWidth * 0.86))
      const loopWidth = Number(track.dataset.loopWidth)
      let target = track.scrollLeft + direction * distance
      if (loopWidth) {
        if (target < loopWidth * 0.05) target += loopWidth
        if (target > loopWidth * 1.95) target -= loopWidth
      } else {
        const maxScroll = track.scrollWidth - track.clientWidth
        target = Math.max(0, Math.min(maxScroll, target))
      }
      track.scrollTo({ left: target, behavior: 'smooth' })
    }
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
    if (book) showImportConsent(book)
  }
})

$('#import-consent-form').addEventListener('submit', (event) => {
  event.preventDefault()
  const checkbox = $('#import-consent-accepted')
  const status = $('#import-consent-status')
  if (!checkbox?.checked) {
    if (status) status.textContent = 'Per importare devi confermare di aver letto e accettato le condizioni.'
    checkbox?.focus()
    return
  }
  const book = state.pendingImport
  state.pendingImport = null
  $('#import-consent-dialog')?.close()
  if (book) sendImport(book)
})

document.querySelectorAll('[data-close-import-consent]').forEach((button) => {
  button.addEventListener('click', () => {
    state.pendingImport = null
    $('#import-consent-dialog')?.close()
  })
})

await initSupabase()
await loadCatalog()
window.parent.postMessage({ type: 'stagedesk-store-ready' }, '*')
