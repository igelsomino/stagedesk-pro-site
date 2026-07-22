import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = fileURLToPath(new URL('..', import.meta.url))
const packageDir = resolve(projectRoot, process.env.STORE_PACKAGE_DIR || '.store-assets/copioni')

const plays = [
  {
    slug: 'macbeth',
    title: 'Macbeth',
    author: 'William Shakespeare',
    characters: ['MACBETH', 'LADY MACBETH', 'BANCO', 'MACDUFF', 'MALCOLM', 'DUNCAN', 'ROSS', 'LENNOX', 'LE TRE STREGHE'],
    scenes: [
      [1, 'Il presagio nella brughiera', 'MACBETH, BANCO, LE TRE STREGHE', 'Una brughiera vuota, attraversata da vento e nebbia.', 'Le tre figure entrano da lati diversi e chiudono lentamente il cerchio intorno ai soldati.', 'Il destino deve sembrare una tentazione che ha imparato a parlare.', 'La corona è vicina, ma nessuno sa ancora quale prezzo abbia.'],
      [1, 'La lettera della vittoria', 'MACBETH, LADY MACBETH, ROSS', 'Un tavolo con una lettera e una luce stretta sul centro.', 'Lady Macbeth legge in piedi, poi sposta la lettera davanti a Macbeth senza consegnargliela.', 'L’ambizione cresce nel silenzio domestico prima di diventare gesto politico.', 'La notizia del re in visita cambia il peso di ogni oggetto.'],
      [1, 'La notte del re', 'DUNCAN, MACBETH, LADY MACBETH, BANCO', 'La sala degli ospiti è ordinata, ma una porta resta sempre visibile.', 'Duncan attraversa il centro salutando; Macbeth resta ai margini e Banco osserva la porta.', 'L’ospitalità e il pericolo devono convivere nello stesso quadro.', 'Nessuno nomina il delitto, ma ogni pausa lo prepara.'],
      [2, 'Il gesto irreversibile', 'MACBETH, LADY MACBETH, LENNOX', 'La sala è vuota; una campana segna il passaggio dalla decisione all’azione.', 'Macbeth resta fermo mentre Lady Macbeth attraversa la scena e torna con le mani vuote.', 'Il terrore nasce quando il pensiero non può più tornare indietro.', 'Dopo il gesto, il castello sembra più grande e più ostile.'],
      [2, 'Il banchetto e il fantasma', 'MACBETH, LADY MACBETH, BANCO, ROSS', 'Un tavolo lungo separa il re dai suoi invitati.', 'Gli ospiti prendono posto; Macbeth lascia vuota una sedia e la guarda più volte.', 'La colpa invade lo spazio pubblico e rompe il cerimoniale.', 'Il potere non riesce a nascondere ciò che il corpo vede.'],
      [2, 'La seconda profezia', 'MACBETH, LE TRE STREGHE, LENNOX', 'Una stanza circolare suggerita da tre candele e una bacinella d’acqua.', 'Le streghe lavorano intorno all’acqua mentre Macbeth si avvicina solo quando viene chiamato.', 'La sicurezza promessa dal soprannaturale deve suonare ambigua.', 'Ogni risposta apre una paura più precisa.'],
      [3, 'La foresta in cammino', 'MACDUFF, MALCOLM, ROSS, LENNOX', 'Un campo militare con rami e stoffe che possono diventare alberi.', 'I soldati raccolgono rami e avanzano mantenendo la stessa distanza.', 'La resistenza acquista forma attraverso un movimento collettivo.', 'La profezia cambia significato quando diventa una strategia.'],
      [3, 'La stanza vuota', 'LADY MACBETH, MACBETH, LENNOX', 'La stanza della regina è quasi priva di oggetti.', 'Lady Macbeth percorre una linea breve e ripete un gesto di lavaggio; Macbeth non la interrompe.', 'La mente non distingue più il ricordo dalla presenza.', 'Il regno si sgretola prima nei corpi e poi nelle mura.'],
      [3, 'Il giorno senza sole', 'MACBETH, MACDUFF, MALCOLM, ROSS, BANCO', 'Il campo finale è aperto e senza il tavolo del castello.', 'Macbeth resta al centro; gli altri personaggi avanzano soltanto dopo ogni sua risposta.', 'Il finale non è una vendetta privata, ma il passaggio di una responsabilità.', 'La corona torna a essere un oggetto, non una promessa.'],
    ],
  },
  {
    slug: 'l-avaro',
    title: "L'avaro",
    author: 'Molière',
    characters: ['ARPAGONE', 'ELISA', 'CLEANTE', 'MARIANA', 'VALERIO', 'FROSINA', 'ANSELMO', 'MAESTRO GIACOMO'],
    scenes: [
      [1, 'Il tesoro nascosto', 'ARPAGONE, ELISA, CLEANTE, VALERIO', 'La casa è disposta intorno a una cassa che nessuno deve toccare.', 'Arpagone controlla porte e cassetti; i giovani parlano soltanto quando lui si allontana.', 'La paura del denaro produce un ordine più soffocante della povertà.', 'Il tesoro è invisibile ma governa ogni relazione.'],
      [1, 'Due promesse', 'ELISA, VALERIO, CLEANTE', 'Un giardino stretto separa due percorsi che si incrociano al centro.', 'Elisa e Valerio si scambiano posto ogni volta che sentono i passi di Arpagone.', 'L’amore deve trovare una forma pratica per resistere al controllo.', 'La promessa privata entra in conflitto con il contratto familiare.'],
      [1, 'Il matrimonio conveniente', 'ARPAGONE, FROSINA, MARIANA, CLEANTE', 'Un salotto preparato per ricevere un ospite importante.', 'Frosina dispone le sedie; Arpagone cambia la posizione di ogni sedia prima che Mariana entri.', 'La cortesia diventa una trattativa e ogni sorriso ha un prezzo.', 'Arpagone vuole comprare un futuro che gli altri dovrebbero vivere.'],
      [2, 'Il prestito', 'CLEANTE, MAESTRO GIACOMO, ARPAGONE', 'Un banco con registri e monete divide padre e figlio.', 'Cleante conta le monete ad alta voce; Arpagone cancella le cifre dal registro.', 'Il conflitto generazionale passa attraverso il linguaggio della contabilità.', 'Chi presta denaro pretende anche di possedere le scelte.'],
      [2, 'La cena promessa', 'ARPAGONE, FROSINA, MAESTRO GIACOMO, VALERIO', 'La tavola è apparecchiata con pochi piatti e troppi occhi.', 'Maestro Giacomo entra con i piatti; Arpagone li fa arretrare uno alla volta.', 'La comicità nasce dalla sproporzione fra la festa annunciata e la cena reale.', 'La casa si prepara a mostrare la propria miseria come una virtù.'],
      [2, 'La cassetta scomparsa', 'ARPAGONE, CLEANTE, ELISA, VALERIO', 'Il centro della scena è vuoto, segnato soltanto da una buca nel pavimento.', 'Arpagone cerca seguendo una griglia precisa; tutti gli altri cambiano posizione per non farsi scoprire.', 'Il sospetto rende il padrone incapace di distinguere amici e ladri.', 'La cassetta diventa la prova che il controllo non protegge nulla.'],
      [3, 'La verità di Mariana', 'MARIANA, FROSINA, CLEANTE, ELISA', 'Un cortile aperto consente per la prima volta ai giovani di stare al centro.', 'Mariana porta una lettera; Frosina accompagna Cleante e si ferma sulla soglia.', 'La verità prende spazio quando non deve più chiedere permesso.', 'Il passato di una famiglia apre una via d’uscita inattesa.'],
      [3, 'Il confronto con Anselmo', 'ANSELMO, ARPAGONE, MARIANA, VALERIO', 'Due sedie identiche sono poste una di fronte all’altra.', 'Anselmo non si alza; Arpagone gira intorno alla sedia cercando un vantaggio.', 'Il confronto deve sostituire l’equivoco con una responsabilità concreta.', 'Il denaro non può più nascondere ciò che i nomi rivelano.'],
      [3, 'La casa restituita', 'ARPAGONE, ELISA, CLEANTE, MARIANA, VALERIO, FROSINA', 'La casa è la stessa, ma la cassa è spostata ai margini.', 'I personaggi riordinano la stanza lasciando libera la parte centrale.', 'Il finale è corale: la ricchezza perde il diritto di decidere da sola.', 'Arpagone conserva il tesoro, ma deve finalmente condividere la casa.'],
    ],
  },
  {
    slug: 'casa-di-bambola',
    title: 'Casa di bambola',
    author: 'Henrik Ibsen',
    characters: ['NORA', 'TORVALD', 'KROGSTAD', 'SIGNORA LINDE', 'DOTTOR RANK', 'I BAMBINI', 'ANNE-MARIE'],
    scenes: [
      [1, 'La casa ordinata', 'NORA, TORVALD, ANNE-MARIE', 'Un salotto luminoso con una porta che si apre sempre verso l’esterno.', 'Nora sistema gli oggetti appena Torvald li sposta; Anne-Marie osserva senza intervenire.', 'La felicità domestica deve mostrare le proprie regole prima delle proprie crepe.', 'La casa è accogliente, ma non appartiene allo stesso modo a tutti.'],
      [1, 'La visita della signora Linde', 'NORA, SIGNORA LINDE, TORVALD', 'Due sedie ai lati del salotto creano uno spazio privato e uno pubblico.', 'Nora avvicina le sedie quando Torvald è assente e le separa al suo ritorno.', 'L’amicizia riapre una memoria che la casa aveva tenuto chiusa.', 'Il lavoro e il denaro diventano strumenti di autonomia.'],
      [1, 'La lettera di Krogstad', 'NORA, KROGSTAD, DOTTOR RANK', 'Una cassetta della posta domina il fondo della scena.', 'Krogstad resta vicino alla porta; Nora attraversa il salotto senza mai raggiungere la cassetta.', 'La minaccia cresce attraverso la distanza e non attraverso il volume della voce.', 'Il segreto è ormai un oggetto che tutti possono vedere.'],
      [2, 'La danza', 'NORA, TORVALD, DOTTOR RANK, SIGNORA LINDE', 'Il salotto viene liberato per una festa che nessuno riesce a godere.', 'Nora prova i passi mentre Torvald corregge la postura; la Signora Linde osserva la porta.', 'Il movimento esteriore nasconde una decisione che sta diventando inevitabile.', 'La festa è una forma di attesa e la casa trattiene il respiro.'],
      [2, 'La cassetta aperta', 'TORVALD, NORA, KROGSTAD', 'La porta e la cassetta della posta occupano due estremi della scena.', 'Torvald attraversa il salotto lentamente; Nora cerca di fermarlo senza toccarlo.', 'La scena deve avere il ritmo di una sentenza già scritta.', 'Il matrimonio viene messo alla prova dalla verità che pretendeva di proteggere.'],
      [2, 'Il dialogo interrotto', 'NORA, TORVALD, DOTTOR RANK', 'Una lampada accesa resta sul tavolo fra i due coniugi.', 'Nora e Torvald cambiano lato del tavolo senza mai sedersi insieme.', 'La cortesia cede il posto alla precisione delle domande.', 'Nora comprende che essere amata non significa essere conosciuta.'],
      [3, 'La lettera restituita', 'KROGSTAD, SIGNORA LINDE, NORA', 'La soglia della casa è visibile e non più protetta da tende.', 'La Signora Linde consegna la lettera e resta sulla soglia; Nora sceglie il centro.', 'La restituzione del ricatto non restituisce automaticamente la fiducia.', 'Un gesto corretto può arrivare troppo tardi per cancellare ciò che ha rivelato.'],
      [3, 'Il confronto', 'NORA, TORVALD, ANNE-MARIE', 'Il salotto è spoglio: restano soltanto la tavola e la porta.', 'Torvald cerca di ricomporre la stanza; Nora tiene la porta aperta.', 'La conversazione deve essere ferma, intima e priva di melodramma.', 'La casa diventa il luogo in cui una persona decide di conoscersi.'],
      [3, 'La porta', 'NORA, TORVALD', 'La soglia resta illuminata mentre il salotto si oscura.', 'Nora attraversa la stanza, prende il cappotto e torna una sola volta verso la tavola.', 'Il finale è un gesto netto, non una fuga improvvisa.', 'La porta chiude una parte della vita e apre la responsabilità di sceglierne un’altra.'],
    ],
  },
  {
    slug: 'don-giovanni',
    title: 'Don Giovanni',
    author: 'Lorenzo Da Ponte',
    characters: ['DON GIOVANNI', 'LEPORELLO', 'DONNA ANNA', 'DON OTTAVIO', 'ELVIRA', 'MASETTO', 'ZERLINA', 'IL COMMENDATORE'],
    scenes: [
      [1, 'La fuga notturna', 'DON GIOVANNI, LEPORELLO, DONNA ANNA, IL COMMENDATORE', 'Un cortile notturno con una porta monumentale sul fondo.', 'Don Giovanni attraversa il cortile veloce; Leporello raccoglie gli oggetti lasciati dietro di lui.', 'Il desiderio è energia, ma la violenza interrompe subito il gioco.', 'La fuga lascia dietro di sé una promessa di conseguenze.'],
      [1, 'Il catalogo', 'LEPORELLO, ELVIRA, DON GIOVANNI', 'Una piazza con un registro aperto sopra un leggio.', 'Leporello legge senza avanzare; Elvira percorre la piazza cercando una risposta.', 'La comicità deve contenere già il dolore di chi viene ridotto a numero.', 'Il registro non racconta conquiste: rivela un modo di non vedere gli altri.'],
      [1, 'Il matrimonio interrotto', 'ZERLINA, MASETTO, DON GIOVANNI, LEPORELLO', 'Una festa contadina con una tavola e una ghirlanda.', 'Zerlina e Masetto si avvicinano; Don Giovanni cambia il ritmo della festa con un brindisi.', 'L’allegria è reale, ma il potere può deformarla in un istante.', 'La scelta di Zerlina deve restare visibile, anche dentro la seduzione.'],
      [2, 'La maschera', 'DON GIOVANNI, LEPORELLO, ELVIRA, DON OTTAVIO', 'Una sala da ballo con tre maschere appese alla parete.', 'Don Giovanni cambia maschera al centro; Leporello viene spinto verso le uscite.', 'La farsa è una macchina di identità e responsabilità scambiate.', 'Chi indossa una maschera non smette di essere riconoscibile.'],
      [2, 'La statua', 'DON GIOVANNI, LEPORELLO, IL COMMENDATORE', 'Un tavolo di pietra suggerisce il monumento senza rappresentarlo.', 'La statua entra dal fondo; Don Giovanni non arretra e Leporello perde la linea.', 'Il soprannaturale arriva con una calma più minacciosa del grido.', 'La cena promessa obbliga il protagonista a rispondere del passato.'],
      [2, 'Elvira alla porta', 'ELVIRA, DON GIOVANNI, LEPORELLO', 'La porta della casa è illuminata da una luce verticale.', 'Elvira bussa senza entrare; Don Giovanni continua a preparare la tavola.', 'La scena ha il tempo di una possibilità che viene rifiutata.', 'Il pentimento non può essere delegato a chi soffre.'],
      [3, 'La ricerca della verità', 'DONNA ANNA, DON OTTAVIO, ELVIRA, LEPORELLO', 'Una sala vuota con il registro chiuso al centro.', 'Donna Anna apre il registro e lo richiude; Don Ottavio resta accanto alla porta.', 'La giustizia deve distinguere vendetta, memoria e protezione.', 'Le vittime non sono comparse nella storia di un altro.'],
      [3, 'L’ultima cena', 'DON GIOVANNI, LEPORELLO, IL COMMENDATORE', 'Una tavola apparecchiata in modo solenne e completamente vuota.', 'Don Giovanni serve due piatti; il Commendatore avanza senza sedersi.', 'Il rituale comico si trasforma in un confronto senza possibilità di fuga.', 'La libertà senza responsabilità diventa una stanza chiusa.'],
      [3, 'Dopo il fuoco', 'ELVIRA, DONNA ANNA, DON OTTAVIO, ZERLINA, MASETTO, LEPORELLO', 'La piazza torna aperta e il registro è lasciato a terra.', 'I personaggi formano un gruppo non gerarchico; Leporello depone la chiave della casa.', 'Il finale guarda ai vivi e alla responsabilità di ricominciare.', 'La storia non termina con il colpevole: continua con chi deve scegliere diversamente.'],
    ],
  },
  {
    slug: 'la-commedia-degli-equivoci',
    title: 'La commedia degli equivoci',
    author: 'William Shakespeare',
    characters: ['ANTIFOLI DI SIRACUSA', 'ANTIFOLI DI EFESO', 'DROMI DI SIRACUSA', 'DROMI DI EFESO', 'ADRIANA', 'LUCIANA', 'EMILIA', 'ANGELO'],
    scenes: [
      [1, 'La città delle somiglianze', 'ANTIFOLI DI SIRACUSA, DROMI DI SIRACUSA, EMILIA', 'Una piazza con due porte identiche e un cartello spostabile.', 'I due viaggiatori entrano da porte opposte e scelgono sempre quella sbagliata.', 'La comicità nasce dalla precisione con cui la città si rifiuta di spiegarsi.', 'Un nome somiglia a un altro prima ancora che qualcuno lo pronunci.'],
      [1, 'Il primo errore', 'ANTIFOLI DI EFESO, DROMI DI EFESO, ADRIANA', 'La soglia di una casa con un tavolo apparecchiato.', 'Adriana accoglie l’uomo sbagliato; Dromi corre fra casa e piazza con due messaggi.', 'L’equivoco deve essere rapido, affettuoso e già pericoloso.', 'La casa riconosce un marito che il marito non riconosce.'],
      [1, 'La catena degli ordini', 'DROMI DI SIRACUSA, ANGELO, LUCIANA', 'Un laboratorio con una catena e un anello su un panno.', 'Angelo attraversa il laboratorio; Dromi cambia destinatario ogni volta che sente il proprio nome.', 'Gli oggetti hanno una traiettoria più affidabile delle persone.', 'Un ordine sbagliato mette in movimento tutta la città.'],
      [2, 'La casa divisa', 'ADRIANA, LUCIANA, ANTIFOLI DI SIRACUSA, DROMI DI SIRACUSA', 'Il salotto è separato da una linea di luce che nessuno deve oltrepassare.', 'Adriana indica la casa; Luciana protegge la porta; i forestieri restano sulla linea.', 'La gelosia traduce l’errore in una colpa personale.', 'Quando una persona pretende una spiegazione, la città risponde con un altro equivoco.'],
      [2, 'Il banchetto', 'ANTIFOLI DI EFESO, ADRIANA, DROMI DI EFESO, EMILIA', 'Una tavola centrale viene apparecchiata e sparecchiata più volte.', 'Dromi porta piatti in direzioni opposte; Adriana cambia posto a ogni ingresso.', 'Il ritmo del banchetto deve diventare una partitura fisica.', 'Tutti hanno un ricordo della stessa cena e nessuno ha mangiato.'],
      [2, 'La chiave e l’anello', 'ANGELO, LUCIANA, ANTIFOLI DI SIRACUSA, DROMI DI SIRACUSA', 'Il laboratorio torna vuoto, con il panno al centro.', 'Angelo mostra l’anello; Antifolo cerca una risposta; Dromi controlla entrambe le porte.', 'La prova materiale non basta quando l’identità resta incerta.', 'Il valore dell’oggetto cresce perché la città non sa più a chi appartenga.'],
      [3, 'La città si ferma', 'ADRIANA, LUCIANA, ANTIFOLI DI EFESO, ANTIFOLI DI SIRACUSA', 'La piazza è libera e le due porte sono finalmente aperte.', 'Tutti avanzano a coppie speculari; nessuno parla prima di aver guardato il proprio doppio.', 'La commedia rallenta per lasciare spazio al riconoscimento.', 'La somiglianza non è più un ostacolo, ma una domanda comune.'],
      [3, 'L’abbazia', 'EMILIA, DROMI DI SIRACUSA, DROMI DI EFESO, ANGELO', 'Una soglia neutra separa la piazza dalla stanza dell’abbazia.', 'Emilia resta sulla soglia; i due Dromi si scambiano gli oggetti che hanno trasportato.', 'La soluzione arriva attraverso ascolto e non attraverso autorità.', 'La memoria della famiglia ricompone ciò che l’errore aveva disperso.'],
      [3, 'Due famiglie, una tavola', 'EMILIA, ADRIANA, LUCIANA, ANTIFOLI DI EFESO, ANTIFOLI DI SIRACUSA, DROMI DI EFESO, DROMI DI SIRACUSA', 'La tavola occupa il centro e le due porte restano visibili.', 'I personaggi prendono posto alternando i due gruppi; i Dromi servono lo stesso piatto.', 'Il finale conserva il ritmo della farsa e la chiarezza del riconoscimento.', 'La città non ha smesso di essere strana, ma ora tutti conoscono il proprio nome.'],
    ],
  },
]

const slugify = (value) => value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

const escapeAttribute = (value) => String(value).replace(/"/g, '&quot;')

function buildScript(play) {
  const characters = new Set(play.characters)
  const lines = ['| Personaggio | Interprete | Presenza | Note |', '| --- | --- | --- | --- |']
  for (const character of characters) lines.push(`| ${character} | Da assegnare | In scena | Personaggio dell’adattamento originale. |`)
  lines.push('', `# ${play.title}`, '', '> **EDIZIONE STAGEDESK**: adattamento originale ispirato a un’opera di pubblico dominio. Battute e note create appositamente per StageDesk Pro e non tratte da traduzioni moderne.', '')

  let dialogueCount = 0
  for (let act = 1; act <= 3; act += 1) {
    lines.push(`## Atto ${act}`, '')
    play.scenes.filter(([sceneAct]) => sceneAct === act).forEach((scene, sceneIndex) => {
      const [, title, cast, position, movement, tone, focus] = scene
      const sceneId = `atto-${act}-scena-${sceneIndex + 1}`
      lines.push(`### Scena ${sceneIndex + 1} — ${title}`, '')
      const notes = [
        ['characters', 'blue', 'Personaggi in scena', cast, 'personaggi'],
        ['position', 'blue', 'Posizione', position, 'posizione'],
        ['movement', 'green', 'Movimento', movement, 'movimento'],
        ['tone', 'purple', 'Tono', tone, 'tono'],
      ]
      for (const [type, color, noteTitle, content, suffix] of notes) {
        const noteId = `note-${sceneId}-${suffix}`
        lines.push(`::regia{id="${noteId}" type="${type}" color="${color}" title="${escapeAttribute(noteTitle)}" sceneId="${sceneId}" anchorId="${noteId}"}`, content, '::', '')
      }
      const speakers = cast.split(',').map((value) => value.trim())
      const dialogueLines = [
        `${speakers[0]} osserva la scena e comprende che ${focus.toLowerCase()}`,
        `${speakers[1] || speakers[0]} risponde che ogni scelta ha bisogno di una prova, non soltanto di una promessa.`,
        `${speakers[2] || speakers[0]} chiede di parlare prima che il silenzio decida per tutti.`,
        `${speakers[0]} conclude: allora restiamo al centro e affrontiamo ciò che abbiamo aperto.`,
      ]
      dialogueLines.forEach((content, index) => {
        dialogueCount += 1
        const character = speakers[index % speakers.length]
        lines.push(`::battuta{id="battuta-${sceneId}-${dialogueCount}" characterId="${slugify(character)}" character="${escapeAttribute(character)}" sceneId="${sceneId}"}`, content, '::', '')
      })
    })
  }
  lines.push('> **Nota per la prova**: questa è una riscrittura originale modificabile. Personaggi, battute, note e cue possono essere adattati direttamente nell’editor.')
  return lines.join('\n') + '\n'
}

await mkdir(packageDir, { recursive: true })
for (const play of plays) {
  await writeFile(resolve(packageDir, `${play.slug}.stagedesk`), buildScript(play), 'utf8')
  console.log(`Generato: ${play.title}`)
}
