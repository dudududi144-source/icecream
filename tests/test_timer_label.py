# -*- coding: utf-8 -*-

#
# IceCream - Never use print() to debug again
#
# Ansgar Grunseid
# grunseid.com
# grunseid@gmail.com
#
# License: MIT
#
"""Tests for the optional label feature of ``ic.timer``.

Three forms of ``ic.timer`` must keep working:

* ``with ic.timer('phase-one'):`` -> emits a labeled timing line that
  contains the prefix, the label, and ``' took '`` followed by the
  duration (e.g. ``ic| phase-one took 1.02ms``).

* ``with ic.timer:`` -> unchanged. Emits a bare duration with no label
  and no ``' took '``.

* ``@ic.timer`` -> unchanged. Reports the function's name with the
  ``' took '`` form (``ic| <funcname> took <duration>``).
"""

import re
import unittest

from io import StringIO
from contextlib import contextmanager

from icecream import ic, stderr_print


# Match a bare duration (units: ns, us, ms, s). Used to assert that the
# unlabeled context manager form is unchanged.
TIMER_BARE_DURATION_RE = r'(\d+\.\d{2})(ns|us|ms|s)'
# Match a labeled timing line: '<label> took <duration>'.
TIMER_LABELED_LINE_RE = (
    r'^(?P<prefix>\S+\| )?(?P<label>\S.*?) took '
    + TIMER_BARE_DURATION_RE
    + r'$'
)


@contextmanager
def capture_standard_streams():
    import sys
    realStdout = sys.stdout
    realStderr = sys.stderr
    newStdout = StringIO()
    newStderr = StringIO()
    try:
        sys.stdout = newStdout
        sys.stderr = newStderr
        yield newStdout, newStderr
    finally:
        sys.stdout = realStdout
        sys.stderr = realStderr


@contextmanager
def disable_coloring():
    """Capture raw text with no ANSI color codes (matches existing tests)."""
    originalOutputFunction = ic.outputFunction
    ic.configureOutput(outputFunction=stderr_print)
    yield
    ic.configureOutput(outputFunction=originalOutputFunction)


class TestTimerLabel(unittest.TestCase):
    """Verify that the optional label feature of ``ic.timer`` works and
    that pre-existing behavior is preserved."""

    def setUp(self):
        # Make sure ic is enabled and producing output for every test.
        ic.enable()

    # ------------------------------------------------------------------
    # R1: labeled timing block `with ic.timer('phase-one'):`
    # ------------------------------------------------------------------
    def test_labeled_block_emits_prefix_label_and_took(self):
        """`with ic.timer('phase-one'):` must include the prefix, the
        label and ``' took '`` followed by a duration."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer('phase-one'):
                x = 1 + 1  # noqa: F841 - body content is irrelevant.
            self.assertEqual(out.getvalue(), '')

        text = err.getvalue().strip()

        # The prefix must be present.
        self.assertTrue(text.startswith('ic|'),
                        msg=f'missing prefix: {text!r}')
        # The label must be present, between the prefix and ``' took '``.
        self.assertIn('phase-one', text)
        # The ' took ' separator and a duration suffix must be present.
        self.assertIn(' took ', text)
        # And the format must match the canonical labeled line pattern.
        self.assertRegex(text, TIMER_LABELED_LINE_RE)

        # The label must precede ``' took '`` (i.e. not appear as a stray
        # token appended after the duration).
        took_index = text.index(' took ')
        prefix_index = text.index('phase-one')
        self.assertLess(prefix_index, took_index,
                        msg=f'label must precede " took ": {text!r}')

    def test_labeled_block_with_empty_body_still_emits_label(self):
        """An empty body inside `with ic.timer('foo'):` still emits the
        labeled timing line."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer('foo'):
                pass
            self.assertEqual(out.getvalue(), '')

        text = err.getvalue().strip()
        self.assertTrue(text.startswith('ic|'))
        self.assertIn('foo', text)
        self.assertIn(' took ', text)
        self.assertRegex(text, TIMER_LABELED_LINE_RE)

    def test_labeled_block_label_with_special_characters(self):
        """Labels may contain spaces and dashes; they are passed through."""
        label = 'phase one-build'
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer(label):
                pass

        text = err.getvalue().strip()
        self.assertTrue(text.startswith('ic|'))
        self.assertIn(label, text)
        self.assertIn(' took ', text)

    def test_labeled_block_with_custom_prefix(self):
        """A custom prefix is respected by the labeled timer block."""
        prefix = 'timer> '
        with disable_coloring() as _:
            ic.configureOutput(prefix=prefix)
            try:
                with capture_standard_streams() as (out, err):
                    with ic.timer('phase-one'):
                        pass
            finally:
                ic.configureOutput(prefix='ic| ')

        text = err.getvalue().strip()
        self.assertTrue(text.startswith(prefix),
                        msg=f'expected custom prefix {prefix!r}, got {text!r}')
        self.assertIn('phase-one', text)
        self.assertIn(' took ', text)

    def test_labeled_block_measures_elapsed_time(self):
        """The duration reported for a labeled block is at least the time
        we slept for (within the timer resolution)."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer('phase-one'):
                import time as _t
                _t.sleep(0.05)
            self.assertEqual(out.getvalue(), '')

        text = err.getvalue().strip()
        match = re.search(TIMER_BARE_DURATION_RE, text)
        self.assertIsNotNone(match, msg=f'no duration in {text!r}')
        value, unit = float(match.group(1)), match.group(2)
        multiplier = {'ns': 1e-6, 'us': 1e-3, 'ms': 1.0, 's': 1000.0}
        self.assertGreaterEqual(value * multiplier[unit], 30.0,
                                msg=f'duration too small: {text!r}')

    def test_labeled_block_propagates_exception(self):
        """An exception inside `with ic.timer('label'):` must still cause
        the labeled timing line to be emitted (matching the unlabeled
        behavior)."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with self.assertRaises(ValueError):
                with ic.timer('boom'):
                    raise ValueError('explode')
            self.assertEqual(out.getvalue(), '')

        text = err.getvalue().strip()
        self.assertTrue(text.startswith('ic|'))
        self.assertIn('boom', text)
        self.assertIn(' took ', text)
        self.assertRegex(text, TIMER_LABELED_LINE_RE)

    def test_labeled_block_does_not_break_subsequent_unlabeled_block(self):
        """Using the labeled form must not mutate ``ic.timer`` (the
        pre-bound Timer instance) so subsequent unlabeled blocks still
        behave as today."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer('phase-one'):
                pass
            with ic.timer:
                pass
            self.assertEqual(out.getvalue(), '')

        lines = [l for l in err.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2, msg=f'expected 2 lines, got {lines!r}')

        labeled_line = lines[0].strip()
        unlabeled_line = lines[1].strip()

        # First line is labeled.
        self.assertTrue(labeled_line.startswith('ic|'))
        self.assertIn('phase-one', labeled_line)
        self.assertIn(' took ', labeled_line)

        # Second line is the bare unlabeled duration.
        self.assertNotIn(' took ', unlabeled_line,
                         msg=f'unlabeled line must not contain " took ": '
                             f'{unlabeled_line!r}')
        self.assertRegex(unlabeled_line, TIMER_BARE_DURATION_RE)

    # ------------------------------------------------------------------
    # R2: unlabeled timing block `with ic.timer:` is unchanged.
    # ------------------------------------------------------------------
    def test_unlabeled_block_bare_duration(self):
        """`with ic.timer:` outputs only a bare duration, no label, no
        ' took '."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer:
                x = 1  # noqa: F841
            self.assertEqual(out.getvalue(), '')

        text = err.getvalue().strip()
        self.assertNotIn(' took ', text,
                         msg=f'unlabeled must not contain " took ": {text!r}')
        self.assertRegex(text, TIMER_BARE_DURATION_RE)

    def test_unlabeled_block_does_not_contain_ic_prefix(self):
        """The unlabeled block must NOT include the ``ic|`` prefix; it
        must look like a bare duration."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer:
                pass
            self.assertEqual(out.getvalue(), '')

        text = err.getvalue().strip()
        self.assertFalse(text.startswith('ic|'),
                         msg=f'unlabeled must not start with prefix: {text!r}')

    # ------------------------------------------------------------------
    # R3: decorator form `@ic.timer` is unchanged.
    # ------------------------------------------------------------------
    def test_decorator_reports_function_name(self):
        """`@ic.timer` must still report the wrapped function's name with
        ``' took '`` between name and duration."""
        @ic.timer
        def work():
            return 42

        with disable_coloring(), capture_standard_streams() as (out, err):
            result = work()
            self.assertEqual(out.getvalue(), '')

        self.assertEqual(result, 42)
        text = err.getvalue().strip()
        self.assertTrue(text.startswith('ic|'),
                        msg=f'decorator must keep prefix: {text!r}')
        self.assertIn('work', text)
        self.assertIn(' took ', text)
        self.assertRegex(text, TIMER_LABELED_LINE_RE)

        # Function name must appear before ``' took '``.
        took_index = text.index(' took ')
        self.assertLess(text.index('work'), took_index,
                        msg=f'function name must precede " took ": {text!r}')

    def test_decorator_is_unaffected_by_labeled_call(self):
        """Calling ``ic.timer('label')`` must not corrupt the decorator
        behavior of subsequent ``@ic.timer`` usages."""
        with disable_coloring(), capture_standard_streams() as (out, err):
            with ic.timer('phase-one'):
                pass

            @ic.timer
            def another():
                return 'ok'

            self.assertEqual(another(), 'ok')
            self.assertEqual(out.getvalue(), '')

        lines = [l for l in err.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2, msg=f'expected 2 lines, got {lines!r}')

        # Decorator output must still report the function name with the
        # standard ' took ' format.
        dec_line = lines[1].strip()
        self.assertTrue(dec_line.startswith('ic|'))
        self.assertIn('another', dec_line)
        self.assertIn(' took ', dec_line)


if __name__ == '__main__':
    unittest.main()