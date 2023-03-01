import os
import pandas as pd
from tqdm import tqdm
import tiktoken
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

tokenizer = tiktoken.get_encoding("cl100k_base")

# check if 'podiodata' index already exists (only create index if not)
if 'podiodata' not in pinecone.list_indexes():
    res = openai.Embedding.create(
        input=[
                "Sample document text goes here",
                "there will be several phrases in each batch"
            ], engine=MODEL
    )

    # extract embeddings to a list
    embeds = [record['embedding'] for record in res['data']]
    pinecone.create_index('podiodata', dimension=len(embeds[0]))

pine_index = pinecone.Index("podiodata")


def descrption(field, customer_name, value):
    # print(type(value))
    match field:
        case "Unique ID":
            return "The Unique ID for "+ customer_name+" is "+value
        case "Created on":
            return "This project was created at "+value
        # case "Created by":
        #     if(value=="Projects"):
        #         return ""
        #     else:
        #         return ""
        case "Customer Full Name":
            return "The full name of customer is "+value
        case "Date Created":
            return "The project is created at" + value
        case "Estimated Install Date set at sale - start":
            return ""
        case default:
            return "The "+field+" for "+customer_name+" is "+value

max_tokens = 500

# Function to split the text into chunks of a maximum number of tokens
def split_into_many(text, max_tokens = max_tokens):

    # Split the text into sentences
    sentences = text.split('. ')

    # Get the number of tokens for each sentence
    n_tokens = [len(tokenizer.encode(" " + sentence)) for sentence in sentences]
    
    chunks = []
    tokens_so_far = 0
    chunk = []

    # Loop through the sentences and tokens joined together in a tuple
    for sentence, token in zip(sentences, n_tokens):

        # If the number of tokens so far plus the number of tokens in the current sentence is greater 
        # than the max number of tokens, then add the chunk to the list of chunks and reset
        # the chunk and tokens so far
        if tokens_so_far + token > max_tokens:
            chunks.append(". ".join(chunk) + ".")
            chunk = []
            tokens_so_far = 0

        # If the number of tokens in the current sentence is greater than the max number of 
        # tokens, go to the next sentence
        if token > max_tokens:
            continue

        # Otherwise, add the sentence to the chunk and add the number of tokens to the total
        chunk.append(sentence)
        tokens_so_far += token + 1

    return chunks

headers=[]
df=pd.read_csv('processed/initial.csv', low_memory=False)
headers = next(df.iterrows())[0]


df=pd.read_csv('processed/initial.csv', low_memory=False, header=1)

pbar = tqdm(df.iterrows(),  desc="Progress bar: ")
for row in pbar:
    text=''
    shortened=[]
    for index, header_cell in enumerate(headers):
        if(header_cell != 'Customer Full Name'):
            value = str(row[1][header_cell])
            customer_fullname= str(row[1]['Customer Full Name'])
            text += descrption(header_cell, customer_fullname, value) +"."

    # If the text is None, go to the next row
    if text is None:
        continue

    # If the number of tokens is greater than the max number of tokens, split the text into chunks
    if len(tokenizer.encode(text)) > max_tokens:
        shortened += split_into_many(text)
    
    # Otherwise, add the text to the list of shortened texts
    else:
        shortened.append( text )
    upsert_data = []
    for index, data in enumerate(shortened):
        upsert_data.append((
            str(row[1]["Unique ID"])+ "-" + str(index),
            openai.Embedding.create(input=data, engine=MODEL)['data'][0]['embedding'],
            {"text" : data}
        ))
    pine_index.upsert(vectors=upsert_data)
