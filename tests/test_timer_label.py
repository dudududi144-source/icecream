#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# IceCream - Never use print() to debug again
#
# Tests for the optional-label behavior of icecream's timing context manager.
#
# Three forms are exercised:
#   1) ``with ic.timer('label'):``     -> "<prefix><label> took <duration>"
#   2) ``with ic.timer:``              -> bare "<duration>" (no label, no " took ")
#   3) ``@ic.timer``                   -> "<prefix><func_name> took <duration>"
#
# All three forms are validated against the existing timer format regex
# (``TIMER_DURATION_RE``) and the project default prefix (``ic| ``).
#
# These tests are written to FAIL on the pristine base revision (which
# rejected ``ic.timer('phase-one')`` by raising ``TypeError`` because the
# decorator path only accepted a callable) and PASS with the implementation
# change that allows a single string argument to be treated as a label.
#

import re
import unittest

from io import StringIO
from contextlib import contextmanager

from icecream import ic
from icecream.icecream import stderr_print


# A duration such as "1.02ms" / "1.20s" / "950.00ns" / "1m 2.00s" / etc.
TIMER_DURATION_RE = r'\d+\.\d{2}(ns|us|ms|s)'
DEFAULT_PREFIX = 'ic| '


@contextmanager
def capture_output():
    """Capture output written via ic.outputFunction into an in-memory buffer.

    The output function is restored after the context exits.
    """
    buf = StringIO()
    original = ic.outputFunction
    ic.configureOutput(outputFunction=buf.write)
    try:
        yield buf
    finally:
        ic.configureOutput(outputFunction=original)


class TestTimerLabelContextManager(unittest.TestCase):
    """``with ic.timer('label'): ...`` reports the prefix, label, and duration."""

    def test_label_appears_in_output(self):
        with capture_output() as buf:
            with ic.timer('phase-one'):
                x = 1 + 1

        out = buf.getvalue()
        # The label must be present and must be followed by " took ".
        self.assertIn('phase-one', out)
        self.assertIn(' took ', out)

    def test_label_uses_default_prefix(self):
        with capture_output() as buf:
            with ic.timer('phase-one'):
                pass

        out = buf.getvalue().strip()
        # Whole-line format: "<prefix><label> took <duration>"
        pattern = r'^' + re.escape(DEFAULT_PREFIX) + r'phase-one took ' + TIMER_DURATION_RE + r'$'
        self.assertRegex(out, pattern)

    def test_label_respects_custom_prefix(self):
        custom_prefix = 'timer> '
        original_prefix = ic.prefix
        ic.configureOutput(prefix=custom_prefix, outputFunction=lambda s: None)
        try:
            buf = StringIO()
            ic.configureOutput(outputFunction=buf.write)
            try:
                with ic.timer('phase-two'):
                    pass
                out = buf.getvalue().strip()
                pattern = r'^' + re.escape(custom_prefix) + r'phase-two took ' + TIMER_DURATION_RE + r'$'
                self.assertRegex(out, pattern)
            finally:
                ic.configureOutput(outputFunction=lambda s: None)
        finally:
            ic.configureOutput(prefix=original_prefix)

    def test_label_reusable(self):
        # The Timer returned by ``ic.timer('label')`` must be re-usable as a
        # context manager just like ``ic.timer`` itself.
        labeled = ic.timer('reusable')
        with capture_output() as buf:
            with labeled:
                pass
            with labeled:
                pass

        out = buf.getvalue()
        self.assertEqual(out.count('reusable'), 2)
        self.assertEqual(out.count(' took '), 2)

    def test_label_propagates_exception(self):
        # Exceptions raised inside the labeled block must still produce
        # the labeled timing output (mirrors the unlabeled behavior).
        with self.assertRaises(ValueError):
            with capture_output() as buf:
                with ic.timer('boom'):
                    raise ValueError('kaboom')

        out = buf.getvalue()
        self.assertIn('boom', out)
        self.assertIn(' took ', out)


class TestTimerUnlabeledContextManager(unittest.TestCase):
    """``with ic.timer: ...`` is unchanged: bare duration, no ' took '."""

    def test_unlabeled_outputs_bare_duration(self):
        with capture_output() as buf:
            with ic.timer:
                x = 1 + 1

        out = buf.getvalue().strip()
        # No ' took ' and no 'ic| ' prefix in the unlabeled form.
        self.assertNotIn(' took ', out)
        self.assertNotIn(DEFAULT_PREFIX, out)
        self.assertRegex(out, r'^' + TIMER_DURATION_RE + r'$')

    def test_unlabeled_does_not_print_label(self):
        with capture_output() as buf:
            with ic.timer:
                pass

        out = buf.getvalue().strip()
        self.assertNotIn('ic|', out)
        self.assertNotIn(' took ', out)
        # Must end with a valid duration unit suffix.
        self.assertRegex(out, r'(ns|us|ms|s)$')


class TestTimerDecoratorUnchanged(unittest.TestCase):
    """``@ic.timer`` still reports the function's name with ' took '."""

    def test_decorator_reports_function_name(self):
        @ic.timer
        def work():
            return 42

        with capture_output() as buf:
            self.assertEqual(work(), 42)

        out = buf.getvalue()
        self.assertIn('work', out)
        self.assertIn(' took ', out)

    def test_decorator_format_with_default_prefix(self):
        @ic.timer
        def something_specific():
            return None

        with capture_output() as buf:
            something_specific()

        out = buf.getvalue().strip()
        pattern = r'^' + re.escape(DEFAULT_PREFIX) + r'something_specific took ' + TIMER_DURATION_RE + r'$'
        self.assertRegex(out, pattern)

    def test_decorator_callable_form_unchanged(self):
        # ``ic.timer(func)`` should still wrap and report ``func.__name__``.
        def do_thing():
            return 7

        wrapped = ic.timer(do_thing)
        with capture_output() as buf:
            self.assertEqual(wrapped(), 7)

        out = buf.getvalue()
        self.assertIn('do_thing', out)
        self.assertIn(' took ', out)


class TestTimerLabelIsolation(unittest.TestCase):
    """A labeled timer must not affect later uses of the bare ``ic.timer``."""

    def test_label_then_bare(self):
        with capture_output() as buf:
            with ic.timer('phase-A'):
                pass
            with ic.timer:
                pass

        out = buf.getvalue()
        # First line: labeled
        self.assertIn('phase-A', out)
        # ' took ' appears only for the labeled line.
        self.assertEqual(out.count(' took '), 1)


if __name__ == '__main__':
    unittest.main()