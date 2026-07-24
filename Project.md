# Agentic AI Course – Individual Project (55%)

## Overview

You will design, implement, and evaluate an AI agentic system (multi-agent workflow) to solve a realistic problem in a chosen domain (e.g., education, productivity, health assistance, customer support, creative tools, data analysis, etc.).

The project is individual (not group work) and is worth 55% of the final grade.

Your system should combine:

- Tool-using or API-calling agents,

- A multi-agent workflow (e.g., planner–executor, reviewer–critic, specialized role agents),

- A user-facing front-end interface,

- A clear evaluation of system behavior, risks, and usefulness.



## Grading Breakdown (55%)

- Proposal – 10%

- Milestone I: Multi-agent Workflow / System Design– 5%

- Milestone II: Evaluation Plan & Pilot Results – 5%

- Milestone III: Front-end – 5%

- Peer Rating / Feedback – 5%

- Final Presentation (10-min video) – 10%

- Final Implementation & Report – 15%

- Total: 55%




## 1. Project Proposal (10%) – Released on Week 1, Due Week 2

Goal: Clearly define the problem, users, and agentic solution.
Your written proposal (2–3 pages) should include:

### Problem statement & motivation

- What real-world business problem are you addressing?

- Who are the target users?

- Why is an agentic AI solution appropriate here (vs. a simple single-call model)?

### Use cases & scenarios

- 2–3 concrete user scenarios (e.g., “A student wants to…”).

- For each scenario, what tasks will the agent(s) perform?

### Initial system design

- Preliminary list of agents and their roles (e.g., Planner, Data Fetcher, Summarizer, Critic).

- Expected tools/APIs or data sources (e.g., web search, internal API, local files).

### Feasibility & risks

- Potential challenges (e.g., hallucination, long context, tool failures).

- Any constraints (e.g., rate limits, privacy constraints, computation).

- Time lime for project execution (cannot extend beyond the class duration).

- Deliverable: PDF or markdown document uploaded individually.




## 2. Milestone I – Multi-agent Workflow / System Design (5%) – Released on Week 1, Due Week 3

Goal: Implement a multi-agent pipeline or workflow.

Requirements:

- At least two distinct agents with different roles, such as:
  - Planner / Task Decomposer

  - Tool-using Executor

  - Critic / Verifier

  - Data Collector vs. Analyzer

  - Domain Expert vs. Explainer

    - **\**These roles may vary based on the problem you are solving.**

- A defined coordination mechanism, e.g.:

  - Orchestrated by a controller agent,

  - Fixed pipeline (A → B → C),

  - Loop (generate–critique–revise) with stopping conditions.

You should provide:

1. Agent Architecture Diagram

  - Could be similar to an ER diagram in the DB project, but now shows:

    - Agents,

    - Tools/APIs,

    - Dataflow/workflow between them.

2. Brief design document (2–3 pages) describing:

  - Each agent’s role and input/output format,

  - How they communicate,

  - How failures or low-quality outputs are handled.

Deliverables:

- Architecture diagram image (high resolution, e.g., PNG/PDF).

- Short design document.

- Updated code with multi-agent workflow implemented.




## 3. Milestone II – System Evaluation (5%) – Released on Week 1, Due Week 4

Goal: Design and run an evaluation of your agentic system.

You should:

  - Define evaluation criteria, e.g.:

  - Task success rate (did the system complete the user’s goal?),

  - Output quality (helpfulness, correctness),

  - Efficiency (number of steps/calls),

  - User satisfaction (if you collect human ratings),

  - HHH score [helpful (i.e. fulfill the user’s intent and needs), honest (accurate, well-sourced information and indicate when it is unsure, rather than inventing facts or hallucinating), harmless (avoid producing toxic, biased, illegal, or offensive content)]

2. Define evaluation method, e.g.:

Scripted benchmark tasks / test set,

Human evaluation (small user study),

Model-based evaluation (e.g., an LLM judge with clear rubric).

3. Collect pilot results

At least a small sample (e.g., 10–20 test cases or 5+ users).

Show basic statistics or summary.

4. Reflect on failure cases

Provide 2–3 concrete examples where the system fails and analyze why.

5. Risk assessment

Create a risk assessment and provide risk matrix for your agentic system

Deliverables:

2–3 pages with evaluation plan, risk assessments & pilot test report. Don’t forget to summarize the findings/results in tables.

Any evaluation scripts or notebooks.




## 4. Milestone III – Front-end for Your Agent (5%) – Released on Week 1, Due Week 5

Goal: Build a simple user interface for interacting with your system.

**Requirements:**

- A web or mobile interface (e.g., n8n, vellum, opal, simple React app, Flask web app, mobile UI, etc.) that:

  - Allows a user to interact with your agentic system (i.e. submit inputs / tasks to the agents).

  - Displays the agent’s response.

- Doesn’t need to be fully styled, but should be:

  - Functional and clearly structured,

  - Usable by a non-technical user.

Deliverables:

Short description (1–2 pages or README) with:

Screenshots of the UI,

A brief explanation of the tech stack.

Code for the front-end (submitted as part of the repo). [You may submit a description of the front-end if you are using a no-code/low-code platform.]




5. Peer Rating / Feedback (5%) – due Week 6

Each student will attend the final presentations in Week 6, and will need to provide structured feedback (using the rubric provided) on:

Problem clarity,

System design,

Quality of evaluation,

Clarity of presentation,

Technical & functional rubrics are to be provided in class.

Your grade for this part is based on:

Live in-class demo of your agentic system (no show will result in 0 points),

Completion of peer reviews on time,

Thoughtfulness and constructiveness of feedback provided for your peers’ projects.

6. Final Presentation – 10-Minute Video (10%) – due Week 6

Record a 10-minute video presentation (with slides) demonstrating your project.

In the video, you should:

Introduce the main problem

What business problem are you solving?

Why is it important and why is an agentic AI approach suitable?

Walk through the system/agent design

Show your agent architecture diagram:

Agents, tools/APIs, data flow.

Explain key design choices (why these roles, why this workflow).

Explain the data / tools you use

What data sources or APIs are used?

How do you handle context, memory, and prompts?

[Main part ~ 5 minutes]: Demo & analysis

Show live or recorded demos for 2–3 representative tasks.

Focus on:

What the system does step-by-step (not just the final answer),

What worked well and what limitations you observed.

Evaluation & reflection

Summarize evaluation setup and results (no need to show every detail).

Discuss:

How well the system supports the original problem,

Limitations, failure modes,

Potential improvements or future work.

Final video deliverable:

A link to your video (e.g., unlisted on YouTube, or cloud link).

Make sure the link is accessible to “anyone with the link” (or provide a passcode).
Otherwise 5 points will be automatically deducted from your project grade.

Judges scores for in-class demo will be 50% of the grade for this component.




## 7. Final Implementation & Report (15%) – due Week 6

This part evaluates the quality and completeness of your implementation and written report.

### 7.1 Final Report (8–10 pages)

Your report should include:

Introduction & problem statement



System design

Detailed description of: Agents and roles, tools/APIs, workflow / orchestration logic, any memory or state management.

Include your final architecture diagram.

Implementation details

Tech stack (libraries, frameworks),

Prompting strategies (e.g., system prompts, self-critique),

Handling of errors/retries.

Evaluation

Full description (more detail than video):

Metrics, test cases, data,

Evaluation protocol.

Results (tables/figures) and analysis.

Failure cases and discussion.

Security, reliability, and ethics

Is the system vulnerable to misuse, prompt injection, data leakage?

How robust is it to unexpected inputs?

What safeguards did you add (if any)?

Conclusion

Overall assessment: Does your agentic system provide real support/insights for the target problem?

What would you change with more time/resources?

### 7.2 Code & Artifacts

Please submit the project individually (one submission per student), including:

Code repository (zipped or link, plus a zipped backup), containing:

All implementation code for agents, orchestration, tools, and front-end.

README with:

Setup instructions,

How to run the system locally,

How to run the evaluation scripts.

Architecture diagram (high-resolution image, e.g., PNG/PDF).

Prompt / config files (if separate from code).

Evaluation scripts and data:

Notebooks or scripts (e.g., evaluation.ipynb),

Any structured test cases (e.g., JSON, CSV).

Slides used in the final presentation (PDF or PPTX).