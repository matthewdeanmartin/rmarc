
# Phase 2: Generic Rewrite Plan

## Objective

Replace the stub with a real implementation in Rust while exposing a Python interface that is compatible, or as compatible as practical, with the target Python library.

Phase 2 is where behavior, data model, parsing, serialization, and compatibility work happen.

---

## Phase 2 Guiding Principle

The rewrite should preserve the **public user experience** more than the internal design.

If a choice must be made, prefer:

* Python API familiarity
* clear migration path
* behavioral correctness
* explicit documented differences

over reproducing the original internals.

---

## Phase 2 Deliverables

The implementing agent should produce:

* a Rust implementation of the core domain model
* Python bindings for the public API surface
* tests covering compatibility expectations
* fixtures or examples representing real-world use
* migration notes for unsupported or intentionally changed behavior
* performance and correctness validation at a basic level

---

## Phase 2 Workstreams

### A. Public API inventory

Before implementation, the agent should identify the public interface to preserve.

This should include:

* top-level functions
* classes
* constructors
* methods
* common attributes/properties
* iteration behavior
* exceptions
* serialization and deserialization entry points
* equality or repr/str behavior if user-visible

The inventory should focus on what users import and call, not private internals.

### B. Data model design in Rust

The agent should define Rust-native data structures corresponding to the target library’s main concepts.

These should:

* model the domain cleanly
* preserve user-visible semantics where practical
* separate owned data from transient parsing state
* allow future validation and transformation logic
* support conversion into Python-friendly forms

### C. Python binding design

Bindings should preserve familiar Python behavior where practical, including:

* constructor signatures
* property access patterns
* iteration
* indexing if appropriate
* string conversion / representation
* exception semantics

Where Python conventions and Rust ownership differ, the Python-facing behavior should win unless the performance cost is unreasonable.

### D. Compatibility layer

A compatibility layer may be required.

This may include:

* alias names
* deprecated parameter handling
* convenience constructors
* pure-Python wrappers around Rust-backed internals
* compatibility exceptions
* normalized return types

The compatibility layer should be thin and well documented.

### E. Incremental feature migration

The rewrite should proceed in slices, not all at once.

Recommended sequence:

1. core model objects
2. read/parse path
3. write/serialize path
4. field access and mutation operations
5. convenience APIs
6. edge-case behavior and legacy quirks
7. performance passes

### F. Test strategy

Phase 2 should use multiple levels of tests:

* unit tests for Rust internals
* Python-facing behavior tests
* compatibility tests against documented behavior
* fixture-driven tests using representative sample data
* regression tests for bugs found during migration

If the original library can be installed independently, black-box comparison tests are desirable, but this spec does not require them.

---

## Phase 2 Functional Requirements

### 1. Stable import surface

The final package must expose the expected import path and major public symbols.

### 2. Core object model implemented

The main user-facing objects must exist and support the expected common operations.

### 3. Read/parse functionality implemented

If the original library reads structured input, that pathway must be implemented with:

* success behavior for valid input
* useful exceptions for invalid input
* deterministic handling of malformed cases where possible

### 4. Write/serialize functionality implemented

If the original library emits structured output, serialization must be supported in a form acceptable to existing users.

### 5. Common mutation and inspection operations implemented

Typical user workflows must be possible, such as:

* create
* inspect
* modify
* serialize
* reload or round-trip

### 6. Exceptions documented and mapped

Rust errors must become Python exceptions with predictable behavior.

### 7. Reasonable compatibility preserved

The rewrite should preserve expected behavior for the common case even if rare edge cases differ initially.

Any known incompatibilities must be documented explicitly.

---

## Phase 2 Non-Functional Requirements

### Performance

The rewrite should not be slower than the original in the common case unless compatibility demands it.

Performance improvement is desirable but secondary to correctness early in Phase 2.

### Safety

Rust implementation should prefer safe code.

Unsafe code should be minimized, justified, and isolated.

### Maintainability

The Rust core should be structured so future contributors can understand:

* parsing path
* object model
* Python translation layer
* serialization path
* error flow

### Debuggability

Errors should include enough context for developers to diagnose failures.

### Packaging continuity

All packaging and install workflows proven in Phase 1 must continue to work in Phase 2.

---

## Phase 2 Suggested Milestones

### Milestone 2.1: API skeleton replacement

Replace Phase 1 placeholders with real object shells and documented method signatures.

### Milestone 2.2: Core model parity

Implement the primary in-memory objects and common manipulations.

### Milestone 2.3: Parsing parity

Implement read path for representative input.

### Milestone 2.4: Serialization parity

Implement write path and round-trip tests.

### Milestone 2.5: Compatibility polish

Handle edge cases, aliases, convenience APIs, and error semantics.

### Milestone 2.6: Performance and packaging polish

Optimize hotspots and ensure build/install/test story remains smooth.

---

## Phase 2 Acceptance Criteria

Phase 2 is complete when:

* the package installs cleanly
* the package imports cleanly
* the main public API surface is implemented
* common user workflows succeed
* smoke tests and compatibility tests pass
* documented known differences are small and explicit
* packaging produces installable artifacts
* a migration-minded user can adopt the rewrite with minimal code change

---

# Cross-Phase Rules

## Naming stability

The project should decide package names early and avoid renaming after Phase 1 unless unavoidable.

## Documentation continuity

Phase 1 setup instructions should remain valid in Phase 2, with only additive updates.

## No premature overengineering

Phase 1 should not implement speculative abstractions unrelated to proving the stack.

## No throwaway bootstrap if avoidable

Phase 1 code should be simple, but it should be structured to survive into Phase 2 where sensible.

---

# Handoff Notes for the Next Bots

## For the implementation-spec bot

That bot should elaborate:

* concrete repo layout
* exact package/module naming
* exact commands for build/install/test
* recommended binding patterns
* test matrix
* error translation strategy
* compatibility prioritization strategy

## For the conversion bot

That bot should:

* preserve Phase 1 packaging workflow
* preserve public import surface
* implement features incrementally
* avoid rewriting the bootstrap structure unless necessary
* document every deliberate incompatibility

---

# Minimal Success Definition

If everything else slips, the minimum acceptable outcome is:

* Phase 1: a Python-installable Rust-backed package that imports and executes one Rust function and one Rust class method
* Phase 2: a real Rust implementation behind a Python-facing API that covers the common public workflows of the original library
