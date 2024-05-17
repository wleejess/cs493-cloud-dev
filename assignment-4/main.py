import random
import string
import requests
import logging

from flask import Flask, render_template, request, redirect, url_for, session
from google.cloud import datastore

app = Flask(__name__)

BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth?"
CLIENT_ID = "this is a secret" # information when you create OAuth credentials
CLIENT_SECRET = "more secrets" # information when you create OAuth credentials
REDIRECT_URI = "https://a4-jessicalee.uw.r.appspot.com/oauth" # actual link
# REDIRECT_URI = "http://localhost:8080/oauth" for local testing
TOKEN_URL = "https://oauth2.googleapis.com/token"
PROFILE_API_URL = "https://people.googleapis.com/v1/people/me?personFields=names"

datastore_client = datastore.Client()

@app.route("/", methods=["GET", "POST"])
def root():
    """
    Index page for assignment.
    """
    return render_template("index.html")

@app.route("/get_auth", methods=["POST"])
def get_auth():
    """
    Helper function to build the request.
    """
    response_type = "code"
    scope = "https://www.googleapis.com/auth/userinfo.profile"
    state = str(get_random_state())
    save_state(state)
    prompt = "consent"
    include_granted_scopes = "true"
    request_link = (f"{BASE_URL}response_type={response_type}&scope={scope}&state={state}"
                    f"&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&"
                    f"&PROMPT={prompt}&include_granted_scopes={include_granted_scopes}")
    return redirect(request_link)

def get_random_state(length=16):
    """
    Helper function to generate a random state.
    """
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def save_state(state):
    """
    Save state value to Datastore.
    """
    kind = "OAuthState"
    key = datastore_client.key(kind)
    entity = datastore.Entity(key=key)
    entity.update({"state": state})
    datastore_client.put(entity)

def get_state():
    """
    Retrieve state value from Datastore.
    """
    query = datastore_client.query(kind='OAuthState')
    entities = list(query.fetch())
    if entities:
        return entities[0]['state']
    else:
        return None

def delete_oauth_states():
    """
    Delete all saved OAuth states from Datastore.
    """
    client = datastore.Client()

    query = client.query(kind='OAuthState')
    keys = [entity.key for entity in query.fetch()]

    if keys:
        client.delete_multi(keys)

@app.route("/oauth")
def oauth_callback():
    """
    Check parameters and then send a request for authorization.
    """
    saved_state = get_state()
    received_state = request.args.get('state')
    code = request.args.get('code')

    print("saved_state", save_state)
    print("received", received_state)

    if received_state != saved_state:
        return "Error: State mismatch"

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": 'authorization_code'
    }

    response = requests.post(TOKEN_URL, data=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get('access_token')
        save_access_token(access_token)
        return redirect(url_for('profile'))
    else:
        logging.error("Error during token retrieval: %s", response.text)
        return redirect(url_for('root'))

def save_access_token(access_token):
    """
    Save access token to Datastore.
    """
    kind = 'AccessToken'
    key = datastore_client.key(kind, 'singleton')
    entity = datastore.Entity(key=key)
    entity.update({'access_token': access_token})
    datastore_client.put(entity)

def get_access_token():
    """
    Retrieve access token from Datastore.
    """
    kind = 'AccessToken'
    key = datastore_client.key(kind, 'singleton')
    entity = datastore_client.get(key)
    if entity:
        return entity.get('access_token')
    else:
        return None

@app.route("/profile")
def profile():
    """
    Returns profile page with information.
    """
    access_token = get_access_token()

    if access_token:
        headers = {'Authorization': 'Bearer ' + access_token}
        response = requests.get(PROFILE_API_URL, headers=headers)

        if response.status_code == 200:
            profile_data = response.json()
            names = profile_data['names']
            given_name = names[0]['givenName']
            family_name = names[0]['familyName']
            saved_state = get_state()
            delete_oauth_states()
            return render_template("profile.html", given_name=given_name, family_name=family_name, state=saved_state)
        else:
            logging.error("Error fetching profile information: %s", response.text)
            return "Error fetching profile information"
    else:
        logging.error("Access token not found.")
        return "Error: Access token not found."

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)