"""Differential compatibility probes; reports differences without hiding them.

Run from the repository root with the environment under investigation.
"""

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import sys
import warnings
from pathlib import Path


def outcome(function):
    try:
        return {"value": function()}
    except Exception as error:
        result = {"error": type(error).__name__}
        if isinstance(error, UnicodeDecodeError):
            result.update(
                encoding=error.encoding,
                start=error.start,
                end=error.end,
                object_hex=error.object.hex(),
                reason=error.reason,
            )
        return result


def snapshot(module, data, options):
    events = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reader = module.MARCReader(data, **options)
        for index, record in enumerate(reader):
            if index >= 1000:
                raise AssertionError("unexpected reader length")
            if record is None:
                error = reader.current_exception

                def raise_error(error=error):
                    raise error

                events.append(outcome(raise_error))
            else:
                events.append(
                    {
                        "record": record.as_dict(),
                        "encode": outcome(lambda record=record: hashlib.sha256(record.as_marc()).hexdigest()),
                    }
                )
        return {"events": events, "warnings": [[type(item.message).__name__, str(item.message)] for item in caught]}


def probes(module):
    def fresh():
        record = module.Record()
        for tag, value in [("650", "first"), ("245", "title"), ("650", "second")]:
            record.add_field(module.Field(tag=tag, indicators=[" ", " "], subfields=[module.Subfield("a", value)]))
        return record

    functions = {
        "fields_is_list": lambda r: isinstance(r.fields, list),
        "selector_order": lambda r: [f.tag for f in r.get_fields("650", "245")],
        "duplicate_selectors": lambda r: [f.tag for f in r.get_fields("650", "650")],
        "fields_list_identity": lambda r: r.get_fields() is r.fields,
        "missing_subfield": lambda r: r["245"]["z"],
        "append_subfield": lambda r: (r["245"].subfields.append(module.Subfield("b", "subtitle")), r.title)[1],
        "assign_subfield": lambda r: (r["245"].__setitem__("a", "changed"), r.title)[1],
        "append_field": lambda r: (
            r.fields.append(module.Field(tag="500", indicators=[" ", " "], subfields=[module.Subfield("a", "note")])),
            len(r.get_fields("500")),
        )[1],
    }
    results = {name: outcome(lambda fn=fn: fn(fresh())) for name, fn in functions.items()}
    for tag in [None, " 1", "+01", "001", "\u0661\u0662\u0663"]:
        results[f"tag_{tag!r}"] = outcome(lambda tag=tag: module.Field(tag=tag).tag)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--libraries", nargs="+", default=["pymarc", "rmarc", "mrrc"])
    args = parser.parse_args()
    modules = {name: importlib.import_module(name) for name in args.libraries}
    report = {
        "python": sys.version,
        "versions": {name: importlib.metadata.version(name) for name in modules},
        "probes": {name: probes(module) for name, module in modules.items()},
        "fixtures": [],
    }
    reference = modules["pymarc"].Record(force_utf8=True)
    reference.add_field(
        modules["pymarc"].Field(
            tag="245", indicators=[" ", " "], subfields=[modules["pymarc"].Subfield("a", "valid\ufffdX")]
        )
    )
    malformed = reference.as_marc().replace(b"X", b"\xff")
    report["utf8_handlers"] = {}
    for name in ["pymarc", "rmarc"]:

        def read_title(handling, module=modules[name]):
            reader = module.MARCReader(malformed, utf8_handling=handling)
            record = next(reader)
            if record is None:
                raise reader.current_exception
            return record.title

        report["utf8_handlers"][name] = {
            handling: outcome(lambda handling=handling: read_title(handling))
            for handling in ["strict", "ignore", "replace", "backslashreplace", "surrogateescape"]
        }
    unicode_record = modules["pymarc"].Record(force_utf8=True)
    unicode_record.add_field(
        modules["pymarc"].Field(
            tag="245", indicators=[" ", " "], subfields=[modules["pymarc"].Subfield("a", "caf\u00e9")]
        )
    )
    unicode_bytes = unicode_record.as_marc()
    unicode_bytes = unicode_bytes[:9] + b" " + unicode_bytes[10:]
    control = modules["pymarc"].Record(to_unicode=False)
    control.add_field(modules["pymarc"].Field(tag="001", data="\u00e9"))
    cases = [
        ("explicit_utf8_without_flag", unicode_bytes, {"file_encoding": "utf-8"}),
        ("latin1_control_field", control.as_marc(), {}),
    ]
    report["encoding_cases"] = {
        case: {
            name: outcome(lambda name=name, data=data, options=options: snapshot(modules[name], data, options))
            for name in ["pymarc", "rmarc"]
        }
        for case, data, options in cases
    }
    options = [
        {},
        {"to_unicode": False},
        {"utf8_handling": "replace"},
        {"utf8_handling": "ignore"},
        {"force_utf8": True},
        {"file_encoding": "cp1251"},
    ]
    fixtures = sorted([*Path("test_pymarc").glob("*.dat"), *Path("test_pymarc").glob("*.mrc")])
    for path in fixtures:
        for kwargs in options:
            data = path.read_bytes()
            reference = outcome(lambda data=data, kwargs=kwargs: snapshot(modules["pymarc"], data, kwargs))
            actual = outcome(lambda data=data, kwargs=kwargs: snapshot(modules["rmarc"], data, kwargs))
            report["fixtures"].append(
                {
                    "file": path.name,
                    "options": kwargs,
                    "equal": actual == reference,
                    **({} if actual == reference else {"pymarc": reference, "rmarc": actual}),
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=lambda x: {"bytes_hex": x.hex()}) + "\n", encoding="utf-8"
    )
    matches = sum(row["equal"] for row in report["fixtures"])
    print(f"{matches}/{len(report['fixtures'])} fixture/option combinations exactly match pymarc")
    for row in report["fixtures"]:
        if not row["equal"]:
            print(row["file"], row["options"])
    print(json.dumps(report["probes"], indent=2))


if __name__ == "__main__":
    main()
