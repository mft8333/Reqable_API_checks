# API Docs: https://reqable.com/docs/capture/addons
# ========================= kind 说明 =========================
# kind 说明:
#   top_fields : 必须存在的字段列表；默认查当前对象，加 "path" 可查某个嵌套子对象
#                (子对象为 null 或父级为 null 视为正常，与 list_field/for_each 一致)
#                可选子对象(某些记录里没有 / 为 null / 为 {})：
#                  加 "optional": True 放行【对象整体不存在】(只在写了 path 时有意义)
#                  加 "null_ok": True  放行【空对象 {} / 空数组 []】(null 本来就不算失败)
#                  两者可同时写；不加时"字段不存在"照旧判 ❌，避免把配错的 path 掩盖过去
#   eq         : 字段值 == 期望值
#                {"desc","kind","key","value"}         顶层字段
#                {"desc","kind","path","value"}        嵌套字段(path 点分，数组用下标如 vlms.0.x)
#   in_list    : 字段值【属于自己定义的常量集合】（枚举校验：文档里 "Possible values: a, b" 这种）
#                {"desc","kind","path","value":["operating","non-operating"]}
#                命中任一项 → ✅；不在集合 → ❌ 并打印实际值与允许集合；严格相等（大小写、类型都不猜）
#                path 取到数组时要求【每个元素都在】集合里；加 "loose": True 放宽「数字 ↔ 数字字符串」
#                字段不存在 / 值为 null 默认 ❌，加 "null_ok": True 放行
#                value 写成空列表 / 不是列表 → 打 ⚠️ 跳过（没有可接受值，不能静默通过）
#   not_in_list : 字段值【不属于】自己定义的禁止集合（黑名单，in_list 的反面）
#                {"desc","kind","path","value":["deleted","archived"]}
#                命中禁值 → ❌ 并打印命中项；不在集合 → ✅；严格相等，加 "loose": True 同样放宽
#                path 取到数组时要求【每个元素都不命中】；value 写空列表 → ℹ️ 视为通过（没有禁止值）
#                字段不存在 / 值为 null 默认 ❌，加 "null_ok": True 放行
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
#                加 "loose": True 时放宽「数字 ↔ 数字字符串」：'3000' 与 3000 视为相等
#                (422 的 input 是原始字符串、_query.size 已转 int，这种场景必用)；其余类型仍严格
#                不写 loose 就是严格相等，原有配置行为不变
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
#                加 "label": "id" 时，输出里每条带上该字段值(如 [2] id=206)，便于人工定位是哪个元素；
#                取不到或值不是标量就退回纯下标，不影响判定结果
#   整体级     : META_CHECKS 列表，只跑一次、对象是整个响应 data（分页的 page / size / total 等信封字段）
#                kind 语法与 checks 完全相同；不写 / 写 [] / 写 None 都不会报错
#    通用	   : path / shared_key 遇到数组时，写数字是下标(vlms.0.x)，写字段名则投影成列表
#                (如 _body.event_type_id → [103, 206]，要求每项都有该字段)
#                字段名后加 ? 是【松散投影】：只保留有该字段的元素，一个都没有就是 []（仍算取到）
#                (如事件里有的写 id、有的写 vlm_flow_id → _body.events.id? = [103, 112, 113])
#                段名写 * 是【摊平一层】：数组套数组时用 (event_types.zones?.*.id? → [102, 106])
#                段名后带 [字段=值] 是【按值配对】：数组里找第一条匹配项，| 表示任一命中
#                (_body.events[id=103].zones → 请求里 id=103 那条的 zones；找不到即取不到)
#                shared_key 里可写 ${字段}（当前元素）/ ${..字段}（往上一层），嵌套配对时用
#                (如 "_body.events[id=${..id}|vlm_flow_id=${..id}].zones[id=${id}].coordinates")
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
    # 1) top_fields：记录自身必需字段（不是响应最外层；嵌套里就别写“顶层”了）
    {"desc": "记录自身必需字段", "kind": "top_fields",
     "fields": ["id", "name", "task_status", "operating_status", "scheduler",
                "event_types", "camera", "location", "cluster", "snapshot",
                "object_size_filter", "confidence_threshold"]},

    # 1b) top_fields + path：可选子对象（某些记录里没有它 / 它是 null / 它是 {}）
    #     optional=True 放行「对象整体不存在」，null_ok=True 放行「空对象 {}」；两个都写最宽
    #     只写其中一个也行：null 天然放行，{} 靠 null_ok，缺失靠 optional
    {"desc": "model_settings 的必需字段", "kind": "top_fields", "path": "model_settings",
     "fields": ["id", "name", "version"], "optional": True, "null_ok": True},

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

    # 3b) in_list：枚举取值（文档写的 Possible values 全部列进来，命中任一即通过）
    #     严格相等：Operating ≠ operating；字符串数字枚举（"384"）要加 loose 才和数字互等
    #     注：样例报文里 task_status 实际是 "Unknown"，文档的 Possible values 只有 operating /
    #     non-operating —— 这个值先按实际放行，要不要算异常由业务定（去掉它就会报 ❌）
    {"desc": "task_status 取值", "kind": "in_list", "path": "task_status",
     "value": ["operating", "non-operating", "Unknown"]},

    # 3c) not_in_list：黑名单（in_list 的反面，命中任一禁值就失败）
    {"desc": "task_status 不能是删除态", "kind": "not_in_list", "path": "task_status",
     "value": ["deleted", "archived"]},

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
    #    段名带连字符也原样保留：/v2/events/vlm-relationship/206 → shared["vlm-relationship"]
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
# 类型不一致时（422 的 input 是原始字符串 '3000'，_query.size 已是 int 3000）：
# {"desc": "input 与请求参数一致", "kind": "shared_eq", "path": "detail.0.input",
#  "shared_key": "_query.size", "loose": True, "require_shared": True}
# 或直接取原始字符串（不加 loose 也能过）：
# {"desc": "input 与请求参数一致", "kind": "shared_eq", "path": "detail.0.input",
#  "shared_key": "_query_all.size.0", "require_shared": True}
#
# 排除名单（返回的 id 不能出现在请求的 exclude_ids 里）：
# {"desc": "id 不在排除名单", "kind": "shared_not_in",
#  "path": "id", "shared_key": "_query.exclude_ids", "require_shared": True}
#
# 创建接口（响应是请求的超集，服务端会补默认项）：
# {"desc": "event_type_ids 响应包含请求", "kind": "shared_contains",
#  "path": "event_types.id", "shared_key": "event_type_ids", "require_shared": True}
#
# 三层对比：① 外层 event id 配对 → ② zone id 是否一致 → ③ 每个 zone 的坐标是否一致
# {"desc": "请求的 event 都出现在响应中", "kind": "shared_contains",
#  "path": "event_types.id", "shared_key": "_body.events.id?", "require_shared": True}
# {"desc": "event 与请求对账", "kind": "for_each", "path": "event_types", "label": "id", "sub": [
#     {"desc": "zone id 包含请求的", "kind": "shared_contains", "path": "zones?.id",
#      "shared_key": "_body.events[id=${id}|vlm_flow_id=${id}].zones.id?"},
#     {"desc": "zone 坐标", "kind": "for_each", "path": "zones?", "null_ok": True, "label": "id", "sub": [
#         {"desc": "coordinates 一致", "kind": "shared_eq", "path": "geometry.coordinates",
#          "shared_key": "_body.events[id=${..id}|vlm_flow_id=${..id}].zones[id=${id}].coordinates"}]}]}
# ============================================================
