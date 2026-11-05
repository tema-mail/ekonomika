#!/usr/bin/env python3
"""Сводит время из чатов, журнал часов и платежи ДДС в src/data/ekonomika.json. Запуск: python3 scripts/sobrat.py chaty.json dds.csv"""
import collections, csv, datetime as dt, json, os, re, sys

C = os.path.expanduser("~/.config/product-lead/")
e = json.load(open(C + "ekonomika.json", encoding="utf-8"))
PR = json.load(open(C + "proekty.json", encoding="utf-8"))
ZH = json.load(open(C + "zhurnal-chasov.json", encoding="utf-8"))
chaty = json.load(open(sys.argv[1], encoding="utf-8"))
MES = {"Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12}


def novyy(p):
    return {"name": p["name"], "gruppa": p.get("gruppa"), "artem": 0.0, "claude": 0.0, "replik": 0, "chatov": 0, "komanda": 0.0, "vyruchka": 0}


R = {p["name"]: novyy(p) for p in PR}
R["Без проекта"] = novyy({"name": "Без проекта"})
mes = collections.defaultdict(lambda: {"artem": 0.0, "claude": 0.0, "replik": 0})
gde = collections.Counter()
bez = []
for s in chaty:
    t = (s.get("nazv") or "") + " " + os.path.basename(s.get("cwd") or "")
    r = next((R[p["name"]] for p in PR if re.search(p["chaty"], t, re.I)), R["Без проекта"])
    a = c = 0.0
    for d, v in s["dni"].items():
        a += v["artem"] / 3600
        c += v["claude"] / 3600
        r["replik"] += v["replik"]
        m = mes[d[:7]]
        m["artem"] += v["artem"] / 3600
        m["claude"] += v["claude"] / 3600
        m["replik"] += v["replik"]
    r["artem"] += a
    r["claude"] += c
    r["chatov"] += 1
    gde[s["gde"]] += 1
    if r["name"] == "Без проекта":
        bez.append({"nazv": s.get("nazv") or "без названия", "artem": round(a, 1), "claude": round(c, 1)})
for p in PR:
    R[p["name"]]["komanda"] = sum(ZH["proekty"].get(z, 0) for z in p["zhurnal"])

# Платежи ДДС 2026 с июня, как и журнал часов; строки без контрагента – сводки
rows = list(csv.reader(open(sys.argv[2], encoding="utf-8")))
start = next(i for i, x in enumerate(rows) if x and x[0].strip() == "2026")
cur, plat = None, []
for x in rows[start:]:
    x = x + [""] * 5
    if x[1].strip() in MES:
        cur = MES[x[1].strip()]
        continue
    s = re.sub(r"[^\d\-]", "", x[2])
    if cur and cur >= 6 and x[3].strip() and re.fullmatch(r"\d+", s):
        plat.append((x[3].strip(), int(s)))
servis = sum(n for w, n in plat if re.search(r"^сервис\b|^ev\b", w, re.I))
for p in PR:
    if p["dds"]:
        R[p["name"]]["vyruchka"] = sum(n for w, n in plat if re.search(p["dds"], w, re.I))

ch, mn = e["chas_polnyy"], e["chas_prodazhi_min"]
def stroka(r):
    h = r["artem"] + r["komanda"]
    r["chasy"] = round(h, 1)
    r["sebest"] = round(h * ch)
    r["minimum"] = round(h * mn)
    r["rub_chas"] = round(r["vyruchka"] / h) if r["vyruchka"] and h else None
    for k in ("artem", "claude", "komanda"):
        r[k] = round(r[k], 1)
    return r
sv = novyy({"name": "Сервис всего (EV Sibir и TEYES Sibir)"})
for r in R.values():
    if r["gruppa"] == "Сервис":
        for k in ("artem", "claude", "replik", "chatov", "komanda"):
            sv[k] += r[k]
sv["vyruchka"] = servis
proekty = sorted((stroka(r) for r in list(R.values()) + [sv]), key=lambda r: -(r["chasy"] + r["claude"]))
out = {
    "sobrano": dt.datetime.now().strftime("%d.%m.%Y %H:%M"), "chas": ch, "minimum_chas": mn, "nalog": e["nalog"], "podpiski_mes": e.get("podpiski_mes", 12500),
    "zhurnal_snyat": ZH["snyato"], "pervyy_den": min(d for s in chaty for d in s["dni"]), "gde": dict(gde), "proekty": proekty,
    "mesyatsy": [{"mes": k, **{a: round(b, 1) for a, b in v.items()}} for k, v in sorted(mes.items())],
    "tipy": ZH["tipy"], "komanda_vsego": ZH["vsego"], "tarify": e["obsluzhivanie"]["tarify"], "chas_sverh": e["obsluzhivanie"]["chas_sverh"],
    "klassy": [{"nazv": v["nazv"], "chasy": round(v["chasy_komandy"] + v["chasy_artema"], 1), "sebest": round((v["chasy_komandy"] + v["chasy_artema"]) * ch + v["ii_rub"]), "minimum": round((v["chasy_komandy"] + v["chasy_artema"]) * mn + v["ii_rub"] / (1 - e["nalog"])), "status": v["status"]} for v in e["klassy"].values()],
    "bez_proekta": sorted((b for b in bez if b["artem"] + b["claude"] >= 0.1), key=lambda x: -(x["artem"] + x["claude"]))[:15],
}
os.makedirs("src/data", exist_ok=True)
json.dump(out, open("src/data/ekonomika.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("чатов", len(chaty), dict(gde), "| без проекта", len(bez), "| Сервис платежи", servis)
