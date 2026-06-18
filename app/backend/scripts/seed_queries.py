import requests


API_URL = "http://localhost:8000/ask"

QUESTIONS = [
    "What are AWS responsibilities under the agreement?",
    "What are customer responsibilities?",
    "What does the agreement say about customer content?",
    "Who is responsible for account security?",
    "What happens if AWS changes a service level agreement?",
    "Can AWS access customer content?",
    "What are the customer's backup responsibilities?",
    "What does the agreement say about log-in credentials?",
    "What is the effective date?",
    "What does Section 2.2 cover?",
    "What does Section 1.4 say about data privacy?",
    "How much notice does AWS give before discontinuing material functionality?",
    "Does the privacy notice apply to customer content?",
    "What are end user responsibilities?",
    "What are AWS security obligations?",
    "Can customers use third-party content?",
    "What payment method should I use for AWS?",
    "Does the agreement mention pizza delivery?",
    "What is the weather in Tokyo?",
    "Who won the World Cup?",
    "Does the agreement explain Kubernetes pod scheduling?",
    "What is the capital of France?",
    "Can I create multiple accounts per email?",
    "What does AWS say about unauthorized access?",
    "What is the role of service terms?",
    "What regions can customer content be stored in?",
    "Can AWS move customer content across regions?",
    "What legal authority does an entity representative need?",
    "Does the agreement mention encryption?",
    "What should the model say when the answer is absent?",
]


def main():
    for question in QUESTIONS:
        response = requests.post(API_URL, json={"query": question}, timeout=120)
        print(response.status_code, question)


if __name__ == "__main__":
    main()
