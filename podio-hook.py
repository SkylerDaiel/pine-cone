import os
#podio module
from  pypodio2 import api as podio_api

# read env file
from dotenv import load_dotenv
#get api key of openai from .env
load_dotenv()

#############################
client_id=os.getenv("PODIO_CLIENT_ID")
client_secret=os.getenv("PODIO_CLIENT_SECRET")
app_id=os.getenv("PODIO_APP_ID")
app_token=os.getenv("PODIO_APP_TOKEN")

podio = podio_api.OAuthAppClient(client_id,client_secret,app_id,app_token)

response = podio.Hook.create(attributes={
    'url': 'http://3.74.28.231:80/api/podio',
    'type': 'item.update'
})

print(response)