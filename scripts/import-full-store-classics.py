#!/usr/bin/env python3
"""Convert public-domain source editions into StageDesk packages.

The source texts are kept outside git (see FULL_SOURCE_DIR).  This importer
preserves the source dialogue and stage directions while adding original,
scene-level StageDesk notes for rehearsal work.
"""

from __future__ import annotations

import html
import os
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(os.environ.get("FULL_SOURCE_DIR", ".store-assets/source-cache"))
if not SOURCE_DIR.is_absolute():
    SOURCE_DIR = ROOT / SOURCE_DIR
PACKAGE_DIR = Path(os.environ.get("STORE_PACKAGE_DIR", ".store-assets/copioni"))
if not PACKAGE_DIR.is_absolute():
    PACKAGE_DIR = ROOT / PACKAGE_DIR


ROMAN_OR_ITALIAN_SCENE = (
    r"PRIMA|SECONDA|TERZA|QUARTA|QUINTA|SESTA|SETTIMA|OTTAVA|NONA|DECIMA|"
    r"UNDICESIMA|DODICESIMA|TREDICESIMA|QUATTORDICESIMA|QUINDICESIMA|"
    r"SEDICESIMA|DICIASSETTESIMA|DICIOTTESIMA|DICIANNOVESIMA|VENTESIMA|"
    r"VENTUNESIMA|VENTIDUESIMA|ULTIMA|I{1,3}|IV|V|VI|VII|VIII|IX|X|XI|XII|"
    r"XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX|XXI|XXII"
)
SCENE_RE = re.compile(
    rf"^\s*SCENA\s+(?P<number>{ROMAN_OR_ITALIAN_SCENE})(?:\s*[.\-–—:]\s*(?P<title>.*?))?\s*[.]?\s*$",
    re.IGNORECASE,
)
ACT_RE = re.compile(
    r"^\s*ATTO\s+(?P<number>PRIMO|SECONDO|TERZO|QUARTO|QUINTO|SOLO|I|II|III|IV|V)\s*[.]?\s*$",
    re.IGNORECASE,
)


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def attr(value: str) -> str:
    return html.escape(str(value), quote=True)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode()
    value = value.upper().replace("’", "'")
    value = re.sub(r"[.(),:;!?\-—–]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def repair_historical_ocr(line: str) -> str:
    """Repair frequent long-s OCR substitutions in the 1740 Molière scan."""
    replacements = {
        "voftro": "vostro", "voftra": "vostra", "quefta": "questa", "quefto": "questo",
        "queft\u2019": "quest\u2019", "efser": "esser", "fempre": "sempre", "fopra": "sopra",
        "fotto": "sotto", "fenza": "senza", "fuo": "suo", "fua": "sua", "fubito": "subito",
        "fegreto": "segreto", "ftato": "stato", "ftessa": "stessa", "pafso": "passo",
        "pafsione": "passione", "teftamento": "testamento", "bafteranno": "basteranno",
        "bafter": "baster", "fignora": "signora", "furbatu": "furbata",
    }
    for source, target in replacements.items():
        line = re.sub(rf"(?i)\b{re.escape(source)}\b", target, line)
    return line


def clean_lines(text: str, strip_numbered_notes: bool = False, repair_ocr: bool = False) -> list[str]:
    lines: list[str] = []
    skipping_numbered_note = False
    for raw in text.replace("\r", "").replace("\f", "\n").splitlines():
        line = raw.strip()
        line = re.sub(r"\s+", " ", line)
        if repair_ocr:
            line = repair_historical_ocr(line)
        if not line or re.fullmatch(r"\d+", line):
            skipping_numbered_note = False
            continue
        # Remove navigation and page-layer fragments present in scraped
        # editions (for example Wikisource's [p. ... modifica] markers).
        if (
            re.fullmatch(r"\[?p\.?\]?", line, re.IGNORECASE)
            or line.lower() in {"modifica", "◄", "►", "[", "]"}
            or line.startswith("<dc:")
            or line.startswith("</dc:")
            or re.fullmatch(r"<[^>]+>", line)
        ):
            continue
        if strip_numbered_notes:
            # Liber Liber places numbered translator notes in separate
            # paragraphs. Keep the play text, discard the note paragraph.
            if re.match(r"^\d{1,2}\s", line):
                skipping_numbered_note = True
                continue
            if skipping_numbered_note:
                continue
        if re.fullmatch(r"(?:nota|note)\s*\d+", line, re.IGNORECASE):
            continue
        if strip_numbered_notes:
            # Remove inline footnote markers left by the PDF text layer,
            # while preserving the surrounding sentence.
            line = re.sub(r"\s+[1-9]\d?\s*$", "", line)
            line = re.sub(r"(?<=[A-Za-zÀ-ÿ])(?:[1-9]\d?)(?=(?:\s|[.,;:!?…]))", "", line)
            line = re.sub(r"(?<=[.,;:!?…”»)\]])(?:[1-9]\d?)(?=\s|[.,;:!?…]|$)", "", line)
            line = re.sub(r"(?<=[,.;:!?…])\s+[1-9]\d?\s+(?=[A-Za-zÀ-ÿ])", " ", line)
        lines.append(line)
    return lines


def source_lines(work: dict) -> list[str]:
    result: list[str] = []
    for filename in work["source_files"]:
        file_lines = clean_lines(
            (SOURCE_DIR / filename).read_text(encoding="utf-8", errors="ignore"),
            strip_numbered_notes=work.get("strip_numbered_notes", False),
            repair_ocr=work.get("repair_ocr", False),
        )
        if work.get("trim_wikisource_act_files"):
            first_act = next((index for index, line in enumerate(file_lines) if ACT_RE.match(line)), None)
            if first_act is not None:
                file_lines = file_lines[first_act:]
        result.extend(file_lines)
    if work.get("clean_wikisource_markup"):
        cleaned: list[str] = []
        for line in result:
            # Wikisource exports the page footer and TeX alternatives as
            # ordinary paragraphs. They must never enter a dialogue block.
            if "\\displaystyle" in line:
                continue
            if (
                line.startswith("Estratto da")
                or line.startswith("https://it.wikisource.org/")
                or line in {"\"", "fine", "—", "Informazioni sulla fonte del testo"}
            ):
                continue
            cleaned.append(line)
        result = cleaned
        source_text = "\n".join(result)
        source_text = re.sub(
            r"Vieni, vieni, carin\s+o\s+a\s*,",
            "Vieni, vieni, carino/a,",
            source_text,
            flags=re.IGNORECASE,
        )
        source_text = re.sub(r"\bChet\s+a\s+o\s+chet\s+a\s+o\s+", "Cheta, cheta, o ", source_text, flags=re.IGNORECASE)
        source_text = re.sub(
            r"Tutti,\s*fuorchè\s*\nGio\.\s*\ne\s*\nLep\.\s*\n",
            "Tutti, fuorchè Gio. e Lep.\n",
            source_text,
            flags=re.IGNORECASE,
        )
        result = source_text.splitlines()
    return result


def find_actual_acts(lines: list[str], expected: int) -> list[tuple[int, str]]:
    matches = [
        (index, match.group("number"), line)
        for index, line in enumerate(lines)
        if (match := ACT_RE.match(line))
    ]
    # Some public-domain editions concatenate the source text with a table of
    # contents or navigation headings. Prefer the all-caps headings used by
    # the actual text when enough of them are available; otherwise retain the
    # historical last-N fallback used by the other editions.
    strong_matches = [
        (index, number, line)
        for index, number, line in matches
        if line.strip() == line.strip().upper()
    ]
    selected = strong_matches if len(strong_matches) >= expected else matches
    return [(index, number) for index, number, _ in selected[-expected:]]


def heading_number(value: str) -> str:
    return value.upper().replace("PRIMO", "1").replace("SECONDO", "2").replace("TERZO", "3").replace("QUARTO", "4").replace("QUINTO", "5").replace("SOLO", "1")


def speaker_aliases(work: dict) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for character in work["characters"]:
        aliases[normalize(character)] = character
    for canonical, values in work.get("aliases", {}).items():
        aliases[normalize(canonical)] = canonical
        for value in values:
            aliases[normalize(value)] = canonical
    return aliases


def _looks_like_stage_direction(text: str) -> bool:
    value = normalize(text)
    return value.startswith((
        "ENTRA ", "ENTRANO ", "ESCE ", "ESCENO ", "RIENTRA ", "RIENTRANO ",
        "PARTE ", "PARTONO ", "SCUOPRE ", "SCOPRE ", "SI RITIRA ",
        "SI NASCONDE ", "CON ", "POI ", "SEGUITO ", "SEGUONO ",
        "AL ", "IN UN ", "SPAVENTATO ",
    )) or value.endswith((" PARTE", " PARTONO"))


def detect_speaker(line: str, aliases: dict[str, str], bare_labels: set[str] | None = None) -> str | None:
    # Stage directions and location descriptions are never speaker labels.
    if line.startswith(("(", "[", "Entr", "Esce", "Rient", "Entra", "SCENA", "Scena")):
        return None
    candidate = re.sub(r"\s+", " ", line.strip())
    bare_labels = bare_labels or set()

    # A line containing several abbreviated voices is an ensemble line. Keep
    # it as one block instead of interpreting the first abbreviation as the
    # speaker and the remaining voices as dialogue text.
    direct_group = aliases.get(normalize(candidate))
    if direct_group and (normalize(candidate) in bare_labels or direct_group == "TUTTI"):
        return direct_group

    # Prefer an explicit speaker delimiter. A period is included because the
    # historical editions use labels such as "Gio." and "NORA.".
    label_match = re.match(r"^(.{1,90}?)\s*(?:—|–|-|:|\.)\s*", candidate)
    if label_match:
        label = label_match.group(1).strip()
        remainder = candidate[label_match.end():].strip()
        # In old editions a stage direction can mention another character as
        # part of the sentence, for example "Lep., e finge...". The comma or
        # conjunction means this is not a new speaker label.
        if remainder.startswith(",") or re.match(r"^(?:e|ed)\b", remainder, re.IGNORECASE):
            return None
        if _looks_like_stage_direction(remainder):
            return None
        direct = aliases.get(normalize(label))
        if direct:
            return direct

    # A bare label is valid only when it is explicitly supplied by the source
    # edition. This prevents cast lists such as "Leporello, poi Don Giovanni"
    # from becoming empty dialogue blocks.
    had_terminal_punctuation = bool(re.search(r"[.?!:;—–-]$", candidate))
    candidate = re.sub(r"\s*(?:—|–|-|:|\.)$", "", candidate).strip()
    direct = aliases.get(normalize(candidate))
    if direct and (normalize(candidate) in bare_labels or candidate == candidate.upper() or had_terminal_punctuation):
        return direct
    return None


def scene_heading(line: str) -> re.Match[str] | None:
    match = SCENE_RE.match(line)
    if match:
        return match
    # The Molière scan has several OCR variants such as "SCENA.I." and
    # "SCENA TIT". They are still unambiguous short scene headings.
    compact_line = re.sub(r"\s+", " ", line.strip())
    if re.match(r"^(?:I[Ff]|[Ii]|TY|ty)?\s*SCENA(?:[ .,:]|$)", compact_line) and len(compact_line) <= 35:
        return re.match(r"^(?P<prefix>.*)$", compact_line)
    return None


def compact(text: str, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def clean_dialogue(text: str) -> str:
    """Remove OCR punctuation leaked from a separate line before dialogue."""
    text = re.sub(r"^[ \t]*[!?:;,\)\]]+(?=\s|[A-ZÀ-Ýa-zà-ÿ])", "", text).strip()
    return text


def scene_notes(scene_text: list[str], speakers: list[str], title: str, scene_id: str) -> list[str]:
    directions = [
        line for line in scene_text
        if (line.startswith(("(", "[")) or line.lower().startswith(("entr", "esce", "rient")))
        and line.strip("()[] ").strip()
    ]
    location = next((line for line in scene_text if not detect_speaker(line, {})), "La scena segue l'ambientazione indicata nell'edizione di riferimento.")
    position = compact(location if location else "La scena segue l'ambientazione indicata nell'edizione di riferimento.")
    movement = compact(" ".join(directions[:3])) if directions else "Seguire le entrate, le uscite e le azioni indicate nelle didascalie originali, mantenendo leggibili le relazioni nello spazio."
    tone = f"La scena «{title}» conserva il ritmo e il tono dell'edizione di riferimento; le pause devono lasciare emergere il conflitto tra i personaggi."
    cast = ", ".join(dict.fromkeys(speakers)) or "Personaggi indicati nell'edizione di riferimento."
    return [
        f'::regia{{id="note-{scene_id}-personaggi" type="characters" color="blue" title="Personaggi in scena" sceneId="{scene_id}" anchorId="note-{scene_id}-personaggi"}}\n{cast}\n::',
        f'::regia{{id="note-{scene_id}-posizione" type="position" color="blue" title="Posizione" sceneId="{scene_id}" anchorId="note-{scene_id}-posizione"}}\n{position}\n::',
        f'::regia{{id="note-{scene_id}-movimento" type="movement" color="green" title="Movimento" sceneId="{scene_id}" anchorId="note-{scene_id}-movimento"}}\n{movement}\n::',
        f'::regia{{id="note-{scene_id}-tono" type="tone" color="purple" title="Tono" sceneId="{scene_id}" anchorId="note-{scene_id}-tono"}}\n{tone}\n::',
    ]


def parse_scene(scene_text: list[str], aliases: dict[str, str], fallback_character: str, bare_labels: set[str] | None = None) -> tuple[list[tuple[str, str]], list[str]]:
    blocks: list[tuple[str, str]] = []
    preface: list[str] = []
    current_speaker: str | None = None
    current: list[str] = []
    bare_labels = bare_labels or set()
    for index, line in enumerate(scene_text):
        speaker = detect_speaker(line, aliases, bare_labels)
        # A bare source label followed by punctuation is usually part of the
        # cast description at the top of a scene, not a spoken line.
        is_bare_source_label = normalize(line) in bare_labels or (
            line == line.upper() and not re.search(r"[—–:.;!?]", line)
        )
        if speaker and is_bare_source_label:
            next_line = scene_text[index + 1].strip() if index + 1 < len(scene_text) else ""
            if line.rstrip().endswith(",") or next_line.startswith((",", ".", ";", ")", "e ", "ed ", "a ", "di ", "con ", "entra", "esce", "rientra", "spavent")):
                speaker = None
        if speaker:
            if current_speaker and current:
                blocks.append((current_speaker, " ".join(current).strip()))
            current_speaker = speaker
            current = []
            continue
        if current_speaker:
            current.append(line)
        else:
            preface.append(line)
    if current_speaker and current:
        blocks.append((current_speaker, " ".join(current).strip()))
    if not blocks:
        text = " ".join(scene_text).strip()
        if text:
            blocks.append((fallback_character, text))
    return [(speaker, clean_dialogue(text)) for speaker, text in blocks if text], preface


def parse_work(work: dict) -> str:
    lines = source_lines(work)
    acts = find_actual_acts(lines, work["act_count"])
    if not acts:
        raise RuntimeError(f"Nessun atto riconosciuto per {work['title']}")
    aliases = speaker_aliases(work)
    bare_labels = {normalize(value) for value in work.get("bare_labels", [])}
    characters = list(work["characters"])
    parsed_scenes: list[tuple[int, int, str, list[str], list[tuple[str, str]], list[str]]] = []
    for act_index, (act_start, act_number) in enumerate(acts, start=1):
        act_end = acts[act_index][0] if act_index < len(acts) else len(lines)
        act_lines = lines[act_start + 1 : act_end]
        scene_matches = [(index, match) for index, line in enumerate(act_lines) if (match := scene_heading(line))]
        if not scene_matches:
            scene_matches = [(0, None)]
        for scene_index, (scene_start, scene_match) in enumerate(scene_matches, start=1):
            scene_end = scene_matches[scene_index][0] if scene_index < len(scene_matches) else len(act_lines)
            raw_scene = act_lines[scene_start + 1 : scene_end] if scene_match else act_lines
            scene_title = ""
            if scene_match and "title" in scene_match.groupdict():
                scene_title = (scene_match.group("title") or "").strip()
            if not scene_title:
                scene_title = f"Scena {scene_index}"
            scene_id = f"atto-{act_index}-scena-{scene_index}"
            blocks, preface = parse_scene(raw_scene, aliases, characters[0], bare_labels)
            speakers = [speaker for speaker, _ in blocks]
            parsed_scenes.append((act_index, scene_index, scene_title, raw_scene, blocks, preface))
            for speaker, _ in blocks:
                if speaker not in characters:
                    characters.append(speaker)
    output = ["| Personaggio | Interprete | Presenza | Note |", "| --- | --- | --- | --- |"]
    for character in characters:
        output.append(f"| {character} | Da assegnare | In scena | Personaggio dell'edizione integrale di riferimento. |")
    output.extend([
        "",
        f"# {work['title']}",
        "",
        f"> **EDIZIONE INTEGRALE**: {work['attribution']}.",
        "> Le note di regia StageDesk sono originali e aggiunte al testo per il lavoro in prova; il testo e le didascalie seguono la fonte indicata.",
        "",
    ])
    dialogue_count = 0
    for act_index in range(1, len(acts) + 1):
        output.extend([f"## Atto {act_index}", ""])
        for parsed_act, scene_index, scene_title, raw_scene, blocks, preface in parsed_scenes:
            if parsed_act != act_index:
                continue
            scene_id = f"atto-{act_index}-scena-{scene_index}"
            output.extend([f"### Scena {scene_index}" + (f" — {scene_title}" if scene_title and not scene_title.lower().startswith("scena ") else ""), ""])
            output.extend(scene_notes(preface + raw_scene, [speaker for speaker, _ in blocks], scene_title, scene_id))
            output.append("")
            for speaker, text in blocks:
                dialogue_count += 1
                output.extend([
                    f'::battuta{{id="battuta-{scene_id}-{dialogue_count}" characterId="{slugify(speaker)}" character="{attr(speaker)}" sceneId="{scene_id}"}}',
                    text,
                    "::",
                    "",
                ])
    # Keep the table synchronized with speakers discovered in the source.
    # Dynamic speakers are rare in the public editions, but are retained in the
    # dialogue objects even when the source uses a collective label.
    output.append(f"> **Fonte**: {work['source_url']} (consultata per l'edizione integrale).")
    output.append("")
    return "\n".join(output)


WORKS = [
    {
        "slug": "il-malato-immaginario-riscrittura",
        "title": "Il malato immaginario",
        "act_count": 3,
        "source_files": ["malato-atto1.txt", "malato-atto2.txt", "malato-atto3.txt"],
        "source_url": "https://digital.ub.uni-paderborn.de/ihd/content/structure/3393377",
        "attribution": "testo di Molière nella traduzione storica di Niccolò di Castelli, tratta dalla scansione dell'edizione settecentesca conservata dalla Universitätsbibliothek Paderborn",
        "repair_ocr": True,
        "characters": ["ARGAN", "TOINETTE", "ANGELICA", "CLEANTE", "BERALDO", "BELINA", "SIGNOR DIAFOIRUS", "TOMMASO DIAFOIRUS", "DOTTOR PURGONE", "SIGNORA FLEURANT", "NOTAIO"],
        "aliases": {"ARGAN": ["ARGANO", "GANO", "ARGA NO", "ARGAN O", "ARGANG"], "TOINETTE": ["ANTONIETTA", "ANTONIETT", "ANTONI TA", "TONIETTA"], "ANGELICA": ["ANG LICA", "ANGELI A"], "BELINA": ["BELTINA", "BELI", "BE LINA"], "BERALDO": ["RERALDO", "BERAL DO", "BERALD"], "CLEANTE": ["CLEA E", "CLE ANT E"], "SIGNOR DIAFOIRUS": ["DIAFOIRUS", "DIAFORIO", "DIAFORIA", "DIAFORTO", "DIAFORTIO", "DIAFORI0", "DOTTOR DIAFOIRUS"], "TOMMASO DIAFOIRUS": ["TOMMASO", "TOMASO", "TOMASO DIAFORIO", "TOMMASO DIAFORIO"], "DOTTOR PURGONE": ["PURGONE", "PURGON E"], "SIGNORA FLEURANT": ["FLEURANT", "FLORANTE"]},
        "package": "il-malato-immaginario-riscrittura.stagedesk",
    },
    {
        "slug": "il-servitore-di-due-padroni", "title": "Il servitore di due padroni", "act_count": 3,
        "source_files": ["servitore-real.txt"], "source_url": "https://liberliber.it/autori/autori-g/carlo-goldoni/il-servitore-di-due-padroni/",
        "attribution": "testo di Carlo Goldoni, tratto dall'edizione integrale digitale del Progetto Manuzio di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["TRUFFALDINO", "BRIGHELLA", "BEATRICE", "PANTALONE", "CLARICE", "SILVIO", "FLORINDO", "SMERALDINA", "DOTTORE", "CAMERIERE", "FACCHINO", "TUTTI"],
        "aliases": {"DOTTORE": ["DOTT.", "IL DOTTORE"], "TRUFFALDINO": ["TRUFFALDIN"], "SMERALDINA": ["SMERALDINA"]},
        "package": "il-servitore-di-due-padroni.stagedesk",
    },
    {
        "slug": "romeo-e-giulietta", "title": "Romeo e Giulietta", "act_count": 5,
        "source_files": ["romeo-real.txt"], "source_url": "https://liberliber.it/autori/autori-s/william-shakespeare/romeo-e-giulietta/",
        "attribution": "testo di William Shakespeare nella traduzione di Goffredo Raponi, tratto dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["ROMEO", "GIULIETTA", "BENVOLIO", "MERCUZIO", "TEBALDO", "CAPULETI", "MONNA CAPULETI", "MONTECCHI", "MONNA MONTECCHI", "NUTRICE", "FRATE LORENZO", "PARIDE", "PRINCIPE SCALIGERO", "MESSAGGERO", "BALTHASAR", "ABRAMO", "BALDASSARRE", "PIETRO", "CITTADINI", "TUTTI"],
        "aliases": {"PRINCIPE SCALIGERO": ["PRINCIPE"], "NUTRICE": ["NUTRICE", "LA NUTRICE"], "FRATE LORENZO": ["FRATE LORENZO", "LORENZO"], "BALTHASAR": ["BALTASSAR", "BALDASSARRE"], "MONNA CAPULETI": ["MONNA CAPULETI"], "MONNA MONTECCHI": ["MONNA MONTECCHI"], "SANSONE": ["SANSONE"], "GREGORIO": ["GREGORIO"], "ABRAMO": ["ABRAMO"], "BALDASSARRE": ["BALDASSARRE"], "CITTADINI": ["CITTADINI"], "SPEZIALE": ["SPEZIALE"], "PAGGIO": ["PAGGIO", "PAGGETTO"]},
        "package": "romeo-e-giulietta.stagedesk",
    },
    {
        "slug": "amleto", "title": "Amleto", "act_count": 5,
        "source_files": ["amleto-real.txt"], "source_url": "https://liberliber.it/autori/autori-s/william-shakespeare/amleto/",
        "attribution": "testo di William Shakespeare nella traduzione di Goffredo Raponi, tratto dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["AMLETO", "CLAUDIO", "GERTRUDE", "POLONIO", "OFELIA", "LAERTE", "ORAZIO", "SPETTRO", "ROSENCRANTZ", "GUILDENSTERN", "FORTINBRAS", "BERNARDO", "MARCELLO", "FRANCESCO", "OSRICO", "PRIMO BECCHINO", "SECONDO BECCHINO", "MESSAGGERO", "ATTORI", "TUTTI"],
        "aliases": {"FORTINBRAS": ["FORTebraccio", "FORTBRACCIO"], "SPETTRO": ["SPETTRO DEL PADRE DI AMLETO"], "PRIMO BECCHINO": ["PRIMO BECCHINO"], "SECONDO BECCHINO": ["SECONDO BECCHINO"]},
        "package": "amleto.stagedesk",
    },
    {
        "slug": "la-tempesta", "title": "La tempesta", "act_count": 5,
        "source_files": ["tempesta-real.txt"], "source_url": "https://liberliber.it/autori/autori-s/william-shakespeare/la-tempesta/",
        "attribution": "testo di William Shakespeare nella traduzione di Goffredo Raponi, tratto dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["PROSPERO", "MIRANDA", "ARIEL", "CALIBANO", "FERDINANDO", "ALONSO", "ANTONIO", "SEBASTIANO", "GONZALO", "TRINCULO", "STEFANO", "ADRIANO", "FRANCESCO", "CAPITANO", "CAPO NOCCHIERO", "MARINAI", "IRIDE", "CERERE", "GIUNONE", "NINFE", "SPIRITI", "TUTTI"],
        "aliases": {"ARIEL": ["ARIELE"], "SEBASTIANO": ["SEBASTIAN"], "CAPO NOCCHIERO": ["NOSTROMO", "CAPO NOCCHIERO"], "CAPITANO": ["IL CAPITANO DELLA NAVE"]},
        "package": "la-tempesta.stagedesk",
    },
    {
        "slug": "macbeth", "title": "Macbeth", "act_count": 5,
        "source_files": ["macbeth-real.txt"], "source_url": "https://liberliber.it/autori/autori-s/william-shakespeare/macbeth/",
        "attribution": "testo di William Shakespeare nella traduzione di Goffredo Raponi, tratto dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["MACBETH", "LADY MACBETH", "BANCO", "MACDUFF", "MALCOLM", "DUNCANO", "DONALBANO", "ROSS", "LENNOX", "ANGUS", "MENTEITH", "CAITHNESS", "SIWARD", "FIGLIO DI MACDUFF", "LE TRE STREGHE", "PRIMA STREGA", "SECONDA STREGA", "TERZA STREGA", "FLEANCE", "TUTTI"],
        "aliases": {"DUNCANO": ["DUNCAN"], "BANCO": ["BANQUO"], "LE TRE STREGHE": ["TUTTE E TRE"], "PRIMA STREGA": ["1A STREGA", "1 A STREGA"], "SECONDA STREGA": ["2A STREGA", "2 A STREGA"], "TERZA STREGA": ["3A STREGA", "3 A STREGA"]},
        "package": "macbeth.stagedesk",
    },
    {
        "slug": "l-avaro", "title": "L'avaro", "act_count": 1,
        "source_files": ["avaro-real.txt"], "source_url": "https://liberliber.it/autori/autori-g/carlo-goldoni/lavaro/",
        "attribution": "testo di Carlo Goldoni, tratto dall'edizione integrale digitale del Progetto Manuzio di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["DON AMBROGIO", "DONNA EUGENIA", "DON FERNANDO", "CONTE DELL'ISOLA", "CAVALIERE COSTANZO", "CECCHINO", "PROCURATORE"],
        "aliases": {"DON AMBROGIO": ["AMB", "AMB."], "DONNA EUGENIA": ["EUG", "EUG."], "DON FERNANDO": ["FER", "FER."], "CONTE DELL'ISOLA": ["CON", "CON."], "CAVALIERE COSTANZO": ["CAV", "CAV."], "CECCHINO": ["CEC", "CEC."]},
        "package": "l-avaro.stagedesk",
    },
    {
        "slug": "casa-di-bambola", "title": "Casa di bambola", "act_count": 3,
        "source_files": ["casa.txt"], "source_url": "https://liberliber.it/autori/autori-i/henrik-ibsen/casa-di-bambola/",
        "attribution": "testo di Henrik Ibsen nella traduzione autorizzata di Pietro Galletti, edizione Fratelli Treves 1928, tratta dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["NORA", "HELMER", "KROGSTAD", "SIGNORA LINDE", "DOTTOR RANK", "ELENA", "ANNE-MARIE", "IL FACCHINO", "I BAMBINI", "IL MESSO"],
        "aliases": {"HELMER": ["HELM", "HELM."], "SIGNORA LINDE": ["LINDE", "SIGNORA LINDE"], "DOTTOR RANK": ["RANK", "DOTT. RANK"], "IL FACCHINO": ["FACC", "FACC."], "ANNE-MARIE": ["ANNA MARIA", "ANNE MARIE"]},
        "package": "casa-di-bambola.stagedesk",
    },
    {
        "slug": "don-giovanni", "title": "Don Giovanni", "act_count": 2,
        "source_files": ["don1-clean.txt", "don2-clean.txt"], "source_url": "https://it.wikisource.org/wiki/Don_Giovanni",
        "attribution": "libretto di Lorenzo Da Ponte, edizione 1867 digitalizzata da Wikisource, distribuito con licenza CC BY-SA 3.0 e GFDL",
        "characters": ["DON GIOVANNI", "LEPORELLO", "DONNA ANNA", "DON OTTAVIO", "ELVIRA", "MASETTO", "ZERLINA", "IL COMMENDATORE", "CORO", "CONTADINI", "CAVALIERI", "TUTTI"],
        "aliases": {
            "DON GIOVANNI": ["GIO", "GIO.", "GTO."],
            "LEPORELLO": ["LEP", "LEP."],
            "DONNA ANNA": ["ANNA", "D. ANNA", "ANN.", "DONN'ANNA", "DONN’ANNA"],
            "DON OTTAVIO": ["OTT", "OTT."],
            "IL COMMENDATORE": ["COM", "COM.", "COMMENDATORE"],
            "MASETTO": ["MAS", "MAS."],
            "ZERLINA": ["ZER", "ZER."],
            "ELVIRA": ["ELV", "ELV.", "DONN'ELVIRA", "DONN’ELVIRA"],
            "TUTTI": [
                "GIO. E LEP.", "ZER. E MAS.", "AN. OTT.", "OTT. ELV.",
                "ANNA, ELV.", "ANNA, OTT., ELV.", "ANNA, OTT. ELV.",
                "ANNA, OTT. E ELV.", "ANNA, OTTAVIO E ELVIRA", "GIO. E LEP.",
                "ZER. MAS. E LEP.", "TUTTI, FUORCHÈ GIO. E LEP.", "A 2", "TUTTI",
            ],
        },
        "bare_labels": [
            "ANNA", "LEPORELLO", "ELVIRA", "ZERLINA", "MASETTO", "OTTAVIO",
            "DON OTTAVIO", "GIO", "LEP", "OTT", "COM", "MAS", "ZER", "ELV",
            "TUTTI", "CORO", "CONTADINI", "CAVALIERI",
        ],
        "clean_wikisource_markup": True,
        "trim_wikisource_act_files": True,
        "package": "don-giovanni.stagedesk",
    },
    {
        "slug": "la-commedia-degli-equivoci", "title": "La commedia degli equivoci", "act_count": 5,
        "source_files": ["commedia-real.txt"], "source_url": "https://liberliber.it/autori/autori-s/william-shakespeare/la-commedia-degli-equivoci/",
        "attribution": "testo di William Shakespeare nella traduzione di Goffredo Raponi, tratto dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["ANTIFOLI DI SIRACUSA", "ANTIFOLI DI EFESO", "DROMI DI SIRACUSA", "DROMI DI EFESO", "ADRIANA", "LUCIANA", "EMILIA", "ANGELO", "EGEONE", "DUCA", "PINCH", "BALTASAR", "CORO", "TUTTI"],
        "aliases": {
            "ANTIFOLI DI SIRACUSA": ["ANTIFOLO DI S.", "ANTIFOLO DI S", "ANTIFOLO DI SIRA", "ANTIFOLO DI SIRA- CUSA", "ANTIFOLO DI SIRACUSA", "ANFIFOLO DI S."],
            "ANTIFOLI DI EFESO": ["ANTIFOLO D’E.", "ANTIFOLO D'E.", "ANTIFOLO D’E", "ANTIFOLO D'E", "ANTIFOLO DI EFESO", "ANTOFOLO D’E."],
            "DROMI DI SIRACUSA": ["DROMIO DI S.", "DROMIO DI S", "DROMO DI S.", "DROMO DI S", "DROMIO DI SIRA", "DROMIO DI SIRA- CUSA", "DROMIO DI SIRACUSA"],
            "DROMI DI EFESO": ["DROMIO D’E.", "DROMIO D'E.", "DROMIO D’E", "DROMIO D'E", "DROMIO DI EFESO"],
            "DUCA": ["DUCA SOLINO"],
            "BALTASAR": ["BALDASSARRE"],
            "PINCH": ["PINZA"],
            "CORO": ["CORO DEI CITTADINI"],
            "PRIMO MERCANTE": ["1° MERCANTE", "1O MERCANTE", "PRIMO MERCANTE"],
            "SECONDO MERCANTE": ["2° MERCANTE", "2O MERCANTE", "SECONDO MERCANTE"],
            "ETERA": ["ETÈRA", "ETERA", "ETÈRA DI EFESO"],
            "UFFICIALE": ["UFFICIALE DI POLIZIA", "UFFIZIALE", "CARCERIERE"],
            "BADESSA": ["BADESSA EMILIA"],
            "SERVO": ["SERVO DI ADRIANA", "SERVO"],
        },
        "strip_numbered_notes": True,
        "package": "la-commedia-degli-equivoci.stagedesk",
    },
]


def main() -> None:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    for work in WORKS:
        content = parse_work(work)
        path = PACKAGE_DIR / work["package"]
        path.write_text(content, encoding="utf-8")
        print(f"{work['title']}: {path.name} ({len(content):,} caratteri)")


if __name__ == "__main__":
    main()
