# Reqable 响应结构检查脚本 · 使用说明

基于当前规则脚本整理的说明文档。这套脚本由 **Reqable Addon 规则脚本** + **公共引擎 `reqable_check_core.py`** 组成，用来在抓包时自动校验 API 响应的 JSON 结构。

> 官方 API 文档：<https://reqable.com/docs/capture/addons>

---

## 一、它做什么

抓包时自动校验接口返回结构：顶层 / 嵌套必需字段是否齐全、数组逐项是否完整、指定字段值是否符合预期、可选字段缺失是否只是提示、响应值与请求参数是否一致。适合接口联调、回归验证、字段变更监控。

**职责分离**：规则脚本只负责声明 `EXPECTED_CODE` 和 `checks` 列表，实际遍历与输出由公共引擎完成。改规则不动引擎。

## 二、文件组成与加载方式

| 文件 | 位置 | 作用 |
| --- | --- | --- |
| 规则脚本（本 addon） | Reqable Addons 脚本目录 | 只声明 `EXPECTED_CODE`、`checks`，加载公共引擎 |
| `reqable_check_core.py` | `~/Documents/reqable/reqable_check_core.py` | 公共引擎：`onRequest` / `onResponse` 回调、遍历结果、输出结论 |

规则脚本只剩「开头固定写法 + `EXPECTED_CODE` + `checks`」三块（整体级断言再加一个可选的 `META_CHECKS`），**路径必须用绝对路径、`~` 要展开**（Reqable 的工作目录不固定）：

```python
from reqable import *
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())

EXPECTED_CODE = 201
META_CHECKS = []        # 整体级：只跑一次、对象是整个响应 data（分页 page/size/total 用）；不写也行

checks = [
    # ...
]
```

`exec(..., globals())` 把引擎的函数与变量注入当前命名空间，之后定义 `checks` 即可。

**期望响应码**：`EXPECTED_CODE` 默认 `200`（引擎里定义），规则脚本里写 `EXPECTED_CODE = 201` 即可覆盖。响应码不匹配时引擎直接打印 `⚠️ 响应码不是200: xxx` 并跳过检查，不会解析响应体。

> ⚠️ **两个回调在不同进程**：`onRequest` 与 `onResponse` 不共享模块级变量，跨阶段取值只能走 `context.shared`（见第五节）。请求体、查询参数都由引擎的 `onRequest` 收集，**规则脚本一般不用再写 `onRequest`**；确实要写（例如想取 URL 路径里的 ID）时，先存一份引擎的实现再覆盖，见第五节 3)。

## 三、快速开始

1. 确认 `~/Documents/reqable/reqable_check_core.py` 存在（脚本会主动校验，缺失直接抛 `FileNotFoundError`）。
2. 把规则脚本挂到 Reqable Addons，开启抓包会话。
3. 触发目标接口，查看检查结果：字段缺失 / 值不符判失败，`optional` 字段缺失只提示。
4. 需要调整时只改 `checks` 列表。

---

## 四、检查项配置速查（核心）

`checks` 是列表，每项形如 `{"desc": ..., "kind": ..., ...}`。

### 通用键

| 键 | 说明 |
| --- | --- |
| `desc` | 规则描述，报错时用来定位是哪条检查 |
| `kind` | 检查类型，见下表 |
| `path` | 点分路径，指向嵌套对象或数组；数组元素用下标，如 `vlms.0.x`；写 `"."` 表示当前对象本身（数组套数组时用）；字段名后加 `?` 为松散投影、加 `*` 摊平一层、加 `[字段=值]` 按值配对（见第五节 2.5） |
| `key` | 仅 `eq` / `exists` / `gt`·`gte`·`lt`·`lte` 的顶层字段写法 |
| `fields` | 批量字段名列表，用于 `top_fields` / 批量 `exists` |
| `value` | `eq` 的期望值；`in_list` / `not_in_list` 的允许值 / 禁止值列表（如 `["operating", "non-operating"]`）；`gt` / `gte` / `lt` / `lte` 的比较基准（常量） |
| `sub` | `sub_checks` / `for_each` 的子检查列表，可继续嵌套 |
| `shared_key` | `shared_eq` / `shared_in` / `shared_not_in` / `shared_contains` / `gt`·`gte`·`lt`·`lte`：`context.shared` 里的取值路径（点分，如 `_query.ids`）；数组写字段名会投影成列表；省略时退化为 `path` / `key` |
| `require_shared` | `shared_eq` / `shared_in` / `shared_not_in` / `shared_contains` / `gt`·`gte`·`lt`·`lte`：`True` 时 `shared` 里没有该字段判 ❌，否则只 ℹ️ 跳过 |
| `null_ok` | `True` 时放行 `null` / 空串 `""`（含父级为 `null`）；在 `for_each` / `list_field` / `sub_checks` 上还表示「字段整体不存在」也放行（等价于 `optional`）；在 `top_fields` 上表示「空对象 `{}` / 空数组 `[]`」也放行（`null` 本来就不算失败） |
| `optional` | `True` 时字段整体缺失只提示、不算失败（随类型变化的可选字段）。容器类也认：`top_fields`（可选子对象）、`for_each` / `list_field`（可选数组）、`sub_checks`（可选对象），以及比较类 `eq` / `in_list` / `not_in_list` / `shared_eq` / `gt`·`gte`·`lt`·`lte`——**只放行「东西没有」，值为 `null` 仍按原逻辑判错**。`for_each` / `list_field` / `sub_checks` 上的旧写法 `null_ok` 等价保留 |
| `loose` | `shared_eq` / `shared_in` / `shared_not_in` / `shared_contains` / `in_list` / `not_in_list`：`True` 时放宽「数字 ↔ 数字字符串」（`'3000'` 与 `3000` 相等），其余类型仍严格；**两边都是数组时逐项放宽**（`[103]` 与 `['103']` 相等，长度、顺序仍须一致）；不写即严格相等 |
| `label` | 仅 `for_each`：输出里每条带上该字段的值（`"label": "id"` → `[2] id=206`），纯显示用、不影响判定；取不到或值不是标量时退回纯下标 |
| `when` | **任意 kind 都能加**：条件不成立就整条跳过（ℹ️，不计失败），一份清单覆盖多种请求参数。写法见「3.6 条件检查」 |

> 每个 `kind` 只认自己的键。写了它不支持的键（例如给 `exists` 塞 `sub`）不会报错，但那个键**不生效**，引擎会打一行 `⚠️ kind=exists 不支持 ['sub']，这些键被忽略`——看到这个提示说明这条多半没在检查你以为的内容。

### `kind` 一览

| kind | 用途 | 对象要求 |
| --- | --- | --- |
| `top_fields` | 必须存在的字段列表；加 `path` 可查嵌套子对象（可选子对象配 `optional` / `null_ok`） | 单个对象 |
| `eq` | 字段值 == 期望值 | 任意可寻址字段 |
| `in_list` | 字段值属于自定义的常量集合（枚举取值，`value` 写列表，命中任一即通过） | 任意可寻址字段 / 数组（逐项） |
| `not_in_list` | 字段值**不属于**自定义的禁止集合（黑名单，命中即失败；`in_list` 的反面） | 任意可寻址字段 / 数组（逐项） |
| `gt` / `gte` / `lt` / `lte` | 大小比较（`>` / `>=` / `<` / `<=`），两边同为数字或同为 ISO 时间串 | 任意可寻址字段（值为数字 / 时间串） |
| `exists` | 字段是否存在（默认严格，`null` 或 `""` 也判失败） | 单个或批量顶层字段 |
| `list_field` | 数组里每个元素都必须含某字段（可选数组配 `optional`） | `path` 指向数组 |
| `shared_eq` | 响应字段 == `onRequest` 写入 `context.shared` 的值（`loose: True` 时数字与数字字符串互等） | 任意可寻址字段 |
| `shared_in` | 响应字段属于 `context.shared` 里的列表（列表接口逐条校验）；响应字段本身是数组时，要求每个元素都属于；`loose: True` 时 `103` 属于 `['103']` | 任意可寻址字段 / 数组 |
| `shared_not_in` | 响应字段**不属于** `context.shared` 里的列表（排除名单）；响应字段本身是数组时，要求每个元素都不命中；同样支持 `loose` | 任意可寻址字段 / 数组 |
| `shared_contains` | 响应数组**包含** `context.shared` 里的每个值（响应 ⊇ 请求，允许服务端追加默认项）；`loose: True` 逐项放宽类型 | `path` 指向数组 / 投影成数组 |
| `sub_checks` | 对单个对象执行 `sub` 里的一组子检查（可选对象打包用；`optional` 放行对象不存在） | `path` 指向单个对象 |
| `for_each` | 对数组每个元素递归执行 `sub` 里的子检查；`optional` 放行可选数组，`label` 可让输出带上元素 id | `path` 必须指向数组 |

### 写法示例

**1. 记录自身必需字段 → `top_fields`**

```python
{"desc": "记录自身必需字段", "kind": "top_fields", "fields":
  ["id", "name", "task_status", "operating_status", "scheduler", "event_types", "camera", "location", "cluster", "snapshot", "object_size_filter", "confidence_threshold"]
},
```

> `desc` 只是给人看的标签（引擎不解析），但它会出现在每一行输出里，所以建议按层级用词统一：
> 记录级写「记录自身必需字段」，子对象写「model_settings 的必需字段」（带对象名），
> `for_each` / `sub_checks` 里的子检查写「必需字段」（外层前缀已经带了 `[0] id=206·` 这种定位）。
> 别在子层写「顶层」——那会被读成响应最外层，实际指的是"当前这个对象自己的字段"。

失败时会连带打印实际存在的键，用来判断 `path` 是否指错了对象：

```
❌ location检查·必需字段 ['timezone', 'organization_id'] 实际有: ['id', 'name', 'source_url', 'fps', ...]
```

上面这行里实际键是 `source_url` / `fps`，说明查的其实是 `camera`，`path` 该改成 `"location"`（键超过 12 个只显示前 12 个并标注总数）。

**2. 可选单个对象 → `sub_checks`**（一个对象要查很多字段时，打包成一组；对象为 `null` 整组跳过）

```python
{"desc": "camera", "kind": "sub_checks", "path": "camera", "sub":
  [{"desc": "必需字段", "kind": "top_fields", "fields":
    ["id", "name", "source_url", "fps", "resolution_height",
      "resolution_width", "model_name", "coordinates", "address"]
  },
  {"desc": "coordinates 字段", "kind": "top_fields", "path": "coordinates", "fields":
    ["latitude", "longitude"]
  },
  {"desc": "source_url 非空", "kind": "exists", "path": "source_url"}]
},
```

`sub` 里的 `path` **从对象内部写起**（`"coordinates"` 而不是 `"camera.coordinates"`）；子检查可以是任意 kind，也能再套 `for_each`。

只有一两个字段要查时，直接用 `top_fields` + `path` 更省事（效果一样，`null` 也放行）：

```python
{"desc": "camera.coordinates 的必需字段", "kind": "top_fields", "path": "camera.coordinates", "fields":
  ["latitude", "longitude"]
},
```

`sub_checks` 的三种边界：对象为 `null` → 整组 ℹ️ 跳过；对象整体不存在 → 默认 ❌，加 `optional: True`（旧写法 `null_ok: True`）放行；对象不是 dict（是数组/字符串）→ ❌ 并提示改用 `for_each`。`path` 写 `"."` 或省略表示当前对象本身。

**2.5 可选子对象 → `top_fields` + `optional` / `null_ok`**

同一个数组里，某些记录有 `model_settings`、某些没有，或者它是 `null` / `{}`——这些都是**可选对象**，不该判失败：

```python
{"desc": "model_settings 的必需字段", "kind": "top_fields", "path": "model_settings", "fields":
  ["id", "name", "version"],
  "optional": True, "null_ok": True},
```

- `optional: True` → 字段 `model_settings` **整体不存在**（这条记录没有这个对象）：ℹ️ 跳过
- `null_ok: True` → 值为 **空对象 `{}` / 空数组 `[]`** 也跳过（`null` 本来就不报错，写它是为了连 `{}` 一起放行）
- 两个都不写 → 「字段不存在」照旧 ❌（保留这个默认，`path` 写错时才抓得出来）

> 注意 `optional` 只放行「对象不存在」，**不放行**「对象存在但缺里面的字段」——`{"id": 1}` 缺 `name` / `version` 仍然 ❌。想把「缺字段」也放过，就别把该字段写进 `fields`，或者改用 `exists` 的批量写法。

对象存在时还要查好几组字段（每组各有可选性）时，用 `sub_checks` 打包：

```python
{"desc": "model_settings", "kind": "sub_checks", "path": "model_settings", "optional": True, "sub":
  [{"desc": "必需字段", "kind": "top_fields", "fields": ["id", "name", "version"]},
  {"desc": "scheduler 可选子对象", "kind": "top_fields", "path": "scheduler", "fields": ["id", "name"], "optional": True}]
},
```

**2.6 可选对象 / 可选数组：容器类检查统一用 `optional`**

四类容器都认同一个键，缺东西就打 ℹ️，不再 ❌：

| 检查对象 | kind | 放行「整体不存在」 | 备注 |
| --- | --- | --- | --- |
| 子对象 | `top_fields` + `path` | `optional: True` | `null_ok` 在这里表示「空对象 `{}` / 空数组 `[]`」 |
| 单个对象打包 | `sub_checks` | `optional: True` | 对象为 `null` 本来就整组跳过 |
| 数组 | `for_each` | `optional: True` | 旧写法 `null_ok` 等价；元素本身为 `null` 的元素仍会报错 |
| 数组（只看字段在不在） | `list_field` | `optional: True` | 旧写法 `null_ok` 等价 |

```python
{"desc": "zones 列表", "kind": "for_each", "path": "zones", "optional": True, "sub":
  [{"desc": "必需字段", "kind": "top_fields", "fields": ["id", "name", "geometry"]}]
},
```

> 不写 `optional` 时「东西不存在」照旧 ❌——这是故意的，否则 `path` 拼错（`zzones`）也会静默通过。数组/对象的值本身为 `null` 时仍按原行为视为正常（`sub_checks` 整组跳过、`for_each` 打 ℹ️）。

**3. 固定值断言 → `eq`（两种写法）**

```python
{"desc": "timezone 应为 Asia/Taipei", "kind": "eq",
  "path": "location.timezone", "value": "Asia/Taipei"},          # 嵌套写法
{"desc": "某顶层字段应为 X", "kind": "eq", "key": "task_status", "value": "active"},  # 顶层写法
```

**3.1 可选但给了就不能空 → 任意比较类检查 + `optional`**

有些字段是**可选**的：这条记录可能压根没有 `detecting_threshold`，但**一旦出现就必须是合法值**（不能 `null`、不能空串）。这种就写 `optional`：

```python
{"desc": "信心阈值 >= 0", "kind": "gte", "path": "detecting_threshold",
  "value": 0, "optional": True},
{"desc": "信心阈值 <= 1", "kind": "lte", "path": "detecting_threshold",
  "value": 1, "optional": True},
```

| 响应里的情况 | 不写 `optional` | `optional: True` |
| --- | --- | --- |
| 字段没有（整条记录没这个键） | ❌ | ℹ️ `可选字段 detecting_threshold 不存在（optional 放行）` |
| 父级对象为 `null`（路径走不到） | ❌ | ℹ️ `可选字段，父级为 null（optional 放行）` |
| `"detecting_threshold": 0.9` | 正常比较 | 正常比较 |
| `"detecting_threshold": null` | ❌ | **❌**（`optional` 不放行 null） |
| `"detecting_threshold": ""` | ❌ | **❌**（`optional` 不放行空串） |

支持的 kind：`eq` / `in_list` / `not_in_list` / `shared_eq` / `gt` / `gte` / `lt` / `lte`（`top_fields` / `exists` 上的 `optional` 是同一个含义）。

> 一句话区分：**`optional` 管「有没有这个字段」，`null_ok` 管「值是不是 null / 空串」。** 想让 `null` 也放过，两个都写；只写 `optional` 就是「可以没有，给了就不能空」。这也意味着——数据里如果是 `"detecting_threshold": null` 而不是整个键缺失，`optional` 抓不住它，还会照旧 ❌。真遇到这种要先看清是「字段没给」还是「给了个空值」。

**3.2 取值范围 / 枚举 → `in_list`**（值必须属于你自己列的常量集合，命中任一即通过）

```python
{"desc": "task_status 取值", "kind": "in_list", "path": "task_status",
  "value": ["operating", "non-operating"]},                                     # 字符串枚举
{"desc": "vlm_image_resize 取值", "kind": "in_list", "path": "vlm_image_resize",
  "value": ["384", "576", "768"]},                                              # 字符串数字枚举
{"desc": "event_types 逐个 polygon_type", "kind": "for_each", "path": "event_types", "sub":
  [{"desc": "polygon_type 取值", "kind": "in_list", "path": "polygon_type", "value":
    ["polygon", "line", "rectangle"]}]
},
```

```
✅ task_status 取值: 实际 'operating' 在允许 ['operating', 'non-operating'] 中
❌ task_status 取值: 实际 'paused' 不在允许 ['operating', 'non-operating'] 中
```

- **严格相等**：`Operating` ≠ `operating`，`"384"` ≠ `384`——文档里写什么就抄什么。字符串数字枚举
  （`"384"` / `"576"`）要么按文档写字符串，要么加 `"loose": True` 让数字与数字字符串互等；
- **允许值只按接口文档写**：文档枚举要一条不落，但**别拿"实际返回过"的值去补**。真出现文档外的值
  （如只有 `operating` / `non-operating` 却返回了 `Unknown`），那是问题本身——要么文档漏了状态，
  要么服务端吐了异常值；把它塞进列表只是把红灯糊成绿灯。确属中间态/兜底值，再改文档、再补列表。
- `path` 投影成数组时（如 `event_types.polygon_type`）要求**每个元素都在**集合里，失败会列出具体哪几项；
- 字段不存在、值为 `null` 都判 ❌，加 `"null_ok": True` 放行（`{}` / `[]` 这类空值见上节规则）；
- `value` 写成空列表 `[]` 或不是列表 → 打 `⚠️` 跳过，不会静默"全部通过"；
- 只要一个值就用 `eq`；要排除某几个值用下面的 `not_in_list`（黑名单）。

**3.3 黑名单 → `not_in_list`**（`in_list` 的反面：命中禁值即失败，用于「不能是 X」）

```python
{"desc": "task_status 不能是删除态", "kind": "not_in_list", "path": "task_status",
  "value": ["deleted", "archived"]},
```

```
✅ task_status 不能是删除态: 实际 'operating'，不在禁止 ['deleted', 'archived'] 中
❌ task_status 不能是删除态: 实际 'deleted'，命中禁止 ['deleted', 'archived']
```

- 判定、`loose`、`null_ok`、数组逐项、`path` 投影规则与 `in_list` 完全对称，只是方向相反；
- `value` 写空列表 → **ℹ️ 视为通过**（没有禁止值，等于没限制）；`value` 不是列表 → `⚠️` 跳过；
- 白名单优先：**能列出「允许哪些」就别写黑名单**——黑名单只挡住你想到的那几个值，服务端新加一个状态照样通过；
  只有确实只能枚举少数坏值时（`deleted` / `archived`）再用它。

**3.5 大小比较 → `gt` / `gte` / `lt` / `lte`**（`>` / `>=` / `<` / `<=`，写法和 `eq` 一样）

```python
{"desc": "confidence_score >= 0.4", "kind": "gte", "path": "confidence_score", "value": 0.4},
{"desc": "confidence_score <= 1",   "kind": "lte", "path": "confidence_score", "value": 1},
{"desc": "task_id 是正数",           "kind": "gt",  "path": "task_id", "value": 0},
```

```
✅ confidence_score >= 0.4: 实际 0.48 >= 0.4 → 成立
❌ confidence_score <= 1: 实际 1.2 <= 1 → 不成立
```

**时间也能比**：两边同为 ISO 8601 时间串时自动按时间比较（输出末尾带 `（按时间）`）：

```python
{"desc": "事件时间不早于请求时间", "kind": "gte", "path": "event_time", "shared_key": "_body.event_time"},
{"desc": "created_at 晚于 2026-05-15", "kind": "gt", "path": "created_at", "value": "2026-05-15"},
```

```
✅ 事件时间不早于请求时间: 实际 '2026-05-15T08:00:36.782976Z' >= shared '2026-05-15T08:00:00Z'（按时间） → 成立
```

认得的写法：`2026-05-15`、`2026-05-15T08:00:00`、`2026-05-15 08:00:00`（空格分隔）、带 `.782976` 微秒、
带 `Z` 或 `+08:00` / `+0800` 时区。**没写时区的一律按 UTC**，所以 `2026-05-15T16:00:00+08:00` 与
`2026-05-15T08:00:00Z` 是同一时刻；微秒和秒级也能直接比。

- **两边都必须是数字或都是时间串**：`"5"`、`null`、`true` / `false` 都判 ❌ 并打印实际类型，不做隐式转换；
  一边数字一边时间串同样判 ❌；**普通文本绝不按字典序比较**（否则 `"abc" > "abd"` 会让配错的检查悄悄通过）；
- **比较基准可换成请求值**：写 `shared_key` 代替 `value`，就是拿响应值和 `context.shared` 里的值比
  （`{"kind": "gte", "path": "id", "shared_key": "_query.id"}` → `✅ 实际 116 >= shared 103`）；
  两个都写时按 `shared_key` 比较并打 ⚠️；`shared` 里没有该键默认 ℹ️ 跳过，加 `require_shared: True` 改判 ❌；
- 区间用两条（`gte` + `lte`），引擎没有 `between`；
- 字段缺失判 ❌，值为 `null` 也判 ❌，两种情况都可以加 `"null_ok": True` 放行。

**3.6 条件检查 → `when`**（任意 kind 都能加；条件不成立就整条跳过，ℹ️ 不计失败）

同一个接口常被不同参数访问（`?event_type_ids=103` 与 `?event_type_ids=other`），要求各不相同。
`when` 让一条检查只在特定条件下生效，一份清单就能覆盖多种参数组合：

```python
# 数字过滤：响应每条只需包含该 event_type（可能还有别的）
{"desc": "event_type_ids 响应与请求检查", "kind": "shared_contains",
  "path": "event_types.event_type_id", "shared_key": "_query_all.event_type_ids", "loose": True,
  "when": {"shared_key": "_query_all.event_type_ids.0", "numeric": True}},

# 关键字过滤 other：这类图片不带 event_type，响应 event_types 应为空
{"desc": "other 过滤时 event_types 应为空", "kind": "eq", "path": "event_types", "value": [],
  "when": {"shared_key": "_query_all.event_type_ids.0", "eq": "other"}},
```

```
?event_type_ids=103   → ✅ 响应包含请求的 event_type: 实际 [103]，请求的 1 项都在响应中
                        ℹ️ other 过滤时 event_types 应为空: when 条件不成立（shared _query_all.event_type_ids.0 = '103'），跳过
?event_type_ids=other → ℹ️ 响应包含请求的 event_type: when 条件不成立（… = 'other'），跳过
                        ✅ other 过滤时 event_types 应为空: 实际 [] / 期望 []
```

条件怎么写（`shared_key` 取请求侧，`path` 取响应侧）：

| 判断 | 例子 | 成立条件 |
| --- | --- | --- |
| `eq` | `{"shared_key": "_query_all.event_type_ids.0", "eq": "other"}` | 取值 == 常量 |
| `in` | `{"shared_key": "_query_all.event_type_ids", "in": ["103", "207"]}` | 取值（或数组每项）都在集合内 |
| `numeric` | `{"shared_key": "_query_all.event_type_ids.0", "numeric": True}` | 能当数字用（`'103'` 算，`'other'` 不算）；写 `false` 表示反过来 |
| 用响应字段 | `{"path": "status", "eq": "failed"}` | 响应里该字段等于常量 |

- 多个判断写在一起是**且**关系，全部成立才执行；加 `"loose": True` 同样放宽「数字 ↔ 数字字符串」。
- 条件**取不到**（`shared` 没写入、字段不存在）打 `⚠️ … 本条跳过（没在检查）`，不会判断成 ❌——
  免得 `onRequest` 没生效时一片假红。
- `when` 放在 `for_each` / `sub_checks` 上时按元素逐个判断（外层元素也能用 `${..字段}`）。
- 断言「数组为空」直接用 `eq` + `"value": []`，不需要额外的 kind。

**4. 严格存在性 → `exists`**（默认 `null` 与空串 `""` 都判失败；`null_ok: True` 才放行）

```python
{"desc": "confidence_threshold 必须非 null", "kind": "exists", "path": "confidence_threshold"},
{"desc": "geometry.type 字段是否存在(允许null)", "kind": "exists", "path": "geometry.type", "null_ok": True},
```

批量形式用 `fields`，一次查多个顶层字段：

```python
{"desc": "event_types 字段是否存在(允许null)", "kind": "exists",
  "null_ok": True, "optional": True,
  "fields": ["frequency", "detecting_duration", "detecting_threshold", "interval", "zones"]},
```

这里 `optional: True` 表示这些字段本身是**可选项**：缺失只提示、不算失败（随 `event_type` 不同而不同）。

> `0`、`false`、`[]`、`{}` **不算空值**，不会被 `exists` 判失败——判空只针对 `null` 和 `""`。

**5. 数组逐项 → `for_each` + `sub`（可套两层）**

```python
{"desc": "event_types.zones 每个区域必需字段", "kind": "for_each", "path": "event_types", "sub":
  [{"desc": "zones 每项", "kind": "for_each", "path": "zones", "null_ok": True, "sub":
    [{"desc": "区域必需字段", "kind": "top_fields", "fields":
      ["id", "name", "polygon_type", "geometry"]
    },
    {"desc": "geometry.type 字段是否存在(允许null)", "kind": "exists", "path": "geometry.type"},
    {"desc": "geometry.coordinates 字段是否存在", "kind": "exists", "path": "geometry.coordinates"}]
  }]
},
```

`null_ok: True` 在这里表示：某些 event_type **没有 `zones` 数组**也放行（可选数组）。

加 `"label": "id"` 后，每条输出会带上该元素的值，长列表里不用数下标就知道是哪个：

```python
{"desc": "event_types 每项", "kind": "for_each", "path": "event_types", "label": "id", "sub": [...]}
```

```
✅ event_types 每项[2] id=206·必需字段
❌ event_types 每项[3] id=103·必需字段: 缺少 ['name']
```

`label` 只是显示层：字段取不到、或值是对象/数组时，退回纯下标 `[2]`，判定结果完全不受影响。

数组套数组还可以用 `"path": "."` 指回「当前元素本身」，省掉一层多余字段名：

```python
{"desc": "detected_objects 逐组", "kind": "for_each", "path": "detected_objects", "sub":
  [{"desc": "组内逐框", "kind": "for_each", "path": ".", "sub":
    [{"desc": "框必需字段", "kind": "top_fields", "fields": ["label", "confidence", "bbox"]}]
  }]
},
```

**6. `list_field`**（当前规则未用到）

数组里每个元素都必须含某字段；数组为 `null` 或父级为 `null` 视为正常。具体键名以 `reqable_check_core.py` 的实现为准。

**7. 与请求参数比对 → `shared_eq` / `shared_in` / `shared_not_in` / `shared_contains`**（详见第五节）

```python
# 响应回显请求体里的字段（请求体顶层字段已平铺到 shared 根上）
{"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq",
  "path": "event_type_id", "require_shared": True},

# 列表接口：返回的每条记录 id 都属于请求 ?ids=1&ids=2
{"desc": "每条 id 都属于请求的 ids", "kind": "shared_in",
  "path": "id", "shared_key": "_query.ids", "require_shared": True},

# 排除名单：返回的 id 不能出现在 ?exclude_ids=9&exclude_ids=10 里
{"desc": "id 不在排除名单", "kind": "shared_not_in",
  "path": "id", "shared_key": "_query.exclude_ids", "require_shared": True},

# 创建接口：响应必须包含请求传的每个 id（服务端会补默认项，不能要求完全一致）
{"desc": "event_type_ids 响应包含请求", "kind": "shared_contains",
  "path": "event_types.id", "shared_key": "event_type_ids", "require_shared": True},
```

### null / 缺失规则（最容易混）

| 场景 | 行为 |
| --- | --- |
| `top_fields` 查的子对象为 `null` / 父级为 `null` | 视为正常，不报错 |
| `top_fields` 查的子对象为 `{}` / `[]` | 默认 ❌（字段全缺），`null_ok: True` 放行 |
| `top_fields` 查的子对象**整体不存在** | 默认 ❌，`optional: True` 放行 |
| `sub_checks` 指向的对象为 `null` / 父级为 `null` | 整组 ℹ️ 跳过，不计失败 |
| `sub_checks` 指向的字段整体不存在 | 默认 ❌，`optional: True`（旧写法 `null_ok: True`）放行 |
| `list_field` / `for_each` 的数组为 `null` / 父级为 `null` | 视为正常 |
| `exists` 字段值为 `null` 或 `""` | 默认**判失败**，`null_ok: True` 才放行 |
| `exists` 字段值为 `0` / `false` / `[]` | 正常，不算空值 |
| `for_each` / `list_field` 的数组字段**整体不存在** | 默认 ❌，`optional: True`（旧写法 `null_ok: True`）放行 |
| `optional: True` 的字段整体缺失 | 只提示，不算失败 |

一句话：`null_ok` 管「值是 null / 空串（对象则为 `{}`）」，`optional` 管「东西压根没有」；容器类（对象 / 数组）两者都认，比较类只认 `optional`。

### 整体级检查：`META_CHECKS`（分页 `page` / `size` / `total`）

`checks` 是**每条记录跑一遍**，所以分页信封上的 `page` / `size` / `total_pages` / `total` 它取不到。这类字段写进 `META_CHECKS`：**只跑一次、对象是整个响应 `data`**，`kind` 语法与 `checks` 完全一样。

```python
# 引擎里默认 META_CHECKS = []，规则脚本里覆盖即可
META_CHECKS = [
    {"desc": "分页字段齐全", "kind": "top_fields", "fields": ["page", "size", "total_pages", "total"]},
    {"desc": "page 从 1 开始", "kind": "eq", "path": "page", "value": 1},
    {"desc": "size 为 5", "kind": "eq", "path": "size", "value": 5},
]
```

输出排在逐条检查之后、总结之前：

```
✅ 请求成功: page=1, total=2, size=5, 返回 2 条

—— 检查 [0] 事件记录 ——
...
—— 检查 [整体] ——
✅ 分页字段齐全
✅ page 从 1 开始: 实际 1 / 期望 1
❌ size 为 5: 实际 10 / 期望 5

✅ Response成功！响应码预期是200: 实际结果200，CheckList检查完成，失败项: 1
```

三条注意事项：

- **不写 `META_CHECKS` 完全没问题**：引擎按 `globals().get("META_CHECKS") or []` 取，未定义、`[]`、`None` 都当空——不报错，也不多打印一行。
- **`path` 从 `data` 顶层写起**：`total` / `page` 直接写字段名，别写 `results.0.xxx`；`results` 里逐条的字段仍归 `checks`。
- **末页 `size` ≠ 实际条数**：`size=5` 只回 1 条很正常，别断言 `len(results) == size`；`eq` 只比常量，也做不了 `total == len(results)` 这种动态对比，真要算就在规则脚本里自己算好常量再写。

---

## 五、跨请求校验：`context.shared`

### 为什么需要

Reqable 的 `onRequest` 与 `onResponse` **在两个进程里执行**，模块级变量不互通。要在响应侧拿到请求里的值（请求体字段、查询参数），必须由 `onRequest` 写进 `context.shared`，`onResponse` 再读出来。

### 1) 引擎的 `onRequest` 收集了什么

引擎内置了通用的 `onRequest`，**规则脚本不用再写**。它不认接口名、不认参数名，挂到哪个接口上都只读不改：

| 键 | 内容 | 例子 |
| --- | --- | --- |
| 请求体顶层字段 | JSON body 的每个字段平铺到 `shared` 根上 | body `{"event_type_id": 116}` → `shared["event_type_id"]` |
| `_body` | 原始请求体结构（body 是数组、或要取嵌套字段时用） | `_body.data.object_key` |
| `_query` | 查询参数：单值→标量、重复 key→列表、纯数字转 `int`，**URL 解码** | `?ids=1&ids=2` → `{"ids": [1, 2]}` |
| `_query_all` | 查询参数：一律列表、字符串（不转 `int`），同样 URL 解码 | `{"ids": ["1", "2"]}` |
| 路径末两段 | 末段是 ID 时，倒数第二段当键、末段当值（详见 3)） | `/v2/events/record/xxxxxx` → `{"record": xxxxxx}` |

取值规则：

- 重复 key 合并成列表：`?location_ids=3&location_ids=2` → `[3, 2]`
- 逗号分隔且每段都是数字也转列表：`?ids=1,2` → `[1, 2]`
- 前导 0 的数字串保持字符串：`?code=007` → `"007"`
- **做 URL 解码**：`?event_record_status=False%20Alarm` → `"False Alarm"`，中文同理（`%E4%B8%AD...` → `中文`）；
  不做这一步，响应里的 `"False Alarm"` 永远对不上请求里的 `"False%20Alarm"`，每条都判 ❌
- **`+` 不当作空格**：`?q=a+b` → `"a+b"`。要空格请用 `%20`，要字面加号也直接用 `+`
- GET 没有 body、URL 也没有 query 时，`shared` 是 `{}`

`onRequest` 会把它打印出来，照着写 `shared_key` 最省事：

```
request url https://.../observ/apiserver/v2/tasks?location_ids=3&location_ids=2
shared = {"_query": {"location_ids": [3, 2]}, "_query_all": {"location_ids": ["3", "2"]}}
```

带空格的值（URL 里是 `%20`，`shared` 里已经是空格）：

```
request url https://.../v2/events/record?event_record_status=False%20Alarm
shared = {"_query": {"event_record_status": "False Alarm"}, "_query_all": {"event_record_status": ["False Alarm"]}}
```

### 2) 清单侧：`shared_eq` / `shared_in` / `shared_not_in` / `shared_contains`

| 键 | 指向 |
| --- | --- |
| `path` / `key` | **响应**里的字段 |
| `shared_key` | **`context.shared`** 里的取值路径（点分），省略时退化为 `path` / `key` |
| `require_shared` | `True` 时 shared 缺该字段判 ❌，否则 ℹ️ 跳过 |

- `shared_eq`：响应值 **==** shared 值（请求体回显、单值参数）；类型严格，`'3000'` 与 `3000` 不相等
  - 唯一例外是显式加 `"loose": True`：只放宽「数字 ↔ 数字字符串」这一种，`'3000'` 与 `3000`、`'-1'` 与 `-1`、`'3.0'` 与 `3` 算相等
  - 不放宽的部分：`'abc'` 与 `'ABC'`、`None` 与 `'None'`、`[]` 与 `''` 仍判不相等；`bool` 不参与（`True` 不等于 `1` / `'1'`）
  - **两边都是数组时逐项放宽**：`path` 投影成数组（如 `event_types.event_type_id` → `[103]`）对 `_query_all` 的 `['103']` 算相等；长度不同、顺序不同仍判 ❌——`[103, 17469]` 对 `['103']` 该用 `shared_contains`
  - 放宽生效时输出会追一句，便于识别：`✅ …: 实际 '3000' / 请求中携带的 3000（按 loose 视为相等）`
- `shared_in`：响应值 **属于** shared 里的列表（列表接口逐条校验）；响应值是数组时，要求**每个元素都属于**，有一个不在就判 ❌（如 `detail.task_ids` vs 请求的 `ids`）
- `shared_not_in`：响应值 **不属于** shared 里的列表（**排除名单**，`shared_in` 的反面）；响应值是数组时，要求**每个元素都不命中**，命中一个就判 ❌ 并列出命中项；shared 是空列表 `[]` 时没有可排除的值，打 ℹ️ 视为通过并说明原因
- `shared_contains`：响应数组 **包含** shared 里的每个值（**响应 ⊇ 请求**，允许服务端多给）；创建类接口必用——服务端会补默认项（如默认 event_types），此时 `shared_in`（每项都属于请求）必然失败；缺少哪几个会直接列出来；shared 是空列表时打 ℹ️ 视为通过
- 这三条与 `shared_eq` 一样认 `"loose": True`：`_query_all` 里的值全是字符串，响应是数字时（`103` vs `'103'`）不加 loose 判不过
- 同一接口被不同参数访问时，用 `when` 让检查只在对应参数下生效（见「3.6 条件检查」）

```python
# 请求体回显（顶层字段已平铺，可省略 shared_key）
{"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq",
  "path": "event_type_id", "require_shared": True},

# 嵌套请求体字段走 _body
{"desc": "object_key 与请求一致", "kind": "shared_eq",
  "path": "object_key", "shared_key": "_body.data.object_key"},

# 422 的 input 是原始字符串，query 参数已被转成 int —— 加 loose 让 '3000' 等于 3000
#   ?size=3000 → shared: _query.size = 3000(int) / _query_all.size = ["3000"](str)
{"desc": "input 与请求参数一致", "kind": "shared_eq",
  "path": "detail.0.input", "shared_key": "_query.size", "loose": True, "require_shared": True},
# 不想放宽类型就去取原始字符串，效果一样
{"desc": "input 与请求参数一致", "kind": "shared_eq",
  "path": "detail.0.input", "shared_key": "_query_all.size.0", "require_shared": True},

# 过滤接口：?event_type_ids=103 返回的图片，event_types 里可能还带别的类型
#   响应投影 [103] / [103, 17469]，请求侧 _query_all 是 ['103'] → 用 shared_contains + loose
#   这里千万别用 shared_eq：它要求两边一模一样，[103, 17469] 永远过不了
{"desc": "event_type_ids 响应与请求检查", "kind": "shared_contains",
  "path": "event_types.event_type_id", "shared_key": "_query_all.event_type_ids", "loose": True},

# 列表接口：?ids=1&ids=2 返回 {"total":2,"results":[...]}，逐条判归属
{"desc": "每条 id 都属于请求的 ids", "kind": "shared_in",
  "path": "id", "shared_key": "_query.ids", "require_shared": True},

# 请求体是数组：[{"event_type_id":103},{"event_type_id":206}]，取字段自动投影成列表
{"desc": "每条 event_type_id 都属于请求", "kind": "for_each", "path": "successful", "sub":
  [{"desc": "event_type_id 属于请求", "kind": "shared_in", "path": "event_type_id",
    "shared_key": "_body.event_type_id", "require_shared": True}]
},

# 响应字段本身是数组：detail.task_ids = [144310, 144311] 对 ?ids=144310，逐个判归属
{"desc": "每条 task_id 都属于请求", "kind": "shared_in",
  "path": "detail.task_ids", "shared_key": "_query.ids", "require_shared": True},

# 排除名单：请求 ?exclude_ids=9&exclude_ids=10，返回的 id 一个都不能落在名单里
{"desc": "id 不在排除名单", "kind": "shared_not_in",
  "path": "id", "shared_key": "_query.exclude_ids", "require_shared": True},

# 响应数组对排除名单：每个元素都不能命中（如返回的 task_ids 不含已删除的）
{"desc": "task_ids 不含已排除的 id", "kind": "shared_not_in",
  "path": "detail.task_ids", "shared_key": "_body.exclude_ids", "require_shared": True},

# 创建接口：请求只传了 event_type_ids=[103]，响应多了服务端默认项（15608 / 206 / 207）
{"desc": "event_type_ids 响应包含请求", "kind": "shared_contains",
  "path": "event_types.id", "shared_key": "event_type_ids", "require_shared": True},

# 元素字段不统一：events 里第一条写 vlm_flow_id、其余写 id —— 用 ? 松散投影，各查一遍
{"desc": "请求的 event id 都出现在响应中", "kind": "shared_contains",
  "path": "event_types.id", "shared_key": "_body.events.id?", "require_shared": True},
{"desc": "请求的 vlm_flow_id 都出现在响应中", "kind": "shared_contains",
  "path": "event_types.id", "shared_key": "_body.events.vlm_flow_id?", "require_shared": True},
```

输出示例：

```
✅ 响应 event_type_id 与请求一致: 实际 116 / 请求中携带的 116
❌ 每条 id 都属于请求的 ids: 实际 141076，不在 [129728] 中
✅ 每条 task_id 都属于请求: 实际 [144310]，1 项都属于请求
❌ 每条 task_id 都属于请求: 实际 [144310, 144311]，其中 [144311] 不在请求消息 [144310] 中
❌ 每条 task_id 都属于请求: 取不到 detail.task_idsss（字段不存在或路径写错）
ℹ️ 响应 id 与 URL 中的 ID 一致: context.shared 不可用或没有 record，跳过
✅ id 不在排除名单: 实际 5
❌ id 不在排除名单: 实际 9，命中排除名单 [9, 10]
✅ task_ids 不含已排除的 id: 实际 [144310, 144311]，2 项都不在排除名单
❌ task_ids 不含已排除的 id: 实际 [1, 9, 10]，其中 [9, 10] 命中排除名单 [9, 10]
ℹ️ id 不在排除名单: shared exclude_ids 是空列表，没有可排除的值（视为通过）
✅ event_type_ids 响应包含请求: 实际 [15608, 206, 103, 207]，请求的 1 项都在响应中
❌ event_type_ids 响应包含请求: 实际 [15608, 206]，缺少请求中的 [103]
ℹ️ event_type_ids 响应包含请求: shared event_type_ids 是空列表，没有要求包含的值（视为通过）
❌ 请求的 event id 都出现在响应中: 实际 [15608, 15594, 206, 103, 15903, '...共7个']，缺少请求中的 [112, 113, 13892]
✅ 请求的 vlm_flow_id 都出现在响应中: 实际 [15608, 15594, 206, 103, 15903, '...共7个']，请求的 1 项都在响应中
ℹ️ 请求的 vlm_flow_id 都出现在响应中: shared _body.events.vlm_flow_id? 是空列表，没有要求包含的值（视为通过）
```

> **类型要一致**：两者都是严格相等。`_query` 已把纯数字转成 `int`，响应是数字就能直接比；响应侧是字符串时改用 `_query_all`（保留字符串类型，不转 `int`，但同样做了 URL 解码）。
>
> **常见误配**：把 `shared_key` 写成 `"shared"`。它填的是 `shared` 这个 dict 里的键名（如 `event_type_id`、`_query.ids`），不是 `shared` 本身。
>
> **关键项加 `require_shared: True`**：否则 `onRequest` 没跑到（脚本报错、请求没经过 hook）时这条会**静默跳过**，看起来通过其实没校验。
>
> **数组不用手写 `onRequest`**：`path` / `shared_key` 遇到数组时，写数字是下标（`_body.0.task_id` → `144838`），写字段名则**投影成列表**（`_body.event_type_id` → `[103, 206]`）。投影要求每项都是对象且都有该字段，有元素缺字段就算取不到，不会返回残缺列表去比对。
>
> **字段不统一的数组用松散投影**：字段名后加 `?`（如 `_body.events.id?`），只保留有该字段的元素，缺字段的直接跳过；一个元素都没有该字段时返回空列表 `[]`（仍算取到），配合 `shared_contains` 打 ℹ️ 说明「没有要求包含的值」，不会误报。典型场景：请求 `events` 里有的写 `id`、有的写 `vlm_flow_id`——严格投影会整体取不到，`id` 侧那批会被漏检。
>
> **数组套数组**（`events[].zones[]`）用 `*` 摊平、`[字段=值]` 配对、`${字段}` 占位，详见本节 2.5。

### 2.5) 数组套数组：`*` 摊平、`[字段=值]` 配对、`${字段}` 占位

`events[]` 里每个 event 还带 `zones[]` 时，路径要多走一层。三件小工具：

| 写法 | 作用 | 例子 |
|---|---|---|
| `*` | **摊平一层**，把 `[[a],[b]]` 变成 `[a,b]` | `event_types.zones?.*.id?` → `[102, 106, 102, 104]` |
| `[字段=值]` | **按值配对**，在数组里找第一条匹配项；多个条件用 `\|` 表示任一命中 | `_body.events[id=103]` → 请求里 id=103 那条 event |
| `${字段}` / `${..字段}` | **占位符**，取当前元素 / 往上一层的字段值 | `[id=${..id}]` 用外层 event 的 id 去配对 |

合起来就能表达「**先用外层 id 配对，配上了再比 zone id、再比坐标**」这三层顺序：

```python
# ① 集合层：请求里的每个 event 都得在响应里（抓「没保存成功」）
{"desc": "请求的 event 都出现在响应中", "kind": "shared_contains",
  "path": "event_types.id", "shared_key": "_body.events.id?", "require_shared": True},

# ② 逐 event：外层 id 配上了才往下比 zones
{"desc": "event 与请求对账", "kind": "for_each", "path": "event_types", "label": "id", "sub":
  [ # ②-1 zone id 是否一致（请求的每个 zone 都要在响应里）
    {"desc": "zone id 包含请求的", "kind": "shared_contains", "path": "zones?.id",
      "shared_key": "_body.events[id=${id}|vlm_flow_id=${id}].zones.id?"
    },
    # ②-2 同一个 zone id，比坐标
    {"desc": "zone 坐标", "kind": "for_each", "path": "zones?", "null_ok": True, "label": "id", "sub":
      [{"desc": "coordinates 一致", "kind": "shared_eq", "path": "geometry.coordinates",
        "shared_key": "_body.events[id=${..id}|vlm_flow_id=${..id}].zones[id=${id}].coordinates"
      }]
    }
  ]
}
```

输出（服务端把坐标改回整幅默认框，只有 206 / 103 两条能配上对）：

```
❌ 请求的 event 都出现在响应中: 实际 [15608, 15594, 206, 103, 15903, '...共7个']，缺少请求中的 [112, 113, 13892]
ℹ️ event 与请求对账[0] id=15608·zone id 包含请求的: 请求里没有配对的元素…，跳过
ℹ️ event 与请求对账[1] id=15594·zone id 包含请求的: 请求里没有配对的元素…，跳过
✅ event 与请求对账[2] id=206·zone id 包含请求的: 实际 [106]，请求的 1 项都在响应中
❌ event 与请求对账[2] id=206·zone 坐标[0] id=106·coordinates 一致: 实际 [[[[0.0, 0.0], …]]] / 请求中携带的 [[[[0.2, 0.3], …]]]
✅ event 与请求对账[3] id=103·zone id 包含请求的: 实际 [102]，请求的 1 项都在响应中
❌ event 与请求对账[3] id=103·zone 坐标[0] id=102·coordinates 一致: 实际 [[[[0.0, 0.0], …]]] / 请求中携带的 [[[[0.2, 0.3], …]]]
```

读法：`[2] id=206` 说明外层配上了 → `zone id` ✅ 说明 zone 也是同一个 → `coordinates` ❌ 说明**坐标没按请求保存**。`[0] [1] [4] [5] [6]` 全是 ℹ️，因为请求里没有这些 event（服务端默认项），不误报。

四个要点：

- **配对不到默认只 ℹ️ 跳过**（不判 ❌），因为服务端会返回请求里没有的默认 event_types；想让缺失变成失败，加 `"require_shared": True`。
- **`[k=v]` 取第一条命中**：同一个 id 在数组里重复时只校验第一条，重复数据请先用 L1 的 `shared_contains` 兜住数量。
- **坐标是严格相等**：`0.2` 与 `0.2000000001` 算不一致；服务端做过精度归一化时，这类比对会误报，需要先确认。
- **每层 `for_each` 的 `path` 都从当前元素写起**：外层 `event_types`，内层 `zones?`；没有 zones 的 event 靠内层的 `null_ok: True` 放行。
- **`label` 让输出带上元素标识**（`"label": "id"` → `[2] id=206`），多层嵌套时不用数下标就知道是哪条；它只影响显示，不影响判定。

### 3) URL 路径里的 ID

引擎已经自动收了：取路径**末两段**当「键 = 值」，末段是纯数字（转 `int`）或 UUID（保留原始字符串）才写入，键名就是倒数第二段：

```
request url https://.../v2/events/record/xxxxxx
shared = {"record": xxxxxx}
```

清单侧直接用那段的名字：

```python
{"desc": "响应 id 与 URL 中的 ID 一致", "kind": "shared_eq",
  "path": "id", "shared_key": "record", "require_shared": True},
```

四条规则：

- **末段不像 ID 就不收**：`/tasks/batch-task/update_type` 这种尾巴是动作名，`shared` 保持原样，不会塞进垃圾键。
- **键名允许字母、下划线、连字符**：`v2` 这类带数字的段不当键名；连字符**原样保留**，`/v2/events/vlm-relationship/206` → `shared["vlm-relationship"] = 206`，`shared_key` 写 `"vlm-relationship"`（`-` 不是点分分隔符，能正常取到）。
- **和请求体字段重名时以请求体为准**：`/clusters/7` + body `{"clusters": [7]}`，`shared["clusters"]` 是 body 的值，路径值不覆盖。
- **只在 ID 位于末段时有效**：`/record/{id}/objects` 这类 ID 在中间、或想一次取多个段，自己补 `onRequest`：

```python
_engine_onRequest = onRequest          # 覆盖前先存住引擎的实现

def onRequest(context, request):
    request = _engine_onRequest(context, request)   # 请求体 / 查询参数 / 末两段照旧
    nums = [int(s) for s in str(context.url).split("?")[0].split("/") if s.isdigit()]
    if nums:
        context.shared["_path_ids"] = nums          # 存 int，响应里的 id 才是数字
        _print_shared(context)                      # 合并后再打一次
    return request
```

清单侧：

```python
{"desc": "响应 id 与 URL 中的 ID 一致", "kind": "shared_eq",
  "path": "id", "shared_key": "_path_ids.0", "require_shared": True},
```

- **存 `int` 不能存 `str`**：`144310 != "144310"`，存成字符串会永远失败。
- **匹配不到就不要写这个键**：写 `{"_path_ids": None}` 是「有键但值为空」→ 判 ❌；不写才会 ℹ️ 跳过。
- 自定义部分同样是通用写法（取路径里所有纯数字段），**不要写死 `/v2/tasks`、`task_id`** 这类专用路径与键名。
- 这里的 `_path_ids`、`_path_id` 都是**自己起的键名**，引擎不产生，纯自定义；引擎只产生路径**末两段**那一对
  `<倒数第二段>: <末段值>`（如 `record` / `tasks`）。

---

## 六、当前规则覆盖的字段树

```
每条结果（顶层必需字段 12 项）
├─ camera（单对象，sub_checks 整组）→ id name source_url fps resolution_height
│                             resolution_width model_name coordinates address
│  ├─ coordinates           → latitude longitude
│  └─ source_url            → 非 null 断言
├─ location（单对象）       → id name timezone organization_id coordinates
│  └─ coordinates           → latitude longitude
├─ cluster（单对象）        → id name address
├─ scheduler（单对象）      → type scheduled_times
├─ event_types（数组，逐项） → id name is_detecting scheduled_times
│  ├─ 可选字段（exists + null_ok + optional）
│  │    frequency detecting_duration detecting_threshold interval zones
│  └─ zones（数组套数组，两层 for_each）
│       └─ 每项 → id name polygon_type geometry
│            ├─ geometry.type        （exists，允许 null）
│            └─ geometry.coordinates（exists）
├─ snapshot
├─ object_size_filter        → 非 null 断言
└─ confidence_threshold     → 非 null 断言

另有：
  camera.source_url                 → 非 null 断言（在 sub_checks 内）
  location.timezone == Asia/Taipei  → eq 固定值断言
```

## 七、新增一条检查

在 `checks` 列表里追加一项即可，规则按列表顺序执行。例如：

```python
# 新增固定值断言
{"desc": "operating_status 应为 running", "kind": "eq",
  "key": "operating_status", "value": "running"},

# 新增非 null 断言
{"desc": "cluster.address 必须非 null", "kind": "exists", "path": "cluster.address"},

# 新增枚举取值断言
{"desc": "task_status 取值", "kind": "in_list", "path": "task_status",
  "value": ["operating", "non-operating"]},

# 新增黑名单断言
{"desc": "task_status 不能是删除态", "kind": "not_in_list", "path": "task_status",
  "value": ["deleted", "archived"]},

# 新增「响应与请求一致」
{"desc": "响应 device_id 与请求一致", "kind": "shared_eq", "path": "device_id", "require_shared": True},

# 新增「列表逐条归属请求参数」
{"desc": "每条 id 都属于请求的 ids", "kind": "shared_in", "path": "id", "shared_key": "_query.ids"},

# 新增「可选对象打包一组子检查」
{"desc": "cluster", "kind": "sub_checks", "path": "cluster", "sub":
  [{"desc": "必需字段", "kind": "top_fields", "fields": ["id", "name", "address"]}]
},
```

`desc` 建议写清「对象 + 字段」，报错时能一眼定位。

## 八、常见坑

1. **CORE 路径**：绝对路径 + `expanduser("~")`，别用裸相对路径。
2. **单个对象不能用 `for_each`**：`camera` / `location` / `cluster` / `scheduler` 都是对象，用 `sub_checks`（字段多、对象可空时）或 `top_fields` + `path`（字段少时）；`for_each` 的 `path` 必须指向数组，否则会报错。
3. **数组套数组要两层 `for_each`**：`event_types` → `zones`；可选数组记得加 `null_ok: True`。
4. **path 数组下标**：点分 + 数字下标，如 `vlms.0.x`。
5. **`null_ok` vs `optional`**：前者放行 null / 空串值，后者放行「东西整体没有」。容器类（`top_fields` / `sub_checks` / `for_each` / `list_field`）两者都认，比较类（`eq` / `in_list` / `not_in_list` / `shared_eq` / `gt`·`gte`·`lt`·`lte`）只认 `optional`——写 `optional` 不会顺带放过 `null`。
6. **`EXPECTED_CODE` 默认 200**：其它状态码（201 / 204 / 4xx）要在规则脚本里显式覆盖。
7. **类型严格相等**：`eq` / `in_list` / `not_in_list` / `shared_eq` 都是 `==` 比较，`True` 与 `"True"`、`103` 与 `"103"`、`[]` 与 `"[]"` 都不相等。期望值写成 Python 字面量，别加引号。`_query_all` 里的值**全是字符串**，跟数字比要么加 `loose`，要么取单个下标再配 `loose`。
8. **规则脚本里写 `onRequest` 会覆盖引擎的**：引擎注入的 `onRequest` 不再生效，请求体 / 查询参数的收集要自己补。推荐先 `_engine_onRequest = onRequest` 存一份再调用（见第五节 3)。
9. **204 没有响应体**：`EXPECTED_CODE = 204` 会因 `JSON 解析失败` 提前返回，成功场景别和 200 的清单共用一份。
10. **数组元素不是对象时别用 `for_each`**：同一个 `event_types`，详情接口返回对象数组，列表接口可能只返回 ID 数组（`[168, 169]`）。对 ID 数组跑 `for_each`，每个元素都会报「数组元素是 int，不是对象」。先确认响应结构，ID 数组只需 `exists` 或 `top_fields`。
11. **配置写错不会中断整轮检查**：每条检查单独兜底，`list_field` 漏 `field`、`top_fields` 漏 `fields` 会打 `⚠️ ... 跳过`，其它异常打 `❌ ... 检查执行异常`，后面的检查照常执行。
12. **写错键名不会报错、只会「永远通过」**：`exists` 里写 `sub`、`shared_in` 写成 `shared` 之类的键，引擎不认就直接忽略。现在会打 `⚠️ kind=xxx 不支持 [...]`，看到就改；`shared_in` / `shared_eq` 取不到路径时也会明确打 `❌ ... 取不到 xxx（字段不存在或路径写错）`，不再静默通过。
13. **`META_CHECKS` 里写 `results.0.x` 取不到**：它拿到的是整个 `data`（信封），分页时 `results` 是数组，逐条字段仍然只能用 `checks`；`META_CHECKS` 只管 `page` / `size` / `total` 这类整体字段。

### 顺带：Pydantic 422 报文的坑

校验「参数校验失败」这类响应时，`detail` 是数组，每项含 `type` / `loc` / `msg` / `input` / `ctx` / `url`：

- **`loc` 长度不固定**：字段缺失 / 类型错是 2~4 段（`["body","vlm",0,"vlm_image_resize"]`）；模型级校验器（`value_error`）只到元素下标，3 段（`["body","triggers",0]`）。用 `eq` 整值比对时，场景变了就会失败，可改判 `loc.1 == "vlm"` 这类分段校验。
- **`literal_error` 看 `ctx.expected` 的引号**：`"'384', '576' or '768'"` 带单引号 → schema 是字符串枚举，要传 `"768"`；`"384, 576 or 768"` 不带引号 → 传数字 `768`。文档写「One of 384, 576, 768」时，一律先按字符串试。
- `input` 回显的是**出错那一层**的值（如 `vlm[0]` 整个对象），不是整个 body。

## 九、维护建议 / FAQ

- **硬编码的 `eq` 值**：`location.timezone == "Asia/Taipei"` 这类固定值断言在多地区 / 多环境数据下容易误报，建议按环境拆规则脚本或抽成可配置项。
- **改规则不动引擎**：`reqable_check_core.py` 被多个规则脚本共用，升级前先做回归。
- **可选字段 / 可选对象 / 可选数组都用 `optional`**：随 `event_type` 变化的字段（`frequency`、`zones`）别写成必需；对象配 `top_fields` + `path` 或 `sub_checks`，数组配 `for_each` / `list_field`，都加 `"optional": True`。
- **Q：报「公共引擎不存在」？** 检查 `~/Documents/reqable/reqable_check_core.py` 是否在位、`~` 是否正确展开。
- **Q：字段明明有值却判失败？** 看是不是 `exists` 默认严格（null / 空串也失败）、`for_each` 指到了对象而非数组，或 `eq` 的期望值类型写错（字符串 vs 数字）。`top_fields` 报缺失时看行尾的「实际有」列表——键名对不上就是 `path` 指错了对象（复制别的检查忘改）。
- **Q：`shared_eq` 一直显示「跳过」？** 先看 `onRequest` 打印的 `shared = {...}` 里有没有那个键；注意 `shared_key` 填的是键名，不是 `shared`。
- **Q：写了 `shared_key` 但没在比对？** 看是不是 kind 写成了 `exists` / `top_fields` 这类不认 `shared_key` 的——行首会有 `⚠️ kind=exists 不支持 ['shared_key']`。要比对就用 `shared_eq` / `shared_in` / `shared_not_in` / `shared_contains`。顺带一提：`exists` 默认把 `[]` 当空值判 ❌，`event_types: []` 这种会红。
- **Q：`shared` 里没有 URL 里的那个 ID？** 引擎只收「末两段、且末段像 ID（纯数字 / UUID）」，键名是**倒数第二段原样**——`/v2/events/record/xxxxxx` 是 `record`，不是 `id`；`/apiserver/v2/events/vlm-relationship/206` 是 `vlm-relationship`（连字符保留，不转下划线）；段名里带数字（`face-detection2`）或末段不像 ID 就不会收；`/record/{id}/objects` 这种 ID 在中间的要自己补（第五节 3）。
- **Q：URL 明明带了参数，`shared` 还是 `{}`？** 多半是 Reqable 里挂的引擎还是旧版（旧版 `onRequest` 只收请求体，GET 就是空）；换成当前 `reqable_check_core.py` 后 `?ids=1&ids=2` 会出现 `_query`。
- **Q：`sub_checks` 整组显示「跳过」？** 说明那个对象是 `null`，按设计视为正常。若它本该存在，另加一条 `{"desc": "camera 必须存在", "kind": "exists", "path": "camera"}` 断言非 null。
- **Q：`page` / `size` / `total` 写进 `checks` 一直取不到？** 它们不在单条记录上，属整体级，挪到 `META_CHECKS`（见第四节末）。`checks` 对每条 record 各跑一遍，信封字段本来就不在那儿。
- **Q：想临时跳过某条规则？** 直接从 `checks` 里删掉或注释那一项；整体级的同理，从 `META_CHECKS` 里去掉。
