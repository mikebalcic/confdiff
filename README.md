# confdiff

**两份配置到底差在哪？把噪音去掉，只看该看的。**

`confdiff` 比对两份配置文件，把差异分成四类打印出来：新增、删除、真正改动、仅空白差异。
支持 JSON、YAML、`.env`、INI 四种格式。

- 零依赖，Python 3.10+ 标准库
- 单文件运行，输出可直接贴进 PR 评论
- 不联网、不修改任何文件

## 为什么不用 `diff`

`diff` 给你的是行级差异。配置文件的行级差异通常没法看：

```diff
-  "port": 80,
+  "port": 8080,
-  "features": {
-    "beta": true
-  }
+  "features": {
+    "beta": false,
+    "gamma": true
+  }
```

你真正想问的是"哪个配置项变了"。`confdiff` 把嵌套结构拍平成点号路径后直接告诉你：

```
~ db.port: '5432' -> '5433'
- features.beta: 'true'
+ features.gamma: 'true'
~ port: '80' -> '8080'
```

## 用法

```bash
# 基本用法
python confdiff.py old.json new.json

# 忽略某个前缀的所有键
python confdiff.py old.yaml new.yaml --ignore "^debug\."

# 多个忽略规则可以叠加
python confdiff.py old.env new.env --ignore "^PATH$" --ignore "^HOME$"

# JSON 输出，方便接进流水线
python confdiff.py old.json new.json --json
```

退出码：有差异时返回 `1`，完全一致返回 `0`。所以可以直接这样用：

```bash
python confdiff.py config.before.json config.after.json || echo "配置变了，别忘了同步文档"
```

## 四种差异类型

| 符号 | 类型 | 含义 |
|---|---|---|
| `+` | added | 新增的键 |
| `-` | removed | 被删掉的键 |
| `~` | changed | 值真的变了 |
| `·` | whitespace | 值没变，只是引号或空格不同 |

`whitespace` 这一类单列出来，是因为它经常是唯一"不算问题"的变化——格式化工具跑了一遍而已，
但它确实出现在 diff 里，值得知道。

## 键路径是怎么来的

嵌套字典用点号连接，列表用方括号索引：

```json
{"db": {"pool": {"size": 10}}, "hosts": ["a", "b"]}
```

拍平后是：

```
db.pool.size
hosts[0]
hosts[1]
```

所以 `hosts` 里第 2 个元素变了，报的是 `hosts[1]`，不会只说"hosts 变了"。

## 各格式的解析方式

| 格式 | 说明 |
|---|---|
| `.json` | 标准 JSON，嵌套结构完整展开 |
| `.yaml` / `.yml` | 只支持 `key: value` 形式与缩进嵌套，不支持列表、多行标量、锚点 |
| `.env` | `KEY=value`，忽略 `export ` 前缀与 `#` 注释 |
| `.ini` / `.cfg` / `.conf` | `key=value` 或 `key: value`，忽略 `[section]` 行 |

YAML 那一栏是**故意做窄**的。完整的 YAML 解析要引第三方库，而这个工具的定位是
"随手比对一下"，不值得为此增加依赖。遇到带列表或复杂结构的 YAML，
建议先转成 JSON 再比。

## 已知局限

- **不做语义比较**。`"8080"`（字符串）和 `8080`（数字）在 JSON 里是不同的值，这里会报成改动。
- **YAML 支持有限**，见上。
- **不比较键的顺序**。配置文件的顺序变化不算差异——如果你需要这个行为，说明你需要的是 `diff`。
- **不处理多行值**。多行字符串会被当成单行处理。

## 跑测试

```bash
python test_confdiff.py
```

---

## 关于作者

mikebalcic 专注配置与变更管理。这个工具的判断标准是：一条 diff 值得你看，是因为它改变了行为，不是因为它改变了字符。

- 个人主页：<https://mikebalcic.github.io>
- 仓库：<https://github.com/mikebalcic/confdiff>

## 许可

MIT，见 [LICENSE](LICENSE)。
