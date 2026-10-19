import json

import pytest

from escuchator.llm.parsing import parse_analysis


def test_accepts_fenced_json_and_filters_invalid_items():
    text = """```json
{"resumen": "ok", "conceptos": [{"termino": "RTO", "explicacion": "Recovery time objective"}, {"bad": 1}],
 "preguntas": [{"pregunta": "How?", "breve": "Like this"}, "nope"]}
```"""
    data = parse_analysis(text)
    assert data["resumen"] == "ok"
    assert [c["termino"] for c in data["conceptos"]] == ["RTO"]
    assert len(data["preguntas"]) == 1


def test_rejects_wrong_shapes():
    with pytest.raises(ValueError):
        parse_analysis('{"conceptos": "wrong"}')
    with pytest.raises(ValueError):
        parse_analysis("[]")


def test_caps_number_of_items():
    concepts = [{"termino": f"t{i}", "explicacion": "e"} for i in range(10)]
    assert len(parse_analysis(json.dumps({"conceptos": concepts}))["conceptos"]) == 4
