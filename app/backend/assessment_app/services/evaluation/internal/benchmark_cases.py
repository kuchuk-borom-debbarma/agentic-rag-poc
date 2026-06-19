"""Static AWS Customer Agreement benchmark cases."""

from assessment_app.services.evaluation.public.models import BenchmarkCase


BENCHMARK_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        id="eval-001-simple",
        query="What does AWS promise about securing customer content?",
        expected_answer="AWS will implement reasonable and appropriate measures designed to help secure Your Content against accidental or unlawful loss, access, or disclosure.",
        expected_section_numbers=["1.3"],
        answer_type="answerable",
        tags=["simple", "security"],
    ),
    BenchmarkCase(
        id="eval-002-simple",
        query="What must a customer have to access the AWS services?",
        expected_answer="A customer must have an AWS account associated with a valid email address and a valid form of payment.",
        expected_section_numbers=["2.1"],
        answer_type="answerable",
        tags=["simple", "accounts"],
    ),
    BenchmarkCase(
        id="eval-003-simple",
        query="How often does AWS calculate and bill service fees?",
        expected_answer="AWS calculates and bills fees and charges monthly, but may bill more frequently if it reasonably suspects fraud or non-payment risk.",
        expected_section_numbers=["3.1"],
        answer_type="answerable",
        tags=["simple", "billing"],
    ),
    BenchmarkCase(
        id="eval-004-mid",
        query="Can AWS move my content out of the AWS regions I select?",
        expected_answer="AWS will not move Your Content from the AWS regions you select except as necessary to comply with law or a binding governmental order.",
        expected_section_numbers=["1.4"],
        answer_type="answerable",
        tags=["mid", "privacy", "regions"],
    ),
    BenchmarkCase(
        id="eval-005-mid",
        query="What is the aggregate liability cap under the agreement?",
        expected_answer="Aggregate liability will not exceed amounts paid by the customer to AWS for the services that gave rise to liability during the 12 months before the liability arose, subject to stated exceptions.",
        expected_section_numbers=["9.2"],
        answer_type="answerable",
        tags=["mid", "liability", "damages"],
    ),
    BenchmarkCase(
        id="eval-006-mid",
        query="Can either party assign the agreement freely without consent?",
        expected_answer="The customer may not assign or transfer the agreement without AWS prior written consent. AWS may assign without consent for merger, acquisition, asset sale, affiliate assignment, or corporate reorganization.",
        expected_section_numbers=["11.1"],
        answer_type="answerable",
        tags=["mid", "assignment"],
    ),
    BenchmarkCase(
        id="eval-007-complex",
        query="Who handles intellectual property infringement claims involving both the Services and Your Content?",
        expected_answer="AWS defends the customer against third-party claims that the Services infringe intellectual property rights, while the customer defends AWS against claims that Your Content infringes or misappropriates rights.",
        expected_section_numbers=["7.2"],
        answer_type="answerable",
        tags=["complex", "indemnification", "ip", "multi-hop"],
    ),
    BenchmarkCase(
        id="eval-008-complex",
        query="If my account is suspended because I breached my payment obligations, do I still receive service credits for downtime?",
        expected_answer="No. During suspension the customer is not entitled to service credits under Service Level Agreements.",
        expected_section_numbers=["4.1", "4.2"],
        answer_type="answerable",
        tags=["complex", "suspension", "sla", "payment"],
    ),
    BenchmarkCase(
        id="eval-009-extreme",
        query="If my end user violates the agreement by infringing on a third party's intellectual property, what am I required to do immediately, and who is responsible for defending the resulting claim?",
        expected_answer="The customer must immediately suspend the End User's access (Section 2.5), and the customer is responsible for defending AWS against the third-party intellectual property claim (Section 7.1 or 7.2).",
        expected_section_numbers=["2.5", "7.1", "7.2"],
        answer_type="answerable",
        tags=["extreme", "end-users", "indemnification", "multi-hop"],
    ),
    BenchmarkCase(
        id="eval-010-extreme",
        query="What uptime percentage does AWS guarantee for every service across all regions in this agreement?",
        expected_answer="The agreement does not state one universal uptime percentage for every service; Service Level Agreements apply separately to certain Services.",
        expected_section_numbers=["1.1", "1.6"],
        answer_type="unanswerable",
        tags=["extreme", "unanswerable", "hallucination-check"],
    ),
    BenchmarkCase(
        id="eval-011-unanswerable-easy",
        query="What are the specific hourly pricing rates for Amazon EC2 t3.micro instances?",
        expected_answer="The agreement does not contain specific pricing rates for any services; pricing is described on the AWS Site.",
        expected_section_numbers=[],
        answer_type="unanswerable",
        tags=["easy", "unanswerable", "pricing"],
    ),
    BenchmarkCase(
        id="eval-012-unanswerable-mid",
        query="How many days does AWS retain my data in a backup repository after I permanently close my account?",
        expected_answer="The agreement does not specify an exact number of days for data retention after account closure; it only states that post-termination, AWS will delete Your Content.",
        expected_section_numbers=["5.3"],
        answer_type="unanswerable",
        tags=["mid", "unanswerable", "data-retention"],
    ),
    BenchmarkCase(
        id="eval-013-unanswerable-hard",
        query="What is the exact monetary penalty AWS must pay a customer if a security breach is directly caused by an AWS employee's negligence?",
        expected_answer="The agreement does not specify exact monetary penalties for employee negligence or security breaches; it only outlines general aggregate liability caps and exclusions for indirect damages.",
        expected_section_numbers=["9.1", "9.2"],
        answer_type="unanswerable",
        tags=["hard", "unanswerable", "liability", "hallucination-check"],
    ),
)


def get_benchmark_cases() -> list[BenchmarkCase]:
    """Return benchmark cases as a fresh list."""
    return list(BENCHMARK_CASES)
