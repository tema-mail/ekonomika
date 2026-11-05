#!/usr/bin/env python3
"""Время по чатам Claude и Codex: сколько Артём потратил на команды и сколько работал Claude.
Запуск: python3 scripts/chaty.py [папка_проектов ...] > выход.json. Только чтение jsonl.
Claude: от реплики Артёма до последнего события перед его следующей репликой; паузы внутри хода режутся до 10 мин.
Артём (оценка): min(пауза до реплики, 1 мин чтения + длина реплики / 100 знаков в мин), не больше 15 мин на реплику."""
import datetime as dt, glob, json, os, re, sys

PAUZA = 600
MAX_ARTEM = 900
SLUZH = ("<command-", "<local-command", "<system-reminder", "<task-notification", "Caveat:", "<environment_context", "<user_instructions", "[Request interrupted", "<bash-", "Base directory for this skill")


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def tekst(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") in ("text", "input_text"))
    return ""


def nachat():
    return {"replik": 0, "znakov": 0, "artem": 0.0, "claude": 0.0}


def itog(day, dni, sek_a, sek_c, zn):
    d = dni.setdefault(day, nachat())
    d["replik"] += 1 if zn is not None else 0
    d["znakov"] += zn or 0
    d["artem"] += sek_a
    d["claude"] += sek_c


def den(t):
    return dt.datetime.fromtimestamp(t, dt.timezone(dt.timedelta(hours=7))).strftime("%Y-%m-%d")


def sessiya(path, gde):
    dni, nazv, cwd, prev, start, last = {}, "", "", None, None, None
    hod = 0.0
    def zakryt():
        nonlocal hod
        if start is not None and last is not None:
            itog(den(start), dni, 0, hod, None)
        hod = 0.0
    for l in open(path, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("type") == "custom-title" and e.get("customTitle"):
            nazv = e["customTitle"]
        elif e.get("type") == "ai-title" and e.get("aiTitle") and not nazv:
            nazv = e["aiTitle"]
        if e.get("isSidechain") or not e.get("timestamp") or e.get("type") not in ("user", "assistant"):
            continue
        cwd = cwd or e.get("cwd", "")
        t = ts(e["timestamp"])
        m = e.get("message") or {}
        tx = tekst(m.get("content")).strip() if e["type"] == "user" else ""
        zhivoy = e["type"] == "user" and tx and not e.get("isMeta") and not tx.startswith(SLUZH) and not (isinstance(m.get("content"), list) and any(x.get("type") == "tool_result" for x in m["content"] if isinstance(x, dict)))
        if zhivoy:
            zakryt()
            pauza = max(0.0, t - last) if last else 60.0
            a = min(pauza if pauza > 0 else 60.0, 60 + len(tx) / 100 * 60, MAX_ARTEM)
            itog(den(t), dni, a, 0, len(tx))
            start, last = t, t
        elif start is not None:
            hod += min(max(0.0, t - last), PAUZA)
            last = t
    zakryt()
    if not dni:
        return None
    return {"gde": gde, "id": os.path.basename(path)[:-6], "nazv": nazv, "cwd": cwd, "dni": dni}


def codex(path):
    dni, start, last, nazv, cwd, hod = {}, None, None, "", "", 0.0
    def zakryt():
        nonlocal hod
        if start is not None:
            itog(den(start), dni, 0, hod, None)
        hod = 0.0
    for l in open(path, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        p = e.get("payload") or {}
        if p.get("cwd") and not cwd:
            cwd = p["cwd"]
        if not e.get("timestamp"):
            continue
        t = ts(e["timestamp"])
        tx = tekst(p.get("content")).strip() if p.get("type") == "message" and p.get("role") == "user" else ""
        if tx and not tx.startswith(SLUZH):
            zakryt()
            nazv = nazv or tx[:70]
            pauza = max(0.0, t - last) if last else 60.0
            a = min(pauza if pauza > 0 else 60.0, 60 + len(tx) / 100 * 60, MAX_ARTEM)
            itog(den(t), dni, a, 0, len(tx))
            start, last = t, t
        elif start is not None:
            hod += min(max(0.0, t - last), PAUZA)
            last = t
    zakryt()
    return {"gde": "Codex", "id": os.path.basename(path)[:-6], "nazv": nazv, "cwd": cwd, "dni": dni} if dni else None


def main():
    out, H = [], os.path.expanduser("~")
    for a in sys.argv[1:] or [H + "/.claude/projects"]:
        gde = "VPS" if "vps" in a else "мак"
        for f in glob.glob(a + "/*/*.jsonl"):
            s = sessiya(f, gde)
            if s:
                out.append(s)
    for f in glob.glob(H + "/.codex/sessions/*/*/*/*.jsonl"):
        s = codex(f)
        if s:
            out.append(s)
    json.dump(out, sys.stdout, ensure_ascii=False)


main()
