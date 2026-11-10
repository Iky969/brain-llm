import json
import os
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.vault import Vault, parse_note, CORE_DIR, BRAIN_DIR, DAILY_DIR
from brain.search import tokenize, search, snippet
from brain.graph import build_graph, to_dot, to_json, to_ascii
from brain import mcp


def _read_line(proc, timeout=10):
    if select.select([proc.stdout], [], [], timeout)[0]:
        return proc.stdout.readline()
    raise AssertionError("MCP server did not respond within timeout")


class VaultTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ensure_creates_structure_and_soul(self):
        self.assertFalse((self.v.path / "README.md").exists())
        self.v.ensure()
        self.assertTrue((self.v.path / "README.md").exists())
        self.assertTrue((self.v.path / CORE_DIR).is_dir())
        self.assertTrue((self.v.path / BRAIN_DIR).is_dir())
        self.assertTrue((self.v.path / DAILY_DIR).is_dir())
        self.assertTrue((self.v.path / CORE_DIR / "soul.md").exists())

    def test_create_and_find_in_brain(self):
        n = self.v.create("Machine Learning", content="# Machine Learning\n\nContent here")
        self.assertEqual(n.path.stem, "Machine Learning")
        self.assertEqual(n.category, BRAIN_DIR)
        self.assertTrue((self.v.path / BRAIN_DIR / "Machine Learning.md").exists())
        self.assertIsNotNone(self.v.find("Machine Learning"))
        self.assertIsNotNone(self.v.find("Machine Learning.md"))
        self.assertIsNone(self.v.find("Nonexistent Note"))
        with self.assertRaises(FileExistsError):
            self.v.create("Machine Learning", content="duplicate")

    def test_core_soul_operations(self):
        self.v.ensure()
        soul = self.v.get_core("soul")
        self.assertIsNotNone(soul)
        self.assertEqual(soul.category, CORE_DIR)
        self.assertIn("Core Soul", soul.content)

        updated = self.v.save_core("soul", "# Updated Soul\n\nCustom Directives")
        self.assertEqual(updated.stem, "soul")
        self.assertIn("Updated Soul", self.v.get_core("soul").content)

        custom_core = self.v.save_core("memory", "# Facts\nUser profile")
        self.assertEqual(custom_core.stem, "memory")
        self.assertEqual(len(self.v.core_notes()), 2)

    def test_safe_filename(self):
        n = self.v.create("A/B:C", content="x")
        self.assertEqual(n.path.stem, "A_B_C")

    def test_code_spans_ignored(self):
        n = self.v.create(
            "CodeNote",
            content=(
                "Body `#tag1` and `[[NonexistentLink]]`.\n\n"
                "```\n#tag2 [[AlsoIgnored]]\n```\n\n"
                "Real tag #real"
            ),
        )
        self.assertEqual(n.tags, ["real"])
        self.assertEqual(n.links, [])

    def test_links_and_backlinks_across_folders(self):
        self.v.create("DeepLearning", content="Deep Learning is a branch of [[ArtificialIntelligence]]. #ai")
        self.v.create("ArtificialIntelligence", content="Introduction to AI. See [[DeepLearning]].", folder=BRAIN_DIR)
        base = self.v.find("DeepLearning")
        self.assertIn("ArtificialIntelligence", base.links)
        backs = self.v.backlinks("ArtificialIntelligence")
        self.assertEqual([n.path.stem for n in backs], ["DeepLearning"])
        out = self.v.outlinks(self.v.find("ArtificialIntelligence"))
        self.assertEqual(out, [("DeepLearning", "DeepLearning")])

    def test_link_alias_and_section(self):
        self.v.create("TargetNote", content="x")
        self.v.create("AliasTest", content="See [[TargetNote|Custom Alias]] and [[TargetNote#Section]].")
        note = self.v.find("AliasTest")
        self.assertEqual(note.links, ["TargetNote"])
        out = self.v.outlinks(note)
        self.assertEqual([r for _, r in out], ["TargetNote"])

    def test_tags(self):
        n = self.v.create("TagTest", content="Body #python and #dev/ml")
        self.assertIn("python", n.tags)
        self.assertIn("dev/ml", n.tags)
        idx = self.v.tags_index()
        self.assertEqual(len(idx["python"]), 1)
        self.assertNotIn("tagtest", n.tags)

    def test_frontmatter(self):
        n = self.v.create(
            "fm",
            content="---\ntags: [python, research]\n---\n\nBody #notes",
        )
        self.assertIn("python", n.tags)
        self.assertIn("research", n.tags)
        self.assertIn("notes", n.tags)
        self.assertEqual(n.front["tags"], ["python", "research"])

    def test_rename_updates_links(self):
        self.v.create("OldTitle", content="Old content")
        self.v.create("Referrer", content="See [[OldTitle]]")
        new_note, changed = self.v.rename("OldTitle", "NewTitle")
        self.assertEqual(new_note.path.stem, "NewTitle")
        self.assertEqual(changed, 1)
        self.assertIn("[[NewTitle]]", self.v.find("Referrer").content)

    def test_rename_preserves_alias(self):
        self.v.create("Old", content="x")
        self.v.create("Ref", content="[[Old|Custom Alias]]")
        self.v.rename("Old", "New")
        self.assertIn("[[New|Custom Alias]]", self.v.find("Ref").content)

    def test_daily_note(self):
        p = self.v.daily_path()
        self.assertTrue(str(p).endswith(".md"))
        self.assertEqual(p.parent.name, DAILY_DIR)
        self.v.create(p.stem, content="__daily__", folder=DAILY_DIR)
        self.assertTrue(p.exists())
        self.assertEqual(len(self.v.daily_notes()), 1)

    def test_stats(self):
        self.v.ensure()
        self.v.create("NoteA", content="[[NoteB]]", folder=BRAIN_DIR)
        self.v.create("NoteB", content="[[Nonexistent]]", folder=BRAIN_DIR)
        s = self.v.stats()
        self.assertIn("total_notes", s)
        self.assertIn("core_notes", s)
        self.assertIn("brain_notes", s)
        self.assertIn("daily_notes", s)
        self.assertGreaterEqual(s["total_notes"], 3)  # soul + NoteA + NoteB
        self.assertEqual(s["valid_links"], 1)
        self.assertEqual(s["broken_links"], 1)


class SearchTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)
        self.v.create("MachineLearning", content="Machine learning is a subset of artificial intelligence.")
        self.v.create("CookingRecipes", content="Today we cooked delicious pasta with tomato sauce.")

    def tearDown(self):
        self.tmp.cleanup()

    def test_tokenize_english_and_cjk(self):
        toks = tokenize("AI and 人工智能")
        self.assertIn("ai", toks)
        self.assertIn("and", toks)
        self.assertIn("人工", toks)
        self.assertIn("智能", toks)
        self.assertIn("人", toks)

    def test_search_english(self):
        results = search(self.v.notes(), "artificial intelligence")
        self.assertTrue(results)
        self.assertEqual(results[0][2].path.stem, "MachineLearning")

    def test_search_other_note(self):
        results = search(self.v.notes(), "pasta")
        self.assertEqual(results[0][2].path.stem, "CookingRecipes")

    def test_search_no_match(self):
        self.assertEqual(search(self.v.notes(), "quantum_computing_xyz"), [])

    def test_snippet(self):
        s = snippet("Prefix info. Machine learning is a field of computer science. Suffix info.", "machine learning")
        self.assertIn("Machine", s)
        self.assertIn("learning", s)


class GraphTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)
        self.v.create("A", content="[[B]]")
        self.v.create("B", content="[[C]]")
        self.v.create("C", content="No links")

    def tearDown(self):
        self.tmp.cleanup()

    def test_graph(self):
        g = build_graph(self.v)
        self.assertEqual(g["A"]["out"], ["B"])
        self.assertEqual(g["B"]["inn"], ["A"])
        self.assertEqual(g["C"]["inn"], ["B"])

    def test_dot(self):
        dot = to_dot(build_graph(self.v))
        self.assertIn("digraph Brain", dot)
        self.assertIn('"A" -> "B";', dot)
        self.assertIn('"B" -> "C";', dot)

    def test_json(self):
        data = json.loads(to_json(build_graph(self.v)))
        self.assertIn("A", data)
        self.assertEqual(data["A"]["outlinks"], ["B"])

    def test_ascii(self):
        txt = to_ascii(build_graph(self.v))
        self.assertIn("A", txt)
        self.assertIn("Outlinks", txt)


class McpTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)
        self.v.create("McpTest", content="Brain MCP note content regarding artificial intelligence.")

    def tearDown(self):
        self.tmp.cleanup()

    def test_handle_initialize(self):
        resp = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, self.v)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "brain")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_handle_tools_list(self):
        resp = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, self.v)
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertIn("brain_search", names)
        self.assertIn("brain_save", names)
        self.assertIn("brain_get_core", names)
        self.assertIn("brain_save_core", names)

    def test_handle_tools_call_search(self):
        resp = mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "brain_search", "arguments": {"query": "intelligence"}},
            },
            self.v,
        )
        text = resp["result"]["content"][0]["text"]
        self.assertIn("McpTest", text)
        self.assertFalse(resp["result"]["isError"])

    def test_handle_tools_call_save_and_get(self):
        resp = mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "brain_save",
                    "arguments": {"title": "NewMemory", "content": "# New Memory\n\nDetails"},
                },
            },
            self.v,
        )
        self.assertFalse(resp["result"]["isError"])
        resp = mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "brain_get", "arguments": {"title": "NewMemory"}},
            },
            self.v,
        )
        self.assertIn("New Memory", resp["result"]["content"][0]["text"])

    def test_handle_tools_call_core_memory(self):
        resp = mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "brain_save_core",
                    "arguments": {"name": "soul", "content": "# Core Soul\nAI Directives"},
                },
            },
            self.v,
        )
        self.assertFalse(resp["result"]["isError"])

        resp = mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "brain_get_core", "arguments": {"name": "soul"}},
            },
            self.v,
        )
        self.assertIn("AI Directives", resp["result"]["content"][0]["text"])

    def test_notification_no_response(self):
        self.assertIsNone(
            mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, self.v)
        )

    def test_unknown_method(self):
        resp = mcp.handle({"jsonrpc": "2.0", "id": 8, "method": "unknown_call"}, self.v)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_mcp_stdio(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + (":" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
        proc = subprocess.Popen(
            [sys.executable, "-m", "brain", "--vault", self.tmp.name, "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        try:
            reqs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "brain_stats", "arguments": {}},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "brain_search", "arguments": {"query": "intelligence"}},
                },
            ]
            texts = []
            for r in reqs:
                proc.stdin.write(json.dumps(r, ensure_ascii=False) + "\n")
                proc.stdin.flush()
                data = json.loads(_read_line(proc))
                self.assertEqual(data["id"], r["id"])
                self.assertIn("result", data)
                if r["id"] > 1:
                    texts.append(data["result"]["content"][0]["text"])
            self.assertIn("total_notes", texts[0])
            self.assertIn("McpTest", texts[1])
        finally:
            proc.stdin.close()
            proc.stdout.close()
            proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
