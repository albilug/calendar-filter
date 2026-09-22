"""Generate UniSR calendars: Orario takes precedence over Blackboard."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event
from courses import COURSES, detect_course
from .unisr_fetch import fetch_ics
from .orario_unisr import ACTIVE_COURSES, BASE_URL, excluded, fetch_range, is_seminar, params

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://bb.unisr.it/webapps/calendar/calendarFeed/af56165b8375449796cccade61ccbdfa/learn.ics'
ROME = ZoneInfo('Europe/Rome')
START_DATE = date(2026, 9, 23)


def event_course(event):
    return str(event.get('X-UNISR-COURSE', '')) or detect_course(
        str(event.get('DESCRIPTION', '')) + ' ' + str(event.get('SUMMARY', '')))


def relevant_source(source, start):
    filtered = deepcopy(source)
    selected = []
    for event in filtered.walk('VEVENT'):
        text = str(event.get('SUMMARY', '')) + ' ' + str(event.get('DESCRIPTION', ''))
        beginning = event.decoded('DTSTART', None)
        if isinstance(beginning, datetime):
            beginning = beginning.astimezone(ROME).date() if beginning.tzinfo else beginning.date()
        if not beginning or beginning < start or excluded(text):
            continue
        seminar = is_seminar(text)
        course = event_course(event)
        if seminar:
            # Blackboard belongs to this student's feed; generic seminar titles
            # are retained, while website rows additionally validate degree/year.
            replace(event, 'X-UNISR-KIND', 'SEMINAR')
            replace(event, 'X-UNISR-COURSE', 'seminars')
            if str(event.get('SUMMARY', '')).lower().startswith('aula'):
                replace(event, 'LOCATION', str(event['SUMMARY']))
                replace(event, 'SUMMARY', str(event.get('DESCRIPTION', 'Seminario')))
        elif course not in ACTIVE_COURSES:
            continue
        replace(event, 'X-UNISR-SOURCE', 'BLACKBOARD')
        selected.append(event)
    filtered.subcomponents = [c for c in filtered.subcomponents if c.name != 'VEVENT'] + selected
    return filtered


def subject(event):
    course = event_course(event)
    if course != 'seminars':
        return course
    title = re.sub(r'\(.*?\)', '', str(event.get('SUMMARY', '')))
    title = re.sub(r'^(seminario|seminar|workshop):\s*', '', title, flags=re.I)
    return 'seminars:' + ' '.join(re.findall(r'\w+', title.lower()))


def prioritize_orario(source, rows, state):
    """Overlay Orario onto Blackboard without interpreting empty days as deletion."""
    registry = state.setdefault('orario_ids', {})
    aliases = state.setdefault('official_aliases', {})
    bb = [deepcopy(e) for e in source.walk('VEVENT')]
    site = []
    for row in rows:
        e = Event()
        for prop, key in [('DTSTART', 'start'), ('DTEND', 'end')]:
            e.add(prop, datetime.fromisoformat(row['date'] + 'T' + row[key]).replace(tzinfo=ROME))
        e.add('SUMMARY', row['title'])
        e.add('DESCRIPTION', row['title'])
        e.add('LOCATION', row['location'])
        e.add('X-UNISR-COURSE', row['course'])
        e.add('X-UNISR-SOURCE', 'ORARIO')
        if row['course'] == 'seminars' or is_seminar(row['title']):
            replace(e, 'X-UNISR-COURSE', 'seminars')
            e.add('X-UNISR-KIND', 'SEMINAR')
        from urllib.parse import urlencode
        e.add('URL', BASE_URL + '?' + urlencode(params(date.fromisoformat(row['date']))))
        site.append(e)
    remaining = {i: [span(e)] for i, e in enumerate(bb) if span(e)}
    used_uids, results, replaced = set(), [], []
    # Build groups before mutation: one site's updated time can replace one BB
    # lesson even without overlap, but multiple same-day sessions need overlap.
    for e in site:
        a, b = span(e)
        group = subject(e) + '|' + a.date().isoformat()
        same_bb = [i for i, old in enumerate(bb) if span(old) and subject(old) == subject(e)
                   and span(old)[0].date() == a.date() and not old.get('RRULE') and not old.get('RECURRENCE-ID')]
        same_site = [s for s in site if subject(s) == subject(e) and span(s)[0].date() == a.date()]
        candidates = [i for i in same_bb if max(a, span(bb[i])[0]) < min(b, span(bb[i])[1])]
        whole = len(same_bb) == len(same_site) == 1
        if whole:
            candidates = same_bb
        signature = group + '|' + a.strftime('%H:%M')
        saved = registry.get(signature)
        if not saved and len(same_site) == 1:
            previous = [v for v in registry.values() if v['group'] == group]
            previous_uids = {v['uid'] for v in previous}
            if len(previous_uids) == 1:
                saved = previous[0]
        candidates_uids = [str(bb[i]['UID']) for i in candidates if str(bb[i]['UID']) not in used_uids]
        uid = (saved['uid'] if saved else candidates_uids[0] if candidates_uids else
               'orario-' + hashlib.sha256(signature.encode()).hexdigest()[:24] + '@unisr')
        if uid in used_uids:
            raise ValueError('Ambiguous simultaneous Orario events; refusing duplicate UIDs')
        registry[signature] = {'group': group, 'uid': uid}
        used_uids.add(uid)
        e.add('UID', uid)
        for i in candidates:
            remaining[i] = [] if whole else subtract(remaining[i], (a, b))
            old_key = event_key(bb[i])
            if whole:
                aliases[old_key] = uid
            replaced.append({'orario_uid': uid, 'blackboard_key': old_key})
        results.append(e)
    for i, e in enumerate(bb):
        if i not in remaining:
            results.append(e)
            continue
        for a, b in remaining[i]:
            part = deepcopy(e)
            if event_key(e) in aliases:
                replace(part, 'UID', aliases[event_key(e)])
            if (a, b) != span(e):
                replace(part, 'DTSTART', a)
                replace(part, 'DTEND', b)
                part.pop('DURATION', None)
            if str(part['UID']) in used_uids:
                replace(part, 'UID', str(part['UID']) + '-remaining-' + a.strftime('%H%M'))
            results.append(part)
    combined = deepcopy(source)
    combined.subcomponents = [c for c in combined.subcomponents if c.name != 'VEVENT'] + results
    return combined, state, replaced


def load_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else deepcopy(default)


def replace(event, key, value):
    event.pop(key, None)
    event.add(key, value)


def span(event):
    start = event.decoded('DTSTART', None)
    end = event.decoded('DTEND', None)
    if isinstance(start, datetime) and end is None and event.get('DURATION'):
        end = start + event.decoded('DURATION')
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    return tuple(d.replace(tzinfo=ROME) if d.tzinfo is None else d.astimezone(ROME) for d in (start, end))


def session_span(session):
    return tuple(datetime.fromisoformat(session['date'] + 'T' + session[k]).replace(tzinfo=ROME)
                 for k in ('start', 'end'))


def event_key(event):
    uid = str(event.get('UID', ''))
    if not uid:
        raise ValueError('Blackboard event without UID')
    rid = event.get('RECURRENCE-ID')
    return uid + ('|' + rid.to_ical().decode() if rid is not None else '')


def subtract(intervals, cut):
    result = []
    for start, end in intervals:
        if cut[1] <= start or cut[0] >= end:
            result.append((start, end))
        else:
            if start < cut[0]:
                result.append((start, cut[0]))
            if cut[1] < end:
                result.append((cut[1], end))
    return result


def merge(source, provisional, state, overrides=None):
    """Return events, updated persistent state, and an inspectable sync report.

    Only overlap or a unique same-day, equal-duration session is auto-matched.
    Saved Blackboard identities continue matching after date changes. Coverage
    refers to the original PDF slot, so changes never resurrect stale PDF times.
    """
    state = deepcopy(state)
    links = state.setdefault('links', {})
    published_pdf = set(state.get('published_pdf', []))
    overrides = overrides or {}
    sessions = {s['id']: s for s in provisional['sessions']}
    if len(sessions) != len(provisional['sessions']):
        raise ValueError('Duplicate provisional session IDs')
    for s in sessions.values():
        if s['course'] not in COURSES or session_span(s)[1] <= session_span(s)[0]:
            raise ValueError(f'Invalid session {s}')
    suppressed = set(overrides.get('suppress', []))
    if suppressed - sessions.keys():
        raise ValueError('Unknown suppressed provisional ID')
    official = source.walk('VEVENT')
    keys = [event_key(e) for e in official]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate Blackboard UID/RECURRENCE-ID')
    report = {'matched': [], 'review': [], 'missing_previously_matched': [], 'provisional': []}
    courses = {event_key(e): event_course(e) for e in official}
    spans = {event_key(e): span(e) for e in official}
    for event in official:
        key = event_key(event)
        course, times = courses[key], spans[key]
        explicit = overrides.get('matches', {}).get(key)
        if key in links and explicit is None:
            # Later uploads may extend a previously partial official block.
            if times:
                for pid, covered in links[key]['coverage'].items():
                    if pid not in sessions:
                        continue
                    a, b = session_span(sessions[pid])
                    if max(a, times[0]) < min(b, times[1]):
                        old_a, old_b = (datetime.fromisoformat(d) for d in covered)
                        links[key]['coverage'][pid] = [min(old_a, max(a, times[0])).isoformat(), max(old_b, min(b, times[1])).isoformat()]
            continue
        previous_link = links.pop(key, None) if explicit is not None else None
        if explicit is not None:
            if any(pid not in sessions for pid in explicit):
                raise ValueError(f'Unknown provisional ID in override {key}')
            candidates = explicit
            full = True
        elif not course or not times or event.get('RRULE') or event.get('RECURRENCE-ID'):
            continue
        else:
            same_day = [pid for pid, s in sessions.items() if pid not in suppressed
                        and s['course'] == course and session_span(s)[0].date() == times[0].date()]
            candidates = [pid for pid in same_day if max(session_span(sessions[pid])[0], times[0]) < min(session_span(sessions[pid])[1], times[1])]
            full = False
            if not candidates and len(same_day) == 1:
                other = [k for k in keys if courses[k] == course and spans[k] and spans[k][0].date() == times[0].date()]
                pspan = session_span(sessions[same_day[0]])
                if len(other) == 1 and times[1] - times[0] == pspan[1] - pspan[0]:
                    candidates, full = same_day, True
        if not candidates:
            if course in {s['course'] for s in sessions.values()}:
                report['review'].append({'blackboard_key': key, 'course': course,
                    'start': times[0].isoformat() if times else None,
                    'reason': 'Nessun abbinamento sicuro al PDF; evento ufficiale mantenuto.'})
            continue
        coverage = {}
        for pid in candidates:
            a, b = session_span(sessions[pid])
            coverage[pid] = [d.isoformat() for d in ((a, b) if full else (max(a, times[0]), min(b, times[1])))]
        first_pid = candidates[0]
        proposed_uid = first_pid + '@unisr-provisional'
        used = {link['uid'] for link in links.values()}
        remainder_uid = (first_pid + '-remaining-' +
                         datetime.fromisoformat(coverage[first_pid][0]).strftime('%H%M') +
                         '@unisr-provisional')
        if remainder_uid in state.get('versions', {}) and remainder_uid not in used:
            proposed_uid = remainder_uid
        # A split official session gets its own UID; the first keeps the PDF UID.
        uid = (previous_link['uid'] if previous_link else
               proposed_uid if first_pid in published_pdf and proposed_uid not in used else str(event['UID']))
        links[key] = {'uid': uid, 'coverage': coverage}

    remaining = {pid: [session_span(s)] for pid, s in sessions.items() if pid not in suppressed}
    for key, link in links.items():
        for pid, covered in link['coverage'].items():
            if pid in remaining:
                remaining[pid] = subtract(remaining[pid], tuple(datetime.fromisoformat(d) for d in covered))
        if key not in keys:
            report['missing_previously_matched'].append(key)
    output = []
    for original in official:
        event = deepcopy(original)
        key = event_key(original)
        course = courses[key]
        if key in links:
            replace(event, 'UID', links[key]['uid'])
            report['matched'].append({'blackboard_key': key, 'pdf_ids': list(links[key]['coverage'])})
        if course:
            room = str(event.get('SUMMARY', ''))
            if room.lower().startswith('aula') and not event.get('LOCATION'):
                event.add('LOCATION', room)
            if course != 'seminars':
                replace(event, 'SUMMARY', COURSES[course][1])
            replace(event, 'X-UNISR-COURSE', course)
        if not event.get('X-UNISR-SOURCE'):
            replace(event, 'X-UNISR-SOURCE', 'BLACKBOARD')
        output.append(event)
    for pid, intervals in remaining.items():
        s = sessions[pid]
        for start, end in intervals:
            e = Event()
            # Preserve the original UID until a partial official event consumes it.
            uid = pid + '@unisr-provisional'
            if any(link['uid'] == uid for link in links.values()):
                uid = pid + '-remaining-' + start.strftime('%H%M') + '@unisr-provisional'
            e.add('UID', uid)
            e.add('DTSTART', start.astimezone(timezone.utc))
            e.add('DTEND', end.astimezone(timezone.utc))
            e.add('SUMMARY', '⏳ Provvisorio · ' + COURSES[s['course']][1])
            e.add('DESCRIPTION', f"{s['detail']}\nOrario provvisorio dal PDF {provisional['source']}, pagina {s['page']}.\nAula non specificata; verificare Blackboard.")
            e.add('STATUS', 'TENTATIVE')
            e.add('X-UNISR-SOURCE', 'PDF')
            e.add('X-UNISR-COURSE', s['course'])
            output.append(e)
            report['provisional'].append(pid)
            published_pdf.add(pid)
    state['published_pdf'] = sorted(published_pdf)
    return output, state, report


def revision(events, state):
    """Increment SEQUENCE only when content changes, keeping output idempotent."""
    versions = state.setdefault('versions', {})
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for event in events:
        key = event_key(event)
        body = deepcopy(event)
        for prop in ('DTSTAMP', 'LAST-MODIFIED', 'SEQUENCE'):
            body.pop(prop, None)
        digest = hashlib.sha256(body.to_ical()).hexdigest()
        previous = versions.get(key)
        if previous and previous['hash'] == digest:
            data = previous
        else:
            data = {'hash': digest, 'sequence': max(int(event.get('SEQUENCE', 0)), previous['sequence'] + 1 if previous else 0), 'modified': now.isoformat()}
            versions[key] = data
        replace(event, 'SEQUENCE', data['sequence'])
        replace(event, 'DTSTAMP', datetime.fromisoformat(data['modified']))
        replace(event, 'LAST-MODIFIED', datetime.fromisoformat(data['modified']))


def calendar_bytes(source, events, name=None):
    cal = deepcopy(source)
    cal.subcomponents = [c for c in cal.subcomponents if c.name != 'VEVENT']
    cal.pop('METHOD', None)
    if name:
        replace(cal, 'X-WR-CALNAME', name)
        replace(cal, 'X-WR-TIMEZONE', 'Europe/Rome')
        replace(cal, 'X-PUBLISHED-TTL', 'PT6H')
    for event in events:
        cal.add_component(deepcopy(event))
    return cal.to_ical()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(content)
    temporary.replace(path)


def generate_all(root=ROOT, source_path=None, orario_cache_only=False):
    blackboard_error = None
    try:
        source = Calendar.from_ical(Path(source_path).read_bytes() if source_path else fetch_ics(URL))
    except SystemExit as exc:
        blackboard_error = str(exc)
        cached_bb = root / 'data' / 'blackboard_cache.ics'
        if cached_bb.exists():
            source = Calendar.from_ical(cached_bb.read_bytes())
        else:
            source = Calendar()
            source.add('VERSION', '2.0')
            source.add('PRODID', '-//UniSR calendar-filter//EN')
    state = load_json(root / 'data' / 'sync_state.json', {})
    overrides = load_json(root / 'archive' / 'pdf' / 'sync_overrides.json', {})
    config = load_json(root / 'calendar_config.json', {})
    use_pdf = config.get('use_provisional_pdf', False)
    provisional = (load_json(root / 'archive' / 'pdf' / 'provisional_events.json', {'source': '', 'sessions': []})
                   if use_pdf else {'source': '', 'sessions': []})
    if not use_pdf:
        overrides = {}
    start = date.fromisoformat(config.get('start_date', START_DATE.isoformat()))
    today = datetime.now(ROME).date()
    last_pdf = max((date.fromisoformat(s['date']) for s in provisional['sessions']), default=start)
    through = max(last_pdf, today + timedelta(days=config.get('lookahead_days', 90)))
    cache = load_json(root / 'data' / 'orario_cache.json', {})
    if orario_cache_only:
        rows = [row for day, value in cache.get('days', {}).items()
                if start <= date.fromisoformat(day) <= through for row in value['events']]
        orario_report = {'mode': 'cache_only', 'from': start.isoformat(), 'through': through.isoformat(), 'failures': []}
    else:
        rows, cache, orario_report = fetch_range(start, through, cache, today=today, progress=True)
    source = relevant_source(source, start)
    blackboard_snapshot = calendar_bytes(source, source.walk('VEVENT'))
    source, state, replaced = prioritize_orario(source, rows, state)
    events, state, report = merge(source, provisional, state, overrides)
    # Keep the complete PDF in memory for persisted associations/overrides, but
    # publish only the requested date range and selected courses/seminars.
    events = [e for e in events if (span(e)[0].date() if span(e) else e.decoded('DTSTART')) >= start
              and event_course(e) in ACTIVE_COURSES | {'seminars'}
              and not excluded(str(e.get('SUMMARY', '')) + ' ' + str(e.get('DESCRIPTION', '')))]
    visible_pdf = {str(e['UID']) for e in events if e.get('X-UNISR-SOURCE') == 'PDF'}
    report['provisional'] = [pid for pid in report['provisional']
                             if any(uid.startswith(pid + '@') or uid.startswith(pid + '-remaining-') for uid in visible_pdf)]
    report['orario'] = orario_report
    report['orario_over_blackboard'] = replaced
    report['blackboard_only'] = [event_key(e) for e in events if e.get('X-UNISR-SOURCE') == 'BLACKBOARD']
    report['priority'] = ['ORARIO', 'BLACKBOARD'] + (['PDF'] if use_pdf else [])
    report['pdf_enabled'] = use_pdf
    report['blackboard_error'] = blackboard_error
    report['override_notes'] = overrides.get('notes', {})
    report['missing_previously_matched'] = [key for key in report['missing_previously_matched']
        if any(date.fromisoformat(covered[0][:10]) >= start
               for covered in state['links'][key]['coverage'].values())]
    revision(events, state)
    files = {'shared_calendar.ics': events,
             'filtered_calendar.ics': events}
    files.update({course + '.ics': [e for e in events if str(e.get('X-UNISR-COURSE', '')) == course] for course in COURSES})
    payloads = {name: calendar_bytes(source, selected,
        COURSES[name[:-4]][1] if name[:-4] in COURSES else 'Health Informatics · Secondo anno')
        for name, selected in files.items()}
    for name, content in payloads.items():
        parsed = Calendar.from_ical(content)
        ids = [event_key(e) for e in parsed.walk('VEVENT')]
        if len(ids) != len(set(ids)):
            raise ValueError(f'Duplicate output event identity in {name}')
    report['counts'] = {course: dict(Counter(str(e['X-UNISR-SOURCE']) for e in files[course + '.ics'])) for course in COURSES}
    for name, content in payloads.items():
        atomic_write(root / 'calendars' / name, content)
        if name in ('shared_calendar.ics', 'filtered_calendar.ics'):
            atomic_write(root / name, content)  # Preserve existing subscription URLs.
    if blackboard_error is None:
        atomic_write(root / 'data' / 'blackboard_cache.ics', blackboard_snapshot)
    for name, data in [('sync_state.json', state), ('sync_report.json', report), ('orario_cache.json', cache)]:
        atomic_write(root / 'data' / name, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())
    print(f"Calendari aggiornati: {len(report['matched'])} eventi abbinati, {len(report['provisional'])} provvisori, {len(report['review'])} da verificare.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', help='Use a local Blackboard ICS for an offline run')
    parser.add_argument('--orario-cache-only', action='store_true', help='Use the saved Orario snapshot without HTTP requests (verification only)')
    args = parser.parse_args()
    generate_all(source_path=args.source, orario_cache_only=args.orario_cache_only)
