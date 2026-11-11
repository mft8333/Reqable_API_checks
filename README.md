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
| 规则脚本（本 addon） | Reqable Addons 脚本目录 | 声明 `EXPECTED_CODE`、`checks`，加载公共引擎 |
| `reqable_check_core.py` | `~/Documents/reqable/reqable_check_core.py` | 公共引擎：注册回调、遍历结果、输出结论 |

规则脚本开头是固定写法，**路径必须用绝对路径、`~` 要展开**（Reqable 的工作目录不固定）：

```python
from reqable import *
import json
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径，别用裸相对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())
```

`exec(..., globals())` 把引擎的函数与变量注入当前命名空间，之后定义 `checks` 即可。

**期望响应码**：`EXPECTED_CODE` 默认 `200`（引擎里定义），规则脚本里写 `EXPECTED_CODE = 201` 即可覆盖。响应码不匹配时引擎直接打印 `⚠️ 响应码不是200: xxx` 并跳过检查，不会解析响应体。

> ⚠️ **两个回调在不同进程**：`onRequest` 与 `onResponse` 不共享模块级变量，跨阶段取值只能走 `context.shared`（见第五节）。另外规则脚本里若定义同名 `onRequest`，**会覆盖**引擎注入的那个（后定义生效）。

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
| `shared_key` | 仅 `shared_eq` / `shared_in`：`context.shared` 里的取值路径；省略时退化为 `path` / `key` |
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
| `shared_in` | 响应字段**属于** `context.shared` 里的列表（列表接口逐条判 ID） | 任意可寻址字段 |
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

**7. 与请求参数比对 → `shared_eq`**（详见第五节）

```python
{"desc": "响应 id 与 URL 中的 task_id 一致", "kind": "shared_eq",
 "path": "id", "shared_key": "task_id", "require_shared": True},
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

## 五、跨请求校验：`context.shared` 与 `shared_eq`

### 为什么需要

Reqable 的 `onRequest` 与 `onResponse` **在两个进程里执行**，模块级变量不互通。要在响应侧拿到请求里的值（URL 路径参数、请求体字段、环境变量），必须由 `onRequest` 写进 `context.shared`，`onResponse` 再读出来。

### 1) 引擎默认行为：把整个请求体放进 shared

```python
    try:
        context.shared = json.loads(request.body.payload)   # 整个请求体带过去
    except Exception:
        context.shared = {}

    _print_shared(context)      # 控制台打印 shared = {...}
```

`_print_shared` 的输出形如：

```
request url https://.../v2/vlms/template/21029
shared = {"name": "new_template_name1", "temperature": 0.9, "aliases": {...}}
```

照着它写 `shared_key` 最省事。GET 请求没有 body（或 body 不是 JSON）时，`shared` 是 `{}`。

### 2) 合并版 `onRequest`：一份挂到所有接口

不写死接口名、也不猜参数名：路径段、查询参数、请求体各收一份进 `shared`，检查时按需取。规则脚本里的同名 `onRequest` 会覆盖引擎那个，所以「打印 URL + 请求体进 shared + 打印 shared」也一并写在里面，不必再调引擎那版。

```python
import re        # 只有第 4) 段用；漏了会 NameError: name 're' is not defined


def _val(v):
    """纯数字转 int（便于与响应里的数字比）；逗号分隔且每段都是数字转列表；其余保持字符串。"""
    parts = v.split(",")
    if len(parts) > 1 and all(p.isdigit() for p in parts):
        return [int(p) for p in parts]
    return int(v) if v.isdigit() and (v == "0" or not v.startswith("0")) else v


def onRequest(context, request):
    print("request url " + context.url)
    sh = {}

    # 1) 请求体：顶层字段平铺 + 原始结构 _body
    try:
        body = json.loads(request.body.payload)
        if isinstance(body, dict):
            sh.update(body)
            sh["_body"] = body
        elif body is not None:
            sh["_body"] = body
    except Exception:
        pass                                     # GET / 非 JSON body

    path = str(getattr(request, "path", "") or context.url)   # 可能不含 query
    full = str(context.url)                                   # 完整 URL，含 query

    # 2) 路径段
    segs = [s for s in path.split("?")[0].split("/") if s]
    if segs:
        sh["_path"] = segs
        nums = [int(s) for s in segs if s.isdigit()]
        if nums:
            sh["_path_ids"] = nums
            sh["_path_id"] = nums[0]
            sh["_path_count"] = len(nums)

    # 3) 查询参数
    if "?" in full:
        q, qall = {}, {}
        for pair in full.split("?", 1)[1].split("&"):
            if not pair:
                continue
            k, v = pair.split("=", 1) if "=" in pair else (pair, "")
            qall.setdefault(k, []).append(v)
        for k, vs in qall.items():
            vals = [_val(x) for x in vs]
            q[k] = vals if len(vals) > 1 else vals[0]
        sh["_query"] = q
        sh["_query_all"] = qall
        sh["_query_counts"] = {k: len(vs) for k, vs in qall.items()}
        sh["_query_count"] = sum(len(vs) for vs in qall.values())

    # 4) 兼容早期的正则写法：/v2/tasks/144310 → task_id（与 _path_ids.0 等价）
    m = re.search(r"/v2/tasks/(\d+)", path or full)
    if m:
        sh["task_id"] = int(m.group(1))

    context.shared = sh
    _print_shared(context)
    return request
```

### 3) `shared` 里的通用键

| 键 | 内容 | 典型用途 |
| --- | --- | --- |
| `_path` | 路径分段原样，如 `["v2","tasks","144310"]` | 需要自己切路径时 |
| `_path_ids` | 路径里**全部**纯数字段，如 `[144310, 15608]` | `shared_key: "_path_ids.0"` 取资源 ID |
| `_path_id` | 第一个数字段（= `_path_ids.0`） | 同上，写法短一点 |
| `_path_count` | 数字段个数 | 判断路径里带了几个 ID |
| `_query` | 查询参数；单值→标量、重复 key→列表，**纯数字已转 int** | `shared_key: "_query.ids"` |
| `_query_all` | 同上但一律列表、一律**原始字符串** | 要原始形态/保留前导零时 |
| `_query_counts` | `{参数名: 值的个数}` | `shared_key: "_query_counts.ids"` 拿「请求了几条」 |
| `_query_count` | 所有参数值的**总个数** | 只带一类 ID 参数时可直接用 |
| （body 顶层字段） | 平铺在根上 | `shared_key: "object_key"` 老写法继续可用 |
| `_body` | 请求体原始结构 | `shared_key: "_body.data.object_key"` 取嵌套 |

另外，路径匹配 `/v2/tasks/{id}` 时会额外写一个兼容键 **`task_id`**（与 `_path_ids.0` 同值），老检查项 `"shared_key": "task_id"` 不用改；新写建议用 `_path_ids.0`，因为它在 `/v2/vlms/template/21029`、`/v2/event_records/2289267` 这类接口上同样有效。

> `_query_all.ids` 是 `["129728","141076"]`（字符串），响应里的 `id` 是 `129728`（数字）。严格相等下必然不等 —— **要比就比 `_query.ids`**，它已经转成 int。

### 4) 清单侧：`shared_eq`（值相等）

```python
{"desc": "响应 id 与 URL 中的 ID 一致", "kind": "shared_eq",
 "path": "id", "shared_key": "_path_ids.0", "require_shared": True},

{"desc": "响应 name 与请求一致", "kind": "shared_eq", "path": "name"},      # 同名可省 shared_key
```

| 键 | 指向 |
| --- | --- |
| `path` / `key` | **响应**里的字段 |
| `shared_key` | **`context.shared`** 里的字段（省略时退化为 `path` / `key`） |
| `require_shared` | `True` 时 shared 缺该字段判 ❌，否则 ℹ️ 跳过 |

输出示例：

```
✅ 响应 id 与 URL 中的 ID 一致: 实际 144310 / shared 144310
❌ 响应 name 与请求一致: 实际 'old_name' / shared 'new_template_name1'
ℹ️ 响应 id 与 URL 中的 ID 一致: context.shared 不可用或没有 _path_ids.0，跳过
```

### 5) 清单侧：`shared_in`（值属于列表）

列表接口 `?ids=129728&ids=141076` 返回多条，每条记录的 `id` 只是请求列表中的一个，用 `shared_eq` 永远不等。改用 `shared_in`：

```python
{"desc": "返回的每条 id 都属于请求的 ids", "kind": "shared_in",
 "path": "id", "shared_key": "_query.ids"},
```

```
✅ 返回的每条 id 都属于请求的 ids: 实际 129728
❌ 返回的每条 id 都属于请求的 ids: 实际 999999，不在 [129728, 141076] 中
```

> ⚠️ `{"total": 2, "results": [...]}` 这种响应，`checks` 是**逐条**在每条记录上跑的，`"path": "total"` 取不到值。所以「返回条数 == 请求条数」目前做不到（需要整体级检查，引擎没有这一层）。

> 常见误配：把 `path` 写成 `"shared"`、或把 `shared_key` 写成 `"shared"`。`shared_key` 要填的是 **`shared` 这个 dict 里的键名**（如 `task_id`），不是 `shared` 自己。日志里出现「没有 shared」通常就是这个原因。
>
> 建议给关键项加 `require_shared: True`：否则 `onRequest` 没跑到（脚本报错、请求未经过 hook）时这条会**静默跳过**，看起来通过其实没校验。

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
{"desc": "响应 device_id 与请求一致", "kind": "shared_eq", "path": "device_id"},
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
8. **规则脚本里写 `onRequest` 会覆盖引擎的**：引擎注入的 `onRequest` 不再生效，请求体进 `shared` 这一步要自己补。
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
- **Q：想临时跳过某条规则？** 直接从 `checks` 里删掉或注释那一项。
