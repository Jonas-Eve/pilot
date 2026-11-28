#!/usr/bin/env python3
"""Fake data for the PILOT dashboard, so the template is developed against a demo artifact
("Cockpit pilot (démo)") and never against a real project's dashboard.

Usage:
  python3 scripts/demo_snapshot.py --out FILE        # the `snapshots/Jonas-Eve__pilot` document
  python3 scripts/demo_snapshot.py --dir DIR         # that document + a few events (tickets and runs), a design document, a wiki document, an architecture document and prototypes

Timestamps are relative to now, so re-run it to refresh the demo. Stdlib only.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot  # noqa: E402  (the steps of the workflows: the same function `pilot.py snapshot` uses)

REPO = "Jonas-Eve/pilot"


def iso(hours_ago=0.0):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# (number, title, labels, hours since update, parent, [done, total] sub-issues, assignee, open PR)
def tickets():
    t = []

    def add(n, title, labels, h, p=None, k=None, a=None, r=None):
        t.append((n, title, labels, h, p, k, a, r))

    add(100, "Parcours voyageur accessible de bout en bout", ["type:feature", "level:epic", "status:planned"], 30, k=[3, 9])
    add(101, "Itinéraire sans escalier entre deux correspondances", ["type:feature", "level:story", "status:planned", "priority:P1"], 6, 100, [1, 3])
    add(111, "Calcul de l'itinéraire sans escalier", ["type:feature", "level:task", "status:building", "priority:P1"], 2, 101, None, "alice")
    add(112, "Écran de choix des contraintes", ["type:feature", "level:task", "status:reviewing", "priority:P1"], 5, 101, None, None, 61)
    add(113, "Test e2e de l'itinéraire sans escalier", ["type:feature", "level:task", "status:ready", "priority:P1"], 8, 101)
    add(102, "Alerte ascenseur en panne sur le trajet", ["type:feature", "level:story", "status:to-plan", "priority:P0"], 20, 100)
    add(103, "Profil voyageur senior", ["type:feature", "level:story", "status:merged", "priority:P1"], 40, 100)
    add(104, "Notification de relais humain", ["type:feature", "level:story", "status:forming", "priority:P2"], 3, 100, None, "carol")
    add(200, "Plateforme multi-organisations", ["type:feature", "level:epic", "status:planned"], 70, k=[1, 4])
    add(201, "Inviter un administrateur dans son organisation", ["type:feature", "level:story", "status:planned", "priority:P1"], 12, 200, [1, 2])
    add(211, "API d'invitation et jeton à usage unique", ["type:tech", "level:task", "status:reviewing", "priority:P1"], 4, 201, None, None, 58)
    add(212, "Écran d'acceptation d'invitation", ["type:feature", "level:task", "status:building", "priority:P1"], 3, 201, None, "bob", 59)
    add(202, "Renommer son organisation", ["type:feature", "level:story", "status:merged", "priority:P2"], 50, 200)
    add(203, "Supprimer son organisation", ["type:feature", "level:story", "status:to-plan", "priority:P2", "needs-human"], 90, 200)
    add(301, "Cache des états d'équipements", ["type:tech", "level:story", "status:planning", "priority:P1", "needs-human"], 7, None, None, "alice")
    add(302, "Migration du stockage des profils", ["type:tech", "level:story", "status:ready", "priority:P2"], 1)
    add(303, "Tier-2 : source de credential déléguée", ["type:tech", "level:story", "status:to-plan", "priority:P2", "on-hold"], 200)
    add(304, "Purge planifiée des comptes jamais confirmés", ["type:tech", "level:story", "status:ready", "priority:P2"], 26)
    add(401, "Pictogramme PMR masqué en mode sombre", ["type:feature", "level:task", "status:ready", "priority:P0", "fix"], 9)
    add(402, "Le jeton expiré n'est pas détecté", ["type:tech", "level:task", "status:ready", "priority:P1", "fix"], 15)
    add(403, "Le flux s'interrompt si un message part pendant la réponse", ["type:tech", "level:task", "status:building", "priority:P1", "needs-human"], 18, None, None, "carol")
    add(404, "Reprise d'un build interrompu", ["type:tech", "level:task", "status:building", "priority:P1", "can-resume"], 22, None, None, "alice")
    add(405, "Correctif : horaires affichés au mauvais fuseau", ["type:feature", "level:story", "status:reviewing", "priority:P0", "express"], 4, None, None, "bob", 62)
    add(406, "Carte des équipements hors ligne", ["type:feature", "level:task", "status:ready", "priority:P1", "gap"], 11)
    add(701, "run:proto Itinéraire sans escalier : choisir ses contraintes", ["run:proto"], 2, None, None, "alice")
    add(702, "run:proto Alerte ascenseur en panne sur le trajet", ["run:proto", "needs-human"], 5)
    add(710, "run:technical-frame Règle de nommage des modules", ["run:technical-frame"], 1, None, None, "carol")
    add(711, "run:design-system Thème à fort contraste", ["run:design-system"], 1, None, None, "bob")
    add(712, "run:persona Persona : Léa, 16 ans, daltonienne", ["run:persona", "needs-human"], 3)
    add(713, "run:user-flow Parcours : réserver une assistance en gare", ["run:user-flow"], 2, None, None, "alice")
    for i in range(24):
        status = ["ready", "reviewing", "merged", "ready"][i % 4]
        labels = ["type:tech", "level:task", f"status:{status}", f"priority:P{(i % 3)}"]
        add(500 + i, f"Tâche technique d'exemple {i + 1}", labels, 24 + i * 5, None, None, None, 70 + i if status == "reviewing" else None)
    return t


TASK_CHAIN = ["ready", "building", "reviewing", "merged"]
STORY_CHAIN = ["forming", "to-plan", "planning", "ready", "building", "reviewing", "merged"]


def history(labels, hours):
    """The stages a demo ticket went through (what `pilot.py snapshot` reads from the label events): the current
    one entered `hours` ago, each earlier one a plausible stretch before. A planned parent has none."""
    status = next((l[len("status:"):] for l in labels if l.startswith("status:")), "")
    chain = TASK_CHAIN if "level:task" in labels else STORY_CHAIN
    if status not in chain:
        return None
    out, back = [[status, iso(hours)]], hours
    for i in range(chain.index(status) - 1, -1, -1):
        back += 6 + (i * 7) % 29
        out.insert(0, [chain[i], iso(back)])
    return out


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
        if history(labels, hours):  # as `pilot.py snapshot`: no history, no flag time either
            row["h"] = history(labels, hours)
            if "needs-human" in labels:
                row["nh"] = iso(hours)
        rows.append(row)
    rows.sort(key=lambda r: r["u"], reverse=True)
    return {"repo": REPO, "at": iso(0.5), "source": "demo", "total": len(rows), "truncated": False, "issues": rows,
            "modules": {"wiki": True, "architecture": True, "dashboard": True, "design": True, "proto": True},
            "language": "fr", "workflows": WORKFLOWS, "workflowSteps": pilot.workflow_steps(pilot.load_workflows())}


WORKFLOWS = ["accept", "build", "design-system", "express", "functional-frame", "need", "persona", "plan", "proto", "report", "technical-frame", "user-flow"]


def live_documents():
    """The events a workflow would have pushed, as `events` documents: tickets (`pilot.py claim|set|flag`) and run steps (`pilot.py run`)."""
    def run(n, workflow, step, state, hours, action="advance:ok", loops=None, **extra):
        return {"kind": "run", "n": n, "workflow": workflow, "step": step, "state": state, "loops": loops or {}, "action": action,
                "by": "alice", "at": iso(hours), **extra}
    return {
        "event-600": {"kind": "ticket", "n": 600, "title": "Tâche créée par une conception depuis le dernier instantané",
                      "labels": ["type:feature", "level:task", "status:ready", "priority:P1"],
                      "assignees": [], "state": "open", "action": "created", "phase": "plan", "parent": 101,
                      "by": "alice", "at": iso(0.2)},
        "event-105": {"kind": "ticket", "n": 105, "title": "Story clôturée après le besoin",
                      "labels": ["type:feature", "level:story", "status:to-plan", "priority:P1"],
                      "assignees": [], "state": "open", "action": "close-forming", "phase": "need", "parent": 100,
                      "by": "carol", "at": iso(0.1)},
        "event-111": {"kind": "ticket", "n": 111, "title": "Calcul de l'itinéraire sans escalier",
                      "labels": ["type:feature", "level:task", "status:building", "priority:P1"],
                      "assignees": ["alice"], "state": "open", "action": "claim:fresh", "phase": "build",
                      "by": "alice", "at": iso(0.4)},
        "run-111": run(111, "build", "implement", "running", 0.4, "start"),
        "run-301": run(301, "plan", "ask", "waiting-human", 0.8, "advance:blocked", loops={"check": 1},
                       question="Découper l'epic par parcours (réserver, annuler) ou par écran ? Le découpage par parcours livre plus tôt, par écran évite les doublons.",
                       branch="pilot-run/301"),
        "run-302": run(302, "build", "check", "waiting-human", 0.5, "advance:fail", loops={"check": 2},
                       escalated={"from": "check", "failures": 3}),
        "run-701": run(701, "proto", "build", "running", 0.3),
        "run-702": run(702, "proto", "ask", "waiting-human", 1.5, "advance:blocked",
                       question="Faut-il un écran de confirmation avant d'envoyer l'alerte d'ascenseur en panne ?", branch="pilot-run/702"),
        "run-703": run(703, "proto", "end", "done", 29, "end", result="accepted"),
        "run-704": run(704, "proto", "end", "done", 40, "end", result="accepted"),
        "run-705": run(705, "proto", "end", "done", 150, "end", result="accepted"),
        "run-706": run(706, "proto", "end", "done", 260, "end", result="rejected"),
        "run-710": run(710, "technical-frame", "check", "waiting-human", 1.0, "advance:fail", escalated={"from": "check", "failures": 3}),
        "run-711": run(711, "design-system", "build", "running", 0.6, loops={"check": 1}),
        "run-712": run(712, "persona", "challenge", "waiting-human", 2.0),
        "run-713": run(713, "user-flow", "write", "running", 0.5),
    }


def flow_documents():
    """The `flowRuns` documents, one per user flow that has been played."""
    rows = {e["id"]: e for e in wiki_document()["entries"]}
    passed = {"kind": "flowRun", "repo": REPO, "flow": "lire-un-lieu", "at": iso(20), "hash": rows["lire-un-lieu"]["hash"], "result": "passed", "bugs": [], "report": "",
              "personas": [{"id": "marie-senior", "hash": rows["marie-senior"]["hash"], "result": "passed", "steps": {"passed": 1, "failed": 0, "untestable": 0}}]}
    return {"flowrun-trouver-un-lieu": flow_run_document(), "flowrun-lire-un-lieu": passed}


def flow_run_document():
    """What `pilot.py flow doc` would have written after Marie and Paul played the demo flow two days ago:
    Marie passed, Paul could not finish one step; Paul's persona entry has changed since."""
    rows = {e["id"]: e for e in wiki_document()["entries"]}
    return {"kind": "flowRun", "repo": REPO, "flow": "trouver-un-lieu", "at": iso(48), "hash": rows["trouver-un-lieu"]["hash"],
            "result": "partial", "bugs": [401], "report": "",
            "personas": [{"id": "marie-senior", "hash": rows["marie-senior"]["hash"], "result": "passed", "steps": {"passed": 2, "failed": 0, "untestable": 0}},
                         {"id": "paul-aidant", "hash": "0123456789ab", "result": "partial", "steps": {"passed": 1, "failed": 0, "untestable": 1}}]}


def design_document():
    """The `design/Jonas-Eve__pilot` document a /pilot-design-system session would have written."""
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


def architecture_document():
    """The `architecture/Jonas-Eve__pilot` document `pilot.py arch snapshot` would have written."""
    def entry(eid, title, path, status, tickets, text, supersedes="", superseded_by="", verified="", by=""):
        return {"id": eid, "title": title, "description": text.split(".")[0] + ".", "path": path, "status": status,
                "tickets": tickets, "supersedes": supersedes, "supersededBy": superseded_by, "verifiedAt": verified, "verifiedBy": by, "text": text}
    entries = [
        entry("overview", "Vue d'ensemble", "overview.md", "accepted", [], "Une application en ligne de commande, sans service distant."),
        entry("layering", "Couches", "guidelines/layering.md", "accepted", [], "Le domaine n'importe jamais les adaptateurs.", verified=iso(40), by="process:pilot-wiki"),
        entry("data-model", "Modèle de données", "reference/data-model.md", "accepted", [], "Table catalogue(id, nom, version) et table etapes(id, catalogue_id, rang).", verified=iso(180), by="process:pilot-wiki"),
        entry("stack", "Pile technique", "reference/stack.md", "accepted", [], "Node 22, TypeScript 5.6, Vitest 2."),
        entry("0001-compute", "Catalogue calculé", "adr/0001-compute.md", "superseded", [5], "Le catalogue est recalculé à chaque appel.", "", "0002-store"),
        entry("0002-store", "Catalogue stocké", "adr/0002-store.md", "accepted", [12], "Le catalogue est stocké, pas calculé.", "0001-compute", verified=iso(90), by="process:pilot-wiki"),
        entry("web-overview", "Application web", "apps/web/web-overview.md", "accepted", [], "L'interface web, en React."),
        entry("a11y", "Accessible par défaut", "apps/web/guidelines/a11y.md", "accepted", [], "Chaque contrôle a un nom accessible."),
    ]
    return {"kind": "architecture", "repo": REPO, "at": iso(3), "total": len(entries), "truncated": False, "entries": entries}


def wiki_document():
    """The `wiki/Jonas-Eve__pilot` document `pilot.py wiki snapshot` would have written."""
    def entry(eid, title, path, status, derived, tickets, verified, text, typ="Behavior", by=""):
        shown = status + (" · " + derived if derived else "")
        return {"id": eid, "type": typ, "hash": hashlib.sha256((title + "\n" + text).encode("utf-8")).hexdigest()[:12], "title": title, "description": text.split(".")[0] + ".", "path": path, "status": status,
                "derived": derived, "display": shown, "tickets": tickets,
                "verifiedAt": iso(verified) if verified else "", "verifiedBy": by if verified else "", "text": text}
    entries = [
        entry("vision", "Vision du produit", "product/vision.md", "", "", [], 0,
              "Aider chacun à se déplacer sans mauvaise surprise : le produit vérifie l'état réel des équipements avant le départ.", "Vision"),
        entry("search-by-name", "Rechercher un lieu par son nom", "recherche/search-by-name.md", "implemented", "verified", [1], 40,
              "On cherche un lieu par une partie de son nom, sans tenir compte des majuscules.", by="process:pilot-qa"),
        entry("filter-step-free", "Filtrer sur l'accès de plain-pied", "recherche/filter-step-free.md", "implemented", "", [2], 40,
              "Avec l'option, seuls les lieux dont l'accès de plain-pied est confirmé sont proposés.", by="process:pilot-dev"),
        entry("sort-by-distance", "Trier par distance, le plus proche d'abord", "recherche/sort-by-distance.md", "implemented", "", [3], 0,
              "Les résultats sont triés du plus proche au plus éloigné."),
        entry("km-display", "Afficher les longues distances en km", "affichage/km-display.md", "specified", "in-review", [12, 14], 0,
              "Une distance de 1000 m ou plus est affichée en kilomètres avec une décimale."),
        entry("csv-export", "Exporter le résultat en CSV", "export/csv-export.md", "proposed", "", [4], 0,
              "Une option affiche le résultat en CSV avec une ligne d'en-tête."),
        entry("marie-senior", "Marie, 74 ans, malvoyante", "persona/marie-senior.md", "", "", [], 0,
              "Elle utilise son téléphone avec un zoom à 200 %. Compte de test : marie.", "Persona"),
        entry("paul-aidant", "Paul, aidant de sa mère", "persona/paul-aidant.md", "", "", [], 0,
              "Il prépare les trajets de sa mère depuis son ordinateur. Compte de test : paul.", "Persona"),
        entry("trouver-un-lieu", "Trouver un lieu accessible", "user-flow/trouver-un-lieu.md", "implemented", "", [], 0,
              "Objectif : trouver un lieu de plain-pied près de soi.\nPersonas : marie-senior, paul-aidant\n1. Ouvrir la recherche → le champ est visible.\n2. Filtrer sur l'accès de plain-pied → la liste se réduit.", "UserFlow"),
        entry("lire-un-lieu", "Lire la fiche d'un lieu", "user-flow/lire-un-lieu.md", "implemented", "", [], 0,
              "Objectif : lire l'accessibilité d'un lieu avant de partir.\nPersonas : marie-senior\n1. Ouvrir une fiche → le nom et la distance sont lus.", "UserFlow"),
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
        "proto-703": meta(703, "Relais humain depuis l'application", parts=1, height=260, at=iso(30),
                          brief="Tester le bouton qui met le voyageur en relation avec un conseiller."),
        "proto-704": meta(704, "Profil voyageur senior", parts=1, height=300, at=iso(48),
                          brief="Tester un profil qui agrandit les textes et simplifie les écrans."),
        "proto-705": meta(705, "Carte des équipements en temps réel", parts=1, height=260, at=iso(200),
                          brief="Tester l'affichage en direct de l'état des ascenseurs sur une carte."),
        "proto-706": meta(706, "Assistant vocal de bout en bout", parts=1, height=260, at=iso(300),
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
        with open(os.path.join(args.dir, "architecture.json"), "w", encoding="utf-8") as fh:
            json.dump(architecture_document(), fh, ensure_ascii=False)
        for name, doc in proto_documents().items():
            with open(os.path.join(args.dir, name + ".json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)
        for name, doc in list(live_documents().items()) + list(flow_documents().items()):
            with open(os.path.join(args.dir, name + ".json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)


if __name__ == "__main__":
    main()
