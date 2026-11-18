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
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径，别用裸相对路径）")

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
| `path` | 点分路径，指向嵌套对象或数组；数组元素用下标，如 `vlms.0.x`；写 `"."` 表示当前对象本身（数组套数组时用） |
| `key` | 仅 `eq` / `exists` / `gt`·`gte`·`lt`·`lte` 的顶层字段写法 |
| `fields` | 批量字段名列表，用于 `top_fields` / 批量 `exists` |
| `value` | `eq` 的期望值；`gt` / `gte` / `lt` / `lte` 的比较基准（常量） |
| `sub` | `sub_checks` / `for_each` 的子检查列表，可继续嵌套 |
| `shared_key` | `shared_eq` / `shared_in` / `shared_not_in` / `gt`·`gte`·`lt`·`lte`：`context.shared` 里的取值路径（点分，如 `_query.ids`）；数组写字段名会投影成列表；省略时退化为 `path` / `key` |
| `require_shared` | `shared_eq` / `shared_in` / `shared_not_in` / `gt`·`gte`·`lt`·`lte`：`True` 时 `shared` 里没有该字段判 ❌，否则只 ℹ️ 跳过 |
| `null_ok` | `True` 时放行 `null` / 空串 `""`（含父级为 `null`）；在 `for_each` 上还表示「数组字段整体不存在」也放行 |
| `optional` | `True` 时字段整体缺失只提示、不算失败（随类型变化的可选字段） |

> 每个 `kind` 只认自己的键。写了它不支持的键（例如给 `exists` 塞 `sub`）不会报错，但那个键**不生效**，引擎会打一行 `⚠️ kind=exists 不支持 ['sub']，这些键被忽略`——看到这个提示说明这条多半没在检查你以为的内容。

### `kind` 一览

| kind | 用途 | 对象要求 |
| --- | --- | --- |
| `top_fields` | 必须存在的字段列表；加 `path` 可查嵌套子对象 | 单个对象 |
| `eq` | 字段值 == 期望值 | 任意可寻址字段 |
| `gt` / `gte` / `lt` / `lte` | 大小比较（`>` / `>=` / `<` / `<=`），两边同为数字或同为 ISO 时间串 | 任意可寻址字段（值为数字 / 时间串） |
| `exists` | 字段是否存在（默认严格，`null` 或 `""` 也判失败） | 单个或批量顶层字段 |
| `list_field` | 数组里每个元素都必须含某字段 | `path` 指向数组 |
| `shared_eq` | 响应字段 == `onRequest` 写入 `context.shared` 的值 | 任意可寻址字段 |
| `shared_in` | 响应字段属于 `context.shared` 里的列表（列表接口逐条校验）；响应字段本身是数组时，要求每个元素都属于 | 任意可寻址字段 / 数组 |
| `shared_not_in` | 响应字段**不属于** `context.shared` 里的列表（排除名单）；响应字段本身是数组时，要求每个元素都不命中 | 任意可寻址字段 / 数组 |
| `sub_checks` | 对单个对象执行 `sub` 里的一组子检查（可选对象打包用） | `path` 指向单个对象 |
| `for_each` | 对数组每个元素递归执行 `sub` 里的子检查 | `path` 必须指向数组 |

### 写法示例

**1. 顶层必需字段 → `top_fields`**

```python
{"desc": "顶层必需字段", "kind": "top_fields",
 "fields": ["id", "name", "task_status", "operating_status", "scheduler",
            "event_types", "camera", "location", "cluster", "snapshot",
            "object_size_filter", "confidence_threshold"]},
```

失败时会连带打印实际存在的键，用来判断 `path` 是否指错了对象：

```
❌ location检查·必需字段 ['timezone', 'organization_id'] 实际有: ['id', 'name', 'source_url', 'fps', ...]
```

上面这行里实际键是 `source_url` / `fps`，说明查的其实是 `camera`，`path` 该改成 `"location"`（键超过 12 个只显示前 12 个并标注总数）。

**2. 可选单个对象 → `sub_checks`**（一个对象要查很多字段时，打包成一组；对象为 `null` 整组跳过）

```python
{"desc": "camera", "kind": "sub_checks", "path": "camera", "sub": [
    {"desc": "必需字段", "kind": "top_fields",
     "fields": ["id", "name", "source_url", "fps", "resolution_height",
                "resolution_width", "model_name", "coordinates", "address"]},
    {"desc": "coordinates 字段", "kind": "top_fields", "path": "coordinates",
     "fields": ["latitude", "longitude"]},
    {"desc": "source_url 非空", "kind": "exists", "path": "source_url"},
]},
```

`sub` 里的 `path` **从对象内部写起**（`"coordinates"` 而不是 `"camera.coordinates"`）；子检查可以是任意 kind，也能再套 `for_each`。

只有一两个字段要查时，直接用 `top_fields` + `path` 更省事（效果一样，`null` 也放行）：

```python
{"desc": "camera.coordinates 的必需字段", "kind": "top_fields",
 "path": "camera.coordinates", "fields": ["latitude", "longitude"]},
```

`sub_checks` 的三种边界：对象为 `null` → 整组 ℹ️ 跳过；字段整体不存在 → 默认 ❌，加 `null_ok: True` 放行；对象不是 dict（是数组/字符串）→ ❌ 并提示改用 `for_each`。`path` 写 `"."` 或省略表示当前对象本身。

**3. 固定值断言 → `eq`（两种写法）**

```python
{"desc": "timezone 应为 Asia/Taipei", "kind": "eq",
 "path": "location.timezone", "value": "Asia/Taipei"},          # 嵌套写法
{"desc": "某顶层字段应为 X", "kind": "eq", "key": "task_status", "value": "active"},  # 顶层写法
```

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
{"desc": "event_types.zones 每个区域必需字段", "kind": "for_each", "path": "event_types", "sub": [
    {"desc": "zones 每项", "kind": "for_each", "path": "zones", "null_ok": True, "sub": [
        {"desc": "区域必需字段", "kind": "top_fields",
         "fields": ["id", "name", "polygon_type", "geometry"]},
        {"desc": "geometry.type 字段是否存在(允许null)", "kind": "exists", "path": "geometry.type"},
        {"desc": "geometry.coordinates 字段是否存在", "kind": "exists", "path": "geometry.coordinates"},
    ]},
]},
```

`null_ok: True` 在这里表示：某些 event_type **没有 `zones` 数组**也放行（可选数组）。

数组套数组还可以用 `"path": "."` 指回「当前元素本身」，省掉一层多余字段名：

```python
{"desc": "detected_objects 逐组", "kind": "for_each", "path": "detected_objects", "sub": [
    {"desc": "组内逐框", "kind": "for_each", "path": ".", "sub": [
        {"desc": "框必需字段", "kind": "top_fields", "fields": ["label", "confidence", "bbox"]},
    ]},
]},
```

**6. `list_field`**（当前规则未用到）

数组里每个元素都必须含某字段；数组为 `null` 或父级为 `null` 视为正常。具体键名以 `reqable_check_core.py` 的实现为准。

**7. 与请求参数比对 → `shared_eq` / `shared_in` / `shared_not_in`**（详见第五节）

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
```

### null / 缺失规则（最容易混）

| 场景 | 行为 |
| --- | --- |
| `top_fields` 查的子对象为 `null` / 父级为 `null` | 视为正常，不报错 |
| `sub_checks` 指向的对象为 `null` / 父级为 `null` | 整组 ℹ️ 跳过，不计失败 |
| `sub_checks` 指向的字段整体不存在 | 默认 ❌，`null_ok: True` 才放行 |
| `list_field` / `for_each` 的数组为 `null` / 父级为 `null` | 视为正常 |
| `exists` 字段值为 `null` 或 `""` | 默认**判失败**，`null_ok: True` 才放行 |
| `exists` 字段值为 `0` / `false` / `[]` | 正常，不算空值 |
| `for_each` 的数组字段**整体不存在** | 加 `null_ok: True` 才放行 |
| `optional: True` 的字段整体缺失 | 只提示，不算失败 |

一句话：`null_ok` 管「值是 null / 空串」，`optional` 管「字段压根没有」。

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

### 2) 清单侧：`shared_eq` / `shared_in` / `shared_not_in`

| 键 | 指向 |
| --- | --- |
| `path` / `key` | **响应**里的字段 |
| `shared_key` | **`context.shared`** 里的取值路径（点分），省略时退化为 `path` / `key` |
| `require_shared` | `True` 时 shared 缺该字段判 ❌，否则 ℹ️ 跳过 |

- `shared_eq`：响应值 **==** shared 值（请求体回显、单值参数）
- `shared_in`：响应值 **属于** shared 里的列表（列表接口逐条校验）；响应值是数组时，要求**每个元素都属于**，有一个不在就判 ❌（如 `detail.task_ids` vs 请求的 `ids`）
- `shared_not_in`：响应值 **不属于** shared 里的列表（**排除名单**，`shared_in` 的反面）；响应值是数组时，要求**每个元素都不命中**，命中一个就判 ❌ 并列出命中项；shared 是空列表 `[]` 时没有可排除的值，打 ℹ️ 视为通过并说明原因

```python
# 请求体回显（顶层字段已平铺，可省略 shared_key）
{"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq",
 "path": "event_type_id", "require_shared": True},

# 嵌套请求体字段走 _body
{"desc": "object_key 与请求一致", "kind": "shared_eq",
 "path": "object_key", "shared_key": "_body.data.object_key"},

# 列表接口：?ids=1&ids=2 返回 {"total":2,"results":[...]}，逐条判归属
{"desc": "每条 id 都属于请求的 ids", "kind": "shared_in",
 "path": "id", "shared_key": "_query.ids", "require_shared": True},

# 请求体是数组：[{"event_type_id":103},{"event_type_id":206}]，取字段自动投影成列表
{"desc": "每条 event_type_id 都属于请求", "kind": "for_each", "path": "successful", "sub": [
    {"desc": "event_type_id 属于请求", "kind": "shared_in", "path": "event_type_id",
     "shared_key": "_body.event_type_id", "require_shared": True}]},

# 响应字段本身是数组：detail.task_ids = [144310, 144311] 对 ?ids=144310，逐个判归属
{"desc": "每条 task_id 都属于请求", "kind": "shared_in",
 "path": "detail.task_ids", "shared_key": "_query.ids", "require_shared": True},

# 排除名单：请求 ?exclude_ids=9&exclude_ids=10，返回的 id 一个都不能落在名单里
{"desc": "id 不在排除名单", "kind": "shared_not_in",
 "path": "id", "shared_key": "_query.exclude_ids", "require_shared": True},

# 响应数组对排除名单：每个元素都不能命中（如返回的 task_ids 不含已删除的）
{"desc": "task_ids 不含已排除的 id", "kind": "shared_not_in",
 "path": "detail.task_ids", "shared_key": "_body.exclude_ids", "require_shared": True},
```

输出示例：

```
✅ 响应 event_type_id 与请求一致: 实际 116 / shared 116
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
```

> **类型要一致**：两者都是严格相等。`_query` 已把纯数字转成 `int`，响应是数字就能直接比；响应侧是字符串时改用 `_query_all`（保留字符串类型，不转 `int`，但同样做了 URL 解码）。
>
> **常见误配**：把 `shared_key` 写成 `"shared"`。它填的是 `shared` 这个 dict 里的键名（如 `event_type_id`、`_query.ids`），不是 `shared` 本身。
>
> **关键项加 `require_shared: True`**：否则 `onRequest` 没跑到（脚本报错、请求没经过 hook）时这条会**静默跳过**，看起来通过其实没校验。
>
> **数组不用手写 `onRequest`**：`path` / `shared_key` 遇到数组时，写数字是下标（`_body.0.task_id` → `144838`），写字段名则**投影成列表**（`_body.event_type_id` → `[103, 206]`）。投影要求每项都是对象且都有该字段，有元素缺字段就算取不到，不会返回残缺列表去比对。

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
- **键名要纯字母**：`v2` 这类带数字的段不当键名。
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

# 新增「响应与请求一致」
{"desc": "响应 device_id 与请求一致", "kind": "shared_eq", "path": "device_id", "require_shared": True},

# 新增「列表逐条归属请求参数」
{"desc": "每条 id 都属于请求的 ids", "kind": "shared_in", "path": "id", "shared_key": "_query.ids"},

# 新增「可选对象打包一组子检查」
{"desc": "cluster", "kind": "sub_checks", "path": "cluster", "sub": [
    {"desc": "必需字段", "kind": "top_fields", "fields": ["id", "name", "address"]},
]},
```

`desc` 建议写清「对象 + 字段」，报错时能一眼定位。

## 八、常见坑

1. **CORE 路径**：绝对路径 + `expanduser("~")`，别用裸相对路径。
2. **单个对象不能用 `for_each`**：`camera` / `location` / `cluster` / `scheduler` 都是对象，用 `sub_checks`（字段多、对象可空时）或 `top_fields` + `path`（字段少时）；`for_each` 的 `path` 必须指向数组，否则会报错。
3. **数组套数组要两层 `for_each`**：`event_types` → `zones`；可选数组记得加 `null_ok: True`。
4. **path 数组下标**：点分 + 数字下标，如 `vlms.0.x`。
5. **`null_ok` vs `optional`**：前者放行 null / 空串值，后者放行字段整体缺失。
6. **`EXPECTED_CODE` 默认 200**：其它状态码（201 / 204 / 4xx）要在规则脚本里显式覆盖。
7. **类型严格相等**：`eq` / `shared_eq` 都是 `==` 比较，`True` 与 `"True"`、`103` 与 `"103"`、`[]` 与 `"[]"` 都不相等。期望值写成 Python 字面量，别加引号。
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
- **可选字段用 `optional`**：随 `event_type` 变化的字段（`frequency`、`zones` 等）别写成必需。
- **Q：报「公共引擎不存在」？** 检查 `~/Documents/reqable/reqable_check_core.py` 是否在位、`~` 是否正确展开。
- **Q：字段明明有值却判失败？** 看是不是 `exists` 默认严格（null / 空串也失败）、`for_each` 指到了对象而非数组，或 `eq` 的期望值类型写错（字符串 vs 数字）。`top_fields` 报缺失时看行尾的「实际有」列表——键名对不上就是 `path` 指错了对象（复制别的检查忘改）。
- **Q：`shared_eq` 一直显示「跳过」？** 先看 `onRequest` 打印的 `shared = {...}` 里有没有那个键；注意 `shared_key` 填的是键名，不是 `shared`。
- **Q：`shared` 里没有 URL 里的那个 ID？** 引擎只收「末两段、且末段像 ID（纯数字 / UUID）」，键名是**倒数第二段原样**——`/v2/events/record/xxxxxx` 是 `record`，不是 `id`；`/record/{id}/objects` 这种 ID 在中间的要自己补（第五节 3）。
- **Q：URL 明明带了参数，`shared` 还是 `{}`？** 多半是 Reqable 里挂的引擎还是旧版（旧版 `onRequest` 只收请求体，GET 就是空）；换成当前 `reqable_check_core.py` 后 `?ids=1&ids=2` 会出现 `_query`。
- **Q：`sub_checks` 整组显示「跳过」？** 说明那个对象是 `null`，按设计视为正常。若它本该存在，另加一条 `{"desc": "camera 必须存在", "kind": "exists", "path": "camera"}` 断言非 null。
- **Q：`page` / `size` / `total` 写进 `checks` 一直取不到？** 它们不在单条记录上，属整体级，挪到 `META_CHECKS`（见第四节末）。`checks` 对每条 record 各跑一遍，信封字段本来就不在那儿。
- **Q：想临时跳过某条规则？** 直接从 `checks` 里删掉或注释那一项；整体级的同理，从 `META_CHECKS` 里去掉。
