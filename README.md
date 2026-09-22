# Calendari Health Informatics · Secondo anno

Calendari per Apple Calendar aggiornati automaticamente da **Orario UniSR**, con
**Blackboard** come fonte secondaria. Il PDF è escluso. Sono inclusi corsi e seminari
dal **23 settembre 2026**; esami e festività sono esclusi.

## Abbonamenti Apple Calendar

Usare **File → Nuovo abbonamento calendario** su Mac e incollare uno degli URL.
Scegliere **iCloud** per ritrovare l'abbonamento sugli altri dispositivi e impostare
l'aggiornamento automatico, per esempio ogni ora. I file pubblicati vengono
rigenerati ogni **6 ore** da GitHub Actions; gli aggiornamenti non sono istantanei.

| Calendario | URL da incollare |
| --- | --- |
| Tutti i corsi e seminari | https://raw.githubusercontent.com/albilug/calendar-filter/main/calendars/shared_calendar.ics |
| Machine Learning | https://raw.githubusercontent.com/albilug/calendar-filter/main/calendars/machine_learning.ics |
| Human Machine Interaction | https://raw.githubusercontent.com/albilug/calendar-filter/main/calendars/human_machine_interaction.ics |
| Wearable Devices | https://raw.githubusercontent.com/albilug/calendar-filter/main/calendars/wearable_devices.ics |
| Radiomics | https://raw.githubusercontent.com/albilug/calendar-filter/main/calendars/radiomics.ics |
| Seminari | https://raw.githubusercontent.com/albilug/calendar-filter/main/calendars/seminars.ics |

Abbonarsi **al calendario completo oppure ai singoli**, per evitare duplicati.
Aprire/importare un file scaricato una volta non crea una sincronizzazione.
La [pagina abbonamenti](https://albilug.github.io/calendar-filter/) offre anche i
pulsanti `webcal` per aprire direttamente l'abbonamento in Apple Calendar.

I feed usano il contenuto diretto del ramo `main`, quindi non dipendono da una nuova
pubblicazione di GitHub Pages a ogni aggiornamento dei dati. I vecchi URL
`shared_calendar.ics` e `filtered_calendar.ics` nella radice rimangono compatibili.

## Struttura

```text
sync_calendars.py       unico comando di aggiornamento
courses.py             nomi dei corsi e titoli brevi
calendar_config.json   data iniziale e orizzonte di controllo
calendars/             ICS pubblicati per gli abbonamenti
data/                  cache, stato persistente e report
unisr_calendar/        codice delle fonti e della sincronizzazione
tests/                 verifiche automatiche
archive/pdf/           vecchia importazione PDF, non utilizzata
```

I due ICS nella radice sono copie compatibili con i precedenti abbonamenti.
Non cancellare `data/sync_state.json`: conserva l'identità degli eventi pubblicati.
`data/blackboard_cache.ics` è una copia tecnica filtrata, non un abbonamento.

## Esecuzione locale

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python sync_calendars.py
```

Non serve tenere acceso il computer: una volta pubblicato il progetto, il workflow
`.github/workflows/update-calendars.yml` aggiorna e pubblica i file ogni 6 ore.
Può essere avviato anche da **GitHub → Actions → Update Calendars → Run workflow**.
Gli orari pianificati possono subire ritardi del servizio GitHub.

## Regole di sincronizzazione

- Orario UniSR è letto con i filtri Health Informatics (`CDS_ID=10283`), anno 2.
  Ogni risposta è verificata per data e filtri prima di leggere le lezioni.
- Orario prevale su Blackboard per data, orario, aula e docente degli eventi abbinati.
  Blackboard aggiunge eventi pertinenti non trovati sul sito.
- Il confronto usa corso, giorno e sovrapposizione. Una sola lezione per corso/giorno
  in entrambe le fonti è abbinata anche se cambia orario. Con più lezioni vengono
  sostituite solo le porzioni sovrapposte.
- Seminari/workshop mantengono il titolo completo. Sul sito devono appartenere al
  corso di laurea e anno selezionati; su Blackboard provengono dal feed personale.
- Il sito non espone ID stabili delle prenotazioni. Spostamenti tra giorni diversi
  potrebbero non essere riconosciuti automaticamente: verificare `blackboard_only`
  in `data/sync_report.json` per possibili vecchie date o aggiunte.
- Una pagina vuota non dimostra una cancellazione di eventi di Blackboard.
- Se una fonte non risponde si usa la sua ultima copia valida, segnalando il
  problema nel report. Le copie potrebbero contenere dati superati.
- Gli UID sono mantenuti e `SEQUENCE` aumenta solo quando cambia un evento.

`calendar_config.json` imposta il controllo fino a oggi + `lookahead_days` (90).
L'orizzonte avanza automaticamente. Sono riletti tutti i giorni futuri e gli ultimi
sette giorni; lo storico più vecchio viene dalla cache. Per ricontrollare una data
storica eliminare solo quella voce da `data/orario_cache.json` e rieseguire.

Il PDF resta disabilitato (`use_provisional_pdf: false`); i suoi vecchi abbinamenti
possono conservare gli UID, ma non producono date né eventi provvisori.

## Verifica offline

```sh
python -m unittest discover -s tests -v
python sync_calendars.py --source data/blackboard_cache.ics --orario-cache-only
```

[Guida Apple agli abbonamenti iCloud](https://support.apple.com/en-my/102301).
