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
        Initialize the app with empty task list and focus session settings
        """
        self.tasks = []
        self.focus_time = 25  # Default Pomodoro timer duration
        self.break_time = 5
        self.session_history = []  # Track completed focus sessions
        self.points = 0
        self.in_focus_mode = False
        self.reward_info = {
            'points_per_session': 10,
            'level_up_threshold': 100,
            'current_level': 1
        }
    
    def start(self) -> str:
        """
        Start the app and return description
        """
        return ("Welcome to FocusFlow! A productivity app that helps you stay focused.\n"
               "Features:\n"
               "- Pomodoro timer for focus sessions\n"
               "- Task management with priorities (1=highest, 5=lowest)\n"
               "- Focus mode to block distractions\n"
               "- Reward system: Earn 10 points per session, level up every 100 points\n"
               "Type 'help' for commands.")
    
    def run(self, prompt: str) -> str:
        """
        Process user commands and return app response
        """
        try:
            commands = prompt.lower().split()
            if not commands:
                return "Please enter a command. Type 'help' for options."
            
            if commands[0] == "help":
                return ("Available commands:\n"
                       "add <task> - Add a new task\n"
                       "add priority <n> <task> - Add task with priority (1-5)\n"
                       "list - Show all tasks\n"
                       "complete <n> - Mark task n as completed\n"
                       "start [minutes] - Begin focus session (default: 25, or specify duration)\n"
                       "stop - End focus session\n"
                       "points - Show earned points\n"
                       "focus - Toggle focus mode\n"
                       "\nTip: Use 'start 50' for a 50-minute focus session")
            
            elif commands[0] == "add" and len(commands) > 1:
                task = " ".join(commands[1:])
                priority = 3  # Default priority
                if len(commands) > 2 and commands[1] == "priority":
                    try:
                        priority = int(commands[2])
                        if priority < 1 or priority > 5:
                            return "Priority must be between 1 (highest) and 5 (lowest)"
                        task = " ".join(commands[3:])
                    except ValueError:
                        return "Priority must be a number between 1 and 5"
                elif len(commands) > 1 and commands[1] == "priority":
                    return "Please specify a priority number after 'priority'"
                self.tasks.append({
                    'description': task,
                    'priority': priority,
                    'completed': False
                })
                return f"Added task: {task} (Priority: {priority})"
            
            elif commands[0] == "list":
                if not self.tasks:
                    return "No tasks added yet."
                sorted_tasks = sorted(self.tasks, key=lambda x: x['priority'])
                task_list = []
                for i, task in enumerate(sorted_tasks):
                    status = "[x]" if task['completed'] else "[ ]"
                    task_list.append(f"{i+1}. {status} {task['description']} (Priority: {task['priority']})")
                return "Your tasks (1=highest priority, 5=lowest):\n" + \
                       "\n".join(task_list)
            
            elif commands[0] == "complete" and len(commands) > 1:
                try:
                    task_num = int(commands[1]) - 1
                    if task_num < 0 or task_num >= len(self.tasks):
                        return "Invalid task number"
                    self.tasks[task_num]['completed'] = True
                    return f"Marked task {commands[1]} as completed"
                except ValueError:
                    return "Please specify a valid task number"
            
            elif commands[0] == "start":
                if not self.tasks:
                    return "Please add tasks before starting a focus session."
                
                # Check for custom duration
                if len(commands) > 1 and commands[1].isdigit():
                    duration = int(commands[1])
                    if duration < 5 or duration > 120:
                        return "Focus session must be between 5 and 120 minutes"
                    self.focus_time = duration
                    self.break_time = max(1, duration // 5)  # Auto-calculate break time
                
                self.in_focus_mode = True
                return (f"Starting focus session for {self.focus_time} minutes...\n"
                      f"Focus mode activated. Distractions blocked.\n"
                      f"Break time: {self.break_time} minutes")
            
            elif commands[0] == "stop":
                if not self.in_focus_mode:
                    return "No active focus session."
                self.in_focus_mode = False
                self.points += 10
                points_needed = self.reward_info['level_up_threshold'] - self.points
                
                # Track session history
                self.session_history.append({
                    'duration': self.focus_time,
                    'timestamp': pd.Timestamp.now(),
                    'points_earned': 10
                })
                
                # Calculate productivity insights
                total_focus_time = sum(s['duration'] for s in self.session_history)
                avg_session_length = total_focus_time / len(self.session_history)
                
                return (f"Focus session completed! You earned 10 points.\n"
                      f"Total points: {self.points} (Level {self.reward_info['current_level']})\n"
                      f"Earn {points_needed} more points to reach Level {self.reward_info['current_level'] + 1}!\n"
                      f"Take a {self.break_time} minute break.\n"
                      f"\nProductivity Insights:\n"
                      f"- Total focus time: {total_focus_time} minutes\n"
                      f"- Average session length: {avg_session_length:.1f} minutes\n"
                      f"- Total sessions completed: {len(self.session_history)}")
            
            elif commands[0] == "points":
                points_needed = self.reward_info['level_up_threshold'] - self.points
                return (f"You have {self.points} points (Level {self.reward_info['current_level']}).\n"
                       f"Earn {points_needed} more points to reach Level {self.reward_info['current_level'] + 1}!")
            
            elif commands[0] == "focus":
                self.in_focus_mode = not self.in_focus_mode
                status = "activated" if self.in_focus_mode else "deactivated"
                return f"Focus mode {status}."
            
            else:
                return "Unknown command. Type 'help' for options."
                
        except Exception as e:
            return f"Error: {str(e)}"


survey = Survey(
    questions=[
        MultipleChoiceQuestion(
            question="Did the app help you maintain focus?",
            options=["Yes, significantly", "Somewhat", "Not really", "No"],
        ),
        MultipleChoiceQuestion(
            question="How would you rate your productivity while using the app?",
            options=["Much higher", "Somewhat higher", "About the same", "Lower"],
        ),
        MultipleChoiceQuestion(
            question="Did the reward system motivate you to complete focus sessions?",
            options=["Yes, very motivating", "Somewhat motivating", "Not motivating"],
        ),
        OpenEndedQuestion(
            question="What improvements would you suggest for the app?",
        ),
        OpenEndedQuestion(
            question="What did you find most helpful about the app?",
        ),
    ],
    target_demographics="25-35 year old professionals, tech-savvy, knowledge workers, urban areas",
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
    
