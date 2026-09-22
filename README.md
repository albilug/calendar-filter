# Calendari Health Informatics · Secondo anno

Calendari per Apple Calendar aggiornati automaticamente solo da **Orario UniSR**.
Blackboard e PDF sono esclusi. Sono inclusi corsi e seminari
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
Gli URL degli abbonamenti restano invariati anche dopo il cambio della fonte.

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

- Unica fonte: Orario UniSR, con i filtri Health Informatics (`CDS_ID=10283`), anno 2.
  Ogni risposta è verificata per data e filtri prima di leggere le lezioni.
- Date, orari, aule e docenti provengono esclusivamente dal sito. Non vengono più
  consultati Blackboard, la sua cache o il PDF, neppure come fonti alternative.
- Seminari e workshop mantengono il titolo completo e devono appartenere al corso
  di laurea e anno selezionati. Festività ed esami restano esclusi.
- In caso di errore del sito si conserva l'ultima risposta valida di Orario per
  quel giorno, segnalando il problema in `data/sync_report.json`.
- Una risposta valida senza lezioni rimuove dal calendario quelle precedenti per
  quel giorno; la cache viene aggiornata. Non vengono aggiunti eventi provvisori.
- Gli identificativi pubblicati sono mantenuti. Le vecchie associazioni salvate
  conservano solo l'identità ICS, senza importare contenuti da altre fonti.
- Gli orari sono esportati in UTC; Apple Calendar li mostra nel fuso locale,
  rispettando il cambio fra ora legale e solare.

`calendar_config.json` imposta il controllo fino a oggi + `lookahead_days` (90).
L'orizzonte avanza automaticamente. Sono riletti tutti i giorni futuri e gli ultimi
sette giorni; lo storico più vecchio viene dalla cache. Per ricontrollare una data
storica eliminare solo quella voce da `data/orario_cache.json` e rieseguire.

## Verifica offline

```sh
python -m unittest discover -s tests -v
python sync_calendars.py --orario-cache-only
```

[Guida Apple agli abbonamenti iCloud](https://support.apple.com/en-my/102301).
