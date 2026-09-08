"""Seed the question bank, resource library and demo sample papers.

Run:  python -m app.database.seed_content      (from backend/)
Also invoked automatically by `app.database.seed`.

What is real and what is not
----------------------------
* Questions are ordinary textbook-style exercises written for this project. They
  are demo content for development and marked source='CogniPath demo bank'.
  They are not drawn from any university's question paper.
* Resources link to genuinely free, publicly available material (MIT
  OpenCourseWare, Khan Academy, 3Blue1Brown, Paul's Online Notes). The mapping
  from concept to resource is a curriculum decision, not a model output.
* Sample papers are GENERATED PLACEHOLDER PDFs created at seed time by
  `_demo_pdf` below. They are stored with is_demo=1 and every surface that shows
  them says so. They are not official or previous-year university papers and
  carry no institutional status whatsoever.

Idempotent: seeding twice does not duplicate rows.
"""

from __future__ import annotations

import zlib

from app.database import practice_db
from app.database.db import get_conn

DEMO_SOURCE = "CogniPath demo bank"


# --------------------------------------------------------------------------- #
# minimal PDF writer
# --------------------------------------------------------------------------- #
def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _demo_pdf(title: str, lines: list[str]) -> bytes:
    """Build a small, valid single-page PDF without adding a dependency.

    Deliberately hand-rolled: pulling in reportlab for four placeholder files
    would add a build dependency to the Render deploy for no real benefit.
    """
    content_lines = ["BT", "/F1 16 Tf", "72 760 Td", f"({_escape(title)}) Tj", "/F1 10 Tf"]
    for line in lines:
        content_lines.append("0 -20 Td")
        content_lines.append(f"({_escape(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")
    compressed = zlib.compress(stream)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\nstream\n"
        + compressed + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n".encode()
    )
    out += b"%%EOF\n"
    return bytes(out)


# --------------------------------------------------------------------------- #
# questions
# --------------------------------------------------------------------------- #
def _mcq(subject, concept, difficulty, text, options, answer, explanation, marks=1.0):
    return {
        "subject": subject, "concept": concept, "difficulty": difficulty,
        "question_type": "MCQ", "question_text": text,
        "options": [{"key": k, "text": t} for k, t in options],
        "correct_answer": answer, "explanation": explanation,
        "marks": marks, "source": DEMO_SOURCE, "created_by": "seed",
    }


def _num(subject, concept, difficulty, text, answer, explanation, tolerance=0.01, marks=2.0):
    return {
        "subject": subject, "concept": concept, "difficulty": difficulty,
        "question_type": "Numerical", "question_text": text, "options": None,
        "correct_answer": str(answer), "explanation": explanation,
        "marks": marks, "tolerance": tolerance, "source": DEMO_SOURCE, "created_by": "seed",
    }


def _theory(subject, concept, difficulty, text, answer, marks=5.0):
    return {
        "subject": subject, "concept": concept, "difficulty": difficulty,
        "question_type": "Theory", "question_text": text, "options": None,
        "correct_answer": answer,
        "explanation": "Self-marked: compare your answer against the model answer above.",
        "marks": marks, "source": DEMO_SOURCE, "created_by": "seed",
    }


M, C, T, S, A = "Mathematics", "Calculus", "Transforms", "Systems", "Applications"

QUESTIONS: list[dict] = [
    # --- algebra ---
    _mcq(M, "algebra", "Easy", "Solve for x: 3x - 7 = 14.",
         [("A", "5"), ("B", "7"), ("C", "21"), ("D", "3")], "B",
         "Add 7 to both sides to get 3x = 21, then divide by 3."),
    _num(M, "algebra", "Medium",
         "If x^2 - 5x + 6 = 0, what is the larger root?", 3, 
         "Factorises as (x-2)(x-3)=0, so the roots are 2 and 3.", tolerance=0.001),

    # --- trigonometry ---
    _mcq(M, "trigonometry", "Easy", "What is sin(30 degrees)?",
         [("A", "1/2"), ("B", "sqrt(3)/2"), ("C", "1"), ("D", "0")], "A",
         "A standard angle value from the 30-60-90 triangle."),
    _mcq(M, "trigonometry", "Medium", "Simplify sin^2(x) + cos^2(x).",
         [("A", "0"), ("B", "1"), ("C", "2sin(x)cos(x)"), ("D", "tan(x)")], "B",
         "The Pythagorean identity, which follows from the unit circle."),

    # --- functions ---
    _mcq(M, "functions", "Easy", "What is the domain of f(x) = 1/(x - 2)?",
         [("A", "All real x"), ("B", "x > 2"), ("C", "All real x except 2"), ("D", "x < 2")], "C",
         "The denominator vanishes at x = 2, so that point is excluded."),
    _mcq(M, "functions", "Medium", "If f(x) = 2x + 1 and g(x) = x^2, what is f(g(3))?",
         [("A", "19"), ("B", "49"), ("C", "13"), ("D", "10")], "A",
         "g(3) = 9, then f(9) = 2(9) + 1 = 19. Composition applies inside first."),

    # --- limits ---
    _mcq(C, "limits", "Easy", "Evaluate the limit of (x^2 - 1)/(x - 1) as x approaches 1.",
         [("A", "0"), ("B", "1"), ("C", "2"), ("D", "undefined")], "C",
         "Factor the numerator to (x-1)(x+1); the (x-1) cancels leaving x+1, which tends to 2."),
    _num(C, "limits", "Medium",
         "Evaluate the limit of sin(x)/x as x approaches 0.", 1,
         "A standard limit, provable by the squeeze theorem.", tolerance=0.001),
    _mcq(C, "limits", "Hard", "A function is continuous at x = a when:",
         [("A", "f(a) is defined"), ("B", "the limit at a exists"),
          ("C", "f(a) is defined, the limit exists, and they are equal"),
          ("D", "f is differentiable at a")], "C",
         "All three conditions are required. Differentiability is sufficient but not necessary."),

    # --- differentiation ---
    _mcq(C, "differentiation", "Easy", "What is d/dx of x^3?",
         [("A", "3x"), ("B", "3x^2"), ("C", "x^2"), ("D", "3x^3")], "B",
         "The power rule: d/dx x^n = n*x^(n-1)."),
    _mcq(C, "differentiation", "Easy", "What is d/dx of sin(x)?",
         [("A", "cos(x)"), ("B", "-cos(x)"), ("C", "-sin(x)"), ("D", "sec^2(x)")], "A",
         "A standard derivative from the definition and the small-angle limit."),
    _mcq(C, "differentiation", "Medium", "Differentiate f(x) = (3x + 1)^4.",
         [("A", "4(3x+1)^3"), ("B", "12(3x+1)^3"), ("C", "3(3x+1)^3"), ("D", "12(3x+1)^4")], "B",
         "Chain rule: outer derivative 4(3x+1)^3 times inner derivative 3."),
    _num(C, "differentiation", "Medium",
         "If f(x) = x^2 + 3x, what is f'(2)?", 7,
         "f'(x) = 2x + 3, so f'(2) = 7.", tolerance=0.001),
    _mcq(C, "differentiation", "Hard", "Differentiate y = x*ln(x).",
         [("A", "ln(x)"), ("B", "1 + ln(x)"), ("C", "1/x"), ("D", "x/ln(x)")], "B",
         "Product rule: (1)(ln x) + (x)(1/x) = ln x + 1."),
    _theory(C, "differentiation", "Hard",
            "State the chain rule and explain why it is needed to differentiate "
            "composite functions such as sin(3x^2).",
            "The chain rule states that if y = f(g(x)) then dy/dx = f'(g(x)) * g'(x). "
            "It is needed because the rate of change of the outer function must be "
            "measured with respect to its own argument, then rescaled by how fast that "
            "argument itself changes. For sin(3x^2): cos(3x^2) * 6x."),

    # --- integration ---
    _mcq(C, "integration", "Easy", "What is the integral of 2x dx?",
         [("A", "x^2 + C"), ("B", "2x^2 + C"), ("C", "x + C"), ("D", "2 + C")], "A",
         "Reverse the power rule and add the constant of integration."),
    _num(C, "integration", "Medium",
         "Evaluate the definite integral of x from 0 to 4.", 8,
         "The antiderivative is x^2/2; evaluated from 0 to 4 gives 16/2 = 8.", tolerance=0.01),
    _mcq(C, "integration", "Medium", "Which technique best suits the integral of x*e^x dx?",
         [("A", "Substitution"), ("B", "Integration by parts"),
          ("C", "Partial fractions"), ("D", "Trigonometric substitution")], "B",
         "A polynomial multiplied by an exponential is the standard by-parts case."),
    _mcq(C, "integration", "Hard", "The integral of 1/x dx equals:",
         [("A", "x^-2 + C"), ("B", "ln|x| + C"), ("C", "1/(2x^2) + C"), ("D", "e^x + C")], "B",
         "The power rule fails at n = -1; the antiderivative is the natural log of |x|."),

    # --- differential equations ---
    _mcq(C, "differential_equations", "Easy", "What is the order of d2y/dx2 + 3dy/dx + 2y = 0?",
         [("A", "1"), ("B", "2"), ("C", "3"), ("D", "0")], "B",
         "Order is the highest derivative present, here the second."),
    _mcq(C, "differential_equations", "Medium",
         "The general solution of dy/dx = ky is:",
         [("A", "y = kx + C"), ("B", "y = Ce^(kx)"), ("C", "y = C/x"), ("D", "y = k/x + C")], "B",
         "Separate variables and integrate: ln|y| = kx + c, hence y = Ce^(kx)."),
    _mcq(C, "differential_equations", "Hard",
         "For y'' + 3y' + 2y = 0, the characteristic roots are:",
         [("A", "-1 and -2"), ("B", "1 and 2"), ("C", "-3 and 2"), ("D", "0 and -3")], "A",
         "r^2 + 3r + 2 = (r+1)(r+2) = 0, so the system is overdamped and stable."),
    _theory(C, "differential_equations", "Medium",
            "Explain the difference between the general solution and a particular "
            "solution of an ordinary differential equation.",
            "The general solution contains arbitrary constants and describes the whole "
            "family of functions satisfying the equation. A particular solution fixes "
            "those constants using initial or boundary conditions, selecting one member "
            "of that family."),

    # --- linear algebra ---
    _num(M, "linear_algebra", "Easy",
         "What is the determinant of [[2, 0], [0, 3]]?", 6,
         "For a diagonal matrix the determinant is the product of the diagonal entries.",
         tolerance=0.001),
    _mcq(M, "linear_algebra", "Medium", "A square matrix is invertible if and only if:",
         [("A", "it is symmetric"), ("B", "its determinant is non-zero"),
          ("C", "it is diagonal"), ("D", "all entries are non-zero")], "B",
         "A zero determinant means the columns are linearly dependent and the map is singular."),
    _mcq(M, "linear_algebra", "Hard",
         "Eigenvalues of A satisfy which equation?",
         [("A", "Ax = 0"), ("B", "det(A - lambda*I) = 0"),
          ("C", "A^T = A"), ("D", "trace(A) = 0")], "B",
         "The characteristic equation; non-trivial solutions require a singular A - lambda*I."),

    # --- laplace transforms ---
    _mcq(T, "laplace_transforms", "Easy", "The Laplace transform of the unit step u(t) is:",
         [("A", "1"), ("B", "1/s"), ("C", "s"), ("D", "1/s^2")], "B",
         "Integrating e^(-st) from 0 to infinity gives 1/s for s > 0."),
    _mcq(T, "laplace_transforms", "Medium", "L{e^(at)} equals:",
         [("A", "1/(s-a)"), ("B", "1/(s+a)"), ("C", "a/s"), ("D", "s/(s^2+a^2)")], "A",
         "Shifting in the s-domain; the region of convergence is s > a."),
    _mcq(T, "laplace_transforms", "Hard",
         "L{f'(t)} in terms of F(s) is:",
         [("A", "sF(s)"), ("B", "sF(s) - f(0)"), ("C", "F(s)/s"), ("D", "F(s) - f(0)")], "B",
         "Differentiation in time becomes multiplication by s minus the initial condition, "
         "which is exactly why Laplace methods handle initial-value problems cleanly."),

    # --- signals and systems ---
    _mcq(S, "signals_systems", "Easy", "An LTI system is fully characterised by its:",
         [("A", "step response only"), ("B", "impulse response"),
          ("C", "input signal"), ("D", "sampling rate")], "B",
         "Any input can be decomposed into impulses, so convolution with h(t) gives the output."),
    _mcq(S, "signals_systems", "Medium", "Convolution in the time domain corresponds to:",
         [("A", "addition in frequency"), ("B", "multiplication in frequency"),
          ("C", "convolution in frequency"), ("D", "differentiation in frequency")], "B",
         "The convolution theorem, and the reason frequency-domain analysis is preferred."),
    _theory(S, "signals_systems", "Hard",
            "Explain what it means for an LTI system to be BIBO stable and give the "
            "condition on its impulse response.",
            "Bounded-input bounded-output stability means every bounded input produces a "
            "bounded output. The necessary and sufficient condition is that the impulse "
            "response is absolutely integrable: the integral of |h(t)| over all t is finite."),

    # --- control systems ---
    _mcq(S, "control_systems", "Easy",
         "A continuous-time LTI system is stable when all poles lie:",
         [("A", "in the right half plane"), ("B", "in the left half plane"),
          ("C", "on the imaginary axis"), ("D", "at the origin")], "B",
         "Left-half-plane poles give decaying exponential modes."),
    _mcq(S, "control_systems", "Medium",
         "Adding integral action to a controller primarily:",
         [("A", "increases bandwidth"), ("B", "eliminates steady-state error"),
          ("C", "reduces overshoot"), ("D", "adds a zero")], "B",
         "Integral action drives accumulated error to zero, at the cost of phase margin."),
    _num(S, "control_systems", "Hard",
         "For G(s) = 10/(s^2 + 2s + 10), what is the undamped natural frequency in rad/s?",
         3.162,
         "Comparing with the standard form, wn^2 = 10, so wn = sqrt(10) = 3.162.",
         tolerance=0.05),

    # --- robotics ---
    _mcq(A, "robotics", "Easy", "Forward kinematics computes:",
         [("A", "joint angles from end-effector pose"),
          ("B", "end-effector pose from joint angles"),
          ("C", "joint torques from forces"), ("D", "the trajectory time")], "B",
         "Inverse kinematics is the other direction and is generally harder and non-unique."),
    _mcq(A, "robotics", "Medium",
         "A robot configuration where the Jacobian loses rank is called:",
         [("A", "a workspace limit"), ("B", "a singularity"),
          ("C", "a home position"), ("D", "a joint limit")], "B",
         "At a singularity the manipulator loses a degree of freedom and joint "
         "velocities can blow up."),

    # --- probability ---
    _num(M, "probability", "Easy",
         "A fair six-sided die is rolled. What is the probability of rolling a 4 or higher? "
         "Answer as a decimal.", 0.5,
         "Three of six outcomes (4, 5, 6) qualify.", tolerance=0.01),
    _mcq(M, "probability", "Medium",
         "For independent events A and B, P(A and B) equals:",
         [("A", "P(A) + P(B)"), ("B", "P(A) * P(B)"),
          ("C", "P(A) - P(B)"), ("D", "P(A|B)")], "B",
         "Independence is defined by exactly this factorisation."),

    # --- numerical methods ---
    _mcq("Computation", "numerical_methods", "Easy",
         "The bisection method requires that the function:",
         [("A", "is differentiable"), ("B", "changes sign over the interval"),
          ("C", "is monotonic"), ("D", "is linear")], "B",
         "The intermediate value theorem guarantees a root when f(a) and f(b) have "
         "opposite signs."),
    _mcq("Computation", "numerical_methods", "Medium",
         "Newton-Raphson converges quadratically but can fail when:",
         [("A", "the initial guess is exact"), ("B", "the derivative is near zero"),
          ("C", "the function is a polynomial"), ("D", "the root is negative")], "B",
         "The update divides by f'(x), so a near-zero derivative produces a huge step."),
    _theory("Computation", "numerical_methods", "Hard",
            "Compare the convergence rate and robustness of the bisection method "
            "against Newton-Raphson.",
            "Bisection converges linearly, halving the bracket each iteration, but is "
            "guaranteed to converge given a sign change. Newton-Raphson converges "
            "quadratically near a simple root but needs a derivative and a good initial "
            "guess, and may diverge or cycle otherwise. Hybrid methods such as Brent's "
            "combine the guarantee of bracketing with superlinear speed."),
]


# --------------------------------------------------------------------------- #
# resources
# --------------------------------------------------------------------------- #
RESOURCES: list[dict] = [
    {"title": "Algebra Basics", "subject": M, "concept": "algebra", "resource_type": "Video",
     "difficulty": "Easy", "estimated_minutes": 45,
     "url": "https://www.khanacademy.org/math/algebra-basics",
     "description": "Equations, inequalities and symbolic manipulation from the ground up."},
    {"title": "Trigonometric Functions Review", "subject": M, "concept": "trigonometry",
     "resource_type": "Notes", "difficulty": "Easy", "estimated_minutes": 25,
     "url": "https://tutorial.math.lamar.edu/Classes/CalcI/TrigFcns.aspx",
     "description": "Compact identity and unit-circle reference."},
    {"title": "Functions, Domain and Composition", "subject": M, "concept": "functions",
     "resource_type": "Article", "difficulty": "Easy", "estimated_minutes": 25,
     "url": "https://tutorial.math.lamar.edu/Classes/Alg/FunctionNotation.aspx",
     "description": "Notation, domain and range, inverses and composition."},
    {"title": "Limits, Visually", "subject": C, "concept": "limits", "resource_type": "Video",
     "difficulty": "Easy", "estimated_minutes": 20,
     "url": "https://www.3blue1brown.com/lessons/limits",
     "description": "Geometric intuition for limiting behaviour and continuity."},
    {"title": "MIT 18.01 Limits Problem Set", "subject": C, "concept": "limits",
     "resource_type": "Exercise", "difficulty": "Medium", "estimated_minutes": 60,
     "url": "https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/",
     "description": "Worked problem sets with solutions from MIT OpenCourseWare."},
    {"title": "Differentiation Fundamentals", "subject": C, "concept": "differentiation",
     "resource_type": "Notes", "difficulty": "Easy", "estimated_minutes": 20,
     "url": "https://tutorial.math.lamar.edu/Classes/CalcI/DerivativeIntro.aspx",
     "description": "Definition of the derivative, the power rule, and a formula sheet."},
    {"title": "Chain Rule Practice", "subject": C, "concept": "differentiation",
     "resource_type": "Exercise", "difficulty": "Medium", "estimated_minutes": 25,
     "url": "https://www.khanacademy.org/math/differential-calculus",
     "description": "Graded exercises building from single to nested composition."},
    {"title": "Essence of Calculus: Derivatives", "subject": C, "concept": "differentiation",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 30,
     "url": "https://www.3blue1brown.com/topics/calculus",
     "description": "Why the derivative is a rate of change, built up visually."},
    {"title": "Integration Techniques", "subject": C, "concept": "integration",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 45,
     "url": "https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/",
     "description": "Substitution, by parts and partial fractions."},
    {"title": "Integral Calculus Exercises", "subject": C, "concept": "integration",
     "resource_type": "Exercise", "difficulty": "Medium", "estimated_minutes": 50,
     "url": "https://www.khanacademy.org/math/integral-calculus",
     "description": "Definite and indefinite integral drills."},
    {"title": "Differential Equations, Visually", "subject": C,
     "concept": "differential_equations", "resource_type": "Video", "difficulty": "Medium",
     "estimated_minutes": 30, "url": "https://www.3blue1brown.com/topics/differential-equations",
     "description": "Phase space and what an ODE actually describes."},
    {"title": "MIT 18.03 Problem Sets", "subject": C, "concept": "differential_equations",
     "resource_type": "Exercise", "difficulty": "Hard", "estimated_minutes": 60,
     "url": "https://ocw.mit.edu/courses/18-03sc-differential-equations-fall-2011/",
     "description": "First and second order ODEs with full solutions."},
    {"title": "Essence of Linear Algebra", "subject": M, "concept": "linear_algebra",
     "resource_type": "Video", "difficulty": "Easy", "estimated_minutes": 40,
     "url": "https://www.3blue1brown.com/topics/linear-algebra",
     "description": "Vectors, matrices and eigenvectors as geometric transformations."},
    {"title": "MIT 18.06 Problem Sets", "subject": M, "concept": "linear_algebra",
     "resource_type": "Exercise", "difficulty": "Hard", "estimated_minutes": 60,
     "url": "https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/",
     "description": "Gilbert Strang's problem sets on spaces, rank and eigenvalues."},
    {"title": "Laplace Transform Table", "subject": T, "concept": "laplace_transforms",
     "resource_type": "Notes", "difficulty": "Easy", "estimated_minutes": 15,
     "url": "https://tutorial.math.lamar.edu/Classes/DE/Laplace_Table.aspx",
     "description": "Standard pairs and properties for quick reference."},
    {"title": "Laplace Methods for ODEs", "subject": T, "concept": "laplace_transforms",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 40,
     "url": "https://ocw.mit.edu/courses/18-03sc-differential-equations-fall-2011/",
     "description": "Solving initial-value problems in the s-domain."},
    {"title": "Signals and Systems Lectures", "subject": S, "concept": "signals_systems",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 50,
     "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/",
     "description": "LTI properties, convolution and frequency response."},
    {"title": "Convolution Practice Problems", "subject": S, "concept": "signals_systems",
     "resource_type": "Exercise", "difficulty": "Hard", "estimated_minutes": 45,
     "url": "https://ocw.mit.edu/courses/res-6-007-signals-and-systems-spring-2011/",
     "description": "Graphical and analytical convolution exercises."},
    {"title": "Control Systems Lectures", "subject": S, "concept": "control_systems",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 40,
     "url": "https://engineeringmedia.com/",
     "description": "Brian Douglas on feedback, stability and controller design."},
    {"title": "Root Locus and Stability Exercises", "subject": S, "concept": "control_systems",
     "resource_type": "Exercise", "difficulty": "Hard", "estimated_minutes": 50,
     "url": "https://ocw.mit.edu/courses/16-06-principles-of-automatic-control-fall-2012/",
     "description": "Pole placement and stability margin problems."},
    {"title": "Modern Robotics: Kinematics", "subject": A, "concept": "robotics",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 45,
     "url": "https://modernrobotics.northwestern.edu/nu-gm-book-resource/",
     "description": "Forward and inverse kinematics of serial manipulators."},
    {"title": "Introduction to Probability", "subject": M, "concept": "probability",
     "resource_type": "Video", "difficulty": "Medium", "estimated_minutes": 45,
     "url": "https://ocw.mit.edu/courses/res-6-012-introduction-to-probability-spring-2018/",
     "description": "Random variables, distributions and expectation."},
    {"title": "Numerical Root Finding Notes", "subject": "Computation",
     "concept": "numerical_methods", "resource_type": "Article", "difficulty": "Medium",
     "estimated_minutes": 30,
     "url": "https://ocw.mit.edu/courses/18-330-introduction-to-numerical-analysis-spring-2012/",
     "description": "Bisection, Newton-Raphson, secant methods and error analysis."},
]


# --------------------------------------------------------------------------- #
# demo sample papers
# --------------------------------------------------------------------------- #
DISCLAIMER = (
    "DEMO PLACEHOLDER - generated by CogniPath AI for development and "
    "demonstration only. This is NOT an official or previous-year university "
    "question paper and carries no institutional status."
)

PAPERS = [
    {"title": "Mathematics Model Paper (Demo)", "subject": "Mathematics", "year": 2026,
     "semester": "Fall", "difficulty": "Medium",
     "description": "Placeholder model paper covering algebra, functions and calculus.",
     "topics": ["Section A - Algebra and Functions", "Section B - Limits and Continuity",
                "Section C - Differentiation and Integration"]},
    {"title": "Calculus Practice Paper (Demo)", "subject": "Calculus", "year": 2025,
     "semester": "Spring", "difficulty": "Hard",
     "description": "Placeholder practice paper on differentiation and differential equations.",
     "topics": ["Section A - Derivatives and the Chain Rule",
                "Section B - Integration Techniques",
                "Section C - Ordinary Differential Equations"]},
    {"title": "Control Systems Model Paper (Demo)", "subject": "Systems", "year": 2026,
     "semester": "Fall", "difficulty": "Medium",
     "description": "Placeholder model paper on transfer functions and stability.",
     "topics": ["Section A - Transfer Functions", "Section B - Stability and Root Locus",
                "Section C - Controller Design"]},
    {"title": "Signals & Systems Practice Paper (Demo)", "subject": "Systems", "year": 2025,
     "semester": "Spring", "difficulty": "Hard",
     "description": "Placeholder practice paper on LTI systems and convolution.",
     "topics": ["Section A - LTI Properties", "Section B - Convolution",
                "Section C - Frequency Response"]},
]


def _existing_question_texts() -> set[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT question_text FROM questions").fetchall()
    return {r["question_text"] for r in rows}


def _existing_resource_titles() -> set[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT title FROM resources").fetchall()
    return {r["title"] for r in rows}


def seed_content() -> dict:
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
                "filename": p["title"].lower().replace(" ", "-").replace("(", "").replace(")", "") + ".pdf",
                "is_demo": 1, "uploaded_by": "seed",
            },
            pdf,
        )
        papers_added += 1

    return {
        "questions_added": questions_added,
        "resources_added": resources_added,
        "sample_papers_added": papers_added,
        "questions_in_bank": len(practice_db.list_questions(limit=500)),
        "note": "Sample papers are generated demo placeholders, not official papers.",
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(seed_content(), indent=2))
