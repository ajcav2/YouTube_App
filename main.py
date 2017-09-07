import time
import httplib2
import os
import sys
from datetime import datetime, timedelta
from twilio.rest import Client
import aws_keys

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

import boto3
import phone_numbers

dynamodb = boto3.resource('dynamodb',
                          aws_access_key_id=aws_keys.key_id,
                          aws_secret_access_key=aws_keys.secret_key,
                          region_name="us-west-2")

table = dynamodb.Table('YouTube_App')

def getListOfUsernames():
    # Get all the usernames from DDB
    print("Getting usernames...")
    scan = table.scan(
        ProjectionExpression="username"
    )

    usernames = []
    for key in scan['Items']:
        if key['username'] != "phrases":
            usernames.append(key['username'])
    print("Fetched usernames")
    return usernames


def getListOfUploadIDs(usernames):
    # Get all upload IDs.
    print("Getting upload IDs...")
    scan = table.scan(
        ProjectionExpression="uploadsID"
    )

    uploadsID = []

    for key in scan['Items']:
        try:
            uploadsID.append(key['uploadsID'])
        except KeyError as e:
            pass
    print("Fetched upload IDs")
    return uploadsID

def getAllPhrases():
    # Get all phrases.
    print("Getting phrases...")
    scan = table.scan(
        ProjectionExpression="phrase"
    )

    phrases = []
    for key in scan['Items']:
        try:
            phrases.append(key['phrase'])
        except KeyError as e:
            pass

    print("Fetched phrases")
    return phrases

def checkForMatch(Usernames, uploadsID, phrases):
    # Check for videos in uploadsID that are less than an hour old. If the video
    # is less than an hour old, check if it has a key phrase. If it has a key
    # phrase, send a text with the username and title.

    print("Checking for matches...")
    i = 0
    for ID in uploadsID:
        ytResponse = playlist_perID_wrapper(ID)

        title = ytResponse['items'][0]['snippet']['title']
        description = ytResponse['items'][0]['snippet']['description'].strip()
        publishedAt_yt = ytResponse['items'][0]['snippet']['publishedAt'].strip()
        videoId = ytResponse['items'][0]['snippet']['resourceId']['videoId']

        publishedAt = datetime.strptime(publishedAt_yt, '%Y-%m-%dT%H:%M:%S.000Z') - timedelta(hours = 5)
        now = datetime.now()
        if (now - timedelta(hours = 24) < publishedAt):
            for phrase in phrases[0]:
                if phrase.lower() in description.lower() or phrase.lower() in title.lower():
                    sendText(constructMessage(Usernames[i], title, videoId))
                    print("Text sent")
                    break
        i += 1
    print("Match check complete")



def constructMessage(username, title, videoId):
    print("Message constructed")
    return "Hi Shelby! " + username.title() + " just posted a video you may be interested in: " + title + ". Watch it here: " + createLink(videoId)

def sendText(message):
    account_sid = twilio_keys.account_sid
    auth_token = twilio_keys.auth_token
    client = Client(account_sid, auth_token)
    client.api.account.messages.create(to=phone_numbers.my_number,from_="+16307553450",body=message)

def createLink(videoId):
    print("Link created")
    return "https://www.youtube.com/watch?v=" + videoId

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret.
CLIENT_SECRETS_FILE = "/home/pi/YouTube_App/client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
YOUTUBE_READ_WRITE_SSL_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# This variable defines a message to display if the CLIENT_SECRETS_FILE is
# missing.
MISSING_CLIENT_SECRETS_MESSAGE = "WARNING: Please configure OAuth 2.0"

# Authorize the request and store authorization credentials.
def get_authenticated_service(args):
  flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=YOUTUBE_READ_WRITE_SSL_SCOPE,
    message=MISSING_CLIENT_SECRETS_MESSAGE)

  storage = Storage("youtube-api-snippets-oauth2.json")
  credentials = storage.get()

  if credentials is None or credentials.invalid:
    credentials = run_flow(flow, storage, args)

  # Trusted testers can download this discovery document from the developers page
  # and it should be in the same directory with the code.
  return build(API_SERVICE_NAME, API_VERSION,
      http=credentials.authorize(httplib2.Http()))


args = argparser.parse_args()
service = get_authenticated_service(args)

def print_results(results):
  print(results)

# Build a resource based on a list of properties given as key-value pairs.
# Leave properties with empty values out of the inserted resource.
def build_resource(properties):
  resource = {}
  for p in properties:
    # Given a key like "snippet.title", split into "snippet" and "title", where
    # "snippet" will be an object and "title" will be a property in that object.
    prop_array = p.split('.')
    ref = resource
    for pa in range(0, len(prop_array)):
      is_array = False
      key = prop_array[pa]
      # Convert a name like "snippet.tags[]" to snippet.tags, but handle
      # the value as an array.
      if key[-2:] == '[]':
        key = key[0:len(key)-2:]
        is_array = True
      if pa == (len(prop_array) - 1):
        # Leave properties without values out of inserted resource.
        if properties[p]:
          if is_array:
            ref[key] = properties[p].split(',')
          else:
            ref[key] = properties[p]
      elif key not in ref:
        # For example, the property is "snippet.title", but the resource does
        # not yet have a "snippet" object. Create the snippet object here.
        # Setting "ref = ref[key]" means that in the next time through the
        # "for pa in range ..." loop, we will be setting a property in the
        # resource's "snippet" object.
        ref[key] = {}
        ref = ref[key]
      else:
        # For example, the property is "snippet.description", and the resource
        # already has a "snippet" object.
        ref = ref[key]
  return resource

# Remove keyword arguments that are not set
def remove_empty_kwargs(**kwargs):
  good_kwargs = {}
  if kwargs is not None:
    for key, value in kwargs.iteritems():
      if value:
        good_kwargs[key] = value
  return good_kwargs

### END BOILERPLATE CODE

def channels_list_by_username(service, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)
  results = service.channels().list(
    **kwargs
  ).execute()

  return results

def playlist_perID_wrapper(uploadsID):
  return playlist_items_list_by_playlist_id(service,
       part='snippet,contentDetails',
       maxResults=50,
       playlistId=uploadsID)

def playlist_items_list_by_playlist_id(service, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)
  results = service.playlistItems().list(
    **kwargs
  ).execute()
  return results

if __name__ == '__main__':
  checkForMatch(getListOfUsernames(), getListOfUploadIDs(getListOfUsernames()), getAllPhrases())
