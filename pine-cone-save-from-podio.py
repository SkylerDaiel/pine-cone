import json
import os
from tqdm import tqdm
import time

# moduld related with openai
import openai

# pinecone module
import pinecone

# podio module
from pypodio2 import api as podio_api

# read env file
from dotenv import load_dotenv

# get api key of openai from .env
load_dotenv()

pine_cone_api_key = os.getenv("PINE_CONE_API_KEY")
pine_cone_environment = os.getenv("PINE_CONE_ENVIRONMENT")
pine_cone_indexName = os.getenv("PINE_CONE_INDEXNAME")
print("pine_cone_api_key: ", pine_cone_api_key)
print("pine_cone_environment: ", pine_cone_environment)
print("pine_cone_indexName: ", pine_cone_indexName)


openai_api_key = os.getenv("OPENAI_API_KEY")
print("openai_api_key_____", openai_api_key)
openai.api_key = openai_api_key

MODEL = "text-embedding-ada-002"

pinecone.init(api_key=pine_cone_api_key, environment=pine_cone_environment)

# check if 'pine_cone_indexName' index already exists (only create index if not)
if pine_cone_indexName not in pinecone.list_indexes():
    res = openai.Embedding.create(
        input=[
            "Sample document text goes here",
            "there will be several phrases in each batch",
        ],
        engine=MODEL,
    )

    # extract embeddings to a list
    embeds = [record["embedding"] for record in res["data"]]
    try:
        pinecone.create_index(pine_cone_indexName, dimension=len(embeds[0]))
        print("created index")
    except:
        print("error")

pine_index = pinecone.Index(pine_cone_indexName)

#############################
client_id = os.getenv("PODIO_CLIENT_ID")
client_secret = os.getenv("PODIO_CLIENT_SECRET")
app_id = os.getenv("PODIO_APP_ID")
app_token = os.getenv("PODIO_APP_TOKEN")

podio = podio_api.OAuthAppClient(client_id, client_secret, app_id, app_token)

max_cycle_cnt = 6
DELAY_TIME = 1
print("start training")


def get_items(app_id, limit, offset, cycle_cnt=0):
    try:
        return podio.Item.filter(
            int(app_id),
            attributes={
                "limit": limit,
                "offset": offset,
                # "sort_by": "created_on",
                # "sort_desc": False,
                "sort_by": "last_edit_on",
                "sort_desc": True,
            },
        )["items"]
    except Exception as error:
        if cycle_cnt > max_cycle_cnt:
            return False
        print("error when get item from podio :\n", error)
        return get_items(app_id, limit, offset, cycle_cnt + 1)


def str_embedding(text, cycle_cnt=0):
    try:
        return openai.Embedding.create(input=text, engine=MODEL)["data"][0]["embedding"]
    except Exception as error:
        if cycle_cnt > max_cycle_cnt:
            return False
        print(error)
        time.sleep(DELAY_TIME)
        return str_embedding(text, cycle_cnt + 1)


def upsert_pinecone(vectors, cycle_cnt=0):
    try:
        upsert_response = pine_index.upsert(vectors, async_req=True)
        # print(upsert_response)
    except Exception as error:
        if cycle_cnt > max_cycle_cnt:
            return False
        print(error)
        time.sleep(DELAY_TIME)
        upsert_pinecone(vectors, cycle_cnt + 1)


def get_item_from_podio(id, cycle_cnt=0):
    try:
        return podio.Item.find(item_id=int(id))
    except Exception as error:
        if cycle_cnt > max_cycle_cnt:
            return False
        print(error)
        time.sleep(DELAY_TIME)
        return get_item_from_podio(id, cycle_cnt + 1)


def set_item(id, new_values={}, comments=[]):
    text = ""
    if ("Customer Full Name" in new_values) == False:
        return False
    text += f"The customer's name is {new_values['Customer Full Name']}. "

    text += f"Now the stage of project is "
    if "Stage" in new_values:
        text += new_values["Stage"]
    else:
        text += "none"
    text += ". "

    text += f"And the address of customer is "
    if "Property Address" in new_values:
        text += new_values["Property Address"]
    else:
        text += "none"
    text += ". "
    text += f"The email of customer is "

    if "Customer Email" in new_values:
        text += new_values["Customer Email"]
    else:
        text += "none"
    text += ". "

    embedding = str_embedding(text)

    return {
        "id": id,
        "values": embedding,
        "metadata": {"project": new_values, "comments": comments},
    }


def all_values(fields):
    values = {}
    for field in fields:
        # match (field["label"]):
        #     case "Customer Full Name" | "Customer Email" | "Property Address":
        #         values[field["label"]] = field["values"][0]["value"]
        #     case "Stage":
        #         values[field["label"]] = field["values"][0]["value"]["text"]
        #     case default:
        #         continue
        match (field["type"]):
            case "app":
                values[field["label"]] = None
            case "category":
                values[field["label"]] = field["values"][0]["value"]["text"]
            case "date":
                values[field["label"]] = field["values"][0]["start"]
            case "embed":
                values[field["label"]] = field["values"][0]["embed"]["url"]
            case default:
                values[field["label"]] = retrun_values(field)
    # print(values)
    return values


def retrun_values(field):
    # print(field['label'],field['type'], ' :',field['values'][0])
    match (field["label"]):
        case "Date Created" | "? Install Complete Date" | "MTRX NTP Approved Date" | "CCA Date":
            return field["values"][0]["start"]
        case "Stage" | "Warehouse territory" | "Status" | "? MTRX Install Status" | "Finance Type" | "Deal Status (Sales)" | "Welcome Call Checklist" | "HOA Approval Required?":
            return field["values"][0]["value"]["text"]
        case "Project Manager":
            return field["values"][0]["value"]["name"]
        case "Metrics" | "Sales Item":
            return None
        case default:
            return field["values"][0]["value"]


def handle_comments(comments=[]):
    new_comments = []
    for comment in comments:
        new_comments.append(
            {
                "Username who wrote the comment": comment["user"]["name"],
                "comment": comment["value"],
                "Date/time the comment was created": comment["created_on"],
            }
        )
    return new_comments


page_cnt = 0
item_cnt_per_page = 50
total = podio.Item.filter(int(app_id), attributes={})["total"]
print(total)

cnt = 0

for offset in tqdm(range(0, total, item_cnt_per_page)):
    cnt += 1
    # if(cnt<950):
    #     continue
    if cnt > 10:
        break
    items = get_items(app_id, limit=item_cnt_per_page, offset=offset)
    vectors = []
    pbar = tqdm(items)
    for item in pbar:
        id = item["item_id"]
        comments_data = []
        if item["comment_count"] != 0:
            item = get_item_from_podio(id)
            comments_data = handle_comments(comments=item["comments"])
        # json_formatted_str = json.dumps(comments_data, indent=2)
        # print(json_formatted_str)
        values = all_values(item["fields"])
        vector = set_item("id-" + str(id), values, comments_data)
        if vector is False:
            continue
        vectors.append(vector)
        time.sleep(0.01)
        pbar.set_description("Processing %s")
    upsert_pinecone(vectors)
