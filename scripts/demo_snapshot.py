#!/usr/bin/env python3
"""Fake data for the PILOT dashboard, so the template is developed against a demo artifact
("Cockpit pilot (démo)") and never against a real project's dashboard.

Usage:
  python3 scripts/demo_snapshot.py --out FILE        # the `snapshots/Jonas-Eve__pilot` document
  python3 scripts/demo_snapshot.py --dir DIR         # that document + a live session, a few events, a design document, a wiki document and prototypes

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
    add(701, "Itinéraire sans escalier : choisir ses contraintes", ["type:poc", "level:story", "status:poc-draft"], 2, None, None, "alice")
    add(702, "Alerte ascenseur en panne sur le trajet", ["type:poc", "level:story", "status:poc-review"], 5)
    add(703, "Relais humain depuis l'application", ["type:poc", "level:story", "status:poc-validated"], 30)
    add(704, "Profil voyageur senior", ["type:poc", "level:story", "status:poc-validated"], 48)
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
        "event-600": {"kind": "ticket", "n": 600, "title": "Tâche créée par un split depuis le dernier instantané",
                      "labels": ["type:feature", "level:task", "status:dev-ready", "priority:P1"],
                      "assignees": [], "state": "open", "action": "created", "phase": "spec", "parent": 101,
                      "by": "alice", "at": iso(0.2)},
        "event-105": {"kind": "ticket", "n": 105, "title": "Story approuvée en Discovery",
                      "labels": ["type:feature", "level:story", "status:backlog", "priority:P1"],
                      "assignees": [], "state": "open", "action": "approved", "phase": "discovery", "parent": 100,
                      "by": "carol", "at": iso(0.1)},
        "event-111": {"kind": "ticket", "n": 111, "title": "Calcul de l'itinéraire sans escalier",
                      "labels": ["type:feature", "level:task", "status:in-dev", "priority:P1"],
                      "assignees": ["alice"], "state": "open", "action": "claim:fresh", "phase": "dev",
                      "by": "alice", "at": iso(0.4)},
    }


def design_document():
    """The `design/Jonas-Eve__pilot` document a /pilot-design session would have written."""
    return {
        "kind": "design", "repo": REPO, "at": iso(5),
        "charter": {
            "name": "Cockpit pilot (démo)", "summary": "Un cockpit sobre et lisible, pensé pour voyager sans obstacle.",
            "colors": [{"name": "Cobalt", "hex": "#1747C9", "use": "Actions principales et liens"},
                       {"name": "Papier", "hex": "#F2F5F8", "use": "Fond de page"}],
            "voice": "Clair, direct et bienveillant. Jamais de jargon.",
            "rules": "Un seul bouton principal par écran. Pas de texte blanc sur fond clair.",
        },
        "colors": [{"name": "Fond", "light": "#F2F5F8", "dark": "#0E141B", "use": "Arrière-plan de page"},
                   {"name": "Action", "light": "#1747C9", "dark": "#7EA2FF", "use": "Boutons et liens"},
                   {"name": "Succès", "light": "#17803D", "dark": "#4CC27A", "use": "État validé"},
                   {"name": "Alerte", "light": "#B42318", "dark": "#FF8B7E", "use": "Erreur, équipement en panne"}],
        "type": {"family": "IBM Plex Sans", "scale": [
            {"name": "Titre", "size": 22, "weight": 600, "use": "Titre de page"},
            {"name": "Corps", "size": 14, "weight": 400, "use": "Texte courant"},
            {"name": "Note", "size": 12, "weight": 400, "use": "Aide et mentions"}]},
        "space": {"spacing": [{"name": "s", "value": "8px"}, {"name": "m", "value": "16px"}, {"name": "l", "value": "24px"}],
                  "radius": [{"name": "s", "value": "8px"}, {"name": "m", "value": "12px"}]},
        "components": [{"name": "Bouton", "description": "Action principale ou secondaire.",
                        "rules": "Cible d'au moins 44 px, libellé à l'infinitif.", "height": 70,
                        "preview": "<button style=\"min-height:44px;padding:0 16px;border:0;border-radius:var(--radius-s);background:var(--color-action);color:#fff;font:inherit\">Démarrer</button>"},
                       {"name": "Carte de trajet", "description": "Résume un itinéraire et son accessibilité.",
                        "rules": "L'accessibilité s'affiche en texte, jamais par la couleur seule.", "height": 110,
                        "preview": "<div style=\"border:1px solid var(--color-action);border-radius:var(--radius-m);padding:var(--space-m)\"><b>Gare du Nord → Châtelet</b><br>3 correspondances accessibles<br><span style=\"color:var(--color-succes)\">Ascenseurs en service</span></div>"}],
        "a11y": ["Contraste AA minimum (4,5:1) dans les deux thèmes.",
                 "Navigation complète au clavier, focus toujours visible.",
                 "Aucune information portée par la couleur seule."],
    }


PROTO_HTML = """<!doctype html><meta charset=utf8><title>Alerte ascenseur</title>
<style>body{margin:0;font:16px system-ui;background:#F2F5F8;color:#121C26;padding:16px}.card{background:#fff;border:1px solid #D5DDE5;border-radius:12px;padding:14px;max-width:420px}
button{min-height:44px;padding:0 16px;border:0;border-radius:8px;background:#1747C9;color:#fff;font:inherit;margin-top:10px}.ko{color:#B42318;font-weight:600}.ok{color:#17803D;font-weight:600}</style>
<div class=card><b>Gare du Nord → Châtelet</b><p id=s class=ko>Ascenseur du quai 4 en panne</p>
<p id=alt hidden>Itinéraire de remplacement : 2 correspondances, sans escalier. <span class=ok>Prévenu 3 min avant l'arrivée.</span></p>
<button id=b>Voir l'itinéraire de remplacement</button></div>
<script>document.getElementById("b").onclick=function(){document.getElementById("alt").hidden=false;this.hidden=true}</script>"""


PROTO_SENIOR = """<!doctype html><meta charset=utf8><title>Profil senior</title>
<style>body{margin:0;font:16px system-ui;background:#F2F5F8;color:#121C26;padding:16px}.card{background:#fff;border:1px solid #D5DDE5;border-radius:12px;padding:14px;max-width:420px}
body.big{font-size:22px}button{min-height:48px;padding:0 18px;border:0;border-radius:8px;background:#1747C9;color:#fff;font:inherit}</style>
<div class=card><b>Mon trajet</b><p>Prochain départ : 14h32, quai 2, sans escalier.</p><button id=b>Agrandir les textes</button></div>
<script>document.getElementById("b").onclick=function(){document.body.classList.toggle("big")}</script>"""


def wiki_document():
    """The `wiki/Jonas-Eve__pilot` document `pilot.py wiki snapshot` would have written."""
    def entry(eid, title, path, status, derived, tickets, verified, text):
        shown = status + (" · " + derived if derived else "")
        return {"id": eid, "title": title, "description": text.split(".")[0] + ".", "path": path, "status": status,
                "derived": derived, "display": shown, "tickets": tickets,
                "verifiedAt": iso(verified) if verified else "", "text": text}
    entries = [
        entry("search-by-name", "Rechercher un lieu par son nom", "recherche/search-by-name.md", "implemented", "verified", [1], 40,
              "On cherche un lieu par une partie de son nom, sans tenir compte des majuscules."),
        entry("filter-step-free", "Filtrer sur l'accès de plain-pied", "recherche/filter-step-free.md", "implemented", "", [2], 40,
              "Avec l'option, seuls les lieux dont l'accès de plain-pied est confirmé sont proposés."),
        entry("sort-by-distance", "Trier par distance, le plus proche d'abord", "recherche/sort-by-distance.md", "implemented", "", [3], 0,
              "Les résultats sont triés du plus proche au plus éloigné."),
        entry("km-display", "Afficher les longues distances en km", "affichage/km-display.md", "specified", "in-review", [12, 14], 0,
              "Une distance de 1000 m ou plus est affichée en kilomètres avec une décimale."),
        entry("csv-export", "Exporter le résultat en CSV", "export/csv-export.md", "proposed", "", [4], 0,
              "Une option affiche le résultat en CSV avec une ligne d'en-tête."),
    ]
    return {"kind": "wiki", "repo": REPO, "at": iso(3), "total": len(entries), "truncated": False, "entries": entries}


def small_mock(title, text, button, after):
    """A tiny interactive mockup, for the demo prototypes that have no hand-written one."""
    return ("<!doctype html><meta charset=utf8><title>" + title + "</title>"
            "<style>body{margin:0;font:16px system-ui;background:#F2F5F8;color:#121C26;padding:16px}.card{background:#fff;border:1px solid #D5DDE5;border-radius:12px;padding:14px;max-width:420px}"
            "button{min-height:44px;padding:0 16px;border:0;border-radius:8px;background:#1747C9;color:#fff;font:inherit;margin-top:10px}</style>"
            "<div class=card><b>" + title + "</b><p>" + text + "</p><p id=r hidden>" + after + "</p><button id=b>" + button + "</button></div>"
            "<script>document.getElementById('b').onclick=function(){document.getElementById('r').hidden=false;this.hidden=true}</script>")


def proto_documents():
    """The `protos` metadata documents and the `protoHtml` parts a /pilot-proto session would have written."""
    def meta(n, title, **extra):
        return {"kind": "proto", "n": n, "repo": REPO, "title": title, "parts": 0, "at": iso(6), **extra}
    metas = {
        "proto-701": meta(701, "Itinéraire sans escalier : choisir ses contraintes", at=iso(2),
                          brief="Tester un écran où le voyageur indique ses contraintes (escalier, ascenseur, distance) avant le calcul."),
        "proto-702": meta(702, "Alerte ascenseur en panne sur le trajet", parts=1, height=340, at=iso(5),
                          brief="Tester l'alerte et la proposition d'un itinéraire de remplacement quand un ascenseur est en panne."),
        "proto-703": meta(703, "Relais humain depuis l'application", parts=1, height=260, at=iso(30), decision="accepted", decidedAt=iso(29),
                          brief="Tester le bouton qui met le voyageur en relation avec un conseiller."),
        "proto-704": meta(704, "Profil voyageur senior", parts=1, height=300, at=iso(48), decision="accepted", decidedAt=iso(40), stories=[103, 111],
                          brief="Tester un profil qui agrandit les textes et simplifie les écrans."),
        "proto-705": meta(705, "Carte des équipements en temps réel", parts=1, height=260, at=iso(200), decision="accepted", decidedAt=iso(150), stories=[990],
                          brief="Tester l'affichage en direct de l'état des ascenseurs sur une carte."),
        "proto-706": meta(706, "Assistant vocal de bout en bout", parts=1, height=260, at=iso(300), decision="rejected", decidedAt=iso(260),
                          reason="Trop coûteux pour le gain observé : le bouton de relais humain couvre déjà le besoin.",
                          brief="Tester un assistant vocal qui guide tout le trajet."),
    }
    parts = {"protoHtml-702-0": {"n": 702, "k": 0, "html": PROTO_HTML},
             "protoHtml-704-0": {"n": 704, "k": 0, "html": PROTO_SENIOR},
             "protoHtml-703-0": {"n": 703, "k": 0, "html": small_mock("Relais humain", "Besoin d'aide pendant le trajet ?", "Parler à un conseiller", "Un conseiller vous rappelle dans 2 minutes.")},
             "protoHtml-705-0": {"n": 705, "k": 0, "html": small_mock("Équipements en direct", "Ascenseur quai 4 : en panne. Ascenseur quai 2 : en service.", "Actualiser", "Mis à jour à l'instant.")},
             "protoHtml-706-0": {"n": 706, "k": 0, "html": small_mock("Assistant vocal", "Dites votre destination.", "Parler", "Destination comprise : Châtelet.")}}
    return {**metas, **parts}


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
        with open(os.path.join(args.dir, "design.json"), "w", encoding="utf-8") as fh:
            json.dump(design_document(), fh, ensure_ascii=False)
        with open(os.path.join(args.dir, "wiki.json"), "w", encoding="utf-8") as fh:
            json.dump(wiki_document(), fh, ensure_ascii=False)
        for name, doc in proto_documents().items():
            with open(os.path.join(args.dir, name + ".json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)
        for name, doc in live_documents().items():
            with open(os.path.join(args.dir, name + ".json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)


if __name__ == "__main__":
    main()
