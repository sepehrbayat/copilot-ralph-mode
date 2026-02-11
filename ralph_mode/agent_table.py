"""Agent Table — Multi-agent deliberation protocol for Ralph Mode.

Implements a 3-agent collaboration pattern:
  Agent 1 (Implementor/Doer)  – Executes tasks, writes code
  Agent 2 (Critic/Reviewer)   – Reviews plans and code, provides critique
  Agent 3 (Arbiter/Judge)     – Makes final decisions, resolves disagreements

Communication is file-based via `.ralph-mode/table/` with structured rounds.
"""

import json
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TABLE_DIR = "table"
ROUNDS_DIR = "rounds"
TRANSCRIPT_FILE = "transcript.jsonl"
TABLE_STATE_FILE = "table-state.json"

# Agent roles
ROLE_DOER = "doer"
ROLE_CRITIC = "critic"
ROLE_ARBITER = "arbiter"

ALL_ROLES = (ROLE_DOER, ROLE_CRITIC, ROLE_ARBITER)


# Phases within a single round
class Phase(str, Enum):
    PLAN = "plan"  # Doer presents plan → Critic reviews
    IMPLEMENT = "implement"  # Doer implements → Critic reviews output
    RESOLVE = "resolve"  # Arbiter decides on disagreements
    APPROVE = "approve"  # Arbiter gives final go/no-go


# Message types
class MessageType(str, Enum):
    PLAN = "plan"
    CRITIQUE = "critique"
    RESPONSE = "response"
    DECISION = "decision"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    APPROVAL = "approval"
    REJECTION = "rejection"
    ESCALATION = "escalation"


# ---------------------------------------------------------------------------
# AgentMessage
# ---------------------------------------------------------------------------


class AgentMessage:
    """A single message in the agent deliberation."""

    def __init__(
        self,
        sender: str,
        recipient: str,
        msg_type: str,
        content: str,
        *,
        round_number: int = 0,
        phase: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        self.sender = sender
        self.recipient = recipient
        self.msg_type = msg_type
        self.content = content
        self.round_number = round_number
        self.phase = phase
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "msg_type": self.msg_type,
            "content": self.content,
            "round_number": self.round_number,
            "phase": self.phase,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        return cls(
            sender=data["sender"],
            recipient=data["recipient"],
            msg_type=data["msg_type"],
            content=data["content"],
            round_number=data.get("round_number", 0),
            phase=data.get("phase", ""),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp"),
        )

    def __repr__(self) -> str:
        return f"<AgentMessage {self.sender}→{self.recipient} [{self.msg_type}] round={self.round_number}>"


# ---------------------------------------------------------------------------
# AgentTable
# ---------------------------------------------------------------------------


class AgentTable:
    """Orchestrates multi-agent deliberation for a task.

    Directory layout under `.ralph-mode/table/`:
        table-state.json     – Current table state (round, phase, decisions)
        transcript.jsonl     – Full log of all messages
        rounds/
            round-001/
                plan.md          – Doer's plan
                critique.md      – Critic's review of plan
                decision.md      – Arbiter's decision (if escalated)
                implementation.md – Doer's implementation notes
                review.md        – Critic's review of implementation
                approval.md      – Arbiter's final approval
    """

    def __init__(self, ralph_dir: Optional[Path] = None) -> None:
        if ralph_dir is None:
            ralph_dir = Path.cwd() / ".ralph-mode"
        self.ralph_dir = Path(ralph_dir)
        self.table_dir = self.ralph_dir / TABLE_DIR
        self.rounds_dir = self.table_dir / ROUNDS_DIR
        self.transcript_file = self.table_dir / TRANSCRIPT_FILE
        self.state_file = self.table_dir / TABLE_STATE_FILE

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        task_description: str,
        *,
        max_rounds: int = 10,
        require_unanimous: bool = False,
        auto_escalate: bool = True,
    ) -> Dict[str, Any]:
        """Initialize a new Agent Table session.

        Args:
            task_description: The task to be deliberated on.
            max_rounds: Maximum deliberation rounds before forced decision.
            require_unanimous: If True, Critic must approve before Arbiter.
            auto_escalate: If True, automatically escalate to Arbiter on disagreement.

        Returns:
            The initial table state dict.
        """
        self.table_dir.mkdir(parents=True, exist_ok=True)
        self.rounds_dir.mkdir(parents=True, exist_ok=True)

        state: Dict[str, Any] = {
            "active": True,
            "task": task_description,
            "current_round": 0,
            "current_phase": Phase.PLAN.value,
            "max_rounds": max_rounds,
            "require_unanimous": require_unanimous,
            "auto_escalate": auto_escalate,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "outcome": None,  # "approved" | "rejected" | "max_rounds_reached"
            "total_messages": 0,
            "escalation_count": 0,
            "rounds_summary": [],
        }
        self._save_state(state)
        return state

    # ------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Check if an Agent Table session is active."""
        return self.state_file.exists()

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get current table state."""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.table_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Round Management
    # ------------------------------------------------------------------

    def new_round(self) -> Dict[str, Any]:
        """Start a new deliberation round.

        Returns:
            Updated state with new round number.

        Raises:
            ValueError: If table is not active or max rounds reached.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active. Call initialize() first.")

        if state["current_round"] >= state["max_rounds"]:
            state["outcome"] = "max_rounds_reached"
            state["active"] = False
            state["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._save_state(state)
            raise ValueError(f"Maximum rounds ({state['max_rounds']}) reached. " "Table session ended.")

        state["current_round"] += 1
        state["current_phase"] = Phase.PLAN.value
        self._save_state(state)

        # Create round directory
        round_dir = self._round_dir(state["current_round"])
        round_dir.mkdir(parents=True, exist_ok=True)

        return state

    def _round_dir(self, round_number: int) -> Path:
        return self.rounds_dir / f"round-{round_number:03d}"

    def get_round_dir(self, round_number: Optional[int] = None) -> Path:
        """Get the directory for a specific round (or current)."""
        if round_number is None:
            state = self.get_state()
            round_number = state["current_round"] if state else 1
        return self._round_dir(round_number)

    # ------------------------------------------------------------------
    # Message Handling
    # ------------------------------------------------------------------

    def send_message(self, message: AgentMessage) -> AgentMessage:
        """Record a message in the transcript and round directory.

        Args:
            message: The AgentMessage to record.

        Returns:
            The same message (with timestamp filled in).
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        # Ensure round number is set
        if message.round_number == 0:
            message.round_number = state["current_round"]

        # Append to transcript
        with open(self.transcript_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")

        # Write to round directory as readable markdown
        round_dir = self._round_dir(message.round_number)
        round_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{message.msg_type}.md"
        filepath = round_dir / filename

        # If file already exists (e.g. multiple critiques), append
        mode = "a" if filepath.exists() else "w"
        header = (
            f"\n---\n\n## {message.sender} → {message.recipient} ({message.msg_type})\n\n"
            if mode == "a"
            else (
                f"# {message.msg_type.title()}\n\n"
                f"**From:** {message.sender}  \n"
                f"**To:** {message.recipient}  \n"
                f"**Round:** {message.round_number}  \n"
                f"**Phase:** {message.phase}  \n"
                f"**Time:** {message.timestamp}  \n\n---\n\n"
            )
        )
        with open(filepath, mode, encoding="utf-8") as f:
            f.write(header + message.content + "\n")

        # Update state counters
        state["total_messages"] = state.get("total_messages", 0) + 1
        self._save_state(state)

        return message

    def get_messages(
        self,
        *,
        round_number: Optional[int] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        msg_type: Optional[str] = None,
    ) -> List[AgentMessage]:
        """Retrieve messages from transcript with optional filters."""
        if not self.transcript_file.exists():
            return []

        messages: List[AgentMessage] = []
        with open(self.transcript_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msg = AgentMessage.from_dict(data)
                    if round_number is not None and msg.round_number != round_number:
                        continue
                    if sender is not None and msg.sender != sender:
                        continue
                    if recipient is not None and msg.recipient != recipient:
                        continue
                    if msg_type is not None and msg.msg_type != msg_type:
                        continue
                    messages.append(msg)
                except (json.JSONDecodeError, KeyError):
                    pass
        return messages

    def get_last_message(
        self,
        *,
        sender: Optional[str] = None,
        msg_type: Optional[str] = None,
    ) -> Optional[AgentMessage]:
        """Get the most recent message matching the filters."""
        messages = self.get_messages(sender=sender, msg_type=msg_type)
        return messages[-1] if messages else None

    # ------------------------------------------------------------------
    # Phase Transitions (Protocol Logic)
    # ------------------------------------------------------------------

    def advance_phase(self) -> Dict[str, Any]:
        """Advance to the next phase in the current round.

        Phase order: plan → implement → resolve (if needed) → approve

        Returns:
            Updated state.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        current = state["current_phase"]

        transitions = {
            Phase.PLAN.value: Phase.IMPLEMENT.value,
            Phase.IMPLEMENT.value: Phase.RESOLVE.value,
            Phase.RESOLVE.value: Phase.APPROVE.value,
            Phase.APPROVE.value: Phase.PLAN.value,  # wraps to next round
        }

        next_phase = transitions.get(current, Phase.PLAN.value)

        if next_phase == Phase.PLAN.value and current == Phase.APPROVE.value:
            # Round complete — don't auto-advance, caller should call new_round()
            state["current_phase"] = Phase.APPROVE.value
        else:
            state["current_phase"] = next_phase

        self._save_state(state)
        return state

    def set_phase(self, phase: str) -> Dict[str, Any]:
        """Explicitly set the current phase."""
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        if phase not in [p.value for p in Phase]:
            raise ValueError(f"Invalid phase: {phase}. Must be one of {[p.value for p in Phase]}")

        state["current_phase"] = phase
        self._save_state(state)
        return state

    # ------------------------------------------------------------------
    # High-Level Protocol Methods
    # ------------------------------------------------------------------

    def submit_plan(self, plan_content: str) -> AgentMessage:
        """Doer submits an implementation plan for Critic review.

        Args:
            plan_content: The plan text.

        Returns:
            The recorded plan message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content=plan_content,
            round_number=state["current_round"],
            phase=Phase.PLAN.value,
        )
        return self.send_message(msg)

    def submit_critique(self, critique_content: str, *, approved: bool = False) -> AgentMessage:
        """Critic submits a critique of the Doer's plan or implementation.

        Args:
            critique_content: The critique text.
            approved: Whether the Critic approves the current work.

        Returns:
            The recorded critique message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_CRITIC,
            recipient=ROLE_DOER,
            msg_type=MessageType.CRITIQUE.value,
            content=critique_content,
            round_number=state["current_round"],
            phase=state["current_phase"],
            metadata={"approved": approved},
        )
        self.send_message(msg)

        # Auto-escalate to arbiter if not approved and auto_escalate is on
        if not approved and state.get("auto_escalate"):
            self.escalate(reason="Critic did not approve. Escalating to Arbiter for decision.")

        return msg

    def submit_implementation(self, implementation_notes: str) -> AgentMessage:
        """Doer submits implementation notes after making changes.

        Args:
            implementation_notes: Description of what was implemented.

        Returns:
            The recorded implementation message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.IMPLEMENTATION.value,
            content=implementation_notes,
            round_number=state["current_round"],
            phase=Phase.IMPLEMENT.value,
        )
        self.send_message(msg)

        # Advance to implement phase
        state["current_phase"] = Phase.IMPLEMENT.value
        self._save_state(state)

        return msg

    def submit_review(self, review_content: str, *, approved: bool = False) -> AgentMessage:
        """Critic submits a review of the Doer's implementation.

        Args:
            review_content: The review text.
            approved: Whether the Critic approves the implementation.

        Returns:
            The recorded review message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_CRITIC,
            recipient=ROLE_DOER,
            msg_type=MessageType.REVIEW.value,
            content=review_content,
            round_number=state["current_round"],
            phase=Phase.IMPLEMENT.value,
            metadata={"approved": approved},
        )
        self.send_message(msg)

        if not approved and state.get("auto_escalate"):
            self.escalate(reason="Critic did not approve implementation. Escalating to Arbiter.")

        return msg

    def escalate(self, reason: str = "") -> AgentMessage:
        """Escalate to the Arbiter for a final decision.

        Args:
            reason: Why the escalation is needed.

        Returns:
            The recorded escalation message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        state["escalation_count"] = state.get("escalation_count", 0) + 1
        state["current_phase"] = Phase.RESOLVE.value
        self._save_state(state)

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_ARBITER,
            msg_type=MessageType.ESCALATION.value,
            content=reason,
            round_number=state["current_round"],
            phase=Phase.RESOLVE.value,
        )
        return self.send_message(msg)

    def submit_decision(self, decision_content: str, *, side_with: str = "") -> AgentMessage:
        """Arbiter submits a decision resolving a disagreement.

        Args:
            decision_content: The decision text with reasoning.
            side_with: Which agent the arbiter sides with ("doer" or "critic").

        Returns:
            The recorded decision message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_ARBITER,
            recipient=ROLE_DOER,
            msg_type=MessageType.DECISION.value,
            content=decision_content,
            round_number=state["current_round"],
            phase=Phase.RESOLVE.value,
            metadata={"side_with": side_with},
        )
        self.send_message(msg)

        # Move to approve phase
        state["current_phase"] = Phase.APPROVE.value
        self._save_state(state)

        return msg

    def submit_approval(self, notes: str = "") -> AgentMessage:
        """Arbiter gives final approval for the round.

        Args:
            notes: Optional notes about the approval.

        Returns:
            The recorded approval message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_ARBITER,
            recipient=ROLE_DOER,
            msg_type=MessageType.APPROVAL.value,
            content=notes or "Approved. Proceed with implementation.",
            round_number=state["current_round"],
            phase=Phase.APPROVE.value,
            metadata={"approved": True},
        )
        self.send_message(msg)

        # Record round summary
        summary = {
            "round": state["current_round"],
            "outcome": "approved",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        state.setdefault("rounds_summary", []).append(summary)
        self._save_state(state)

        return msg

    def submit_rejection(self, reason: str) -> AgentMessage:
        """Arbiter rejects the current approach and requests rework.

        Args:
            reason: Why the work is rejected.

        Returns:
            The recorded rejection message.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_ARBITER,
            recipient=ROLE_DOER,
            msg_type=MessageType.REJECTION.value,
            content=reason,
            round_number=state["current_round"],
            phase=Phase.APPROVE.value,
            metadata={"approved": False},
        )
        self.send_message(msg)

        # Record round summary
        summary = {
            "round": state["current_round"],
            "outcome": "rejected",
            "reason": reason,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        state.setdefault("rounds_summary", []).append(summary)
        self._save_state(state)

        return msg

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def finalize(self, outcome: str = "approved") -> Dict[str, Any]:
        """Finalize the Agent Table session.

        Args:
            outcome: Final outcome ("approved", "rejected", "max_rounds_reached").

        Returns:
            Final state.
        """
        state = self.get_state()
        if not state:
            raise ValueError("No active Agent Table session.")

        state["active"] = False
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        state["outcome"] = outcome
        self._save_state(state)

        return state

    def reset(self) -> None:
        """Remove all Agent Table data."""
        import shutil

        if self.table_dir.exists():
            shutil.rmtree(self.table_dir)

    # ------------------------------------------------------------------
    # Context Building (for feeding to AI agents)
    # ------------------------------------------------------------------

    def build_doer_context(self) -> str:
        """Build context prompt for the Doer agent.

        Includes: task, latest critique, latest arbiter decision, history.
        """
        state = self.get_state()
        if not state:
            return ""

        parts: List[str] = []
        parts.append(f"# Agent Table — Doer Context (Round {state['current_round']})\n")
        parts.append(f"## Task\n\n{state['task']}\n")
        parts.append(f"## Current Phase: {state['current_phase']}\n")

        # Latest critique
        critique = self.get_last_message(sender=ROLE_CRITIC, msg_type=MessageType.CRITIQUE.value)
        if critique:
            parts.append(f"## Latest Critique from Critic\n\n{critique.content}\n")
            parts.append(f"**Approved:** {critique.metadata.get('approved', False)}\n")

        # Latest review
        review = self.get_last_message(sender=ROLE_CRITIC, msg_type=MessageType.REVIEW.value)
        if review:
            parts.append(f"## Latest Review from Critic\n\n{review.content}\n")
            parts.append(f"**Approved:** {review.metadata.get('approved', False)}\n")

        # Latest arbiter decision
        decision = self.get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.DECISION.value)
        if decision:
            parts.append(f"## Arbiter's Decision\n\n{decision.content}\n")
            parts.append(f"**Sides with:** {decision.metadata.get('side_with', 'N/A')}\n")

        # Approval/rejection
        approval = self.get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.APPROVAL.value)
        rejection = self.get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.REJECTION.value)
        if approval:
            parts.append(f"## ✅ Arbiter Approval\n\n{approval.content}\n")
        if rejection:
            parts.append(f"## ❌ Arbiter Rejection\n\n{rejection.content}\n")

        return "\n".join(parts)

    def build_critic_context(self) -> str:
        """Build context prompt for the Critic agent.

        Includes: task, Doer's latest plan/implementation, history.
        """
        state = self.get_state()
        if not state:
            return ""

        parts: List[str] = []
        parts.append(f"# Agent Table — Critic Context (Round {state['current_round']})\n")
        parts.append(f"## Task\n\n{state['task']}\n")
        parts.append(f"## Current Phase: {state['current_phase']}\n")

        # Latest plan from Doer
        plan = self.get_last_message(sender=ROLE_DOER, msg_type=MessageType.PLAN.value)
        if plan:
            parts.append(f"## Doer's Plan\n\n{plan.content}\n")

        # Latest implementation from Doer
        impl = self.get_last_message(sender=ROLE_DOER, msg_type=MessageType.IMPLEMENTATION.value)
        if impl:
            parts.append(f"## Doer's Implementation\n\n{impl.content}\n")

        # Arbiter's latest decision (for context)
        decision = self.get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.DECISION.value)
        if decision:
            parts.append(f"## Arbiter's Previous Decision\n\n{decision.content}\n")

        parts.append(
            "\n## Your Role\n\n"
            "You are the **Critic**. Review the Doer's work critically.\n"
            "- Identify bugs, logic errors, security issues\n"
            "- Suggest improvements\n"
            "- State clearly if you APPROVE or REJECT\n"
            "- If you reject, explain exactly what needs to change\n"
        )

        return "\n".join(parts)

    def build_arbiter_context(self) -> str:
        """Build context prompt for the Arbiter agent.

        Includes: task, full conversation between Doer and Critic.
        """
        state = self.get_state()
        if not state:
            return ""

        parts: List[str] = []
        parts.append(f"# Agent Table — Arbiter Context (Round {state['current_round']})\n")
        parts.append(f"## Task\n\n{state['task']}\n")
        parts.append(f"## Escalation #{state.get('escalation_count', 0)}\n")

        # All messages this round
        round_messages = self.get_messages(round_number=state["current_round"])
        if round_messages:
            parts.append("## Full Conversation This Round\n")
            for msg in round_messages:
                role_emoji = {"doer": "🛠️", "critic": "🔍", "arbiter": "⚖️"}.get(msg.sender, "")
                parts.append(f"### {role_emoji} {msg.sender} → {msg.recipient} ({msg.msg_type})\n")
                parts.append(f"{msg.content}\n")

        parts.append(
            "\n## Your Role\n\n"
            "You are the **Arbiter**. You have final authority.\n"
            "- Read both the Doer's work and the Critic's feedback\n"
            "- Make a fair, well-reasoned decision\n"
            "- State which approach is correct and why\n"
            "- Your decision is final — the Doer must follow it\n"
        )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Convenience: Run a Full Protocol Round
    # ------------------------------------------------------------------

    def run_protocol_round(
        self,
        plan: str,
        critique: str,
        critique_approved: bool,
        implementation: str = "",
        review: str = "",
        review_approved: bool = False,
        arbiter_decision: str = "",
        arbiter_side_with: str = "",
        arbiter_approves: bool = True,
    ) -> Dict[str, Any]:
        """Run a complete deliberation round programmatically.

        Useful for testing and automated workflows. In real usage,
        each step is typically invoked separately as each agent runs.

        Args:
            plan: Doer's plan text.
            critique: Critic's review of the plan.
            critique_approved: Whether critic approves the plan.
            implementation: Doer's implementation notes (if plan approved).
            review: Critic's review of implementation.
            review_approved: Whether critic approves implementation.
            arbiter_decision: Arbiter's decision text (if escalated).
            arbiter_side_with: Who arbiter agrees with.
            arbiter_approves: Whether arbiter gives final approval.

        Returns:
            Updated state after the round.
        """
        self.new_round()

        # Phase 1: Plan
        self.submit_plan(plan)
        self.submit_critique(critique, approved=critique_approved)

        # If critic approved, proceed to implementation
        if critique_approved and implementation:
            self.submit_implementation(implementation)

            if review:
                self.submit_review(review, approved=review_approved)

        # Arbiter decision (if there was an escalation or at the end)
        if arbiter_decision:
            self.submit_decision(arbiter_decision, side_with=arbiter_side_with)

        # Final approval or rejection
        if arbiter_approves:
            self.submit_approval()
        else:
            self.submit_rejection(arbiter_decision or "Rejected by Arbiter.")

        return self.get_state()

    # ------------------------------------------------------------------
    # Status & Summary
    # ------------------------------------------------------------------

    def status(self) -> Optional[Dict[str, Any]]:
        """Get a human-readable status summary."""
        state = self.get_state()
        if not state:
            return None

        messages = self.get_messages()
        msg_by_sender: Dict[str, int] = {}
        for msg in messages:
            msg_by_sender[msg.sender] = msg_by_sender.get(msg.sender, 0) + 1

        return {
            "active": state.get("active", False),
            "task": state.get("task", ""),
            "current_round": state.get("current_round", 0),
            "max_rounds": state.get("max_rounds", 10),
            "current_phase": state.get("current_phase", ""),
            "outcome": state.get("outcome"),
            "total_messages": state.get("total_messages", 0),
            "escalation_count": state.get("escalation_count", 0),
            "messages_by_agent": msg_by_sender,
            "rounds_summary": state.get("rounds_summary", []),
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
        }

    def get_transcript_text(self) -> str:
        """Get the full transcript as readable text."""
        messages = self.get_messages()
        if not messages:
            return "No messages yet."

        lines: List[str] = []
        current_round = 0
        for msg in messages:
            if msg.round_number != current_round:
                current_round = msg.round_number
                lines.append(f"\n{'='*60}")
                lines.append(f"  ROUND {current_round}")
                lines.append(f"{'='*60}\n")

            emoji = {"doer": "🛠️", "critic": "🔍", "arbiter": "⚖️"}.get(msg.sender, "")
            lines.append(f"{emoji} [{msg.sender}] → [{msg.recipient}] ({msg.msg_type})")
            lines.append(f"   {msg.content[:200]}{'...' if len(msg.content) > 200 else ''}")
            lines.append("")

        return "\n".join(lines)
