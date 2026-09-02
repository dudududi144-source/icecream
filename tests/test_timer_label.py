# -*- coding: utf-8 -*-

#
# IceCream - Never use print() to debug again
#
# Tests for the optional label form of the timer context manager:
#
#   with ic.timer:                  -> bare duration (no prefix, no ' took ')
#   with ic.timer('phase-one'):     -> '<prefix><label> took <duration>'
#   @ic.timer                       -> '<prefix><func_name> took <duration>'
#
# The unlabeled and decorator forms must remain byte-for-byte identical to
# the existing behavior. Only the labeled form is new.
#
import io
import re
import unittest

from contextlib import contextmanager

import icecream  # noqa: F401  -- ensures the package is importable
from icecream import ic


def _make_line_buffer():
    """Return a (StringIO, writer) pair where the writer adds a newline
    after every write. The default ic output is a print-style sink, so
    outputs are line-oriented and not concatenated together.
    """
    buf = io.StringIO()

    def writer(s):
        buf.write(s)
        if not s.endswith('\n'):
            buf.write('\n')

    return buf, writer


# Matches a bare duration with the existing time-unit suffixes used by
# ``Timer.format_duration`` (ns/us/ms/s/m/h).
BARE_DURATION_RE = re.compile(r'^\d+\.\d{2}(ns|us|ms|s|m \d+\.\d{2}s|h \d+m \d+\.\d{2}s)$')

# Matches the new labeled context-manager output: <prefix><label> took <duration>.
LABELED_RE = re.compile(r'^ic\| [^ ]+ took \d+\.\d{2}(ns|us|ms|s|m \d+\.\d{2}s|h \d+m \d+\.\d{2}s)$')

# Matches the decorator form: <prefix><func_name> took <duration>.
DECORATOR_RE = re.compile(r'^ic\| \w+ took \d+\.\d{2}(ns|us|ms|s|m \d+\.\d{2}s|h \d+m \d+\.\d{2}s)$')


@contextmanager
def output_to_line_buffer():
    """Route ic() / ic.timer output to a StringIO buffer with one entry
    per line, matching ic's print-style default output.
    """
    real = ic.outputFunction
    buf, writer = _make_line_buffer()
    ic.configureOutput(outputFunction=writer)
    try:
        yield buf
    finally:
        ic.configureOutput(outputFunction=real)


class TestTimerLabel(unittest.TestCase):
    """
    The new optional label form of the timer context manager.

    Three behavioral contracts are exercised here:

    1. ``with ic.timer('phase-one'):`` produces
       ``ic| phase-one took <duration>``.

    2. ``with ic.timer:`` (no label) is byte-for-byte unchanged: a bare
       duration string with no prefix and no ' took '.

    3. ``@ic.timer`` on a function still produces
       ``ic| <func_name> took <duration>``.
    """

    def setUp(self):
        # Always operate on a freshly configured ic, so test order or prior
        # state in the module can't leak into the assertions.
        ic.configureOutput(prefix='ic| ')
        ic.enabled = True

    # ------------------------------------------------------------------
    # Labeled context-manager form:  with ic.timer('phase-one'):
    # ------------------------------------------------------------------
    def test_labeled_context_manager_contains_prefix_label_and_took(self):
        with output_to_line_buffer() as buf:
            with ic.timer('phase-one'):
                x = 1 + 1  # noqa: F841

        out = buf.getvalue()
        # The required parts must all be present, in the documented form.
        self.assertIn('phase-one', out)
        self.assertIn(' took ', out)
        # The default prefix must precede the label.
        self.assertIn('ic| phase-one', out)

    def test_labeled_context_manager_matches_full_pattern(self):
        with output_to_line_buffer() as buf:
            with ic.timer('phase-one'):
                pass

        out = buf.getvalue().strip()
        self.assertRegex(out, LABELED_RE,
                         'expected "ic| <label> took <duration>", got: %r' % out)

    def test_labeled_context_manager_distinct_labels(self):
        # Two consecutive labeled blocks must each carry their own label
        # and must not bleed into each other.
        with output_to_line_buffer() as buf:
            with ic.timer('phase-one'):
                pass
            with ic.timer('phase-two'):
                pass

        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn('phase-one', lines[0])
        self.assertNotIn('phase-two', lines[0])
        self.assertIn('phase-two', lines[1])
        self.assertNotIn('phase-one', lines[1])
        for ln in lines:
            self.assertIn(' took ', ln)

    def test_labeled_context_manager_respects_custom_prefix(self):
        # The configured prefix is honored by the labeled form too.
        ic.configureOutput(prefix='debug| ')
        with output_to_line_buffer() as buf:
            with ic.timer('phase-one'):
                pass

        out = buf.getvalue()
        self.assertIn('debug| phase-one took ', out)
        self.assertNotIn('ic| phase-one', out)

    # ------------------------------------------------------------------
    # Unlabeled context-manager form:  with ic.timer:
    # Behavior must be EXACTLY identical to the pre-existing form.
    # ------------------------------------------------------------------
    def test_unlabeled_context_manager_is_bare_duration(self):
        with output_to_line_buffer() as buf:
            with ic.timer:
                x = 1  # noqa: F841

        out = buf.getvalue().strip()
        # The output must NOT contain the prefix or ' took ' — that is the
        # whole point of preserving the original behavior.
        self.assertNotIn('ic|', out)
        self.assertNotIn(' took ', out)
        # And it must look like a bare duration.
        self.assertRegex(out, BARE_DURATION_RE,
                         'expected a bare duration, got: %r' % out)

    def test_unlabeled_context_manager_unchanged_under_repeated_use(self):
        # Re-entering the unlabeled context manager repeatedly should
        # still produce bare durations (no state leaks into the output).
        with output_to_line_buffer() as buf:
            for _ in range(3):
                with ic.timer:
                    pass

        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertNotIn(' took ', line)
            self.assertNotIn('ic|', line)
            self.assertRegex(line, BARE_DURATION_RE)

    # ------------------------------------------------------------------
    # Decorator form:  @ic.timer
    # Must remain unchanged: still reports the function's name with
    # ' took ' and the prefix.
    # ------------------------------------------------------------------
    def test_decorator_form_reports_function_name(self):
        with output_to_line_buffer() as buf:
            @ic.timer
            def work():
                return 42

            work()

        out = buf.getvalue()
        self.assertIn('work', out)
        self.assertIn(' took ', out)
        self.assertIn('ic| work', out)

    def test_decorator_form_matches_full_pattern(self):
        with output_to_line_buffer() as buf:
            @ic.timer
            def some_named_function():
                return None

            some_named_function()

        out = buf.getvalue().strip()
        self.assertRegex(out, DECORATOR_RE,
                         'expected "ic| <name> took <duration>", got: %r' % out)

    def test_decorator_form_preserves_function_metadata(self):
        # functools.wraps must still be applied, so __name__/__doc__ survive.
        @ic.timer
        def decorated_target():
            """original docstring"""
            return None

        self.assertEqual(decorated_target.__name__, 'decorated_target')
        self.assertEqual(decorated_target.__doc__, 'original docstring')

    def test_decorator_form_ignores_label_kwarg_conflict(self):
        # The decorator form takes a callable, not a string. Even if the
        # only argument happens to be a callable, the decorator branch
        # must be selected (not the label branch).
        with output_to_line_buffer() as buf:
            @ic.timer
            def labeled_decorator_target():
                return 1

            labeled_decorator_target()

        out = buf.getvalue()
        self.assertIn('labeled_decorator_target', out)
        self.assertIn(' took ', out)
        # The literal decorator name is NOT a label, so the function-name
        # form should match the decorator regex (no extra label).
        self.assertRegex(out.strip(), DECORATOR_RE)


if __name__ == '__main__':
    unittest.main()
