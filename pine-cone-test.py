import os
from tqdm.auto import tqdm 
# moduld related with openai
import openai
# pinecone module
import pinecone
# read env file
from dotenv import load_dotenv
#get api key of openai from .env
load_dotenv()

pine_cone_api_key = os.getenv("PINE_CONE_API_KEY")
pine_cone_environment = os.getenv("PINE_CONE_ENVIRONMENT")
print("pine_cone_api_key: ",pine_cone_api_key)
print("pine_cone_environment: ",pine_cone_environment)


openai_api_key = os.getenv("OPENAI_API_KEY")
print("openai_api_key_____",openai_api_key)
openai.api_key=openai_api_key

MODEL = 'text-embedding-ada-002'

pinecone.init(api_key=pine_cone_api_key, environment=pine_cone_environment)

pine_index = pinecone.Index("podiodata")

def create_context(question):
    """
    Create a context for a question by finding the most similar context from the dataframe
    """

    # Get the embeddings for the question
    xq  = openai.Embedding.create(input=question, engine=MODEL)['data'][0]['embedding']

    res = pine_index.query([xq], top_k=2, include_metadata=True)

    returns = []

    for match in res['matches']:
        returns.append(match['metadata']["text"])

    # Return the context
    return "\n\n###\n\n".join(returns)


def answer_question(
    model="text-davinci-003",
    question="Am I allowed to publish model outputs to Twitter, without a human review?",
    debug=False,
    max_tokens=1000,
    stop_sequence=None
):
    """
    Answer a question based on the most similar context from the dataframe texts
    """
    context = create_context(
        question,
    )
    # If debug, print the raw model response
    if debug:
        print("Context:\n" + context)
        print("\n\n")

    try:
        # Create a completions using the questin and context
        response = openai.Completion.create(
            prompt=f"Answer the question based on the context below.\"\n\nContext: {context}\n\n---\n\nQuestion: {question}\nAnswer:",
            temperature=0,
            max_tokens=max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=stop_sequence,
            model=model,
        )
        return response["choices"][0]["text"].strip()
    except Exception as e:
        print(e)
        return ""

################################################################################
################################################################################
questions = [
    'What is the Stage for Ma. Sagrario Castellanos?',
]

for question in questions:
    print('question: ',question)
    print('answer: ', answer_question(question=question, debug=True))