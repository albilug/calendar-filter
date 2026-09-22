"""Read the public daily UniSR timetable with validated filters and a disk cache."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import time

from bs4 import BeautifulSoup
import requests
from courses import detect_course

BASE_URL = 'https://orario.unisr.it/default.asp'
ACTIVE_COURSES = {'machine_learning', 'human_machine_interaction', 'wearable_devices', 'radiomics'}


def is_seminar(text):
    return bool(re.search(r'\b(seminar\w*|workshop\w*|conference\w*|conferenza|convegno\w*)\b', text, re.I))


def excluded(text):
    return bool(re.search(r'\b(holiday|holidays|exams?|esam[ei]|festivit[aà]|study leave|lunch break)\b', text, re.I))


def params(day):
    return dict(ext='ok', data=day.strftime('%d/%m/%Y'), CDS_ID='10283',
                DAORA='0', ANNO_CORSO='2', id_palazzo='0', lezioni='ok', esami='ok')


def parse_day(html, day):
    soup = BeautifulSoup(html, 'html.parser')
    day_input = soup.find('input', attrs={'name': 'data'})
    if not day_input or day_input.get('value') != day.strftime('%d/%m/%Y'):
        raise ValueError('Orario response does not confirm the requested date')
    for name, value in [('CDS_ID', '10283'), ('ANNO_CORSO', '2')]:
        select = soup.find('select', attrs={'name': name})
        selected = select.find('option', selected=True) if select else None
        if not selected or selected.get('value') != value:
            raise ValueError(f'Orario response does not confirm filter {name}')
    rows, location = [], ''
    timetable_rows = 0
    for tr in soup.find_all('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 4:
            continue
        texts = [' '.join(c.get_text(' ', strip=True).split()) for c in cells]
        if texts[2] == 'Corso di Laurea' and texts[3] == 'anno':
            location = re.sub(r'\s+live$', '', texts[1])
            continue
        clock = re.fullmatch(r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})', texts[0])
        if not clock:
            continue
        timetable_rows += 1
        if 'health informatics' not in texts[2].lower() or texts[3] != '2':
            raise ValueError('Unexpected programme/year in Orario event row')
        title = texts[1]
        if excluded(title):
            continue
        course = detect_course(title)
        if course not in ACTIVE_COURSES and not is_seminar(title):
            continue
        if not location:
            raise ValueError('Orario event without room header')
        clean_title = re.sub(r'^(Lezione|Seminario):\s*', '', title, flags=re.I)
        rows.append(dict(date=day.isoformat(), start=clock[1], end=clock[2],
                         title=clean_title, course=course if course in ACTIVE_COURSES else 'seminars',
                         location=location))
    if timetable_rows == 0 and 'nessun risultato' not in soup.get_text(' ', strip=True).lower():
        raise ValueError('Unrecognized Orario layout; refusing to treat it as an empty day')
    return rows


def fetch_range(start, end, cache, today=None, progress=False):
    """Refresh upcoming days, retain old history and explicitly flag cached fallbacks."""
    today = today or date.today()
    days = cache.setdefault('days', {})
    report = {'from': start.isoformat(), 'through': end.isoformat(), 'failures': [], 'refreshed_days': 0}
    session = requests.Session()
    session.headers['User-Agent'] = 'calendar-filter/2.0'
    current = start
    result = []
    while current <= end:
        key = current.isoformat()
        cached = days.get(key)
        if not cached or current >= today - timedelta(days=7):
            error = None
            for attempt in range(2):
                try:
                    response = session.get(BASE_URL, params=params(current), timeout=(5, 15))
                    response.raise_for_status()
                    rows = parse_day(response.text, current)
                    days[key] = {'events': rows, 'checked': datetime.now(timezone.utc).isoformat()}
                    report['refreshed_days'] += 1
                    error = None
                    break
                except (requests.RequestException, ValueError) as exc:
                    error = str(exc)
                    if attempt == 0:
                        time.sleep(0.5)
            if error:
                report['failures'].append({'date': key, 'error': error, 'used_cache': cached is not None})
            time.sleep(0.05)
        result.extend(days.get(key, {}).get('events', []))
        if progress and (current - start).days % 15 == 0:
            print(f'Orario: checked through {key}, {len(result)} relevant events', flush=True)
        current += timedelta(days=1)
    session.close()
    return result, cache, report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2026-09-23')
    parser.add_argument('--end', required=True)
    parser.add_argument('--cache', default='orario_cache.json')
    args = parser.parse_args()
    path = Path(args.cache)
    cache = json.loads(path.read_text()) if path.exists() else {}
    rows, cache, report = fetch_range(date.fromisoformat(args.start), date.fromisoformat(args.end), cache, progress=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path('tmp/orario_fetch_report.json').write_text(json.dumps(report, indent=2))
    print(f'{len(rows)} events; {len(report["failures"])} failed days')
