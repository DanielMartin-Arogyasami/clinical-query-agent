"""CLI pipeline runner. [FIX H6]"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    from config.settings import settings
    settings.ensure_dirs()

    parser = argparse.ArgumentParser(description="Clinical Trial MAS Pipeline Runner")
    parser.add_argument("--study", default="SYNTH-001")
    parser.add_argument("--data", default="data/synthetic/vs_anomalous.csv")
    parser.add_argument("--domain", default="VS")
    parser.add_argument("--agent", default=None)
    parser.add_argument("--protocol", default="")
    parser.add_argument("--output", default="results/pipeline_output.json")
    args = parser.parse_args()

    protocol_text = Path(args.protocol).read_text(encoding="utf-8") if args.protocol and Path(args.protocol).exists() else ""

    if args.agent:
        from src.audit.trail import AuditTrail
        from src.agents.query_generation import QueryGenerationAgent
        from src.agents.crf_design import CRFDesignAgent
        from src.agents.edc_config import EDCConfigAgent
        from src.agents.data_cleaning import DataCleaningAgent
        from src.agents.programming import ProgrammingAgent

        agents_map = {
            "query_generation": QueryGenerationAgent,
            "crf_design": CRFDesignAgent,
            "edc_config": EDCConfigAgent,
            "data_cleaning": DataCleaningAgent,
            "programming": ProgrammingAgent,
        }
        agent_cls = agents_map.get(args.agent)
        if not agent_cls:
            print(f"Unknown agent: {args.agent}. Choose from: {list(agents_map)}")
            return
        audit = AuditTrail(run_id=f"single-{args.agent}")
        agent = agent_cls(audit_trail=audit)
        result = agent.run({
            "study_id": args.study,
            "data_path": args.data,
            "domain": args.domain,
            "protocol_text": protocol_text,
        })
    else:
        from src.graph.pipeline import run_pipeline
        result, _ = run_pipeline(
            study_id=args.study,
            protocol_text=protocol_text,
            data_path=args.data,
            domain=args.domain,
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in result.items() if k != "dataframe"}, f, indent=2, default=str)
    print(f"\nOK: Output saved to {output_path}")


if __name__ == "__main__":
    main()
