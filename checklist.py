# API Docs: https://reqable.com/docs/capture/addons
# ========================= 检查项配置区 =========================
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
#                {"desc","kind","path","field"}   field 是要检查的元素字段名
#   shared_eq  : 与 onRequest 写入的 context.shared 比对（如响应 id 是否等于 URL 里的 task_id）
#                {"desc","kind","path","shared_key"}  响应取值用 path/key，shared 取值用 shared_key
#                shared_key 省略时依次退化为 path / key；context.shared 不可用(测试脚本为 null)时
#                打印 ℹ️ 跳过、不计失败；加 "require_shared": True 则改为判 ❌
#   for_each   : 对【数组】每个元素递归执行 "sub" 里的子检查(可再套 top_fields/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  数组为 null 或父级为 null 视为正常
#                注意: path 必须指向数组；单个对象请用 top_fields + path
#                数组套数组时，内层写 "path": "." 表示【当前这个元素本身】(如 detected_objects)
#                加 "null_ok": True 时，该数组字段【整体不存在】也放行(用于可选数组，如某些项没有 zones)
# ==============================================================

from reqable import *
import json
import os
import re

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())
# ===============================================================

# 期望的响应码；默认 200，其它状态码（201 / 204 / 4xx）在这里覆盖
# 下面这份清单针对任务详情接口（返回 201），换成别的接口时改这里
EXPECTED_CODE = 201


def onRequest(context, request):
    """覆盖引擎默认的 onRequest：把【请求体】和【URL 里的 ID】一起写进 context.shared。

    Reqable 的 onRequest / onResponse 在不同进程里执行，跨阶段取不到模块变量，
    只能靠 context.shared 传；规则脚本里定义同名函数会覆盖引擎注入的那一个。
    """
    sh = {}
    try:                                          # 请求体是 JSON 就合并进来（GET 没有 body）
        body = json.loads(request.body.payload)
        if isinstance(body, dict):
            sh.update(body)
    except Exception:
        pass

    m = re.search(r"/v2/tasks/(\d+)", str(getattr(request, "path", "") or context.url))
    if m:
        sh["task_id"] = int(m.group(1))           # 存 int：响应里的 id 是数字，存字符串比对必失败

    context.shared = sh
    _print_shared(context)                        # 控制台打印 shared = {...}，照着它写 shared_key
    return request


# ========================= 检查项 =========================
# 每种 kind / 写法保留一条示例，需要时按同样的形状往下加。
checks = [
    # 1) top_fields：顶层必需字段
    {"desc": "顶层必需字段", "kind": "top_fields",
     "fields": ["id", "name", "task_status", "operating_status", "scheduler",
                "event_types", "camera", "location", "cluster", "snapshot",
                "object_size_filter", "confidence_threshold"]},

    # 2) top_fields + path：嵌套的【单个对象】（对象为 null 视为正常）
    {"desc": "camera 必需字段", "kind": "top_fields", "path": "camera",
     "fields": ["id", "name", "source_url", "fps", "resolution_height",
                "resolution_width", "model_name", "coordinates", "address"]},

    # 3) eq：固定值断言（字符串要带引号，数字不要）
    {"desc": "timezone 应为 Asia/Taipei", "kind": "eq",
     "path": "location.timezone", "value": "Asia/Taipei"},

    # 4) exists 单条：默认严格，null / "" 都判失败
    {"desc": "confidence_threshold 必须非 null", "kind": "exists", "path": "confidence_threshold"},

    # 5) exists 批量：null_ok 放行 null/""，optional 允许字段整体缺失（只提示不算失败）
    {"desc": "event_types 可选字段", "kind": "exists", "null_ok": True, "optional": True,
     "fields": ["frequency", "detecting_duration", "detecting_threshold", "interval", "zones"]},

    # 6) list_field：数组每一项都必须含某字段（键名是 field，不是 key）
    {"desc": "event_types 每项都要有 id", "kind": "list_field", "path": "event_types", "field": "id"},

    # 7) for_each：数组逐项，子检查可以是任意 kind
    {"desc": "event_types 每项必需字段", "kind": "for_each", "path": "event_types", "sub": [
        {"desc": "必需字段", "kind": "top_fields", "fields": ["id", "name", "is_detecting", "scheduled_times"]},
    ]},

    # 8) for_each 套 for_each：数组套数组，内层 "path": "." 表示当前元素本身
    {"desc": "event_types.zones 每个区域", "kind": "for_each", "path": "event_types", "sub": [
        {"desc": "zones 逐项", "kind": "for_each", "path": "zones", "null_ok": True, "sub": [
            {"desc": "区域必需字段", "kind": "top_fields", "fields": ["id", "name", "polygon_type", "geometry"]},
            {"desc": "geometry.coordinates 必须存在", "kind": "exists", "path": "geometry.coordinates"},
        ]},
    ]},

    # 9) shared_eq：响应值与 onRequest 写入 context.shared 的值比对
    #    关键项建议加 "require_shared": True —— 否则 onRequest 没跑到时会静默跳过
    {"desc": "响应 id 与 URL 中的 task_id 一致", "kind": "shared_eq",
     "path": "id", "shared_key": "task_id"},
]
# ===============================================================
