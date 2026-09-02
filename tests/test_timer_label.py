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
"""Tests for the optional-label form of ``ic.timer``.

Three call forms are exercised:

* ``with ic.timer('phase-one'):``  -- labeled context manager; output must
  contain the configured prefix, the label and ``" took "`` followed by a
  duration in the standard ``...`` form (``ic| phase-one took 1.02ms``).

* ``with ic.timer:``               -- unlabeled context manager; output must
  be a bare duration with no label and no ``" took "`` (existing behavior).

* ``@ic.timer``                    -- decorator; output must contain the
  decorated function's ``__name__`` and ``" took "`` (existing behavior).
"""

import io
import re
import time
import unittest

from icecream import ic


# A duration suffix that the timer emits on any of its three forms.
DURATION_RE = r"\d+\.\d{2}(ns|us|ms|s|m| h|h)"


class TestTimerLabel(unittest.TestCase):
    def setUp(self):
        # Make sure each test starts from an enabled debugger.
        ic.enable()

    # ----- R1: labeled context manager --------------------------------

    def test_labeled_context_manager_emits_prefix_label_and_took(self):
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            with ic.timer('phase-one'):
                x = 1 + 1
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue()

        self.assertIn('phase-one', out)
        self.assertIn(' took ', out)
        # Must start with the configured prefix and end with a duration.
        self.assertTrue(out.startswith('ic| '), repr(out))
        self.assertRegex(out.strip(), rf'phase-one took {DURATION_RE}$')

    def test_labeled_context_manager_label_is_exactly_as_passed(self):
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            with ic.timer('my-phase'):
                pass
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue()

        self.assertRegex(out.strip(), r'^ic\| my-phase took ' + DURATION_RE + r'$')

    def test_labeled_context_manager_honors_custom_prefix(self):
        buf = io.StringIO()
        original_prefix = ic.prefix
        original_output = ic.outputFunction
        ic.configureOutput(prefix='timed> ', outputFunction=buf.write)
        try:
            with ic.timer('load-data'):
                pass
        finally:
            ic.configureOutput(prefix=original_prefix, outputFunction=original_output)
        out = buf.getvalue()

        self.assertTrue(out.startswith('timed> load-data took '), repr(out))

    def test_labeled_context_manager_when_disabled_emits_nothing(self):
        buf = io.StringIO()
        original_output = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            ic.disable()
            try:
                with ic.timer('phase-one'):
                    pass
            finally:
                ic.enable()
        finally:
            ic.configureOutput(outputFunction=original_output)
        self.assertEqual(buf.getvalue(), '')

    def test_labeled_context_manager_returns_self_via_enter(self):
        # __enter__ on the labeled Timer must return the labeled instance
        # itself (existing contract for context managers).
        t = ic.timer('phase-one')
        self.assertIs(t.__enter__(), t)
        t.__exit__(None, None, None)
        self.assertIsNone(t._enter_time)

    # ----- R2: unlabeled context manager -------------------------------

    def test_unlabeled_context_manager_is_bare_duration(self):
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            with ic.timer:
                x = 1
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue().strip()

        self.assertNotIn(' took ', out)
        self.assertRegex(out, rf'^{DURATION_RE}$')

    def test_unlabeled_context_manager_no_prefix(self):
        # The bare form must NOT include the configured ``ic| `` prefix --
        # only the duration itself. This is the behavior that must not
        # change.
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            with ic.timer:
                pass
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue()
        self.assertNotIn('ic|', out)
        self.assertNotIn(' took ', out)

    def test_unlabeled_context_manager_when_disabled_emits_nothing(self):
        buf = io.StringIO()
        original_output = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            ic.disable()
            try:
                with ic.timer:
                    pass
            finally:
                ic.enable()
        finally:
            ic.configureOutput(outputFunction=original_output)
        self.assertEqual(buf.getvalue(), '')

    # ----- R3: decorator form ------------------------------------------

    def test_decorator_reports_function_name_with_took(self):
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            @ic.timer
            def work():
                return 42
            result = work()
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue()

        self.assertEqual(result, 42)
        self.assertIn('work', out)
        self.assertIn(' took ', out)
        self.assertRegex(out.strip(), rf'^ic\| work took {DURATION_RE}$')

    def test_decorator_preserves_function_metadata(self):
        def original():
            """My docstring."""
            return

        wrapped = ic.timer(original)
        self.assertEqual(wrapped.__name__, 'original')
        self.assertEqual(wrapped.__doc__, 'My docstring.')

    def test_decorator_measures_elapsed_time(self):
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            @ic.timer
            def slow():
                time.sleep(0.05)
                return

            slow()
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue().strip()

        match = re.search(rf'^{re.escape("ic| slow took ")}(\d+\.\d{{2}})(ms|s)$', out)
        self.assertIsNotNone(match, repr(out))
        value = float(match.group(1))
        unit = match.group(2)
        duration_ms = value if unit == 'ms' else value * 1000
        self.assertGreater(duration_ms, 20)

    def test_decorator_when_disabled_emits_nothing(self):
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            ic.disable()
            try:
                @ic.timer
                def work():
                    return 42

                self.assertEqual(work(), 42)
            finally:
                ic.enable()
        finally:
            ic.configureOutput(outputFunction=original)
        self.assertEqual(buf.getvalue(), '')

    def test_decorator_reports_function_name_not_label(self):
        # Calling ic.timer('phase-one') with a function must still wrap it
        # as a decorator using the function's __name__, NOT the label.
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            @ic.timer('phase-one')  # label form, NOT decorator form
            def work():
                return 42

            result = work()
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue()
        self.assertEqual(result, 42)
        # The decorator form must report 'work', not 'phase-one'.
        self.assertIn('work', out)
        self.assertIn(' took ', out)
        self.assertRegex(out.strip(), rf'^ic\| work took {DURATION_RE}$')

    # ----- Independence: one form must not affect another --------------

    def test_each_call_to_timer_property_is_independent(self):
        # `ic.timer` must keep yielding a fresh Timer each access so that
        # unrelated contexts don't bleed into each other.
        t1 = ic.timer
        t2 = ic.timer
        self.assertIsNot(t1, t2)

    def test_label_does_not_leak_into_subsequent_unlabeled_use(self):
        buf = io.StringIO()
        original = ic.outputFunction
        ic.configureOutput(outputFunction=buf.write)
        try:
            with ic.timer('phase-one'):
                pass
            # Now a bare context manager must still emit a bare duration.
            with ic.timer:
                pass
        finally:
            ic.configureOutput(outputFunction=original)
        out = buf.getvalue()

        # Extract the labeled line and the trailing bare duration. The
        # duration group is non-capturing so we can capture the trailing
        # part cleanly with group(2).
        labeled_pat = r'ic\| phase-one took \d+\.\d{2}(?:ns|us|ms|s|m| h|h)'
        m = re.match(rf'^({labeled_pat})(.+)$', out)
        self.assertIsNotNone(m, repr(out))
        labeled, bare = m.group(1), m.group(2)
        self.assertTrue(labeled.startswith('ic| phase-one took '))
        self.assertNotIn(' took ', bare)
        self.assertRegex(bare, rf'^{DURATION_RE}$')


if __name__ == '__main__':
    unittest.main()