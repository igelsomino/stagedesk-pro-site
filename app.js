const owner = 'igelsomino'
const repo = 'stagedesk-pro'
const latestReleaseUrl = `https://github.com/${owner}/${repo}/releases/latest`

const downloadsEl = document.querySelector('#downloads')
const statusEl = document.querySelector('#release-status')
const heroVersionEl = document.querySelector('#hero-version')
const headerDownloadEl = document.querySelector('#header-download')

function setupCarousel(carousel) {
  if (!carousel) return
  const track = carousel.querySelector('[data-carousel-track]')
  const slides = [...carousel.querySelectorAll('[data-carousel-slide]')]
  const dots = [...carousel.querySelectorAll('[data-carousel-dot]')]
  const counter = carousel.querySelector('[data-carousel-counter]')
  const previous = carousel.querySelector('[data-carousel-previous]')
  const next = carousel.querySelector('[data-carousel-next]')
  if (!track || slides.length === 0) return

  let activeIndex = 0
  let timer
  let touchStartX

  const render = (index) => {
    activeIndex = (index + slides.length) % slides.length
    track.style.transform = `translate3d(${-activeIndex * 100}%, 0, 0)`
    slides.forEach((slide, slideIndex) => {
      slide.setAttribute('aria-hidden', String(slideIndex !== activeIndex))
    })
    dots.forEach((dot, dotIndex) => {
      dot.setAttribute('aria-selected', String(dotIndex === activeIndex))
    })
    if (counter) counter.textContent = `${String(activeIndex + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`
  }

  const stop = () => {
    if (timer) window.clearInterval(timer)
    timer = undefined
  }

  const start = () => {
    stop()
    timer = window.setInterval(() => render(activeIndex + 1), 6500)
  }

  previous?.addEventListener('click', () => { render(activeIndex - 1); start() })
  next?.addEventListener('click', () => { render(activeIndex + 1); start() })
  dots.forEach((dot, index) => dot.addEventListener('click', () => { render(index); start() }))

  carousel.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      render(activeIndex - 1)
      start()
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault()
      render(activeIndex + 1)
      start()
    }
  })
  carousel.addEventListener('mouseenter', stop)
  carousel.addEventListener('mouseleave', start)
  carousel.addEventListener('focusin', stop)
  carousel.addEventListener('focusout', (event) => {
    if (!(event.relatedTarget instanceof Node) || !carousel.contains(event.relatedTarget)) start()
  })
  carousel.addEventListener('touchstart', (event) => {
    touchStartX = event.changedTouches[0]?.clientX
    stop()
  }, { passive: true })
  carousel.addEventListener('touchend', (event) => {
    const endX = event.changedTouches[0]?.clientX
    if (touchStartX !== undefined && endX !== undefined && Math.abs(endX - touchStartX) > 42) {
      render(activeIndex + (endX < touchStartX ? 1 : -1))
    }
    touchStartX = undefined
    start()
  }, { passive: true })

  render(0)
  start()
}

const osGroups = [
  {
    id: 'macos',
    label: 'macOS',
    description: 'Installer DMG per Apple Silicon e Intel.',
    match: (name) => name.endsWith('.dmg'),
  },
  {
    id: 'windows',
    label: 'Windows',
    description: 'Setup EXE e pacchetto MSI per Windows x64.',
    match: (name) => name.endsWith('.exe') || name.endsWith('.msi'),
  },
  {
    id: 'linux',
    label: 'Linux',
    description: 'Pacchetti AppImage, DEB e RPM per distribuzioni Linux x64.',
    match: (name) => name.endsWith('.AppImage') || name.endsWith('.deb') || name.endsWith('.rpm'),
  },
]

function detectOperatingSystem() {
  const platform = `${navigator.userAgentData?.platform || ''} ${navigator.platform || ''} ${navigator.userAgent || ''}`.toLowerCase()
  if (platform.includes('win')) return 'windows'
  if (platform.includes('mac')) return 'macos'
  if (platform.includes('linux')) return 'linux'
  return undefined
}

function selectInstaller(osId, assets) {
  const group = osGroups.find((item) => item.id === osId)
  const candidates = group ? assets.filter((asset) => group.match(asset.name)) : []
  if (candidates.length === 0) return undefined

  if (osId === 'macos') {
    const architecture = `${navigator.userAgentData?.architecture || ''} ${navigator.platform || ''}`.toLowerCase()
    const preferred = architecture.includes('arm') || architecture.includes('aarch')
      ? candidates.find((asset) => /aarch64|arm64/i.test(asset.name))
      : candidates.find((asset) => /x64|x86_64|intel/i.test(asset.name))
    return preferred || candidates[0]
  }

  if (osId === 'windows') {
    return candidates.find((asset) => asset.name.endsWith('.exe')) || candidates[0]
  }

  return candidates.find((asset) => asset.name.endsWith('.AppImage'))
    || candidates.find((asset) => asset.name.endsWith('.deb'))
    || candidates[0]
}

function configureHeaderDownload(tag, assets) {
  if (!headerDownloadEl) return
  const installer = selectInstaller(detectOperatingSystem(), assets)
  if (!installer) {
    headerDownloadEl.href = '#download'
    headerDownloadEl.removeAttribute('title')
    return
  }

  headerDownloadEl.href = installer.browser_download_url || githubDownloadUrl(tag, installer.name)
  headerDownloadEl.title = `Scarica ${assetLabel(installer.name)}`
}

function osIcon(id) {
  if (id === 'macos') {
    return `<svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M16.7 13.1c0-2.2 1.8-3.3 1.9-3.4-1-1.5-2.6-1.7-3.2-1.8-1.4-.1-2.6.8-3.3.8-.7 0-1.8-.8-2.9-.8-1.5 0-2.9.9-3.7 2.2-1.6 2.8-.4 7 1.2 9.2.8 1.1 1.7 2.4 2.9 2.3 1.2 0 1.6-.7 3-.7s1.8.7 3 .7c1.3 0 2.1-1.1 2.8-2.3.9-1.3 1.2-2.5 1.2-2.6 0-.1-2.4-1-2.4-3.6ZM14.5 6.5c.6-.8 1.1-1.8 1-2.9-1 .1-2 .7-2.7 1.5-.6.7-1.1 1.8-1 2.8 1 .1 2.1-.5 2.7-1.4Z"/>
    </svg>`
  }

  if (id === 'windows') {
    return `<svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 5.2 11 4v7.6H3V5.2Zm9-1.4 9-1.3v9.1h-9V3.8ZM3 12.7h8v7.4L3 19v-6.3Zm9 0h9v8.8l-9-1.3v-7.5Z"/>
    </svg>`
  }

  return '<img class="os-raster-icon" src="./assets/linux-platform-icon.png" alt="" aria-hidden="true" />'
}

function assetLabel(name) {
  if (name.includes('aarch64') && name.endsWith('.dmg')) return 'Apple Silicon'
  if (name.includes('x64') && name.endsWith('.dmg')) return 'Intel'
  if (name.endsWith('.exe')) return 'Setup EXE'
  if (name.endsWith('.msi')) return 'MSI'
  if (name.endsWith('.AppImage')) return 'AppImage'
  if (name.endsWith('.deb')) return 'Debian/Ubuntu'
  if (name.endsWith('.rpm')) return 'Fedora/RHEL'
  return 'Download'
}

function githubDownloadUrl(tag, name) {
  return `https://github.com/${owner}/${repo}/releases/download/${tag}/${encodeURIComponent(name)}`
}

function renderDownloads(tag, assets, sourceUrl) {
  if (!downloadsEl) return
  const filteredAssets = (Array.isArray(assets) ? assets : []).filter((asset) => !asset.name.endsWith('.sig') && asset.name !== 'latest.json')
  downloadsEl.innerHTML = ''
  if (heroVersionEl) heroVersionEl.textContent = tag
  configureHeaderDownload(tag, filteredAssets)

  osGroups.forEach((group) => {
    const groupAssets = filteredAssets.filter((asset) => group.match(asset.name))
    const card = document.createElement('article')
    card.className = 'download-card'

    const header = document.createElement('header')
    header.innerHTML = `<span class="os">${osIcon(group.id)}${group.label}</span>`

    const description = document.createElement('p')
    description.textContent = group.description

    const list = document.createElement('div')
    list.className = 'asset-list'

    if (groupAssets.length === 0) {
      const link = document.createElement('a')
      link.href = sourceUrl
      link.target = '_blank'
      link.rel = 'noreferrer'
      link.textContent = 'Apri release'
      list.append(link)
    } else {
      groupAssets.forEach((asset, index) => {
        const link = document.createElement('a')
        link.href = asset.browser_download_url || githubDownloadUrl(tag, asset.name)
        link.textContent = assetLabel(asset.name)
        list.append(link)
      })
    }

    card.append(header, description, list)
    downloadsEl.append(card)
  })
}

async function loadRelease() {
  if (!downloadsEl || !statusEl) return
  try {
    const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/releases/latest`, {
      headers: { Accept: 'application/vnd.github+json' },
    })
    if (!response.ok) throw new Error(`GitHub API ${response.status}`)
    const release = await response.json()
    renderDownloads(release.tag_name, release.assets, release.html_url)
    statusEl.textContent = `Ultima release disponibile: ${release.tag_name}`
  } catch {
    renderDownloads('Ultima release', [], latestReleaseUrl)
    statusEl.textContent = 'Non riesco a leggere automaticamente la release: apri la pagina GitHub aggiornata.'
  }
}

if (downloadsEl && statusEl) loadRelease()
document.querySelectorAll('[data-carousel]').forEach(setupCarousel)
