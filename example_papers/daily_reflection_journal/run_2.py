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
        Initialize the app with empty journal and streak counter
        """
        self.journal_entries = []
        self.current_streak = 0
        self.longest_streak = 0
        self.badges = set()
    
    def start(self) -> str:
        """
        Start the app and return description
        """
        return ("Welcome to Daily Reflection Journal!\n"
               "Each day you'll get a prompt to reflect on your day.\n"
               "Maintain your streak by journaling daily to earn badges!\n\n"
               "Available commands:\n"
               "  journal <your entry> - Add a journal entry\n"
               "  view - View all journal entries\n"
               "  stats - View your streaks and badges\n"
               "  help - Show this help message")
    
    def run(self, prompt: str) -> str:
        """
        Handle journal commands and return responses
        """
        try:
            if not prompt.strip():
                return "Please enter a command. Type 'help' for instructions."
                
            if prompt.lower() == "help":
                return self.start()
                
            if prompt.lower().startswith("journal "):
                # Add journal entry
                entry = prompt[len("journal "):].strip()
                if not entry:
                    return "Please provide your journal entry after 'journal'"
                    
                self.journal_entries.append(entry)
                
                # Update streaks
                self.current_streak += 1
                if self.current_streak > self.longest_streak:
                    self.longest_streak = self.current_streak
                
                # Check for badge achievements
                if self.current_streak >= 3:
                    self.badges.add("3-day Streak")
                if self.current_streak >= 7:
                    self.badges.add("7-day Streak")
                
                return f"Journal entry saved! Current streak: {self.current_streak} days"
                
            elif prompt.lower() == "view":
                if not self.journal_entries:
                    return "No entries yet. Use 'journal <your entry>' to add one."
                return "Your Journal Entries:\n" + "\n".join(
                    f"Day {i+1}: {entry}" 
                    for i, entry in enumerate(self.journal_entries))
                
            elif prompt.lower() == "stats":
                return ("Your Progress:\n"
                       f"Current streak: {self.current_streak} days\n"
                       f"Longest streak: {self.longest_streak} days\n"
                       f"Badges earned: {', '.join(self.badges) or 'None'}")
                
            else:
                return ("Unknown command. Type 'help' for instructions.\n"
                       "Valid commands: journal, view, stats, help")
                
        except Exception as e:
            return f"Error: {str(e)}"


survey = Survey(
    questions=[
        MultipleChoiceQuestion(
            question="Did the app help you reflect on your day?",
            options=["Yes", "Somewhat", "No"],
        ),
        MultipleChoiceQuestion(
            question="How would you rate the ease of use of the app?",
            options=["Very Easy", "Easy", "Neutral", "Difficult", "Very Difficult"],
        ),
        MultipleChoiceQuestion(
            question="Did the streak system motivate you to journal consistently?",
            options=["Yes", "Somewhat", "No"],
        ),
        OpenEndedQuestion(
            question="What improvements would you suggest for the app?",
        ),
        OpenEndedQuestion(
            question="What did you find most helpful about the app?",
        ),
    ],
    target_demographics="25-35 year old professionals interested in personal development and mindfulness, tech-savvy, urban",
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
    
