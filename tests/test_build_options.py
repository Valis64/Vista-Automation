import json
import re
import subprocess
from pathlib import Path
from string import Template
import textwrap


def _extract_build_options_sources():
    source = Path("template_creator.jsx").read_text()

    lam_match = re.search(r"var LAM_OPTIONS = [\s\S]*?];", source)
    if not lam_match:
        raise AssertionError("LAM_OPTIONS definition not found")

    build_start = source.find("function buildOptions(data)")
    if build_start == -1:
        raise AssertionError("buildOptions definition not found")

    brace_depth = 0
    end_idx = None
    for idx in range(build_start, len(source)):
        char = source[idx]
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
            if brace_depth == 0:
                end_idx = idx
                break
    if end_idx is None:
        raise AssertionError("Failed to locate end of buildOptions")

    build_source = source[build_start:end_idx + 1]
    return lam_match.group(0), build_source


def _run_build_options(data):
    lam_source, build_source = _extract_build_options_sources()
    node_script_template = Template(
        textwrap.dedent(
            """
            const data = $data_json;
            $lam_source
            var ART_ROOT = "ART";
            var TEMPLATE_ROOT = "TEMPLATE";
            function File(path) {
                return {
                    path: path,
                    fsName: path,
                    absoluteURI: path,
                    toString: function() { return path; },
                };
            }
            $build_source
            const result = buildOptions(data);
            const mapped = result.pairs.map(p => ({
                skip: !!p.skip,
                mode: p.mode,
                processingMode: p.processingMode,
                blankTemplateMode: !!p.blankTemplateMode,
                artFile: p.artFile ? p.artFile.path : null,
                templateFile: p.templateFile ? p.templateFile.path : null,
                templateCode: p.templateCode,
                laminate: p.laminate,
                paper: p.paper,
                orderData: p.orderData,
            }));
            console.log(JSON.stringify({ pairs: mapped }));
            """
        )
    )
    node_script = node_script_template.substitute(
        data_json=json.dumps(data), lam_source=lam_source, build_source=build_source
    )

    completed = subprocess.run(
        ["node", "-e", node_script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)["pairs"]


def test_build_options_skips_flagged_pairs_and_items():
    data = {
        "items": [
            {"filename": "keep.ai", "info": "first", "lamType": "Matte", "paperType": "Paper A"},
            {"filename": "pair-skip.ai", "info": "skip pair", "lamType": "Gloss", "paperType": "Paper B"},
            {
                "filename": "item-skip.ai",
                "info": "skip item",
                "lamType": "SoftTouch",
                "paperType": "Paper C",
                "skip": True,
            },
            {"filename": "keep-last.ai", "info": "last", "lamType": "Uncoated", "paperType": "Paper D"},
        ],
        "pairs": [
            {"art_path": "art-one.ai", "template_path": "template-one.ai", "template": "T1"},
            {"art_path": "art-two.ai", "template_path": "template-two.ai", "template": "T2", "skip": True},
            {"art_path": "art-three.ai", "template_path": "template-three.ai", "template": "T3"},
            {"art_path": "art-four.ai", "template_path": "template-four.ai", "template": "T4"},
        ],
    }

    pairs = _run_build_options(data)

    assert len(pairs) == 4
    assert [p["artFile"] for p in pairs] == [
        "art-one.ai",
        "art-two.ai",
        "art-three.ai",
        "art-four.ai",
    ]
    assert pairs[1]["skip"] is True
    assert pairs[2]["skip"] is True
    assert pairs[0]["orderData"]["filename"] == "keep.ai"
    assert pairs[3]["orderData"]["filename"] == "keep-last.ai"
    assert pairs[3]["laminate"]["name"] == "Uncoated"
    assert pairs[3]["paper"] == "Paper D"


def test_build_options_blank_template_mode_does_not_require_art_path():
    data = {
        "items": [
            {"filename": "blank.ai", "info": "blank-mode", "lamType": "Matte", "paperType": "Paper A"},
            {"filename": "normal.ai", "info": "standard", "lamType": "Gloss", "paperType": "Paper B"},
        ],
        "pairs": [
            {
                "art_path": "should-not-be-used.ai",
                "template_path": "template-blank.ai",
                "template": "TB",
                "blank_template": True,
            },
            {"art_path": "normal-art.ai", "template_path": "template-normal.ai", "template": "TN"},
        ],
    }

    pairs = _run_build_options(data)

    assert pairs[0]["templateCode"] == "TB"
    assert pairs[0]["templateFile"] == "template-blank.ai"
    assert pairs[0]["artFile"] is None
    assert pairs[1]["artFile"] == "normal-art.ai"


def test_build_options_default_mode_keeps_art_file_when_blank_template_not_enabled():
    data = {
        "items": [
            {"filename": "default.ai", "info": "default", "lamType": "Matte", "paperType": "Paper A"}
        ],
        "pairs": [
            {"art_path": "default-art.ai", "template_path": "template-default.ai", "template": "TD"}
        ],
    }

    pairs = _run_build_options(data)

    assert len(pairs) == 1
    assert pairs[0]["artFile"] == "default-art.ai"
