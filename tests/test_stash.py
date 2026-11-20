import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import code_stash as stash


class StashTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for name, filename in (("CONFIG_PATH", "config.yaml"), ("DB_PATH", "db")):
            setting = patch.object(stash, name, Path(directory.name) / filename)
            setting.start()
            self.addCleanup(setting.stop)

    def test_default_empty_and_overridden_config(self):
        self.assertEqual(stash.load_config(), stash.DEFAULT_CONFIG)
        stash.CONFIG_PATH.write_text("")
        self.assertEqual(stash.load_config(), stash.DEFAULT_CONFIG)
        stash.CONFIG_PATH.write_text("embedding_model: fixture")
        self.assertEqual(stash.load_config()["embedding_model"], "fixture")
        self.assertEqual(stash.load_config()["ollama_url"], stash.DEFAULT_CONFIG["ollama_url"])

    def test_invalid_config_reports_the_expected_type(self):
        stash.CONFIG_PATH.write_text("- bad")
        with self.assertRaisesRegex(ValueError, "mapping"):
            stash.load_config()

    def test_reindex_rebuilds_old_binary_cache_from_text(self):
        out = io.StringIO()
        with patch.object(stash, "get_embedding", return_value=[0.6, 0.8]), redirect_stdout(out):
            snippet_id = stash.add_snippet("sample", "print(1)")
            with stash.get_db() as conn:
                self.assertEqual(json.loads(conn.execute("SELECT embedding FROM snippets").fetchone()[0]), [0.6, 0.8])
                conn.execute("UPDATE snippets SET embedding = ? WHERE id = ?", (b"old cached vector", snippet_id))
            stash.search_snippets("sample")
            self.assertIn("reindex", out.getvalue())
            stash.regenerate_embeddings()
            stash.search_snippets("sample")
        self.assertIn("similarity: 1.000", out.getvalue())
