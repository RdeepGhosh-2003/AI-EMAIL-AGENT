"""Connect accounts without starting inbox processing or sending mail."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('provider', nargs='?', choices=['outlook'], default='outlook')
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    try:
        from outlook.auth import get_outlook_token
        get_outlook_token(interactive=True)
    except Exception as error:
        parser.exit(1, f'Connection failed: {error}\n')
    print(f'{args.provider.capitalize()} authorization saved. No inbox processing started.')


if __name__ == '__main__':
    main()
