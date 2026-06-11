"""Unit tests for the pure diff parser (_parse) -- hermetic, fixed strings.

The I/O wrapper (list_changed_files) is exercised in test_cli.py.
"""
from audit_skills import _parse, ChangedFile


def test_parses_single_modified_file_with_added_lines():
    text = """\
diff --git a/foo.py b/foo.py
index abc..def 100644
--- a/foo.py
+++ b/foo.py
@@ -10,0 +11,2 @@ def existing():
+    print("new line 1")
+    print("new line 2")
"""
    out = _parse(text)
    assert len(out) == 1
    cf = out[0]
    assert cf.path == "foo.py"
    assert cf.status == "M"
    assert cf.added_lines == (
        (11, '    print("new line 1")'),
        (12, '    print("new line 2")'),
    )
    assert cf.rename_from is None


def test_parses_multiple_files():
    text = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -0,0 +1,1 @@
+print("a")
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -5,0 +6,1 @@
+print("b")
"""
    out = _parse(text)
    assert {cf.path for cf in out} == {"a.py", "b.py"}


def test_parses_new_file_status_A():
    text = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..abc
--- /dev/null
+++ b/new.py
@@ -0,0 +1,1 @@
+print("hello")
"""
    out = _parse(text)
    assert len(out) == 1
    assert out[0].status == "A"
    assert out[0].path == "new.py"


def test_parses_deleted_file_status_D():
    text = """\
diff --git a/gone.py b/gone.py
deleted file mode 100644
index abc..0000000
--- a/gone.py
+++ /dev/null
@@ -1,1 +0,0 @@
-print("removed")
"""
    out = _parse(text)
    assert len(out) == 1
    assert out[0].status == "D"
    assert out[0].path == "gone.py"
    assert out[0].added_lines == ()


def test_parses_rename_status_R():
    text = """\
diff --git a/old.py b/new.py
similarity index 90%
rename from old.py
rename to new.py
index abc..def 100644
--- a/old.py
+++ b/new.py
@@ -1,1 +1,1 @@
-print("old")
+print("new")
"""
    out = _parse(text)
    assert len(out) == 1
    assert out[0].status == "R"
    assert out[0].path == "new.py"
    assert out[0].rename_from == "old.py"


def test_skips_binary_file_diff():
    text = """\
diff --git a/img.png b/img.png
index abc..def 100644
Binary files a/img.png and b/img.png differ
"""
    out = _parse(text)
    # Binary diffs have no parseable hunks; emit a ChangedFile with empty
    # added_lines so the path is still visible to doc-currency scanning.
    assert len(out) == 1
    assert out[0].path == "img.png"
    assert out[0].added_lines == ()


def test_empty_diff_returns_empty_tuple():
    assert _parse("") == ()


def test_hunk_header_offset_tracks_added_line_numbers():
    text = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -100,0 +101,3 @@
+a
+b
+c
"""
    out = _parse(text)
    assert out[0].added_lines == ((101, "a"), (102, "b"), (103, "c"))


def test_multiple_hunks_in_one_file():
    text = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -10,0 +11,1 @@
+first
@@ -50,0 +52,1 @@
+second
"""
    out = _parse(text)
    assert out[0].added_lines == ((11, "first"), (52, "second"))


def test_added_line_starting_with_plus_is_preserved():
    """'+++ b/path' is a header; '++ literal' after a hunk is content."""
    text = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -0,0 +1,1 @@
+++ comment with double plus
"""
    out = _parse(text)
    assert out[0].added_lines == ((1, "++ comment with double plus"),)
