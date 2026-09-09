"""Demo content for the non-Mathematics subjects.

Run:  python -m app.database.seed_multisubject      (from backend/)

This complements `seed_content.py`, which seeds the Mathematics/Calculus bank.
Same conventions: the same `_mcq` / `_num` / `_theory` helpers, the same
`DEMO_SOURCE` label, `is_demo = 1` on papers, and the same idempotent
insert-if-absent behaviour, so it is safe to re-run on every deployment.

Every `concept` below is a knowledge-graph concept id, which is what keeps the
bank wired to root-cause analysis: a DSP root cause resolves to DSP questions
without any subject-specific code path.

The sample papers are generated placeholders. They say so on the page and carry
the same disclaimer as the existing demo papers: they are not official or
previous-year university papers.
"""

from __future__ import annotations

from app.database import practice_db
from app.database.seed_content import (
    DISCLAIMER,
    _demo_pdf,
    _existing_question_texts,
    _existing_resource_titles,
    _mcq,
    _num,
    _theory,
)

DSP, VLSI, CN, DB, AIML = (
    "Digital Signal Processing", "VLSI Design", "Computer Networks",
    "Database Management Systems", "Artificial Intelligence / Machine Learning",
)

QUESTIONS: list[dict] = [
    # ---------------- Digital Signal Processing -------------------------- #
    _mcq(DSP, "sampling", "Easy", "Sampling converts a signal from:",
         [("A", "Discrete time to continuous time"), ("B", "Continuous time to discrete time"),
          ("C", "Time domain to frequency domain"), ("D", "Analog power to digital power")], "B",
         "Sampling takes instantaneous values of a continuous-time signal at regular intervals."),
    _num(DSP, "sampling", "Medium",
         "A signal is sampled at 8 kHz. What is the sampling interval in microseconds?", 125,
         "T = 1/fs = 1/8000 s = 125 microseconds.", tolerance=0.5),
    _mcq(DSP, "nyquist_theorem", "Easy",
         "A signal band-limited to 4 kHz must be sampled at a rate of at least:",
         [("A", "2 kHz"), ("B", "4 kHz"), ("C", "8 kHz"), ("D", "16 kHz")], "C",
         "The Nyquist rate is twice the highest frequency component: 2 x 4 kHz = 8 kHz."),
    _num(DSP, "nyquist_theorem", "Medium",
         "A signal contains components up to 15 kHz. State the Nyquist rate in kHz.", 30,
         "The Nyquist rate is 2 x 15 = 30 kHz."),
    _mcq(DSP, "aliasing", "Medium",
         "A 9 kHz tone sampled at 8 kHz appears at which frequency?",
         [("A", "9 kHz"), ("B", "1 kHz"), ("C", "8 kHz"), ("D", "17 kHz")], "B",
         "The tone folds back: |9 - 8| = 1 kHz. This is aliasing caused by under-sampling."),
    _theory(DSP, "aliasing", "Hard",
            "Explain why an anti-aliasing filter is placed before the sampler rather than after it.",
            "Once a signal is sampled below its Nyquist rate, high-frequency components fold "
            "into the baseband and become indistinguishable from genuine low-frequency content. "
            "No filter applied after sampling can separate them, because the information that "
            "would distinguish them has already been destroyed. The anti-aliasing filter must "
            "therefore band-limit the signal before sampling."),
    _mcq(DSP, "fourier_transform", "Medium",
         "Convolution in the time domain corresponds to which operation in the frequency domain?",
         [("A", "Convolution"), ("B", "Addition"), ("C", "Multiplication"), ("D", "Division")], "C",
         "The convolution theorem: convolution in one domain is multiplication in the other."),
    _mcq(DSP, "fourier_transform", "Easy", "The Fourier transform of a signal shows its:",
         [("A", "Time-domain amplitude"), ("B", "Frequency content"),
          ("C", "Sampling rate"), ("D", "Phase noise only")], "B",
         "The transform decomposes a signal into the frequencies it contains."),
    _num(DSP, "dft_fft", "Medium",
         "How many complex multiplications does a radix-2 FFT of length N = 8 require, "
         "using the (N/2)log2(N) estimate?", 12,
         "(8/2) x log2(8) = 4 x 3 = 12."),
    _mcq(DSP, "dft_fft", "Hard",
         "The FFT reduces DFT complexity from O(N^2) to:",
         [("A", "O(N)"), ("B", "O(N log N)"), ("C", "O(log N)"), ("D", "O(N^3)")], "B",
         "Divide and conquer on the DFT's symmetry gives O(N log N)."),
    _mcq(DSP, "digital_filtering", "Medium",
         "Which is always true of an FIR filter?",
         [("A", "It has feedback"), ("B", "It is always unstable"),
          ("C", "It has a finite impulse response and is inherently stable"),
          ("D", "It cannot have linear phase")], "C",
         "FIR filters have no feedback path, so their impulse response ends and they are stable."),
    _theory(DSP, "digital_filtering", "Hard",
            "Compare FIR and IIR filters in terms of stability, phase and computational cost.",
            "FIR filters have no poles, so they are inherently stable and can be designed with "
            "exactly linear phase, at the cost of a higher order for a given selectivity. IIR "
            "filters achieve sharp responses with far fewer coefficients but use feedback, so "
            "stability depends on pole locations and phase is generally non-linear. The choice "
            "is between guaranteed stability and linear phase (FIR) or computational efficiency (IIR)."),

    # ---------------- VLSI ------------------------------------------------ #
    _mcq(VLSI, "semiconductor_physics", "Easy",
         "Doping silicon with a pentavalent element produces:",
         [("A", "p-type material"), ("B", "n-type material"),
          ("C", "An insulator"), ("D", "A superconductor")], "B",
         "Pentavalent donors contribute free electrons, making the material n-type."),
    _mcq(VLSI, "mosfet", "Easy", "An NMOS transistor is in saturation when:",
         [("A", "Vgs < Vt"), ("B", "Vds < Vgs - Vt"), ("C", "Vds >= Vgs - Vt and Vgs > Vt"),
          ("D", "Vds = 0")], "C",
         "Above threshold with Vds at or beyond the overdrive, the channel pinches off."),
    _num(VLSI, "threshold_voltage", "Medium",
         "An NMOS has Vt = 0.7 V and Vgs = 2.0 V. What is the overdrive voltage in volts?", 1.3,
         "Overdrive = Vgs - Vt = 2.0 - 0.7 = 1.3 V.", tolerance=0.01),
    _mcq(VLSI, "threshold_voltage", "Hard",
         "Increasing the source-to-body voltage of an NMOS causes the threshold voltage to:",
         [("A", "Decrease"), ("B", "Increase"), ("C", "Stay constant"), ("D", "Become negative")], "B",
         "The body effect widens the depletion region, so more gate voltage is needed."),
    _mcq(VLSI, "mobility", "Medium", "Carrier mobility in silicon generally decreases when:",
         [("A", "Temperature falls"), ("B", "Doping concentration increases"),
          ("C", "The sample is made longer"), ("D", "The supply voltage drops")], "B",
         "Heavier doping increases ionised-impurity scattering, reducing mobility."),
    _mcq(VLSI, "velocity_saturation", "Hard",
         "In a short-channel MOSFET at high fields, drain current becomes approximately:",
         [("A", "Quadratic in overdrive voltage"), ("B", "Linear in overdrive voltage"),
          ("C", "Independent of gate voltage"), ("D", "Exponential in overdrive voltage")], "B",
         "Once carriers saturate in velocity, current scales roughly linearly with overdrive "
         "rather than quadratically."),
    _mcq(VLSI, "channel_length_modulation", "Medium",
         "Channel length modulation primarily affects which device characteristic?",
         [("A", "Threshold voltage"), ("B", "Output resistance in saturation"),
          ("C", "Gate capacitance"), ("D", "Subthreshold slope")], "B",
         "The current rises slightly with Vds in saturation, giving finite output resistance."),
    _num(VLSI, "cmos_logic", "Medium",
         "How many transistors are needed for a static CMOS 2-input NAND gate?", 4,
         "Two NMOS in series in the pull-down network and two PMOS in parallel in the pull-up."),
    _theory(VLSI, "cmos_logic", "Hard",
            "Explain why static CMOS logic consumes almost no power when idle, and what "
            "dominates its dynamic power.",
            "In a static CMOS gate exactly one of the pull-up or pull-down networks conducts for "
            "any stable input, so there is no DC path from supply to ground and static power is "
            "limited to leakage. Dynamic power is dominated by charging and discharging load "
            "capacitance, approximately alpha*C*V^2*f, plus a smaller short-circuit component "
            "during input transitions when both networks conduct briefly."),

    # ---------------- Computer Networks ------------------------------------ #
    _mcq(CN, "network_models", "Easy", "Which OSI layer is responsible for routing?",
         [("A", "Data link"), ("B", "Network"), ("C", "Transport"), ("D", "Session")], "B",
         "The network layer handles logical addressing and path selection."),
    _mcq(CN, "circuit_switching", "Medium",
         "Compared with packet switching, circuit switching:",
         [("A", "Shares links statistically"), ("B", "Reserves capacity for the call duration"),
          ("C", "Has no setup delay"), ("D", "Is more efficient for bursty traffic")], "B",
         "A circuit dedicates capacity end to end, which is wasteful for bursty traffic."),
    _num(CN, "packet_switching", "Medium",
         "A 1000-bit packet is sent over a 1 Mbps link. What is the transmission delay in "
         "milliseconds?", 1,
         "Transmission delay = 1000 bits / 1,000,000 bps = 1 ms.", tolerance=0.01),
    _mcq(CN, "network_delay", "Hard",
         "Which delay component grows as a router's output buffer fills?",
         [("A", "Propagation delay"), ("B", "Transmission delay"),
          ("C", "Queueing delay"), ("D", "Processing delay")], "C",
         "Queueing delay depends on traffic intensity; the others do not."),
    _num(CN, "network_delay", "Medium",
         "A link is 3000 km long with a propagation speed of 2 x 10^8 m/s. What is the "
         "propagation delay in milliseconds?", 15,
         "3,000,000 m / 2e8 m/s = 0.015 s = 15 ms.", tolerance=0.1),
    _mcq(CN, "tcp", "Medium", "TCP's congestion window is halved on:",
         [("A", "Every acknowledgement"), ("B", "A triple duplicate ACK (fast retransmit)"),
          ("C", "Connection setup"), ("D", "Every RTT")], "B",
         "Fast recovery halves cwnd on triple duplicate ACKs; a timeout resets it to one MSS."),
    _theory(CN, "tcp", "Hard",
            "Explain the difference between flow control and congestion control in TCP.",
            "Flow control protects the receiver: the advertised window stops a fast sender from "
            "overrunning the receiver's buffer. Congestion control protects the network: the "
            "congestion window responds to loss and delay signals so senders do not collectively "
            "overload routers. The sender transmits at the minimum of the two windows."),
    _mcq(CN, "routing", "Medium", "Dijkstra's algorithm is the basis of which routing family?",
         [("A", "Distance vector"), ("B", "Link state"), ("C", "Flooding"), ("D", "Source routing")], "B",
         "Link-state protocols such as OSPF compute shortest paths with Dijkstra."),

    # ---------------- DBMS -------------------------------------------------- #
    _mcq(DB, "relational_model", "Easy", "A candidate key is:",
         [("A", "Any attribute"), ("B", "A minimal set of attributes that uniquely identifies a tuple"),
          ("C", "Always a single column"), ("D", "A foreign key")], "B",
         "Minimality is what distinguishes a candidate key from a superkey."),
    _mcq(DB, "functional_dependencies", "Medium",
         "Given A -> B and B -> C, which dependency follows by transitivity?",
         [("A", "C -> A"), ("B", "A -> C"), ("C", "B -> A"), ("D", "AC -> B")], "B",
         "Armstrong's transitivity axiom gives A -> C."),
    _mcq(DB, "first_normal_form", "Easy", "A relation violates 1NF when:",
         [("A", "It has a composite key"), ("B", "An attribute holds multiple values in one cell"),
          ("C", "It has a transitive dependency"), ("D", "It has a foreign key")], "B",
         "1NF requires atomic attribute values."),
    _mcq(DB, "second_normal_form", "Medium", "2NF eliminates:",
         [("A", "Transitive dependencies"), ("B", "Partial dependencies on part of a composite key"),
          ("C", "Multi-valued dependencies"), ("D", "Foreign keys")], "B",
         "2NF requires full functional dependency on the whole primary key."),
    _mcq(DB, "third_normal_form", "Medium", "3NF removes dependencies that are:",
         [("A", "Partial"), ("B", "Transitive on non-key attributes"),
          ("C", "Trivial"), ("D", "Multi-valued")], "B",
         "In 3NF no non-prime attribute is transitively dependent on a candidate key."),
    _theory(DB, "bcnf", "Hard",
            "State the BCNF condition and explain when a relation can be in 3NF but not in BCNF.",
            "A relation is in BCNF when, for every non-trivial dependency X -> Y, X is a "
            "superkey. 3NF relaxes this by also allowing the case where Y is a prime attribute. "
            "So a relation with overlapping candidate keys can satisfy 3NF while still having a "
            "determinant that is not a superkey, which puts it outside BCNF."),
    _mcq(DB, "sql_queries", "Medium",
         "Which clause filters rows AFTER aggregation in SQL?",
         [("A", "WHERE"), ("B", "HAVING"), ("C", "GROUP BY"), ("D", "ORDER BY")], "B",
         "WHERE filters rows before grouping; HAVING filters the aggregated groups."),
    _mcq(DB, "transactions", "Medium", "The 'D' in ACID guarantees that:",
         [("A", "Transactions do not interfere"), ("B", "Committed changes survive a crash"),
          ("C", "Constraints always hold"), ("D", "A transaction is all or nothing")], "B",
         "Durability: once committed, the effects persist through failure."),

    # ---------------- AI / ML ------------------------------------------------ #
    _mcq(AIML, "regression", "Easy", "Which metric is appropriate for a regression model?",
         [("A", "Accuracy"), ("B", "Precision"), ("C", "Mean absolute error"), ("D", "ROC-AUC")], "C",
         "Accuracy, precision and ROC-AUC are classification metrics; MAE measures continuous error."),
    _num(AIML, "regression", "Medium",
         "A model predicts 8, 6 and 7 where the true values are 7, 7 and 7. What is the mean "
         "absolute error?", 0.667,
         "(|8-7| + |6-7| + |7-7|) / 3 = 2/3 = 0.667.", tolerance=0.01),
    _mcq(AIML, "classification", "Medium",
         "A classifier has precision 1.0 and recall 0.5. What does that mean?",
         [("A", "It finds every positive but with false alarms"),
          ("B", "Everything it flags is correct, but it misses half the positives"),
          ("C", "It is perfectly calibrated"), ("D", "It always predicts the majority class")], "B",
         "High precision means few false positives; low recall means many false negatives."),
    _mcq(AIML, "feature_engineering", "Medium",
         "Why must a scaler be fitted on the training split only?",
         [("A", "It runs faster"), ("B", "Otherwise test statistics leak into training, inflating scores"),
          ("C", "Scalers cannot handle test data"), ("D", "It changes the model type")], "B",
         "Fitting on all data leaks information about the test set - the classic preprocessing leak."),
    _mcq(AIML, "model_evaluation", "Medium", "The purpose of k-fold cross-validation is to:",
         [("A", "Increase the training set permanently"),
          ("B", "Estimate generalisation more reliably than a single split"),
          ("C", "Remove the need for a test set"), ("D", "Guarantee no overfitting")], "B",
         "Averaging over folds reduces the variance of the performance estimate."),
    _mcq(AIML, "overfitting", "Easy",
         "A model with near-perfect training accuracy and poor test accuracy is:",
         [("A", "Underfitting"), ("B", "Overfitting"), ("C", "Well regularised"), ("D", "Unbiased")], "B",
         "It has memorised the training data instead of learning a generalisable pattern."),
    _mcq(AIML, "explainable_ai", "Medium", "A SHAP value for a feature represents:",
         [("A", "Its correlation with the target"),
          ("B", "Its contribution to moving this prediction away from the base value"),
          ("C", "Its p-value"), ("D", "Its variance in the dataset")], "B",
         "SHAP attributes the gap between the base value and this prediction across features."),
    _theory(AIML, "explainable_ai", "Hard",
            "Explain the difference between global feature importance and a SHAP explanation "
            "for a single prediction.",
            "Global importance summarises how much a feature matters to the model across the "
            "whole dataset - a single number per feature. A SHAP explanation is local: it "
            "decomposes one specific prediction into signed per-feature contributions that sum "
            "to the difference between that prediction and the model's base value. A feature can "
            "be globally important yet contribute nothing to a particular case, and vice versa."),
]

RESOURCES: list[dict] = [
    {"title": "Sampling and the Nyquist Rate", "subject": DSP, "concept": "nyquist_theorem",
     "resource_type": "Notes", "difficulty": "Easy", "estimated_minutes": 25,
     "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/",
     "description": "Sampling theorem statement, Nyquist rate and reconstruction.", "is_demo": 1},
    {"title": "Aliasing in Practice", "subject": DSP, "concept": "aliasing",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 25,
     "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/",
     "description": "How under-sampling folds high frequencies into the baseband.", "is_demo": 1},
    {"title": "FFT Walkthrough", "subject": DSP, "concept": "dft_fft",
     "resource_type": "Article", "difficulty": "Hard", "estimated_minutes": 40,
     "url": "https://ocw.mit.edu/courses/6-341-discrete-time-signal-processing-fall-2005/",
     "description": "Radix-2 decimation in time, step by step.", "is_demo": 1},
    {"title": "FIR and IIR Filter Design", "subject": DSP, "concept": "digital_filtering",
     "resource_type": "Exercise", "difficulty": "Hard", "estimated_minutes": 50,
     "url": "https://ocw.mit.edu/courses/6-341-discrete-time-signal-processing-fall-2005/",
     "description": "Design exercises comparing FIR and IIR responses.", "is_demo": 1},
    {"title": "MOSFET Operating Regions", "subject": VLSI, "concept": "mosfet",
     "resource_type": "Video", "difficulty": "Easy", "estimated_minutes": 40,
     "url": "https://nptel.ac.in/courses/117101058",
     "description": "Cutoff, linear and saturation regions with I-V curves.", "is_demo": 1},
    {"title": "Threshold Voltage and Body Effect", "subject": VLSI, "concept": "threshold_voltage",
     "resource_type": "Notes", "difficulty": "Medium", "estimated_minutes": 30,
     "url": "https://nptel.ac.in/courses/117101058",
     "description": "Where Vt comes from and how the body effect shifts it.", "is_demo": 1},
    {"title": "Short Channel Effects", "subject": VLSI, "concept": "velocity_saturation",
     "resource_type": "Article", "difficulty": "Hard", "estimated_minutes": 35,
     "url": "https://nptel.ac.in/courses/117101058",
     "description": "Velocity saturation and channel length modulation.", "is_demo": 1},
    {"title": "Static CMOS Gate Design", "subject": VLSI, "concept": "cmos_logic",
     "resource_type": "Exercise", "difficulty": "Medium", "estimated_minutes": 45,
     "url": "https://nptel.ac.in/courses/117101058",
     "description": "Building pull-up and pull-down networks from a Boolean expression.", "is_demo": 1},
    {"title": "Four Sources of Packet Delay", "subject": CN, "concept": "network_delay",
     "resource_type": "Notes", "difficulty": "Medium", "estimated_minutes": 25,
     "url": "https://gaia.cs.umass.edu/kurose_ross/",
     "description": "Processing, queueing, transmission and propagation delay.", "is_demo": 1},
    {"title": "TCP Congestion Control", "subject": CN, "concept": "tcp",
     "resource_type": "Video", "difficulty": "Hard", "estimated_minutes": 45,
     "url": "https://gaia.cs.umass.edu/kurose_ross/videos.php",
     "description": "Slow start, congestion avoidance, fast retransmit and recovery.", "is_demo": 1},
    {"title": "Routing Algorithms Compared", "subject": CN, "concept": "routing",
     "resource_type": "Article", "difficulty": "Medium", "estimated_minutes": 35,
     "url": "https://gaia.cs.umass.edu/kurose_ross/",
     "description": "Link-state versus distance-vector, with worked examples.", "is_demo": 1},
    {"title": "Normalization Step by Step", "subject": DB, "concept": "third_normal_form",
     "resource_type": "Notes", "difficulty": "Medium", "estimated_minutes": 40,
     "url": "https://www.db-book.com/",
     "description": "1NF through 3NF on a single worked schema.", "is_demo": 1},
    {"title": "Functional Dependency Exercises", "subject": DB, "concept": "functional_dependencies",
     "resource_type": "Exercise", "difficulty": "Medium", "estimated_minutes": 40,
     "url": "https://www.db-book.com/slides-dir/index.html",
     "description": "Closures, candidate keys and minimal covers.", "is_demo": 1},
    {"title": "BCNF Decomposition", "subject": DB, "concept": "bcnf",
     "resource_type": "Article", "difficulty": "Hard", "estimated_minutes": 35,
     "url": "https://www.db-book.com/",
     "description": "When 3NF is not enough, and how to decompose losslessly.", "is_demo": 1},
    {"title": "SQL Joins and Aggregation", "subject": DB, "concept": "sql_queries",
     "resource_type": "Exercise", "difficulty": "Easy", "estimated_minutes": 45,
     "url": "https://www.db-book.com/slides-dir/index.html",
     "description": "Practice queries covering joins, GROUP BY and HAVING.", "is_demo": 1},
    {"title": "Regression Fundamentals", "subject": AIML, "concept": "regression",
     "resource_type": "Video", "difficulty": "Easy", "estimated_minutes": 40,
     "url": "https://www.statlearning.com/",
     "description": "Fitting, interpreting and evaluating a linear model.", "is_demo": 1},
    {"title": "Classification Metrics in Depth", "subject": AIML, "concept": "classification",
     "resource_type": "Article", "difficulty": "Medium", "estimated_minutes": 35,
     "url": "https://scikit-learn.org/stable/modules/model_evaluation.html",
     "description": "Precision, recall, F1 and ROC-AUC, and when each misleads.", "is_demo": 1},
    {"title": "Avoiding Data Leakage", "subject": AIML, "concept": "feature_engineering",
     "resource_type": "Notes", "difficulty": "Medium", "estimated_minutes": 30,
     "url": "https://scikit-learn.org/stable/modules/compose.html",
     "description": "Why preprocessing belongs inside the pipeline.", "is_demo": 1},
    {"title": "Cross-Validation Practice", "subject": AIML, "concept": "model_evaluation",
     "resource_type": "Exercise", "difficulty": "Medium", "estimated_minutes": 45,
     "url": "https://scikit-learn.org/stable/modules/cross_validation.html",
     "description": "Comparing models with k-fold cross-validation.", "is_demo": 1},
    {"title": "Explaining Models with SHAP", "subject": AIML, "concept": "explainable_ai",
     "resource_type": "Article", "difficulty": "Hard", "estimated_minutes": 40,
     "url": "https://shap.readthedocs.io/en/latest/",
     "description": "Shapley values, additivity and reading a force plot.", "is_demo": 1},
]

PAPERS = [
    {"title": "Digital Signal Processing Practice Paper 2026", "subject": DSP, "year": 2026,
     "semester": "Semester 5", "difficulty": "Medium",
     "description": "Sampling, transforms and filter design.",
     "topics": ["Unit 1: Sampling and reconstruction", "Unit 2: DFT and FFT",
                "Unit 3: FIR and IIR filter design"]},
    {"title": "VLSI Design Practice Paper 2026", "subject": VLSI, "year": 2026,
     "semester": "Semester 5", "difficulty": "Hard",
     "description": "Device physics through CMOS gate design.",
     "topics": ["Unit 1: MOSFET operation", "Unit 2: Short channel effects",
                "Unit 3: Static CMOS logic"]},
    {"title": "Computer Networks Practice Paper 2025", "subject": CN, "year": 2025,
     "semester": "Semester 4", "difficulty": "Medium",
     "description": "Switching, delay analysis, transport and routing.",
     "topics": ["Unit 1: Layered models and switching", "Unit 2: Delay and throughput",
                "Unit 3: TCP and routing"]},
    {"title": "Database Management Systems Practice Paper 2026", "subject": DB, "year": 2026,
     "semester": "Semester 4", "difficulty": "Medium",
     "description": "Relational design, normalization, SQL and transactions.",
     "topics": ["Unit 1: Relational model and keys", "Unit 2: Normalization to BCNF",
                "Unit 3: SQL and transactions"]},
    {"title": "AI and Machine Learning Practice Paper 2026", "subject": AIML, "year": 2026,
     "semester": "Semester 6", "difficulty": "Medium",
     "description": "Supervised learning, evaluation and explainability.",
     "topics": ["Unit 1: Regression and classification", "Unit 2: Evaluation and overfitting",
                "Unit 3: Explainable AI"]},
]


def seed_multisubject() -> dict:
    """Idempotent: inserts only rows that are not already present."""
    from app.database import db

    db.init_db()

    seen_questions = _existing_question_texts()
    questions_added = 0
    for q in QUESTIONS:
        if q["question_text"] in seen_questions:
            continue
        practice_db.create_question(q)
        questions_added += 1

    seen_resources = _existing_resource_titles()
    resources_added = 0
    for r in RESOURCES:
        if r["title"] in seen_resources:
            continue
        practice_db.create_resource({**r, "created_by": "seed"})
        resources_added += 1

    seen_papers = practice_db.paper_titles()
    papers_added = 0
    for p in PAPERS:
        if p["title"] in seen_papers:
            continue
        pdf = _demo_pdf(
            p["title"],
            [DISCLAIMER, "", f"Subject: {p['subject']}", f"Year: {p['year']}",
             f"Difficulty: {p['difficulty']}", "", *p["topics"], "",
             "Question content is intentionally not included in this placeholder."],
        )
        practice_db.create_paper(
            {
                "title": p["title"], "subject": p["subject"], "year": p["year"],
                "semester": p["semester"], "difficulty": p["difficulty"],
                "description": f"{p['description']} {DISCLAIMER}",
                "filename": p["title"].lower().replace(" ", "-") + ".pdf",
                "is_demo": 1, "uploaded_by": "seed",
            },
            pdf,
        )
        papers_added += 1

    counts = practice_db.question_counts_by_concept()
    return {
        "questions_added": questions_added,
        "resources_added": resources_added,
        "papers_added": papers_added,
        "concepts_with_questions": len(counts),
        "total_questions": sum(sum(v.values()) for v in counts.values()),
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(seed_multisubject(), indent=2))
