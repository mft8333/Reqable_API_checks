# API Docs: https://reqable.com/docs/capture/addons
# ========================= kind 说明 =========================
# kind 说明:
#   top_fields : 必须存在的字段列表；默认查当前对象，加 "path" 可查某个嵌套子对象
#                (子对象为 null 或父级为 null 视为正常，与 list_field/for_each 一致)
#   eq         : 字段值 == 期望值
#                {"desc","kind","key","value"}         顶层字段
#                {"desc","kind","path","value"}        嵌套字段(path 点分，数组用下标如 vlms.0.x)
#   gt/gte/lt/lte : 大小比较（> / >= / < / <=），写法和 eq 一样
#                两边同为数字 → 比数字：{"desc","kind":"gte","path","value":0.4}  实际 0.48 >= 0.4 → 成立
#                两边同为 ISO 时间串 → 比时间（输出末尾带「（按时间）」）：
#                {"desc":"事件时间不早于请求","kind":"gte","path":"event_time","shared_key":"_body.event_time"}
#                认 2026-05-15 / 2026-05-15T08:00:36.782976Z / 空格分隔 / +08:00、+0800；无时区按 UTC
#                比较基准写 value（常量）或 shared_key（请求值，此时不写 value）
#                剩下的一律判 ❌：不做隐式转换（"5" 和 5 不同类）、bool 不是数字、普通文本不按字典序比
#                区间用两条：gte + lte；字段缺失/值为 null 时加 "null_ok": True 放行
#   exists     : 字段是否存在；默认 null 和 ""(空串) 都算错，加 "null_ok": True 放行 null/""(含父级为 null)
#                ★支持批量: {"desc","kind","fields":[...],"null_ok":True,"optional":True}
#                fields 一次查多个顶层字段；null_ok 放行 null；optional 允许字段整体缺失(只提示不失败)
#   list_field : 数组里每个元素都必须含某字段；数组为 null 或父级为 null 视为正常
#   shared_eq  : 与 onRequest 写入的 context.shared 比对（如 object_key 是否被改写成 env 值）
#                {"desc","kind","path","shared_key"}  响应取值用 path/key，shared 取值用 shared_key
#                shared_key 省略时依次退化为 path / key；context.shared 不可用(测试脚本为 null)时
#                打印 ℹ️ 跳过、不计失败；加 "require_shared": True 则改为判 ❌
#   shared_in  : 响应值【属于】shared 里的列表(列表接口用：返回的每条 id 是否都在请求的 ids 里)
#                {"desc","kind","path","shared_key"}  取键规则与 shared_eq 完全相同
#                shared 取到的若不是列表，会自动当成单元素列表比；严格相等，注意类型
#                path 取到的是数组时，要求【每个元素都属于】请求(如 detail.task_ids vs _body.task_id)
#   shared_not_in : 响应值【不属于】shared 里的列表 —— shared_in 的反面（排除名单 / 黑名单）
#                {"desc","kind","path","shared_key"}  取键规则与 shared_in 完全相同
#                {"desc":"id 不在排除名单","kind":"shared_not_in","path":"id",
#                 "shared_key":"_query.exclude_ids","require_shared":True}
#                path 取到的是数组时，要求【每个元素都不命中】，失败会列出命中项
#                shared 是空列表 [] 时打 ℹ️「没有可排除的值」视为通过，不会静默全通过
#   shared_contains : 响应数组【包含】shared 里的每个值（响应 ⊇ 请求，允许服务端追加默认项）
#                {"desc","kind","path","shared_key"}  取键规则与 shared_in 完全相同
#                创建类接口必须用这条：服务端会补默认 event_types，此时 shared_in 必然失败
#                {"desc":"event_type_ids 响应包含请求","kind":"shared_contains",
#                 "path":"event_types.id","shared_key":"event_type_ids","require_shared":True}
#                path 必须指向数组或投影成数组；单个值请用 shared_eq
#   sub_checks : 对【单个对象】执行 "sub" 里的多条子检查(可套 top_fields/eq/exists/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  对象为 null / 父级为 null 视为正常
#                适用「可选对象但字段多」：一条检查打包整组，对象是 null 时整组 ℹ️ 跳过
#                "path": "." 表示当前对象本身；对象字段整体不存在时加 null_ok: True 放行
#   for_each   : 对【数组】每个元素递归执行 "sub" 里的子检查(可再套 top_fields/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  数组为 null 或父级为 null 视为正常
#                注意: path 必须指向数组；单个对象请用 sub_checks（或 top_fields + path）
#                数组套数组时，内层写 "path": "." 表示【当前这个元素本身】(如 detected_objects)
#                加 "null_ok": True 时，该数组字段【整体不存在】也放行(用于可选数组，如某些项没有 zones)
#   整体级     : META_CHECKS 列表，只跑一次、对象是整个响应 data（分页的 page / size / total 等信封字段）
#                kind 语法与 checks 完全相同；不写 / 写 [] / 写 None 都不会报错
#    通用	   : path / shared_key 遇到数组时，写数字是下标(vlms.0.x)，写字段名则投影成列表
#                (如 _body.event_type_id → [103, 206]，要求每项都有该字段)
#                写了不属于该 kind 的键(如 exists 里塞 sub)会打 ⚠️，这些键不生效
# ==============================================================

from reqable import *
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())

# 期望响应码；本清单按任务详情接口（201）写的，换接口改这里
EXPECTED_CODE = 201

# 整体级检查：只跑一次、对象是整个响应 data（分页的 page / size / total / total_pages）
# 本接口是单对象响应，没有整体级断言；不写 / 写 [] 都行，引擎不会报错
META_CHECKS = []

# 分页接口按需启用（示例）：
# META_CHECKS = [
#     {"desc": "分页字段齐全", "kind": "top_fields", "fields": ["page", "size", "total_pages", "total"]},
#     {"desc": "page 从 1 开始", "kind": "eq", "path": "page", "value": 1},
#     {"desc": "size 为 5", "kind": "eq", "path": "size", "value": 5},
# ]


# ========================= 检查项 =========================
# 每种 kind 保留一条示例
checks = [
    # 1) top_fields：顶层必需字段
    {"desc": "顶层必需字段", "kind": "top_fields",
     "fields": ["id", "name", "task_status", "operating_status", "scheduler",
                "event_types", "camera", "location", "cluster", "snapshot",
                "object_size_filter", "confidence_threshold"]},

    # 2) sub_checks：可选对象打包多条子检查（camera 为 null 时整组 ℹ️ 跳过）
    {"desc": "camera", "kind": "sub_checks", "path": "camera", "sub": [
        {"desc": "必需字段", "kind": "top_fields",
         "fields": ["id", "name", "source_url", "fps", "resolution_height",
                    "resolution_width", "model_name", "coordinates", "address"]},
        {"desc": "coordinates 字段", "kind": "top_fields", "path": "coordinates",
         "fields": ["latitude", "longitude"]},
        {"desc": "source_url 非空", "kind": "exists", "path": "source_url"},
    ]},

    # 3) eq：固定值（字符串带引号，数字不加）
    {"desc": "timezone 应为 Asia/Taipei", "kind": "eq",
     "path": "location.timezone", "value": "Asia/Taipei"},

    # 4) exists 单条：默认严格，null / "" 都判失败
    {"desc": "confidence_threshold 必须非 null", "kind": "exists", "path": "confidence_threshold"},

    # 5) exists 批量：null_ok 放行 null/""，optional 允许字段整体缺失（只提示）
    {"desc": "event_types 可选字段", "kind": "exists", "null_ok": True, "optional": True,
     "fields": ["frequency", "detecting_duration", "detecting_threshold", "interval", "zones"]},

    # 6) list_field：数组每项都要有该字段（键名是 field）
    {"desc": "event_types 每项都要有 id", "kind": "list_field", "path": "event_types", "field": "id"},

    # 7) for_each：数组逐项
    {"desc": "event_types 每项必需字段", "kind": "for_each", "path": "event_types", "sub": [
        {"desc": "必需字段", "kind": "top_fields", "fields": ["id", "name", "is_detecting", "scheduled_times"]},
    ]},

    # 8) for_each 套 for_each：内层 "path": "." 表示当前元素本身
    {"desc": "event_types.zones 每个区域", "kind": "for_each", "path": "event_types", "sub": [
        {"desc": "zones 逐项", "kind": "for_each", "path": "zones", "null_ok": True, "sub": [
            {"desc": "区域必需字段", "kind": "top_fields", "fields": ["id", "name", "polygon_type", "geometry"]},
            {"desc": "geometry.coordinates 必须存在", "kind": "exists", "path": "geometry.coordinates"},
        ]},
    ]},

    # 9) shared_eq：响应值与 shared 比对
    #    ID 在路径末段时引擎已自动收：/v2/tasks/{id} → shared["tasks"]，直接用这个键名
    #    ID 在路径中间（/record/{id}/objects）时才需按 README 第五节 3) 自己补 onRequest
    {"desc": "响应 id 与 URL 中的 ID 一致", "kind": "shared_eq",
     "path": "id", "shared_key": "tasks"},

    # 10) gt / gte / lt / lte：大小比较（拿不准字段值就别写死上限，先用 gte 探实际值）
    {"desc": "id 是正数", "kind": "gt", "path": "id", "value": 0},

    # 时间比较大：两边都是 ISO 时间串就自动按时间比，不用转格式
    # {"desc": "事件时间不早于请求时间", "kind": "gte",
    #  "path": "event_time", "shared_key": "_body.event_time"},

    # 11) shared_not_in：排除名单（响应值不能落在 shared 的名单里）
    #     请求侧要有对应参数（如 ?exclude_ids=9&exclude_ids=10）才生效，没有则 ℹ️ 跳过
    # {"desc": "id 不在排除名单", "kind": "shared_not_in",
    #  "path": "id", "shared_key": "_query.exclude_ids", "require_shared": True},

    # 12) shared_contains：响应数组要包含请求的每个值（创建接口服务端会补默认项）
    # {"desc": "event_type_ids 响应包含请求", "kind": "shared_contains",
    #  "path": "event_types.id", "shared_key": "event_type_ids", "require_shared": True},
]
# ============================================================

# ==================== 其它接口写法（注释示例） ====================
# 列表接口（?ids=1&ids=2 → {"total":N,"results":[...]}）：
# checks = [c for c in checks if c.get("kind") != "shared_eq"] + [
#     {"desc": "每条 id 都属于请求的 ids", "kind": "shared_in",
#      "path": "id", "shared_key": "_query.ids"},
# ]
# 注意：results 型响应 checks 是逐条跑的，"page / size / total" 这类信封字段写进 checks 取不到，
#      改用整体级 META_CHECKS（写法见文件上方 EXPECTED_CODE 之后）。
#
# 请求体回显（顶层字段已平铺，直接用原字段名）：
# {"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq", "path": "event_type_id"}
#
# 嵌套请求体字段（走 _body）：
# {"desc": "object_key 与请求一致", "kind": "shared_eq",
#  "path": "object_key", "shared_key": "_body.data.object_key"}
#
# 排除名单（返回的 id 不能出现在请求的 exclude_ids 里）：
# {"desc": "id 不在排除名单", "kind": "shared_not_in",
#  "path": "id", "shared_key": "_query.exclude_ids", "require_shared": True}
#
# 创建接口（响应是请求的超集，服务端会补默认项）：
# {"desc": "event_type_ids 响应包含请求", "kind": "shared_contains",
#  "path": "event_types.id", "shared_key": "event_type_ids", "require_shared": True}
# ============================================================
