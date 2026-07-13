const owner = 'igelsomino'
const repo = 'stagedesk-pro'
const latestReleaseUrl = `https://github.com/${owner}/${repo}/releases/latest`

const downloadsEl = document.querySelector('#downloads')
const statusEl = document.querySelector('#release-status')
const heroVersionEl = document.querySelector('#hero-version')

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

  return `<svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4.4 4.2h15.2c1 0 1.8.8 1.8 1.8v9.8c0 1-.8 1.8-1.8 1.8h-5.4l1.2 1.9h2.1c.5 0 .9.4.9.9s-.4.9-.9.9h-11c-.5 0-.9-.4-.9-.9s.4-.9.9-.9h2.1l1.2-1.9H4.4c-1 0-1.8-.8-1.8-1.8V6c0-1 .8-1.8 1.8-1.8Zm.2 2v9.4h14.8V6.2H4.6Zm4.1 2.1 2.4 2.4-2.4 2.4-1.2-1.2 1.2-1.2-1.2-1.2 1.2-1.2Zm3.6 4h4.2V14h-4.2v-1.7Z"/>
  </svg>`
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
  const filteredAssets = assets.filter((asset) => !asset.name.endsWith('.sig') && asset.name !== 'latest.json')
  downloadsEl.innerHTML = ''
  if (heroVersionEl) heroVersionEl.textContent = tag

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

loadRelease()
