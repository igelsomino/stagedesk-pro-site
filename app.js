const owner = 'igelsomino'
const repo = 'stagedesk-pro'
const fallbackTag = 'v1.0.13'
const releaseUrl = `https://github.com/${owner}/${repo}/releases/tag/${fallbackTag}`

const fallbackAssets = [
  'StageDesk.Pro_1.0.13_aarch64.dmg',
  'StageDesk.Pro_1.0.13_x64.dmg',
  'StageDesk.Pro_1.0.13_x64-setup.exe',
  'StageDesk.Pro_1.0.13_x64_en-US.msi',
  'StageDesk.Pro_1.0.13_amd64.AppImage',
  'StageDesk.Pro_1.0.13_amd64.deb',
  'StageDesk.Pro-1.0.13-1.x86_64.rpm',
]

const downloadsEl = document.querySelector('#downloads')
const statusEl = document.querySelector('#release-status')

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

  osGroups.forEach((group) => {
    const groupAssets = filteredAssets.filter((asset) => group.match(asset.name))
    const card = document.createElement('article')
    card.className = 'download-card'

    const header = document.createElement('header')
    header.innerHTML = `<span class="os">${group.label}</span><span class="version">${tag}</span>`

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
        link.className = index === 0 ? 'primary' : ''
        link.href = asset.browser_download_url || githubDownloadUrl(tag, asset.name)
        link.textContent = assetLabel(asset.name)

        const detail = document.createElement('span')
        detail.textContent = asset.name
        link.append(detail)
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
    const assets = fallbackAssets.map((name) => ({
      name,
      browser_download_url: githubDownloadUrl(fallbackTag, name),
    }))
    renderDownloads(fallbackTag, assets, releaseUrl)
    statusEl.textContent = `Download disponibili dalla release ${fallbackTag}.`
  }
}

loadRelease()
