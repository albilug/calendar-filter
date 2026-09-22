from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from icalendar import Calendar

from unisr_calendar.calendar_sync import generate_all, prioritize_orario, relevant_source, merge, revision, span
from unisr_calendar.orario_unisr import parse_day, fetch_range
from test_calendar_sync import feed, pdf


def row(start='09:00', end='13:00', day='2026-10-26', title='Wearable devices (docente: CONSOLO)', course='wearable_devices'):
    return dict(date=day, start=start, end=end, title=title, course=course, location='DIBIT1 - Aula NUOVA (piano terra)')


def html(body):
    return '''<input name="data" value="26/10/2026">
    <select name="CDS_ID"><option value="10283" selected>Health Informatics</option></select>
    <select name="ANNO_CORSO"><option value="2" selected>2</option></select>
    <table><tr><td>map</td><td>DIBIT1 - Aula NUOVA</td><td>Corso di Laurea</td><td>anno</td></tr>''' + body + '</table>'


def lesson(text='Lezione: Wearable devices (docente: CONSOLO)'):
    return '<tr><td>09:00-13:00</td><td>' + text + '</td><td>Corso di Laurea Magistrale in Health Informatics</td><td>2</td></tr>'


class OrarioTests(unittest.TestCase):
    def test_generator_ignores_pdf_completely(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            # Invalid input proves the disabled PDF source is not even read.
            (root / 'provisional_events.json').write_text('INVALID JSON')
            (root / 'calendar_config.json').write_text(json.dumps({'start_date':'2026-09-23','use_provisional_pdf':False}))
            (root / 'data' / 'orario_cache.json').write_text(json.dumps({'days': {'2026-10-26': {'events':[row()]}}}))
            source = root / 'data' / 'blackboard_cache.ics'
            source.write_bytes(feed().to_ical())
            generate_all(root=root, orario_cache_only=True)
            events = Calendar.from_ical((root / 'shared_calendar.ics').read_bytes()).walk('VEVENT')
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['X-UNISR-SOURCE'], 'ORARIO')
            self.assertFalse(any(e.get('STATUS') == 'TENTATIVE' for e in events))
            self.assertFalse(json.loads((root/'data'/'sync_report.json').read_text())['pdf_enabled'])

    @patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected HTTP request'))
    def test_offline_generation_never_contacts_blackboard(self, fetch):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'data' / 'orario_cache.json').write_text(json.dumps({'days': {'2026-10-26': {'events':[row()]}}}))
            generate_all(root=root, orario_cache_only=True)
            events = Calendar.from_ical((root / 'shared_calendar.ics').read_bytes()).walk('VEVENT')
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['X-UNISR-SOURCE'], 'ORARIO')
            self.assertFalse(json.loads((root/'data'/'sync_report.json').read_text())['blackboard_enabled'])
            fetch.assert_not_called()

    def test_room_and_priority_over_bb_and_pdf(self):
        source = relevant_source(feed(), date(2026, 9, 23))
        official, state, _ = prioritize_orario(source, [row()], {})
        events, _, _ = merge(official, pdf(), state)
        self.assertEqual(len(events), 1)
        self.assertIn('NUOVA', str(events[0]['LOCATION']))
        self.assertEqual(str(events[0]['X-UNISR-SOURCE']), 'ORARIO')
        self.assertEqual(str(events[0]['UID']), 'official-1')

    def test_changed_time_and_room_keep_uid(self):
        source, state, _ = prioritize_orario(feed(), [row()], {})
        uid = str(source.walk('VEVENT')[0]['UID'])
        source, _, _ = prioritize_orario(feed(), [row(start='14:00', end='18:00')], state)
        events = source.walk('VEVENT')
        self.assertEqual(len(events), 1)
        self.assertEqual(str(events[0]['UID']), uid)
        self.assertEqual(span(events[0])[0].hour, 14)

    def test_missing_future_day_keeps_pdf(self):
        source, state, _ = prioritize_orario(Calendar(), [], {})
        events, _, _ = merge(source, pdf(), state)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['STATUS'], 'TENTATIVE')

    def test_empty_orario_falls_back_to_blackboard(self):
        source, state, _ = prioritize_orario(feed(), [], {})
        events, _, _ = merge(source, pdf(), state)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['X-UNISR-SOURCE'], 'BLACKBOARD')

    def test_partial_official_preserves_blackboard_remainder(self):
        source, state, _ = prioritize_orario(feed(), [row(end='11:00')], {})
        # One-to-one is an explicit authoritative change of duration.
        self.assertEqual(len(source.walk('VEVENT')), 1)
        source, state, _ = prioritize_orario(feed(), [row(end='10:00'), row(start='11:00',end='13:00')], {})
        events = source.walk('VEVENT')
        self.assertEqual(len(events), 3)
        self.assertEqual(len({str(e['UID']) for e in events}), 3)

    def test_split_site_events_do_not_duplicate_pdf_uids(self):
        events, state, _ = merge(Calendar(), pdf(), {})
        revision(events, state)
        _, state, _ = merge(feed(), pdf(), state)
        source, state, _ = prioritize_orario(feed(), [row(end='11:00'), row(start='11:00')], state)
        events, _, _ = merge(source, pdf(), state)
        self.assertEqual(len(events), 2)
        self.assertEqual(len({str(e['UID']) for e in events}), 2)

    def test_site_published_first_later_bb_and_fallback_same_uid(self):
        source, state, _ = prioritize_orario(Calendar(), [row()], {})
        uid = str(source.walk('VEVENT')[0]['UID'])
        _, state, _ = prioritize_orario(feed(), [row()], state)
        source, _, _ = prioritize_orario(feed(), [], state)
        self.assertEqual(str(source.walk('VEVENT')[0]['UID']), uid)

    def test_parser_and_validation(self):
        rows = parse_day(html(lesson()), date(2026,10,26))
        self.assertEqual(rows[0]['location'], 'DIBIT1 - Aula NUOVA')
        self.assertEqual(rows[0]['course'], 'wearable_devices')
        self.assertEqual(parse_day(html('Nessun risultato'), date(2026,10,26)), [])
        for bad in [html(''), 'Login required', html(lesson()).replace('value="2" selected','value="1" selected')]:
            with self.assertRaises(ValueError):
                parse_day(bad, date(2026,10,26))

    def test_exams_excluded_seminars_included(self):
        self.assertFalse(parse_day(html(lesson('Esame: Wearable devices')), date(2026,10,26)))
        rows = parse_day(html(lesson('Seminario: AI in clinical practice')), date(2026,10,26))
        self.assertEqual(rows[0]['course'], 'seminars')
        source, state, _ = prioritize_orario(Calendar(), [row(title='AI in clinical practice',course='seminars')], {})
        events, _, _ = merge(source, {'sessions': []}, state)
        self.assertEqual(str(events[0]['SUMMARY']), 'AI in clinical practice')

    def test_blackboard_date_and_scope_filter(self):
        old = relevant_source(feed('2026-09-21T09:00','2026-09-21T13:00'), date(2026,9,23))
        self.assertFalse(old.walk('VEVENT'))
        c = feed()
        e = c.walk('VEVENT')[0]
        e['DESCRIPTION'] = 'EXAMS Wearable devices'
        self.assertFalse(relevant_source(c,date(2026,9,23)).walk('VEVENT'))
        e['DESCRIPTION'] = 'Seminar on research methods'
        selected = relevant_source(c,date(2026,9,23)).walk('VEVENT')
        self.assertEqual(selected[0]['X-UNISR-COURSE'], 'seminars')
        self.assertIn('Seminar',str(selected[0]['SUMMARY']))

    @patch('unisr_calendar.orario_unisr.time.sleep')
    @patch('unisr_calendar.orario_unisr.requests.Session')
    def test_outage_preserves_cache(self, session, sleep):
        import requests
        session.return_value.get.side_effect = requests.ConnectionError('offline')
        cache = {'days': {'2026-10-26': {'events':[row()], 'checked':'old'}}}
        rows, _, report = fetch_range(date(2026,10,26),date(2026,10,26),cache,today=date(2026,10,26))
        self.assertEqual(len(rows),1)
        self.assertTrue(report['failures'][0]['used_cache'])


if __name__ == '__main__':
    unittest.main()
