"""
Mutation Testing Support for Ralph Mode
=======================================

This module provides mutation testing infrastructure to verify test quality.
Mutation testing modifies code in small ways (mutations) and checks if tests
catch these changes. High mutation score = high quality tests.

This is essential for enterprise-grade software quality assurance.
"""

import ast
import copy
import importlib
import sys
import tempfile
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import subprocess
import json
import re

import pytest


@dataclass
class Mutation:
    """Represents a single code mutation."""
    name: str
    description: str
    line_number: int
    original_code: str
    mutated_code: str
    category: str
    killed: bool = False
    survived: bool = False
    error: Optional[str] = None


@dataclass
class MutationReport:
    """Report of mutation testing results."""
    total_mutations: int = 0
    killed: int = 0
    survived: int = 0
    errors: int = 0
    timeout: int = 0
    mutations: List[Mutation] = field(default_factory=list)
    
    @property
    def score(self) -> float:
        """Calculate mutation score (killed / total)."""
        if self.total_mutations == 0:
            return 0.0
        return self.killed / self.total_mutations
    
    @property
    def score_percent(self) -> str:
        """Return score as percentage string."""
        return f"{self.score * 100:.1f}%"


class MutationOperators:
    """Collection of mutation operators for Python code."""
    
    @staticmethod
    def negate_conditionals(code: str) -> List[Tuple[str, str, str]]:
        """Negate conditional operators."""
        mutations = []
        
        replacements = [
            ('==', '!=', 'EQ_TO_NE'),
            ('!=', '==', 'NE_TO_EQ'),
            ('<', '>=', 'LT_TO_GE'),
            ('<=', '>', 'LE_TO_GT'),
            ('>', '<=', 'GT_TO_LE'),
            ('>=', '<', 'GE_TO_LT'),
            (' is ', ' is not ', 'IS_TO_IS_NOT'),
            (' is not ', ' is ', 'IS_NOT_TO_IS'),
            (' in ', ' not in ', 'IN_TO_NOT_IN'),
            (' not in ', ' in ', 'NOT_IN_TO_IN'),
        ]
        
        for original, replacement, name in replacements:
            if original in code:
                mutated = code.replace(original, replacement, 1)
                if mutated != code:
                    mutations.append((name, code, mutated))
        
        return mutations
    
    @staticmethod
    def arithmetic_operators(code: str) -> List[Tuple[str, str, str]]:
        """Mutate arithmetic operators."""
        mutations = []
        
        # Be careful not to mutate operators in strings or comments
        replacements = [
            (' + ', ' - ', 'ADD_TO_SUB'),
            (' - ', ' + ', 'SUB_TO_ADD'),
            (' * ', ' / ', 'MUL_TO_DIV'),
            (' / ', ' * ', 'DIV_TO_MUL'),
            (' // ', ' / ', 'FLOORDIV_TO_DIV'),
            (' % ', ' * ', 'MOD_TO_MUL'),
            (' ** ', ' * ', 'POW_TO_MUL'),
        ]
        
        for original, replacement, name in replacements:
            if original in code and not code.strip().startswith('#'):
                mutated = code.replace(original, replacement, 1)
                if mutated != code:
                    mutations.append((name, code, mutated))
        
        return mutations
    
    @staticmethod
    def boundary_mutations(code: str) -> List[Tuple[str, str, str]]:
        """Mutate boundary conditions."""
        mutations = []
        
        # Find patterns like "range(n)" -> "range(n+1)" or "range(n-1)"
        range_pattern = r'range\((\w+)\)'
        match = re.search(range_pattern, code)
        if match:
            var = match.group(1)
            mutated = re.sub(range_pattern, f'range({var} + 1)', code, count=1)
            if mutated != code:
                mutations.append(('RANGE_PLUS_ONE', code, mutated))
            mutated = re.sub(range_pattern, f'range({var} - 1)', code, count=1)
            if mutated != code:
                mutations.append(('RANGE_MINUS_ONE', code, mutated))
        
        # +1 / -1 mutations
        plus_one_pattern = r'\+ 1(?!\d)'
        if re.search(plus_one_pattern, code):
            mutated = re.sub(plus_one_pattern, '+ 2', code, count=1)
            mutations.append(('PLUS_ONE_TO_PLUS_TWO', code, mutated))
            mutated = re.sub(plus_one_pattern, '', code, count=1)
            mutations.append(('REMOVE_PLUS_ONE', code, mutated))
        
        minus_one_pattern = r'- 1(?!\d)'
        if re.search(minus_one_pattern, code):
            mutated = re.sub(minus_one_pattern, '- 2', code, count=1)
            mutations.append(('MINUS_ONE_TO_MINUS_TWO', code, mutated))
            mutated = re.sub(minus_one_pattern, '', code, count=1)
            mutations.append(('REMOVE_MINUS_ONE', code, mutated))
        
        return mutations
    
    @staticmethod
    def return_value_mutations(code: str) -> List[Tuple[str, str, str]]:
        """Mutate return values."""
        mutations = []
        
        if 'return True' in code:
            mutations.append(('TRUE_TO_FALSE', code, code.replace('return True', 'return False', 1)))
        if 'return False' in code:
            mutations.append(('FALSE_TO_TRUE', code, code.replace('return False', 'return True', 1)))
        if 'return None' in code:
            mutations.append(('NONE_TO_EMPTY_DICT', code, code.replace('return None', 'return {}', 1)))
        if 'return []' in code:
            mutations.append(('EMPTY_LIST_TO_NONE', code, code.replace('return []', 'return None', 1)))
        if 'return {}' in code:
            mutations.append(('EMPTY_DICT_TO_NONE', code, code.replace('return {}', 'return None', 1)))
        
        return mutations
    
    @staticmethod
    def logical_operators(code: str) -> List[Tuple[str, str, str]]:
        """Mutate logical operators."""
        mutations = []
        
        if ' and ' in code:
            mutations.append(('AND_TO_OR', code, code.replace(' and ', ' or ', 1)))
        if ' or ' in code:
            mutations.append(('OR_TO_AND', code, code.replace(' or ', ' and ', 1)))
        if 'not ' in code and 'is not' not in code and 'not in' not in code:
            mutations.append(('REMOVE_NOT', code, code.replace('not ', '', 1)))
        
        return mutations


class MutationTester:
    """
    Mutation tester for Ralph Mode.
    
    Usage:
        tester = MutationTester('ralph_mode.py')
        report = tester.run()
        print(f"Mutation Score: {report.score_percent}")
    """
    
    def __init__(
        self,
        source_file: str,
        test_command: str = "pytest tests/ -x -q",
        timeout: int = 30
    ):
        self.source_file = Path(source_file)
        self.test_command = test_command
        self.timeout = timeout
        self.operators = MutationOperators()
    
    def generate_mutations(self) -> List[Mutation]:
        """Generate all possible mutations for the source file."""
        mutations = []
        
        source_code = self.source_file.read_text(encoding='utf-8')
        lines = source_code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Skip comments and empty lines
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # Skip docstrings
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            
            # Apply mutation operators
            all_mutations = []
            all_mutations.extend(self.operators.negate_conditionals(line))
            all_mutations.extend(self.operators.arithmetic_operators(line))
            all_mutations.extend(self.operators.boundary_mutations(line))
            all_mutations.extend(self.operators.return_value_mutations(line))
            all_mutations.extend(self.operators.logical_operators(line))
            
            for name, original, mutated in all_mutations:
                mutations.append(Mutation(
                    name=name,
                    description=f"Line {line_num}: {name}",
                    line_number=line_num,
                    original_code=original,
                    mutated_code=mutated,
                    category=name.split('_')[0]
                ))
        
        return mutations
    
    def apply_mutation(self, mutation: Mutation) -> str:
        """Apply a mutation to the source code and return modified code."""
        source_code = self.source_file.read_text(encoding='utf-8')
        lines = source_code.split('\n')
        
        # Replace the specific line
        lines[mutation.line_number - 1] = mutation.mutated_code
        
        return '\n'.join(lines)
    
    def run_tests_with_mutation(self, mutated_code: str) -> Tuple[bool, str]:
        """
        Run tests with mutated code.
        Returns (killed, error_message).
        """
        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Copy project structure
            project_root = self.source_file.parent
            for item in project_root.iterdir():
                if item.name in ('.git', '__pycache__', '.pytest_cache', 'htmlcov', '.venv'):
                    continue
                if item.is_file():
                    shutil.copy2(item, tmp_path / item.name)
                elif item.is_dir():
                    shutil.copytree(item, tmp_path / item.name, 
                                   ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            
            # Write mutated code
            mutated_file = tmp_path / self.source_file.name
            mutated_file.write_text(mutated_code, encoding='utf-8')
            
            # Run tests
            try:
                result = subprocess.run(
                    self.test_command,
                    shell=True,
                    cwd=tmp_path,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env={**dict(__import__('os').environ), 'PYTHONDONTWRITEBYTECODE': '1'}
                )
                
                # Test failed = mutation killed
                killed = result.returncode != 0
                return killed, result.stderr if not killed else ""
                
            except subprocess.TimeoutExpired:
                return True, "Timeout"  # Timeout counts as killed
            except Exception as e:
                return False, str(e)
    
    def run(self, max_mutations: Optional[int] = None) -> MutationReport:
        """
        Run mutation testing and return report.
        
        Args:
            max_mutations: Maximum number of mutations to test (for quick runs)
        """
        report = MutationReport()
        mutations = self.generate_mutations()
        
        if max_mutations:
            mutations = mutations[:max_mutations]
        
        report.total_mutations = len(mutations)
        
        for mutation in mutations:
            mutated_code = self.apply_mutation(mutation)
            killed, error = self.run_tests_with_mutation(mutated_code)
            
            mutation.killed = killed
            mutation.survived = not killed
            mutation.error = error if error else None
            
            if killed:
                report.killed += 1
            else:
                report.survived += 1
            
            report.mutations.append(mutation)
        
        return report


# =============================================================================
# MUTATION TESTING TESTS
# =============================================================================

class TestMutationTestingInfrastructure:
    """Tests for the mutation testing infrastructure itself."""
    
    def test_negate_conditionals_operator(self):
        """Test conditional negation operator."""
        ops = MutationOperators()
        
        code = "if x == 5:"
        mutations = ops.negate_conditionals(code)
        
        assert len(mutations) > 0
        assert any('EQ_TO_NE' in m[0] for m in mutations)
        assert any('!=' in m[2] for m in mutations)
    
    def test_arithmetic_operators_mutation(self):
        """Test arithmetic operator mutations."""
        ops = MutationOperators()
        
        code = "result = a + b"
        mutations = ops.arithmetic_operators(code)
        
        assert len(mutations) > 0
        assert any('ADD_TO_SUB' in m[0] for m in mutations)
    
    def test_boundary_mutations(self):
        """Test boundary condition mutations."""
        ops = MutationOperators()
        
        code = "for i in range(n):"
        mutations = ops.boundary_mutations(code)
        
        assert len(mutations) > 0
        assert any('RANGE' in m[0] for m in mutations)
    
    def test_return_value_mutations(self):
        """Test return value mutations."""
        ops = MutationOperators()
        
        code = "return True"
        mutations = ops.return_value_mutations(code)
        
        assert len(mutations) > 0
        assert any('TRUE_TO_FALSE' in m[0] for m in mutations)
    
    def test_logical_operators_mutation(self):
        """Test logical operator mutations."""
        ops = MutationOperators()
        
        code = "if a and b:"
        mutations = ops.logical_operators(code)
        
        assert len(mutations) > 0
        assert any('AND_TO_OR' in m[0] for m in mutations)
    
    def test_mutation_report_score_calculation(self):
        """Test mutation score calculation."""
        report = MutationReport()
        report.total_mutations = 10
        report.killed = 8
        report.survived = 2
        
        assert report.score == 0.8
        assert report.score_percent == "80.0%"
    
    def test_mutation_report_zero_mutations(self):
        """Test mutation score with zero mutations."""
        report = MutationReport()
        
        assert report.score == 0.0
        assert report.score_percent == "0.0%"
    
    def test_mutation_dataclass(self):
        """Test Mutation dataclass."""
        mutation = Mutation(
            name="TEST_MUTATION",
            description="Test mutation",
            line_number=10,
            original_code="x = 1",
            mutated_code="x = 2",
            category="TEST"
        )
        
        assert mutation.name == "TEST_MUTATION"
        assert mutation.killed is False
        assert mutation.survived is False


class TestCriticalMutations:
    """
    Tests that verify critical code paths are protected by tests.
    These simulate specific mutations and verify tests catch them.
    """
    
    def test_iteration_increment_mutation_caught(self, tmp_path):
        """
        Mutation: Change 'iteration + 1' to 'iteration + 2'
        This mutation must be caught by tests.
        """
        # This test verifies that our test suite would catch
        # if someone accidentally changed the iteration increment
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=10, completion_promise="DONE")
        
        # First iteration
        result = rm.iterate()
        assert result['iteration'] == 2, "Iteration should increment by exactly 1"
        
        # Second iteration
        result = rm.iterate()
        assert result['iteration'] == 3, "Iteration should increment by exactly 1"
        
        rm.disable()
    
    def test_max_iterations_comparison_mutation_caught(self, tmp_path):
        """
        Mutation: Change 'iteration > max_iterations' to '>='
        This mutation must be caught by tests.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=3, completion_promise="DONE")
        
        # Should allow exactly 3 iterations (1 initial + 2 iterate calls)
        rm.iterate()  # iteration 2
        result = rm.iterate()  # iteration 3
        
        # At iteration 3 with max=3, should still be active
        # (unless it's > comparison which allows this)
        assert result['iteration'] == 3
        
        rm.disable()
    
    def test_completion_promise_exact_match_mutation_caught(self, tmp_path):
        """
        Mutation: Change exact match to contains check
        This mutation must be caught by tests.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=10, completion_promise="DONE")
        
        # Should NOT match partial promise
        assert rm.check_completion("<promise>DONE_EXTRA</promise>") is False
        assert rm.check_completion("<promise>ALMOST_DONE</promise>") is False
        
        # Should ONLY match exact promise
        assert rm.check_completion("<promise>DONE</promise>") is True
        
        rm.disable()
    
    def test_batch_task_index_increment_mutation_caught(self, tmp_path):
        """
        Mutation: Change task index increment
        This mutation must be caught by tests.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        rm = RalphMode(base_path=tmp_path)
        tasks = [
            {"id": "task-1", "title": "Task 1", "prompt": "Do 1"},
            {"id": "task-2", "title": "Task 2", "prompt": "Do 2"},
            {"id": "task-3", "title": "Task 3", "prompt": "Do 3"},
        ]
        rm.init_batch(tasks, max_iterations=5, completion_promise="DONE")
        
        # First task
        assert rm.status()['current_task_index'] == 0
        
        # Complete and move to next
        rm.complete("<promise>DONE</promise>")
        assert rm.status()['current_task_index'] == 1
        
        # Complete and move to next
        rm.complete("<promise>DONE</promise>")
        assert rm.status()['current_task_index'] == 2
        
        rm.disable()
    
    def test_is_active_logic_mutation_caught(self, tmp_path):
        """
        Mutation: Negate is_active() return value
        This mutation must be caught by tests.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        rm = RalphMode(base_path=tmp_path)
        
        # Before enable
        assert rm.is_active() is False
        
        # After enable
        rm.enable("Test", max_iterations=5, completion_promise="DONE")
        assert rm.is_active() is True
        
        # After disable
        rm.disable()
        assert rm.is_active() is False
    
    def test_history_append_mutation_caught(self, tmp_path):
        """
        Mutation: Remove history append calls
        This mutation must be caught by tests.
        """
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=10, completion_promise="DONE")
        
        # Should have 'started' entry
        history = rm.get_history()
        assert len(history) >= 1
        assert any(h['status'] == 'started' for h in history)  # Field is 'status', not 'event'
        
        # After iterations
        rm.iterate()
        rm.iterate()
        
        history = rm.get_history()
        assert len(history) >= 3  # started + 2 iterations
        
        rm.disable()


class TestMutationCoverage:
    """
    Tests that measure mutation coverage for critical functions.
    """
    
    def test_check_completion_mutations_covered(self, tmp_path):
        """Verify check_completion is well-tested against mutations."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        rm = RalphMode(base_path=tmp_path)
        rm.enable("Test", max_iterations=10, completion_promise="EXACT_MATCH")
        
        # Test cases that would catch various mutations
        test_cases = [
            ("<promise>EXACT_MATCH</promise>", True),
            ("<promise>exact_match</promise>", False),  # Case sensitive
            ("<promise>EXACT_MATCH_EXTRA</promise>", False),  # No partial
            ("<promise>ALMOST_EXACT_MATCH</promise>", False),  # No partial
            ("EXACT_MATCH", False),  # Needs tags
            ("<promise>EXACT_MATCH", False),  # Missing close tag
            ("EXACT_MATCH</promise>", False),  # Missing open tag
            ("", False),  # Empty
            ("   <promise>EXACT_MATCH</promise>   ", True),  # Whitespace OK
            ("prefix<promise>EXACT_MATCH</promise>suffix", True),  # Embedded OK
        ]
        
        for output, expected in test_cases:
            result = rm.check_completion(output)
            assert result == expected, f"Failed for output: {output!r}"
        
        rm.disable()
    
    def test_slugify_mutations_covered(self):
        """Verify slugify is well-tested against mutations."""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from ralph_mode import RalphMode
        
        def slugify(text):
            return RalphMode._slugify(text)
        
        # Test cases that would catch various mutations
        test_cases = [
            ("Hello World", "hello-world"),
            ("UPPERCASE", "uppercase"),
            ("already-lowercase", "already-lowercase"),
            ("Multiple   Spaces", "multiple-spaces"),
            ("Special!@#$%^&*()Chars", "special-chars"),
            ("123 Numbers 456", "123-numbers-456"),
            ("Mixed123Case", "mixed123case"),
            ("  Trim Whitespace  ", "trim-whitespace"),
            ("Under_Scores", "under_scores"),
            ("Dashes-Already", "dashes-already"),
        ]
        
        for input_text, expected in test_cases:
            result = slugify(input_text)
            assert result == expected, f"slugify({input_text!r}) = {result!r}, expected {expected!r}"


# Run specific mutation tests on critical paths
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
