import os
from dataclasses import dataclass

import openai
import pandas as pd


@dataclass
class MultipleChoiceQuestion:
    question: str
    options: list[str]

@dataclass
class OpenEndedQuestion:
    question: str

@dataclass
class Survey:
    questions: list[MultipleChoiceQuestion | OpenEndedQuestion]
    target_demographics: str


TESTING_PROMPT = """First test the MVP.
You will recieve the output from the app in the following format:
APP OUTPUT:
<APP OUTPUT>

Respond in the following format: 

THOUGHT:
<THOUGHT>

COMMAND:
<COMMAND>

In <THOUGHT> describe the current though process as the persona using the app including:
- What the persona is trying to do
- What the persona is confused about
- What the persona likes about the app
- The app might be used multiple times with intervals between each use. In this case, describe the persona's actions in the interval. Eg. Persona closes the app, buys milk, and opens the app again.

When you have comprehensively tested the app or the app becomes unusable, submit the command "END". "END" will stop the survey, do not use when user closes the app temporarily.

In <COMMAND> provide the next command to the app. The app starts now.
APP OUTPUT:
"""

SURVEY_PROMPT = """You are done testing the app. You cannot run anymore commands. Now take the survey.
Respond in the following format:

RESPONSE:
<RESPONSE>

For multiple choice questions, respond with the exact option you choose. It will be parsed, so make sure the option is exactly as it is in the options list. The answers must be written as how a persona would answer the question.
"""

class SurveyTaker:
    def __init__(self, demographics: str, model_name: str):
        self.model_name = model_name
        if model_name == "deepseek-chat":
            self.client = openai.OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
        else:
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Generate persona
        self.personal = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": f"Generate a detailed person description for a user that matches some of the the following demographics: {demographics}."}],
        ).choices[0].message.content


    def take_survey(self, app, survey: Survey, max_iterations: int = 10) -> tuple[list[str], str]:
        """
        Takes a survey by first testing the MVP and then answering survey questions.

        Args:
            app: A class that implements the app interface (start() and run(command) methods)
            survey: Survey object containing questions to ask
            max_iterations: Maximum number of test iterations before forcing survey

        Returns:
            tuple[list[str], str]: List of survey answers and testing interaction logs
        """
        # === Test the MVP ===
        app = app()
        first_app_output = app.start()
        messages = [{"role": "system", "content": f"You are testing an MVP of an app. You will be required to take a survey of the app. You have the following persona: \n {self.personal}."}, {"role": "user", "content": TESTING_PROMPT + first_app_output}]
        
        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
            ).choices[0].message.content
            print(response)
            messages.append({"role": "assistant", "content": response})
            command = response.split("COMMAND:")[-1].strip()
            if command == "END":
                break
            app_output = app.run(command)
            print(f"APP OUTPUT:\n{app_output}")
            messages.append({"role": "user", "content": f"APP OUTPUT:\n{app_output}"})
        logs = "\n\n".join(m['content'] for m in messages[2:])


        # === Take the survey ===
        answers = []
        messages.append({"role": "user", "content": SURVEY_PROMPT})
        for question in survey.questions:
            if isinstance(question, MultipleChoiceQuestion):
                messages.append({"role": "user", "content": f"QUESTION: {question.question}\nOPTIONS: {question.options}"})
            elif isinstance(question, OpenEndedQuestion):
                messages.append({"role": "user", "content": f"QUESTION: {question.question}"})
            else:
                raise ValueError(f"Unknown question type: {type(question)}")
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
            ).choices[0].message.content
            messages.append({"role": "assistant", "content": response})
            answer = response.split("RESPONSE:")[-1].strip().strip('"').strip("'")
            answers.append(answer)

        return answers, logs
    


def run_survey(app, survey: Survey, n_samples: int = 2) -> tuple[pd.DataFrame, list[str]]:
    """
    Conducts a survey on the app. For now, we simulate the survey by using LLM as a survey taker.
    """
    answers_list = []
    logs_list = []
    for _ in range(n_samples):
        survey_taker = SurveyTaker(survey.target_demographics, model_name="deepseek-chat")
        answers, logs = survey_taker.take_survey(app, survey)
        answers_list.append({q.question: a for q, a in zip(survey.questions, answers)} )
        logs_list.append(logs)

    
    answers = pd.DataFrame(answers_list)
    answers['respondent_id'] = [f'respondent_{i+1}' for i in range(len(answers_list))]
    return answers, logs_list

if __name__ == "__main__":
    # Define a simple ToDo app
    class ToDoApp():
        def __init__(self):
            self.todos = []
            
        def start(self) -> str:
            return "Welcome to ToDo App! Commands: add <task>, list, done <number>, help"
            
        def run(self, prompt: str) -> str:
            try:
                commands = prompt.split()
                if not commands:
                    return "Please enter a command. Type 'help' for available commands."
                
                command = commands[0].lower()
                
                if command == "help":
                    return "Commands:\n- add <task>: Add a new task\n- list: Show all tasks\n- done <number>: Mark task as complete"
                elif command == "add" and len(commands) > 1:
                    task = " ".join(commands[1:])
                    self.todos.append(task)
                    return f"Added task: {task}"
                elif command == "list":
                    if not self.todos:
                        return "No tasks yet"
                    return "\n".join(f"{i+1}. {task}" for i, task in enumerate(self.todos))
                elif command == "done" and len(commands) > 1:
                    try:
                        idx = int(commands[1]) - 1
                        if 0 <= idx < len(self.todos):
                            completed = self.todos.pop(idx)
                            return f"Completed task: {completed}"
                        return "Invalid task number"
                    except ValueError:
                        return "Please provide a valid task number"
                else:
                    return "Invalid command. Type 'help' for available commands."
            except Exception as e:
                return str(e)

    # Define a simple survey
    todo_survey = Survey(
        questions=[
            MultipleChoiceQuestion(
                question="How easy was it to use the ToDo app?",
                options=["Very Easy", "Easy", "Neutral", "Difficult", "Very Difficult"]
            ),
            MultipleChoiceQuestion(
                question="Would you use this app regularly?",
                options=["Definitely", "Probably", "Maybe", "Probably Not", "Definitely Not"]
            ),
            OpenEndedQuestion(
                question="What features would you like to see added to the ToDo app?"
            ),
            OpenEndedQuestion(
                question="Did you encounter any issues while using the app?"
            )
        ],
        target_demographics="25-35 year old professionals who use digital productivity tools"
    )

    # Run the survey
    results = run_survey(ToDoApp, todo_survey, n_samples=3)
    
    # Save results to CSV
    results.to_csv("todo_survey_results.csv", index=False)
    print("Survey results saved to todo_survey_results.csv")