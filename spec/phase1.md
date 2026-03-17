# Spec: Two-Phase Rust + Python Rewrite Project

## Purpose

Create a replacement implementation for an existing Python library using a Rust core with Python bindings.

This specification is intentionally split into two phases:

* **Phase 1** proves the project skeleton, toolchain, packaging, and Python invocation path.
* **Phase 2** performs the actual rewrite behind a Python-compatible interface.

This document is deliberately generic. It does **not** assume access to the original source code, internal design, or exact behavior beyond what can be inferred from public usage patterns and packaging expectations.

---

# Goals

The project should:

* use **Rust** for the native implementation
* expose a **Python package** importable from Python
* support local development and packaging into installable artifacts
* establish a path toward **interface compatibility** with an existing Python library
* allow Phase 1 to complete without implementing real business logic
* allow Phase 2 to proceed incrementally, with compatibility work and feature parity separated from packaging/bootstrap concerns

---

# Non-Goals

This spec does not require:

* exact behavioral parity in Phase 1
* knowledge of the original internal implementation
* a full reverse-engineering effort
* optimization beyond reasonable architectural choices
* ABI stability for non-Python consumers
* support for non-Python language bindings

---

# High-Level Architecture

The final system should have three layers:

1. **Rust core**

   * owns the main data structures and future implementation
   * contains parsing, serialization, validation, and transformation logic as applicable

2. **Python binding layer**

   * exposes Python-callable classes and functions
   * maps Rust errors into Python exceptions
   * provides Python-friendly method names and return types

3. **Python package surface**

   * gives users an import path and module layout consistent with the intended compatibility target
   * may include thin pure-Python adapter code if needed

---

# Phase 1: Bootstrap, Build, Package, and Invoke

## Objective

Create an empty but working project that proves all of the following:

* the Rust crate builds
* the Python extension module builds
* the package can be installed in a Python environment
* Python can import the package
* Python can call into Rust successfully
* packaging structure is suitable for later expansion

Phase 1 is a toolchain and packaging proof, not a feature implementation.

---

## Phase 1 Deliverables

The implementing agent should produce:

* a Rust crate configured for Python bindings
* a Python package directory
* packaging metadata
* a minimal exported Rust-backed Python API
* a minimal automated test suite
* a short README for local developer usage
* a basic CI-ready build/test command sequence

---

## Phase 1 Functional Requirements

### 1. Project layout

The repository should have a clean layout separating:

* Rust source
* Python packaging metadata
* Python tests
* project documentation

The exact directory names may vary, but the structure must make it obvious where:

* Rust code lives
* Python import surface lives
* tests live
* build metadata lives

### 2. Rust extension module exists

The project must define a minimal Rust-backed Python extension module.

It must expose at least one of the following:

* a function that returns a fixed string, version string, or health-check value
* a class with a trivial constructor and at least one method

Preferred pattern:

* one small function proving function export
* one small class proving object export

### 3. Python import path works

A Python user must be able to do the equivalent of:

* import the package
* call a Rust-backed function
* instantiate a Rust-backed class

The import path selected in Phase 1 must be the same path intended for the final package unless there is a compelling migration reason.

### 4. Local editable-style developer workflow exists

A developer must be able to:

* create a Python virtual environment
* install or develop the package locally
* rebuild after Rust changes
* rerun tests without manual artifact cleanup

This workflow should be documented clearly enough that a new contributor can reproduce it.

### 5. Packaging proof exists

Phase 1 must prove that the project can produce distributable artifacts.

At minimum:

* source distribution or equivalent packaging metadata is valid
* wheel build succeeds
* built artifact installs into a clean environment
* installed package imports correctly

### 6. Minimal test coverage exists

Tests must verify:

* import succeeds
* exported function returns expected value
* exported class can be instantiated
* a method call crosses the Rust/Python boundary correctly

These tests are smoke tests, not feature tests.

---

## Phase 1 Technical Requirements

### Rust-side requirements

The Rust portion should:

* compile cleanly
* avoid placeholder unsafe code unless absolutely required
* define at least one simple struct for later expansion
* define a minimal error-handling pattern suitable for future translation into Python exceptions
* keep public Rust APIs organized for future growth

The Rust stub should not be a throwaway toy if avoidable. Even if behavior is trivial, the module structure should anticipate Phase 2.

### Python-side requirements

The Python side should:

* present a stable package name
* provide an import experience suitable for end users
* avoid unnecessary Python logic in Phase 1
* include type-hint-friendly interfaces where practical
* leave room for future compatibility shims

### Build and packaging requirements

The project should:

* support reproducible local builds
* support wheel creation
* avoid hand-edited compiled artifacts in version control
* use a modern Python packaging layout
* document exactly how to build, install, and test

### Testing requirements

The test suite should be runnable with one obvious command.

Tests should be small, deterministic, and local-only.

No network dependency should exist in Phase 1.

---

## Phase 1 Acceptance Criteria

Phase 1 is complete when a fresh developer can:

1. clone the repository
2. create a virtual environment
3. install the package locally
4. run tests successfully
5. import the package in Python
6. call the Rust-backed stub successfully
7. build a wheel
8. install that wheel in a clean environment
9. import and invoke the package successfully there too

---

## Phase 1 Suggested API Shape

Because the final project is intended to rewrite an existing Python library, the Phase 1 API should already resemble a future real package.

Suggested minimum shape:

* package top-level import
* one exported version or health-check function
* one exported placeholder class representing the eventual core object model

Example intent, not literal code:

* top-level function: returns a fixed success marker
* placeholder class: constructible from Python, with one no-op or metadata method

This gives later agents a stable place to attach the real implementation.

---

## Phase 1 Risks

The implementing agent should watch for:

* import-name mismatches between Python package and native module
* wheel builds that succeed but do not import
* confusion between Rust crate name and Python package name
* accidental reliance on local machine state
* missing runtime artifacts in built distributions
* tests that pass only in editable/developer mode

---

## Phase 1 Output Artifacts

Expected artifacts from the implementing agent:

* repository skeleton
* minimal Rust module
* Python packaging metadata
* smoke tests
* build/install instructions
* short note documenting known limitations
