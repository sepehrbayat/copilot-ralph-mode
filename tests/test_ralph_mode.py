#!/usr/bin/env python3
"""
Test suite for Copilot Ralph Mode (Python version)
Cross-platform tests that work on Windows, macOS, and Linux
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ralph_mode import RalphMode, VERSION


class TestRalphMode(unittest.TestCase):
    """Test cases for RalphMode class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.ralph = RalphMode(self.test_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_initial_state(self):
        """Test that Ralph mode is initially inactive."""
        self.assertFalse(self.ralph.is_active())
        self.assertIsNone(self.ralph.get_state())
    
    def test_enable_basic(self):
        """Test basic enable functionality."""
        state = self.ralph.enable("Test task")
        
        self.assertTrue(self.ralph.is_active())
        self.assertEqual(state['iteration'], 1)
        self.assertEqual(state['max_iterations'], 0)
        self.assertIsNone(state['completion_promise'])
        self.assertTrue(state['active'])
    
    def test_enable_with_options(self):
        """Test enable with max_iterations and completion_promise."""
        state = self.ralph.enable(
            prompt="Build something",
            max_iterations=10,
            completion_promise="DONE"
        )
        
        self.assertEqual(state['max_iterations'], 10)
        self.assertEqual(state['completion_promise'], "DONE")
    
    def test_enable_creates_files(self):
        """Test that enable creates all required files."""
        self.ralph.enable("Test task")
        
        self.assertTrue(self.ralph.state_file.exists())
        self.assertTrue(self.ralph.prompt_file.exists())
        self.assertTrue(self.ralph.instructions_file.exists())
        self.assertTrue(self.ralph.history_file.exists())
    
    def test_enable_when_active_raises(self):
        """Test that enabling when already active raises error."""
        self.ralph.enable("First task")
        
        with self.assertRaises(ValueError) as context:
            self.ralph.enable("Second task")
        
        self.assertIn("already active", str(context.exception))
    
    def test_disable(self):
        """Test disable functionality."""
        self.ralph.enable("Test task")
        state = self.ralph.disable()
        
        self.assertIsNotNone(state)
        self.assertFalse(self.ralph.is_active())
        self.assertFalse(self.ralph.ralph_dir.exists())
    
    def test_disable_when_inactive(self):
        """Test disable when not active returns None."""
        result = self.ralph.disable()
        self.assertIsNone(result)
    
    def test_iterate(self):
        """Test iterate functionality."""
        self.ralph.enable("Test task")
        
        state = self.ralph.iterate()
        self.assertEqual(state['iteration'], 2)
        
        state = self.ralph.iterate()
        self.assertEqual(state['iteration'], 3)
    
    def test_iterate_max_reached(self):
        """Test iterate stops at max_iterations."""
        self.ralph.enable("Test task", max_iterations=2)
        
        self.ralph.iterate()  # iteration 2
        
        with self.assertRaises(ValueError) as context:
            self.ralph.iterate()  # Should stop
        
        self.assertIn("Max iterations", str(context.exception))
        self.assertFalse(self.ralph.is_active())
    
    def test_iterate_when_inactive(self):
        """Test iterate when not active raises error."""
        with self.assertRaises(ValueError):
            self.ralph.iterate()
    
    def test_prompt_storage(self):
        """Test prompt is stored and retrieved correctly."""
        prompt = "Build a REST API\nWith multiple lines"
        self.ralph.enable(prompt)
        
        self.assertEqual(self.ralph.get_prompt(), prompt)
    
    def test_completion_promise_detection(self):
        """Test completion promise detection."""
        self.ralph.enable("Test task", completion_promise="DONE")
        
        # No promise
        self.assertFalse(self.ralph.check_completion("Some output"))
        
        # Wrong promise
        self.assertFalse(self.ralph.check_completion("<promise>WRONG</promise>"))
        
        # Correct promise
        self.assertTrue(self.ralph.check_completion("Output <promise>DONE</promise> text"))
    
    def test_complete_disables(self):
        """Test that complete() disables when promise found."""
        self.ralph.enable("Test task", completion_promise="DONE")
        
        result = self.ralph.complete("Output <promise>DONE</promise>")
        
        self.assertTrue(result)
        self.assertFalse(self.ralph.is_active())
    
    def test_complete_continues(self):
        """Test that complete() continues when promise not found."""
        self.ralph.enable("Test task", completion_promise="DONE")
        
        result = self.ralph.complete("Just some output")
        
        self.assertFalse(result)
        self.assertTrue(self.ralph.is_active())
    
    def test_status(self):
        """Test status includes all info."""
        self.ralph.enable("Test prompt", max_iterations=5, completion_promise="DONE")
        
        status = self.ralph.status()
        
        self.assertEqual(status['iteration'], 1)
        self.assertEqual(status['max_iterations'], 5)
        self.assertEqual(status['completion_promise'], "DONE")
        self.assertEqual(status['prompt'], "Test prompt")
        self.assertIn('history_entries', status)
    
    def test_history(self):
        """Test history logging."""
        self.ralph.enable("Test task")
        self.ralph.iterate()
        self.ralph.iterate()
        
        history = self.ralph.get_history()
        
        self.assertEqual(len(history), 3)  # started + 2 iterations
        self.assertEqual(history[0]['status'], 'started')
        self.assertEqual(history[1]['status'], 'iterate')
        self.assertEqual(history[2]['status'], 'iterate')

    def test_batch_init_creates_tasks(self):
        """Test batch init creates tasks and sets state."""
        tasks = [
            {"id": "HXA-0004", "title": "RTL", "prompt": "Apply RTL"},
            {"id": "HXA-0010", "title": "AI Gateway", "prompt": "Implement AI Gateway"}
        ]

        state = self.ralph.init_batch(tasks, max_iterations=20, completion_promise="DONE")

        self.assertTrue(self.ralph.is_active())
        self.assertEqual(state['mode'], 'batch')
        self.assertEqual(state['tasks_total'], 2)
        self.assertEqual(state['current_task_index'], 0)
        self.assertTrue(self.ralph.tasks_index.exists())
        self.assertTrue(self.ralph.tasks_dir.exists())

    def test_batch_next_task(self):
        """Test moving to the next task in batch mode."""
        tasks = [
            {"id": "HXA-0004", "title": "RTL", "prompt": "Apply RTL"},
            {"id": "HXA-0010", "title": "AI Gateway", "prompt": "Implement AI Gateway"}
        ]

        self.ralph.init_batch(tasks, max_iterations=20, completion_promise="DONE")
        state = self.ralph.next_task(reason="completed")

        self.assertEqual(state['current_task_index'], 1)
        self.assertEqual(state['iteration'], 1)

    def test_batch_complete_advances(self):
        """Test complete() advances to next task in batch mode."""
        tasks = [
            {"id": "HXA-0004", "title": "RTL", "prompt": "Apply RTL"},
            {"id": "HXA-0010", "title": "AI Gateway", "prompt": "Implement AI Gateway"}
        ]

        self.ralph.init_batch(tasks, max_iterations=20, completion_promise="DONE")
        self.assertTrue(self.ralph.complete("<promise>DONE</promise>"))

        state = self.ralph.get_state()
        self.assertIsNotNone(state)
        self.assertEqual(state['current_task_index'], 1)

    def test_batch_max_iterations_advances(self):
        """Test reaching max iterations advances task in batch mode."""
        tasks = [
            {"id": "HXA-0004", "title": "RTL", "prompt": "Apply RTL"},
            {"id": "HXA-0010", "title": "AI Gateway", "prompt": "Implement AI Gateway"}
        ]

        self.ralph.init_batch(tasks, max_iterations=1, completion_promise="DONE")
        state = self.ralph.iterate()

        self.assertEqual(state['current_task_index'], 1)

    def test_batch_finishes_all_tasks(self):
        """Test batch finishes and disables after last task."""
        tasks = [
            {"id": "HXA-0004", "title": "RTL", "prompt": "Apply RTL"}
        ]

        self.ralph.init_batch(tasks, max_iterations=20, completion_promise="DONE")

        with self.assertRaises(ValueError):
            self.ralph.next_task(reason="completed")

        self.assertFalse(self.ralph.is_active())
    
    def test_unicode_support(self):
        """Test Unicode characters in prompts."""
        prompt = "Build an API 🚀"
        self.ralph.enable(prompt, completion_promise="Finished!")
        
        self.assertEqual(self.ralph.get_prompt(), prompt)
        
        state = self.ralph.get_state()
        self.assertEqual(state['completion_promise'], "Finished!")
    
    def test_special_characters_in_promise(self):
        """Test special characters in completion promise."""
        self.ralph.enable("Test", completion_promise="Done! (100%)")
        
        self.assertTrue(self.ralph.check_completion("<promise>Done! (100%)</promise>"))
    
    def test_multiline_promise_content(self):
        """Test multiline content around promise."""
        self.ralph.enable("Test", completion_promise="DONE")
        
        output = """
        Some output here
        <promise>DONE</promise>
        More output
        """
        
        self.assertTrue(self.ralph.check_completion(output))


class TestCrossPlatform(unittest.TestCase):
    """Test cross-platform compatibility."""
    
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.ralph = RalphMode(self.test_dir)
    
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_path_separators(self):
        """Test path handling works on all platforms."""
        self.ralph.enable("Test")
        
        # Should work regardless of platform
        self.assertTrue(self.ralph.ralph_dir.exists())
        self.assertTrue(self.ralph.state_file.exists())
    
    def test_file_encoding(self):
        """Test UTF-8 encoding works on all platforms."""
        prompt = "Test with émojis 🎉 and unicode text"
        self.ralph.enable(prompt)
        
        # Read back and verify
        stored = self.ralph.get_prompt()
        self.assertEqual(stored, prompt)


if __name__ == '__main__':
    print(f"\n🔄 Copilot Ralph Mode Test Suite v{VERSION}")
    print("=" * 50)
    print()
    
    # Run tests with verbosity
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 50)
    if result.wasSuccessful():
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print(f"❌ {len(result.failures)} failures, {len(result.errors)} errors")
        sys.exit(1)
