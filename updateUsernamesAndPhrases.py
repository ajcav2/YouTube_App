import httplib2
import os
import sys
import aws_keys

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

import boto3

# Declare table variables
dynamodb = boto3.resource('dynamodb',
                          aws_access_key_id=aws_keys.key_id,
                          aws_secret_access_key=aws_keys.secret_key,
                          region_name="us-west-2")

table = dynamodb.Table('YouTube_App')

# This function performs the following tasks to get an accurate list of usernames:
#   1.) Read usernames from user-modified text file
#   2.) Get a list of old usernames from DDB and delete them all
#   3.) Get uploads playlist ID for each username in usernames
#   4.) Send all usernames/uploadIDs to DDB
#   5.) Add user phrases to DDB
def updateUsernames():
    # Open file and read individual lines to get usernames
    with open("C:\Users\Alex\Desktop\usernames.txt", "r") as usernameFile:
        usernames = []
        for line in usernameFile:
            usernames.append(line.strip())

        # Get all old usernames from table
        oldScan = table.scan(
            ProjectionExpression="username"
        )

        oldUsernames = []
        for key in oldScan['Items']:
            oldUsernames.append(key['username'])

        # Delete all old usernames
        for oldName in oldUsernames:
            table.delete_item(
                Key={
                    'username':oldName
                }
            )

        # Get uploads playlist ID for each user
        uploadsID = getUploadsID(usernames)

        # Add new usernames
        i = 0
        for name in usernames:
            table.put_item(
                Item={
                    'username':name,
                    'uploadsID':uploadsID[i]
                }
            )
            i += 1

        addPhrases()
        return usernames

# This function returns an array of upload playlist IDs when passed an array
# of usernames
def getUploadsID(usernames):
    uploadsID = []
    for name in usernames:
        channels = channels_list_by_username(service,
            part='snippet,contentDetails',
            forUsername=name
            )
        uploadsID.append(channels['items'][0]['contentDetails']['relatedPlaylists']['uploads'])
    return uploadsID

# This function adds user-defined phrases to DDB
def addPhrases():
    with open("C:\Users\Alex\Desktop\phrases.txt", "r") as phraseFile:
        phrases = []
        for line in phraseFile:
            phrases.append(line.strip())

        for phrase in phrases:
            table.put_item(
                Item={
                    'username':'phrases',
                    'phrase':phrases
                }
            )
        return phrases


# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret.
CLIENT_SECRETS_FILE = "C:\Users\Alex\Documents\YouTube_App\client_secret.json"

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

# Sample python code for channels.list

def channels_list_by_username(service, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs) # See full sample for function
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
  kwargs = remove_empty_kwargs(**kwargs) # See full sample for function
  results = service.playlistItems().list(
    **kwargs
  ).execute()
  return results

if __name__ == '__main__':
    try:
        updateUsernames()
    except:
        print("An error occured.")
