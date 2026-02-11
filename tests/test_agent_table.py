"""Comprehensive tests for the Agent Table multi-agent deliberation protocol."""

import json
import shutil
from pathlib import Path

import pytest

from ralph_mode.agent_table import ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER, AgentMessage, AgentTable, MessageType, Phase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_ralph_dir(tmp_path):
    """Create a temporary .ralph-mode directory."""
    ralph_dir = tmp_path / ".ralph-mode"
    ralph_dir.mkdir()
    return ralph_dir


@pytest.fixture
def table(tmp_ralph_dir):
    """Create an AgentTable instance with a temp directory."""
    return AgentTable(ralph_dir=tmp_ralph_dir)


@pytest.fixture
def active_table(table):
    """Create an initialized and active AgentTable."""
    table.initialize("Refactor the authentication module")
    return table


@pytest.fixture
def table_with_round(active_table):
    """Create an AgentTable with one round started."""
    active_table.new_round()
    return active_table


# ---------------------------------------------------------------------------
# AgentMessage Tests
# ---------------------------------------------------------------------------


class TestAgentMessage:
    """Tests for the AgentMessage data class."""

    def test_create_message(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="My plan is to refactor the auth module.",
        )
        assert msg.sender == "doer"
        assert msg.recipient == "critic"
        assert msg.msg_type == "plan"
        assert msg.content == "My plan is to refactor the auth module."
        assert msg.round_number == 0
        assert msg.phase == ""
        assert msg.metadata == {}
        assert msg.timestamp is not None

    def test_message_with_metadata(self):
        msg = AgentMessage(
            sender=ROLE_CRITIC,
            recipient=ROLE_DOER,
            msg_type=MessageType.CRITIQUE.value,
            content="The plan is incomplete.",
            round_number=1,
            phase=Phase.PLAN.value,
            metadata={"approved": False, "severity": "high"},
        )
        assert msg.metadata["approved"] is False
        assert msg.metadata["severity"] == "high"
        assert msg.round_number == 1
        assert msg.phase == "plan"

    def test_to_dict(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Test content",
            round_number=2,
            phase=Phase.IMPLEMENT.value,
        )
        d = msg.to_dict()
        assert isinstance(d, dict)
        assert d["sender"] == "doer"
        assert d["recipient"] == "critic"
        assert d["msg_type"] == "plan"
        assert d["content"] == "Test content"
        assert d["round_number"] == 2
        assert d["phase"] == "implement"
        assert "timestamp" in d

    def test_from_dict(self):
        data = {
            "sender": "arbiter",
            "recipient": "doer",
            "msg_type": "decision",
            "content": "I side with the critic.",
            "round_number": 3,
            "phase": "resolve",
            "metadata": {"side_with": "critic"},
            "timestamp": "2026-02-11T10:00:00+00:00",
        }
        msg = AgentMessage.from_dict(data)
        assert msg.sender == "arbiter"
        assert msg.recipient == "doer"
        assert msg.msg_type == "decision"
        assert msg.content == "I side with the critic."
        assert msg.round_number == 3
        assert msg.metadata["side_with"] == "critic"

    def test_roundtrip_serialization(self):
        original = AgentMessage(
            sender=ROLE_CRITIC,
            recipient=ROLE_ARBITER,
            msg_type=MessageType.ESCALATION.value,
            content="We disagree on the approach.",
            round_number=5,
            phase=Phase.RESOLVE.value,
            metadata={"urgent": True},
        )
        data = original.to_dict()
        restored = AgentMessage.from_dict(data)

        assert restored.sender == original.sender
        assert restored.recipient == original.recipient
        assert restored.msg_type == original.msg_type
        assert restored.content == original.content
        assert restored.round_number == original.round_number
        assert restored.phase == original.phase
        assert restored.metadata == original.metadata

    def test_repr(self):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="test",
            round_number=1,
        )
        repr_str = repr(msg)
        assert "doer" in repr_str
        assert "critic" in repr_str
        assert "plan" in repr_str


# ---------------------------------------------------------------------------
# Enums Tests
# ---------------------------------------------------------------------------


class TestEnums:

    def test_phase_values(self):
        assert Phase.PLAN.value == "plan"
        assert Phase.IMPLEMENT.value == "implement"
        assert Phase.RESOLVE.value == "resolve"
        assert Phase.APPROVE.value == "approve"

    def test_message_type_values(self):
        assert MessageType.PLAN.value == "plan"
        assert MessageType.CRITIQUE.value == "critique"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.DECISION.value == "decision"
        assert MessageType.IMPLEMENTATION.value == "implementation"
        assert MessageType.REVIEW.value == "review"
        assert MessageType.APPROVAL.value == "approval"
        assert MessageType.REJECTION.value == "rejection"
        assert MessageType.ESCALATION.value == "escalation"

    def test_phase_is_string_enum(self):
        assert isinstance(Phase.PLAN, str)
        assert Phase.PLAN == "plan"

    def test_message_type_is_string_enum(self):
        assert isinstance(MessageType.PLAN, str)
        assert MessageType.PLAN == "plan"


# ---------------------------------------------------------------------------
# AgentTable Initialization Tests
# ---------------------------------------------------------------------------


class TestAgentTableInit:

    def test_create_table(self, tmp_ralph_dir):
        table = AgentTable(ralph_dir=tmp_ralph_dir)
        assert table.ralph_dir == tmp_ralph_dir
        assert not table.is_active()

    def test_create_table_default_path(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        table = AgentTable()
        assert table.ralph_dir == tmp_path / ".ralph-mode"

    def test_initialize(self, table):
        state = table.initialize("Build a REST API")
        assert state["active"] is True
        assert state["task"] == "Build a REST API"
        assert state["current_round"] == 0
        assert state["current_phase"] == "plan"
        assert state["max_rounds"] == 10
        assert state["require_unanimous"] is False
        assert state["auto_escalate"] is True
        assert state["outcome"] is None
        assert state["total_messages"] == 0
        assert state["escalation_count"] == 0

    def test_initialize_custom_options(self, table):
        state = table.initialize(
            "Complex task",
            max_rounds=5,
            require_unanimous=True,
            auto_escalate=False,
        )
        assert state["max_rounds"] == 5
        assert state["require_unanimous"] is True
        assert state["auto_escalate"] is False

    def test_initialize_creates_directories(self, table):
        table.initialize("Test task")
        assert table.table_dir.exists()
        assert table.rounds_dir.exists()


# ---------------------------------------------------------------------------
# State Management Tests
# ---------------------------------------------------------------------------


class TestStateManagement:

    def test_is_active(self, active_table):
        assert active_table.is_active()

    def test_is_not_active(self, table):
        assert not table.is_active()

    def test_get_state(self, active_table):
        state = active_table.get_state()
        assert state is not None
        assert state["active"] is True
        assert state["task"] == "Refactor the authentication module"

    def test_get_state_when_inactive(self, table):
        state = table.get_state()
        assert state is None

    def test_state_persists(self, active_table):
        # Create a new instance pointing to same dir
        table2 = AgentTable(ralph_dir=active_table.ralph_dir)
        state = table2.get_state()
        assert state is not None
        assert state["task"] == "Refactor the authentication module"

    def test_get_state_handles_corrupted_json(self, active_table):
        # Corrupt the state file
        with open(active_table.state_file, "w") as f:
            f.write("{invalid json")
        state = active_table.get_state()
        assert state is None


# ---------------------------------------------------------------------------
# Round Management Tests
# ---------------------------------------------------------------------------


class TestRoundManagement:

    def test_new_round(self, active_table):
        state = active_table.new_round()
        assert state["current_round"] == 1
        assert state["current_phase"] == "plan"

    def test_multiple_rounds(self, active_table):
        active_table.new_round()
        active_table.new_round()
        state = active_table.new_round()
        assert state["current_round"] == 3

    def test_max_rounds_enforced(self, table):
        table.initialize("Test", max_rounds=2)
        table.new_round()
        table.new_round()
        with pytest.raises(ValueError, match="Maximum rounds"):
            table.new_round()

    def test_max_rounds_sets_outcome(self, table):
        table.initialize("Test", max_rounds=1)
        table.new_round()
        with pytest.raises(ValueError):
            table.new_round()
        state = table.get_state()
        assert state["outcome"] == "max_rounds_reached"
        assert state["active"] is False

    def test_new_round_requires_active_table(self, table):
        with pytest.raises(ValueError, match="not active"):
            table.new_round()

    def test_round_directory_created(self, active_table):
        active_table.new_round()
        round_dir = active_table.get_round_dir(1)
        assert round_dir.exists()
        assert round_dir.name == "round-001"

    def test_get_round_dir_current(self, table_with_round):
        rd = table_with_round.get_round_dir()
        assert rd.name == "round-001"

    def test_get_round_dir_specific(self, active_table):
        active_table.new_round()
        active_table.new_round()
        rd = active_table.get_round_dir(1)
        assert rd.name == "round-001"
        rd = active_table.get_round_dir(2)
        assert rd.name == "round-002"


# ---------------------------------------------------------------------------
# Message Handling Tests
# ---------------------------------------------------------------------------


class TestMessageHandling:

    def test_send_message(self, table_with_round):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Here is my plan",
        )
        result = table_with_round.send_message(msg)
        assert result.round_number == 1
        assert table_with_round.transcript_file.exists()

    def test_send_message_requires_active_table(self, table):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="test",
        )
        with pytest.raises(ValueError, match="not active"):
            table.send_message(msg)

    def test_message_saved_to_transcript(self, table_with_round):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan content",
        )
        table_with_round.send_message(msg)

        with open(table_with_round.transcript_file, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["sender"] == "doer"
        assert data["content"] == "Plan content"

    def test_message_saved_to_round_md(self, table_with_round):
        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content="Plan content here",
        )
        table_with_round.send_message(msg)

        plan_file = table_with_round.get_round_dir(1) / "plan.md"
        assert plan_file.exists()
        content = plan_file.read_text()
        assert "Plan content here" in content

    def test_get_messages(self, table_with_round):
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="Plan 1",
            )
        )
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_CRITIC,
                recipient=ROLE_DOER,
                msg_type=MessageType.CRITIQUE.value,
                content="Critique 1",
            )
        )
        messages = table_with_round.get_messages()
        assert len(messages) == 2

    def test_get_messages_filter_by_sender(self, table_with_round):
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="Plan",
            )
        )
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_CRITIC,
                recipient=ROLE_DOER,
                msg_type=MessageType.CRITIQUE.value,
                content="Critique",
            )
        )
        doer_msgs = table_with_round.get_messages(sender=ROLE_DOER)
        assert len(doer_msgs) == 1
        assert doer_msgs[0].sender == "doer"

    def test_get_messages_filter_by_round(self, active_table):
        active_table.new_round()
        active_table.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="Round 1",
                round_number=1,
            )
        )
        active_table.new_round()
        active_table.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="Round 2",
                round_number=2,
            )
        )
        r1_msgs = active_table.get_messages(round_number=1)
        assert len(r1_msgs) == 1
        assert r1_msgs[0].content == "Round 1"

    def test_get_messages_filter_by_type(self, table_with_round):
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="Plan",
            )
        )
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_CRITIC,
                recipient=ROLE_DOER,
                msg_type=MessageType.CRITIQUE.value,
                content="Critique",
            )
        )
        plans = table_with_round.get_messages(msg_type=MessageType.PLAN.value)
        assert len(plans) == 1
        assert plans[0].msg_type == "plan"

    def test_get_last_message(self, table_with_round):
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="Plan 1",
            )
        )
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="Plan 2",
            )
        )
        last = table_with_round.get_last_message(sender=ROLE_DOER)
        assert last.content == "Plan 2"

    def test_get_last_message_none(self, table_with_round):
        result = table_with_round.get_last_message(sender=ROLE_ARBITER)
        assert result is None

    def test_get_messages_empty_transcript(self, table_with_round):
        messages = table_with_round.get_messages()
        assert messages == []

    def test_total_messages_counter(self, table_with_round):
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_DOER,
                recipient=ROLE_CRITIC,
                msg_type=MessageType.PLAN.value,
                content="A",
            )
        )
        table_with_round.send_message(
            AgentMessage(
                sender=ROLE_CRITIC,
                recipient=ROLE_DOER,
                msg_type=MessageType.CRITIQUE.value,
                content="B",
            )
        )
        state = table_with_round.get_state()
        assert state["total_messages"] == 2


# ---------------------------------------------------------------------------
# Phase Transition Tests
# ---------------------------------------------------------------------------


class TestPhaseTransitions:

    def test_advance_phase_plan_to_implement(self, table_with_round):
        state = table_with_round.advance_phase()
        assert state["current_phase"] == "implement"

    def test_advance_phase_implement_to_resolve(self, table_with_round):
        table_with_round.advance_phase()  # plan → implement
        state = table_with_round.advance_phase()  # implement → resolve
        assert state["current_phase"] == "resolve"

    def test_advance_phase_resolve_to_approve(self, table_with_round):
        table_with_round.advance_phase()  # plan → implement
        table_with_round.advance_phase()  # implement → resolve
        state = table_with_round.advance_phase()  # resolve → approve
        assert state["current_phase"] == "approve"

    def test_advance_phase_approve_stays(self, table_with_round):
        """Approve doesn't auto-advance to next round."""
        table_with_round.advance_phase()  # plan → implement
        table_with_round.advance_phase()  # implement → resolve
        table_with_round.advance_phase()  # resolve → approve
        state = table_with_round.advance_phase()  # approve stays
        assert state["current_phase"] == "approve"

    def test_set_phase(self, table_with_round):
        state = table_with_round.set_phase("resolve")
        assert state["current_phase"] == "resolve"

    def test_set_invalid_phase(self, table_with_round):
        with pytest.raises(ValueError, match="Invalid phase"):
            table_with_round.set_phase("invalid")

    def test_advance_phase_requires_active(self, table):
        with pytest.raises(ValueError, match="not active"):
            table.advance_phase()


# ---------------------------------------------------------------------------
# Protocol Method Tests
# ---------------------------------------------------------------------------


class TestProtocolMethods:

    def test_submit_plan(self, table_with_round):
        msg = table_with_round.submit_plan("Step 1: Extract interface\nStep 2: Implement")
        assert msg.sender == "doer"
        assert msg.recipient == "critic"
        assert msg.msg_type == "plan"
        assert "Extract interface" in msg.content

    def test_submit_critique_approved(self, table_with_round):
        table_with_round.submit_plan("My plan")
        msg = table_with_round.submit_critique("Looks good!", approved=True)
        assert msg.sender == "critic"
        assert msg.metadata["approved"] is True

    def test_submit_critique_rejected_auto_escalates(self, table_with_round):
        table_with_round.submit_plan("My plan")
        msg = table_with_round.submit_critique("Missing error handling", approved=False)
        assert msg.metadata["approved"] is False

        # Should have auto-escalated
        state = table_with_round.get_state()
        assert state["escalation_count"] == 1
        assert state["current_phase"] == "resolve"

    def test_submit_critique_no_auto_escalate(self, table):
        table.initialize("Test", auto_escalate=False)
        table.new_round()
        table.submit_plan("My plan")
        table.submit_critique("Issues found", approved=False)

        state = table.get_state()
        assert state["escalation_count"] == 0

    def test_submit_implementation(self, table_with_round):
        msg = table_with_round.submit_implementation("Added error handling to auth.ts")
        assert msg.sender == "doer"
        assert msg.msg_type == "implementation"
        state = table_with_round.get_state()
        assert state["current_phase"] == "implement"

    def test_submit_review_approved(self, table_with_round):
        table_with_round.submit_implementation("Changes made")
        msg = table_with_round.submit_review("LGTM", approved=True)
        assert msg.sender == "critic"
        assert msg.msg_type == "review"
        assert msg.metadata["approved"] is True

    def test_submit_review_rejected(self, table_with_round):
        table_with_round.submit_implementation("Changes made")
        msg = table_with_round.submit_review("Still has bugs", approved=False)
        assert msg.metadata["approved"] is False

    def test_escalate(self, table_with_round):
        msg = table_with_round.escalate(reason="Deadlock between Doer and Critic")
        assert msg.sender == "doer"
        assert msg.recipient == "arbiter"
        assert msg.msg_type == "escalation"
        state = table_with_round.get_state()
        assert state["escalation_count"] >= 1
        assert state["current_phase"] == "resolve"

    def test_submit_decision(self, table_with_round):
        table_with_round.escalate("Need decision")
        msg = table_with_round.submit_decision(
            "The Doer's approach is more practical.",
            side_with="doer",
        )
        assert msg.sender == "arbiter"
        assert msg.recipient == "doer"
        assert msg.msg_type == "decision"
        assert msg.metadata["side_with"] == "doer"
        state = table_with_round.get_state()
        assert state["current_phase"] == "approve"

    def test_submit_approval(self, table_with_round):
        msg = table_with_round.submit_approval(notes="Good work, proceed.")
        assert msg.sender == "arbiter"
        assert msg.msg_type == "approval"
        assert msg.metadata["approved"] is True
        state = table_with_round.get_state()
        assert len(state.get("rounds_summary", [])) == 1
        assert state["rounds_summary"][0]["outcome"] == "approved"

    def test_submit_rejection(self, table_with_round):
        msg = table_with_round.submit_rejection("Not ready. Fix the edge cases.")
        assert msg.sender == "arbiter"
        assert msg.msg_type == "rejection"
        assert msg.metadata["approved"] is False
        state = table_with_round.get_state()
        assert len(state.get("rounds_summary", [])) == 1
        assert state["rounds_summary"][0]["outcome"] == "rejected"

    def test_submit_plan_requires_active(self, table):
        with pytest.raises(ValueError, match="not active"):
            table.submit_plan("test")

    def test_submit_critique_requires_active(self, table):
        with pytest.raises(ValueError, match="not active"):
            table.submit_critique("test")

    def test_submit_implementation_requires_active(self, table):
        with pytest.raises(ValueError, match="not active"):
            table.submit_implementation("test")


# ---------------------------------------------------------------------------
# Full Protocol Flow Tests
# ---------------------------------------------------------------------------


class TestFullProtocolFlow:

    def test_happy_path_approved(self, table_with_round):
        """Complete flow: plan → critique(approve) → implement → review(approve) → arbiter approve."""
        # Step 1: Doer plans
        table_with_round.submit_plan("I'll refactor auth into service layer")

        # Step 2: Critic approves
        table_with_round.submit_critique("Good plan, well structured", approved=True)

        # Step 3: Doer implements
        table_with_round.submit_implementation("Extracted AuthService class")

        # Step 4: Critic reviews and approves
        table_with_round.submit_review("Clean implementation, tests pass", approved=True)

        # Step 5: Arbiter gives final approval
        table_with_round.submit_approval("Excellent work by both agents")

        state = table_with_round.get_state()
        assert state["total_messages"] >= 3
        assert len(state["rounds_summary"]) == 1
        assert state["rounds_summary"][0]["outcome"] == "approved"

    def test_disagreement_path(self, table_with_round):
        """Flow with disagreement: plan → critique(reject) → escalate → arbiter decides."""
        # Step 1: Doer plans
        table_with_round.submit_plan("Use global state for auth tokens")

        # Step 2: Critic rejects (auto-escalates)
        table_with_round.submit_critique(
            "Global state is an anti-pattern. Use dependency injection.",
            approved=False,
        )

        # Step 3: Arbiter decides
        table_with_round.submit_decision(
            "The Critic is correct. Global state makes testing difficult.",
            side_with="critic",
        )

        # Step 4: Arbiter approves the corrected approach
        table_with_round.submit_approval("Proceed with dependency injection")

        state = table_with_round.get_state()
        assert state["escalation_count"] >= 1
        assert state["rounds_summary"][0]["outcome"] == "approved"

    def test_multi_round_flow(self, active_table):
        """Multiple rounds of deliberation."""
        # Round 1: Plan rejected
        active_table.new_round()
        active_table.submit_plan("Quick and dirty fix")
        active_table.submit_critique("Too hacky", approved=False)
        active_table.submit_decision("Critic is right, do it properly", side_with="critic")
        active_table.submit_rejection("Start over with a proper approach")

        # Round 2: Plan approved
        active_table.new_round()
        active_table.submit_plan("Proper refactoring with tests")
        active_table.submit_critique("Much better!", approved=True)
        active_table.submit_implementation("Refactored with full test coverage")
        active_table.submit_review("All tests pass, clean code", approved=True)
        active_table.submit_approval("Well done")

        state = active_table.get_state()
        assert state["current_round"] == 2
        assert len(state["rounds_summary"]) == 2
        assert state["rounds_summary"][0]["outcome"] == "rejected"
        assert state["rounds_summary"][1]["outcome"] == "approved"

    def test_run_protocol_round_approved(self, active_table):
        """Test the convenience method for running a full round."""
        state = active_table.run_protocol_round(
            plan="Build REST API",
            critique="Good plan",
            critique_approved=True,
            implementation="API built with Express",
            review="Looks great",
            review_approved=True,
            arbiter_approves=True,
        )
        assert state["current_round"] == 1
        assert len(state["rounds_summary"]) == 1
        assert state["rounds_summary"][0]["outcome"] == "approved"

    def test_run_protocol_round_rejected(self, active_table):
        """Test convenience method with rejection."""
        state = active_table.run_protocol_round(
            plan="Use eval() for config",
            critique="Security risk!",
            critique_approved=False,
            arbiter_decision="Critic is right, eval is dangerous",
            arbiter_side_with="critic",
            arbiter_approves=False,
        )
        assert state["rounds_summary"][0]["outcome"] == "rejected"


# ---------------------------------------------------------------------------
# Context Building Tests
# ---------------------------------------------------------------------------


class TestContextBuilding:

    def test_build_doer_context(self, table_with_round):
        table_with_round.submit_plan("My plan")
        table_with_round.submit_critique("Fix error handling", approved=False)

        ctx = table_with_round.build_doer_context()
        assert "Doer Context" in ctx
        assert "Round 1" in ctx
        assert "Refactor the authentication module" in ctx
        assert "Fix error handling" in ctx

    def test_build_critic_context(self, table_with_round):
        table_with_round.submit_plan("My plan here")

        ctx = table_with_round.build_critic_context()
        assert "Critic Context" in ctx
        assert "My plan here" in ctx
        assert "You are the **Critic**" in ctx

    def test_build_arbiter_context(self, table_with_round):
        table_with_round.submit_plan("Plan A")
        table_with_round.submit_critique("I disagree", approved=False)
        table_with_round.escalate("Need resolution")

        ctx = table_with_round.build_arbiter_context()
        assert "Arbiter Context" in ctx
        assert "You are the **Arbiter**" in ctx
        assert "final authority" in ctx

    def test_build_context_empty(self, table):
        assert table.build_doer_context() == ""
        assert table.build_critic_context() == ""
        assert table.build_arbiter_context() == ""

    def test_doer_context_includes_arbiter_decision(self, table_with_round):
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Bad", approved=False)
        table_with_round.submit_decision("Use plan B", side_with="critic")

        ctx = table_with_round.build_doer_context()
        assert "Arbiter's Decision" in ctx
        assert "Use plan B" in ctx


# ---------------------------------------------------------------------------
# Finalization Tests
# ---------------------------------------------------------------------------


class TestFinalization:

    def test_finalize_approved(self, active_table):
        state = active_table.finalize(outcome="approved")
        assert state["active"] is False
        assert state["outcome"] == "approved"
        assert state["completed_at"] is not None

    def test_finalize_rejected(self, active_table):
        state = active_table.finalize(outcome="rejected")
        assert state["outcome"] == "rejected"

    def test_finalize_no_session(self, table):
        with pytest.raises(ValueError, match="No active"):
            table.finalize()

    def test_reset_clears_everything(self, active_table):
        active_table.new_round()
        active_table.submit_plan("test")
        active_table.reset()
        assert not active_table.table_dir.exists()
        assert not active_table.is_active()

    def test_reset_on_empty(self, table):
        table.reset()  # Should not raise
        assert not table.is_active()


# ---------------------------------------------------------------------------
# Status & Transcript Tests
# ---------------------------------------------------------------------------


class TestStatusAndTranscript:

    def test_status(self, table_with_round):
        table_with_round.submit_plan("Test plan")
        table_with_round.submit_critique("Test critique", approved=True)

        st = table_with_round.status()
        assert st is not None
        assert st["active"] is True
        assert st["current_round"] == 1
        assert st["total_messages"] >= 2
        assert "doer" in st["messages_by_agent"]
        assert "critic" in st["messages_by_agent"]

    def test_status_inactive(self, table):
        assert table.status() is None

    def test_get_transcript_text(self, table_with_round):
        table_with_round.submit_plan("Plan")
        table_with_round.submit_critique("Critique", approved=True)

        text = table_with_round.get_transcript_text()
        assert "ROUND 1" in text
        assert "doer" in text
        assert "critic" in text

    def test_get_transcript_text_empty(self, table_with_round):
        text = table_with_round.get_transcript_text()
        assert "No messages yet" in text


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_unicode_content(self, table_with_round):
        msg = table_with_round.submit_plan("ریفکتور ماژول احراز هویت 🔐")
        assert "ریفکتور" in msg.content
        assert "🔐" in msg.content

        messages = table_with_round.get_messages()
        assert messages[0].content == "ریفکتور ماژول احراز هویت 🔐"

    def test_very_long_content(self, table_with_round):
        long_text = "x" * 10000
        msg = table_with_round.submit_plan(long_text)
        assert len(msg.content) == 10000

    def test_empty_content(self, table_with_round):
        msg = table_with_round.submit_plan("")
        assert msg.content == ""

    def test_special_characters(self, table_with_round):
        special = 'Plan with "quotes", <tags>, & ampersands\nand newlines\ttabs'
        msg = table_with_round.submit_plan(special)
        messages = table_with_round.get_messages()
        assert messages[0].content == special

    def test_concurrent_messages_to_transcript(self, table_with_round):
        """Send many messages rapidly."""
        for i in range(20):
            table_with_round.send_message(
                AgentMessage(
                    sender=ROLE_DOER,
                    recipient=ROLE_CRITIC,
                    msg_type=MessageType.PLAN.value,
                    content=f"Message {i}",
                )
            )
        messages = table_with_round.get_messages()
        assert len(messages) == 20

    def test_multiple_critiques_appended(self, table_with_round):
        """Multiple messages of same type are appended."""
        table_with_round.submit_plan("Plan A")
        table_with_round.submit_critique("First critique", approved=False)

        # Send another critique manually
        msg = AgentMessage(
            sender=ROLE_CRITIC,
            recipient=ROLE_DOER,
            msg_type=MessageType.CRITIQUE.value,
            content="Second critique after revision",
            round_number=1,
        )
        table_with_round.send_message(msg)

        critique_file = table_with_round.get_round_dir(1) / "critique.md"
        content = critique_file.read_text()
        assert "First critique" in content
        assert "Second critique" in content

    def test_reinitialize_overwrites(self, active_table):
        """Re-initializing should reset the state."""
        active_table.new_round()
        active_table.submit_plan("Old plan")
        active_table.initialize("New task entirely")
        state = active_table.get_state()
        assert state["task"] == "New task entirely"
        assert state["current_round"] == 0
        assert state["total_messages"] == 0


# ---------------------------------------------------------------------------
# Integration with Ralph Mode (if state exists)
# ---------------------------------------------------------------------------


class TestRalphModeIntegration:

    def test_table_inside_ralph_dir(self, tmp_path):
        """Table uses the same .ralph-mode directory as Ralph Mode."""
        ralph_dir = tmp_path / ".ralph-mode"
        ralph_dir.mkdir()
        # Simulate Ralph Mode state
        state_file = ralph_dir / "state.json"
        state_file.write_text(json.dumps({"iteration": 1}))

        table = AgentTable(ralph_dir=ralph_dir)
        table.initialize("Test task")

        # Table files are inside ralph_dir/table/
        assert (ralph_dir / "table" / "table-state.json").exists()

        # Ralph state still intact
        assert state_file.exists()

    def test_table_reset_preserves_ralph_state(self, tmp_path):
        """Resetting table should not affect Ralph Mode state."""
        ralph_dir = tmp_path / ".ralph-mode"
        ralph_dir.mkdir()
        state_file = ralph_dir / "state.json"
        state_file.write_text(json.dumps({"iteration": 5}))

        table = AgentTable(ralph_dir=ralph_dir)
        table.initialize("Test")
        table.new_round()
        table.submit_plan("test plan")
        table.reset()

        # Ralph state should still be there
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["iteration"] == 5
