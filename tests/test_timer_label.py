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

"""
Tests for the optional label support in icecream's timing context manager.

Three forms must be exercised:

  1. ``with ic.timer('label'):``     — labeled context manager.
  2. ``with ic.timer:``              — unlabeled context manager (unchanged).
  3. ``@ic.timer``                   — decorator (unchanged).

These tests intentionally FAIL against the base revision where
``ic.timer('label')`` is not a supported API and the timer cannot
distinguish between labeled and unlabeled use.
"""

import io
import re
import time
import unittest

from icecream import ic


LABEL_DURATION_RE = r"\d+\.\d{2}(ns|us|ms|s)"
BARE_DURATION_RE = r"\d+\.\d{2}(ns|us|ms|s)"


class TestTimerLabel(unittest.TestCase):
    """Behavioral tests for the optional label on ic.timer()."""

    def setUp(self):
        # Always start from a clean output configuration so tests are
        # independent regardless of what other tests have done.
        self._original_prefix = ic.prefix
        self._original_output = ic.outputFunction
        self._original_enabled = ic.enabled
        ic.configureOutput(prefix='ic| ', outputFunction=self._capture)

    def tearDown(self):
        ic.configureOutput(
            prefix=self._original_prefix,
            outputFunction=self._original_output,
        )
        ic.enabled = self._original_enabled

    def _capture(self, s):
        self._captured.write(s)

    # ---- form 1: ``with ic.timer('label'):`` ------------------------------

    def test_labeled_context_manager_emits_label_and_took(self):
        """The labeled form must include the prefix, label, and ' took '."""
        self._captured = io.StringIO()
        with ic.timer('phase-one'):
            x = 1 + 1  # noqa: F841

        out = self._captured.getvalue()
        self.assertIn('phase-one', out)
        self.assertIn(' took ', out)
        # The duration portion must still be present.
        self.assertRegex(out, LABEL_DURATION_RE)

    def test_labeled_context_manager_full_match(self):
        """Strict match against 'ic| <label> took <duration>'."""
        self._captured = io.StringIO()
        with ic.timer('phase-one'):
            pass

        out = self._captured.getvalue().strip()
        pattern = rf"^ic\| phase-one took {LABEL_DURATION_RE}$"
        self.assertRegex(out, pattern)

    def test_labeled_context_manager_uses_custom_prefix(self):
        """Custom prefixes must be honored in the labeled form too."""
        self._captured = io.StringIO()
        ic.configureOutput(prefix='timer> ', outputFunction=self._capture)
        with ic.timer('phase-one'):
            pass

        out = self._captured.getvalue().strip()
        pattern = rf"^timer> phase-one took {LABEL_DURATION_RE}$"
        self.assertRegex(out, pattern)

    def test_labeled_context_manager_measures_real_elapsed_time(self):
        """The reported duration must reflect real elapsed wall-clock time."""
        self._captured = io.StringIO()
        with ic.timer('phase-one'):
            time.sleep(0.05)

        out = self._captured.getvalue()
        match = re.search(LABEL_DURATION_RE, out)
        self.assertIsNotNone(match)
        value = float(match.group(0)[:-2])
        unit = match.group(0)[-2:]
        multiplier = {"ns": 1e-6, "us": 1e-3, "ms": 1.0, "s": 1000.0}
        duration_ms = value * multiplier[unit]
        self.assertGreater(duration_ms, 30)

    def test_labeled_context_manager_propagates_exception(self):
        """An exception inside the labeled block must still print timing."""
        self._captured = io.StringIO()
        with self.assertRaises(ValueError):
            with ic.timer('phase-one'):
                raise ValueError('boom')

        out = self._captured.getvalue()
        self.assertIn('phase-one', out)
        self.assertIn(' took ', out)
        self.assertRegex(out, LABEL_DURATION_RE)

    def test_labeled_context_manager_resets_label_after_exit(self):
        """Using a labeled block must not leak state into subsequent blocks."""
        self._captured = io.StringIO()
        with ic.timer('phase-one'):
            pass
        # A second, unlabeled block must behave like the bare form.
        self._captured = io.StringIO()
        ic.configureOutput(prefix='ic| ', outputFunction=self._capture)
        with ic.timer:
            pass

        out = self._captured.getvalue().strip()
        self.assertNotIn(' took ', out)
        self.assertNotIn('phase-one', out)
        self.assertRegex(out, rf"^{BARE_DURATION_RE}$")

    def test_labeled_context_manager_when_disabled(self):
        """Output must be silenced when icecream is disabled."""
        self._captured = io.StringIO()
        ic.enabled = False
        try:
            with ic.timer('phase-one'):
                pass
        finally:
            ic.enabled = True
        self.assertEqual(self._captured.getvalue(), '')

    # ---- form 2: ``with ic.timer:`` (unchanged) ----------------------------

    def test_unlabeled_context_manager_emits_bare_duration(self):
        """The unlabeled form must emit only the bare duration — no prefix."""
        self._captured = io.StringIO()
        with ic.timer:
            x = 1  # noqa: F841

        out = self._captured.getvalue().strip()
        self.assertNotIn(' took ', out)
        self.assertNotIn('ic|', out)
        self.assertRegex(out, rf"^{BARE_DURATION_RE}$")

    def test_unlabeled_context_manager_full_form(self):
        """Allow the formatted duration to fall through whichever unit
        ``format_duration`` chooses (ns / us / ms / s). The key invariant is
        that there is no ' took ' and no prefix.
        """
        self._captured = io.StringIO()
        with ic.timer:
            time.sleep(0.001)

        out = self._captured.getvalue().strip()
        self.assertNotIn(' took ', out)
        self.assertNotIn('ic|', out)
        # Match a bare duration with one of the supported unit suffixes.
        self.assertRegex(
            out, r"^(\d+\.\d{2})(ns|us|ms|s|m \d+\.\d{2}s|h \d+m \d+\.\d{2}s)$"
        )

    # ---- form 3: ``@ic.timer`` (unchanged) --------------------------------

    def test_decorator_form_reports_function_name(self):
        """The decorator form must continue to report the function's name."""
        self._captured = io.StringIO()

        @ic.timer
        def my_decorated_function():
            return 42

        result = my_decorated_function()
        self.assertEqual(result, 42)

        out = self._captured.getvalue().strip()
        self.assertIn('my_decorated_function', out)
        self.assertIn(' took ', out)
        pattern = rf"^ic\| my_decorated_function took {LABEL_DURATION_RE}$"
        self.assertRegex(out, pattern)

    def test_decorator_form_preserves_function_metadata(self):
        """The decorator form must still wrap the function transparently."""
        def original():
            """My docstring."""
            return 1

        wrapped = ic.timer(original)
        self.assertEqual(wrapped.__name__, 'original')
        self.assertEqual(wrapped.__doc__, 'My docstring.')

    def test_decorator_form_uses_custom_prefix(self):
        """Custom prefixes must be honored by the decorator form too."""
        self._captured = io.StringIO()
        ic.configureOutput(prefix='timer> ', outputFunction=self._capture)

        @ic.timer
        def thing():
            return 1

        thing()
        out = self._captured.getvalue().strip()
        pattern = rf"^timer> thing took {LABEL_DURATION_RE}$"
        self.assertRegex(out, pattern)

    def test_decorator_form_when_disabled(self):
        """Output must be silenced when icecream is disabled (decorator)."""
        self._captured = io.StringIO()
        ic.enabled = False
        try:
            @ic.timer
            def silence():
                return 1

            self.assertEqual(silence(), 1)
        finally:
            ic.enabled = True
        self.assertEqual(self._captured.getvalue(), '')

    def test_decorator_form_output_on_exception(self):
        """Timing must still be printed if the wrapped function raises."""
        self._captured = io.StringIO()

        @ic.timer
        def kaboom():
            raise ValueError('nope')

        with self.assertRaises(ValueError):
            kaboom()

        out = self._captured.getvalue().strip()
        pattern = rf"^ic\| kaboom took {LABEL_DURATION_RE}$"
        self.assertRegex(out, pattern)


if __name__ == '__main__':
    unittest.main()