# API Docs: https://reqable.com/docs/capture/addons
# ========================= kind 说明 =========================
# kind 说明:
#   top_fields : 必须存在的字段列表；默认查当前对象，加 "path" 可查某个嵌套子对象
#                (子对象为 null 或父级为 null 视为正常，与 list_field/for_each 一致)
#   eq         : 字段值 == 期望值
#                {"desc","kind","key","value"}         顶层字段
#                {"desc","kind","path","value"}        嵌套字段(path 点分，数组用下标如 vlms.0.x)
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
#   for_each   : 对【数组】每个元素递归执行 "sub" 里的子检查(可再套 top_fields/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  数组为 null 或父级为 null 视为正常
#                注意: path 必须指向数组；单个对象请用 top_fields + path
#                数组套数组时，内层写 "path": "." 表示【当前这个元素本身】(如 detected_objects)
#                加 "null_ok": True 时，该数组字段【整体不存在】也放行(用于可选数组，如某些项没有 zones)
# ==============================================================

from reqable import *
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())

# 期望响应码；本清单按任务详情接口（201）写的，换接口改这里
EXPECTED_CODE = 201


# ========================= 检查项 =========================
# 每种 kind 保留一条示例
checks = [
    # 1) top_fields：顶层必需字段
    {"desc": "顶层必需字段", "kind": "top_fields",
     "fields": ["id", "name", "task_status", "operating_status", "scheduler",
                "event_types", "camera", "location", "cluster", "snapshot",
                "object_size_filter", "confidence_threshold"]},

    # 2) top_fields + path：嵌套单个对象（对象为 null 视为正常）
    {"desc": "camera 必需字段", "kind": "top_fields", "path": "camera",
     "fields": ["id", "name", "source_url", "fps", "resolution_height",
                "resolution_width", "model_name", "coordinates", "address"]},

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
    #    ID 只在路径里时，需按 README 第五节 3) 覆盖 onRequest 补 _path_ids，否则此条 ℹ️ 跳过
    {"desc": "响应 id 与 URL 中的 ID 一致", "kind": "shared_eq",
     "path": "id", "shared_key": "_path_ids.0"},
]
# ============================================================

# ==================== 其它接口写法（注释示例） ====================
# 列表接口（?ids=1&ids=2 → {"total":N,"results":[...]}）：
# checks = [c for c in checks if c.get("kind") != "shared_eq"] + [
#     {"desc": "每条 id 都属于请求的 ids", "kind": "shared_in",
#      "path": "id", "shared_key": "_query.ids"},
# ]
# 注意：results 型响应 checks 是逐条跑的，"total" 这类整体计数当前引擎做不到。
#
# 请求体回显（顶层字段已平铺，直接用原字段名）：
# {"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq", "path": "event_type_id"}
#
# 嵌套请求体字段（走 _body）：
# {"desc": "object_key 与请求一致", "kind": "shared_eq",
#  "path": "object_key", "shared_key": "_body.data.object_key"}
# ============================================================
