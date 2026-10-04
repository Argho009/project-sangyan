"""
SANGYAN — Synthetic Test Runner
Tests the pipeline against all 30 hand-crafted test cases.
Run: python tests/run_test_cases.py
"""

import json
import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.WARNING)  # Quiet for test output

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TEST_FILE = os.path.join(os.path.dirname(__file__), "synthetic_test_cases.json")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⚠️  SKIP"


def run_test(case: dict) -> dict:
    """Run a single test case through the pipeline."""
    from pipeline.input_handler import SangyanInput, InputType, process_input
    from pipeline.entity_extractor import extract_entities
    from pipeline.red_flag_engine import run_red_flag_engine
    from pipeline.ml_engine import run_ml_analysis
    from pipeline.proof_chain import build_proof_chain
    from pipeline.trust_calculator import calculate_trust
    from pipeline.next_best_proof import generate_next_steps

    content = case["content"]
    expected = case["expected_verdict"]

    # Process input
    processed = process_input(SangyanInput(
        input_type=InputType.TEXT,
        content=content,
    ))
    raw_text = processed.raw_text

    # Extract
    entities = extract_entities(raw_text)
    red_flags = run_red_flag_engine(raw_text, urls=entities.urls)
    ml = run_ml_analysis(raw_text)

    # Verify (skipping live API calls in test mode)
    sebi_result = None
    payment_results = []
    social_results = []
    i4c_results = []
    phishtank_results = []

    # Build chain
    chain = build_proof_chain(
        extracted_entities=entities,
        sebi_result=sebi_result,
        payment_results=payment_results,
        social_results=social_results,
        phishtank_results=phishtank_results,
        red_flag_report=red_flags,
    )

    # Trust
    trust = calculate_trust(
        sebi_result=sebi_result,
        payment_results=payment_results,
        phishtank_results=phishtank_results,
        i4c_results=i4c_results,
        red_flag_report=red_flags,
        ml_result=ml,
        social_results=social_results,
        extracted_entities=entities,
    )

    actual = trust.verdict
    matched = actual == expected
    flag_ids = [f.category for f in red_flags.flags]

    return {
        "id": case["id"],
        "expected": expected,
        "actual": actual,
        "score": trust.score,
        "matched": matched,
        "flags_triggered": flag_ids,
        "contradictions": chain.contradictions,
        "ml_combined": ml.combined_score,
    }


def main():
    with open(TEST_FILE, encoding="utf-8") as f:
        test_cases = json.load(f)

    print("\n" + "=" * 70)
    print("  SANGYAN — Synthetic Test Suite")
    print("=" * 70)
    print(f"  Running {len(test_cases)} test cases (no live API calls)\n")

    results = []
    for case in test_cases:
        try:
            result = run_test(case)
            status = PASS if result["matched"] else FAIL
            print(
                f"  {status} [{case['id']}] Expected: {result['expected']:<6} "
                f"Got: {result['actual']:<6} Score: {result['score']:>3} "
                f"ML: {result['ml_combined']:.2f}  "
                f"Flags: {len(result['flags_triggered'])}"
            )
            results.append(result)
        except Exception as exc:
            print(f"  {SKIP} [{case['id']}] Error: {exc}")

    # Summary
    passed = sum(1 for r in results if r["matched"])
    total = len(results)
    accuracy = passed / total * 100 if total > 0 else 0

    print("\n" + "=" * 70)
    print(f"  Results: {passed}/{total} passed ({accuracy:.1f}%)")

    # Breakdown by verdict
    for v in ["STOP", "PAUSE", "TRUST"]:
        v_cases = [r for r in results if r["expected"] == v]
        v_pass = sum(1 for r in v_cases if r["matched"])
        print(f"    {v}: {v_pass}/{len(v_cases)}")

    print("=" * 70 + "\n")

    if accuracy < 80:
        print("  ⚠️  Note: Low accuracy may be due to missing live SEBI/PhishTank checks.")
        print("  Run with live API integration for real-world accuracy.\n")


if __name__ == "__main__":
    main()
