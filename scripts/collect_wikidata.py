#!/usr/bin/env python3
"""从 Wikidata 采集人物的亲属 / 配偶 / 伴侣关系，写入 data/wikidata.json。

- 不需要任何 API 密钥，只用 Python 标准库。
- 种子人物写在 collect/seeds.json；每次运行都会整份重新生成 data/wikidata.json（请勿手工修改它）。
- 只取 Wikidata 里有记载的关系：父亲、母亲、配偶、子女、兄弟姐妹、非婚伴侣。
- 不输出出生日期等个人信息；每条关系都带 Wikidata 来源链接。
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

API = "https://www.wikidata.org/w/api.php"
LANGS = ["zh-cn", "zh-hans", "zh", "zh-hk", "zh-tw", "zh-sg", "zh-mo", "en"]
PROPS = {"P22": "父亲", "P25": "母亲", "P26": "配偶", "P40": "子女", "P3373": "兄弟姐妹", "P451": "伴侣"}
MALE, FEMALE, HUMAN = "Q6581097", "Q6581072", "Q5"
SLEEP = 0.4


# ───────── 网络 ─────────
def http_get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    repo = os.environ.get("GITHUB_REPOSITORY", "local")
    req = urllib.request.Request(url, headers={
        "User-Agent": "RelationSphere/0.1 (https://github.com/%s; personal research project)" % repo})
    last = None
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            time.sleep(SLEEP)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except Exception as e:  # 网络抖动
            last = e
        time.sleep(2 * (i + 1))
    raise RuntimeError("请求 Wikidata 失败：%s" % last)


def get_entities(ids):
    """批量取实体（含 claims），返回 {id: entity}；不存在的实体不会出现在结果里。"""
    out, ids = {}, sorted(set(ids))
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = http_get({"action": "wbgetentities", "ids": "|".join(chunk), "format": "json",
                         "props": "labels|descriptions|aliases|claims", "languages": "|".join(LANGS)})
        for qid, e in (data.get("entities") or {}).items():
            if "missing" in e:
                continue
            out[qid] = e
            if e.get("id") and e["id"] != qid:      # 被合并/重定向的条目
                out[e["id"]] = e
    return out


# ───────── 解析 ─────────
def claim_items(entity, prop):
    """返回 [(目标Q号, claim)]，跳过"已弃用"和空值。"""
    res = []
    for c in (entity.get("claims") or {}).get(prop, []):
        if c.get("rank") == "deprecated":
            continue
        snak = c.get("mainsnak") or {}
        if snak.get("snaktype") != "value":
            continue
        v = (snak.get("datavalue") or {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            res.append((v["id"], c))
    return res


def item_ids(entity, prop):
    return [t for t, _ in claim_items(entity, prop)]


def is_human(e):
    return HUMAN in item_ids(e, "P31")


def gender(e):
    g = item_ids(e, "P21")
    return "m" if MALE in g else "f" if FEMALE in g else None


def label(e):
    labs = e.get("labels") or {}
    for lg in LANGS:
        if lg in labs and labs[lg].get("value"):
            return labs[lg]["value"]
    return e.get("id", "")


def description(e):
    ds = e.get("descriptions") or {}
    for lg in LANGS:
        if lg in ds and ds[lg].get("value"):
            return ds[lg]["value"]
    return ""


def aliases(e, name):
    seen, out = {name}, []
    cand = [v.get("value") for v in (e.get("labels") or {}).values()]
    for lg in LANGS:
        cand += [a.get("value") for a in (e.get("aliases") or {}).get(lg, [])]
    for a in cand:
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def fmt_time(claim, prop):
    """从 claim 的限定词里取时间，按精度输出 2008 / 2008-06 / 2008-06-18；精度不足或异常返回 None。"""
    for q in (claim.get("qualifiers") or {}).get(prop, []):
        if q.get("snaktype") != "value":
            continue
        v = (q.get("datavalue") or {}).get("value") or {}
        t, prec = v.get("time", ""), v.get("precision", 0)
        if not t.startswith("+") or prec < 9:
            continue
        y, m, d = t[1:].split("T")[0].split("-")
        if prec == 9:
            return y
        if prec == 10:
            return "%s-%s" % (y, m)
        return "%s-%s-%s" % (y, m, d)
    return None


ROLE_PARENT = {"m": "父亲", "f": "母亲", None: "父母"}
ROLE_CHILD = {"m": "儿子", "f": "女儿", None: "子女"}
ROLE_SPOUSE = {"m": "丈夫", "f": "妻子", None: "配偶"}
ROLE_SIB = {"m": "兄弟", "f": "姐妹", None: "兄弟姐妹"}


# ───────── 按人名查找 Q 号 ─────────
SEARCH_LANGS = ["zh", "zh-hans", "zh-hant", "zh-cn", "zh-hk", "zh-tw", "en"]


def search_name(name):
    seen, out = set(), []
    for lg in SEARCH_LANGS:
        try:
            data = http_get({"action": "wbsearchentities", "search": name, "language": lg, "uselang": lg,
                             "type": "item", "limit": 10, "format": "json"})
        except Exception:
            continue
        for r in data.get("search", []):
            if r.get("id") and r["id"] not in seen:
                seen.add(r["id"])
                out.append(r["id"])
    return out


def entity_text(e):
    parts = [v.get("value", "") for v in (e.get("labels") or {}).values()]
    parts += [v.get("value", "") for v in (e.get("descriptions") or {}).values()]
    for lst in (e.get("aliases") or {}).values():
        parts += [a.get("value", "") for a in lst]
    return " ".join(parts).lower()


def resolve_name(name, hint=None):
    """按名字找人物。返回 (候选人物 Q 号列表（最像的在前）, 实体字典)。hint 用来区分同名（如 "Tang"、"唐"）。"""
    ids = search_name(name)
    if not ids:
        raise SystemExit("在 Wikidata 找不到名为「%s」的条目，请换个写法，或直接写 Q 号" % name)
    ents = get_entities(ids[:30])
    humans = [q for q in ids if q in ents and is_human(ents[q])]
    if not humans:
        raise SystemExit("「%s」搜到的条目里没有人物，请换个写法，或直接写 Q 号" % name)
    if hint:
        pref = [q for q in humans if hint.lower() in entity_text(ents[q])]
        humans = pref + [q for q in humans if q not in pref]
    return humans, ents


# ───────── 采集 ─────────
def collect(seeds, depth, max_people):
    """返回 (entities, included, expanded)。
    depth=1：只取种子人物自己的关系；depth=2：再取他们的关系人的关系……
    最外层的人物只作为"占位节点"出现（有姓名，但不再展开他们的关系）。"""
    level = {s: 0 for s in seeds}
    ents = get_entities(list(seeds))
    for s in seeds:
        if s not in ents:
            raise SystemExit("找不到种子条目 %s，请检查 Q 号" % s)
        if not is_human(ents[s]):
            raise SystemExit("%s（%s）不是人物（instance of human），请检查 Q 号" % (s, label(ents[s])))
    frontier, capped = list(seeds), False
    for d in range(depth):
        nxt = []
        for qid in frontier:
            e = ents.get(qid)
            if not e or not is_human(e):
                continue
            for prop in PROPS:
                for t in item_ids(e, prop):
                    if t in level:
                        continue
                    if len(level) >= max_people:
                        capped = True
                        continue
                    level[t] = d + 1
                    nxt.append(t)
        need = [t for t in nxt if t not in ents]
        ents.update(get_entities(need))
        frontier = [t for t in nxt if t in ents and is_human(ents[t])]
    included = {q for q in level if q in ents and is_human(ents[q])}
    expanded = {q for q in included if level[q] < depth}
    return ents, included, expanded, capped


def build(ents, included, expanded):
    rels = {}

    def src_for(owner, prop):
        return {"title": "Wikidata：%s · %s（%s）" % (label(ents[owner]), PROPS[prop], prop),
                "url": "https://www.wikidata.org/wiki/%s#%s" % (owner, prop)}

    def add(a, b, typ, a_is, b_is, owner, prop, claim=None):
        key = (a, b, typ)
        r = rels.get(key)
        s = src_for(owner, prop)
        start = fmt_time(claim, "P580") if claim else None
        end = fmt_time(claim, "P582") if claim else None
        if r is None:
            r = rels[key] = {"a": a, "b": b, "type": typ, "aIs": a_is, "bIs": b_is, "src": [s], "_ended": []}
        elif s not in r["src"]:
            r["src"].append(s)
        r["_ended"].append(bool(end))
        if claim is not None and typ in ("spouse", "love"):
            ev = r.setdefault("events", [])
            if start:
                e1 = {"label": "结婚" if typ == "spouse" else "伴侣关系开始", "date": start, "src": s}
                if not any(x["label"] == e1["label"] and x["date"] == e1["date"] for x in ev):
                    ev.append(e1)
            if end:
                e2 = {"label": "关系结束", "date": end, "src": s}
                if not any(x["label"] == e2["label"] and x["date"] == e2["date"] for x in ev):
                    ev.append(e2)
            if end:
                r["to"] = end

    for q in sorted(expanded):
        e = ents[q]
        gq = gender(e)
        for prop in PROPS:
            for t, c in claim_items(e, prop):
                if t not in included or t == q:
                    continue
                gt = gender(ents[t])
                if prop == "P22" or prop == "P25":      # t 是 q 的父/母
                    role = ROLE_PARENT[gt] if gt else ("父亲" if prop == "P22" else "母亲")
                    add(t, q, "kin", role, ROLE_CHILD[gq], q, prop)
                elif prop == "P40":                     # t 是 q 的子女
                    add(q, t, "kin", ROLE_PARENT[gq], ROLE_CHILD[gt], q, prop)
                elif prop == "P26":
                    a, b = sorted((q, t))
                    ga, gb = (gq, gt) if a == q else (gt, gq)
                    add(a, b, "spouse", ROLE_SPOUSE[ga], ROLE_SPOUSE[gb], q, prop, c)
                elif prop == "P451":
                    a, b = sorted((q, t))
                    add(a, b, "love", "伴侣", "伴侣", q, prop, c)
                elif prop == "P3373":
                    a, b = sorted((q, t))
                    ga, gb = (gq, gt) if a == q else (gt, gq)
                    add(a, b, "kin", ROLE_SIB[ga], ROLE_SIB[gb], q, prop)
    out = []
    for key in sorted(rels):
        r = rels[key]
        ended = r.pop("_ended")
        if ended and all(ended):
            r["status"] = "past"
        else:
            r.pop("to", None)           # 只要有一条记录没有结束时间，就按"现在仍有效"处理
        if not r.get("events"):
            r.pop("events", None)
        out.append(r)
    return out


def people_list(ents, included):
    out = []
    for q in sorted(included, key=lambda x: int(x[1:])):
        e = ents[q]
        name = label(e)
        p = {"id": q, "name": name, "wikidata": q}
        al = aliases(e, name)
        if al:
            p["alias"] = al[:8]
        d = description(e)
        if d:
            p["note"] = d
        out.append(p)
    return out


# ───────── 与手写数据的重复检查 ─────────
def find_duplicates(people, data_dir, index):
    dups, hand = [], []
    for f in index.get("files", []):
        if f == "wikidata.json":
            continue
        try:
            doc = json.load(open(os.path.join(data_dir, f), encoding="utf-8"))
        except Exception:
            continue
        for h in doc.get("people", []):
            hand.append((f, h))
    for p in people:
        names = {p["name"].lower(), *[a.lower() for a in p.get("alias", [])]}
        for f, h in hand:
            if h.get("wikidata") == p["wikidata"]:
                continue
            hn = {h["name"].lower(), *[a.lower() for a in h.get("alias", [])]}
            if names & hn:
                dups.append((p, f, h))
    return dups


def apply_names(cfg, text):
    """把 Actions 页面里填的人名（逗号、顿号、换行分隔）追加进种子列表；已有的不重复添加。返回新增的名字。"""
    import re
    names = [n.strip() for n in re.split(r"[,，、;；\n]+", text or "") if n.strip()]
    have = set()
    for s in cfg.get("seeds", []):
        if isinstance(s, str):
            have.add(s.lower())
        else:
            have.update(str(s.get(k, "")).lower() for k in ("name", "qid"))
    added = []
    for n in names:
        if n.lower() not in have:
            cfg.setdefault("seeds", []).append(n)
            have.add(n.lower())
            added.append(n)
    return added


def main():
    root = os.environ.get("ROOT", ".")
    seeds_path = os.path.join(root, "collect", "seeds.json")
    cfg = json.load(open(seeds_path, encoding="utf-8"))
    added = apply_names(cfg, os.environ.get("NAMES", ""))
    if added:      # 写回 seeds.json，这样新加的人会随这次提交保存下来
        with open(seeds_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("本次新增种子：" + "、".join(added))
    depth = int(cfg.get("depth", 1))
    max_people = int(cfg.get("max_people", 150))
    seeds, expects, matched = [], {}, []
    for s in cfg["seeds"]:
        item = {"qid": s} if isinstance(s, str) and s[:1] == "Q" and s[1:].isdigit() else \
               {"name": s} if isinstance(s, str) else dict(s)
        if not item.get("qid"):
            humans, rents = resolve_name(item["name"], item.get("hint"))
            item["qid"] = humans[0]
            matched.append((item["name"], humans[0], humans[1:5], rents))
        if item["qid"] not in seeds:
            seeds.append(item["qid"])
        if item.get("expect"):
            expects[item["qid"]] = item["expect"]
    ents, included, expanded, capped = collect(seeds, depth, max_people)

    for q, ex in expects.items():
        e = ents[q]
        names = [label(e)] + aliases(e, label(e))
        if not any(ex.lower() in n.lower() for n in names):
            raise SystemExit("种子 %s 的名字是「%s」，与预期的「%s」不符，请检查 Q 号" % (q, label(e), ex))

    people = people_list(ents, included)
    relations = build(ents, included, expanded)
    doc = {"meta": {"name": "Wikidata 自动采集（机器生成，请勿手工修改）", "generated_by": "scripts/collect_wikidata.py",
                    "seeds": seeds, "depth": depth,
                    "src": {"title": "Wikidata", "url": "https://www.wikidata.org"}},
           "people": people, "relations": relations}
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "wikidata.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")

    idx_path = os.path.join(data_dir, "index.json")
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {"files": []}
    if "wikidata.json" not in index["files"]:
        index["files"].append("wikidata.json")
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=1)
            f.write("\n")

    dups = find_duplicates(people, data_dir, index)
    lines = ["## Wikidata 自动采集结果", "",
             "- 种子：%s；展开层数：%d" % ("、".join("%s（%s）" % (label(ents[s]), s) for s in seeds), depth),
             "- 人物 %d 人，关系 %d 条（边缘人物 %d 人只含与里层人物的关系）" % (len(people), len(relations), len(included) - len(expanded))]
    if capped:
        lines.append("- ⚠️ 已达人数上限 %d，部分关系人未收录（可调大 collect/seeds.json 的 max_people）" % max_people)
    lines += ["", "### 合并前请检查", "- 请抽查几条关系，点开来源链接核对。",
              "- 本文件只含 Wikidata 已有的亲属、配偶、伴侣；感情传闻、合作关系等仍需手写数据。"]
    if matched:
        lines += ["", "### ⚠️ 以下人物是按名字自动匹配的，请核对是不是你要的人"]
        for name, q, others, rents in matched:
            d = description(rents[q]) if q in rents else ""
            lines.append("- 「%s」→ **%s**（%s）%s" % (name, label(rents[q]) if q in rents else q, q, "：" + d if d else ""))
            for o in others:
                od = description(rents[o])
                lines.append("  - 其他同名候选：%s（%s）%s" % (label(rents[o]), o, "：" + od if od else ""))
        lines.append("- 确认无误后，把 `collect/seeds.json` 里对应的写法改成 `{ \"qid\": \"Q号\" }` 固定下来；匹配错了就写上 `hint` 或直接写 Q 号。")
        lines.append("- 含有按名字匹配的人物时，即使打开了 auto_merge 也不会自动合并。")
    if dups:
        lines += ["", "### 可能与手写数据重复的人物", "名字相同但 id 不同，页面上会显示成两个人。若确认是同一人，请在对应手写数据里补上 `wikidata` 字段，页面会自动合并："]
        for p, f, h in dups:
            lines.append("- `data/%s` 里的 `%s`（%s）≈ %s（%s）→ 加上 `\"wikidata\": \"%s\"`" % (f, h["id"], h["name"], p["name"], p["wikidata"], p["wikidata"]))
    report = "\n".join(lines) + "\n"
    print(report)
    flag = os.path.join(root, "collect_review.flag")
    if matched:
        open(flag, "w", encoding="utf-8").write("name-matched seeds\n")
    elif os.path.exists(flag):
        os.remove(flag)
    rp = os.environ.get("REPORT")
    if rp:
        open(rp, "w", encoding="utf-8").write(report)


if __name__ == "__main__":
    main()
