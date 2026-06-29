# FF7 Materia Graph

A small knowledge graph of the materia system in Final Fantasy VII (1997). It loads a curated set of materia into a graph of nodes and edges, then lets you ask how they connect: which materia share the Fire element, what a summon grants, which support materia pair with Comet, or the shortest link between any two materia.

I built it to learn how a knowledge graph works, taking a pile of facts and turning them into nodes and edges, saving them, and walking the connections. The data is the FF7 materia I grew up with, which made it a fun thing to explore. The idea was sparked by tools that index a codebase into a queryable graph, so here I pointed the same idea at game data instead of source code.

There are two ways to use it: a Python command-line tool backed by SQLite, and a single-page browser explorer. Both read the same dataset.

## What is in the graph

Five kinds of node:

- **materia** (Fire, Bahamut, All, Steal, ...)
- **category** (Magic, Summon, Support, Command, Independent)
- **element** (Fire, Ice, Lightning, ...)
- **ability** (the spells and commands a materia grants, like Fire2 or D.Blow)
- **location** (where a materia is first found)

Five kinds of edge: `BELONGS_TO`, `HAS_ELEMENT`, `GRANTS`, `FOUND_AT`, and `PAIRS_WITH` (the support combos). The current dataset builds 214 nodes and 292 edges from 83 materia.

Spell and ability names use the original North American PlayStation translation, so it is Fire, Fire2, Fire3 and Bolt rather than the later names.

## The Python tool

Python 3, standard library only. From the `engine` folder:

```
python build_index.py            # reads data/materia.json, builds ff7graph.db
python query.py stats
python query.py show Fire
python query.py find --category summon
python query.py find --element fire
python query.py find --at "Gold Saucer"
python query.py path Fire Ifrit
python query.py combos All
python query.py context Bahamut --json
```

`build_index.py` is the indexer. It reads the dataset, checks every field, and saves the graph to a single SQLite file. `query.py` reads that file and answers questions. The `context` command prints a compact JSON bundle of one materia plus its direct neighbors, which is the focused answer you would hand to an assistant instead of a whole page of text.

Run the tests:

```
python -m unittest discover -s tests
```

## The browser explorer

Open `web/index.html` by double-clicking it. It runs entirely in your browser and nothing is uploaded. There are two tabs:

- **Browse** picks one materia at a time. Filter by category and element or search by name, and the panel shows its details with a small live graph of everything it connects to: the materia sits pinned in the middle while its connections float and drift around it. Drag a node to give it a nudge, or click one to walk to it.
- **Map** draws the whole graph at once as a force-directed network spread into a wide oval: every node floating, edges pulling linked nodes together, hubs like the five categories sitting at the center of their spokes. Drag a node to move it, scroll to zoom, drag the background to pan, and hover a node to light up its connections. Click a node to open it in Browse. The checkboxes hide or show a whole kind of node (handy for hiding the many ability nodes to declutter). "Reset view" re-centers and fits the graph, and "Clear selection" removes the current highlight.

Open `web/tests.html` the same way to watch the browser test suite run and report PASS or FAIL on the page.

## Keeping the two in sync

`data/materia.json` is the single source of truth. Edit it, then run `python build_index.py` again. That rebuilds `ff7graph.db` for the Python tool and refreshes `web/data.js` for the browser, so both stay in step. The indexer prints a clear message if a field is missing or points at something that does not exist.

## Repository layout

```
ff7-materia-graph/
  data/
    materia.json          curated dataset, the single source of truth
  engine/
    ff7_graph.py          the graph model and algorithms
    validate.py           dataset checks with clear messages
    build_index.py        the indexer, writes ff7graph.db and web/data.js
    query.py              the command-line query tool
    tests/
      test_ff7_graph.py   the Python test suite
  web/
    index.html            the browser explorer (Browse and Map tabs)
    styles.css
    graph-logic.js        the same graph logic, ported to the browser
    force-graph.js        the force-directed Map view
    app.js                wires the page to the logic
    data.js               generated from materia.json by the indexer
    tests.html            the browser test suite
  README.md
  LICENSE
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).

Final Fantasy VII is the property of Square Enix. This is a fan-made reference tool and is not affiliated with or endorsed by Square Enix.
