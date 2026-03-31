Topics: `agentic-ai`, `langgraph`, `clinical-data-management`, `anomaly-detection`

# Clinical Query Agent (clinical-query-agent)

> **⚠️ INDEPENDENCE & DATA DISCLAIMER:** This reference implementation uses exclusively publicly available protocols and synthetic datasets. It does not reflect, derive from, or use any proprietary systems, workflows, data, or trade secrets of any current or past employers. This work is an independent academic and open-source contribution.

## Overview
A multi-agent workflow orchestrated via `LangGraph` to automate the detection of data anomalies, verify them against protocol rules, and generate targeted data queries for clinical trial sites. This is the companion repository to the preprint: *"Multi-Agent AI Architectures for Clinical Trial Data Management"*.

## Architecture
This framework implements a "Supervisor + Specialists" topology:
* **Reviewer Agent:** Inspects rows of synthetic SDTM data for logical or statistical outliers.
* **Protocol RAG Agent:** Checks detected anomalies against inclusion/exclusion criteria or safety thresholds defined in the protocol.
* **Query Gen Agent:** Drafts professional, actionable queries targeted at the clinical site.
* **Supervisor:** Orchestrates routing and enforces a Human-in-the-Loop (HITL) interrupt before any query is finalized.

## Public Dataset Acquisition
1. **Clinical Protocols:** Download public XML/JSON Phase III protocol synopses from [ClinicalTrials.gov](https://clinicaltrials.gov/) and place them in `data/protocols/`.
2. **Synthetic SDTM Data:** Generate synthetic datasets using [cdiscdataset.com](https://www.cdiscdataset.com/) or run our included synthetic data generator:
   ```bash
   python src/data_gen/generate_synthetic_vs.py --records 100 --inject-anomalies
Quick Start
Bash

# Install dependencies
pip install -r requirements.txt

# Set up your LLM API keys
cp .env.example .env

# Run the Jupyter Notebook demonstration
jupyter notebook notebooks/01_multi_agent_anomaly_detection.ipynb
Citation
Code snippet

@article{arogyasami2026multiagent,
  title={Multi-Agent AI Architectures for Clinical Trial Data Management},
  author={Arogyasami, DanielMartin},
  year={2026},
  journal={Preprint}
}

---
