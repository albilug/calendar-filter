import unittest
from copy import deepcopy
from datetime import datetime, timezone
from icalendar import Calendar, Event
from unisr_calendar.calendar_sync import merge, revision, ROME, span


def pdf():
    return {'source': 'test.pdf', 'sessions': [dict(id='lesson-1', course='wearable_devices',
        date='2026-10-26', start='09:00', end='13:00', detail='Wearable devices', page=1)]}


def feed(start='2026-10-26T09:00', end='2026-10-26T13:00', uid='official-1'):
    c = Calendar()
    c.add('VERSION', '2.0')
    e = Event()
    e.add('UID', uid)
    e.add('DTSTART', datetime.fromisoformat(start).replace(tzinfo=ROME))
    e.add('DTEND', datetime.fromisoformat(end).replace(tzinfo=ROME))
    e.add('SUMMARY', 'Aula PASTEUR')
    e.add('DESCRIPTION', 'Wearable devices (DOCENTE)')
    c.add_component(e)
    return c


class SyncTests(unittest.TestCase):
    def test_provisional_confirmed_and_moved_identity(self):
        events, state, _ = merge(Calendar(), pdf(), {})
        uid = str(events[0]['UID'])
        revision(events, state)
        events, state, _ = merge(feed(), pdf(), state)
        revision(events, state)
        self.assertEqual(len(events), 1)
        self.assertEqual(str(events[0]['UID']), uid)
        self.assertNotIn('Provvisorio', str(events[0]['SUMMARY']))
        self.assertEqual(str(events[0]['LOCATION']), 'Aula PASTEUR')
        self.assertEqual(int(events[0]['SEQUENCE']), 1)
        events, state, _ = merge(feed('2026-10-28T14:00', '2026-10-28T18:00'), pdf(), state)
        self.assertEqual(len(events), 1)
        self.assertEqual(str(events[0]['UID']), uid)
        self.assertEqual(span(events[0])[0].day, 28)

    def test_first_official_keeps_existing_blackboard_uid(self):
        events, _, _ = merge(feed(), pdf(), {})
        self.assertEqual(str(events[0]['UID']), 'official-1')

    def test_missing_official_does_not_restore_old_pdf(self):
        _, state, _ = merge(feed(), pdf(), {})
        events, _, report = merge(Calendar(), pdf(), state)
        self.assertEqual(events, [])
        self.assertEqual(report['missing_previously_matched'], ['official-1'])

    def test_partial_and_later_extension(self):
        _, state, _ = merge(Calendar(), pdf(), {})
        events, state, _ = merge(feed(end='2026-10-26T11:00'), pdf(), state)
        self.assertEqual(len(events), 2)
        tentative = next(e for e in events if e.get('STATUS') == 'TENTATIVE')
        self.assertEqual(span(tentative)[0].hour, 11)
        self.assertEqual(len({str(e['UID']) for e in events}), 2)
        events, _, _ = merge(feed(), pdf(), state)
        self.assertEqual(len(events), 1)

    def test_split_official_blocks(self):
        c = feed(end='2026-10-26T11:00')
        c.add_component(feed(start='2026-10-26T11:00', uid='official-2').walk('VEVENT')[0])
        events, _, report = merge(c, pdf(), {})
        self.assertEqual(len(events), 2)
        self.assertFalse(report['provisional'])

    def test_later_confirmation_keeps_remainder_uid(self):
        events, state, _ = merge(Calendar(), pdf(), {})
        revision(events, state)
        c = feed(end='2026-10-26T11:00')
        events, state, _ = merge(c, pdf(), state)
        revision(events, state)
        remainder = next(e for e in events if e.get('STATUS') == 'TENTATIVE')
        uid = str(remainder['UID'])
        c.add_component(feed(start='2026-10-26T11:00', uid='official-2').walk('VEVENT')[0])
        events, _, _ = merge(c, pdf(), state)
        self.assertIn(uid, {str(e['UID']) for e in events})
        self.assertFalse(any(e.get('STATUS') == 'TENTATIVE' for e in events))

    def test_unknown_move_requires_override(self):
        c = feed('2026-10-27T09:00', '2026-10-27T13:00')
        events, _, report = merge(c, pdf(), {})
        self.assertEqual(len(events), 2)
        self.assertEqual(len(report['review']), 1)
        events, _, _ = merge(c, pdf(), {}, {'matches': {'official-1': ['lesson-1']}})
        self.assertEqual(len(events), 1)

    def test_same_day_time_change(self):
        events, _, _ = merge(feed('2026-10-26T14:00', '2026-10-26T18:00'), pdf(), {})
        self.assertEqual(len(events), 1)

    def test_idempotent_serialization(self):
        events, state, _ = merge(feed(), pdf(), {})
        revision(events, state)
        first = [e.to_ical() for e in events]
        events, state, _ = merge(feed(), pdf(), state)
        revision(events, state)
        self.assertEqual(first, [e.to_ical() for e in events])

    def test_dst_and_unicode_round_trip(self):
        data = pdf()
        data['sessions'].append(dict(data['sessions'][0], id='lesson-2', date='2026-10-19'))
        events, _, _ = merge(Calendar(), data, {})
        hours = [e.decoded('DTSTART').hour for e in events]
        self.assertEqual(hours, [8, 7])
        for e in events:
            parsed = Event.from_ical(e.to_ical())
            self.assertIn('⏳ Provvisorio', str(parsed['SUMMARY']))

    def test_suppress_and_invalid_override(self):
        events, _, _ = merge(Calendar(), pdf(), {}, {'suppress': ['lesson-1']})
        self.assertFalse(events)
        with self.assertRaises(ValueError):
            merge(feed(), pdf(), {}, {'matches': {'official-1': ['wrong-id']}})


if __name__ == '__main__':
    unittest.main()
