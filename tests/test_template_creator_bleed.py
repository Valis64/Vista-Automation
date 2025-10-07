import shutil
import subprocess
from pathlib import Path
import textwrap

import pytest


FUNCTION_NAMES = [
    "normalizeItemName",
    "isTemplateClipName",
    "hasBleedName",
    "collectBleedPaths",
    "findBleedPath",
    "createClippingGroup",
]


def extract_js_function(source: str, name: str) -> str:
    marker = f"function {name}"
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"{name} not found in template_creator.jsx")
    brace = source.find("{", start)
    if brace == -1:
        raise AssertionError(f"Opening brace not found for {name}")
    depth = 1
    i = brace + 1
    in_string = None
    in_single_comment = False
    in_multi_comment = False
    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif in_single_comment:
            if ch == "\n":
                in_single_comment = False
        elif in_multi_comment:
            if ch == "*" and i + 1 < len(source) and source[i + 1] == "/":
                in_multi_comment = False
                i += 1
        else:
            if ch in ('"', "'", "`"):
                in_string = ch
            elif ch == "/" and i + 1 < len(source):
                nxt = source[i + 1]
                if nxt == "/":
                    in_single_comment = True
                    i += 1
                elif nxt == "*":
                    in_multi_comment = True
                    i += 1
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[start : i + 1]
        i += 1
    raise AssertionError(f"Function {name} is not closed properly")


HELPER_RUNTIME = """
const ElementPlacement = { PLACEATEND: 'PLACEATEND', PLACEATBEGINNING: 'PLACEATBEGINNING' };
function alertAndExit(message) { throw new Error(message); }

function attachMove(item) {
    item.move = function(target, placement) {
        if (this.parent && this.parent !== this.doc) {
            if (this.parent.removeChild) {
                this.parent.removeChild(this);
            } else if (this.parent.pageItems) {
                var arr = this.parent.pageItems;
                var idx = arr.indexOf(this);
                if (idx !== -1) arr.splice(idx, 1);
                if (this.parent.pathItems) {
                    var pIdx = this.parent.pathItems.indexOf(this);
                    if (pIdx !== -1) this.parent.pathItems.splice(pIdx, 1);
                }
            }
        }
        if (target && target.addChild) {
            target.addChild(this, placement);
        } else if (target) {
            if (!target.pageItems) target.pageItems = [];
            if (placement === ElementPlacement.PLACEATBEGINNING) {
                target.pageItems.unshift(this);
            } else {
                target.pageItems.push(this);
            }
        }
        this.parent = target;
    };
    return item;
}

function createPath(name, options) {
    options = options || {};
    var item = attachMove({
        typename: 'PathItem',
        name: name || '',
        hidden: !!options.hidden,
        locked: !!options.locked,
        stroked: options.stroked !== undefined ? options.stroked : true,
        strokeColor: options.strokeColor || {},
        geometricBounds: options.geometricBounds || [0, 0, 10, 10],
        visibleBounds: options.visibleBounds || options.geometricBounds || [0, 0, 10, 10],
        parent: null,
        doc: null
    });
    Object.defineProperty(item, 'clipping', {
        get: function() { return !!item._clipping; },
        set: function(value) {
            item._clipping = value;
            if (value) {
                if (item.doc) item.doc._lastClipping = item;
                if (item.parent && item.parent.doc) item.parent.doc._lastClipping = item;
            }
        }
    });
    return item;
}

function createCompound(name, options) {
    options = options || {};
    var child = createPath(name + '_child', options.childOptions || {});
    var compound = attachMove({
        typename: 'CompoundPathItem',
        name: name || '',
        hidden: !!options.hidden,
        locked: !!options.locked,
        strokeColor: options.strokeColor || {},
        geometricBounds: options.geometricBounds || [0, 0, 10, 10],
        visibleBounds: options.visibleBounds || options.geometricBounds || [0, 0, 10, 10],
        parent: null,
        doc: null,
        pathItems: [child]
    });
    child.parent = compound;
    Object.defineProperty(compound, 'clipping', {
        get: function() { return !!compound._clipping; },
        set: function(value) {
            compound._clipping = value;
            if (value) {
                if (compound.doc) compound.doc._lastClipping = compound;
                if (compound.parent && compound.parent.doc) compound.parent.doc._lastClipping = compound;
            }
        }
    });
    return compound;
}

function makeGroup(doc) {
    var group = {
        doc: doc,
        pageItems: [],
        pathItems: [],
        name: '',
        parent: doc
    };
    group.addChild = function(item, placement) {
        if (placement === ElementPlacement.PLACEATBEGINNING) {
            group.pageItems.unshift(item);
        } else {
            group.pageItems.push(item);
        }
        if (item.typename === 'PathItem') {
            if (placement === ElementPlacement.PLACEATBEGINNING) {
                group.pathItems.unshift(item);
            } else {
                group.pathItems.push(item);
            }
        } else if (item.typename === 'CompoundPathItem') {
            for (var i = 0; i < item.pathItems.length; i++) {
                var child = item.pathItems[i];
                if (placement === ElementPlacement.PLACEATBEGINNING) {
                    group.pathItems.unshift(child);
                } else {
                    group.pathItems.push(child);
                }
            }
        }
        item.parent = group;
    };
    group.removeChild = function(item) {
        var idx = group.pageItems.indexOf(item);
        if (idx !== -1) group.pageItems.splice(idx, 1);
        if (item.typename === 'PathItem') {
            var pIdx = group.pathItems.indexOf(item);
            if (pIdx !== -1) group.pathItems.splice(pIdx, 1);
        } else if (item.typename === 'CompoundPathItem') {
            for (var i = 0; i < item.pathItems.length; i++) {
                var child = item.pathItems[i];
                var cIdx = group.pathItems.indexOf(child);
                if (cIdx !== -1) group.pathItems.splice(cIdx, 1);
            }
        }
    };
    group.move = function(target, placement) {
        if (group.parent && group.parent.removeChild) {
            group.parent.removeChild(group);
        }
        if (target && target.addChild) {
            target.addChild(group, placement);
        }
        group.parent = target;
    };
    return group;
}

function makeDocument(options) {
    options = options || {};
    var doc = {
        pathItems: [],
        compoundPathItems: [],
        pageItems: [],
        _lastClipping: null,
        groupItems: {
            add: function() {
                var g = makeGroup(doc);
                doc.pageItems.push(g);
                return g;
            }
        },
        layers: {
            add: function() {
                return {
                    name: '',
                    groupItems: {
                        add: function() {
                            var g = makeGroup(doc);
                            doc.pageItems.push(g);
                            return g;
                        }
                    }
                };
            }
        }
    };
    function register(item) {
        item.doc = doc;
        attachMove(item);
        if (item.typename === 'PathItem') {
            doc.pathItems.push(item);
        } else if (item.typename === 'CompoundPathItem') {
            doc.compoundPathItems.push(item);
            for (var i = 0; i < item.pathItems.length; i++) {
                item.pathItems[i].doc = doc;
            }
        }
        doc.pageItems.push(item);
    }
    var paths = options.pathItems || [];
    for (var i = 0; i < paths.length; i++) {
        register(paths[i]);
    }
    var compounds = options.compoundPathItems || [];
    for (var j = 0; j < compounds.length; j++) {
        register(compounds[j]);
    }
    return doc;
}

function runPathMaskTest() {
    var namedMask = createPath('<Path>', {
        stroked: false,
        geometricBounds: [0, 5, 6, -5],
        visibleBounds: [0, 5, 6, -5]
    });
    var fallback = createPath('Fallback', {
        stroked: true,
        geometricBounds: [0, 7, 20, -7],
        visibleBounds: [0, 7, 20, -7]
    });
    var doc = makeDocument({ pathItems: [namedMask, fallback] });
    var bleedGroup = findBleedPath(doc, function() { return false; }, false);
    if (bleedGroup.pageItems.indexOf(namedMask) === -1) {
        throw new Error('Expected named <Path> mask to be collected into the bleed group');
    }
    var clipGroup = createClippingGroup(doc, bleedGroup);
    if (clipGroup.pageItems[0] !== namedMask) {
        throw new Error('Expected <Path> path to be used as the clipping mask');
    }
    if (!namedMask.clipping) {
        throw new Error('Expected <Path> mask to have clipping enabled');
    }
}

function runCompoundMaskTest() {
    var compoundMask = createCompound('<Path>', {
        geometricBounds: [0, 5, 6, -5],
        visibleBounds: [0, 5, 6, -5]
    });
    var fallback = createPath('Fallback', {
        stroked: true,
        geometricBounds: [0, 7, 20, -7],
        visibleBounds: [0, 7, 20, -7]
    });
    var doc = makeDocument({
        pathItems: [fallback],
        compoundPathItems: [compoundMask]
    });
    var bleedGroup = findBleedPath(doc, function() { return false; }, false);
    if (bleedGroup.pageItems.indexOf(compoundMask) === -1) {
        throw new Error('Expected compound <Path> mask to be collected into the bleed group');
    }
    var clipGroup = createClippingGroup(doc, bleedGroup);
    if (clipGroup.pageItems[0] !== compoundMask) {
        throw new Error('Expected compound <Path> item to be moved to the front of the clipping group');
    }
    var child = compoundMask.pathItems[0];
    if (!child.clipping && !compoundMask.clipping) {
        throw new Error('Expected clipping to be applied to the compound path or its child');
    }
}

runPathMaskTest();
runCompoundMaskTest();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js runtime is required for this test")
def test_template_creator_prefers_named_path(tmp_path):
    source = Path("template_creator.jsx").read_text(encoding="utf-8")
    function_blocks = [extract_js_function(source, name) for name in FUNCTION_NAMES]
    script = "\n\n".join(function_blocks + [textwrap.dedent(HELPER_RUNTIME)])
    result = subprocess.run(
        ["node", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Node test failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
