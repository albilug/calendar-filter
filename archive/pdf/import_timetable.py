"""One-time import of the supplied Year 2 2026/27 PDF; not a generic PDF parser."""
import argparse
import sys
import json
import re
from datetime import date, datetime
from pathlib import Path

import pdfplumber
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from courses import detect_course

MONTHS = {name: i for i, name in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'], 1)}


def extract(path):
    slots = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for table in page.extract_tables():
                if not table[0][0].startswith('WEEK'):
                    continue
                dates = []
                for heading in table[0][1:]:
                    match = re.search(r'(' + '|'.join(MONTHS) + r')\s*(\d+)', heading)
                    if not match:
                        raise ValueError(f'Unrecognized date: {heading}')
                    month = MONTHS[match[1]]
                    dates.append(date(2026 if month >= 9 else 2027, month, int(match[2])))
                for row in table[1:]:
                    times = re.fullmatch(r'(\d+:\d+)-(\d+:\d+)', row[0] or '')
                    if not times:
                        continue
                    for day, cell in zip(dates, row[1:]):
                        text = ' '.join((cell or '').split())
                        course = detect_course(text)
                        if course not in ('machine_learning', 'human_machine_interaction', 'wearable_devices', 'radiomics'):
                            continue
                        # Remove total course-hour labels printed only in the first week.
                        detail = re.sub(r'\s*(?:60\+36|48|24)\b', '', text)
                        slots.append(dict(course=course, date=day.isoformat(),
                            start=datetime.strptime(times[1], '%H:%M').strftime('%H:%M'),
                            end=times[2], detail=detail, page=page_no))
    sessions = []
    for slot in sorted(slots, key=lambda s: (s['date'], s['course'], s['start'])):
        if sessions and all(sessions[-1][k] == slot[k] for k in ('date', 'course', 'detail')) and sessions[-1]['end'] == slot['start']:
            sessions[-1]['end'] = slot['end']
        else:
            sessions.append(slot.copy())
    for session in sessions:
        session['id'] = f"pdf-2026-{session['course']}-{session['date']}-{session['start'].replace(':', '')}"
    return {'source': Path(path).name, 'timezone': 'Europe/Rome', 'sessions': sessions}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf')
    parser.add_argument('--output', default='provisional_events.json')
    args = parser.parse_args()
    target = Path(args.output)
    if target.exists():
        parser.error('Output already exists; use --output with a new filename and review before replacing.')
    data = extract(args.pdf)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Imported {len(data['sessions'])} sessions into {target}")
