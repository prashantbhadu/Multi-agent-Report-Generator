"""
CLI Entry Point for Multi-Agent Report Generator.

Provides a command-line interface for generating reports with full control
over parameters and output options.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import json

from report_generator import generate_report


def main():
    """Main CLI entry point."""

    parser = argparse.ArgumentParser(
        description="Multi-Agent Report Generator - Generate high-quality research reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate an academic report on quantum computing
  python cli.py --topic "Quantum Computing Advances" --type academic

  # Generate a business report with custom quality threshold
  python cli.py --topic "AI Market Trends" --type business --threshold 8.0

  # Generate with verbose output and save to specific directory
  python cli.py --topic "Climate Change" --output ./reports/ -v
        """
    )

    # Required arguments
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="Research topic for report generation"
    )

    # Optional arguments
    parser.add_argument(
        "--type",
        type=str,
        choices=["academic", "business", "technical", "news-style"],
        default="academic",
        help="Type of report to generate (default: academic)"
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=7.0,
        help="Quality threshold score 0-10 (default: 7.0)"
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=4,
        help="Maximum refinement iterations (default: 4)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="./reports/",
        help="Output directory for reports (default: ./reports/)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON (in addition to markdown)"
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save report to file"
    )

    args = parser.parse_args()

    # Validate quality threshold
    if not 0.0 <= args.threshold <= 10.0:
        parser.error("Quality threshold must be between 0.0 and 10.0")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"📊 Multi-Agent Report Generator CLI")
        print(f"{'='*60}")
        print(f"Topic: {args.topic}")
        print(f"Report Type: {args.type}")
        print(f"Quality Threshold: {args.threshold}/10")
        print(f"Max Iterations: {args.max_iterations}")
        print(f"Output Directory: {output_dir.absolute()}")
        print(f"{'='*60}\n")

    try:
        # Generate report
        result = generate_report(
            topic=args.topic,
            report_type=args.type,
            quality_threshold=args.threshold,
            max_iterations=args.max_iterations,
        )

        if args.verbose:
            print(f"\n{'='*60}")
            print(f"✨ Report Generation Complete!")
            print(f"{'='*60}")
            print(f"Final Score: {result['final_score']}/10")
            print(f"Iterations: {result['iterations_completed']}")
            print(f"Quality Threshold Met: {result['quality_threshold_met']}")

        # Save markdown report
        if not args.no_save:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            md_filename = output_dir / f"report_{timestamp}.md"

            with open(md_filename, "w", encoding="utf-8") as f:
                # Write metadata header
                f.write(f"# Research Report\n\n")
                f.write(f"**Topic:** {result['topic']}\n")
                f.write(f"**Report Type:** {result['report_type']}\n")
                f.write(f"**Generated:** {result['timestamp']}\n")
                f.write(f"**Quality Score:** {result['final_score']:.1f}/10\n")
                f.write(f"**Quality Threshold Met:** {result['quality_threshold_met']}\n")
                f.write(f"**Iterations:** {result['iterations_completed']}\n")
                f.write(f"\n---\n\n")

                # Write report content
                f.write(result['final_report'])

            if args.verbose:
                print(f"\n📄 Markdown Report: {md_filename}")

        # Save JSON metadata
        if args.json:
            json_filename = output_dir / f"report_{timestamp}_metadata.json"

            # Prepare JSON-serializable data
            json_result = {
                "topic": result["topic"],
                "report_type": result["report_type"],
                "timestamp": result["timestamp"],
                "final_score": result["final_score"],
                "quality_threshold_met": result["quality_threshold_met"],
                "iterations_completed": result["iterations_completed"],
                "refinement_history": result["refinement_history"],
            }

            if result.get("final_review"):
                review = result["final_review"]
                json_result["final_review"] = {
                    "score": {
                        "factual_accuracy": review.score.factual_accuracy,
                        "completeness": review.score.completeness,
                        "clarity": review.score.clarity,
                        "structure": review.score.structure,
                        "depth": review.score.depth,
                        "average": review.score.average_score,
                    },
                    "strengths": review.strengths,
                    "weaknesses": review.weaknesses,
                    "suggestions": review.suggestions,
                }

            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(json_result, f, indent=2)

            if args.verbose:
                print(f"📊 JSON Metadata: {json_filename}")

        if args.verbose:
            print(f"\n✅ Report generation successful!")

        return 0

    except KeyboardInterrupt:
        print("\n⚠️ Report generation cancelled by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
