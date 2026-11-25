# API Docs: https://reqable.com/docs/capture/addons
# ---------------- kind 速查（完整写法见 README） ----------------
#   top_fields      字段列表；加 path 查子对象；optional 放行「对象不存在」，null_ok 放行 {} / []
#   eq              值 == 期望值（严格相等，类型不猜）
#   in_list         值 ∈ 自定义常量集合；not_in_list 是其反面（黑名单）；两者都支持 loose
#   gt/gte/lt/lte   大小比较：同为数字或同为 ISO 时间串，否则 ❌
#   exists          字段存在；默认 null 和 "" 都算错，null_ok 放行；批量查用 fields
#   list_field      数组每项都要有该字段（键名是 field）；optional 放行「数组不存在」
#   for_each        遍历数组，sub 为子检查；optional 放行可选数组，label 便于定位
#   sub_checks      对单个对象打包多条子检查；optional 放行可选对象，null 时整组 ℹ️ 跳过
#   shared_eq       响应值 == context.shared；shared_in 为 ∈、shared_not_in 为 ∉
#   shared_contains 响应数组 ⊇ shared 列表（创建接口服务端会补默认项）
#   shared_* 取不到键默认 ℹ️ 跳过，加 "require_shared": True 改为 ❌
#   loose          数字 ↔ 数字字符串互等，仅显式加才生效：shared_eq / shared_in / shared_not_in /
#                  shared_contains / in_list / not_in_list；数组逐项放宽（[103] 等于 ['103']）
#   when           任意 kind 都能加：条件不成立就整条跳过（ℹ️，不计失败），一份清单覆盖多种参数
#                  {"shared_key": "_query_all.event_type_ids.0", "numeric": True}  请求值能当数字用
#                  {"shared_key": "...", "eq": "other"} / {"path": "status", "eq": "failed"}
#                  取不到条件打 ⚠️ 跳过，不会误判成 ❌
#   通用：path 点分、数字是下标；写字段名则投影成列表；字段名后 ? 松散投影（跳过缺字段的元素）
#         段名 * 摊平一层；[字段=值] 按值配对（| 任一命中）；shared_key 可写 ${字段} / ${..字段}
#         可选但给了就不能空：加 optional（缺失 ℹ️，null 仍 ❌）；连 null 也放过再加 null_ok
#         容器类（对象 / 数组）：top_fields / for_each / list_field / sub_checks 都用 optional
#         放行「整体不存在」；旧写法 null_ok 也认
#         写了该 kind 不支持的键会打 ⚠️，且不生效
# --------------------------------------------------------------

from reqable import *
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())

# 期望响应码（本清单按任务详情接口写，换接口改这里）
EXPECTED_CODE = 201

# 整体级检查：只跑一次、对象是整个响应 data；单对象响应留空即可
META_CHECKS = []

# 分页接口按需启用（page / size / total 这类信封字段只能放这里）
# META_CHECKS = [
# {"desc": "分页字段齐全", "kind": "top_fields", "fields": ["page", "size", "total_pages", "total"]},
# {"desc": "page 从 1 开始", "kind": "eq", "path": "page", "value": 1},
# {"desc": "size 为 5", "kind": "eq", "path": "size", "value": 5},
# ]


# ========================= 检查项 =========================
# 每种 kind 各留一条示例
checks = [
# 记录自身必需字段（不是响应最外层）
{"desc": "记录自身必需字段", "kind": "top_fields", "fields":
["id", "name", "task_status", "operating_status", "scheduler", "event_types", "camera",
"location", "cluster", "snapshot", "object_size_filter", "confidence_threshold"]
},

# 可选子对象：optional 放行「整体不存在」，null_ok 放行 {}
{"desc": "model_settings 的必需字段", "kind": "top_fields", "path": "model_settings",
"optional": True, "null_ok": True, "fields":
["id", "name", "version"]
},

# 可选对象打包多条子检查（camera 为 null 时整组 ℹ️ 跳过）
{"desc": "camera", "kind": "sub_checks", "path": "camera", "sub":
[{"desc": "必需字段", "kind": "top_fields", "fields":
["id", "name", "source_url", "fps", "resolution_height", "resolution_width", "model_name",
"coordinates", "address"]
},
# coordinates 对象（可选：这条记录没有就不查）
{"desc": "coordinates 对象", "kind": "top_fields", "path": "coordinates", "optional": True, "fields":
["latitude", "longitude"]
},
{"desc": "source_url 非空", "kind": "exists", "path": "source_url"}
]
},

# 固定值（字符串带引号，数字不加）
{"desc": "timezone 应为 Asia/Taipei", "kind": "eq", "path": "location.timezone", "value": "Asia/Taipei"},

# 枚举取值：只按接口文档写，别拿实际返回过的值补（Operating ≠ operating）
{"desc": "task_status 取值", "kind": "in_list", "path": "task_status",
"value": ["operating", "non-operating"]
},

# 黑名单：命中任一禁值就失败
{"desc": "task_status 不能是删除态", "kind": "not_in_list", "path": "task_status",
"value": ["deleted", "archived"]
},

# 字段存在（默认 null 和 "" 都算错）
{"desc": "confidence_threshold 必须非 null", "kind": "exists", "path": "confidence_threshold"},

# 数组每项都要有该字段（轻量版，不逐项展开）
{"desc": "event_types 每项都要有 id", "kind": "list_field", "path": "event_types", "field": "id"},

# --- event_types 是【属性数组】：用 for_each 遍历列表项 ---
{"desc": "event_types 列表", "kind": "for_each", "path": "event_types", "label": "id", "sub":
[{"desc": "必需字段", "kind": "top_fields", "fields":
["id", "name", "is_detecting", "scheduled_times"]
},
{"desc": "可选字段", "kind": "exists", "null_ok": True, "optional": True, "fields":
["frequency", "detecting_duration", "detecting_threshold", "interval", "zones"]
},
{"desc": "侦测持续时间 > 0", "kind": "gt", "path": "detecting_duration", "value": 0, "optional": True},
{"desc": "信心阈值 >= 0", "kind": "gte", "path": "detecting_threshold", "value": 0, "optional": True},
{"desc": "信心阈值 <= 1", "kind": "lte", "path": "detecting_threshold", "value": 1, "optional": True},
{"desc": "zones 列表", "kind": "for_each", "path": "zones", "null_ok": True, "sub":
[{"desc": "必需字段", "kind": "top_fields", "fields":
["id", "name", "polygon_type", "geometry"]
},
{"desc": "geometry 对象", "kind": "top_fields", "path": "geometry", "fields":
["type", "coordinates"]
}]
}]
},

# 与 shared 比对：ID 在 URL 末段时引擎已自动收（/v2/tasks/{id} → shared["tasks"]）
{"desc": "响应 id 与 URL 中的 ID 一致", "kind": "shared_eq", "path": "id", "shared_key": "tasks"},

# 大小比较（拿不准字段值就别写死上限）
{"desc": "id 是正数", "kind": "gt", "path": "id", "value": 0},

# 时间比较：两边都是 ISO 时间串就自动按时间比
# {"desc": "事件时间不早于请求时间", "kind": "gte", "path": "event_time",
# "shared_key": "_body.event_time"},

# 排除名单：请求侧要有 ?exclude_ids=9&exclude_ids=10 才生效，没有则 ℹ️ 跳过
# {"desc": "id 不在排除名单", "kind": "shared_not_in", "path": "id",
# "shared_key": "_query.exclude_ids", "require_shared": True},

# 创建接口：响应是请求的超集（服务端会补默认项）
# {"desc": "event_type_ids 响应包含请求", "kind": "shared_contains", "path": "event_types.id",
# "shared_key": "event_type_ids", "require_shared": True},

# 过滤接口：?event_type_ids=103 与 ?event_type_ids=other 用同一份清单，靠 when 分流
# 数字过滤：响应每条只需【包含】该值（可有别的 event_type）；_query_all 是 ['103']，要 loose
# {"desc": "event_type_ids 响应与请求检查", "kind": "shared_contains",
# "path": "event_types.event_type_id", "shared_key": "_query_all.event_type_ids", "loose": True,
# "when": {"shared_key": "_query_all.event_type_ids.0", "numeric": True}},
# 关键字过滤 other：这类图片不带 event_type，响应 event_types 应为空
# {"desc": "other 过滤时 event_types 应为空", "kind": "eq", "path": "event_types", "value": [],
# "when": {"shared_key": "_query_all.event_type_ids.0", "eq": "other"}},
]
# ============================================================


# ==================== 其它接口写法（注释示例） ====================
# 列表接口（?ids=1&ids=2 → {"total":N,"results":[...]}）：逐条 id 都要属于请求
# checks = [c for c in checks if c.get("kind") != "shared_eq"] + [
# {"desc": "每条 id 都属于请求的 ids", "kind": "shared_in", "path": "id", "shared_key": "_query.ids"},
# ]
# results 型响应的 page / size / total 取不到，改用 META_CHECKS。
#
# 请求体回显（顶层已平铺）/ 嵌套请求体（走 _body）
# {"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq", "path": "event_type_id"}
# {"desc": "object_key 与请求一致", "kind": "shared_eq", "path": "object_key",
# "shared_key": "_body.data.object_key"}
#
# 类型不一致（422 的 input 是 '3000'，_query.size 已是 int）：加 loose，或直接取原始字符串
# {"desc": "input 与请求参数一致", "kind": "shared_eq", "path": "detail.0.input",
# "shared_key": "_query.size", "loose": True, "require_shared": True}
# 数组同理：投影成 [103] 对 ["103"] → 加 loose 逐项放宽（shared_eq / shared_in / shared_contains 都认）
# {"desc": "input 与请求参数一致", "kind": "shared_eq", "path": "detail.0.input",
# "shared_key": "_query_all.size.0", "require_shared": True}
#
# 三层对账：外层 event id 配对 → zone id 是否一致 → 每个 zone 的坐标是否一致
# {"desc": "请求的 event 都出现在响应中", "kind": "shared_contains", "path": "event_types.id",
# "shared_key": "_body.events.id?", "require_shared": True}
# {"desc": "event 与请求对账", "kind": "for_each", "path": "event_types", "label": "id", "sub":
# [{"desc": "zone id 包含请求的", "kind": "shared_contains", "path": "zones?.id",
# "shared_key": "_body.events[id=${id}|vlm_flow_id=${id}].zones.id?"},
# {"desc": "zone 坐标", "kind": "for_each", "path": "zones?", "null_ok": True, "label": "id", "sub":
# [{"desc": "coordinates 一致", "kind": "shared_eq", "path": "geometry.coordinates",
# "shared_key": "_body.events[id=${..id}|vlm_flow_id=${..id}].zones[id=${id}].coordinates"}]}]}
# ============================================================
