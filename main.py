import json
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from dotenv import load_dotenv
load_dotenv()

print("\nimport success\n")

OPENAI_MODEL = "gpt-4o"
# SERVICE_ACCOUNT_FILE = "service_account.json"
DOC_TITLE = "YouTube Knowledge Pipeline"
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive"
]

client = OpenAI()

def extract_video_id(url: str) -> str:
    parsed = urlparse(url)

    if parsed.hostname == "youtu.be":
        return parsed.path[1:]

    return parse_qs(parsed.query)["v"][0]

def get_transcript(youtube_url: str) -> str:
    video_id = extract_video_id(youtube_url)

    yt = YouTubeTranscriptApi()

    transcript = yt.fetch(video_id)
    # transcript = YouTubeTranscriptApi.get_transcript(video_id)

    cleaned_text = " ".join(
        segment.text
        for segment in transcript
    )

    return cleaned_text

def generate_summary(transcript: str) -> str:

    system_prompt = """
You are a Senior Educator.

Read the transcript and produce:

1. Executive Summary
2. Key Takeaways
3. Important Concepts
4. Practical Applications

Use professional bullet points.
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=system_prompt,
        input=transcript
    )

    return response.output_text


QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string"
                    },
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "minItems": 4,
                        "maxItems": 4
                    },
                    "correct_answer": {
                        "type": "string"
                    },
                    "rationale": {
                        "type": "string"
                    }
                },
                "required": [
                    "question",
                    "options",
                    "correct_answer",
                    "rationale"
                ],
                "additionalProperties": False
            }
        }
    },
    "required": ["questions"],
    "additionalProperties": False
}


def generate_quiz(transcript: str):

    prompt = f"""
You are a Senior Educator.

Generate EXACTLY 5 multiple-choice questions.

Requirements:

- Test application and understanding.
- Avoid simple recall.
- Four answer choices.
- One correct answer.
- Include rationale.

Transcript:

{transcript}
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "quiz",
                "schema": QUIZ_SCHEMA
            }
        }
    )

    return json.loads(response.output_text)

def create_google_doc():

    flow = InstalledAppFlow.from_client_secrets_file(
        "client_secret.json",   
        SCOPES
    )

    creds = flow.run_local_server(port=0)

    docs_service = build("docs", "v1", credentials=creds)

    try:

        document = docs_service.documents().create(
            body={"title": DOC_TITLE}
        ).execute()

        doc_id = document["documentId"]

        # print("Created Doc ID:", doc_id)
        # print("Open:", f"https://docs.google.com/document/d/{doc_id}/edit")

        return docs_service, doc_id

    except HttpError as e:
        print("HTTP Error:", e)
        print(e.content.decode())
        raise

def document_content(summary: str, quiz: dict):

    text = ""

    text += "YOUTUBE KNOWLEDGE PIPELINE\n\n"
    text += "SUMMARY\n\n"
    text += summary
    text += "\n\n"

    text += "QUIZ\n\n"

    for idx, q in enumerate(
        quiz["questions"],
        start=1
    ):
        text += f"{idx}. {q['question']}\n"

        text += f"A. {q['options'][0]}\n"
        text += f"B. {q['options'][1]}\n"
        text += f"C. {q['options'][2]}\n"
        text += f"D. {q['options'][3]}\n\n"

        text += (
            f"Correct Answer: "
            f"{q['correct_answer']}\n"
        )

        text += (
            f"Rationale: "
            f"{q['rationale']}\n\n"
        )

    return text

def save_to_google_doc(summary, quiz):

    docs_service, doc_id = create_google_doc()

    content = document_content(summary,quiz)

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "insertText": {
                        "location": {
                            "index": 1
                        },
                        "text": content
                    }
                }
            ]
        }
    ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"
 
def run_pipeline(youtube_url):

    transcript = get_transcript(youtube_url)
    print("got transcript")
    summary = generate_summary(transcript)
    print("generated summary")
    quiz = generate_quiz(transcript)
    print("Generated Quiz")
    doc_url = save_to_google_doc(summary,quiz)
    print("Saved to google doc")

    print("\nCompleted\n")
    print(doc_url)

if __name__ == "__main__":

    youtube_url = input("Enter YouTube URL: ")

    run_pipeline(youtube_url)

    # docs_service, doc_id = create_google_doc()

    # print(f"https://docs.google.com/document/d/{doc_id}/edit")

