import json
import os
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.vault import Vault, parse_note
from brain.search import tokenize, search, snippet
from brain.graph import build_graph, to_dot, to_json, to_ascii
from brain import mcp


def _read_line(proc, timeout=10):
    if select.select([proc.stdout], [], [], timeout)[0]:
        return proc.stdout.readline()
    raise AssertionError("MCP 服务未在超时前响应")


class VaultTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ensure_creates_readme(self):
        self.assertFalse((self.v.path / "README.md").exists())
        self.v.ensure()
        self.assertTrue((self.v.path / "README.md").exists())

    def test_create_and_find(self):
        n = self.v.create("测试笔记", content="# 测试笔记\n\n内容")
        self.assertEqual(n.path.stem, "测试笔记")
        self.assertIsNotNone(self.v.find("测试笔记"))
        self.assertIsNotNone(self.v.find("测试笔记.md"))
        self.assertIsNone(self.v.find("不存在的笔记"))
        with self.assertRaises(FileExistsError):
            self.v.create("测试笔记", content="x")

    def test_safe_filename(self):
        n = self.v.create("A/B:C", content="x")
        self.assertEqual(n.path.stem, "A_B_C")

    def test_code_spans_ignored(self):
        n = self.v.create(
            "代码",
            content=(
                "正文 `#标签` 与 `[[不存在的链接]]`。\n\n"
                "```\n#标签2 [[也不解析]]\n```\n\n"
                "真正标签 #真实"
            ),
        )
        self.assertEqual(n.tags, ["真实"])
        self.assertEqual(n.links, [])

    def test_links_and_backlinks(self):
        self.v.create("机器学习基础", content="机器学习是[[人工智能]]的分支。#人工智能")
        self.v.create("人工智能", content="人工智能导论。参见[[机器学习基础]]。")
        base = self.v.find("机器学习基础")
        self.assertIn("人工智能", base.links)
        backs = self.v.backlinks("人工智能")
        self.assertEqual([n.path.stem for n in backs], ["机器学习基础"])
        out = self.v.outlinks(self.v.find("人工智能"))
        self.assertEqual(out, [("机器学习基础", "机器学习基础")])

    def test_link_alias_and_section(self):
        self.v.create("目标笔记", content="x")
        self.v.create("别名测试", content="见[[目标笔记|别的名字]]与[[目标笔记#小节]]。")
        note = self.v.find("别名测试")
        # links 保存解析后的目标(去掉别名与小节),重复目标会去重
        self.assertEqual(note.links, ["目标笔记"])
        out = self.v.outlinks(note)
        self.assertEqual([r for _, r in out], ["目标笔记"])

    def test_tags(self):
        n = self.v.create("标签测试", content="正文 #人工智能 与 #笔记/ML")
        self.assertIn("人工智能", n.tags)
        self.assertIn("笔记/ml", n.tags)
        idx = self.v.tags_index()
        self.assertEqual(len(idx["人工智能"]), 1)
        # 标题里的 # 不应被当作标签
        self.assertNotIn("标签测试", n.tags)

    def test_frontmatter(self):
        n = self.v.create(
            "fm",
            content="---\ntags: [人工智能, 论文]\n---\n\n正文 #笔记",
        )
        self.assertIn("人工智能", n.tags)
        self.assertIn("论文", n.tags)
        self.assertIn("笔记", n.tags)
        self.assertEqual(n.front["tags"], ["人工智能", "论文"])

    def test_rename_updates_links(self):
        self.v.create("旧标题", content="旧内容")
        self.v.create("引用者", content="见[[旧标题]]")
        new_note, changed = self.v.rename("旧标题", "新标题")
        self.assertEqual(new_note.path.stem, "新标题")
        self.assertEqual(changed, 1)
        self.assertIn("[[新标题]]", self.v.find("引用者").content)

    def test_rename_preserves_alias(self):
        self.v.create("旧", content="x")
        self.v.create("引用", content="[[旧|别名]]")
        self.v.rename("旧", "新")
        self.assertIn("[[新|别名]]", self.v.find("引用").content)

    def test_daily(self):
        p = self.v.daily_path()
        self.v.create(p.stem, content="__daily__")
        self.assertTrue(p.exists())

    def test_stats(self):
        self.v.create("A", content="[[B]]")
        self.v.create("B", content="[[不存在]]")
        s = self.v.stats()
        self.assertEqual(s["笔记总数"], 2)
        self.assertEqual(s["有效链接"], 1)
        self.assertEqual(s["失效链接"], 1)


class SearchTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)
        self.v.create("机器学习基础", content="机器学习是人工智能的一个分支。")
        self.v.create("烹饪笔记", content="今天做了红烧肉,非常好吃。")

    def tearDown(self):
        self.tmp.cleanup()

    def test_tokenize(self):
        toks = tokenize("AI与人工智能")
        self.assertIn("ai", toks)
        self.assertIn("人工", toks)
        self.assertIn("智能", toks)
        self.assertIn("人", toks)

    def test_search_chinese(self):
        results = search(self.v.notes(), "人工智能")
        self.assertTrue(results)
        self.assertEqual(results[0][2].path.stem, "机器学习基础")

    def test_search_other_note(self):
        results = search(self.v.notes(), "红烧肉")
        self.assertEqual(results[0][2].path.stem, "烹饪笔记")

    def test_search_single_char(self):
        results = search(self.v.notes(), "智")
        self.assertTrue(any(n.path.stem == "机器学习基础" for _, _, n in results))

    def test_search_no_match(self):
        self.assertEqual(search(self.v.notes(), "xyz不存在"), [])

    def test_snippet(self):
        s = snippet("前置内容。机器学习是人工智能的一个分支。后置内容。", "人工智能")
        self.assertIn("机器学习", s)
        self.assertIn("人工", s)


class GraphTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)
        self.v.create("A", content="[[B]]")
        self.v.create("B", content="[[C]]")
        self.v.create("C", content="无链接")

    def tearDown(self):
        self.tmp.cleanup()

    def test_graph(self):
        g = build_graph(self.v)
        self.assertEqual(g["A"]["out"], ["B"])
        self.assertEqual(g["B"]["inn"], ["A"])
        self.assertEqual(g["C"]["inn"], ["B"])

    def test_dot(self):
        dot = to_dot(build_graph(self.v))
        self.assertIn("digraph", dot)
        self.assertIn('"A" -> "B";', dot)
        self.assertIn('"B" -> "C";', dot)

    def test_json(self):
        data = json.loads(to_json(build_graph(self.v)))
        self.assertIn("A", data)
        self.assertEqual(data["A"]["出链"], ["B"])

    def test_ascii(self):
        txt = to_ascii(build_graph(self.v))
        self.assertIn("A", txt)
        self.assertIn("出链", txt)


class McpTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(self.tmp.name)
        self.v.create("MCP测试", content="大脑 MCP 笔记内容,关于人工智能。")

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

    def test_handle_tools_call_search(self):
        resp = mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "brain_search", "arguments": {"query": "人工智能"}},
            },
            self.v,
        )
        text = resp["result"]["content"][0]["text"]
        self.assertIn("MCP测试", text)
        self.assertFalse(resp["result"]["isError"])

    def test_handle_tools_call_save_and_get(self):
        resp = mcp.handle(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "brain_save",
                    "arguments": {"title": "新记忆", "content": "# 新记忆\n\n内容"},
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
                "params": {"name": "brain_get", "arguments": {"title": "新记忆"}},
            },
            self.v,
        )
        self.assertIn("新记忆", resp["result"]["content"][0]["text"])

    def test_notification_no_response(self):
        self.assertIsNone(
            mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, self.v)
        )

    def test_unknown_method(self):
        resp = mcp.handle({"jsonrpc": "2.0", "id": 6, "method": "foo"}, self.v)
        self.assertEqual(resp["error"]["code"], -32601)

    def test_mcp_stdio(self):
        env = dict(os.environ)
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
                    "params": {"name": "brain_search", "arguments": {"query": "人工智能"}},
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
            self.assertIn("笔记总数", texts[0])
            self.assertIn("MCP测试", texts[1])
        finally:
            proc.stdin.close()
            proc.stdout.close()
            proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
