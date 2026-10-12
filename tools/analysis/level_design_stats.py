#!/usr/bin/env python3
"""level_design_stats — quantify reuse of generic shells/systems across level (ss-<level>/) state scripts.
Run from repo root: python3 -I tools/analysis/level_design_stats.py"""
import json, collections, re, os
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
S = json.load(open(os.path.join(REPO, "databases", "state_scripts.json")))
GENERIC_DIRS = {"ss-t2", "ss", "ss-fx", "ss-hud2", "ss-test", "ss-t2r-test", "ss-tool", "ss-main-menu", "ss-rogue"}
def level_of(f):
    d = f.split("/")[0]
    return d if d.startswith("ss-") and d not in GENERIC_DIRS else None
tot = collections.Counter(); per_level = collections.defaultdict(collections.Counter)
state_names = collections.Counter(); calls = collections.Counter(); shells = collections.Counter()
nlevel = 0
for k, v in S.items():
    lv = level_of(v["file"])
    if not lv: continue
    nlevel += 1
    st = set(v["states"]); allcalls = set(); evs = set()
    for s in v["states"].values():
        allcalls.update(s["calls"])
        for b in s["blocks"]:
            if b.get("event"): evs.add(b["event"])
    for s in st: state_names[s] += 1
    for c in allcalls: calls[c] += 1
    feats = {
        "task-check-state": "task-check" in st,
        "already-complete-state": "already-complete" in st,
        "complete-or-done-state": bool(st & {"complete", "done"}),
        "handles-player-requested-interact": "player-requested-interact" in evs,
        "handles-task-complete-event": "task-complete" in evs,
        "calls-task-complete?": "task-complete?" in allcalls,
        "calls-task-active?": "task-active?" in allcalls,
        "calls-task-complete!": bool(allcalls & {"task-complete!", "task-complete-if-active!"}),
        "calls-override-interact-def": "override-interact-def" in allcalls,
        "calls-spawn-script": bool(allcalls & {"spawn-script", "spawn-script-with-parent", "spawn-script-at"}),
        "calls-set-svar*": bool(allcalls & {"set-svar", "set-svar-as-boolean", "set-svar-bit", "increment-svar"}),
        "calls-get-svar*": bool(allcalls & {"get-svar", "get-svar-as-boolean", "get-svar-bit"}),
        "calls-fact-set": "fact-set" in allcalls,
        "calls-animate-done": "animate-done" in allcalls,
        "calls-interactable-disable/enable": bool(allcalls & {"interactable-disable", "interactable-enable"}),
        "calls-camera-enable-animated": "camera-enable-animated" in allcalls,
        "calls-wait-player-move-to-entry": "wait-player-move-to-entry" in allcalls,
        "calls-script-caption": bool(allcalls & {"wait-script-caption", "script-caption"}),
        "calls-set-combat-checkpoint": "set-combat-checkpoint" in allcalls,
    }
    for f, b in feats.items():
        if b: tot[f] += 1; per_level[lv][f] += 1
    per_level[lv]["_scripts"] += 1
    shell = ("TC" if feats["task-check-state"] else "") + ("+PRI" if feats["handles-player-requested-interact"] else "") + ("+DONE!" if feats["calls-task-complete!"] else "") + ("+AC" if feats["already-complete-state"] else "")
    shells[shell] += 1
out = {"level_scripts": nlevel, "feature_counts": dict(tot.most_common()), "top_state_names": state_names.most_common(40),
       "shell_signatures": shells.most_common(20), "per_level": {k: dict(v) for k, v in sorted(per_level.items())}}
print(json.dumps(out, indent=1))
