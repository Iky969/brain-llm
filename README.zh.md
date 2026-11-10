# 🧠 大脑(Brain)

> 中文文档 · [English README](README.md) · [架构文档](doc/architecture.md)

面向 LLM 的 **CLI 版 Obsidian**:用 Markdown 笔记、双向链接与中文全文搜索,构建你的第二大脑。
纯 Python 标准库实现,零第三方依赖。

## 特性

- 📝 **Markdown 笔记**:标题即文件名,支持简易 frontmatter(`tags` / `aliases`)
- 🔗 **Obsidian 风格双向链接**:`[[笔记]]`、`[[笔记|别名]]`、`[[笔记#小节]]`,自动解析与反向链接
- 🏷️ **标签系统**:`#人工智能`、`#笔记/ML`,支持中文标签
- 🔍 **中文全文搜索**:单字 + 二元组(bigram)分词,无需 jieba,标题/标签加权
- 🕸️ **链接图谱**:ASCII 邻接表 / Graphviz DOT / JSON
- 📅 **每日笔记**(日记),自动创建
- 🧊 **孤立笔记**检测、📊 知识库统计、✏️ 重命名并自动同步所有链接
- 💻 **交互式 shell**:`brain 交互`,全中文命令
- 🤖 **MCP 服务**:让 Claude Code / Cursor 等任何支持 MCP 的 LLM 客户端把「大脑」当作记忆插件

## 安装

```bash
cd brain-llm
python3 -m venv .venv
.venv/bin/pip install -e .
# 之后即可使用 brain 命令(或 .venv/bin/brain)
```

## 快速开始

```bash
brain --vault ~/.brain 初始化

brain 新建 "机器学习基础" -t 人工智能 笔记
brain 新建 "深度学习" -t 人工智能
# 编辑内容,加入 [[机器学习基础]] 与 #人工智能

brain 搜索 "人工智能"        # 中文全文搜索
brain 列表                   # 全部笔记(按更新时间)
brain 链接 "机器学习基础"     # 出链与反向链接
brain 标签                   # 所有标签
brain 图谱                   # ASCII 图谱(-f dot / -f json)
brain 孤立                   # 孤立笔记
brain 统计                   # 统计信息
brain 日记                   # 今日笔记
brain 交互                   # 进入交互式 shell
```

全局选项:

- `--vault 目录`:指定知识库位置(默认 `~/.brain`,也可用环境变量 `BRAIN_VAULT`)
- `EDITOR` 环境变量:指定编辑器(`brain 打开` / `-e` 使用)

## 命令一览

| 命令 | 别名 | 说明 |
| --- | --- | --- |
| `初始化` | `init` | 初始化知识库目录 |
| `新建 <标题>` | `new` | 新建笔记(`-c` 内容,`-t` 标签,`-e` 编辑) |
| `打开 <标题>` | `open` | 用 `$EDITOR` 打开 |
| `查看 <标题>` | `show` | 查看内容(`--raw` 原样输出) |
| `列表` | `list`, `ls` | 列出全部笔记(`-n` 限制) |
| `搜索 <关键词>` | `search` | 中文全文搜索(`-n` 限制) |
| `删除 <标题>` | `delete`, `rm` | 删除(`-f` 跳过确认) |
| `重命名 <旧> <新>` | `rename` | 重命名并同步所有链接 |
| `链接 <标题>` | `links` | 出链与反向链接 |
| `标签 [标签名]` | `tags` | 列出标签 / 按标签筛选 |
| `日记` | `daily` | 查看/创建今日笔记 |
| `图谱` | `graph` | 导出图谱(`-f ascii\|dot\|json`,`-o` 写文件) |
| `孤立` | `orphans` | 列出孤立笔记 |
| `统计` | `stats` | 知识库统计 |
| `交互` | `repl` | 交互式 shell |
| `mcp` | `serve` | 启动 MCP 服务(供 LLM 使用) |

## 中文搜索原理

查询「人工智能」会被拆成 **单字**(人/工/智/能)与 **二元组**(人工/工智/智能),
与笔记正文、标题、标签中的词元匹配,命中越多得分越高;标题权重 ×3、标签 ×2。
因此搜「人工智慧」也能召回「人工智能」的笔记(简繁/词形相近的容错)。

## 接入 LLM(MCP)

「大脑」内置 MCP 服务器,提供 11 个中文工具:
`brain_search` / `brain_get` / `brain_save` / `brain_delete` / `brain_list` /
`brain_tags` / `brain_links` / `brain_graph` / `brain_orphans` / `brain_stats` / `brain_daily`。

**Claude Code:**

```bash
claude mcp add brain -- brain --vault ~/.brain mcp
```

**Cursor(~/.cursor/mcp.json)或任何支持 MCP 的客户端:**

```json
{
  "mcpServers": {
    "brain": {
      "command": "brain",
      "args": ["--vault", "/home/你的用户名/.brain", "mcp"]
    }
  }
}
```

## 仓库结构

```
~/.brain/
├── README.md
├── 机器学习基础.md
├── 深度学习.md
└── 2026-11-10.md      # 每日笔记
```

笔记即文件,可用任何编辑器直接修改;链接、标签会在下次命令执行时自动重建。

## 开发

```bash
python -m unittest discover -s tests -v   # 运行测试
python -m brain --vault ~/.brain 搜索 人工智能   # 不安装直接运行
```
