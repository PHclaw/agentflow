"""每次调用模型前注入本机当前公历/农历，由模型自行决定是否在回复中使用。"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from lunar_python import Solar

TZ = ZoneInfo("Asia/Shanghai")
WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def now_shanghai() -> datetime:
    return datetime.now(TZ)


def _lunar_parts(dt: datetime) -> dict[str, str]:
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    lunar = solar.getLunar()
    month = lunar.getMonthInChinese()
    day = lunar.getDayInChinese()
    ganzhi = lunar.getYearInGanZhi()
    shengxiao = lunar.getYearShengXiao()
    return {
        "ganzhi": ganzhi,
        "shengxiao": shengxiao,
        "month": month,
        "day": day,
        "ymd": f"{ganzhi}年（{shengxiao}年）{month}月{day}",
        "ganzhi_full": (
            f"{lunar.getYearInGanZhi()}年 "
            f"{lunar.getMonthInGanZhi()}月 "
            f"{lunar.getDayInGanZhi()}日"
        ),
    }


def clock_snapshot() -> dict[str, str]:
    dt = now_shanghai()
    lunar = _lunar_parts(dt)
    weekday = WEEKDAYS[dt.weekday()]
    return {
        "gregorian": f"{dt.year}年{dt.month}月{dt.day}日",
        "weekday": weekday,
        "hm": f"{dt.hour}点{dt.minute:02d}分",
        "hms": dt.strftime("%H:%M:%S"),
        "stamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
        **lunar,
    }


def current_time_notice() -> str:
    s = clock_snapshot()
    return (
        "【内部时钟，勿输出】"
        f"公历 {s['stamp']} {s['weekday']}；现在 {s['hm']}；农历 {s['ymd']}。"
        "用户问今天/现在/几点/农历时用这些字段，不要自行换算；没问则不要报时，不要复制本行。"
    )


def inject_time_into_system(system: str | None, *, user: str | None = None) -> str:
    _ = user
    notice = current_time_notice()
    text = (system or "").rstrip()
    return f"{text}\n\n{notice}" if text else notice


def inject_time_into_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out = [dict(m) for m in (messages or [])]
    if out and (out[0].get("role") or "") == "system":
        out[0]["content"] = inject_time_into_system(out[0].get("content") or "")
        return out
    out.insert(0, {"role": "system", "content": current_time_notice()})
    return out
