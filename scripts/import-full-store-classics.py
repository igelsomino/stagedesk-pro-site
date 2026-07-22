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


def clean_lines(text: str, strip_numbered_notes: bool = False) -> list[str]:
    lines: list[str] = []
    skipping_numbered_note = False
    for raw in text.replace("\r", "").replace("\f", "\n").splitlines():
        line = raw.strip()
        line = re.sub(r"\s+", " ", line)
        if not line or re.fullmatch(r"\d+", line):
            skipping_numbered_note = False
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
        result.extend(clean_lines(
            (SOURCE_DIR / filename).read_text(encoding="utf-8", errors="ignore"),
            strip_numbered_notes=work.get("strip_numbered_notes", False),
        ))
    return result


def find_actual_acts(lines: list[str], expected: int) -> list[tuple[int, str]]:
    matches = [(index, match.group("number")) for index, line in enumerate(lines) if (match := ACT_RE.match(line))]
    if len(matches) > expected:
        matches = matches[-expected:]
    return matches


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


def detect_speaker(line: str, aliases: dict[str, str]) -> str | None:
    # Stage directions and location descriptions are never speaker labels.
    if line.startswith(("(", "[", "Entr", "Esce", "Rient", "Entra", "SCENA", "Scena")):
        return None
    candidate = re.sub(r"\s+", " ", line.strip())
    candidate = re.sub(r"\s*(?:—|–|-|:)$", "", candidate).strip()
    direct = aliases.get(normalize(candidate))
    if direct:
        return direct
    # A few historical editions use a name followed by a full stop.
    candidate = re.sub(r"[.]$", "", candidate).strip()
    direct = aliases.get(normalize(candidate))
    if direct:
        return direct
    # Also accept a known label at the start when the source adds an action.
    normalized = normalize(candidate)
    for key, canonical in sorted(aliases.items(), key=lambda item: -len(item[0])):
        if normalized.startswith(key + " ") and len(normalized) < len(key) + 45:
            return canonical
    # Older Italian editions often use a title-case name followed by a dash
    # without listing that minor/collective role in the cast table.
    label_match = re.fullmatch(r"([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ .’'0-9]{1,55})\s*(?:—|–|-)", candidate)
    if label_match:
        label = re.sub(r"\s+", " ", label_match.group(1)).strip(" .")
        if label and not label.lower().startswith(("entra", "esce", "rientra", "scena")):
            return label.upper()
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


def scene_notes(scene_text: list[str], speakers: list[str], title: str, scene_id: str) -> list[str]:
    directions = [line for line in scene_text if line.startswith(("(", "[")) or line.lower().startswith(("entr", "esce", "rient"))]
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


def parse_scene(scene_text: list[str], aliases: dict[str, str], fallback_character: str) -> tuple[list[tuple[str, str]], list[str]]:
    blocks: list[tuple[str, str]] = []
    preface: list[str] = []
    current_speaker: str | None = None
    current: list[str] = []
    for line in scene_text:
        speaker = detect_speaker(line, aliases)
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
    return [(speaker, text) for speaker, text in blocks if text], preface


def parse_work(work: dict) -> str:
    lines = source_lines(work)
    acts = find_actual_acts(lines, work["act_count"])
    if not acts:
        raise RuntimeError(f"Nessun atto riconosciuto per {work['title']}")
    aliases = speaker_aliases(work)
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
            blocks, preface = parse_scene(raw_scene, aliases, characters[0])
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
        "characters": ["ARGAN", "TOINETTE", "ANGELICA", "CLEANTE", "BERALDO", "BELINA", "SIGNOR DIAFOIRUS", "TOMMASO DIAFOIRUS", "DOTTOR PURGONE", "SIGNORA FLEURANT", "NOTAIO"],
        "aliases": {"ARGAN": ["ARGANO"], "TOINETTE": ["ANTONIETTA"], "SIGNOR DIAFOIRUS": ["DIAFOIRUS", "DOTTOR DIAFOIRUS"], "TOMMASO DIAFOIRUS": ["TOMMASO", "TOMASO"], "DOTTOR PURGONE": ["PURGONE"], "SIGNORA FLEURANT": ["FLEURANT"]},
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
        "aliases": {"DON GIOVANNI": ["GIO", "GIO."], "LEPORELLO": ["LEP", "LEP."], "DONNA ANNA": ["ANNA", "D. ANNA"], "DON OTTAVIO": ["OTT", "OTT."], "IL COMMENDATORE": ["COM", "COM.", "COMMENDATORE"], "MASETTO": ["MAS", "MAS."], "ZERLINA": ["ZER", "ZER."]},
        "package": "don-giovanni.stagedesk",
    },
    {
        "slug": "la-commedia-degli-equivoci", "title": "La commedia degli equivoci", "act_count": 5,
        "source_files": ["commedia-real.txt"], "source_url": "https://liberliber.it/autori/autori-s/william-shakespeare/la-commedia-degli-equivoci/",
        "attribution": "testo di William Shakespeare nella traduzione di Goffredo Raponi, tratto dall'edizione integrale digitale di Liber Liber, distribuita con licenza Creative Commons BY-NC-SA 4.0",
        "characters": ["ANTIFOLI DI SIRACUSA", "ANTIFOLI DI EFESO", "DROMI DI SIRACUSA", "DROMI DI EFESO", "ADRIANA", "LUCIANA", "EMILIA", "ANGELO", "EGEONE", "DUCA", "PINCH", "BALTASAR", "CORO", "TUTTI"],
        "aliases": {
            "ANTIFOLI DI SIRACUSA": ["ANTIFOLO DI S.", "ANTIFOLO DI S", "ANTIFOLO DI SIRA- CUSA", "ANTIFOLO DI SIRACUSA"],
            "ANTIFOLI DI EFESO": ["ANTIFOLO D’E.", "ANTIFOLO D'E.", "ANTIFOLO D’E", "ANTIFOLO D'E", "ANTIFOLO DI EFESO"],
            "DROMI DI SIRACUSA": ["DROMIO DI S.", "DROMIO DI S", "DROMIO DI SIRA- CUSA", "DROMIO DI SIRACUSA"],
            "DROMI DI EFESO": ["DROMIO D’E.", "DROMIO D'E.", "DROMIO D’E", "DROMIO D'E", "DROMIO DI EFESO"],
            "DUCA": ["DUCA SOLINO"],
            "BALTASAR": ["BALDASSARRE"],
            "PINCH": ["PINZA"],
            "CORO": ["CORO DEI CITTADINI"],
            "PRIMO MERCANTE": ["1° MERCANTE", "1O MERCANTE", "PRIMO MERCANTE"],
            "SECONDO MERCANTE": ["2° MERCANTE", "2O MERCANTE", "SECONDO MERCANTE"],
            "ETERA": ["ETÈRA", "ETERA", "ETÈRA DI EFESO"],
            "UFFICIALE": ["UFFICIALE DI POLIZIA", "CARCERIERE"],
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
