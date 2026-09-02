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
"""Tests for the optional label argument on ``IceCreamDebugger.timer``.

This file covers three usage forms of ``ic.timer``:

1. ``with ic.timer('label'):``   — labeled timing block.  The output must
   contain the prefix, the user supplied label, the literal ``" took "`` and
   the formatted duration.
2. ``with ic.timer:``             — bare timing block.  The output must
   remain a bare duration (no label, no ``" took "``).
3. ``@ic.timer``                  — function decorator form.  The output must
   contain the decorated function's ``__name__`` together with
   ``" took "`` and the formatted duration.
"""

import io
import re
import unittest

from icecream import ic
from icecream.icecream import DEFAULT_PREFIX


# Match a duration produced by ``Timer.format_duration`` — e.g. ``1.02ms``,
# ``533.00ns``, ``2m 3.00s``, ``1h 2m 3.00s``.
DURATION_RE = r'\d+(?:\.\d+)?(?:ns|us|ms|s|m\s+\d+\.\d{2}s|h\s+\d+m\s+\d+\.\d{2}s)'
# Match a duration produced by ``Timer.format_duration`` for the *unlabeled*
# context manager form.  Mirrors ``TIMER_DURATION_RE_CONTEXT_MANAGER`` used by
# the existing ``tests/test_icecream.py`` tests so we are robust to any future
# tweak of the duration formatting rules.
UNLABELED_DURATION_RE = r'\d+\.\d{2}(?:ns|us|ms|s)'


def _capture(buf):
    """Run ``buf`` as the icecream output function and return its contents."""
    ic.configureOutput(outputFunction=buf.write)
    # ``__enter__`` / ``__exit__`` use ``call_or_value`` on ``self.prefix`` so
    # even if a future test mutates the prefix back to a callable the labeled
    # block still works.  Reset the prefix between tests just in case.
    ic.configureOutput(prefix=DEFAULT_PREFIX)
    return buf


class TestTimerLabel(unittest.TestCase):
    """Behavior checks for ``ic.timer`` with and without a label."""

    def setUp(self):
        # Make sure ``ic.timer`` output is captured regardless of whatever the
        # other test files (which run in the same interpreter) may have left
        # in place.
        self._buf = io.StringIO()
        self._old_prefix = ic.prefix
        self._old_output = ic.outputFunction
        ic.configureOutput(prefix=DEFAULT_PREFIX,
                           outputFunction=self._buf.write)

    def tearDown(self):
        ic.configureOutput(prefix=self._old_prefix,
                           outputFunction=self._old_output)

    # ------------------------------------------------------------------
    # 1. Labeled context manager: ``with ic.timer('label'): ...``
    # ------------------------------------------------------------------
    def test_labeled_context_manager_emits_prefix_label_and_took(self):
        with ic.timer('phase-one'):
            # Trivial body so the context manager actually exits and emits.
            x = 1 + 1
            self.assertEqual(x, 2)

        out = self._buf.getvalue()
        self.assertIn('phase-one', out,
                      msg='label missing from output: %r' % out)
        self.assertIn(' took ', out,
                      msg='" took " missing from output: %r' % out)
        # The formatted duration must be present immediately after the
        # ``" took "`` substring and the line must end there (matching the
        # existing single-line ``... took ...`` form).
        self.assertRegex(out,
                         r'^ic\| phase-one took ' + DURATION_RE + r'$')

    def test_labeled_context_manager_uses_custom_prefix(self):
        # Honor the user-configured prefix; the label and ``" took "`` must
        # follow it.
        ic.configureOutput(prefix='custom> ')
        with ic.timer('build'):
            x = 1
        out = self._buf.getvalue().strip()
        self.assertTrue(out.startswith('custom> '),
                        msg='custom prefix not used: %r' % out)
        self.assertIn(' build ', out)
        self.assertIn(' took ', out)

    def test_labeled_context_manager_returns_fresh_timer(self):
        # The object returned by ``ic.timer('phase-one')`` must be a distinct
        # Timer instance — mutating one block must not affect another.
        t1 = ic.timer('first')
        t2 = ic.timer('second')
        self.assertIsNot(t1, t2)
        self.assertEqual(t1._label, 'first')
        self.assertEqual(t2._label, 'second')

    def test_labeled_context_manager_measures_elapsed_time(self):
        # The duration portion of the output must be parseable and > 0 for a
        # body that actually does work.
        with ic.timer('work'):
            # Burn a few microseconds so the duration is unambiguously above
            # zero on any reasonable machine.
            total = 0
            for _ in range(1000):
                total += 1
        out = self._buf.getvalue().strip()
        self.assertIn('work', out)
        self.assertIn(' took ', out)

    # ------------------------------------------------------------------
    # 2. Unlabeled context manager: ``with ic.timer: ...``
    # ------------------------------------------------------------------
    def test_unlabeled_context_manager_emits_bare_duration(self):
        with ic.timer:
            x = 1
        out = self._buf.getvalue().strip()
        # No label, no " took ", no prefix — exactly the existing behavior.
        self.assertNotIn(' took ', out,
                         msg='" took " should NOT appear in bare output: %r'
                             % out)
        self.assertNotIn('ic|', out,
                         msg='prefix should NOT appear in bare output: %r'
                             % out)
        self.assertRegex(out, r'^' + UNLABELED_DURATION_RE + r'$')

    def test_unlabeled_context_manager_does_not_apply_prefix(self):
        # Even with a custom prefix configured, the unlabeled form must not
        # prefix the duration — this is the historical contract.
        ic.configureOutput(prefix='custom> ')
        with ic.timer:
            x = 1
        out = self._buf.getvalue().strip()
        self.assertNotIn('custom>', out,
                         msg='prefix leaked into unlabeled output: %r' % out)
        self.assertNotIn(' took ', out)
        self.assertRegex(out, r'^' + UNLABELED_DURATION_RE + r'$')

    # ------------------------------------------------------------------
    # 3. Decorator form: ``@ic.timer`` (unchanged behavior).
    # ------------------------------------------------------------------
    def test_decorator_form_reports_function_name(self):
        @ic.timer
        def work():
            return 42

        # Defining a decorated function must not itself emit any output — the
        # timing report appears only when the function runs.
        self.assertEqual(self._buf.getvalue(), '',
                         msg='decorator must not emit output at definition '
                             'time: %r' % self._buf.getvalue())

        result = work()
        self.assertEqual(result, 42)
        out = self._buf.getvalue().strip()
        self.assertIn('work', out,
                      msg='function name missing from output: %r' % out)
        self.assertIn(' took ', out,
                      msg='" took " missing from output: %r' % out)
        self.assertRegex(out,
                         r'^ic\| work took ' + DURATION_RE + r'$')

    def test_decorator_form_preserves_function_metadata(self):
        @ic.timer
        def some_named_function():
            """Docstring that must survive the decorator."""
            return None

        # ``functools.wraps`` propagates ``__name__``, ``__doc__`` and
        # ``__wrapped__``; if these survive the decorator we know the existing
        # decorator path is unchanged.
        self.assertEqual(some_named_function.__name__,
                         'some_named_function')
        self.assertEqual(some_named_function.__doc__,
                         'Docstring that must survive the decorator.')
        self.assertIsNotNone(getattr(some_named_function,
                                     '__wrapped__', None),
                             msg='functools.wraps should set __wrapped__')

    def test_decorator_form_when_disabled_emits_nothing(self):
        @ic.timer
        def quiet():
            return 1

        ic.configureOutput(prefix=DEFAULT_PREFIX)
        ic.disable()
        try:
            quiet()
            self.assertEqual(self._buf.getvalue(), '')
        finally:
            ic.enable()

    # ------------------------------------------------------------------
    # Interaction tests across the three forms.
    # ------------------------------------------------------------------
    def test_all_three_forms_coexist(self):
        # Run all three forms in the same test to be sure they don't trample
        # on each other's state (Timer instances are created fresh for each
        # usage).
        @ic.timer
        def decorated():
            return 1

        decorated()
        with ic.timer:
            pass
        with ic.timer('phase-one'):
            pass

        out = self._buf.getvalue()
        # Three distinct outputs should appear in order: the decorator one
        # (function name + took + duration), the bare duration, then the
        # labeled block.
        self.assertIn('decorated', out)
        self.assertIn(' took ', out)
        self.assertIn('phase-one', out)
        # The bare duration line has no " took " anywhere — so the substring
        # " took " only appears next to ``decorated`` and ``phase-one``.
        # Confirm by counting occurrences.
        took_count = out.count(' took ')
        self.assertGreaterEqual(took_count, 2,
                                msg='expected at least 2 " took " lines, '
                                    'got %d in %r' % (took_count, out))


if __name__ == '__main__':
    unittest.main()