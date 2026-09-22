"""Single entry point for downloading sources and publishing subscription files."""
import argparse
from unisr_calendar.calendar_sync import generate_all

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--orario-cache-only', action='store_true', help='Offline verification using the saved Orario snapshot')
    args = parser.parse_args()
    generate_all(orario_cache_only=args.orario_cache_only)
