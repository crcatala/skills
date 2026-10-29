#!/usr/bin/env python3
"""Print what to generate for each recipe, for whichever image tool the session has.

    cd <sprite set>; python3 {baseDir}/scripts/prompt.py [recipe-id ...] [--all] [--json]

With no ids, lists the recipes that have no raw/<id>.png yet, in an order where every reference comes
before the recipes that use it. For each: the full prompt (shared style + recipe prompt), the aspect
ratio, the reference image to attach (if any) and the output path. Standard library only.
"""
import argparse, json, os, sys

WORK = os.getcwd()


def order(recipes):
    done, out = set(), []

    def visit(r, seen=()):
        if r['id'] in done:
            return
        ref = r.get('reference')
        if ref:
            if ref in seen or ref not in recipes:
                sys.exit(f"{r['id']}: reference '{ref}' is missing or circular")
            visit(recipes[ref], seen + (r['id'],))
        done.add(r['id']); out.append(r)
    for r in recipes.values():
        visit(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*'); ap.add_argument('--all', action='store_true'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    book = json.load(open(os.path.join(WORK, 'recipes.json')))
    recipes = {r['id']: r for r in book['recipes']}
    raw = lambda i: os.path.join('raw', i + '.png')
    todo = [r for r in order(recipes) if (a.ids and r['id'] in a.ids) or (not a.ids and (a.all or not os.path.exists(os.path.join(WORK, raw(r['id'])))))]
    jobs = []
    for r in todo:
        cols, rows = r['grid']
        jobs.append({
            'id': r['id'],
            'prompt': book['style'] + ' ' + r['prompt'],
            'aspect_ratio': '2:1' if rows == 1 else f'{cols}:{rows}',  # a 4x1 row at 4:1 leaves cells too small
            'transparent': True,
            'reference': raw(r['reference']) if r.get('reference') else None,
            'output': raw(r['id']),
        })
    if a.json:
        print(json.dumps(jobs, indent=1)); return
    if not jobs:
        print('every recipe has a raw sheet; pass ids to redo one'); return
    for j in jobs:
        print(f"## {j['id']}\noutput: {j['output']}\naspect: {j['aspect_ratio']}, transparent background"
              + (f"\nreference image: {j['reference']}" if j['reference'] else '') + f"\nprompt: {j['prompt']}\n")


if __name__ == '__main__':
    main()
