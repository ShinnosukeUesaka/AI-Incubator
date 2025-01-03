import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from survey import MultipleChoiceQuestion, OpenEndedQuestion, Survey, run_survey


class TextApp():
    def __init__(self):
        """
        Initialize the app, does not return anything.
        """
        raise NotImplementedError()
    
    def start(self) -> str:
        """
        Start the app, and return a string description of the app. Called only once at the start.
        """
        raise NotImplementedError()
    
    def run(self, prompt: str) -> str:
        """
        receives a prompt separated by spaces, and returns the output of the app. Called multiples times.
        """
        raise NotImplementedError()
        try:
            commands = prompt.split()
        except Exception as e:
            return str(e)


survey = Survey(
    # Sample questions and target demographics
    questions=[
        MultipleChoiceQuestion(
            question="What is your favorite color?",
            options=["Red", "Blue", "Green"],
        ),
        OpenEndedQuestion(
            question="Was there any difficulty in using the app?",
        ),
    ],
    target_demographics="25-35 year old, male, college educated, tech-savvy, urban, middle-class",
)


    
parser = argparse.ArgumentParser(description="Run experiment")
parser.add_argument("--out_dir", type=str, default="run_0", help="Output directory")
args = parser.parse_args()


if __name__ == "__main__":
    # Do not change the code below
    N_SAVE_LOGS = 1
    N_SAVE_OPEN_ENDED_ANSWERS = 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # run_survey will find users that match the target demographics, and run the survey on them after testing the app.
    # Now app testing and surveys are simulated using LLM agents.
    answers, logs_list = run_survey(TextApp, survey, n_samples=4)  # type: tuple[pd.DataFrame, list[str]]
    answers.to_csv(out_dir / "answers.csv", index=False)

    for i, log in enumerate(logs_list):
        with open(out_dir / f"log_{i+1}.txt", "w") as f:
            f.write(log)
    
    # Select 2 random logs to save
    logs_indices = np.random.choice(len(logs_list), size=N_SAVE_LOGS, replace=False)    
    open_ended_indices = np.random.choice(len(answers), size=N_SAVE_OPEN_ENDED_ANSWERS, replace=False)
    
    results_content = ""
    # Aggregate multiple choice answers
    results_content = "# Survey Results:\n\n"
    results_content += "Multiple Choice Questions:\n"
    for q in survey.questions:
        if isinstance(q, MultipleChoiceQuestion):
            results_content += f"\nQ: {q.question}\n"
            # Count responses for each option
            counts = answers[q.question].value_counts()
            for option in q.options:
                count = counts.get(option, 0)
                results_content += f"{option}: {count}\n"
    
    # Sample open ended answers
    results_content += "\nOpen Ended Responses (Sample):\n"
    for q in survey.questions:
        if isinstance(q, OpenEndedQuestion):
            results_content += f"\nQ: {q.question}\n"
            sampled_answers = answers.iloc[open_ended_indices][q.question]
            for i, answer in enumerate(sampled_answers, 1):
                results_content += f"Response {i}: {answer}\n"
    
    # Add sampled interaction logs
    results_content += "\n# Interaction Logs (Sample):\n"
    for i, log_idx in enumerate(logs_indices, 1):
        results_content += f"\nLog {i}:\n"
        results_content += f"{logs_list[log_idx]}\n"
        results_content += "-" * 40 + "\n"
    
    
    with open(out_dir / "results.txt", "w") as f:
        f.write(results_content)


    out_dir = args.out_dir
    