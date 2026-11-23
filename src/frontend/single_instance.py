"""Keep one Linum desktop window open and raise it on demand."""

import errno
import socket
import sys
import time


ADDRESS = ("127.0.0.1", 42935)


def claim_window():
    listener = socket.socket()
    try:
        if sys.platform == "win32":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(ADDRESS)
        listener.listen()
        listener.setblocking(False)
        return listener
    except OSError as error:
        listener.close()
        if error.errno not in (errno.EADDRINUSE, 10048, 10013):
            raise
        # Another launch may have bound its socket just before calling listen().
        for attempt in range(5):
            try:
                with socket.create_connection(ADDRESS, timeout=0.2):
                    return None
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.05)


def watch_for_activation(app, listener):
    try:
        connection, _ = listener.accept()
    except BlockingIOError:
        pass
    else:
        connection.close()
        topmost = app.attributes("-topmost")
        app.deiconify()
        app.attributes("-topmost", True)
        app.lift()
        app.focus_force()
        app.after_idle(app.attributes, "-topmost", topmost)
    app.after(200, watch_for_activation, app, listener)
