import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.110.1'

const root = document.querySelector('#share-app')
const shareUid = decodeURIComponent(window.location.pathname.split('/').filter(Boolean).pop() || '')
const statusLabels = {
  da_studiare: 'Da studiare',
  in_studio: 'In studio',
  studiata: 'Studiata',
}

let supabase
let session
let share
let selectedCharacters = new Set()
let selectionInitialized = false
let filterMode = 'hide-selected'
let revealedDialogueIds = new Set()
let characterMenuOpen = false
let authMode = 'signin'
const SHARE_ACCESS_TTL_MS = 48 * 60 * 60 * 1000

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;')

const iconSvg = (name) => {
  const paths = {
    google: '<path d="m10.88 21.94 4.58-7.94"/><path d="M21.17 8H12"/><path d="M3.95 6.06 8.54 14"/><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/>',
    github: '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>',
    azure: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
    login: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.8-4L3 10"/><path d="M3 4v6h6"/><path d="M4 13a8 8 0 0 0 14.8 4L21 14"/><path d="M21 20v-6h-6"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/>',
    previous: '<path d="m14 6-6 6 6 6"/>',
    next: '<path d="m10 6 6 6-6 6"/>',
    eye: '<path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/>',
    'eye-off': '<path d="m3 3 18 18"/><path d="M10.6 5.2A10.8 10.8 0 0 1 12 5c6 0 9.5 7 9.5 7a17 17 0 0 1-3.1 3.8M6.2 6.3C3.7 8.1 2.5 12 2.5 12s3.5 7 9.5 7c1 0 1.9-.2 2.7-.5"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    'select-all': '<rect x="4" y="4" width="12" height="12" rx="1.5"/><path d="m8 10 2.2 2.2L15 7.5"/><path d="M8 20h8a2 2 0 0 0 2-2v-8"/>',
    study: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5Z"/><path d="M4 5.5v15M8 7h8m-8 4h8"/>',
    progress: '<path d="m14 6 4 4"/><path d="M4 20h4l10-10a2.8 2.8 0 0 0-4-4L4 16v4Z"/><path d="M13 7 17 11"/>',
    done: '<circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/>',
  }
  return `<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name] || ''}</svg>`
}

const getPinStorageKey = () => `stagedesk-share-progress:${shareUid}`
const getSelectionStorageKey = () => `stagedesk-share-selection:${shareUid}`
const getAccessStorageKey = () => `stagedesk-share-access:v2:${shareUid}`
const getLegacyAccessStorageKey = () => `stagedesk-share-access:${shareUid}`
const shareAuthRedirectUrl = () => `${window.location.origin}/share/${encodeURIComponent(shareUid)}`
const formatScriptTitle = (name) => String(name || 'Copione').trim().replace(/\.md$/i, '').trim().toUpperCase()
const formatPublishedAt = (value) => {
  const date = new Date(value || '')
  if (Number.isNaN(date.getTime())) return 'Versione caricata'
  return `Versione caricata il ${new Intl.DateTimeFormat('it-IT', { dateStyle: 'medium', timeStyle: 'short' }).format(date)}`
}
const readCachedAccess = () => {
  try {
    const currentKey = getAccessStorageKey()
    const legacyKey = getLegacyAccessStorageKey()
    const cachedValue = localStorage.getItem(currentKey) || localStorage.getItem(legacyKey)
    const cached = JSON.parse(cachedValue || 'null')
    const userMismatch = cached?.userId && session?.user?.id && cached.userId !== session.user.id
    if (!cached?.share || userMismatch || !Number.isFinite(cached.expiresAt) || cached.expiresAt <= Date.now()) {
      localStorage.removeItem(currentKey)
      localStorage.removeItem(legacyKey)
      return null
    }
    if (!localStorage.getItem(currentKey)) localStorage.setItem(currentKey, JSON.stringify(cached))
    return { ...cached, hasPin: typeof cached.pin === 'string' && cached.pin.length === 5 }
  } catch {
    localStorage.removeItem(getAccessStorageKey())
    localStorage.removeItem(getLegacyAccessStorageKey())
    return null
  }
}
const cacheShareAccess = (nextShare, pin) => {
  localStorage.setItem(getAccessStorageKey(), JSON.stringify({ userId: session?.user?.id, pin, share: nextShare, expiresAt: Date.now() + SHARE_ACCESS_TTL_MS }))
}
const persistSelectedCharacters = () => {
  localStorage.setItem(getSelectionStorageKey(), JSON.stringify([...selectedCharacters]))
}
const clearSelectedCharacters = () => {
  localStorage.removeItem(getSelectionStorageKey())
  selectedCharacters = new Set()
}
const clearCachedShareAccess = () => {
  localStorage.removeItem(getAccessStorageKey())
  localStorage.removeItem(getLegacyAccessStorageKey())
}

const setMessage = (message, tone = '') => {
  const element = root?.querySelector('[data-message]')
  if (!element) return
  element.textContent = message
  element.dataset.tone = tone
}

const renderShell = (content) => {
  if (root) root.innerHTML = content
}

const renderBrand = (title, subtitle = '', action = '') => `
  <header class="share-header">
    <a class="share-brand" href="/" aria-label="StageDesk Pro">
      <span class="share-brand-mark">SD</span>
      <span>StageDesk <b>Share</b></span>
    </a>
    <div class="share-header-side">${action || `<span class="share-uid">${escapeHtml(shareUid)}</span>`}</div>
  </header>
  <div class="share-heading">
    <span class="share-kicker">StageDesk Pro</span>
    <h1>${escapeHtml(title)}</h1>
    ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ''}
  </div>
`

const renderAuth = (message = '') => {
  renderShell(`
    ${renderBrand('Accedi al copione', 'Autenticati per inserire il PIN condiviso dal regista.')}
    <section class="share-card auth-card">
      <div class="auth-switch" role="tablist" aria-label="Accesso account">
        <button type="button" data-auth-mode="signin" class="${authMode === 'signin' ? 'active' : ''}">Accedi</button>
        <button type="button" data-auth-mode="signup" class="${authMode === 'signup' ? 'active' : ''}">Registrati</button>
      </div>
      <div class="provider-grid">
        <button type="button" data-provider="google">${iconSvg('google')}<span>Google</span></button>
        <button type="button" data-provider="github">${iconSvg('github')}<span>GitHub</span></button>
        <button type="button" data-provider="azure">${iconSvg('azure')}<span>Azure</span></button>
      </div>
      <div class="auth-divider"><span>oppure con e-mail</span></div>
      <form class="share-form" data-auth-form>
        <label>Email<input name="email" type="email" autocomplete="email" required /></label>
        <label>Password<input name="password" type="password" autocomplete="${authMode === 'signin' ? 'current-password' : 'new-password'}" minlength="8" required /></label>
        <button class="share-primary" type="submit">${iconSvg('login')}${authMode === 'signin' ? 'Accedi' : 'Crea account'}</button>
      </form>
      <p class="share-message" data-message data-tone="${message ? 'error' : ''}">${escapeHtml(message)}</p>
    </section>
  `)

  root.querySelectorAll('[data-auth-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      authMode = button.dataset.authMode
      renderAuth()
    })
  })
  root.querySelectorAll('[data-provider]').forEach((button) => {
    button.addEventListener('click', () => void signInWithProvider(button.dataset.provider))
  })
  root.querySelector('[data-auth-form]')?.addEventListener('submit', (event) => {
    event.preventDefault()
    void submitEmailAuth(event.currentTarget)
  })
}

const renderPinForm = (message = '') => {
  renderShell(`
    ${renderBrand('Inserisci il PIN', `Condivisione pronta: ${share?.projectName || 'copione'}.`) }
    <section class="share-card pin-card">
      <div class="pin-icon">•••••</div>
      <h2>PIN del regista</h2>
      <p>Inserisci il codice di 5 cifre ricevuto insieme al link o al QR code.</p>
      <form class="share-form" data-pin-form>
        <label>PIN
          <div class="pin-inputs" role="group" aria-label="PIN di 5 cifre">
            ${Array.from({ length: 5 }, (_, index) => `<input type="text" inputmode="numeric" pattern="[0-9]" maxlength="1" aria-label="Cifra ${index + 1} del PIN" data-pin-digit="${index}" ${index === 0 ? 'autocomplete="one-time-code"' : 'autocomplete="off"'} required />`).join('')}
          </div>
          <input type="hidden" name="pin" data-pin-value />
        </label>
        <button class="share-primary" type="submit">Apri copione</button>
      </form>
      <p class="share-message" data-message data-tone="${message ? 'error' : ''}">${escapeHtml(message)}</p>
      <p class="pin-validity">Dopo la verifica, l’accesso resta attivo per 48 ore su questo dispositivo.</p>
      <button class="share-link-button" type="button" data-signout>Cambia account</button>
    </section>
  `)
  const pinInputs = Array.from(root.querySelectorAll('[data-pin-digit]'))
  const pinValue = root.querySelector('[data-pin-value]')
  const syncPinValue = () => {
    if (pinValue) pinValue.value = pinInputs.map((input) => input.value).join('')
  }
  pinInputs.forEach((input, index) => {
    input.addEventListener('input', () => {
      input.value = input.value.replace(/\D/g, '').slice(-1)
      syncPinValue()
      if (input.value && pinInputs[index + 1]) pinInputs[index + 1].focus()
    })
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Backspace' && !input.value && pinInputs[index - 1]) {
        pinInputs[index - 1].focus()
        pinInputs[index - 1].select()
      } else if (event.key === 'ArrowLeft' && pinInputs[index - 1]) {
        event.preventDefault()
        pinInputs[index - 1].focus()
      } else if (event.key === 'ArrowRight' && pinInputs[index + 1]) {
        event.preventDefault()
        pinInputs[index + 1].focus()
      }
    })
    input.addEventListener('paste', (event) => {
      event.preventDefault()
      const pasted = (event.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 5)
      pasted.split('').forEach((digit, pastedIndex) => {
        if (pinInputs[pastedIndex]) pinInputs[pastedIndex].value = digit
      })
      syncPinValue()
      pinInputs[Math.min(pasted.length, pinInputs.length) - 1]?.focus()
    })
  })
  requestAnimationFrame(() => pinInputs[0]?.focus())
  root.querySelector('[data-pin-form]')?.addEventListener('submit', (event) => {
    event.preventDefault()
    void verifyPin(event.currentTarget)
  })
  root.querySelector('[data-signout]')?.addEventListener('click', () => void signOut())
}

const sameScene = (left, right) => (left && right && left === right) || (!left && !right)

const renderNote = (note, hidden = false, dialogueId = '') => `<aside class="dialogue-context note-${escapeHtml(note.type || 'general')} ${hidden ? 'is-context-hidden' : ''}" ${dialogueId ? `data-dialogue-id="${escapeHtml(dialogueId)}"` : ''}>
  <div class="dialogue-note-title"><span class="note-dot" aria-hidden="true"></span>${escapeHtml(note.title)}</div>
  <p>${escapeHtml(note.content)}</p>
</aside>`

const orderedScriptItems = (items, dialogues, noteDialogueIds) => {
  const dialogueIndexes = new Map(dialogues.map((dialogue, index) => [dialogue.id, index]))
  return items.map((item, index) => {
    if (item.kind === 'dialogue') {
      return {
        kind: 'dialogue',
        item,
        index,
        dialogueIndex: dialogueIndexes.get(item.id) ?? 0,
        sourceLine: Number(item.sourceLine ?? index + 1),
      }
    }
    return {
      kind: 'note',
      item,
      index,
      sourceLine: Number(item.sourceLine ?? index + 1),
      dialogueId: noteDialogueIds.get(item.id),
    }
  })
}

const noteDialogueIdsFromItems = (items) => {
  const owners = new Map()
  items.forEach((item, index) => {
    if (item.kind !== 'note') return
    for (let nextIndex = index + 1; nextIndex < items.length; nextIndex += 1) {
      const next = items[nextIndex]
      if (next.kind !== 'dialogue') continue
      if (sameScene(item.sceneId, next.sceneId)) {
        owners.set(item.id, next.id)
        break
      }
    }
  })
  return owners
}

const statusIcon = {
  da_studiare: 'study',
  in_studio: 'progress',
  studiata: 'done',
}

const updateRefreshStatus = (message, tone = '') => {
  const status = root?.querySelector('[data-refresh-status]')
  if (!status) return
  status.textContent = message
  status.dataset.tone = tone
}

async function refreshSharedScript(fromBootstrap = false) {
  const cached = readCachedAccess()
  if (!cached?.pin) {
    if (fromBootstrap) renderPinForm()
    else await signOut('La sessione di condivisione è scaduta. Inserisci nuovamente il PIN.')
    return
  }
  const refreshButton = root?.querySelector('[data-refresh-share]')
  if (refreshButton) {
    refreshButton.disabled = true
    refreshButton.classList.add('is-loading')
  }
  const previousPublishedAt = share?.publishedAt
  try {
    const { data, error } = await supabase.rpc('verify_script_share', { p_share_uid: shareUid, p_pin: cached.pin })
    if (error) {
      if (fromBootstrap) {
        renderPinForm('Impossibile verificare la versione condivisa. Inserisci nuovamente il PIN.')
      } else {
        updateRefreshStatus('Aggiornamento non disponibile.', 'error')
      }
      return
    }
    if (!data?.ok) {
      await signOut('La condivisione non è più disponibile o il PIN è stato modificato.')
      return
    }
    share = data.share
    cacheShareAccess(share, cached.pin)
    renderShare(previousPublishedAt && previousPublishedAt !== share.publishedAt ? 'Copione aggiornato' : '')
  } catch {
    if (fromBootstrap) renderPinForm('Impossibile aggiornare la versione condivisa. Riprova tra poco.')
    else updateRefreshStatus('Aggiornamento non disponibile.', 'error')
  } finally {
    const currentRefreshButton = root?.querySelector('[data-refresh-share]')
    if (currentRefreshButton) {
      currentRefreshButton.disabled = false
      currentRefreshButton.classList.remove('is-loading')
    }
  }
}

const renderShare = (updateMessage = '', uiState = {}) => {
  const payload = share?.payload || {}
  const characters = Array.isArray(payload.characters) ? payload.characters : []
  const dialogues = Array.isArray(payload.dialogues) ? payload.dialogues : []
  const notes = Array.isArray(payload.notes) ? payload.notes : []
  const items = Array.isArray(payload.items) ? payload.items : []
  const progress = JSON.parse(localStorage.getItem(getPinStorageKey()) || '{}')
  if (!selectionInitialized) {
    try {
      const stored = JSON.parse(localStorage.getItem(getSelectionStorageKey()) || 'null')
      if (Array.isArray(stored)) selectedCharacters = new Set(stored)
    } catch {
      localStorage.removeItem(getSelectionStorageKey())
    }
    selectionInitialized = true
  }
  const availableCharacterIds = new Set(characters.map((character) => character.id))
  selectedCharacters = new Set([...selectedCharacters].filter((id) => availableCharacterIds.has(id)))
  const noteDialogueIds = noteDialogueIdsFromItems(items)
  const scriptItems = orderedScriptItems(items, dialogues, noteDialogueIds)
  const scriptTitle = formatScriptTitle(share?.scriptName)
  const allCharactersSelected = characters.length > 0 && selectedCharacters.size === characters.length
  const selectionActionLabel = allCharactersSelected ? 'Inverti selezione' : 'Seleziona tutto'
  const progressStats = dialogues.reduce((stats, dialogue) => {
    if (!selectedCharacters.has(dialogue.characterId)) return stats
    const status = progress[dialogue.id] || 'da_studiare'
    stats[status] = (stats[status] || 0) + 1
    return stats
  }, { da_studiare: 0, in_studio: 0, studiata: 0 })

  renderShell(`
    ${renderBrand(scriptTitle, formatPublishedAt(share?.publishedAt || payload.publishedAt), `<div class="share-header-actions"><button type="button" class="share-header-icon" data-refresh-share title="Aggiorna copione" aria-label="Aggiorna copione">${iconSvg('refresh')}</button><button type="button" class="share-header-action" data-signout>Esci</button></div>`)}
    <section class="share-card learning-card">
      <div class="learning-layout">
        <aside class="character-panel" aria-label="Selezione personaggi">
          <button type="button" class="character-menu-toggle" data-character-menu-toggle aria-expanded="${characterMenuOpen}" aria-controls="character-menu-content">${iconSvg('menu')}<span>Personaggi</span><span class="selection-count">${selectedCharacters.size}/${characters.length}</span></button>
          <div id="character-menu-content" class="character-panel-content${characterMenuOpen ? ' is-open' : ''}" data-character-menu>
            <div class="filter-heading character-panel-heading"><span class="field-label">Personaggi</span><span class="selection-count">${selectedCharacters.size}/${characters.length}</span></div>
            <label class="character-search">
              <span class="sr-only">Cerca personaggio</span>
              <span class="search-field-icon">${iconSvg('search')}</span>
              <input type="search" placeholder="Cerca personaggio" data-character-search />
            </label>
            <div class="character-options">
              ${characters.map((character) => `
                <label class="character-option" data-character-option data-character-name="${escapeHtml(character.name.toLowerCase())}">
                  <input type="checkbox" value="${escapeHtml(character.id)}" ${selectedCharacters.has(character.id) ? 'checked' : ''} />
                  <span>${escapeHtml(character.name)}</span>
                </label>
              `).join('')}
            </div>
            <div class="filter-modes" role="group" aria-label="Modalità filtro personaggi">
              <button type="button" data-filter-mode="only-selected" class="${filterMode === 'only-selected' ? 'active' : ''}" title="Solo selezionati" aria-label="Solo selezionati">${iconSvg('eye')}<span class="sr-only">Solo selezionati</span></button>
              <button type="button" data-filter-mode="hide-selected" class="${filterMode === 'hide-selected' ? 'active' : ''}" title="Nascondi selezionati" aria-label="Nascondi selezionati">${iconSvg('eye-off')}<span class="sr-only">Nascondi selezionati</span></button>
              <button type="button" data-character-selection-toggle title="${selectionActionLabel}" aria-label="${selectionActionLabel}">${iconSvg('select-all')}<span class="sr-only">${selectionActionLabel}</span></button>
            </div>
            <p class="character-help">Scegli uno o più personaggi per studiare le relative battute.</p>
          </div>
        </aside>
        <div class="learning-content">
          <div class="learning-summary">
            <div class="learning-summary-main"><strong>${dialogues.length} battute</strong><span>${notes.length} note di regia</span></div>
            <span class="refresh-status" data-refresh-status data-tone="${updateMessage ? 'success' : ''}">${escapeHtml(updateMessage)}</span>
            <div class="study-stats" aria-label="Stato delle battute">
              <span class="study-stat study-stat-da_studiare"><span class="study-stat-dot" aria-hidden="true"></span><span>Da studiare</span><strong data-study-stat="da_studiare">${progressStats.da_studiare}</strong></span>
              <span class="study-stat study-stat-in_studio"><span class="study-stat-dot" aria-hidden="true"></span><span>In studio</span><strong data-study-stat="in_studio">${progressStats.in_studio}</strong></span>
              <span class="study-stat study-stat-studiata"><span class="study-stat-dot" aria-hidden="true"></span><span>Completato</span><strong data-study-stat="studiata">${progressStats.studiata}</strong></span>
            </div>
          </div>
          <div class="script-tools">
            <label class="dialogue-search"><span class="search-field-icon">${iconSvg('search')}</span><span class="sr-only">Cerca battuta</span><input type="search" placeholder="Cerca battuta o personaggio" data-dialogue-search /></label>
            <div class="script-navigation" aria-label="Navigazione copione">
              <button type="button" data-script-nav="previous" title="Battuta precedente" aria-label="Battuta precedente">${iconSvg('previous')}</button>
              <label><span class="sr-only">Vai alla battuta</span><input type="number" min="1" max="${dialogues.length || 1}" placeholder="N." title="Numero battuta" aria-label="Numero battuta" data-dialogue-jump /></label>
              <button type="button" data-script-nav="next" title="Battuta successiva" aria-label="Battuta successiva">${iconSvg('next')}</button>
            </div>
          </div>
          <div class="dialogue-list">
            ${selectedCharacters.size === 0 ? '<p class="empty-state">Seleziona almeno un personaggio per visualizzare le battute.</p>' : ''}
            ${scriptItems.map(({ kind, item, index, dialogueIndex, dialogueId }) => {
              if (kind === 'note') {
                const owner = dialogues.find((dialogue) => dialogue.id === dialogueId)
                const noteVisible = !owner || filterMode === 'hide-selected' || selectedCharacters.has(owner.characterId)
                return renderNote(item, !noteVisible, dialogueId)
              }
              const selected = selectedCharacters.has(item.characterId)
              const concealed = filterMode === 'hide-selected' && selected && !revealedDialogueIds.has(item.id)
              const visible = filterMode === 'hide-selected' || selected
              const canToggleVisibility = filterMode === 'hide-selected' && selected
              const hasStudyControls = selected
              const status = progress[item.id] || 'da_studiare'
              return `<article class="actor-dialogue ${visible ? '' : 'is-hidden'} ${concealed ? 'is-dialogue-hidden' : ''}" data-character="${escapeHtml(item.characterId)}" data-dialogue-id="${escapeHtml(item.id)}" data-dialogue-index="${dialogueIndex}" data-dialogue-search="${escapeHtml(`${item.characterName} ${item.text}`.toLowerCase())}">
                <div class="actor-dialogue-header">
                  <strong>${escapeHtml(item.characterName)}</strong>
                <span class="dialogue-index">Battuta ${dialogueIndex + 1}</span>
                </div>
                <p class="dialogue-copy">${escapeHtml(item.text)}</p>
                ${hasStudyControls ? `<div class="status-picker" role="group" aria-label="Stato battuta ${dialogueIndex + 1}">
                  ${Object.entries(statusLabels).map(([value, label]) => `<button type="button" title="${label}" aria-label="${label}" data-progress="${escapeHtml(item.id)}" data-status="${value}" class="status-${value} ${status === value ? 'is-active' : ''}" aria-pressed="${status === value}">${iconSvg(statusIcon[value])}</button>`).join('')}
                  ${canToggleVisibility ? `<button type="button" class="reveal-dialogue" data-toggle-dialogue="${escapeHtml(item.id)}" title="${concealed ? 'Mostra' : 'Nascondi'} battuta" aria-label="${concealed ? 'Mostra' : 'Nascondi'} battuta">${iconSvg(concealed ? 'eye' : 'eye-off')}</button>` : ''}
                </div>` : ''}
              </article>`
            }).join('') || '<p class="empty-state">Nessuna battuta disponibile.</p>'}
          </div>
        </div>
      </div>
    </section>
  `)
  root.querySelector('[data-refresh-share]')?.addEventListener('click', () => void refreshSharedScript())
  root.querySelector('[data-character-menu-toggle]')?.addEventListener('click', (event) => {
    const toggle = event.currentTarget
    const panel = root.querySelector('[data-character-menu]')
    characterMenuOpen = !(panel?.classList.contains('is-open'))
    const open = panel?.classList.toggle('is-open', characterMenuOpen) ?? false
    toggle.setAttribute('aria-expanded', String(open))
  })
  root.querySelector('[data-character-search]')?.addEventListener('input', (event) => {
    const query = String(event.currentTarget.value || '').trim().toLowerCase()
    root.querySelectorAll('[data-character-option]').forEach((option) => {
      option.hidden = query && !String(option.dataset.characterName || '').includes(query)
    })
  })
  root.querySelector('[data-dialogue-search]')?.addEventListener('input', (event) => {
    const query = String(event.currentTarget.value || '').trim().toLowerCase()
    const matchingIds = new Set()
    root.querySelectorAll('.actor-dialogue').forEach((dialogue) => {
      const matches = !query || String(dialogue.dataset.dialogueSearch || '').includes(query)
      dialogue.classList.toggle('is-search-hidden', !matches)
      if (matches) matchingIds.add(dialogue.dataset.dialogueId)
    })
    root.querySelectorAll('.dialogue-context').forEach((note) => {
      const ownerId = note.dataset.dialogueId
      note.classList.toggle('is-search-hidden', Boolean(query && ownerId && !matchingIds.has(ownerId)))
    })
  })
  const focusDialogue = (dialogue) => {
    if (!dialogue) return
    root.querySelectorAll('.actor-dialogue.is-current').forEach((item) => item.classList.remove('is-current'))
    dialogue.classList.add('is-current')
    dialogue.setAttribute('tabindex', '-1')
    dialogue.scrollIntoView({ behavior: 'smooth', block: 'center' })
    dialogue.focus({ preventScroll: true })
  }
  root.querySelectorAll('[data-script-nav]').forEach((button) => {
    button.addEventListener('click', () => {
      const cards = Array.from(root.querySelectorAll('.actor-dialogue:not(.is-hidden):not(.is-search-hidden)'))
      if (!cards.length) return
      const current = root.querySelector('.actor-dialogue.is-current')
      const currentIndex = current ? cards.indexOf(current) : button.dataset.scriptNav === 'next' ? -1 : cards.length
      const direction = button.dataset.scriptNav === 'next' ? 1 : -1
      const nextIndex = Math.max(0, Math.min(cards.length - 1, currentIndex + direction))
      focusDialogue(cards[nextIndex])
    })
  })
  root.querySelector('[data-dialogue-jump]')?.addEventListener('change', (event) => {
    const requested = Number(event.currentTarget.value) - 1
    const target = root.querySelector(`[data-dialogue-index="${requested}"]:not(.is-hidden):not(.is-search-hidden)`)
    if (target) focusDialogue(target)
    else event.currentTarget.value = ''
  })
  root.querySelectorAll('.character-option input').forEach((input) => {
    input.addEventListener('change', () => {
      const scrollY = window.scrollY
      if (input.checked) selectedCharacters.add(input.value)
      else selectedCharacters.delete(input.value)
      persistSelectedCharacters()
      revealedDialogueIds = new Set()
      renderShare('', { focusCharacterId: input.value, scrollY })
    })
  })
  root.querySelectorAll('[data-filter-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      filterMode = button.dataset.filterMode || 'only-selected'
      revealedDialogueIds = new Set()
      renderShare()
    })
  })
  root.querySelector('[data-character-selection-toggle]')?.addEventListener('click', () => {
    const ids = characters.map((character) => character.id)
    selectedCharacters = allCharactersSelected ? new Set(ids.filter((id) => !selectedCharacters.has(id))) : new Set(ids)
    persistSelectedCharacters()
    revealedDialogueIds = new Set()
    renderShare()
  })
  root.querySelectorAll('[data-toggle-dialogue]').forEach((button) => {
    button.addEventListener('click', () => {
      const scrollY = window.scrollY
      const dialogueId = button.dataset.toggleDialogue
      if (revealedDialogueIds.has(dialogueId)) revealedDialogueIds.delete(dialogueId)
      else revealedDialogueIds.add(dialogueId)
      renderShare('', { scrollY })
    })
  })
  root.querySelectorAll('[data-progress]').forEach((button) => {
    button.addEventListener('click', () => {
      const next = JSON.parse(localStorage.getItem(getPinStorageKey()) || '{}')
      next[button.dataset.progress] = button.dataset.status
      localStorage.setItem(getPinStorageKey(), JSON.stringify(next))
      const nextStats = dialogues.reduce((stats, dialogue) => {
        if (!selectedCharacters.has(dialogue.characterId)) return stats
        const status = next[dialogue.id] || 'da_studiare'
        stats[status] = (stats[status] || 0) + 1
        return stats
      }, { da_studiare: 0, in_studio: 0, studiata: 0 })
      Object.entries(nextStats).forEach(([status, count]) => {
        const stat = root.querySelector(`[data-study-stat="${status}"]`)
        if (stat) stat.textContent = count
      })
      const group = button.parentElement
      group?.querySelectorAll('[data-progress]').forEach((item) => {
        const active = item === button
        item.classList.toggle('is-active', active)
        item.setAttribute('aria-pressed', String(active))
      })
    })
  })
  root.querySelector('[data-signout]')?.addEventListener('click', () => void signOut())
  if (uiState.focusCharacterId || Number.isFinite(uiState.scrollY)) {
    requestAnimationFrame(() => {
      if (uiState.focusCharacterId) {
        const input = Array.from(root.querySelectorAll('.character-option input')).find((item) => item.value === uiState.focusCharacterId)
        input?.focus({ preventScroll: true })
      }
      if (Number.isFinite(uiState.scrollY)) window.scrollTo(0, uiState.scrollY)
    })
  }
}

async function submitEmailAuth(form) {
  const formData = new FormData(form)
  const email = String(formData.get('email') || '')
  const password = String(formData.get('password') || '')
  setMessage('Autenticazione in corso...')
  const result = authMode === 'signin'
    ? await supabase.auth.signInWithPassword({ email, password })
    : await supabase.auth.signUp({ email, password, options: { emailRedirectTo: shareAuthRedirectUrl() } })
  if (result.error) {
    renderAuth(result.error.message)
    return
  }
  if (authMode === 'signup' && !result.data.session) {
    renderAuth('Registrazione creata. Controlla la mail per confermare l’account.')
  }
}

async function signInWithProvider(provider) {
  setMessage('Apertura del provider in corso...')
  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: shareAuthRedirectUrl() },
  })
  if (error) renderAuth(error.message)
}

async function verifyPin(form) {
  const pin = String(new FormData(form).get('pin') || '').replace(/\D/g, '')
  setMessage('Verifica PIN in corso...')
  const { data, error } = await supabase.rpc('verify_script_share', { p_share_uid: shareUid, p_pin: pin })
  if (error) {
    renderPinForm(error.message)
    return
  }
  if (!data?.ok) {
    renderPinForm(data?.error || 'PIN non valido')
    return
  }
  share = data.share
  cacheShareAccess(share, pin)
  renderShare()
}

async function signOut(message = '') {
  clearCachedShareAccess()
  await supabase.auth.signOut()
  share = undefined
  clearSelectedCharacters()
  selectionInitialized = false
  filterMode = 'hide-selected'
  revealedDialogueIds = new Set()
  renderAuth(message)
}

async function bootstrap() {
  if (!shareUid || !/^[0-9a-f-]{36}$/i.test(shareUid)) {
    renderShell(`${renderBrand('Link non valido')}<section class="share-card"><p class="share-message" data-tone="error">Il collegamento di condivisione non è valido.</p></section>`)
    return
  }
  const configResponse = await fetch('/share-config', { cache: 'no-store' })
  const config = await configResponse.json()
  if (!config.url || !config.publishableKey) {
    renderShell(`${renderBrand('Configurazione non disponibile')}<section class="share-card"><p class="share-message" data-tone="error">La pagina di condivisione non è ancora configurata.</p></section>`)
    return
  }
  supabase = createClient(config.url, config.publishableKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' } })
  const { data } = await supabase.auth.getSession()
  session = data.session
  if (session) {
    const cachedShare = readCachedAccess()
    if (cachedShare) {
      share = cachedShare.share
      if (cachedShare.hasPin) await refreshSharedScript(true)
      else renderShare('Accesso ripristinato. Premi aggiorna per riconvalidare il PIN.')
    }
    else renderPinForm()
  }
  else renderAuth()
  supabase.auth.onAuthStateChange((_event, nextSession) => {
    session = nextSession
    if (session) {
      const cachedShare = readCachedAccess()
      if (cachedShare) {
        if (!share) {
          share = cachedShare.share
          if (cachedShare.hasPin) void refreshSharedScript(true)
          else renderShare('Accesso ripristinato. Premi aggiorna per riconvalidare il PIN.')
        }
      } else {
        share = undefined
        renderPinForm()
      }
    }
    else {
      clearCachedShareAccess()
      share = undefined
      renderAuth()
    }
  })
}

bootstrap().catch((error) => {
  renderShell(`${renderBrand('Errore di caricamento')}<section class="share-card"><p class="share-message" data-tone="error">${escapeHtml(error.message || error)}</p></section>`)
})
