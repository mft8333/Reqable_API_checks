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

规则脚本只剩「开头固定写法 + `EXPECTED_CODE` + `checks`」三块，**路径必须用绝对路径、`~` 要展开**（Reqable 的工作目录不固定）：

```python
from reqable import *
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径，别用裸相对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())

EXPECTED_CODE = 201

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
| `key` | 仅 `eq` / `exists` 的顶层字段写法 |
| `fields` | 批量字段名列表，用于 `top_fields` / 批量 `exists` |
| `value` | `eq` 的期望值 |
| `sub` | `for_each` 的子检查列表，可继续嵌套 |
| `shared_key` | 仅 `shared_eq` / `shared_in`：`context.shared` 里的取值路径（点分，如 `_query.ids`）；省略时退化为 `path` / `key` |
| `require_shared` | 仅 `shared_eq` / `shared_in`：`True` 时 `shared` 里没有该字段判 ❌，否则只 ℹ️ 跳过 |
| `null_ok` | `True` 时放行 `null` / 空串 `""`（含父级为 `null`）；在 `for_each` 上还表示「数组字段整体不存在」也放行 |
| `optional` | `True` 时字段整体缺失只提示、不算失败（随类型变化的可选字段） |

### `kind` 一览

| kind | 用途 | 对象要求 |
| --- | --- | --- |
| `top_fields` | 必须存在的字段列表；加 `path` 可查嵌套子对象 | 单个对象 |
| `eq` | 字段值 == 期望值 | 任意可寻址字段 |
| `exists` | 字段是否存在（默认严格，`null` 或 `""` 也判失败） | 单个或批量顶层字段 |
| `list_field` | 数组里每个元素都必须含某字段 | `path` 指向数组 |
| `shared_eq` | 响应字段 == `onRequest` 写入 `context.shared` 的值 | 任意可寻址字段 |
| `shared_in` | 响应字段属于 `context.shared` 里的列表（列表接口逐条校验） | 任意可寻址字段 |
| `for_each` | 对数组每个元素递归执行 `sub` 里的子检查 | `path` 必须指向数组 |

### 写法示例

**1. 顶层必需字段 → `top_fields`**

```python
{"desc": "顶层必需字段", "kind": "top_fields",
 "fields": ["id", "name", "task_status", "operating_status", "scheduler",
            "event_types", "camera", "location", "cluster", "snapshot",
            "object_size_filter", "confidence_threshold"]},
```

**2. 嵌套单个对象 → `top_fields` + `path`**（子对象为 `null` 视为正常）

```python
{"desc": "camera 必需字段", "kind": "top_fields", "path": "camera",
 "fields": ["id", "name", "source_url", "fps", "resolution_height",
            "resolution_width", "model_name", "coordinates", "address"]},
{"desc": "camera.coordinates 的必需字段", "kind": "top_fields",
 "path": "camera.coordinates", "fields": ["latitude", "longitude"]},
```

**3. 固定值断言 → `eq`（两种写法）**

```python
{"desc": "timezone 应为 Asia/Taipei", "kind": "eq",
 "path": "location.timezone", "value": "Asia/Taipei"},          # 嵌套写法
{"desc": "某顶层字段应为 X", "kind": "eq", "key": "task_status", "value": "active"},  # 顶层写法
```

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

**7. 与请求参数比对 → `shared_eq` / `shared_in`**（详见第五节）

```python
# 响应回显请求体里的字段（请求体顶层字段已平铺到 shared 根上）
{"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq",
 "path": "event_type_id", "require_shared": True},

# 列表接口：返回的每条记录 id 都属于请求 ?ids=1&ids=2
{"desc": "每条 id 都属于请求的 ids", "kind": "shared_in",
 "path": "id", "shared_key": "_query.ids", "require_shared": True},
```

### null / 缺失规则（最容易混）

| 场景 | 行为 |
| --- | --- |
| `top_fields` 查的子对象为 `null` / 父级为 `null` | 视为正常，不报错 |
| `list_field` / `for_each` 的数组为 `null` / 父级为 `null` | 视为正常 |
| `exists` 字段值为 `null` 或 `""` | 默认**判失败**，`null_ok: True` 才放行 |
| `exists` 字段值为 `0` / `false` / `[]` | 正常，不算空值 |
| `for_each` 的数组字段**整体不存在** | 加 `null_ok: True` 才放行 |
| `optional: True` 的字段整体缺失 | 只提示，不算失败 |

一句话：`null_ok` 管「值是 null / 空串」，`optional` 管「字段压根没有」。

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
| `_query` | 查询参数：单值→标量、重复 key→列表、纯数字转 `int` | `?ids=1&ids=2` → `{"ids": [1, 2]}` |
| `_query_all` | 查询参数：一律列表、一律原始字符串 | `{"ids": ["1", "2"]}` |

取值规则：

- 重复 key 合并成列表：`?location_ids=3&location_ids=2` → `[3, 2]`
- 逗号分隔且每段都是数字也转列表：`?ids=1,2` → `[1, 2]`
- 前导 0 的数字串保持字符串：`?code=007` → `"007"`
- GET 没有 body、URL 也没有 query 时，`shared` 是 `{}`

`onRequest` 会把它打印出来，照着写 `shared_key` 最省事：

```
request url https://.../observ/apiserver/v2/tasks?location_ids=3&location_ids=2
shared = {"_query": {"location_ids": [3, 2]}, "_query_all": {"location_ids": ["3", "2"]}}
```

### 2) 清单侧：`shared_eq` / `shared_in`

| 键 | 指向 |
| --- | --- |
| `path` / `key` | **响应**里的字段 |
| `shared_key` | **`context.shared`** 里的取值路径（点分），省略时退化为 `path` / `key` |
| `require_shared` | `True` 时 shared 缺该字段判 ❌，否则 ℹ️ 跳过 |

- `shared_eq`：响应值 **==** shared 值（请求体回显、单值参数）
- `shared_in`：响应值 **属于** shared 里的列表（列表接口逐条校验）

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
```

输出示例：

```
✅ 响应 event_type_id 与请求一致: 实际 116 / shared 116
❌ 每条 id 都属于请求的 ids: 实际 141076，不在 [129728] 中
ℹ️ 响应 id 与 URL 中的 ID 一致: context.shared 不可用或没有 _path_ids.0，跳过
```

> **类型要一致**：两者都是严格相等。`_query` 已把纯数字转成 `int`，响应是数字就能直接比；响应侧是字符串时改用 `_query_all`（保留原始字符串）。
>
> **常见误配**：把 `shared_key` 写成 `"shared"`。它填的是 `shared` 这个 dict 里的键名（如 `event_type_id`、`_query.ids`），不是 `shared` 本身。
>
> **关键项加 `require_shared: True`**：否则 `onRequest` 没跑到（脚本报错、请求没经过 hook）时这条会**静默跳过**，看起来通过其实没校验。

### 3) 需要 URL 路径里的 ID 时

`/v2/tasks/144310` 这类 ID 只在路径里的接口，引擎**不收集路径段**。确实要用就在规则脚本里补，注意先把引擎的 `onRequest` 存一份再覆盖：

```python
_engine_onRequest = onRequest          # 覆盖前先存住引擎的实现

def onRequest(context, request):
    request = _engine_onRequest(context, request)   # 请求体 / 查询参数照旧
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
- 这是通用写法（取路径里所有纯数字段），**不要写死 `/v2/tasks`、`task_id`** 这类专用路径与键名，换接口就不用改。

---

## 六、当前规则覆盖的字段树

```
每条结果（顶层必需字段 12 项）
├─ camera（单对象）         → id name source_url fps resolution_height
│                             resolution_width model_name coordinates address
│  └─ coordinates           → latitude longitude
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
  camera.source_url                 → 非 null 断言
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
```

`desc` 建议写清「对象 + 字段」，报错时能一眼定位。

## 八、常见坑

1. **CORE 路径**：绝对路径 + `expanduser("~")`，别用裸相对路径。
2. **单个对象别用 `for_each`**：`camera` / `location` / `cluster` / `scheduler` 都是对象，用 `top_fields` + `path`；`for_each` 的 `path` 必须指向数组，否则会报错。
3. **数组套数组要两层 `for_each`**：`event_types` → `zones`；可选数组记得加 `null_ok: True`。
4. **path 数组下标**：点分 + 数字下标，如 `vlms.0.x`。
5. **`null_ok` vs `optional`**：前者放行 null / 空串值，后者放行字段整体缺失。
6. **`EXPECTED_CODE` 默认 200**：其它状态码（201 / 204 / 4xx）要在规则脚本里显式覆盖。
7. **类型严格相等**：`eq` / `shared_eq` 都是 `==` 比较，`True` 与 `"True"`、`103` 与 `"103"`、`[]` 与 `"[]"` 都不相等。期望值写成 Python 字面量，别加引号。
8. **规则脚本里写 `onRequest` 会覆盖引擎的**：引擎注入的 `onRequest` 不再生效，请求体 / 查询参数的收集要自己补。推荐先 `_engine_onRequest = onRequest` 存一份再调用（见第五节 3)。
9. **204 没有响应体**：`EXPECTED_CODE = 204` 会因 `JSON 解析失败` 提前返回，成功场景别和 200 的清单共用一份。

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
- **Q：字段明明有值却判失败？** 看是不是 `exists` 默认严格（null / 空串也失败）、`for_each` 指到了对象而非数组，或 `eq` 的期望值类型写错（字符串 vs 数字）。
- **Q：`shared_eq` 一直显示「跳过」？** 先看 `onRequest` 打印的 `shared = {...}` 里有没有那个键；注意 `shared_key` 填的是键名，不是 `shared`。
- **Q：URL 明明带了参数，`shared` 还是 `{}`？** 多半是 Reqable 里挂的引擎还是旧版（旧版 `onRequest` 只收请求体，GET 就是空）；换成当前 `reqable_check_core.py` 后 `?ids=1&ids=2` 会出现 `_query`。
- **Q：想临时跳过某条规则？** 直接从 `checks` 里删掉或注释那一项。
