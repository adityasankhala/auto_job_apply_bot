"""
Resume Advisor — classifies a job description into a role category so you know
which resume to use (or which one was auto-selected).

Categories:
  - SDE / Backend   — Django, Flask, REST, API, databases, microservices
  - ML / AI / Data  — TensorFlow, PyTorch, scikit-learn, NLP, CV, models
  - DevOps / Cloud  — Docker, K8s, CI/CD, AWS, GCP, Azure, Terraform
  - Full Stack      — frontend + backend signals together

Uses pure keyword frequency scoring — no API keys, no external calls.
Results are logged to resume_recommendations.csv.
"""

import csv
import os
import re
import time


# ---------------------------------------------------------------- categories

CATEGORIES = {
    "SDE / Backend": [
        "backend", "django", "flask", "fastapi", "rest api", "restful",
        "microservice", "sql", "postgresql", "mysql", "mongodb", "redis",
        "spring boot", "spring", "java", "golang", "go lang",
        "node.js", "express", "nestjs", "server side", "server-side",
        "api development", "api design", "database", "orm", "graphql",
        "software engineer", "software developer", "sde",
    ],
    "ML / AI / Data Science": [
        "machine learning", "deep learning", "data science", "data scientist",
        "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn",
        "nlp", "natural language", "computer vision", "cv model",
        "neural network", "transformer", "llm", "large language model",
        "model training", "model deployment", "mlops", "hugging face",
        "pandas", "numpy", "jupyter", "data analysis", "data analytics",
        "feature engineering", "reinforcement learning", "generative ai",
        "gpt", "bert", "fine-tuning", "fine tuning", "ai engineer",
        "research", "statistical", "regression", "classification",
    ],
    "DevOps / Cloud": [
        "devops", "docker", "kubernetes", "k8s", "ci/cd", "ci cd",
        "jenkins", "github actions", "gitlab ci", "terraform", "ansible",
        "aws", "amazon web services", "gcp", "google cloud", "azure",
        "cloud engineer", "site reliability", "sre", "infrastructure",
        "linux", "monitoring", "grafana", "prometheus", "elk",
        "helm", "argocd", "argo cd", "cloud native",
    ],
    "Full Stack": [
        "full stack", "fullstack", "full-stack", "mern", "mean",
        "react", "angular", "vue", "next.js", "nextjs", "nuxt",
        "frontend", "front-end", "front end", "html", "css",
        "javascript", "typescript", "tailwind", "bootstrap",
        "ui/ux", "responsive", "single page", "spa",
    ],
}

# Tie-breaking priority when two categories score the same
PRIORITY = ["ML / AI / Data Science", "DevOps / Cloud", "Full Stack", "SDE / Backend"]


# ---------------------------------------------------------------- scoring

def _count_hits(text: str, keywords: list[str]) -> int:
    """Count how many distinct keywords appear in the text."""
    text_lower = text.lower()
    # Also check a de-hyphenated version for compound terms
    text_dehyph = text_lower.replace("-", " ")
    hits = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in text_lower or kw_lower in text_dehyph:
            hits += 1
    return hits


def classify_job(jd: str) -> tuple[str, dict[str, int]]:
    """Classify a job description into a role category.

    Returns (category_name, scores_dict) where scores_dict maps each
    category to the number of keyword hits found.
    """
    scores = {}
    for category, keywords in CATEGORIES.items():
        scores[category] = _count_hits(jd, keywords)

    best_score = max(scores.values())
    if best_score == 0:
        return "General / Other", scores

    # Among categories tied at the top score, pick by priority order
    tied = [c for c, s in scores.items() if s == best_score]
    for priority_cat in PRIORITY:
        if priority_cat in tied:
            return priority_cat, scores

    return tied[0], scores


# ---------------------------------------------------------------- logging

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECOMMENDATIONS_PATH = os.path.join(_BASE_DIR, "resume_recommendations.csv")
HEADER = ["timestamp", "url", "title", "recommended_resume", "sde_score",
          "ml_score", "devops_score", "fullstack_score"]


def log_recommendation(url: str, title: str, category: str,
                       scores: dict[str, int]) -> None:
    """Append a recommendation to resume_recommendations.csv."""
    new_file = not os.path.exists(RECOMMENDATIONS_PATH)
    with open(RECOMMENDATIONS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(HEADER)
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            url,
            title[:120],
            category,
            scores.get("SDE / Backend", 0),
            scores.get("ML / AI / Data Science", 0),
            scores.get("DevOps / Cloud", 0),
            scores.get("Full Stack", 0),
        ])


def advise(url: str, title: str, jd: str) -> str:
    """Classify a job and log the recommendation. Returns the category name."""
    category, scores = classify_job(jd)
    log_recommendation(url, title, category, scores)
    return category
