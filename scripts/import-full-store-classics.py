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
    # StageDesk parses custom attributes directly and does not decode the HTML
    # apostrophe entity. Escape structural characters while preserving names
    # such as ``CONTE DELL'ISOLA`` exactly as authored.
    return html.escape(str(value), quote=False).replace('"', "&quot;")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode()
    value = value.upper().replace("’", "'")
    value = re.sub(r"[.(),:;!?\-—–]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


COLLECTIVE_SPEAKER_NAMES = {
    "TUTTI",
    "TUTTE",
    "CORO",
    "ENSEMBLE",
    "TUTTI INSIEME",
}


def is_collective_speaker(value: str) -> bool:
    return normalize(value) in COLLECTIVE_SPEAKER_NAMES


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
    drop_source_lines = {normalize(line) for line in work.get("drop_source_lines", [])}
    if drop_source_lines:
        result = [line for line in result if normalize(line) not in drop_source_lines]
    stop_pattern = work.get("stop_at")
    if stop_pattern:
        stop_index = next(
            (index for index, line in enumerate(result) if re.search(stop_pattern, line)),
            None,
        )
        if stop_index is not None:
            result = result[:stop_index]
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

    # Several Italian editions put the delivery direction between the label
    # and the dialogue: ``ELENA (a Helmer). C'è una signora.``. Resolve the
    # label before considering the parenthetical text.
    parenthetical_label = re.match(r"^([^()]{1,90}?)\s+\([^)]*\)\s*(?:—|–|-|:|\.)\s*", candidate)
    if parenthetical_label:
        direct = aliases.get(normalize(parenthetical_label.group(1).strip()))
        if direct:
            return direct
    # PDF extraction can split a long parenthetical over the next physical
    # line, leaving no closing parenthesis in this line. The label is still
    # unambiguous when it is immediately followed by ``(``.
    unclosed_parenthetical_label = re.match(r"^([^()]{1,90}?)\s+\(", candidate)
    if unclosed_parenthetical_label:
        direct = aliases.get(normalize(unclosed_parenthetical_label.group(1).strip()))
        if direct:
            return direct

    # Prefer an explicit speaker delimiter. A period is included because the
    # historical editions use labels such as "Gio." and "NORA.".
    label_match = re.match(r"^(.{1,90}?)\s*(?:—|–|-|:|\.)\s*", candidate)
    if label_match:
        label = label_match.group(1).strip()
        remainder = candidate[label_match.end():].strip()
        # In old editions a stage direction can mention another character as
        # part of the sentence, for example "Lep., e finge...". The comma or
        # conjunction means this is not a new speaker label.
        direct = aliases.get(normalize(label))
        if direct:
            # Once the label is known, every remainder is part of that
            # character's source block. In particular ``NORA. Con...`` and
            # ``NORA. E...`` were incorrectly rejected because ``CON`` and
            # ``E`` also look like stage-direction prefixes.
            return direct
        if remainder.startswith(",") or re.match(r"^(?:e|ed)\b", remainder, re.IGNORECASE):
            return None
        if _looks_like_stage_direction(remainder):
            return None

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
    # Liber Liber extracts numbered translator-note anchors as separate
    # parentheses. They are not part of the spoken text.
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def join_dialogue_lines(lines: list[str]) -> str:
    """Join source lines without preserving PDF line-break hyphenation."""
    text = " ".join(line.strip() for line in lines if line.strip())
    return re.sub(r"(?<=[A-Za-zÀ-ÿ])-[ \t]+(?=[a-zà-ÿ])", "", text)


def split_inline_speaker_segments(line: str, aliases: dict[str, str]) -> list[str]:
    """Split PDF lines that contain two or more printed speaker labels.

    Some editions lose a line break while extracting the PDF text, producing
    fragments such as ``LINDE. ... NORA. E allora?``.  Labels are limited to
    the known cast and must be followed by the same punctuation used by the
    source, so ordinary mentions of a character remain untouched.
    """
    labels = sorted(aliases, key=len, reverse=True)
    if not labels:
        return [line]
    label_pattern = "|".join(re.escape(label) for label in labels if label)
    pattern = re.compile(
        rf"(?<![A-Za-zÀ-ÿ])(?P<label>{label_pattern})"
        r"(?:\s+\([^)]*\))?\s*(?:—|–|-|:|\.)\s*"
    )
    matches = list(pattern.finditer(line))
    if not matches or (len(matches) == 1 and matches[0].start() == 0):
        return [line]
    segments: list[str] = []
    for index, match in enumerate(matches):
        if index == 0 and match.start() > 0:
            prefix = line[:match.start()].strip()
            if prefix:
                segments.append(prefix)
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        segment = line[start:end].strip()
        if segment:
            segments.append(segment)
    return segments or [line]


def dialogue_remainder(line: str, aliases: dict[str, str], speaker: str) -> str:
    """Return the text printed after a recognized speaker label."""
    candidate = re.sub(r"\s+", " ", line.strip())
    parenthetical_label = re.match(r"^([^()]{1,90}?)\s+\([^)]*\)\s*(?:—|–|-|:|\.)\s*", candidate)
    if parenthetical_label and aliases.get(normalize(parenthetical_label.group(1).strip())) == speaker:
        return candidate[parenthetical_label.end():].strip()
    unclosed_parenthetical_label = re.match(r"^([^()]{1,90}?)\s+\(", candidate)
    if unclosed_parenthetical_label and aliases.get(normalize(unclosed_parenthetical_label.group(1).strip())) == speaker:
        return candidate[len(unclosed_parenthetical_label.group(1)):].strip()
    label_match = re.match(r"^(.{1,90}?)\s*(?:—|–|-|:|\.)\s*", candidate)
    if label_match and aliases.get(normalize(label_match.group(1).strip())) == speaker:
        return candidate[label_match.end():].strip()
    return ""


def is_stage_direction_only(text: str) -> bool:
    """Identify blocks that contain only parenthesized stage directions."""
    compact_text = re.sub(r"\s+", " ", text).strip()
    if not compact_text:
        return True
    without_directions = re.sub(r"\([^)]*\)", "", compact_text).strip(" .;,:-—–")
    return not without_directions


def is_cast_heading(line: str, aliases: dict[str, str]) -> bool:
    """Reject cast lists accidentally parsed as scene locations.

    Historical editions put the scene cast immediately below the heading and
    use the same punctuation as a location line. A line containing known
    character labels, especially one ending in a comma or ``poi``, is not an
    ambientazione and must never become the position note.
    """
    value = re.sub(r"\s+", " ", line.strip())
    if not value:
        return True
    normalized = normalize(value).rstrip(" .,;:")
    known_names = {normalize(name) for name in aliases.values()}
    if normalized in known_names:
        return True
    hits = sum(1 for name in known_names if name and re.search(rf"\b{re.escape(name)}\b", normalized))
    if hits >= 2:
        return True
    if hits == 1 and (value.endswith(",") or re.search(r"\bpoi\b", value, re.IGNORECASE)):
        return True
    return False


def is_standalone_direction(line: str) -> bool:
    """Return true only for a complete stage-direction line.

    Do not classify dialogue such as ``(O il Conte...). Ma ditemi...`` as a
    direction merely because it starts with a parenthesis.
    """
    value = re.sub(r"\s+", " ", line.strip())
    return bool(re.fullmatch(r"(?:\([^()]*\)|\[[^\[\]]*\])[.?!;,:-]*", value))


def coalesce_stage_directions(lines: list[str]) -> list[str]:
    """Join parenthetical directions split by PDF line/page extraction."""
    result: list[str] = []
    buffer: str | None = None
    opener: str | None = None
    for line in lines:
        value = line.strip()
        if buffer is not None:
            buffer = f"{buffer} {value}".strip()
            if buffer.count(opener or "(") <= buffer.count(")" if opener == "(" else "]"):
                result.append(buffer)
                buffer = None
                opener = None
            continue
        if value.startswith(("(", "[")):
            close = ")" if value.startswith("(") else "]"
            if value.count(value[0]) > value.count(close):
                buffer = value
                opener = value[0]
                continue
        result.append(value)
    if buffer is not None:
        result.append(buffer)
    return result


def is_action_direction(line: str, aliases: dict[str, str]) -> bool:
    value = re.sub(r"\s+", " ", line.strip())
    if not value or detect_speaker(value, aliases):
        return False
    if is_standalone_direction(value):
        inner = value.strip("()[] ").lower()
        # Asides affect delivery rather than blocking, tone or position.
        return bool(re.search(r"\b(parte|entra|entrano|esce|escono|rientra|rientrano|ritorna|si ritira|si avvicina|si allontana|si siede|si alza|in atto|va|viene|seguono)\b", inner))
    if re.search(r"[!?](?:\s|$)", value):
        return False
    if re.match(r"^parte\b", value, re.IGNORECASE):
        return bool(re.match(r"^parte(?:[.?!;,:-]*$|\s+(?:non visto|fuori|con|poi|e)\b)", value, re.IGNORECASE))
    return bool(re.match(r"^(?:entr(?:a|ano)|esc(?:e|ono)|rientr(?:a|ano)|partono|ritorna|ritornano|si ritira|si avvicina|si allontana|si siede|si alza)\b", value, re.IGNORECASE))


def scene_notes(scene_text: list[str], speakers: list[str], title: str, scene_id: str, aliases: dict[str, str]) -> list[str]:
    cleaned_lines = coalesce_stage_directions([
        re.sub(r"\s+", " ", line.strip()) for line in scene_text if line.strip()
    ])
    first_speaker_index = next(
        (index for index, line in enumerate(cleaned_lines) if detect_speaker(line, aliases)),
        len(cleaned_lines),
    )
    pre_dialogue = cleaned_lines[:first_speaker_index]
    location_candidates = [
        line for line in pre_dialogue
        if not is_cast_heading(line, aliases)
        and not is_action_direction(line, aliases)
        and not detect_speaker(line, aliases)
        and len(line) <= 240
        and re.match(r"^[A-ZÀ-Ý]", line)
        and not line.endswith(",")
        and line.count(",") < 2
        and not re.search(r"[!?]", line)
    ]
    location = next(
        (
            line for line in location_candidates
            if re.search(
                r"\b(?:la scena|sala|stanza|camera|casa|palazzo|piazza|atrio|isola|castello|bosco|giardino|strada|luogo|campo|foresta|soggiorno|salone|cortile|recinto|mare|reggia|caverna|teatro|parco|porto|galleria|corridoio|porta|finestra|stufa|tavola|elsinore|verona|pavia|efeso)\b",
                line,
                re.IGNORECASE,
            )
        ),
        None,
    )
    position = compact(location or "La scena segue l'ambientazione indicata nell'edizione di riferimento.")
    directions = [line for line in cleaned_lines if is_action_direction(line, aliases)]
    movement = compact("; ".join(directions[:3])) if directions else "Seguire le entrate, le uscite e le azioni indicate nelle didascalie originali, mantenendo leggibili le relazioni nello spazio."
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
    expanded_scene: list[str] = []
    for line in scene_text:
        expanded_scene.extend(split_inline_speaker_segments(line, aliases))
    for index, line in enumerate(expanded_scene):
        speaker = detect_speaker(line, aliases, bare_labels)
        # A bare source label followed by punctuation is usually part of the
        # cast description at the top of a scene, not a spoken line.
        is_bare_source_label = normalize(line) in bare_labels or (
            line == line.upper() and not re.search(r"[—–:.;!?]", line)
        )
        if speaker and is_bare_source_label:
            next_line = expanded_scene[index + 1].strip() if index + 1 < len(expanded_scene) else ""
            if line.rstrip().endswith(",") or next_line.startswith((",", ".", ";", ")", "e ", "ed ", "a ", "di ", "con ", "entra", "esce", "rientra", "spavent")):
                speaker = None
        if speaker:
            if current_speaker and current:
                blocks.append((current_speaker, " ".join(current).strip()))
            current_speaker = speaker
            remainder = dialogue_remainder(line, aliases, speaker)
            current = [remainder] if remainder else []
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
    cleaned_blocks = []
    for speaker, text in blocks:
        value = clean_dialogue(join_dialogue_lines(text.splitlines()))
        if value and not is_stage_direction_only(value):
            cleaned_blocks.append((speaker, value))
    return cleaned_blocks, preface


def parse_work(work: dict) -> str:
    lines = source_lines(work)
    acts = find_actual_acts(lines, work["act_count"])
    if not acts:
        raise RuntimeError(f"Nessun atto riconosciuto per {work['title']}")
    aliases = speaker_aliases(work)
    bare_labels = {normalize(value) for value in work.get("bare_labels", [])}
    # Collective voices remain dialogue speakers but are not actor rows. This
    # keeps labels such as "TUTTI" available in the script without presenting
    # them as a character that an actor can select.
    characters = [character for character in work["characters"] if not is_collective_speaker(character)]
    presence: dict[str, list[str]] = {character: [] for character in characters}
    parsed_scenes: list[tuple[int, int, str, list[str], list[tuple[str, str]], list[str], list[str]]] = []
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
            act_prologue = act_lines[:scene_start] if scene_index == 1 else []
            parsed_scenes.append((act_index, scene_index, scene_title, raw_scene, blocks, preface, act_prologue))
            for speaker, _ in blocks:
                if is_collective_speaker(speaker):
                    continue
                if speaker not in characters:
                    characters.append(speaker)
                presence.setdefault(speaker, [])
                scene_label = f"{act_index}/{scene_index}"
                if scene_label not in presence[speaker]:
                    presence[speaker].append(scene_label)
    output = ["| Personaggio | Interprete | Presenza |", "| --- | --- | --- |"]
    for character in characters:
        locations = "; ".join(presence.get(character, []))
        if locations:
            output.append(f"| {character} | D/A | {locations} |")
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
        output.extend([f"# Atto {act_index}", ""])
        for parsed_act, scene_index, scene_title, raw_scene, blocks, preface, act_prologue in parsed_scenes:
            if parsed_act != act_index:
                continue
            scene_id = f"atto-{act_index}-scena-{scene_index}"
            output.extend([f"## Scena {scene_index}" + (f" — {scene_title}" if scene_title and not scene_title.lower().startswith("scena ") else ""), ""])
            scene_source = act_prologue + raw_scene
            output.extend(scene_notes(scene_source, [speaker for speaker, _ in blocks], scene_title, scene_id, aliases))
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
        "stop_at": r"^FINE\s*$",
        "drop_source_lines": ["William Shakespeare, Romeo e Giulietta"],
        "characters": ["ROMEO", "GIULIETTA", "BENVOLIO", "MERCUZIO", "TEBALDO", "CAPULETI", "MONNA CAPULETI", "MONTECCHI", "MONNA MONTECCHI", "NUTRICE", "FRATE LORENZO", "PARIDE", "PRINCIPE SCALIGERO", "MESSAGGERO", "BALTHASAR", "ABRAMO", "BALDASSARRE", "PIETRO", "CITTADINI", "GUARDIA", "TUTTI"],
        "aliases": {"PRINCIPE SCALIGERO": ["PRINCIPE"], "NUTRICE": ["NUTRICE", "LA NUTRICE"], "FRATE LORENZO": ["FRATE LORENZO", "LORENZO"], "FRATE GIOVANNI": ["FRATE GIOVANNI", "FRATEL GIOVANNI", "FRATE GIOVANNI."], "BALTHASAR": ["BALTASSAR", "BALDASSARRE"], "CAPULETI": ["CAPULETO", "CAPULETI", "SECONDO CAPULETI"], "GUARDIA": ["GUARDIA", "UNA GUARDIA", "A GUARDIA"], "GUARDIANO": ["GUARDIANO"], "SERVO": ["SERVO", "1° SERVO", "2° SERVO", "3° SERVO", "UN SERVO"], "MUSICO": ["MUSICO", "1° MUSICO", "2° MUSICO", "3° MUSICO"], "MESSAGGERO": ["MESSAGGERO", "MESSO"], "CITTADINO": ["1° CITTADINO", "2° CITTADINO", "3° CITTADINO"], "MONNA CAPULETI": ["MONNA CAPULETI"], "MONNA MONTECCHI": ["MONNA MONTECCHI"], "SANSONE": ["SANSONE"], "GREGORIO": ["GREGORIO"], "ABRAMO": ["ABRAMO"], "BALDASSARRE": ["BALDASSARRE"], "CITTADINI": ["CITTADINI"], "SPEZIALE": ["SPEZIALE"], "PAGGIO": ["PAGGIO", "PAGGETTO"]},
        "package": "romeo-e-giulietta.stagedesk",
    },
    {
        "slug": "amleto", "title": "Amleto", "act_count": 5,
        "source_files": ["amleto-real.txt"], "source_url": "https://liberliber.it/autori/autori-s/william-shakespeare/amleto/",
        "attribution": "testo di William Shakespeare nella traduzione di Goffredo Raponi, tratto dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["AMLETO", "CLAUDIO", "GERTRUDE", "POLONIO", "OFELIA", "LAERTE", "ORAZIO", "SPETTRO", "ROSENCRANTZ", "GUILDENSTERN", "FORTINBRAS", "BERNARDO", "MARCELLO", "FRANCESCO", "OSRICO", "PRIMO BECCHINO", "SECONDO BECCHINO", "MESSAGGERO", "ATTORI", "TUTTI"],
        "aliases": {
            "CLAUDIO": ["RE", "RE.", "CLAUDIO", "CLAUDIO."],
            "GERTRUDE": ["REGINA", "REGINA.", "GERTRUDE"],
            "FORTINBRAS": ["FORTebraccio", "FORTBRACCIO"],
            "SPETTRO": ["SPETTRO DEL PADRE DI AMLETO"],
            "PRIMO BECCHINO": ["PRIMO BECCHINO"],
            "SECONDO BECCHINO": ["SECONDO BECCHINO"],
        },
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
        "aliases": {
            "HELMER": ["HELM", "HELM.", "HIELM", "HIELM.", "IIELM", "IIELM."],
            "KROGSTAD": ["KROG", "KROG."],
            "SIGNORA LINDE": ["LINDE", "LINDE.", "SIGNORA LINDE"],
            "DOTTOR RANK": ["RANK", "RANK.", "DOTT. RANK"],
            "ELENA": ["ELENA", "ELENA."],
            "NORA": ["NOIR", "NOIR."],
            "ANNE-MARIE": ["ANNA MARIA", "ANNE MARIE", "MARIANNA", "MAR", "MAR."],
            "IL FACCHINO": ["FACC", "FACC.", "FACCHINO", "FACCHINO."],
            "I BAMBINI": ["BAMBINI", "I BAMBINI"],
            "IL MESSO": ["MESSO", "MESSO."],
        },
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
