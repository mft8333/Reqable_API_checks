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
#   shared_in  : 响应值【属于】shared 里的列表（列表接口用：返回的每条 id 是否都在请求的 ids 里）
#                {"desc","kind","path","shared_key"}  取键规则与 shared_eq 完全相同
#                shared 取到的若不是列表，会自动当成单元素列表比；严格相等，注意类型
#   for_each   : 对【数组】每个元素递归执行 "sub" 里的子检查(可再套 top_fields/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  数组为 null 或父级为 null 视为正常
#                注意: path 必须指向数组；单个对象请用 top_fields + path
#                数组套数组时，内层写 "path": "." 表示【当前这个元素本身】(如 detected_objects)
#                加 "null_ok": True 时，该数组字段【整体不存在】也放行(用于可选数组，如某些项没有 zones)
# ==============================================================

from reqable import *
import json
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())
# ===============================================================

# 期望的响应码；默认 200，其它状态码（201 / 204 / 4xx）在这里覆盖
# 下面这份清单针对任务详情接口（返回 201），换成别的接口时改这里
EXPECTED_CODE = 201


def _val(v):
    """查询参数取值转类型：纯数字转 int（便于与响应里的数字比）；逗号分隔且每段都是数字转列表；其余保持字符串。"""
    parts = v.split(",")
    if len(parts) > 1 and all(p.isdigit() for p in parts):
        return [int(p) for p in parts]
    return int(v) if v.isdigit() and (v == "0" or not v.startswith("0")) else v


def onRequest(context, request):
    """合并版 onRequest：引擎默认逻辑（打 URL、请求体进 shared、打印 shared）+ 通用的路径/查询参数收集。

    不写死接口名与参数名，挂到所有接口上都只读不改。
    Reqable 的 onRequest / onResponse 在不同进程里跑，跨阶段只能靠 context.shared 传递。
    """
    print("request url " + context.url)

    sh = {}

    # 1) 请求体：顶层字段平铺（老写法 shared_key: "object_key" 继续可用）+ 原始结构 _body
    try:
        body = json.loads(request.body.payload)
        if isinstance(body, dict):
            sh.update(body)
            sh["_body"] = body
        elif body is not None:
            sh["_body"] = body
    except Exception:
        pass                                    # GET / 非 JSON body 时忽略

    path = str(getattr(request, "path", "") or context.url)   # 可能不含 query
    full = str(context.url)                                   # 完整 URL，含 query

    # 2) 路径段：_path 原样段；_path_ids 全部纯数字段；_path_id 第一个数字段；_path_count 数字段个数
    segs = [s for s in path.split("?")[0].split("/") if s]
    if segs:
        sh["_path"] = segs
        nums = [int(s) for s in segs if s.isdigit()]
        if nums:
            sh["_path_ids"] = nums
            sh["_path_id"] = nums[0]
            sh["_path_count"] = len(nums)

    # 3) 查询参数：不认参数名，全收
    #    _query        单值→标量 / 重复 key→列表（纯数字转 int）
    #    _query_all    一律列表、一律原始字符串（未做类型转换）
    #    _query_counts {参数名: 值的个数}
    #    _query_count  所有参数值的总个数
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

    context.shared = sh
    _print_shared(context)                      # 控制台打印 shared = {...}，照着它写 shared_key
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
    #    单条资源接口（/v2/tasks/144310、/v2/vlms/template/21029…）取 _path_ids.0
    #    关键项建议加 "require_shared": True —— 否则 onRequest 没跑到时会静默跳过
    {"desc": "响应 id 与 URL 中的 ID 一致", "kind": "shared_eq",
     "path": "id", "shared_key": "_path_ids.0"},
]
# ===============================================================

# ==================== 其它接口的写法示例（默认注释） ====================
# 列表接口（?ids=129728&ids=141076 返回 {"total":2,"results":[...]}）：
# 把上面第 9 条换成下面这条 —— 每条记录判「它的 id 属于请求的 ids」
# ⚠️ 注意：results 型响应里 checks 是【逐条】跑的，"path": "total" 取不到东西，
#          「返回条数 == 请求条数」属于整体级检查，当前引擎没有这一层
#
# checks = [c for c in checks if c.get("kind") != "shared_eq"] + [
#     {"desc": "返回的每条 id 都属于请求的 ids", "kind": "shared_in",
#      "path": "id", "shared_key": "_query.ids"},
# ]
#
# 请求体回显（body 顶层字段已平铺在 shared 根上，直接用原字段名）：
# {"desc": "响应 event_type_id 与请求一致", "kind": "shared_eq", "path": "event_type_id"}
#
# 嵌套请求体字段（走 _body 原始结构）：
# {"desc": "object_key 与请求一致", "kind": "shared_eq",
#  "path": "object_key", "shared_key": "_body.data.object_key"}
# ====================================================================
