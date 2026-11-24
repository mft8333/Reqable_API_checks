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
#   gt/gte/lt/lte : 大小比较（> >= < <=），要求两边【同为数字】或【同为 ISO 时间串】
#                {"desc","kind","path","value"}         与常量比
#                {"desc","kind","path","shared_key"}    与 onRequest 写入的请求值比（二选一，都写时按 shared_key）
#                时间写法: 2026-05-15 / 2026-05-15T08:00:00Z / 2026-05-15T08:00:36.782976Z
#                无时区的按 UTC 处理；普通文本不当时间比，"5" 与 5 也不算同类（不做隐式转换）
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
#   shared_not_in : 响应值【不属于】shared 里的列表 —— shared_in 的反面，用于排除名单(黑名单)
#                {"desc","kind","path","shared_key"}  取键规则与 shared_in 完全相同
#                path 取到的是数组时，要求【每个元素都不命中】排除名单
#                shared 取到空列表 [] 时没有可排除的值，打 ℹ️ 视为通过（不会误判通过一堆数据）
#                shared 取到的若不是列表，同样当成单元素列表比；严格相等，注意类型
#   shared_contains : 响应数组【包含】shared 里的每个值（响应 ⊇ 请求，允许服务端追加默认项）
#                {"desc","kind","path","shared_key"}  取键规则与 shared_in 完全相同
#                典型场景：创建任务时服务端会补默认 event_types，响应比请求多出几个，
#                这时 shared_in(每项都属于请求) 必然失败，改用本条只校验「请求的都出现」
#                path 必须指向数组(或投影成数组，如 event_types.id)，否则判 ❌ 并提示改用 shared_eq
#                shared 只有单值时同样要求它出现在响应数组里；空列表 [] 打 ℹ️ 视为通过
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
#   整体级      : META_CHECKS 列表，只跑一次、对象是整个响应 data（分页的 page / size / total 等信封字段）
#                kind 语法与 checks 完全相同；不写 / 写 [] / 写 None 都不会报错
#    通用	   : path / shared_key 遇到数组时，写数字是下标(vlms.0.x)，写字段名则投影成列表
#                (如 _body.event_type_id → [103, 206]，要求每项都有该字段)
#                字段名后加 ? 是【松散投影】：只保留有该字段的元素，一个都没有就是空列表 []
#                (如 events 里有的写 id、有的写 vlm_flow_id → _body.events.id? = [103, 112, 113, 13892])
#                段名写 * 是【摊平一层】：数组套数组时用 (zones?.*.id? → [102, 106, 102, 104])
#                段名后带 [字段=值] 是【按值配对】：在数组里找第一条匹配项，多个条件用 | 表示任一命中
#                (如 _body.events[id=103].zones → 请求里 id=103 那条的 zones；找不到即取不到)
#                shared_key 里可写 ${字段}（当前元素）或 ${..字段}（往上一层），用于嵌套配对
#                (如 "_body.events[id=${..id}|vlm_flow_id=${..id}].zones[id=${id}].coordinates")
#                写了不属于该 kind 的键(如 exists 里塞 sub)会打 ⚠️，这些键不生效
# ==============================================================

from reqable import *
import datetime as _dt
import json
import re
from urllib.parse import unquote

# 期望的响应码；规则脚本里写 EXPECTED_CODE = 201 即可覆盖
EXPECTED_CODE = 200

# 整体级检查：只跑一次、对象是整个响应 data（分页的 page / size / total 这类信封字段）
# 规则脚本里覆盖即可；不写、写 [] 或 None 都不会报错
META_CHECKS = []

_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")


def _split_path(path):
    """按 . 切分，但 [ ] 里的内容不切（过滤条件里可能有 . 或 ${..x}）。"""
    out, buf, depth = [], "", 0
    for ch in path:
        if ch == "[":
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
        if ch == "." and not depth:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return [s for s in out if s]


def _cond_match(x, cond):
    """过滤条件 field=value，值按字符串比（int 206 与 "206" 视为相同）。"""
    if "=" not in cond:
        return False
    k, v = cond.split("=", 1)
    ex, val = _get_nested(x, k.strip())
    return ex and str(val) == v.strip()


def _fill_placeholders(key, cur, stack):
    """把 shared_key 里的 ${路径} 换成字段值：${id} 取当前元素，${..id} 往上一层。
    返回 (替换后的键, 失败说明或 None)；解析不出来时不猜，直接报错让配置可见。
    """
    err = [None]

    def rep(m):
        expr = m.group(1).strip()
        n = 0
        while expr.startswith(".."):
            n += 1
            expr = expr[2:].lstrip(".")
        node = cur if n == 0 else (stack[n - 1] if n - 1 < len(stack) else None)
        ex, val = _get_nested(node, expr) if isinstance(node, (dict, list)) else (False, None)
        if not ex or isinstance(val, (dict, list)):
            err[0] = err[0] or f"占位符 ${{{m.group(1)}}} 解析失败（当前元素里取不到 {expr}）"
            return "?"
        return str(val)

    return _PLACEHOLDER.sub(rep, key), err[0]


def _get_nested(obj, path):
    """按点分路径取值，支持穿过数组(下标)；返回 (是否存在, 值)。
    path 为 "." 或 "$" 时表示【当前对象本身】(数组套数组时内层用)。
    数组 + 非下标键 → 投影成「每项该字段」的列表(如 _body.event_type_id → [103, 206])；
    有元素缺该字段时视为取不到，避免拿到残缺列表还判通过。
    键名带 ? 后缀 → 松散投影：只保留【有该字段】的元素，一个都没有时返回空列表 []（仍算取到）。
    段名写 * → 摊平一层（[[a],[b]] → [a, b]），用于数组套数组。
    段名后带 [字段=值] → 在数组里找第一条匹配的元素（多个条件用 | 分隔，任一命中即可），
    用于 join：拿当前元素的 id 去请求数组里找对应的那条。找不到即视为取不到。
    """
    if path in (".", "$"):
        return True, obj
    cur = obj
    for seg in _split_path(path):
        cond = None
        if "[" in seg and seg.endswith("]"):
            seg, cond = seg.split("[", 1)
            cond = cond[:-1]
        loose = seg.endswith("?")
        if loose:
            seg = seg[:-1]
            if not seg and cond is None:
                return False, None          # "?" 只能加在字段名后，不能加在下标上
        if seg == "*":
            if not isinstance(cur, list):
                return False, None
            cur = [y for x in cur for y in x] if all(isinstance(x, list) for x in cur) else cur
        elif seg:
            if seg.isdigit() or (seg.startswith("-") and seg[1:].isdigit()):
                if loose:
                    return False, None
                if not isinstance(cur, list):
                    return False, None
                try:
                    cur = cur[int(seg)]
                except (IndexError, TypeError):
                    return False, None
            elif isinstance(cur, list):
                if loose:
                    cur = [x[seg] for x in cur if isinstance(x, dict) and seg in x]
                else:
                    if not cur or not all(isinstance(x, dict) and seg in x for x in cur):
                        return False, None
                    cur = [x[seg] for x in cur]
            elif isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                return False, None
        if cond is not None:
            if not isinstance(cur, list):
                return False, None
            if cond.isdigit():                      # [0] 就是下标，等价于 .0
                i = int(cond)
                if not -len(cur) <= i < len(cur):
                    return False, None
                cur = cur[i]
            else:
                hit = [x for x in cur if any(_cond_match(x, p) for p in cond.split("|"))]
                if not hit:
                    return False, None
                cur = hit[0]
    return True, cur


def _null_ancestor(obj, path):
    """路径中是否有某一级父字段的值为 null（用于放行“父级为空”的情况）。"""
    parts = path.split(".")
    for n in range(1, len(parts)):
        ex, v = _get_nested(obj, ".".join(parts[:n]))
        if ex and v is None:
            return True
    return False


def _is_empty(v):
    """null 与空字符串 "" 都算“没有值”（exists 默认判失败）。
    注意用 == 而不是 is，避免 0 / False / [] 被误判为空。
    """
    return v is None or v == ""


def _is_num(v):
    """能参与大小比较的“数字”：int / float，bool 不算（True 会被当成 1 混过去）。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _to_time(v):
    """把 ISO 8601 时间串解析成 UTC datetime；认不出返回 None（调用方据此判 ❌）。
    认: 2026-05-15 / 2026-05-15T08:00:00 / 空格分隔 / 带 .微秒 / 带 Z 或 ±HH:MM(±HHMM)
    不认: 普通文本 —— 绝不做字典序比较，否则 "abc" > "abd" 会让配错的检查悄悄通过
    """
    if not isinstance(v, str):
        return None
    s = v.strip()
    if len(s) < 10 or (len(s) > 10 and "T" not in s and " " not in s):
        return None
    if s[-5] in "+-" and s[-4:].isdigit():      # +0800 → +08:00（3.11 以下 fromisoformat 不认无冒号写法）
        s = s[:-2] + ":" + s[-2:]
    if s[-1] in "Zz":                           # 3.10 及以下 fromisoformat 不认 Z
        s = s[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:                       # naive 统一按 UTC，避免 aware/naive 混比抛 TypeError
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc)


# 大小比较：kind 就是运算符，写法和 eq 一样（path/key + value）
_CMP_OPS = {"gt": (">", lambda a, b: a > b), "gte": (">=", lambda a, b: a >= b),
            "lt": ("<", lambda a, b: a < b), "lte": ("<=", lambda a, b: a <= b)}


def _brief(v, n=5):
    """列表超过 n 项时只显示前 n 项，避免一条检查刷屏。
    n 默认 5：常见的 3~5 项 id 列表能完整显示，不出现「...共N个」占位。
    """
    if isinstance(v, list) and len(v) > n:
        return v[:n] + [f"...共{len(v)}个"]
    return v


def _get_value(obj, c):
    """按 key(顶层) 或 path(嵌套) 取值。两者都没写时返回 (False, None)，避免 KeyError 打断整轮检查。"""
    if "path" in c:
        return _get_nested(obj, c["path"])
    if "key" in c and isinstance(obj, dict):
        return (True, obj[c["key"]]) if c["key"] in obj else (False, None)
    return False, None


def _shared_value(ctx, key, cur=None, stack=None):
    """从 onRequest 写入的 context.shared 里按点分路径取值，返回 (是否存在, 值, 失败说明)。
    key 里可以写 ${字段}（取当前元素）或 ${..字段}（往上一层），先替换再取路径。
    ctx 为 None（本地测试直接调 _run_check）或 shared 不是 dict 时，一律视为不可用。
    """
    sh = getattr(ctx, "shared", None) if ctx is not None else None
    if not isinstance(sh, dict) or not key:
        return False, None, None
    if "${" in key:
        key, err = _fill_placeholders(key, cur, stack or [])
        if err:
            return False, None, err
    exists, val = _get_nested(sh, key)
    if exists:
        return True, val, None
    if "[" in key:
        return False, None, f"请求里没有配对的元素，或该元素没有这个字段（{key}）"
    return False, None, f"context.shared 中没有 {key}（onRequest 未写入/未生效，或 shared 为空）"


def _loose_eq(a, b):
    """loose 模式的相等判断：在严格相等基础上，额外放宽「数字 ↔ 数字字符串」。
    典型场景：422 的 input 是原始字符串 '3000'，而 _query.size 已被转成 int 3000。
    只放宽这一种，其余照旧：'abc' 与 'ABC'、None 与 'None'、[] 与 '' 都不算相等；
    bool 也不参与放宽（True 不等于 1 或 '1'），避免 True 被当成 1 混过去。
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if a == b:
        return True

    def num(v):
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                try:
                    return float(v.strip())
                except ValueError:
                    return None
        return None

    na, nb = num(a), num(b)
    return na is not None and nb is not None and na == nb


def _shared_or_skip(c, ctx, skey, cur, stack):
    """取 shared 值；取不到时按 require_shared 判 ❌ 还是 ℹ️ 跳过。返回 (是否取到, 值, 失败数)。"""
    exists, want, err = _shared_value(ctx, skey, cur, stack)
    if exists:
        return True, want, 0
    where = err or f"context.shared 中没有 {skey}（onRequest 未写入/未生效，或 shared 为空）"
    if c.get("require_shared"):
        print(f"❌ {c['desc']}: {where}")
        return False, None, 1
    print(f"ℹ️ {c['desc']}: {where}，跳过")
    return False, None, 0


# 每种 kind 允许的键（用于提示「写了不支持的键」）
_COMMON_KEYS = {"desc", "kind", "path", "key"}
_KIND_KEYS = {
    "top_fields": {"fields", "null_ok", "optional"},
    "eq": {"value"},
    "in_list": {"value", "null_ok", "loose"},
    "not_in_list": {"value", "null_ok", "loose"},
    "gt": {"value", "null_ok", "shared_key", "require_shared"},
    "gte": {"value", "null_ok", "shared_key", "require_shared"},
    "lt": {"value", "null_ok", "shared_key", "require_shared"},
    "lte": {"value", "null_ok", "shared_key", "require_shared"},
    "exists": {"fields", "null_ok", "optional"},
    "list_field": {"field"},
    "for_each": {"sub", "null_ok", "label"},
    "sub_checks": {"sub", "null_ok"},
    "shared_eq": {"shared_key", "require_shared", "loose"},
    "shared_in": {"shared_key", "require_shared"},
    "shared_not_in": {"shared_key", "require_shared"},
    "shared_contains": {"shared_key", "require_shared"},
}


def _run_check(r, c, ctx=None, stack=None):
    """执行单条检查并打印，返回本条贡献的失败数(0 或 >=1)。可被 for_each 递归调用。
    ctx 供 shared_* 读取 context.shared；stack 是上层元素列表（最近的在前面），
    用于 ${..字段} 往上一层取值。不传 ctx 时 shared 相关项自动跳过（兼容旧调用）。
    """
    kind = c["kind"]
    stack = stack or []

    # 写了不属于该 kind 的键（比如 exists 里塞 sub）会被静默忽略 → 这条等于没检查，先提示出来
    extra = [k for k in c if k not in _COMMON_KEYS and k not in _KIND_KEYS.get(kind, set())]
    if extra:
        print(f"⚠️ {c['desc']}: kind={kind} 不支持 {extra}，这些键被忽略（这条可能没在检查你以为的内容）")

    if kind == "top_fields":
        if "fields" not in c:
            print(f"⚠️ {c['desc']}: top_fields 缺少 fields，跳过")
            return 0
        target = r
        if c.get("path"):                       # 指定了 path：先定位到那个子对象
            exists, target = _get_value(r, c)
            if not exists:
                if _null_ancestor(r, c["path"]):
                    print(f"ℹ️ {c['desc']}: 父级为 null（视为正常）")
                    return 0
                if c.get("optional"):           # 可选对象：这条记录里干脆没有这个对象
                    print(f"ℹ️ {c['desc']}: 可选对象 {c['path']} 不存在（optional 放行）")
                    return 0
                print(f"❌ {c['desc']}: 字段 {c['path']} 不存在")
                return 1
            if target is None:
                print(f"ℹ️ {c['desc']}: {c['path']} 为 null（视为正常）")
                return 0
            if c.get("null_ok") and isinstance(target, (dict, list)) and not target:
                what = "空对象 {}" if isinstance(target, dict) else "空数组 []"
                print(f"ℹ️ {c['desc']}: {c['path']} 为{what}（null_ok 放行）")
                return 0
        if not isinstance(target, dict):         # 无 path 时也要挡：for_each 的元素可能是数字/字符串
            where = f"{c['path']} " if c.get("path") else "当前对象"
            print(f"❌ {c['desc']}: {where}不是对象，实际是 {type(target).__name__}（字段检查需要对象）")
            return 1
        missing = [f for f in c["fields"] if f not in target]
        if not missing:
            print(f"✅ {c['desc']}")
            return 0
        have = list(target)                                 # 失败时带上实际键名，便于发现 path 指错了对象
        if len(have) > 12:
            have = have[:12] + [f"...共{len(target)}个"]
        print(f"❌ {c['desc']} {missing} 实际有: {have}")
        return 1

    elif kind == "eq":
        exists, actual = _get_value(r, c)
        ok = exists and actual == c["value"]
        print(f"{'✅' if ok else '❌'} {c['desc']}: 实际 {actual!r} / 期望 {c['value']!r}")
        return 0 if ok else 1

    # 枚举校验：值属于自己定义的常量集合（value 写列表，命中任一即通过）
    elif kind == "in_list":
        allow = c.get("value")
        if not isinstance(allow, list):
            print(f"⚠️ {c['desc']}: in_list 的 value 要写列表（如 [\"a\", \"b\"]），"
                  f"实际是 {type(allow).__name__}；单个值请用 eq，跳过")
            return 0
        if not allow:
            print(f"⚠️ {c['desc']}: in_list 的 value 是空列表，没有可接受的值，跳过（配置有误）")
            return 0
        exists, actual = _get_value(r, c)
        if not exists:
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 字段不存在（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 字段 {c.get('path') or c.get('key')} 不存在，允许 {_brief(allow)}")
            return 1
        if actual is None:
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 值为 null（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 实际 null，允许 {_brief(allow)}")
            return 1
        loose = bool(c.get("loose"))

        def _hit(x):                                # loose 只放宽「数字 ↔ 数字字符串」，其余严格
            return any(_loose_eq(x, v) for v in allow) if loose else x in allow

        if isinstance(actual, list):                # 投影成数组时：要求每个元素都在集合里
            bad = [x for x in actual if not _hit(x)]
            ok = not bad
            if ok:
                print(f"✅ {c['desc']}: 实际 {_brief(actual)}，{len(actual)} 项都在允许集合内")
            else:
                print(f"❌ {c['desc']}: 实际 {_brief(actual)}，其中 {_brief(bad)} 不在允许 {_brief(allow)} 中")
            return 0 if ok else 1
        ok = _hit(actual)
        tail = "（按 loose 视为命中）" if ok and loose and actual not in allow else ""
        print(f"{'✅' if ok else '❌'} {c['desc']}: 实际 {actual!r}"
              f"{' 在' if ok else ' 不在'}允许 {_brief(allow)} 中{tail}")
        return 0 if ok else 1

    # 黑名单：值不属于自己定义的禁止集合（命中即失败）
    elif kind == "not_in_list":
        deny = c.get("value")
        if not isinstance(deny, list):
            print(f"⚠️ {c['desc']}: not_in_list 的 value 要写列表（如 [\"deleted\"]），"
                  f"实际是 {type(deny).__name__}；单个值也请放进列表，跳过")
            return 0
        if not deny:
            print(f"ℹ️ {c['desc']}: value 是空列表，没有禁止的值（视为通过）")
            return 0
        exists, actual = _get_value(r, c)
        if not exists:
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 字段不存在（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 字段 {c.get('path') or c.get('key')} 不存在")
            return 1
        if actual is None:
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 值为 null（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 实际 null，禁止 {_brief(deny)}")
            return 1
        loose = bool(c.get("loose"))

        def _denied(x):                             # loose 只放宽「数字 ↔ 数字字符串」，其余严格
            return any(_loose_eq(x, v) for v in deny) if loose else x in deny

        if isinstance(actual, list):                # 投影成数组时：要求每个元素都不命中
            bad = [x for x in actual if _denied(x)]
            ok = not bad
            if ok:
                print(f"✅ {c['desc']}: 实际 {_brief(actual)}，{len(actual)} 项都不在禁止 {_brief(deny)} 中")
            else:
                print(f"❌ {c['desc']}: 实际 {_brief(actual)}，其中 {_brief(bad)} 命中禁止 {_brief(deny)}")
            return 0 if ok else 1
        bad = _denied(actual)
        tail = "（按 loose 视为命中）" if bad and loose and actual not in deny else ""
        msg = (f"实际 {actual!r}，命中禁止 {_brief(deny)}{tail}" if bad
               else f"实际 {actual!r}，不在禁止 {_brief(deny)} 中")
        print(f"{'❌' if bad else '✅'} {c['desc']}: {msg}")
        return 0 if not bad else 1

    # 大小比较：kind 即运算符（gt / gte / lt / lte）
    # 两边同为数字 → 比数字；两边同为 ISO 时间串 → 比时间；其余一律 ❌（不做隐式转换）
    # 比较基准：value（常量）或 shared_key（onRequest 写入的请求值），二选一
    elif kind in _CMP_OPS:
        sym, fn = _CMP_OPS[kind]
        skey = c.get("shared_key")
        if skey:
            if "value" in c:
                print(f"⚠️ {c['desc']}: {kind} 同时写了 value 和 shared_key，按 shared_key 比较")
            sh_exists, want, _skip = _shared_or_skip(c, ctx, skey, r, stack)
            if not sh_exists:
                return _skip
            label = "shared"
        else:
            if "value" not in c:
                print(f"⚠️ {c['desc']}: {kind} 缺少 value（或改用 shared_key），跳过")
                return 0
            want, label = c["value"], "期望"
        exists, actual = _get_value(r, c)
        if not exists:
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 字段不存在（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 字段 {c.get('path') or c.get('key')} 不存在")
            return 1
        if actual is None and c.get("null_ok"):
            print(f"ℹ️ {c['desc']}: 值为 null（null_ok 放行）")
            return 0
        if _is_num(actual) and _is_num(want):
            a_v, w_v, tag = actual, want, ""
        else:
            a_v, w_v = _to_time(actual), _to_time(want)   # "5" 和 5 不是一回事，不做隐式转换
            if a_v is None or w_v is None:
                print(f"❌ {c['desc']}: 只能比较数字或 ISO 时间，实际 {actual!r}（{type(actual).__name__}）"
                      f" / {label} {want!r}（{type(want).__name__}）")
                return 1
            tag = "（按时间）"
        ok = fn(a_v, w_v)
        print(f"{'✅' if ok else '❌'} {c['desc']}: 实际 {actual!r} {sym} {label} {want!r}{tag} → {'成立' if ok else '不成立'}")
        return 0 if ok else 1

    # ★新增：批量 exists（一次校验多个顶层字段；optional=True 时缺失放行，null_ok 时 null/"" 放行）
    elif kind == "exists" and "fields" in c:
        # 批量：optional 管“字段缺失”，null_ok 管“值为 null 或空串”
        if not isinstance(r, dict):
            print(f"❌ {c['desc']}: 当前对象不是对象，实际是 {type(r).__name__}（批量 exists 需要对象）")
            return 1
        bad, missing = [], []
        for f in c["fields"]:
            if f not in r:
                (missing if c.get("optional") else bad).append(f)   # 可选项缺失 → 只提示
            elif not c.get("null_ok") and _is_empty(r[f]):
                bad.append(f)                                      # null/"" 且不放行 → 失败
        if bad:
            print(f"❌ {c['desc']} {bad}")
            return 1
        tail = f"（可选项缺失: {missing}）" if missing else ""
        print(f"{'ℹ️' if missing else '✅'} {c['desc']}{tail}")
        return 0

    elif kind == "exists":
        exists, val = _get_value(r, c)
        if c.get("null_ok"):
            if exists:
                if _is_empty(val):
                    print(f"ℹ️ {c['desc']}: 存在但为 null/空串（null_ok 放行）")
                    return 0
                print(f"✅ {c['desc']}")
                return 0
            elif "path" in c and _null_ancestor(r, c["path"]):
                print(f"ℹ️ {c['desc']}: 父级为 null（null_ok 放行）")
                return 0
            else:
                print(f"❌ {c['desc']}: 字段不存在")
                return 1
        else:
            ok = exists and not _is_empty(val)      # null 和 "" 都判失败
            print(f"{'✅' if ok else '❌'} {c['desc']}")
            return 0 if ok else 1

    elif kind == "shared_eq":
        # 与 onRequest 写入的 context.shared 比对（跨进程只能靠 shared 传值）
        skey = c.get("shared_key") or c.get("path") or c.get("key")
        if not skey:
            print(f"⚠️ {c['desc']}: 缺少 shared_key（shared_eq 需指定 shared 中的字段名）")
            return 0
        sh_exists, want, _skip = _shared_or_skip(c, ctx, skey, r, stack)
        if not sh_exists:
            return _skip
        exists, actual = _get_value(r, c)
        loose = bool(c.get("loose"))
        ok = exists and (_loose_eq(actual, want) if loose else actual == want)
        tail = "（按 loose 视为相等）" if loose and ok and actual != want else ""
        print(f"{'✅' if ok else '❌'} {c['desc']}: 实际 {actual!r} / 请求中携带的 {want!r}{tail}")
        return 0 if ok else 1

    elif kind == "shared_in":
        # 响应值【属于】onRequest 写入 context.shared 的列表（列表接口用：返回的每条 id 都在请求的 ids 里）
        skey = c.get("shared_key") or c.get("path") or c.get("key")
        if not skey:
            print(f"⚠️ {c['desc']}: 缺少 shared_key（shared_in 需指定 shared 中的列表字段名）")
            return 0
        sh_exists, want, _skip = _shared_or_skip(c, ctx, skey, r, stack)
        if not sh_exists:
            return _skip
        allow = want if isinstance(want, list) else [want]
        exists, actual = _get_value(r, c)
        if not exists:
            where = c.get("path") or c.get("key") or "?"
            print(f"❌ {c['desc']}: 取不到 {where}（字段不存在或路径写错）")
            return 1
        if isinstance(actual, list):                # 响应侧也是数组：要求每个元素都属于请求
            bad = [x for x in actual if x not in allow]
            ok = not bad
            if ok:
                print(f"✅ {c['desc']}: 实际 {_brief(actual)}，{len(actual)} 项都属于请求")
            else:
                print(f"❌ {c['desc']}: 实际 {_brief(actual)}，其中 {_brief(bad)} 不在请求消息 {_brief(allow)} 中")
            return 0 if ok else 1
        ok = exists and actual in allow
        tail = "" if ok else f"，不在请求消息 {allow!r} 中"
        print(f"{'✅' if ok else '❌'} {c['desc']}: 实际 {actual!r}{tail}")
        return 0 if ok else 1

    elif kind == "shared_not_in":
        # 响应值【不属于】onRequest 写入的排除名单（shared_in 的反面：黑名单里的 id 一个都不能出现）
        skey = c.get("shared_key") or c.get("path") or c.get("key")
        if not skey:
            print(f"⚠️ {c['desc']}: 缺少 shared_key（shared_not_in 需指定 shared 中的列表字段名）")
            return 0
        sh_exists, want, _skip = _shared_or_skip(c, ctx, skey, r, stack)
        if not sh_exists:
            return _skip
        deny = want if isinstance(want, list) else [want]
        if not deny:                                # 空名单：没有可排除的值，说清楚而不是假装检查过
            print(f"ℹ️ {c['desc']}: shared {skey} 是空列表，没有可排除的值（视为通过）")
            return 0
        exists, actual = _get_value(r, c)
        if not exists:
            where = c.get("path") or c.get("key") or "?"
            print(f"❌ {c['desc']}: 取不到 {where}（字段不存在或路径写错）")
            return 1
        if isinstance(actual, list):                # 响应侧也是数组：要求每个元素都不命中排除名单
            bad = [x for x in actual if x in deny]
            ok = not bad
            if ok:
                print(f"✅ {c['desc']}: 实际 {_brief(actual)}，{len(actual)} 项都不在排除名单")
            else:
                print(f"❌ {c['desc']}: 实际 {_brief(actual)}，其中 {_brief(bad)} 命中排除名单 {_brief(deny)}")
            return 0 if ok else 1
        ok = actual not in deny
        tail = "" if ok else f"，命中排除名单 {deny!r}"
        print(f"{'✅' if ok else '❌'} {c['desc']}: 实际 {actual!r}{tail}")
        return 0 if ok else 1

    elif kind == "shared_contains":
        # 响应数组【包含】shared 里的每个值（响应 ⊇ 请求）：服务端会追加默认项时用这条
        skey = c.get("shared_key") or c.get("path") or c.get("key")
        if not skey:
            print(f"⚠️ {c['desc']}: 缺少 shared_key（shared_contains 需指定 shared 中的列表字段名）")
            return 0
        sh_exists, want, _skip = _shared_or_skip(c, ctx, skey, r, stack)
        if not sh_exists:
            return _skip
        need = want if isinstance(want, list) else [want]
        if not need:                                # 请求侧没给要求，说清楚而不是假装检查过
            print(f"ℹ️ {c['desc']}: shared {skey} 是空列表，没有要求包含的值（视为通过）")
            return 0
        exists, actual = _get_value(r, c)
        if not exists:
            where = c.get("path") or c.get("key") or "?"
            print(f"❌ {c['desc']}: 取不到 {where}（字段不存在或路径写错）")
            return 1
        if not isinstance(actual, list):
            print(f"❌ {c['desc']}: path 需指向数组，实际 {actual!r}（{type(actual).__name__}）；"
                  f"单个值请改用 shared_eq")
            return 1
        missing = [x for x in need if x not in actual]
        ok = not missing
        if ok:
            print(f"✅ {c['desc']}: 实际 {_brief(actual)}，请求的 {len(need)} 项都在响应中")
        else:
            print(f"❌ {c['desc']}: 实际 {_brief(actual)}，缺少请求中的 {_brief(missing, 10)}")
        return 0 if ok else 1

    elif kind == "list_field":
        if "field" not in c:
            print(f"⚠️ {c['desc']}: list_field 需要 field（单个字段名，不是 fields），跳过")
            return 0
        if "path" not in c and "key" not in c:
            print(f"⚠️ {c['desc']}: list_field 需要 path（指向数组），跳过")
            return 0
        exists, arr = _get_value(r, c)          # 保留 exists，区分“字段缺失”与“值为 null”
        if not exists:
            if "path" in c and _null_ancestor(r, c["path"]):
                print(f"ℹ️ {c['desc']}: 父级为 null（视为正常）")
                return 0
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 字段不存在（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 字段 {c.get('path') or c.get('key')} 不存在")
            return 1
        elif arr is None:
            print(f"ℹ️ {c['desc']}: {c.get('path') or c.get('key')} 为 null（视为正常）")
            return 0
        elif not isinstance(arr, list):
            print(f"❌ {c['desc']}: {c.get('path') or c.get('key')} 类型异常: {type(arr).__name__}")
            return 1
        elif not arr:
            print(f"✅ {c['desc']}: 数组为空（通过）")
            return 0
        else:
            fail = 0
            for j, item in enumerate(arr):
                ok = isinstance(item, dict) and c["field"] in item
                print(f"{'✅' if ok else '❌'} {c['desc']} → 元素[{j}] 含 {c['field']}: {ok}")
                fail += 0 if ok else 1
            return fail

    elif kind == "for_each":
        exists, arr = _get_value(r, c)
        if not exists:
            if "path" in c and _null_ancestor(r, c["path"]):
                print(f"ℹ️ {c['desc']}: 父级为 null（视为正常）")
                return 0
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 字段不存在（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 字段 {c.get('path') or c.get('key')} 不存在")
            return 1
        elif arr is None:
            print(f"ℹ️ {c['desc']}: {c.get('path') or c.get('key')} 为 null（视为正常）")
            return 0
        elif not isinstance(arr, list):
            where = "当前对象" if c.get("path") in (".", "$") else (c.get("path") or c.get("key"))
            print(f"❌ {c['desc']}: {where} 类型异常: {type(arr).__name__}（for_each 的 path 必须指向数组，单个对象请用 top_fields + path）")
            return 1
        elif not arr:
            print(f"✅ {c['desc']}: 数组为空（通过）")
            return 0
        else:
            subs = c.get("sub") or []
            if not subs:
                print(f"⚠️ {c['desc']}: for_each 缺少 sub，跳过")
                return 0
            fail = 0
            nested = any(s.get("kind") == "for_each" for s in subs)   # 元素本身是数组时交给内层 for_each
            lab = c.get("label")                                      # 想让输出显示哪个字段（如 id），便于定位
            for j, item in enumerate(arr):
                if not isinstance(item, dict) and not (nested and isinstance(item, list)):
                    print(f"❌ {c['desc']}[{j}]: 数组元素是 {type(item).__name__}，不是对象"
                          f"（ID 数组不能逐项查字段，去掉这条 for_each 或改用 exists）")
                    fail += 1
                    continue
                tag = f"[{j}]"
                if lab:
                    _lex, _lv = _get_nested(item, lab) if isinstance(item, dict) else (False, None)
                    if _lex and not isinstance(_lv, (dict, list)):
                        tag = f"[{j}] {lab}={_lv}"                     # 有就带上，取不到退回纯下标
                for sub in subs:
                    sc = dict(sub)                              # 不改动原配置
                    sc["desc"] = f"{c['desc']}{tag}·{sub.get('desc', '')}"
                    # 递归，支持再套 top_fields/list_field/for_each；把当前元素压栈，供 ${..字段} 回溯
                    fail += _run_check(item, sc, ctx, [r] + stack)
            return fail

    elif kind == "sub_checks":
        # 单个对象跑一组子检查：对象为 null（或父级为 null）整组放行，字段缺失看 null_ok
        if c.get("path"):
            exists, obj = _get_value(r, c)
        else:
            exists, obj = True, r                             # 省略 path = 当前对象本身
        if not exists:
            if c.get("path") and _null_ancestor(r, c["path"]):
                print(f"ℹ️ {c['desc']}: 父级为 null（视为正常）")
                return 0
            if c.get("null_ok"):
                print(f"ℹ️ {c['desc']}: 字段不存在（null_ok 放行）")
                return 0
            print(f"❌ {c['desc']}: 字段 {c['path']} 不存在")
            return 1
        elif obj is None:
            print(f"ℹ️ {c['desc']}: {c.get('path') or '当前对象'} 为 null（视为正常）")
            return 0
        elif not isinstance(obj, dict):
            where = "当前对象" if c.get("path") in (".", "$") else c.get("path")
            print(f"❌ {c['desc']}: {where} 类型异常: {type(obj).__name__}（sub_checks 的 path 必须指向单个对象，数组请用 for_each）")
            return 1
        else:
            fail = 0
            for sub in c["sub"]:
                sc = dict(sub)                                # 不改动原配置
                sc["desc"] = f"{c['desc']}·{sub.get('desc', '')}"
                fail += _run_check(obj, sc, ctx, [r] + stack)   # 子检查的 path 从对象内部写起
            return fail

    else:
        print(f"⚠️ 未知检查类型: {kind}")
        return 0



_AUTO_PRINT_SHARED = True       # 清单里设 False 可关掉 onRequest 的自动打印（自行补键后只打一行）


def _print_shared(context):
    """打印 onRequest 写入的 context.shared，方便照着它写测试用例。
    规则脚本在 onRequest 里自己往 shared 补了字段后，可再调一次本函数看合并结果。
    """
    sh = getattr(context, "shared", None)
    try:
        print("shared = " + json.dumps(sh, ensure_ascii=False))
    except Exception:
        print(f"shared = {sh!r}")


def _val(v):
    """参数值转类型：纯数字→int，逗号分隔且全数字→int 列表，其余原样。"""
    parts = v.split(",")
    if len(parts) > 1 and all(p.isdigit() for p in parts):
        return [int(p) for p in parts]
    return int(v) if v.isdigit() and (v == "0" or not v.startswith("0")) else v


def onRequest(context, request):
    """收集 shared：请求体平铺 + _body，URL 查询参数 _query / _query_all，路径末两段「键=值」。

    onRequest 与 onResponse 不同进程，跨阶段只能靠 context.shared。
    """
    print("request url " + context.url)

    sh = {}

    # 1) 请求体：顶层字段平铺 + 原始结构 _body（GET 无 body 时忽略）
    try:
        body = json.loads(request.body.payload)
        if isinstance(body, dict):
            sh.update(body)
            sh["_body"] = body
        elif body is not None:
            sh["_body"] = body
    except Exception:
        pass

    full = str(context.url)                                 # 完整 URL，含 query

    # 2) 查询参数：不认参数名，全收
    #    _query 单值→标量 / 重复 key→列表（转类型）；_query_all 一律列表、字符串
    #    两者都做 URL 解码（%20 → 空格），否则响应里的 "False Alarm" 永远对不上 "False%20Alarm"
    if "?" in full:
        q, qall = {}, {}
        for pair in full.split("?", 1)[1].split("&"):
            if not pair:
                continue
            k, v = pair.split("=", 1) if "=" in pair else (pair, "")
            k, v = unquote(k), unquote(v)
            qall.setdefault(k, []).append(v)
        for k, vs in qall.items():
            vals = [_val(x) for x in vs]
            q[k] = vals if len(vals) > 1 else vals[0]
        sh["_query"] = q
        sh["_query_all"] = qall

    # 3) URL 路径最后两段当「键 = 值」：/record/xxxxx → shared["record"] = xxxxx
    #    末段不像 ID 不收；键名和请求体字段重名时以请求体为准
    #    键名允许字母 + 下划线 + 连字符，连字符原样保留：
    #    /apiserver/v2/events/vlm-relationship/206 → shared["vlm-relationship"] = 206
    #    （去掉 _ 和 - 后必须仍是纯字母，所以 /v2/206 里的 "v2"、纯数字段不会被当键名）
    segs = [s for s in full.split("?", 1)[0].split("/") if s]
    if len(segs) >= 2:
        k, v = segs[-2], segs[-1]
        if (v.isdigit() or (len(v) >= 8 and all(c in "0123456789abcdefABCDEF-" for c in v))) \
                and k.replace("_", "").replace("-", "").isalpha() and k not in sh:
            sh[k] = _val(v)

    context.shared = sh
    if _AUTO_PRINT_SHARED:
        _print_shared(context)                              # 打印 shared，照它写 shared_key
    return request


def onResponse(context, response):
    if response.code != EXPECTED_CODE:
        print(f"⚠️ 响应码不是{EXPECTED_CODE}: {response.code}")
        return response
    try:
        data = json.loads(response.body.payload)
    except Exception as e:
        print(f"❌ JSON 解析失败: {type(e).__name__}: {e}")
        return response

    # 兼容三种响应形态：分页(results 数组) / 单对象 / 根节点即数组
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        if not isinstance(results, list):
            print("⚠️ results 不是列表")
            return response
        records = results
        print(f"✅ 请求成功: page={data.get('page')}, total={data.get('total')}, size={data.get('size')}, 返回 {len(records)} 条\n")
    elif isinstance(data, dict):
        records = [data]                        # 单对象响应：整个 data 当作一条记录
        print("✅ 请求成功: 单对象响应，待检查 1 条\n")
    elif isinstance(data, list):
        records = data                          # 根节点就是数组
        print(f"✅ 请求成功: 根节点为数组，待检查 {len(records)} 条\n")
    else:
        print("⚠️ 无法识别的响应结构")
        return response

    fail = 0
    for i, r in enumerate(records):
        name = (r.get("name") or r.get("event_name")) if isinstance(r, dict) else None
        print(f"—— 检查 [{i}] {name or f'<item-{i}>'} ——")
        for c in checks:
            try:
                fail += _run_check(r, c, context)
            except Exception as e:                  # 单条配置写错不该中断整轮检查
                print(f"❌ {c.get('desc', c.get('kind', '?'))}: 检查执行异常 {type(e).__name__}: {e}")
                fail += 1
        print()
    metas = globals().get("META_CHECKS") or []          # 未定义 / None 都当空，不报错
    if metas:
        print("—— 检查 [整体] ——")
        for c in metas:
            try:
                fail += _run_check(data, c, context)
            except Exception as e:                  # 与逐条检查同样兜底
                print(f"❌ {c.get('desc', c.get('kind', '?'))}: 检查执行异常 {type(e).__name__}: {e}")
                fail += 1
        print()
    print(f"✅ Response成功！响应码预期是{EXPECTED_CODE}: 实际结果{response.code}，CheckList检查完成，失败项: {fail}")
    return response
