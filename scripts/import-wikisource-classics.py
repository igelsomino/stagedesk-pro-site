#!/usr/bin/env python3
"""Import complete Italian theatre editions from Wikisource into StageDesk.

The generated packages are intentionally kept in the ignored Store asset
directory. Source attribution is written into every package and into the
catalog metadata managed by seed-store-demo.mjs.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlencode

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / ".store-assets" / "copioni"
CACHE_DIR = ROOT / ".store-assets" / "source-cache" / "wikisource-html"
API = "https://it.wikisource.org/w/api.php"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def clean(value: str) -> str:
    value = html.unescape(value.replace("\xa0", " "))
    value = re.sub(r"\[\s*p\.?\s*\d+\s+modifica\s*\]", "", value, flags=re.I)
    value = re.sub(r"\[\s*\d+\s*\]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t\r\n")


def api(params: dict[str, str]) -> dict:
    query = urlencode({"format": "json", **params})
    url = f"{API}?{query}"
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            raw = subprocess.check_output(
                ["curl", "-Lk", "-sS", "--max-time", "45", "-A", "StageDeskStoreImporter/1.0", url],
                text=True,
            )
            if raw.lstrip().startswith("{"):
                return json.loads(raw)
            last_error = RuntimeError(f"Risposta non JSON da Wikisource: {raw[:120]!r}")
        except Exception as error:
            last_error = error
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"API Wikisource non disponibile per {params.get('titles') or params.get('page')}: {last_error}")


def linked_pages(base: str) -> list[str]:
    pages: list[str] = []
    params = {"action": "query", "titles": base, "prop": "links", "plnamespace": "0", "pllimit": "max"}
    while True:
        data = api(params)
        page = next(iter(data.get("query", {}).get("pages", {}).values()))
        pages.extend(link["title"] for link in page.get("links", []))
        if "continue" not in data:
            break
        params.update({key: str(value) for key, value in data["continue"].items()})
    return pages


def parse_html(title: str) -> BeautifulSoup:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{slugify(title)}.html"
    if cache_path.exists():
        return BeautifulSoup(cache_path.read_text(encoding="utf-8"), "html.parser")
    url = f"https://it.wikisource.org/wiki/{quote(title, safe='/') }"
    response = subprocess.run(
        ["curl", "-Lk", "-sS", "--max-time", "45", "-A", "StageDeskStoreImporter/1.0", "-w", "\n%{http_code}", url],
        capture_output=True,
        text=True,
        check=True,
    )
    body, status = response.stdout.rsplit("\n", 1)
    if status != "200":
        return BeautifulSoup("", "html.parser")
    markup = body
    cache_path.write_text(markup, encoding="utf-8")
    time.sleep(0.8)
    return BeautifulSoup(markup, "html.parser")


def roman_or_word(value: str) -> int | None:
    words = {
        "primo": 1, "prima": 1, "i": 1,
        "secondo": 2, "seconda": 2, "ii": 2,
        "terzo": 3, "terza": 3, "iii": 3,
        "quarto": 4, "quarta": 4, "iv": 4,
        "quinto": 5, "quinta": 5, "v": 5,
    }
    value = value.strip().rstrip(".").lower()
    return words.get(value)


def page_position(title: str) -> tuple[int, int | None]:
    # Match longer Roman numerals first and require the page boundary. Without
    # this, "Atto II" is incorrectly captured as act I.
    act_match = re.search(r"/Atto\s+(Primo|Secondo|Terzo|Quarto|Quinto|V|IV|III|II|I)(?:/|$)", title, re.I)
    if not act_match:
        raise ValueError(f"Atto non riconosciuto: {title}")
    act = roman_or_word(act_match.group(1))
    scene_match = re.search(r"/Scena\s+(.+)$", title, re.I)
    if not scene_match:
        return act or 1, None
    value = scene_match.group(1).strip()
    words = {
        "prima": 1, "seconda": 2, "terza": 3, "quarta": 4, "quinta": 5,
        "sesta": 6, "settima": 7, "ottava": 8, "nona": 9, "decima": 10,
        "undicesima": 11, "dodicesima": 12, "tredicesima": 13,
        "quattordicesima": 14, "quindicesima": 15, "I": 1, "II": 2,
        "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
        "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13,
    }
    return act or 1, words.get(value.rstrip(".").lower(), words.get(value.rstrip(".").upper()))


def page_lines(title: str) -> list[str]:
    soup = parse_html(title)
    root = soup.select_one(".prp-pages-output") or soup.select_one(".testi")
    if not root:
        return []
    lines: list[str] = []
    # Italian editions on Wikisource use definition lists for speaker/dialogue
    # pairs, while older scanned editions use paragraphs with abbreviated labels.
    for child in root.find_all(["p", "dt", "dd"], recursive=True):
        text = clean(child.get_text(" ", strip=True))
        if not text:
            continue
        if child.name == "dt":
            lines.append(f"@@SPEAKER@@ {text}")
        elif child.name == "dd":
            lines.append(text)
        else:
            lines.append(text)
    return lines


def is_heading(line: str, prefix: str) -> bool:
    return bool(re.match(rf"^{prefix}\s+(?:PRIMO|PRIMA|SECONDO|SECONDA|TERZO|TERZA|QUARTO|QUARTA|QUINTO|QUINTA|[IVX]+)\.?$", line, re.I))


def normalize_label(value: str) -> str:
    value = clean(value)
    value = re.sub(r"\s*\.$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def resolve_speaker(label: str, aliases: dict[str, str], known: list[str]) -> str | None:
    label = normalize_label(label)
    if not label or len(label) > 70:
        return None
    if label.upper() in {"SCENA", "ATTO", "PERSONAGGI", "INTERLOCUTORI"}:
        return None
    key = normalize_label(label).upper()
    for source, target in aliases.items():
        if key == source.upper():
            return target
    for character in known:
        if key == character.upper() or key.startswith(character.upper() + " "):
            return character
    if re.search(r"[.!?]$", label) and " " not in label:
        return None
    return label.upper()


def extract_dialogue(lines: list[str], config: dict) -> tuple[list[tuple[str, str]], list[str]]:
    aliases = config.get("aliases", {})
    known = config["characters"]
    blocks: list[tuple[str, str]] = []
    directions: list[str] = []
    current_speaker: str | None = None
    current_text: list[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_text
        if current_speaker and current_text:
            text = clean(" ".join(current_text))
            if text and not re.fullmatch(r"[—–-]", text):
                blocks.append((current_speaker, text))
        current_speaker = None
        current_text = []

    for raw in lines:
        line = clean(raw.replace("@@SPEAKER@@", ""))
        if not line:
            continue
        if re.match(r"^NOTE\s+DELL\b", line, re.I):
            flush()
            break
        # Music numbers, page headers and source metadata are not dialogue.
        if re.fullmatch(r"(?:N\.\s*)?\d+\s*(?:[-–].*)?", line) or line.lower().startswith(("informazioni sulla fonte", "modifica")):
            continue
        speaker: str | None = None
        if "@@SPEAKER@@" in raw:
            speaker = resolve_speaker(line, aliases, known)
        else:
            match = re.match(r"^(.{1,55}?)\s+\.\s+(.*)$", line)
            if match:
                speaker = resolve_speaker(match.group(1), aliases, known)
                if speaker:
                    line = match.group(2).strip()
            elif re.match(r"^[A-ZÀ-Ý][A-ZÀ-Ý '\-]{1,45}\s*\.\s*$", line):
                speaker = resolve_speaker(line, aliases, known)
                line = ""
        if speaker:
            flush()
            current_speaker = speaker
            if line:
                current_text.append(line)
            continue
        if current_speaker:
            if line.startswith(("(", "[")) and line.endswith((")", "]")):
                directions.append(line)
            current_text.append(line)
        elif line.startswith(("(", "[", "Entr", "Escon", "Rientr", "Entra", "Esce")):
            directions.append(line)
    flush()
    return blocks, directions


def split_scenes(lines: list[str], default_scene: int | None) -> list[tuple[int, list[str]]]:
    scenes: list[tuple[int, list[str]]] = []
    current_number = default_scene or 1
    current: list[str] = []
    for line in lines:
        match = re.match(r"^SCENA\s+(.+?)\.?$", line, re.I)
        if match:
            if current:
                scenes.append((current_number, current))
            value = match.group(1).strip().upper()
            current_number = {
                "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
                "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
                "PRIMA": 1, "SECONDA": 2, "TERZA": 3, "QUARTA": 4, "QUINTA": 5,
                "SESTA": 6, "SETTIMA": 7, "OTTAVA": 8, "NONA": 9, "DECIMA": 10,
                "UNDICESIMA": 11, "DODICESIMA": 12, "TREDICESIMA": 13,
            }.get(value, current_number)
            current = []
            continue
        current.append(line)
    if current:
        scenes.append((current_number, current))
    return scenes


def source_scenes(config: dict) -> list[tuple[int, int, str, list[tuple[str, str]], list[str]]]:
    pages = config.get("source_pages") or linked_pages(config["source_page"])
    content_pages = [
        page for page in pages
        if re.search(r"/Atto\s+(?:Primo|Secondo|Terzo|Quarto|Quinto|V|IV|III|II|I)(?:/Scena\s+.+)?$", page, re.I)
    ]
    content_pages.sort(key=lambda page: (page_position(page)[0], page_position(page)[1] or 0, page))
    result: list[tuple[int, int, str, list[tuple[str, str]], list[str]]] = []
    for page in content_pages:
        act, page_scene = page_position(page)
        lines = page_lines(page)
        if page_scene is not None:
            chunks = [(page_scene, lines)]
        else:
            chunks = split_scenes(lines, None)
        for scene, chunk in chunks:
            filtered = [line for line in chunk if not is_heading(line, "ATTO") and not is_heading(line, "SCENA")]
            title = next((line for line in filtered if line and not re.match(r"^[A-ZÀ-Ý .,'’\-]+$", line) and not line.startswith("@@SPEAKER@@")), f"Scena {scene}")
            blocks, directions = extract_dialogue(filtered, config)
            if blocks:
                result.append((act, scene, title[:120], blocks, directions[:8]))
    return result


def package(config: dict) -> str:
    scenes = source_scenes(config)
    if not scenes:
        raise RuntimeError(f"Nessuna scena importata per {config['title']}")
    all_characters = list(config["characters"])
    presence: dict[str, list[str]] = {name: [] for name in all_characters}
    for act, scene, _, blocks, _ in scenes:
        for speaker, _ in blocks:
            if speaker in {"TUTTI", "TUTTE", "CORO", "ENSEMBLE"} or speaker.startswith("NOTE DELL"):
                continue
            if speaker not in all_characters:
                all_characters.append(speaker)
            presence.setdefault(speaker, [])
            if f"{act}/{scene}" not in presence[speaker]:
                presence[speaker].append(f"{act}/{scene}")
    lines = ["| Personaggio | Interprete | Presenza |", "| --- | --- | --- |"]
    for name in all_characters:
        locations = "; ".join(presence.get(name, []))
        if locations:
            lines.append(f"| {name} | D/A | {locations} |")
    lines += ["", f"# {config['title']}", "", f"> **EDIZIONE INTEGRALE**: {config['attribution']}.", "> Le note di regia StageDesk sono originali e aggiunte alla fonte per il lavoro in prova.", ""]
    count = 0
    for act in sorted({item[0] for item in scenes}):
        lines += [f"# Atto {act}", ""]
        for parsed_act, scene, title, blocks, directions in scenes:
            if parsed_act != act:
                continue
            scene_id = f"atto-{act}-scena-{scene}"
            speakers = ", ".join(dict.fromkeys(
                speaker for speaker, _ in blocks
                if speaker not in {"TUTTI", "TUTTE", "CORO", "ENSEMBLE"} and not speaker.startswith("NOTE DELL")
            ))
            lines += [f"## Scena {scene}" + (f" — {title}" if title and not title.lower().startswith("scena ") else ""), ""]
            lines += [f'::regia{{id="note-{scene_id}-personaggi" type="characters" color="blue" title="Personaggi in scena" sceneId="{scene_id}" anchorId="note-{scene_id}-personaggi"}}', speakers, "::"]
            if directions:
                lines += [f'::regia{{id="note-{scene_id}-movimento" type="movement" color="green" title="Movimento" sceneId="{scene_id}" anchorId="note-{scene_id}-movimento"}}', " ".join(directions), "::"]
            lines += [f'::regia{{id="note-{scene_id}-tono" type="tone" color="purple" title="Tono" sceneId="{scene_id}" anchorId="note-{scene_id}-tono"}}', f"La scena «Scena {scene}» segue il ritmo e il tono dell'edizione integrale di riferimento.", "::", ""]
            for speaker, text in blocks:
                count += 1
                lines += [f'::battuta{{id="battuta-{scene_id}-{count}" characterId="{slugify(speaker)}" character="{html.escape(speaker, quote=False)}" sceneId="{scene_id}"}}', text, "::", ""]
    lines += [f"> **Fonte**: {config['source_url']} (consultata per l'edizione integrale).", ""]
    if count < 20:
        raise RuntimeError(f"Importazione sospetta per {config['title']}: solo {count} battute")
    return "\n".join(lines)


WORKS = [
    {"slug": "la-mandragola", "title": "La mandragola", "source_page": "La mandragola", "source_pages": [f"La mandragola/Atto {act}/Scena {scene}" for act, scenes in [("primo", ["prima", "seconda", "terza"]), ("secondo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta"]), ("terzo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima", "undecima", "duodecima"]), ("quarto", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima"]), ("quinto", ["prima", "seconda", "terza", "quarta", "quinta", "sesta"])] for scene in scenes], "source_url": "https://it.wikisource.org/wiki/La_mandragola", "attribution": "testo di Niccolò Machiavelli, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["CALLIMACO", "LUCREZIA", "MESSER NICIA", "LIGURIO", "SIRO", "FRATE TIMOTEO", "SOSTRATA"], "aliases": {"Callimaco": "CALLIMACO", "Siro": "SIRO", "Ligurio": "LIGURIO", "Lucrezia": "LUCREZIA", "Nicia": "MESSER NICIA", "Messer Nicia": "MESSER NICIA", "Frate Timoteo": "FRATE TIMOTEO", "Timoteo": "FRATE TIMOTEO", "Sostrata": "SOSTRATA"}, "package": "la-mandragola.stagedesk"},
    {"slug": "tartufo", "title": "Tartufo", "source_page": "Tartufo - Il Misantropo/Tartufo", "source_pages": [f"Tartufo - Il Misantropo/Tartufo/Atto {word}" for word in ["primo", "secondo", "terzo", "quarto", "quinto"]], "source_url": "https://it.wikisource.org/wiki/Tartufo_-_Il_Misantropo", "attribution": "testo di Molière, traduzione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["ORGONE", "TARTUFO", "ELMIRA", "DAMIDE", "MARIANA", "VALERIO", "CLEANTO", "DORINA", "MADAMA PERNELLA", "LEALI", "FILIPPA"], "aliases": {}, "package": "tartufo.stagedesk"},
    {"slug": "la-locandiera", "title": "La locandiera", "source_page": "La locandiera", "source_pages": ["La locandiera/Atto I", "La locandiera/Atto II", "La locandiera/Atto III"], "source_url": "https://it.wikisource.org/wiki/La_locandiera", "attribution": "testo di Carlo Goldoni, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["MIRANDOLINA", "CAVALIERE", "MARCHESE", "CONTE", "FABRIZIO", "ORTENSIA", "DEJANIRA", "SERVITORE"], "aliases": {}, "package": "la-locandiera.stagedesk"},
    {"slug": "i-rusteghi", "title": "I rusteghi", "source_page": "I rusteghi", "source_pages": ["I rusteghi/Atto I", "I rusteghi/Atto II", "I rusteghi/Atto III"], "source_url": "https://it.wikisource.org/wiki/I_rusteghi", "attribution": "testo di Carlo Goldoni, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["LUNARDO", "MAURIZIO", "SIMON", "LUCIETTA", "MARGARITA", "MARINA", "FELICE", "FILIPPETTO", "RICCARDO", "CANCIANO"], "aliases": {}, "package": "i-rusteghi.stagedesk"},
    {"slug": "le-baruffe-chiozzotte", "title": "Le baruffe chiozzotte", "source_page": "Le baruffe chiozzotte", "source_pages": ["Le baruffe chiozzotte/Atto I", "Le baruffe chiozzotte/Atto II", "Le baruffe chiozzotte/Atto III"], "source_url": "https://it.wikisource.org/wiki/Le_baruffe_chiozzotte", "attribution": "testo di Carlo Goldoni, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["TOFFOLO", "TITTA-NANE", "PASCUAL", "ISIDORO", "VICENZA", "PASQUA", "LIBERA", "ORSETTA", "CHECCA", "LUCIETTA", "ORSO", "BEPO"], "aliases": {}, "package": "le-baruffe-chiozzotte.stagedesk"},
    {"slug": "il-teatro-comico", "title": "Il teatro comico", "source_page": "Il teatro comico", "source_pages": ["Il teatro comico/Atto I", "Il teatro comico/Atto II", "Il teatro comico/Atto III"], "source_url": "https://it.wikisource.org/wiki/Il_teatro_comico", "attribution": "testo di Carlo Goldoni, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["ORAZIO", "PLACIDA", "BEATRICE", "EUGENIO", "LELIO", "ELEONORA", "VITTORIA", "TONINO", "PETRONIO", "ANSELMO", "GIANNI", "IL SUGGERITORE", "STAFFIERE"], "aliases": {}, "package": "il-teatro-comico.stagedesk"},
    {"slug": "sogno-di-una-notte-d-estate", "title": "Il sogno di una notte d'estate", "source_page": "Il Sogno di una notte d'estate", "source_pages": [f"Il Sogno di una notte d'estate/Atto {word}" for word in ["primo", "secondo", "terzo", "quarto", "quinto"]], "source_url": "https://it.wikisource.org/wiki/Il_Sogno_di_una_notte_d%27estate", "attribution": "testo di William Shakespeare nella traduzione storica di Carlo Rusconi, digitalizzato da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["TESEO", "IPPOLITA", "EGEI", "ERMIA", "LISANDRO", "DEMETRIO", "ELENA", "OBERONE", "TITANIA", "PUCK", "FONDO", "QUINCE", "FLAUTO", "FAME", "TIMPANO", "CECCHINO", "SCAGLIA"], "aliases": {"Tes": "TESEO", "Ip": "IPPOLITA", "Eg": "EGEI", "Er": "ERMIA", "Lis": "LISANDRO", "Dem": "DEMETRIO", "El": "ELENA", "Ob": "OBERONE", "Tit": "TITANIA", "Puc": "PUCK", "Bot": "FONDO", "Qui": "QUINCE", "Fla": "FLAUTO", "Fondo": "FONDO"}, "package": "sogno-di-una-notte-d-estate.stagedesk"},
    {"slug": "la-dodicesima-notte", "title": "La dodicesima notte", "source_page": "La dodicesima notte o quel che vorrete", "source_pages": [f"La dodicesima notte o quel che vorrete/Atto {word}" for word in ["primo", "secondo", "terzo", "quarto", "quinto"]], "source_url": "https://it.wikisource.org/wiki/La_dodicesima_notte_o_quel_che_vorrete", "attribution": "testo di William Shakespeare nella traduzione storica di Carlo Rusconi, digitalizzato da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["DUCA ORSINO", "CURIO", "VALENTINO", "MALVOLIO", "VIOLA", "OLIVIA", "SEBASTIANO", "ANTONIO", "SIR TOBIA", "SIR ANDREA", "MARIA", "FESTE", "FABIANO", "CAPITANO", "SACERDOTE"], "aliases": {"Duc": "DUCA ORSINO", "Cur": "CURIO", "Val": "VALENTINO", "Mal": "MALVOLIO", "Ces": "VIOLA", "Vio": "VIOLA", "Oli": "OLIVIA", "Seb": "SEBASTIANO", "Ant": "ANTONIO", "Tob": "SIR TOBIA", "And": "SIR ANDREA", "Mar": "MARIA", "Fes": "FESTE", "Fab": "FABIANO"}, "package": "la-dodicesima-notte.stagedesk"},
    {"slug": "otello", "title": "Otello", "source_page": "Otello", "source_pages": [f"Otello/Atto {word}" for word in ["primo", "secondo", "terzo", "quarto", "quinto"]], "source_url": "https://it.wikisource.org/wiki/Otello", "attribution": "testo di William Shakespeare nella traduzione storica di Carlo Rusconi, digitalizzato da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["OTELLO", "JAGO", "RODRIGO", "DESDEMONA", "BRABANZIO", "CASSIO", "DOGE", "EMILIA", "MONTANO", "LODOVICO", "GRATIANO", "BIANCA", "CLARISSA", "ARALDI"], "aliases": {"Otell": "OTELLO", "Jago": "JAGO", "Rodr": "RODRIGO", "Desd": "DESDEMONA", "Brab": "BRABANZIO", "Cass": "CASSIO", "Doge": "DOGE", "Emil": "EMILIA", "Mont": "MONTANO", "Lod": "LODOVICO", "Grat": "GRATIANO", "Bian": "BIANCA"}, "package": "otello.stagedesk"},
    {"slug": "le-nozze-di-figaro", "title": "Le nozze di Figaro", "source_page": "Le nozze di Figaro", "source_pages": [f"Le nozze di Figaro/Atto {act}/Scena {scene}" for act, scenes in [("Primo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava"]), ("Secondo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima", "undicesima", "dodicesima"]), ("Terzo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima", "undicesima", "dodicesima", "tredicesima", "quattordicesima"]), ("Quarto", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima", "undicesima", "dodicesima"])] for scene in scenes], "source_url": "https://it.wikisource.org/wiki/Le_nozze_di_Figaro", "attribution": "libretto di Lorenzo Da Ponte per la musica di Wolfgang Amadeus Mozart, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["FIGARO", "SUSANNA", "IL CONTE", "LA CONTESSA", "CHERUBINO", "MARCELLINA", "BARTOLO", "BASILIO", "DON CURZIO", "ANTONIO", "BARBARINA", "DONNE", "CONTADINI"], "aliases": {}, "package": "le-nozze-di-figaro.stagedesk"},
]


def main() -> None:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    for config in WORKS:
        try:
            content = package(config)
            path = PACKAGE_DIR / config["package"]
            path.write_text(content, encoding="utf-8")
            battute = content.count("::battuta{")
            print(f"{config['title']}: {path.name} ({battute} battute, {len(content):,} caratteri)")
        except Exception as error:
            print(f"{config['title']}: IMPORTAZIONE FALLITA: {error}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Importazione fallita: {error}", file=sys.stderr)
        raise
