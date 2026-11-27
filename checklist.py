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
#                加 "optional": True 时字段【整体不存在】只打 ℹ️；字段在但为 null 照旧按值比较
#   in_list    : 字段值【属于自己定义的常量集合】（枚举校验：文档里 "Possible values: a, b" 这种）
#                {"desc","kind","path","value":["operating","non-operating"]}
#                命中任一项 → ✅；不在集合 → ❌ 并打印实际值与允许集合；严格相等（大小写、类型都不猜）
#                path 取到数组时要求【每个元素都在】集合里；加 "loose": True 放宽「数字 ↔ 数字字符串」
#                字段不存在 / 值为 null 默认 ❌；"optional": True 放行缺失，"null_ok": True 放行 null
#                value 写成空列表 / 不是列表 → 打 ⚠️ 跳过（没有可接受值，不能静默通过）
#   not_in_list : 字段值【不属于】自己定义的禁止集合（黑名单，in_list 的反面）
#                {"desc","kind","path","value":["deleted","archived"]}
#                命中禁值 → ❌ 并打印命中项；不在集合 → ✅；严格相等，加 "loose": True 同样放宽
#                path 取到数组时要求【每个元素都不命中】；value 写空列表 → ℹ️ 视为通过（没有禁止值）
#                字段不存在 / 值为 null 默认 ❌；"optional": True 放行缺失，"null_ok": True 放行 null
#   gt/gte/lt/lte : 大小比较（> >= < <=），要求两边【同为数字】或【同为 ISO 时间串】
#                {"desc","kind","path","value"}         与常量比
#                {"desc","kind","path","shared_key"}    与 onRequest 写入的请求值比（二选一，都写时按 shared_key）
#                时间写法: 2026-05-15 / 2026-05-15T08:00:00Z / 2026-05-15T08:00:36.782976Z
#                无时区的按 UTC 处理；普通文本不当时间比，"5" 与 5 也不算同类（不做隐式转换）
#                加 "optional": True 时字段【整体不存在】只打 ℹ️，适合"可选但给了就不能空"的字段
#                (字段在但为 null 仍 ❌，要放过 null 再写 "null_ok": True)
#   exists     : 字段是否存在；默认 null 和 ""(空串) 都算错，加 "null_ok": True 放行 null/""(含父级为 null)
#                ★支持批量: {"desc","kind","fields":[...],"null_ok":True,"optional":True}
#                fields 一次查多个顶层字段；null_ok 放行 null；optional 允许字段整体缺失(只提示不失败)
#   list_field : 数组里每个元素都必须含某字段；数组为 null 或父级为 null 视为正常
#                加 "optional": True 时该数组字段【整体不存在】也放行(可选数组，等价旧写法 null_ok)
#   shared_eq  : 与 onRequest 写入的 context.shared 比对（如 object_key 是否被改写成 env 值）
#                {"desc","kind","path","shared_key"}  响应取值用 path/key，shared 取值用 shared_key
#                shared_key 省略时依次退化为 path / key；context.shared 不可用(测试脚本为 null)时
#                打印 ℹ️ 跳过、不计失败；加 "require_shared": True 则改为判 ❌
#                加 "loose": True 时放宽「数字 ↔ 数字字符串」：'3000' 与 3000 视为相等
#                (422 的 input 是原始字符串、_query.size 已转 int，这种场景必用)；其余类型仍严格
#                两边都是数组时逐项按 loose 比：[103] 与 ['103'] 相等，但 [103,17469] 与 ['103']
#                个数不同仍 ❌（要允许响应多出项，用 shared_contains）；不写 loose 就是严格相等
#                加 "optional": True 时响应里字段整体不存在只打 ℹ️（字段在但为 null 照旧 ❌）
#   shared_in  : 响应值【属于】shared 里的列表(列表接口用：返回的每条 id 是否都在请求的 ids 里)
#                {"desc","kind","path","shared_key"}  取键规则与 shared_eq 完全相同
#                shared 取到的若不是列表，会自动当成单元素列表比；严格相等，注意类型
#                path 取到的是数组时，要求【每个元素都属于】请求(如 detail.task_ids vs _body.task_id)
#                加 "loose": True 时「103 属于 ['103']」也成立（_query_all 的值都是字符串）
#   shared_not_in : 响应值【不属于】shared 里的列表 —— shared_in 的反面，用于排除名单(黑名单)
#                {"desc","kind","path","shared_key"}  取键规则与 shared_in 完全相同
#                path 取到的是数组时，要求【每个元素都不命中】排除名单
#                shared 取到空列表 [] 时没有可排除的值，打 ℹ️ 视为通过（不会误判通过一堆数据）
#                shared 取到的若不是列表，同样当成单元素列表比；严格相等，注意类型
#                同样支持 "loose": True（数字 ↔ 数字字符串互等）
#   shared_contains : 响应数组【包含】shared 里的每个值（响应 ⊇ 请求，允许服务端追加默认项）
#                {"desc","kind","path","shared_key"}  取键规则与 shared_in 完全相同
#                典型场景：创建任务时服务端会补默认 event_types，响应比请求多出几个，
#                这时 shared_in(每项都属于请求) 必然失败，改用本条只校验「请求的都出现」
#                加 "loose": True 时 103 与请求里的 '103' 同样算命中
#                path 必须指向数组(或投影成数组，如 event_types.id)，否则判 ❌ 并提示改用 shared_eq
#                shared 只有单值时同样要求它出现在响应数组里；空列表 [] 打 ℹ️ 视为通过
#   sub_checks : 对【单个对象】执行 "sub" 里的多条子检查(可套 top_fields/eq/exists/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  对象为 null / 父级为 null 视为正常
#                适用「可选对象但字段多」：一条检查打包整组，对象是 null 时整组 ℹ️ 跳过
#                "path": "." 表示当前对象本身；对象字段整体不存在时加 "optional": True 放行(旧写法 null_ok 也认)
#   for_each   : 对【数组】每个元素递归执行 "sub" 里的子检查(可再套 top_fields/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  数组为 null 或父级为 null 视为正常
#                注意: path 必须指向数组；单个对象请用 sub_checks（或 top_fields + path）
#                数组套数组时，内层写 "path": "." 表示【当前这个元素本身】(如 detected_objects)
#                加 "optional": True 时，该数组字段【整体不存在】也放行(可选数组，如某些项没有 zones)
#                (旧写法 "null_ok": True 同样认，两者等价；值为 null 本来就视为正常)
#                加 "label": "id" 时，输出里每条带上该字段值(如 [2] id=206)，便于人工定位是哪个元素；
#                取不到或值不是标量就退回纯下标，不影响判定结果
#   整体级     : META_CHECKS 列表，只跑一次、对象是整个响应 data（分页的 page / size / total 等信封字段）
#                kind 语法与 checks 完全相同；不写 / 写 [] / 写 None 都不会报错
#   通用       : path / shared_key 遇到数组时，写数字是下标(vlms.0.x)，写字段名则投影成列表
#                (如 _body.event_type_id → [103, 206]，要求每项都有该字段)
#                字段名后加 ? 是【松散投影】：只保留有该字段的元素，一个都没有就是空列表 []
#                (如 events 里有的写 id、有的写 vlm_flow_id → _body.events.id? = [103, 112, 113, 13892])
#                段名写 * 是【摊平一层】：数组套数组时用 (zones?.*.id? → [102, 106, 102, 104])
#                段名后带 [字段=值] 是【按值配对】：在数组里找第一条匹配项，多个条件用 | 表示任一命中
#                (如 _body.events[id=103].zones → 请求里 id=103 那条的 zones；找不到即取不到)
#                shared_key 里可写 ${字段}（当前元素）或 ${..字段}（往上一层），用于嵌套配对
#                (如 "_body.events[id=${..id}|vlm_flow_id=${..id}].zones[id=${id}].coordinates")
#                写了不属于该 kind 的键(如 exists 里塞 sub)会打 ⚠️，这些键不生效
#   条件跳过   : 任意 kind 都能加 "when"，条件不成立就整条跳过（ℹ️，不计失败）
#                {"shared_key": "_query_all.event_type_ids.0", "eq": "other"}   请求侧取值 == 常量
#                {"shared_key": "_query_all.event_type_ids.0", "numeric": True} 取值是数字
#                {"shared_key": "_body.ids", "in": ["a", "b"]}                  取值（或数组每项）在集合内
#                {"path": "status", "eq": "failed"}                             也可用响应字段做条件
#                可组合，全部成立才算成立；加 "loose": True 同样放宽「数字 ↔ 数字字符串」
#                取不到条件（shared 没写入等）打 ⚠️ 并跳过，不会误判成 ❌
# ==============================================================

from reqable import *
import os

CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())

# 期望响应码（本清单按事件记录详情接口写，换接口改这里）
EXPECTED_CODE = 200

# 整体级检查：只跑一次、对象是整个响应 data；单对象响应留空即可
# 分页接口把 page / size / total 放这里（results 型响应的信封字段只能在 META_CHECKS 里查）
META_CHECKS = []


# ========================= 检查项 =========================
# 组织顺序：结构（必需字段 → 对象 → 数组）→ 取值（常量 / 枚举 / 范围）→ 对账（与请求比）
checks = [
    # ---------- 1. 记录自身 ----------
    # 基本写法：顶层必需字段，缺一个就 ❌；嵌套字段不要塞进来，交给下面的子对象/数组
    {"desc": "记录自身必需字段", "kind": "top_fields", "fields":
      ["event_record_id", "task_id", "event_type_id", "event_name", "event_description",
        "event_record_status", "timestamp", "updated_timestamp", "video_time", "image_url",
        "image_urls", "video_url", "location_id", "camera_id", "video_id", "timezone",
        "vlms", "coordinates", "note"]
    },

    # 可选子对象：optional 放行「整体不存在」，null_ok 放行「{} / []」
    # 两个都写才是「可以没有，有就不能是空壳」；只写 optional 时 {} 仍会因缺字段判 ❌
    {"desc": "model_settings 的必需字段", "kind": "top_fields", "path": "model_settings",
      "optional": True, "null_ok": True, "fields":
      ["id", "name", "version"]
    },

    # ---------- 2. 单个对象：sub_checks ----------
    # 基本：一个对象打包几条子检查；对象为 null 时整组 ℹ️ 跳过，不必给每条子检查都写 optional
    {"desc": "camera 对象", "kind": "sub_checks", "path": "camera", "sub":
      [{"desc": "必需字段", "kind": "top_fields", "fields":
        ["id", "name", "source_url", "model_name", "coordinates"]
      },
      {"desc": "可选字段", "kind": "exists", "null_ok": True, "optional": True, "fields":
        ["fps", "resolution_height", "resolution_width", "address"]
      },
      {"desc": "coordinates 对象", "kind": "top_fields", "path": "coordinates", "fields":
        ["latitude", "longitude"]
      },
      {"desc": "source_url 非空", "kind": "exists", "path": "source_url"}]
    },

    # 复杂：对象里套数组，数组项再查字段与非空 —— sub_checks → for_each → top_fields / exists
    {"desc": "object_detection 对象", "kind": "sub_checks", "path": "object_detection", "sub": [
      {"desc": "必需字段", "kind": "top_fields", "fields":
        ["event_type_id", "event_type_name", "event_type_description", "detectors"]
      },
      {"desc": "detectors 列表", "kind": "for_each", "path": "detectors", "label": "model_repository_id", "sub":
        [{"desc": "必需字段", "kind": "top_fields", "fields":
          ["model_repository_id", "model_repository_name", "targets"]
        },
        {"desc": "targets 非空", "kind": "exists", "path": "targets"}]
      }]
    },

    # ---------- 3. 属性数组：for_each ----------
    # 基本：逐项查字段
    {"desc": "vlms 列表", "kind": "for_each", "path": "vlms", "label": "vlm_template_id", "sub":
      [{"desc": "必需字段", "kind": "top_fields", "fields":
        ["vlm_template_id", "vlm_template_name", "model_name", "model_version", "results"]
      },
      {"desc": "results 列表", "kind": "for_each", "path": "results", "sub":
        [{"desc": "必需字段", "kind": "top_fields", "fields":
          ["key", "val"]
        }]
      }]
    },

    # 复杂之一：数组套数组 —— 内层 path 写 "." 表示「当前这个元素本身」
    # detected_objects 是 [[{...}], [{...}]]，得先拆外层分组，才能拿到 object_name / 坐标
    {"desc": "detected_objects 列表", "kind": "for_each", "path": "detected_objects", "sub":
      [{"desc": "分组", "kind": "for_each", "path": ".", "sub":
        [{"desc": "必需字段", "kind": "top_fields", "fields":
          ["object_id", "object_name", "coordinates", "confidence_score", "warning"]
        },
        # 占位值出现在检测结果里，通常是模型没认出来，属于真问题
        {"desc": "object_name 不能是占位值", "kind": "not_in_list", "path": "object_name",
          "value": ["", "unknown"]
        },
        {"desc": "信心得分 <= 1", "kind": "lte", "path": "confidence_score", "value": 1}]
      }]
    },

    # 复杂之二：可选字段 + 数值范围 + 嵌套数组 + 子对象，一条覆盖四层
    # zones 用 null_ok：没有布防区域的 event 也合法（数组为 null / 缺字段都放过）
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
      {"desc": "zones 列表", "kind": "for_each", "path": "zones", "null_ok": True, "label": "id", "sub":
        [{"desc": "必需字段", "kind": "top_fields", "fields":
          ["id", "name", "polygon_type", "geometry"]
        },
        {"desc": "geometry 对象", "kind": "top_fields", "path": "geometry", "fields":
          ["type", "coordinates"]
        }]
      }]
    },

    # 轻量版：只要求每项都有该字段，不展开其他检查（和上面的 for_each 二选一即可）
    {"desc": "event_types 每项都要有 id", "kind": "list_field", "path": "event_types", "field": "id"},

    # ---------- 4. 取值 ----------
    # 固定值：字符串带引号，数字 / 布尔不加
    {"desc": "timezone 应为 Asia/Taipei", "kind": "eq", "path": "timezone", "value": "Asia/Taipei"},

    # 枚举：value 只按接口文档的 possible values 写（Operating ≠ operating）
    {"desc": "event_record_status 取值", "kind": "in_list", "path": "event_record_status",
      "value": ["Confirmed", "Unconfirmed"]
    },

    # ---------- 5. 范围 ----------
    # 常量比较
    {"desc": "event_record_id 为正数", "kind": "gt", "path": "event_record_id", "value": 0},

    # 时间窗：与 onRequest 收进 shared 的请求参数比，不写死时间
    {"desc": "事件时间 >= 请求开始时间", "kind": "gte", "path": "timestamp", "shared_key": "_query.start_time"},
    {"desc": "事件时间 < 请求结束时间", "kind": "lt", "path": "timestamp", "shared_key": "_query.end_time"},

    # 地理范围：纬度落在请求的上下界之间（经度同理，换字段即可）
    {"desc": "纬度 >= 请求下界", "kind": "gte", "path": "coordinates.latitude", "shared_key": "_query.start_latitude"},
    {"desc": "纬度 <= 请求上界", "kind": "lte", "path": "coordinates.latitude", "shared_key": "_query.end_latitude"},

    # ---------- 6. 响应与请求对账 ----------
    # 三个取值来源，写 shared_key 前先想清楚用哪个：
    #   _query     参数已按类型转换（size 是 int），适合和数字字段比
    #   _query_all 原始字符串列表（['103']），数组 / 需要保留原样时用，比数字要加 loose
    #   _body      请求体原始结构（JSON 解析后），嵌套字段走 _body.data.xxx
    #   另外：URL 末段是 id 时引擎会自动收（/events/record/2289267 → shared["record"]）

    # 基本：单值相等；require_shared 让「请求没带上」也判失败，避免静默跳过
    {"desc": "event_record_id 响应与请求一致", "kind": "shared_eq", "path": "event_record_id",
      "shared_key": "record", "require_shared": True
    },

    # 列表接口：响应每个值都必须属于请求的集合（多返回一条就是 ❌）
    # _query_all 是原始字符串，响应是数字 → loose；不加就会拿 15610 和 '15610' 硬比
    # 加 when：?event_type_ids=other 时没有可比集合（other 不是类型 id），交给下面的空数组断言
    {"desc": "event_type_id 属于请求的类型", "kind": "shared_in", "path": "event_type_id",
      "shared_key": "_query_all.event_type_ids", "loose": True,
      "when": {"shared_key": "_query_all.event_type_ids.0", "numeric": True}
    },

    # 排除名单：请求 ?exclude_event_type_ids=9&... 时生效，没带则 ℹ️ 跳过
    {"desc": "event_type_id 不在排除名单", "kind": "shared_not_in", "path": "event_type_id",
      "shared_key": "_query.exclude_event_type_ids"
    },

    # 过滤接口：响应 ⊇ 请求（服务端会补默认项，用 shared_in 会误判）
    # _query_all 的值是字符串，响应是数字 → 必须 loose，[103] 才等于 ['103']
    # 同一份清单要兼容 ?event_type_ids=103 与 ?event_type_ids=other，所以用 when 分流：
    #   数字 → 走本条；other → 走下面那条「应为空数组」
    # 用于创建接口（没有过滤参数）时，把 when 去掉即可
    # 字段名注意：这个接口的 event_types 项只有 id（不是 event_type_id），写错会报「取不到」
    {"desc": "数字过滤时 event_types 包含请求", "kind": "shared_contains",
      "path": "event_types.id", "shared_key": "_query_all.event_type_ids", "loose": True,
      "require_shared": True,
      "when": {"shared_key": "_query_all.event_type_ids.0", "numeric": True}
    },

    # 关键字 other：这类图片不带 event_type，响应 event_types 应为空数组
    {"desc": "other 过滤时 event_types 应为空", "kind": "eq", "path": "event_types", "value": [],
      "when": {"shared_key": "_query_all.event_type_ids.0", "eq": "other"}
    },

    # 422 示例：200 响应里没有 detail，必须 optional，否则每条正常响应都会被判「字段不存在」
    {"desc": "422错误结构", "kind": "for_each", "path": "detail", "optional": True, "sub":
      [{"desc": "必需字段", "kind": "top_fields", "fields":
        ["input", "ctx", "type", "loc", "msg"]
      },
      {"desc": "message 检查", "kind": "eq", "path": "msg", "value": "Input should be less than or equal to 300"},
      # --- 响应与请求参数检查 ---
      {"desc": "input 与请求参数检查", "kind": "shared_eq", "path": "input", "shared_key": "_query.size", "require_shared": True, "loose": True}]
    },

    # ---------- 7. 三层对账（最复杂的一条） ----------
    # 目标：请求里的每个 event，其 zones 的 id 与坐标都要和响应一致。
    # 为什么拆成三层，而不是一条 eq 比完：
    #   第 1 层 先断「请求的 event 都在响应里」。外层对不上时，后面按 id 配对必然全部取空，
    #           先给出根因，不至于让人误以为是坐标算错。
    #   第 2 层 按 event id 比 zone id 集合。用 shared_contains（响应 ⊇ 请求）而不是相等，
    #           因为服务端可能合并/补默认 zone，多出来的 zone 不算错。
    #   第 3 层 再按 (event id, zone id) 双重配对，逐个比 geometry.coordinates。
    # 关键语法：
    #   ${id}                          当前 for_each 元素的 id
    #   ${..id}                        往上一层（event）的 id —— 内层已站在 zone 上，所以要退一层
    #   [id=${id}|vlm_flow_id=${id}]   在请求数组里按值找第一条匹配项；| 表示任一命中
    #   zones?.id / .zones.id?         字段名后的 ? 是松散投影：跳过没有该字段的元素，不报错
    # 三个容易踩的点：
    #   1) 坐标是浮点数组，严格相等。后端有精度截断时这里会红，先确认是否需要量化再改。
    #   2) 内层 zones 用 null_ok：有 event 没有 zone 是正常业务，不该判失败。
    #   3) 只校验「请求的都在响应里」，不比对数量 —— 数量对不上时第 2 层不会红，
    #      要强制一对一，得再加一条对 length 的 eq。
    #
    # 第 1 层：请求的 event 都出现在响应里（响应 event_types.id ⊇ 请求 _body.events.id?）
    {"desc": "请求的 event 都出现在响应中", "kind": "shared_contains", "path": "event_types.id",
      "shared_key": "_body.events.id?", "require_shared": True
    },

    # 第 2、3 层：外层 id 配上了，才往下比 zones
    {"desc": "event 与请求对账", "kind": "for_each", "path": "event_types", "label": "id", "sub":
      [ # 第 2 层：zone id 是否一致（请求的每个 zone 都要在响应里）
        {"desc": "zone id 包含请求的", "kind": "shared_contains", "path": "zones?.id",
          "shared_key": "_body.events[id=${id}|vlm_flow_id=${id}].zones.id?"
        },
        # 第 3 层：同一个 zone id，比坐标
        {"desc": "zone 坐标", "kind": "for_each", "path": "zones?", "null_ok": True, "label": "id", "sub":
          [{"desc": "coordinates 一致", "kind": "shared_eq", "path": "geometry.coordinates",
            "shared_key": "_body.events[id=${..id}|vlm_flow_id=${..id}].zones[id=${id}].coordinates"
          }]
        }
      ]
    },
]
# ============================================================
