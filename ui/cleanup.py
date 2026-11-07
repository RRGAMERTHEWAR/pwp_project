"""Graceful shutdown and timer cleanup for CustomTkinter.

CustomTkinter runs background timers for DPI scaling, animations, and hover effects.
This module intercepts and cancels pending timers upon window closing, preventing
annoying Tkinter console errors (`invalid command name "..."`).
"""

from __future__ import annotations

import atexit
import tkinter as tk

_ORIG_AFTER = tk.Misc.after
_ORIG_AFTER_CANCEL = tk.Misc.after_cancel

# Set of active after() timers, keyed by (widget, after_id)
_pending: set[tuple[tk.Misc, str]] = set()
_installed = False


def install() -> None:
    """Patch Tkinter event scheduling methods to track timers. Safe to call multiple times."""
    global _installed
    if _installed:
        return
    tk.Misc.after = _tracked_after
    tk.Misc.after_cancel = _tracked_after_cancel
    _installed = True
    atexit.register(cancel_all)


def _tracked_after(self, ms, func=None, *args):
    """Drop-in replacement for ``Misc.after`` that records the timer id."""
    if func is None:
        return _ORIG_AFTER(self, ms)

    def _wrapped():
        try:
            return func(*args)
        finally:
            # The callback has fired, so it is no longer pending.
            _pending.discard((self, after_id))

    after_id = _ORIG_AFTER(self, ms, _wrapped)
    _pending.add((self, after_id))
    return after_id


def _tracked_after_cancel(self, after_id):
    """Drop-in replacement for ``Misc.after_cancel`` that forgets the id."""
    _pending.discard((self, after_id))
    return _ORIG_AFTER_CANCEL(self, after_id)


def cancel_all() -> None:
    """Cancel every still-pending ``after`` callback we know about.

    Safe to call more than once and from an ``atexit`` hook — cancelled or
    already-destroyed timers raise ``TclError`` which is swallowed here.
    """
    for widget, after_id in list(_pending):
        try:
            widget.tk.call("after", "cancel", after_id)
        except Exception:
            pass
    _pending.clear()


def install_close_protocol(window: tk.Misc) -> None:
    """Make closing *window* cancel pending timers before destroying it.

    ``window`` should be a top-level root (``CTk`` / ``CTkToplevel``). Both the
    close button (``WM_DELETE_WINDOW``) and direct ``destroy()`` calls route
    through a wrapper that cancels pending ``after`` timers first, so
    interpreter teardown never hits stray callbacks. Idempotent per window.
    """
    install()
    if getattr(window, "_cleanup_installed", False):
        return
    window._cleanup_installed = True

    original_destroy = window.destroy

    def _clean_destroy() -> None:
        cancel_all()
        original_destroy()

    try:
        window.destroy = _clean_destroy
        window.protocol("WM_DELETE_WINDOW", _clean_destroy)
    except Exception:
        pass
