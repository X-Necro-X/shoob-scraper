import os
import socket
import sys
import threading
import time
from pathlib import Path


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _wait_for_flask(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _setup_paths() -> None:
    if getattr(sys, 'frozen', False):
        meipass = Path(sys._MEIPASS)
        exe_dir = Path(sys.executable).parent
        os.chdir(exe_dir)
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(meipass / 'browsers')
        os.environ['SHOOB_BASE_DIR'] = str(exe_dir)


def main() -> None:
    _setup_paths()

    port = _find_free_port()

    from app import app as flask_app

    flask_thread = threading.Thread(
        target=lambda: flask_app.run(
            host='127.0.0.1',
            port=port,
            use_reloader=False,
            threaded=True,
        ),
        daemon=True,
    )
    flask_thread.start()

    if not _wait_for_flask(port):
        sys.exit('Flask did not start within 5 seconds.')

    import webview
    webview.create_window('Shoob', f'http://127.0.0.1:{port}/', width=1000, height=700, resizable=True)
    webview.start()


if __name__ == '__main__':
    main()
