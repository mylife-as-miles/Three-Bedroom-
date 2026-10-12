#!/usr/bin/env python3
"""animation_keytable — aggregate optarrays.jsonl.gz (from animation_optkeys.py) into the animate_ option-key table
(counts, value types, top values, named-variable evidence) merged with hand-assigned labels.

Usage: python3 -I tools/analysis/animation_keytable.py <optarrays.jsonl.gz> <out.json>
"""
import gzip, json, re, sys, collections

LABELS = {
 0: ("flag-0 (u8)", "UNKNOWN", "NPC IGC mostly; co-occurs with 36/20/24"),
 1: ("flag-1 (u8)", "UNKNOWN", "player+NPC; co-occurs with 2/3/4; set by drawer/cabinet/safe player anims"),
 2: ("flag-2 (u8)", "UNKNOWN", "co-occurs with 1/3/4"),
 3: ("flag-3 (u8)", "UNKNOWN", "357 uses; co-occurs with 1/4/5; drawer/cabinet player anims"),
 4: ("flag-4 (u8)", "UNKNOWN", "co-occurs with 2/3/51"),
 5: ("flag-5 (u8)", "UNKNOWN", "player-only; drawer/cabinet set 5+87 together"),
 6: ("flag-6 (u8)", "UNKNOWN", "NPC; vehicle passengers"),
 7: ("flag-7 (u8)", "UNKNOWN", "vehicle/turret/bipod contexts (with 49/70/71/85)"),
 9: ("flag-9 (u8)", "UNKNOWN", "cinematic contexts"),
 10: ("ap-ref (align bound-frame / locator)", "CONFIRMED", "values are get-spawner-locator/get-bound-frame/get-object-locator; wrapper animate-start(obj,anim,locator,...)"),
 12: ("camera mode (i32 enum)", "HIGH", "squeeze-through passes gap-dodge-camera-mode(); drawer passes camera-required-low? (1/0); boat 9"),
 13: ("collision / ground mode (i32 enum 0/2/3/5)", "INFERRED", "ss-examine: 2 if tag collision-ground? else 0; anim-npc has s_script-full-body-*-collide states"),
 14: ("ap-ref channel name", "CONFIRMED", "values apReference-*, car, humvee, boat-AP-ref"),
 20: ("end frame (f32, frames)", "HIGH", "abort-frame, bow-swap-frame, med-ratking-squeeze-get-end-frame(); npc-move-to-start-in-motion: 18+fade*30"),
 22: ("end phase (f32 0..1)", "HIGH", "end-phase-for-first-anim; typical 0.5-0.95"),
 24: ("exit mode (i32 enum)", "HIGH (name) / INFERRED (values)", "squeeze-through passes gap-dodge-exit-mode(); var exit-mode; drawer: 18 if crouch else 1"),
 25: ("reference object (u64)", "UNKNOWN", "1 use: drawer scavenge-exit passes current-interactable-scav"),
 27: ("fade-in curve (u8 enum or curve symbol)", "HIGH", "get-curve-type(); uniform-s/ease-in symbols; paired with 28 in code order"),
 28: ("fade-in / blend-in seconds", "CONFIRMED", "blend-to-exit-2, fade-in-time, blend-time vars; simple-animate(obj,anim,spawner,fade-in,fade-out)"),
 29: ("fade-out curve (u8 enum or curve symbol)", "HIGH", "animate-fade-out sets 29=arg next to 30; ease-out symbol"),
 30: ("fade-out / blend-out seconds", "CONFIRMED", "blend-from-exit, anim-exit-fade-out, selection-fade-out-duration vars"),
 31: ("loop", "CONFIRMED", "tag loop-idle?, idle-force-loop; player-script has s_script-*-loop state variants"),
 32: ("flag-32 (u8)", "UNKNOWN", "261 uses; with 56 speed in stub-igc / bindpose / safe dial"),
 34: ("flag-34 (u8)", "UNKNOWN", "value sometimes object-anim-playing?(...)"),
 35: ("hand-IK mode? (i32 enum)", "INFERRED", "strong co-occurrence with 37/38 hand ap-refs"),
 36: ("flag-36 (i32 0/1)", "UNKNOWN", "rare"),
 37: ("left-hand ap-ref channel", "HIGH", "apReference-hand-l*, ap-Ref-*-hand-l, handle_ik_l_pull"),
 38: ("right-hand ap-ref channel", "HIGH", "apReference-hand-r*"),
 40: ("layer type (i32; 1 = partial/gesture layer)", "HIGH", "get-layer-type(); always with 41/75 on partial anims; animate-done(obj,anim,loc,layer,...)"),
 41: ("target script layer state name", "CONFIRMED", "values s_script-gesture-0..3 / s_script-gesture-add-0..1 = state names in anim-player/player-script.bin"),
 42: ("layer / pair blend weight (f32)", "INFERRED", "pickup-anim-pair-weight"),
 43: ("look / overlay gesture anim", "HIGH", "tag look-gesture; *-gesture anims; player-script *-gesture states contain anim-node-gesture"),
 44: ("mirror", "CONFIRMED", "mirror?, mirror, left-side, mirror-anim"),
 45: ("motion (root) blend time? (f32)", "INFERRED", "blend-in-sec-from-gate-enter, get-player-speed()/get-animation-speed() based values"),
 46: ("motion blend-out? (f32)", "UNKNOWN", "11 uses"),
 49: ("flag-49 (u8)", "UNKNOWN", "63 uses, NPC/vehicle"),
 56: ("playback speed", "CONFIRMED", "animation-speed, speed-pct, anim-speed; animate-start/done pass 0.0 = hold pose; -1.0 = reverse"),
 57: ("start frame", "CONFIRMED", "start-frame, tasked-in-start-frame vars; get-animation-frame(other) for sync"),
 58: ("start phase", "CONFIRMED", "get-animation-phase(), get-best-entry-phase(); animate-done passes 1.0"),
 59: ("i32 0..5 (start/phase mode?)", "UNKNOWN", "animate-start/animate-done pass 0; squeeze/ledge pass 1"),
 60: ("stick-abort fade seconds", "CONFIRMED", "blend-from-exit-stick-abort-fade-sec, stick-abort-fade-sec"),
 61: ("stick-abort frame (i32)", "CONFIRMED", "blend-from-exit-stick-abort-frame, stick-abort-frame, abort-frame"),
 70: ("i32 enum (player IGC)", "UNKNOWN", "co-occurs with 71/72; player-stumble 10, workbench-exit 10"),
 71: ("i32 enum (player IGC)", "UNKNOWN", "co-occurs with 70/72"),
 72: ("flag-72 (u8)", "UNKNOWN", ""),
 75: ("joint / blend mask set (symbol)", "HIGH", "*upperbody--left-hard--right-hard--fb*, *scav-drawer-exit-l-hand*"),
 78: ("i32 enum (NPC)", "UNKNOWN", ""),
 82: ("sync/continue flag (u8)", "INFERRED", "co-occurs with 57 start-frame copied from another object (lift 11x); var start-fresh?"),
 83: ("horse binding", "CONFIRMED", "alloc-horse-binding(), *-horse-binding symbols"),
 85: ("animated-camera id/name", "HIGH", "workbench animates a spawned 'workbench-camera' with 85=workbench-enter, later camera-fade-out(workbench-enter,...)"),
 87: ("flag-87 (u8)", "UNKNOWN", "only drawer/cabinet/keypad/npc-begs"),
}


def main():
    src, out = sys.argv[1], sys.argv[2]
    R = [json.loads(l) for l in gzip.open(src, "rt", encoding="utf-8")]
    per = collections.defaultdict(lambda: {"count": 0, "types": collections.Counter(), "values": collections.Counter(),
                                           "names": collections.Counter(), "funcs": collections.Counter(), "targets": collections.Counter()})
    for r in R:
        tgt = "player" if r["args"][0] == "player" else ("self" if "self" in r["args"][0] else "other")
        for k, t, v in r["pairs"]:
            d = per[k]; d["count"] += 1; d["types"][t or "?"] += 1; d["funcs"][r["func"]] += 1; d["targets"][tgt] += 1
            v = v or ""
            if re.fullmatch(r"-?[\d.]+", v) or re.fullmatch(r"[\w\-*]+", v):
                d["values"][v[:48]] += 1
            else:
                d["values"]["<expr>"] += 1
            for m in re.finditer(r"(?:get|tag)-(?:float|int32|boolean|symbol)\(([\w\-?!*]+)", v):
                d["names"]["var:" + m.group(1)] += 1
            for m in re.finditer(r"([\w\-?!*>]+)\(", v):
                if not re.match(r"(get|tag)-(float|int32|boolean|symbol)$", m.group(1)):
                    d["names"]["fn:" + m.group(1)] += 1
    keys = []
    for k in sorted(per):
        d = per[k]
        lab = LABELS.get(k, ("rare (u8/f32)", "UNKNOWN", ""))
        keys.append({"key": k, "meaning": lab[0], "confidence": lab[1], "evidence": lab[2], "count": d["count"],
                     "value_types": dict(d["types"]), "top_values": d["values"].most_common(10),
                     "named_sources": d["names"].most_common(8), "consumer": dict(d["funcs"]), "target_kind": dict(d["targets"])})
    res = {"source": "dconstruct .dcpl, every #%alloc-array(single-frame,16,N,1) consumed by animate_/wait-animate_",
           "records": len(R), "consumers": dict(collections.Counter(r["func"] for r in R)),
           "pairs_per_call": dict(sorted(collections.Counter(len(r["pairs"]) for r in R).items())),
           "native_param_type": "ssAnimateParams (dconstruct boxed-type table)",
           "keys": keys}
    json.dump(res, open(out, "w"), indent=1)
    print(len(keys), "keys")


if __name__ == "__main__":
    main()
