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
from urllib.parse import quote, urlencode, unquote

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
    value = re.sub(r"\[\s*p\.?\s*\d+\s+[^\]]+\]", "", value, flags=re.I)
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
    url = title if title.startswith("http") else f"https://it.wikisource.org/wiki/{quote(title, safe='/') }"
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
    title = unquote(title).replace("_", " ")
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
    root = (
        soup.select_one(".prp-pages-output")
        or soup.select_one(".testi")
        or soup.select_one(".pagetext .mw-parser-output")
        or soup.select_one(".mw-parser-output")
    )
    if not root:
        return []
    lines: list[str] = []
    split_paragraphs = root.find_parent(class_="pagetext") is not None
    # Italian editions on Wikisource use definition lists for speaker/dialogue
    # pairs, while older scanned editions use paragraphs with abbreviated labels.
    if split_paragraphs:
        elements = root.find_all("div", class_="tiInherit", recursive=True) or root.find_all(["p", "dt", "dd"], recursive=True)
    else:
        elements = root.find_all(["p", "dt", "dd"], recursive=True)
    for child in elements:
        separator = "\n" if split_paragraphs and child.name == "p" else " "
        text = child.get_text(separator, strip=True)
        for raw_line in text.splitlines():
            line = clean(raw_line)
            if not line:
                continue
            if child.name == "dt":
                lines.append(f"@@SPEAKER@@ {line}")
            else:
                lines.append(line)
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
        if (
            re.fullmatch(r"(?:N\.\s*)?\d+\s*(?:[-–].*)?", line)
            or re.match(r"^\[?\s*p\.?\s*\d+\b", line, re.I)
            or line.lower() in {"[p.", "]", "modifica", "càgna"}
            or line.lower().startswith(("informazioni sulla fonte", "chesta paggena nun è stata leggiuta"))
        ):
            continue
        speaker: str | None = None
        # Some scanned editions put the speaker on its own line, without a
        # trailing full stop. Resolve exact known labels before parsing the
        # traditional `SPEAKER. text` form.
        exact_speaker = resolve_speaker(line, aliases, known)
        if exact_speaker and (line.upper() == exact_speaker.upper() or any(normalize_label(line).upper() == normalize_label(alias).upper() for alias in aliases)):
            speaker = exact_speaker
        if "@@SPEAKER@@" in raw:
            speaker = resolve_speaker(line, aliases, known)
        elif not speaker:
            match = re.match(r"^(.{1,55}?)\s*\.\s+(.*)$", line)
            if match:
                speaker = resolve_speaker(match.group(1), aliases, known)
                if speaker:
                    line = match.group(2).strip()
            elif re.match(r"^[A-ZÀ-Ý][A-ZÀ-Ý '\-]{1,45}\s*\.\s*$", line):
                speaker = resolve_speaker(line, aliases, known)
                line = ""
        if speaker:
            if config.get("strict_characters") and speaker not in known:
                speaker = None
            if not speaker:
                flush()
                continue
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
    seen_scene_heading = False
    for line in lines:
        match = re.match(r"^SCENA\s+(.+?)\.?$", line, re.I)
        if match:
            # Act pages contain a title, the act heading and often a cast
            # preamble before the first scene heading. That material must not
            # become an artificial Scene 1.
            if seen_scene_heading and current:
                scenes.append((current_number, current))
            seen_scene_heading = True
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
        if seen_scene_heading:
            current.append(line)
    if seen_scene_heading and current:
        scenes.append((current_number, current))
    return scenes


def source_scenes(config: dict) -> list[tuple[int, int, str, list[tuple[str, str]], list[str]]]:
    if config.get("embedded_acts"):
        return embedded_source_scenes(config)
    if config.get("single_section"):
        lines = [line for line in page_lines(config["single_section"]) if line]
        blocks, directions = extract_dialogue(lines, config)
        return [(1, 1, "Scena 1", blocks, directions[:8])] if blocks else []
    pages = config.get("source_pages") or linked_pages(config["source_page"])
    content_pages = [
        page for page in pages
        if re.search(r"/Atto(?:\s+|_)+(?:Primo|Secondo|Terzo|Quarto|Quinto|V|IV|III|II|I)(?:/Scena(?:\s+|_)+.+)?$", unquote(page), re.I)
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


def embedded_source_scenes(config: dict) -> list[tuple[int, int, str, list[tuple[str, str]], list[str]]]:
    """Parse a single Wikisource page containing its acts and scenes inline."""
    lines: list[str] = []
    for page in config.get("combined_pages", []):
        lines.extend(page_lines(page))
    if not lines:
        lines = page_lines(config["source_page"])
    result: list[tuple[int, int, str, list[tuple[str, str]], list[str]]] = []
    act = 1
    scene = 1
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        blocks, directions = extract_dialogue(current, config)
        if blocks:
            result.append((act, scene, f"Scena {scene}", blocks, directions[:8]))
        current = []

    acts = {"PRIMO": 1, "SECONDO": 2, "TERZO": 3, "QUARTO": 4, "QUINTO": 5, "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
    scenes = {"PRIMA": 1, "SECONDA": 2, "TERZA": 3, "QUARTA": 4, "QUINTA": 5, "SESTA": 6, "SETTIMA": 7, "OTTAVA": 8, "NONA": 9, "DECIMA": 10, "UNDICESIMA": 11, "DODICESIMA": 12}
    for line in lines:
        act_match = re.match(r"^ATTO\s+(.+?)\.?$", line, re.I)
        if act_match:
            flush()
            act = acts.get(act_match.group(1).strip().upper(), act)
            scene = 1
            continue
        scene_match = re.match(r"^SCENA\s+(.+?)\.?$", line, re.I)
        if scene_match:
            flush()
            scene = scenes.get(scene_match.group(1).strip().upper(), scene)
            continue
        current.append(line)
    flush()
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
    {"slug": "sogno-di-una-notte-d-estate", "title": "Il sogno di una notte d'estate", "source_page": "Il Sogno di una notte d'estate", "source_pages": [f"Il Sogno di una notte d'estate/Atto {word}" for word in ["primo", "secondo", "terzo", "quarto", "quinto"]], "source_url": "https://it.wikisource.org/wiki/Il_Sogno_di_una_notte_d%27estate", "attribution": "testo di William Shakespeare nella traduzione storica di Carlo Rusconi, digitalizzato da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "strict_characters": True, "characters": ["TESEO", "IPPOLITA", "FILOSTRATO", "EGEI", "ERMIA", "LISANDRO", "DEMETRIO", "ELENA", "OBERONE", "TITANIA", "PUCK", "FATA 1", "FATA 2", "FATA 3", "FATA 4", "FONDO", "QUINCE", "FLAUTO", "STARVELING", "SNOUT", "SNUG", "PIRAMO", "TISBE", "MURO", "CHIARO DI LUNA", "LEONE", "PROLOGO", "TUTTI"], "aliases": {"Tes": "TESEO", "Teseo": "TESEO", "Ip": "IPPOLITA", "Ipolita": "IPPOLITA", "Fil": "FILOSTRATO", "Filostrato": "FILOSTRATO", "Eg": "EGEI", "Egeo": "EGEI", "Er": "ERMIA", "Ermia": "ERMIA", "Lis": "LISANDRO", "Lisandro": "LISANDRO", "Dem": "DEMETRIO", "Demetrio": "DEMETRIO", "El": "ELENA", "Elena": "ELENA", "Ob": "OBERONE", "Oberone": "OBERONE", "Tit": "TITANIA", "Titania": "TITANIA", "Puc": "PUCK", "Puck": "PUCK", "Bot": "FONDO", "Bott": "FONDO", "Bottom": "FONDO", "Fondo": "FONDO", "Quin": "QUINCE", "Quinz": "QUINCE", "Quince": "QUINCE", "Quinzio": "QUINCE", "Flu": "FLAUTO", "Flut": "FLAUTO", "Flauto": "FLAUTO", "Star": "STARVELING", "Starveling": "STARVELING", "Snout": "SNOUT", "Snug": "SNUG", "Fat": "FATA 1", "1ª Fat": "FATA 1", "2ª Fat": "FATA 2", "3ª Fat": "FATA 3", "4ª Fat": "FATA 4", "Pir": "PIRAMO", "Piramo": "PIRAMO", "Tis": "TISBE", "Tisbe": "TISBE", "Muro": "MURO", "Il muro": "MURO", "Luna": "CHIARO DI LUNA", "Leon": "LEONE", "Il Leone": "LEONE", "Prol": "PROLOGO", "Tutti": "TUTTI"}, "package": "sogno-di-una-notte-d-estate.stagedesk"},
    {"slug": "la-dodicesima-notte", "title": "La dodicesima notte", "source_page": "La dodicesima notte o quel che vorrete", "source_pages": [f"La dodicesima notte o quel che vorrete/Atto {word}" for word in ["primo", "secondo", "terzo", "quarto", "quinto"]], "source_url": "https://it.wikisource.org/wiki/La_dodicesima_notte_o_quel_che_vorrete", "attribution": "testo di William Shakespeare nella traduzione storica di Carlo Rusconi, digitalizzato da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["DUCA ORSINO", "CURIO", "VALENTINO", "MALVOLIO", "VIOLA", "OLIVIA", "SEBASTIANO", "ANTONIO", "SIR TOBIA", "SIR ANDREA", "MARIA", "FESTE", "FABIANO", "CAPITANO", "SACERDOTE"], "aliases": {"Duc": "DUCA ORSINO", "Cur": "CURIO", "Val": "VALENTINO", "Mal": "MALVOLIO", "Ces": "VIOLA", "Vio": "VIOLA", "Oli": "OLIVIA", "Seb": "SEBASTIANO", "Ant": "ANTONIO", "Tob": "SIR TOBIA", "And": "SIR ANDREA", "Mar": "MARIA", "Fes": "FESTE", "Fab": "FABIANO"}, "package": "la-dodicesima-notte.stagedesk"},
    {"slug": "otello", "title": "Otello", "source_page": "Otello", "source_pages": [f"Otello/Atto {word}" for word in ["primo", "secondo", "terzo", "quarto", "quinto"]], "source_url": "https://it.wikisource.org/wiki/Otello", "attribution": "testo di William Shakespeare nella traduzione storica di Carlo Rusconi, digitalizzato da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["OTELLO", "JAGO", "RODRIGO", "DESDEMONA", "BRABANZIO", "CASSIO", "DOGE", "EMILIA", "MONTANO", "LODOVICO", "GRATIANO", "BIANCA", "CLARISSA", "ARALDI"], "aliases": {"Otell": "OTELLO", "Jago": "JAGO", "Rodr": "RODRIGO", "Desd": "DESDEMONA", "Brab": "BRABANZIO", "Cass": "CASSIO", "Doge": "DOGE", "Emil": "EMILIA", "Mont": "MONTANO", "Lod": "LODOVICO", "Grat": "GRATIANO", "Bian": "BIANCA"}, "package": "otello.stagedesk"},
    {"slug": "le-nozze-di-figaro", "title": "Le nozze di Figaro", "source_page": "Le nozze di Figaro", "source_pages": [f"Le nozze di Figaro/Atto {act}/Scena {scene}" for act, scenes in [("Primo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava"]), ("Secondo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima", "undicesima", "dodicesima"]), ("Terzo", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima", "undicesima", "dodicesima", "tredicesima", "quattordicesima"]), ("Quarto", ["prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima", "ottava", "nona", "decima", "undicesima", "dodicesima"])] for scene in scenes], "source_url": "https://it.wikisource.org/wiki/Le_nozze_di_Figaro", "attribution": "libretto di Lorenzo Da Ponte per la musica di Wolfgang Amadeus Mozart, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["FIGARO", "SUSANNA", "IL CONTE", "LA CONTESSA", "CHERUBINO", "MARCELLINA", "BARTOLO", "BASILIO", "DON CURZIO", "ANTONIO", "BARBARINA", "DONNE", "CONTADINI"], "aliases": {}, "package": "le-nozze-di-figaro.stagedesk"},
    {"slug": "il-berretto-a-sonagli", "title": "Il berretto a sonagli", "source_page": "Il berretto a sonagli", "source_pages": ["Il berretto a sonagli/Atto I", "Il berretto a sonagli/Atto II"], "source_url": "https://it.wikisource.org/wiki/Il_berretto_a_sonagli", "strict_characters": True, "attribution": "testo di Luigi Pirandello, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["BEATRICE", "FANA", "LA SARACENA", "CIAMPA", "FIFÌ", "ASSUNTA", "SPANÒ", "PINÒ", "IL DELEGATO", "DON LO GIUECO", "DON FIFÌ"], "aliases": {"La saracena": "LA SARACENA", "Ciampa": "CIAMPA", "Fifì": "FIFÌ", "Fifi": "FIFÌ", "Spanò": "SPANÒ", "Pino": "PINÒ", "Pinò": "PINÒ", "Don Fifì": "DON FIFÌ", "Signor delegato": "IL DELEGATO", "Delegato": "IL DELEGATO"}, "package": "il-berretto-a-sonagli.stagedesk"},
    {"slug": "enrico-iv", "title": "Enrico IV", "source_page": "Enrico IV (1965)", "source_pages": ["Enrico IV (1965)/Atto I", "Enrico IV (1965)/Atto II", "Enrico IV (1965)/Atto III"], "source_url": "https://it.wikisource.org/wiki/Enrico_IV_%281965%29", "strict_characters": True, "attribution": "testo di Luigi Pirandello, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["ENRICO IV", "MATILDE SPINA", "BELCREDI", "DOTTOR GENONI", "LANDOLFO", "ORDULFO", "ARIALDO", "FRIDA", "CARLO DI NOLLI", "TITO BELCREDI", "BERTOLDO", "FINO", "PRIMO VALLETTO", "SECONDO VALLETTO", "DUE SERVI"], "aliases": {"Enrico": "ENRICO IV", "Enrico IV": "ENRICO IV", "Matilde": "MATILDE SPINA", "Dottore": "DOTTOR GENONI", "Dottor Genoni": "DOTTOR GENONI", "Carlo": "CARLO DI NOLLI", "Primo valletto": "PRIMO VALLETTO", "Secondo valletto": "SECONDO VALLETTO", "Uno dei valletti": "PRIMO VALLETTO"}, "package": "enrico-iv.stagedesk"},
    {"slug": "sei-personaggi-in-cerca-dautore", "title": "Sei personaggi in cerca d'autore", "source_page": "Sei personaggi in cerca d'autore (1965)", "single_section": "https://it.wikisource.org/wiki/Sei_personaggi_in_cerca_d%27autore_%281965%29/Atto_unico", "source_url": "https://it.wikisource.org/wiki/Sei_personaggi_in_cerca_d%27autore_%281965%29/Atto_unico", "strict_characters": True, "attribution": "testo di Luigi Pirandello, edizione storica digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["IL CAPOCOMICO", "IL DIRETTORE DI SCENA", "IL MACCHINISTA", "IL SUGGERITORE", "IL PRIMO ATTORE", "LA PRIMA ATTRICE", "L'ATTORE GIOVANE", "L'ATTRICE GIOVANE", "IL PADRE", "LA MADRE", "LA FIGLIASTRA", "IL FIGLIO", "LA BAMBINA", "IL GIOVINETTO", "MADAMA PACE", "ATTORI", "ATTRICI"], "aliases": {"Il capocomico": "IL CAPOCOMICO", "Capocomico": "IL CAPOCOMICO", "Il direttore di scena": "IL DIRETTORE DI SCENA", "Direttore": "IL DIRETTORE DI SCENA", "Il macchinista": "IL MACCHINISTA", "Il suggeritore": "IL SUGGERITORE", "Il primo attore": "IL PRIMO ATTORE", "La prima attrice": "LA PRIMA ATTRICE", "L’attore giovane": "L'ATTORE GIOVANE", "L'attor giovane": "L'ATTORE GIOVANE", "L’attrice giovane": "L'ATTRICE GIOVANE", "L'attrice giovane": "L'ATTRICE GIOVANE", "Il padre": "IL PADRE", "La madre": "LA MADRE", "La figliastra": "LA FIGLIASTRA", "Il figlio": "IL FIGLIO", "La bambina": "LA BAMBINA", "Il giovinotto": "IL GIOVINETTO"}, "package": "sei-personaggi-in-cerca-dautore.stagedesk"},
    {"slug": "miseria-e-nobilta", "title": "Miseria e nobiltà", "source_page": "https://nap.wikisource.org/wiki/Miseria_e_nobilt%C3%A0", "combined_pages": [f"https://nap.wikisource.org/wiki/Paggena:Miseria_e_nobilt%C3%A0.djvu/{page}" for page in range(6, 113)], "embedded_acts": True, "strict_characters": True, "source_url": "https://nap.wikisource.org/wiki/Miseria_e_nobilt%C3%A0", "attribution": "testo di Eduardo Scarpetta, edizione storica napoletana digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["GAETANO", "GEMMA", "LUIGINO", "MARCHESE OTTAVIO FAVETTI", "EUGENIO", "PASQUALE", "FELICE", "CONCETTA", "LUISELLA", "BETTINA", "PUPELLA", "GIOACCHINO CASTIELLO", "VICIENZO", "BIASE", "PEPPENIELLO"], "aliases": {"Gaet": "GAETANO", "Gaet.": "GAETANO", "D. Gaetano": "GAETANO", "Gemma": "GEMMA", "Luig": "LUIGINO", "Luig.": "LUIGINO", "Luis": "LUISELLA", "Luis.": "LUISELLA", "Fel": "FELICE", "Fel.": "FELICE", "Pasc": "PASQUALE", "Pasc.": "PASQUALE", "Conc": "CONCETTA", "Conc.": "CONCETTA", "Bett": "BETTINA", "Bett.": "BETTINA", "Pup": "PUPELLA", "Pup.": "PUPELLA", "Eug": "EUGENIO", "Eug.": "EUGENIO", "Ott": "MARCHESE OTTAVIO FAVETTI", "Ott.": "MARCHESE OTTAVIO FAVETTI", "Ottavio": "MARCHESE OTTAVIO FAVETTI", "Giacc": "GIOACCHINO CASTIELLO", "Vicien": "VICIENZO", "Vicien.": "VICIENZO", "Pepp": "PEPPENIELLO", "Pepp.": "PEPPENIELLO"}, "package": "miseria-e-nobilta.stagedesk"},
    {"slug": "e-buscia-o-e-verita", "title": "È buscia o è verità", "source_page": "È buscia o è verità", "source_pages": ["https://nap.wikisource.org/wiki/%C3%88_buscia_o_%C3%A8_verit%C3%A0/Atto_I", "https://nap.wikisource.org/wiki/%C3%88_buscia_o_%C3%A8_verit%C3%A0/Atto_II"], "source_url": "https://nap.wikisource.org/wiki/Ennece:%C3%88_buscia_o_%C3%A8_verit%C3%A0.djvu", "strict_characters": True, "attribution": "testo di Eduardo Scarpetta, edizione storica napoletana digitalizzata da Wikisource, fonte disponibile con licenza CC BY-SA 3.0 e GFDL", "characters": ["GIULIO", "ASDRUBALE", "LUCIELLA", "PULCINELLA", "FELICE", "ROSINA", "DONNA BETTINA", "DONNA CONCETTA", "DON PASQUALE", "BARTOLOMEO", "AMALIA", "FELICIELLO"], "aliases": {"Giul": "GIULIO", "Giul.": "GIULIO", "Asd": "ASDRUBALE", "Asd.": "ASDRUBALE", "Luc": "LUCIELLA", "Luc.": "LUCIELLA", "Pul": "PULCINELLA", "Pul.": "PULCINELLA", "Fel": "FELICE", "Fel.": "FELICE", "Ros": "ROSINA", "Ros.": "ROSINA", "Bett": "DONNA BETTINA", "Conc": "DONNA CONCETTA", "Pasc": "DON PASQUALE", "D. Bartolomeo": "BARTOLOMEO", "Amalia": "AMALIA", "Feliciello": "FELICIELLO"}, "package": "e-buscia-o-e-verita.stagedesk"},
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
