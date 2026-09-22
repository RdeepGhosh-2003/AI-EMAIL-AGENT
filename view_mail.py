"""Open the mailbox viewer on the same server as the main dashboard."""
import os
import webbrowser
from pathlib import Path

import requests
import yaml

os.chdir(Path(__file__).resolve().parent)

if __name__ == '__main__':
    with open('config.yaml') as config_file:
        port = yaml.safe_load(config_file).get('dashboard', {}).get('port', 5001)

    dashboard_url = f'http://localhost:{port}'
    inbox_url = f'{dashboard_url}/inbox.html'
    try:
        response = requests.get(f'{dashboard_url}/api/status', timeout=2)
        response.raise_for_status()
    except requests.RequestException:
        from instance_lock import acquire_dashboard_lock
        dashboard_lock = acquire_dashboard_lock()
        if dashboard_lock is None:
            print(f'The dashboard is starting. Open {inbox_url} in a moment.', flush=True)
            raise SystemExit(0)
        from api.server import app
        print(f'My emails: {inbox_url}', flush=True)
        webbrowser.open(inbox_url)
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
    else:
        print(f'My emails: {inbox_url}', flush=True)
        webbrowser.open(inbox_url)
