import os
from tqdm import tqdm
import time
# moduld related with openai
import openai
# pinecone module
import pinecone
#podio module
from  pypodio2 import api as podio_api

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
    try:
        pinecone.create_index('podiodata', dimension=len(embeds[0]))
        print('created index')
    except:
        print('error')
        
pine_index = pinecone.Index("podiodata")

#############################
client_id=os.getenv("PODIO_CLIENT_ID")
client_secret=os.getenv("PODIO_CLIENT_SECRET")
app_id=os.getenv("PODIO_APP_ID")
app_token=os.getenv("PODIO_APP_TOKEN")

podio = podio_api.OAuthAppClient(client_id,client_secret,app_id,app_token)

print('start training')

def get_items(app_id, limit, offset):
    return podio.Item.filter(int(app_id),attributes={
        "limit": limit,
        "offset": offset,
        "sort_by": "created_on",
    })['items']

def set_item(id, new_value):
    text=''
    if ('Stage' in new_value) & ('Customer Full Name' in new_value):
        text= f"Now the stage for {new_value['Customer Full Name']} is {new_value['Stage']}"
    elif ('Stage' in new_value == False) & ('Customer Full Name' in new_value):
        text= f"Now the stage for {new_value['Customer Full Name']} is none"
    else:
        return False
    embedding=[]
    try:
        embedding = openai.Embedding.create(input=text, engine=MODEL)['data'][0]['embedding']
    except :
        embedding = openai.Embedding.create(input=text, engine=MODEL)['data'][0]['embedding']
    return {
        "id": id,
        "values": embedding,
        "metadata": new_value
    }


def all_values(fields):
    values={}
    for field in fields:
        match(field['type']):
            case 'app':
                values[field['label']]=None
            case 'category':
                values[field['label']]=field['values'][0]['value']['text']
            case 'date':
                values[field['label']]=field['values'][0]['start']
            case 'embed':
                values[field['label']]=field['values'][0]['embed']['url']
            case default:
                values[field['label']]=retrun_values(field)
    # print(values)
    return values

def retrun_values(field):
    # print(field['label'],field['type'], ' :',field['values'][0])
    match(field['label']):
        case "Date Created" | "? Install Complete Date" | "MTRX NTP Approved Date":
            return field['values'][0]['start']
        # case "Stage" | "Warehouse territory" | "Status" | "? MTRX Install Status" | "Finance Type" | "Deal Status (Sales)" | "Welcome Call Checklist" | "HOA Approval Required?":
        #     return field['values'][0]['value']['text']
        case "Project Manager":
            return field['values'][0]['value']['name']
        case "Metrics" | "Sales Item":
            return None
        case default:
            return field['values'][0]['value']
        
page_cnt=0
item_cnt_per_page=50
total=podio.Item.filter(int(app_id),attributes={})['total']
print(total)

cnt= 0

for offset in tqdm(range(0, total, item_cnt_per_page)):
    cnt+=1
    if(cnt<501):
        continue
    items=get_items(app_id, limit=item_cnt_per_page, offset=offset)
    vectors=[]
    pbar = tqdm(items)
    for item in pbar:
        id=item['item_id']
        values= all_values(item['fields'])
        vector=set_item("id-"+str(id), values)
        if vector is False:
            continue
        vectors.append(vector)
        time.sleep(0.001)
        pbar.set_description("Processing %s")

    pine_index.upsert(vectors,async_req=True)