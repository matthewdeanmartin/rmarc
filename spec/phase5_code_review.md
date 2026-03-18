## Code review: important risks and caveats

This is the section contributors should read most carefully if they are deciding how much trust to place in the Rust
path.

## Finding 1: Rust UTF-8 `"strict"` mode is not actually strict

This is the most important semantic issue I found.

In Python, UTF-8 decoding does this:

```python
data.decode("utf-8", utf8_handling)
```

When `utf8_handling == "strict"`, invalid UTF-8 should raise `UnicodeDecodeError`.

In Rust, the helper is:

```rust
fn decode_utf8(data: &[u8], handling: &str) -> String {
    match handling {
        "strict" => String::from_utf8(data.to_vec())
            .unwrap_or_else(|_| String::from_utf8_lossy(data).into_owned()),
        ...
    }
}
```

That means:

- `"strict"` does not raise
- it silently falls back to lossy decoding with replacement characters

Why this matters:

- it is a real semantic divergence from the Python fallback
- bad UTF-8 data may be accepted instead of surfacing as an error
- because the reader is permissive, this may change `current_exception` behavior in edge cases

This is the first place I would tighten if the goal is "can contributors trust the Rust path as behaviorally identical?"

## Finding 2: Rust error mapping still depends on parsing exception message text

`Record._decode_marc_rust()` catches `ValueError` from Rust and then does message matching:

- `"DirectoryInvalid"`
- `"NoFieldsFound"`
- `"not valid ASCII"`

That works, but it is brittle.

The problem is not speed. The problem is maintainability.

If Rust error strings change, Python exception mapping may silently drift.

A more trustworthy design would return structured error codes instead of parsing strings.

## Finding 3: decode semantics are more trustworthy than encode semantics

Decode has a strong story:

- well-isolated hot path
- clear fallback
- lots of tests

Encode is somewhat less complete because:

- field serialization still happens in Python
- Rust only assembles the final record structure

This is not wrong, but it means the encode speedup story is less "Rust owns encoding" and more "Rust owns the record
assembly part."

Contributors should understand that before assuming encode and decode are equally reviewed or equally accelerated.

## Finding 4: generated mapping tables are trustworthy only if the generation path is documented

`src/marc8_mapping.rs` is generated and huge.

That is normal, but it changes the trust question.

You should not try to line-review the whole file manually.

You should instead ask:

1. what generated it?
2. is generation reproducible?
3. do tests validate representative entries and behavior?

Right now the file says it is auto-generated from `python/rmarc/marc8_mapping.py`, which is good, but a documented
regeneration workflow would make contributor trust much stronger.

## Finding 5: there is still Python boundary overhead by design

This is not a correctness problem, but it is important for future optimization discussions.

The architecture deliberately pays for:

- Python tuple/list creation in Rust
- Python object wrapping in `record.py`

That means future "why not 20x faster?" questions have an architectural answer:

- because this project chose compatibility and simplicity over a full Rust object graph

That is probably the right choice, but contributors should know it is a choice.
