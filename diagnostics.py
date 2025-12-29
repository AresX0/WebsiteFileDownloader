"""Diagnostic helpers: capture thread stacks and write dumps safely.

This module provides utility functions used by `epstein_downloader_gui.py` to
capture thread stacks, write them to disk safely (with fallbacks), and log
via a provided logger only when its handlers appear open.
"""

import sys
import threading
import linecache
import os
import time
import tempfile
import logging


def handlers_open(logger):
    """Return True if the given logger has at least one handler with an open stream.

    Defensive: never raise; used during process shutdown when handlers may be closed.
    """
    try:
        if logger is None:
            return False
        handlers = getattr(logger, "handlers", None)
        if not handlers:
            return False
        for _h in handlers:
            try:
                s = getattr(_h, "stream", None)
                if s is None:
                    return True
                if not getattr(s, "closed", False):
                    return True
            except Exception:
                return True
        return False
    except Exception:
        return False


def capture_thread_dump(reason="") -> str:
    """Capture a best-effort thread dump string for the current process."""
    header = f"--- THREAD DUMP ({reason}) ---"
    frames = sys._current_frames()
    try:
        thread_name_by_id = {t.ident: t.name for t in threading.enumerate()}
    except Exception:
        thread_name_by_id = {}
    out_lines = [header]
    for tid, frame in frames.items():
        try:
            tname = thread_name_by_id.get(tid, str(tid))
            out_lines.append(f"Thread {tname} (id={tid}) stack:")
            f = frame
            while f is not None:
                try:
                    co = f.f_code
                    filename = co.co_filename
                    lineno = f.f_lineno
                    func = co.co_name
                    src = linecache.getline(filename, lineno).strip()
                    out_lines.append(f'  File "{filename}", line {lineno}, in {func}')
                    out_lines.append(f'    {src}')
                except Exception:
                    out_lines.append('  <frame formatting failed>')
                try:
                    f = f.f_back
                except Exception:
                    break
        except Exception:
            try:
                logging.getLogger('EpsteinFilesDownloader').exception('Failed to format thread %s', tid)
            except Exception:
                pass
    out_lines.append('--- END THREAD DUMP ---')
    return "\n".join(out_lines)


def write_thread_dump_file(dump_text: str, log_dir: str | None = None, prefix: str = "thread_dump") -> str | None:
    """Write dump_text to disk under log_dir (or tempdir) and return path or None."""
    try:
        logs_dir = log_dir or os.path.join(os.getcwd(), "logs")
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except Exception:
            logs_dir = None
        ts = time.strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        fname = f"{prefix}_{ts}_{pid}.txt"
        if logs_dir:
            try:
                fpath = os.path.join(logs_dir, fname)
                with open(fpath, 'w', encoding='utf-8') as fh:
                    fh.write(dump_text)
                return fpath
            except Exception:
                pass
        # Fallback to tempdir
        try:
            td = tempfile.gettempdir()
            fpath = os.path.join(td, fname)
            with open(fpath, 'w', encoding='utf-8') as fh:
                fh.write(dump_text)
            return fpath
        except Exception:
            try:
                print('THREAD DUMP (fallback):')
                print(dump_text)
            except Exception:
                pass
        return None
    except Exception:
        return None


def safe_log_dump(logger: logging.Logger | None, message: str, dump_text: str, log_dir: str | None = None):
    """Attempt to log message via logger if handlers open, otherwise write marker to log_dir.

    Also write the raw dump_text to disk via write_thread_dump_file so an artifact exists.
    """
    try:
        fpath = write_thread_dump_file(dump_text, log_dir=log_dir)
        if handlers_open(logger):
            try:
                logger.error(message + (f' Wrote thread dump to file: {fpath}' if fpath else ''))
            except Exception:
                pass
        else:
            try:
                md = log_dir or os.path.join(os.getcwd(), 'logs')
                os.makedirs(md, exist_ok=True)
                with open(os.path.join(md, 'heartbeat_errors.txt'), 'a', encoding='utf-8') as _efh:
                    _efh.write(message + '\n')
                    if fpath:
                        _efh.write(f'Wrote dump file: {fpath}\n')
            except Exception:
                pass
    except Exception:
        pass
