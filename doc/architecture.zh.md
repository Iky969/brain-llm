# 架构文档

「大脑」是一个三层架构的命令行知识库:界面层(CLI)、领域层(知识库引擎)、
协议层(MCP)。领域层不依赖任何界面,因此同一套笔记引擎既可以驱动命令行,
也可以驱动 LLM。

## 一、模块分层

```
brain/
├── cli.py      界面层:参数解析、中文输出、交互 REPL
├── vault.py    领域层核心:笔记读写、链接/标签解析、仓库操作
├── search.py   领域层:中文分词、索引、排序、摘要
├── graph.py    领域层:链接图谱构建与导出(ASCII/DOT/JSON)
└── mcp.py      协议层:MCP 服务器,把领域层暴露成 LLM 工具
```

依赖方向是单向的:

```
cli.py ──→ vault.py ←── mcp.py
   │           ↑
   └──→ search.py / graph.py
```

vault 不知道 cli 和 mcp 的存在——这是整个架构的关键:记忆引擎可以被任何前端复用。

## 二、数据模型(vault.py)

```
Note(dataclass)
  ├── path / content / body   原始文件、去掉 frontmatter 的正文
  ├── front                    YAML 头的解析结果
  ├── tags                     标签(小写去重)
  ├── links                    [[链接]] 解析出的目标(去别名、去重)
  └── mtime                    更新时间

Vault(仓库)= 一个目录 + 一组操作
  ensure()       建目录、生成 README
  notes()        扫描所有 .md(跳过隐藏目录)
  find()         按标题找笔记(精确 → 大小写不敏感 → 文件名)
  create/save/delete/rename
  resolve_map()  小写标题 → 规范标题 的映射,链接解析用
  backlinks()    反向链接
  tags_index()   标签倒排
  stats()        统计
```

笔记没有数据库,文件系统就是数据库:标题即文件名,链接即文本。
任何编辑器都能直接改,工具每次运行重新扫描。

## 三、一条命令的数据流(以「搜索 人工智能」为例)

1. cli.py 用 argparse 解析出中文命令和参数
2. Vault(path) 定位仓库
3. cmd_search 调用 vault.notes() —— 遍历目录,每个文件 parse_note():
   - 剥 frontmatter
   - 剥代码块/行内代码(避免示例里的 [[链接]] 被当真)
   - 正则提取 #标签 和 [[链接]]
4. search() 对每篇笔记现场建倒排索引:
   - 英文按整词、中文按单字+二元组
   - 标题权重 ×3、标签 ×2、正文 ×1;二元组比单字权重高
5. 查询词同样分词,统计命中项数与加权得分,排序取前 N
6. snippet() 截取关键词上下文,cli 高亮后输出

索引是「查询时现场构建」的,不落盘。个人量级(几千篇)足够快,
代价是每次命令 O(总字数)。

## 四、链接系统(Obsidian 的灵魂)

```
写入:    笔记正文里写 [[机器学习基础]]
解析:    parse_note 提取目标 → resolve_map 把 "机器学习基础" 映射到真实文件
出链:    这篇笔记指向谁(outlinks)
反链:    谁指向这篇笔记(backlinks)
重命名:  vault.rename() 改文件名后,用正则全库扫描 [[旧标题]],
        连同 |别名 和 #小节 一起保留地替换成 [[新标题]]
失效链接: 解析不到目标的 [[链接]] 会被标红,统计里单独计数
```

## 五、中文搜索原理(search.py)

```
查询「人工智能」→ 词元 {人,工,智,能,人工,工智,智能}
每篇笔记同样切词后建 {词元: 权重}
得分 = 命中词元权重之和 + 标题整词命中 +12 + 正文整串命中 +6
按得分排序,输出匹配项数与摘要
```

好处:不需要 jieba 这类分词库(零依赖);单字召回带来容错——
搜「人工智慧」也能命中「人工智能」的笔记;二元组保证多字查询的精度。

## 六、MCP 协议层(mcp.py)

MCP = Model Context Protocol,让 LLM 客户端调用外部工具的标准。

- 传输:stdio,JSON-RPC 2.0,一行一个 JSON 对象
- 生命周期:

```
LLM 客户端 → initialize   → 返回协议版本、能力、服务器信息
           → tools/list  → 返回 11 个工具的中文名、描述、JSON Schema
           → tools/call  → dispatch() 调用领域层,结果包成 text 返回
           → 通知(无 id) → 不响应
```

工具只是 vault/search/graph 的薄封装:brain_search 调 search(),
brain_save 调 vault.save/create,brain_graph 调 build_graph()。
出错时返回 isError=true,LLM 能读到中文错误信息并自我纠正。

## 七、界面层(cli.py)

- argparse 子命令:中文为主名,英文为别名(搜索 / search / find / grep)
- 输出细节:CJK 字符按 2 格宽对齐(否则中文表格会错位);
  仅在 TTY 时加 ANSI 颜色(重定向到文件时自动变纯文本)
- 交互模式是一个 REPL:读一行 → shlex 切词 → 复用同一套 argparse 和
  处理函数 → 输出,所以交互模式和命令行模式行为完全一致
- 打开编辑器走 $EDITOR 环境变量,退出后清缓存

## 八、关键设计决策与权衡

1. **零第三方依赖**:只用标准库。装完即用、跨机器可移植;
   代价是中文分词是 bigram 近似,不如 jieba 精准(但无依赖更稳)。
2. **无索引落盘**:简单、永远和文件一致;瓶颈是大全库。
   扩展点明确——把 build_index 的结果缓存成 SQLite 即可,接口不用变。
3. **大小写策略**:文件名和链接解析大小写不敏感,标签统一小写;
   中文场景下几乎无副作用。
4. **代码块剥离**:Obsidian 的行为——`[[链接]]` 和 #标签 写在代码里不算数,
   避免文档里的示例污染图谱。
5. **文件名清洗**:标题里的 `/ \ : * ? " < > |` 会替换成 `_`,保证跨平台合法。

## 九、扩展点

- 持久化索引:SQLite 表 token → note,search() 换查询端
- 附件/图片:Note 加 attachments 字段,解析 `![[图片.png]]`
- 模板系统:note_template() 升级为可配置的模板目录
- 同步/加密:仓库即目录,直接套 git 或 git-crypt 即可
- 前端:领域层已经和界面解耦,写 TUI(rich/textual)或 Web 界面都行
