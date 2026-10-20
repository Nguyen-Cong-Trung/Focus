"""
Focus — Spertulo Utility
"""
import sys
import os
import atexit

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    """Main entry point."""
    from utils.windowed_io import ensure_standard_streams
    ensure_standard_streams()
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from core.release_check import run_release_check
        raise SystemExit(run_release_check(sys.argv[2]))
    from core.instance import SingleInstance
    instance = SingleInstance(PROJECT_ROOT)
    if not instance.is_primary:
        instance.activate()
        instance.close()
        return
    from utils.constants import DB_DIR
    from utils.logging_setup import setup_logging
    setup_logging(DB_DIR)
    import logging
    # Import here to catch missing dependencies early
    try:
        from core.site_blocker import SiteBlocker
        from ui.app import DeepFocusApp
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        if sys.stdin is not None and sys.stdin.isatty():
            input("Press Enter to exit...")
        sys.exit(1)
    
    # Safety: clean any leftover host entries from previous crash
    blocker = SiteBlocker()
    # Startup cleanup runs in the app blocking worker.
    # Register atexit handler as a SAFETY NET
    # Even if app crashes, this will try to clean hosts file
    atexit.register(blocker.cleanup)
    
    app = None
    try:
        app = DeepFocusApp(instance_guard=instance)
        app.mainloop()
    except Exception as e:
        logging.getLogger(__name__).exception("Application failed")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        # Cleanup on crash
        blocker.cleanup()
        if sys.stdin is not None and sys.stdin.isatty():
            input("Press Enter to exit...")
        sys.exit(1)
    finally:
        try:
            if app is not None:
                app.shutdown_resources()
        finally:
            instance.close()


if __name__ == "__main__":
    main()
