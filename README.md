# Reqable_API_checks 支持Reqable的API接口消息使用check list方法的python脚本。
# API Docs: https://reqable.com/docs/capture/addons
# ========================= 检查项配置区 =========================
# kind 说明:
#   top_fields : 必须存在的字段列表；默认查当前对象，加 "path" 可查某个嵌套子对象
#                (子对象为 null 或父级为 null 视为正常，与 list_field/for_each 一致)
#   eq         : 字段值 == 期望值
#                {"desc","kind","key","value"}         顶层字段
#                {"desc","kind","path","value"}        嵌套字段(path 点分，数组用下标如 vlms.0.x)
#   exists     : 字段是否存在；默认 null 也算错，加 "null_ok": True 放行 null(含父级为 null)
#                ★支持批量: {"desc","kind","fields":[...],"null_ok":True,"optional":True}
#                fields 一次查多个顶层字段；null_ok 放行 null；optional 允许字段整体缺失(只提示不失败)
#   list_field : 数组里每个元素都必须含某字段；数组为 null 或父级为 null 视为正常
#   for_each   : 对【数组】每个元素递归执行 "sub" 里的子检查(可再套 top_fields/list_field/for_each)；
#                {"desc","kind","path","sub":[ ...子检查... ]}  数组为 null 或父级为 null 视为正常
#                注意: path 必须指向数组；单个对象请用 top_fields + path
#                加 "null_ok": True 时，该数组字段【整体不存在】也放行(用于可选数组，如某些项没有 zones)
# ==============================================================

from reqable import *
import json
import os
    
CORE = os.path.abspath(os.path.expanduser(r"~/Documents/reqable/reqable_check_core.py"))
if not os.path.isfile(CORE):
    raise FileNotFoundError(f"公共引擎不存在: {CORE}（用 ~ 或绝对路径）")

exec(compile(open(CORE, encoding="utf-8").read(), CORE, "exec"), globals())

# 期望的响应码；规则脚本里写 EXPECTED_CODE = 201 即可覆盖
#EXPECTED_CODE = 200

# ===============================================================

checks = [
    # --- 1. 每条结果顶层必需字段 ---
    {"desc": "顶层必需字段", "kind": "top_fields",
     "fields": ["id", "name", "task_status", "operating_status", "scheduler", 
     "event_types", "camera", "location", "cluster", "snapshot", "object_size_filter", "confidence_threshold"]},
    # --- camera 是【单个对象】：直接用 top_fields + path 查它的必需字段(为 null 视为正常) ---
    {"desc": "camera 必需字段", "kind": "top_fields", "path": "camera", "fields":
      ["id", "name", "source_url","fps" , "resolution_height", "resolution_width", "model_name", "coordinates", "address"]
    },
    {"desc": "camera.coordinates 的必需字段", "kind": "top_fields", "path": "camera.coordinates", "fields":
      ["latitude", "longitude"]
    },
    # --- location 是【单个对象】：直接用 top_fields + path 查它的必需字段(为 null 视为正常) ---
    {"desc": "location 必需字段", "kind": "top_fields", "path": "location", "fields":
      ["id", "name", "timezone" , "organization_id", "coordinates"]
    },
    {"desc": "location.coordinates 的必需字段", "kind": "top_fields", "path": "location.coordinates", "fields":
      ["latitude", "longitude"]
    },
    # --- cluster 是【单个对象】：直接用 top_fields + path
    {"desc": "cluster 必需字段", "kind": "top_fields", "path": "cluster", "fields": ["id", "name", "address"]
    },
    # --- scheduler 是【单个对象】：直接用 top_fields + path
    {"desc": "scheduler 必需字段", "kind": "top_fields", "path": "scheduler", "fields": ["type", "scheduled_times"]
    },
    # --- event_types 是【数组】用 for_each 遍历每个元素，再用for_each；
    {"desc": "子元组每项必需字段", "kind": "for_each", "path": "event_types", "sub":
      [{"desc": "event_types 元组必需字段", "kind": "top_fields", "fields":
        ["id", "name", "is_detecting", "scheduled_times" ]
      },
      # 批量 exists：每个字段都必须存在，值为 null 放行(可写 "null_ok": False 要求非 null)
      # "optional": True 表示这些字段本身是【可选项】——缺失只提示不算失败(随 event_type 不同而不同)
      {"desc": "event_types 字段是否存在(允许null)", "kind": "exists", "null_ok": True, "optional": True, "fields":
        ["frequency", "detecting_duration", "detecting_threshold", "interval", "zones"]},
      ]
    },
    # --- zones 在 event_types 每项里面，是【数组套数组】：两层 for_each；没有 zones 的项用 null_ok 跳过 ---
    {"desc": "event_types.zones 每个区域必需字段", "kind": "for_each", "path": "event_types", "sub":
      [{"desc": "zones 每项", "kind": "for_each", "path": "zones", "null_ok": True, "sub":
        [{"desc": "区域必需字段", "kind": "top_fields", "fields":
          ["id", "name", "polygon_type", "geometry"]
        },
        {"desc": "geometry.type 字段是否存在(允许null)", "kind": "exists", "path": "geometry.type"},
        {"desc": "geometry.coordinates 字段是否存在", "kind": "exists", "path": "geometry.coordinates"}]
      }]
    },    
                
    # --- 2. 简单 key==value 断言 ---
    {"desc": "timezone 应为 Asia/Taipei", "kind": "eq", "path": "location.timezone", "value": "Asia/Taipei"},
    
    # --- 3. 字段是否必填（默认严格：null 也判 ❌）---
    {"desc": "confidence_threshold 必须非 null", "kind": "exists", "path": "confidence_threshold"},
    {"desc": "camera.source_url 必须非 null", "kind": "exists", "path": "camera.source_url"},
    {"desc": "object_size_filter 必须非 null", "kind": "exists", "path": "object_size_filter"}
]
# ===============================================================
