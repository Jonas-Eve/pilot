#!/usr/bin/env python3
"""Fake data for the PILOT dashboard, so the template is developed against a demo artifact
("Cockpit pilot (démo)") and never against a real project's dashboard.

Usage:
  python3 scripts/demo_snapshot.py --out FILE        # the `snapshots/Jonas-Eve__pilot` document
  python3 scripts/demo_snapshot.py --dir DIR         # that document + a live session and a few events

Timestamps are relative to now, so re-run it to refresh the demo. Stdlib only.
"""
import argparse
import datetime
import json
import os

REPO = "Jonas-Eve/pilot"


def iso(hours_ago=0.0):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# (number, title, labels, hours since update, parent, [done, total] sub-issues, assignee, open PR)
def tickets():
    t = []

    def add(n, title, labels, h, p=None, k=None, a=None, r=None):
        t.append((n, title, labels, h, p, k, a, r))

    add(100, "Parcours voyageur accessible de bout en bout", ["type:feature", "level:epic"], 30, k=[3, 9])
    add(101, "Itinéraire sans escalier entre deux correspondances", ["type:feature", "level:story", "status:split", "priority:P1"], 6, 100, [1, 3])
    add(111, "Calcul de l'itinéraire sans escalier", ["type:feature", "level:task", "status:in-dev", "priority:P1"], 2, 101, None, "alice")
    add(112, "Écran de choix des contraintes", ["type:feature", "level:task", "status:review-ready", "priority:P1"], 5, 101, None, None, 61)
    add(113, "E2E : itinéraire sans escalier", ["type:e2e", "level:task", "status:dev-ready", "priority:P1"], 8, 101)
    add(102, "Alerte ascenseur en panne sur le trajet", ["type:feature", "level:story", "status:backlog", "priority:P0"], 20, 100)
    add(103, "Profil voyageur senior", ["type:feature", "level:story", "status:qa", "priority:P1"], 40, 100)
    add(104, "Notification de relais humain", ["type:feature", "level:story", "status:draft", "priority:P2"], 3, 100, None, "carol")
    add(200, "Plateforme multi-organisations", ["type:feature", "level:epic"], 70, k=[1, 4])
    add(201, "Inviter un administrateur dans son organisation", ["type:feature", "level:story", "status:split", "priority:P1"], 12, 200, [1, 2])
    add(211, "API d'invitation et jeton à usage unique", ["type:tech", "level:task", "status:changes-requested", "priority:P1"], 4, 201, None, None, 58)
    add(212, "Écran d'acceptation d'invitation", ["type:feature", "level:task", "status:in-review", "priority:P1"], 3, 201, None, "bob", 59)
    add(202, "Renommer son organisation", ["type:feature", "level:story", "status:in-qa", "priority:P2"], 50, 200, None, "bob")
    add(203, "Supprimer son organisation", ["type:feature", "level:story", "status:backlog", "priority:P2", "needs-human"], 90, 200)
    add(301, "Cache des états d'équipements", ["type:tech", "level:story", "status:in-spec", "priority:P1"], 7, None, None, "alice")
    add(302, "Migration du stockage des profils", ["type:tech", "level:story", "status:approved", "priority:P2"], 1, None, None, None, 60)
    add(303, "Tier-2 : source de credential déléguée", ["type:tech", "level:story", "status:backlog", "priority:P2", "on-hold"], 200)
    add(304, "Purge planifiée des comptes jamais confirmés", ["type:tech", "level:story", "status:dev-ready", "priority:P2"], 26)
    add(401, "Pictogramme PMR masqué en mode sombre", ["type:bug", "level:task", "status:dev-ready", "priority:P0"], 9)
    add(402, "Le jeton expiré n'est pas détecté", ["type:bug", "level:task", "status:backlog", "priority:P1"], 15)
    add(403, "Le flux s'interrompt si un message part pendant la réponse", ["type:bug", "level:task", "status:in-dev", "priority:P1", "needs-human"], 18, None, None, "carol")
    for i in range(24):
        status = ["backlog", "dev-ready", "review-ready", "backlog"][i % 4]
        labels = ["type:tech", "level:task", f"status:{status}", f"priority:P{(i % 3)}"]
        add(500 + i, f"Tâche technique d'exemple {i + 1}", labels, 24 + i * 5, None, None, None, 70 + i if status == "review-ready" else None)
    return t


def snapshot():
    rows = []
    for n, title, labels, hours, parent, k, assignee, pr in tickets():
        row = {"n": n, "t": title, "l": sorted(labels), "u": iso(hours)}
        if assignee:
            row["a"] = assignee
        if parent:
            row["p"] = parent
        if k:
            row["k"] = k
        if pr:
            row["r"] = pr
        rows.append(row)
    rows.sort(key=lambda r: r["u"], reverse=True)
    return {"repo": REPO, "at": iso(0.5), "source": "demo", "total": len(rows), "truncated": False, "issues": rows}


def live_documents():
    """A running session and the events a phase would have pushed, as `activity` / `events` documents."""
    return {
        "activity-dev-111": {"kind": "activity", "id": "dev-111-1", "phase": "dev", "n": 111,
                             "title": "Calcul de l'itinéraire sans escalier", "mode": "fresh", "auto": True,
                             "by": "alice", "startedAt": iso(0.4), "lastBeat": iso(0.02)},
        "activity-spec-301": {"kind": "activity", "id": "spec-301-1", "phase": "spec", "n": 301,
                              "title": "Cache des états d'équipements", "mode": "fresh", "auto": False,
                              "by": "alice", "startedAt": iso(2.5), "lastBeat": iso(1.8)},
        "event-111": {"kind": "ticket", "n": 111, "title": "Calcul de l'itinéraire sans escalier",
                      "labels": ["type:feature", "level:task", "status:in-dev", "priority:P1"],
                      "assignees": ["alice"], "state": "open", "action": "claim:fresh", "phase": "dev",
                      "by": "alice", "at": iso(0.4)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--dir")
    args = ap.parse_args()
    if not args.out and not args.dir:
        ap.error("--out or --dir is required")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(snapshot(), fh, ensure_ascii=False)
    if args.dir:
        os.makedirs(args.dir, exist_ok=True)
        with open(os.path.join(args.dir, "snapshot.json"), "w", encoding="utf-8") as fh:
            json.dump(snapshot(), fh, ensure_ascii=False)
        for name, doc in live_documents().items():
            with open(os.path.join(args.dir, name + ".json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)


if __name__ == "__main__":
    main()
