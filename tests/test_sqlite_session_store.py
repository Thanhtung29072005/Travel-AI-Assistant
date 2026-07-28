"""Tests for the Render-compatible SQLite session store."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.services.session_store import SQLiteSessionStore


class SQLiteSessionStoreTests(unittest.TestCase):
    def test_persists_and_deletes_conversation_history(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "sessions.sqlite"
            store = SQLiteSessionStore(database)

            initial = store.get_or_create("session-1")
            self.assertEqual(initial.conversation_history, [])

            history = [{"role": "user", "content": "Plan a Da Nang trip"}]
            store.save_history("session-1", history)
            restored = store.get_or_create("session-1")
            self.assertEqual(restored.conversation_history, history)

            store.clear("session-1")
            cleared = store.get_or_create("session-1")
            self.assertEqual(cleared.conversation_history, [])
