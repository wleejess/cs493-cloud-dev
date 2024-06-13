# Adapted from example code in "Exploration - Implementing Auth Using JWTs"
# Canvas - CS493 Cloud App Development, Module 7: Security and JWTs.

from flask import Flask, request, jsonify
from google.cloud import datastore

import requests
import json

from six.moves.urllib.request import urlopen
from jose import jwt
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

client = datastore.Client()
query = client.query(kind='Your_Entity_Kind')
results = list(query.fetch())
for entity in results:  
    client.delete(entity.key)

BUSINESSES = "businesses"
ERROR_JWT = {"Error":"Invalid JWT / Unauthorized access."}
ERROR_MISSING_ATTRIBUTE = {"Error": "The request body is missing at least one of the required attributes"}
ERROR_NO_BUSINESS = {"Error": "No business with this business_id exists"}
ERROR_DUPE = {"Error": "You have already submitted a review for this business. You can update your previous review, or delete it and submit a new review"}

CLIENT_ID = '06vRwHQgBN3jvEU5Ck4NsrTOEvAv6UUY'
CLIENT_SECRET = 'SHhG0fQpVvOi893X-HJ3oanLXdJa66InT-vuovLNqLhkTmbVbFumxkIwiG8CVJBv'
DOMAIN = 'dev-aiwvx7zp7o7fed7k.us.auth0.com'

ALGORITHMS = ["RS256"]

oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    api_base_url="https://" + DOMAIN,
    access_token_url="https://" + DOMAIN + "/oauth/token",
    authorize_url="https://" + DOMAIN + "/authorize",
    client_kwargs={
        'scope': 'openid profile email',
    },
)

# This code is adapted from https://auth0.com/docs/quickstart/backend/python/01-authorization?_ga=2.46956069.349333901.1589042886-466012638.1589042885#create-the-jwt-validation-decorator

class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response

# Verify the JWT in the request's Authorization header
def verify_jwt(request):
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization'].split()
        token = auth_header[1]
    else:
        return None
    
    jsonurl = urlopen("https://"+ DOMAIN+"/.well-known/jwks.json")
    jwks = json.loads(jsonurl.read())
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        return None
    if unverified_header["alg"] == "HS256":
        return None
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=CLIENT_ID,
                issuer="https://"+ DOMAIN+"/"
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTClaimsError:
            return None
        except Exception:
            return None
        return payload
    else:
        return None

@app.route('/')
def index():
    return render_template("index.html")
    
# Create a lodging if the Authorization header contains a valid JWT
@app.route('/businesses', methods=['POST'])
def businesses_post():
    if request.method == 'POST':
        content = request.get_json()
        if check_attributes(content):
            payload = verify_jwt(request)

            if payload is None:
                return ERROR_JWT, 401

            new_business = datastore.entity.Entity(key=client.key(BUSINESSES))
            new_business.update({
                "owner_id": payload["sub"],
                'name': content['name'],
                'street_address': content['street_address'],
                'city': content['city'],
                'state': content['state'],
                'zip_code': content['zip_code'],
                'inspection_score': content['inspection_score']
            })
            client.put(new_business)
            new_business['id'] = new_business.key.id

            base_url = request.url_root
            self_link = base_url + 'businesses/' + str(new_business['id'])

            return ({"id": new_business['id'],
                "owner_id": payload["sub"],
                "name": content['name'], 
                "street_address": content['street_address'], 
                "city": content['city'],
                "state": content['state'],
                "zip_code": content['zip_code'],
                "inspection_score": content['inspection_score'],
                "self": self_link}, 201)
        else:
            return ERROR_MISSING_ATTRIBUTE, 400
    else:
        return jsonify(error='Method not recogonized')

@app.route('/' + BUSINESSES + '/<int:id>', methods=['GET'])
def business_get(id):
    payload = verify_jwt(request)
    if payload is None:
        return ERROR_JWT, 401

    business_key = client.key(BUSINESSES, id)
    business = client.get(key=business_key)

    if business is None:
        return ERROR_NO_BUSINESS, 403
    if payload['sub'] != business['owner_id']:
        return ERROR_NO_BUSINESS, 403
    business['id'] = business.key.id
    base_url = request.url_root
    self_link = base_url + 'businesses/' + str(business['id'])

    return ({"id": id,
                "owner_id": payload["sub"],
                "name": business['name'], 
                "street_address": business['street_address'], 
                "city": business['city'],
                "state": business['state'],
                "zip_code": business['zip_code'],
                "inspection_score": business['inspection_score'],
                "self": self_link}, 200)

@app.route('/' + BUSINESSES, methods=['GET'])
def businesses_list():
    payload = verify_jwt(request)
    base_url = request.url_root
    
    if payload is None:
        # No valid JWT, return all businesses
        query = client.query(kind=BUSINESSES)
        results = list(query.fetch())
        print(results)
        businesses = []
        for r in results:
            self_link = base_url + 'businesses/' + str(r.key.id)
            business_data = {
                "id": r.key.id,
                "owner_id": r['owner_id'],
                "name": r['name'],
                "street_address": r['street_address'],
                "city": r['city'],
                "state": r['state'],
                "zip_code": r['zip_code'],
                "self": self_link
            }
            businesses.append(business_data)
        return businesses, 200
    else:
        sub = payload.get('sub')
        query = client.query(kind=BUSINESSES)
        query.add_filter('owner_id', '=', sub)
        results = list(query.fetch())
        businesses = []
        for r in results:
            self_link = base_url + 'businesses/' + str(r.key.id)
            business_data = {
                "id": r.key.id,
                "owner_id": r['owner_id'],
                "name": r['name'],
                "street_address": r['street_address'],
                "city": r['city'],
                "state": r['state'],
                "zip_code": r['zip_code'],
                "inspection_score": r['inspection_score'],
                "self": self_link
            }
            businesses.append(business_data)
        return businesses, 200

@app.route('/' + BUSINESSES + '/<int:id>', methods=['DELETE'])
def delete_business(id):
    payload = verify_jwt(request)
    if payload is None:
        return ERROR_JWT, 401

    business_key = client.key(BUSINESSES, id)
    business = client.get(key=business_key)
    if business is None:
        return ERROR_NO_BUSINESS, 403
    if payload['sub'] != business['owner_id']:
        return ERROR_NO_BUSINESS, 403

    client.delete(business_key)
    return ('', 204)

def check_attributes(content):
    if 'name' not in content or content['name'] is None:
        return False
    if 'street_address' not in content or content['street_address'] is None:
        return False
    if 'city' not in content or content['city'] is None:
        return False
    if 'state' not in content or content['state'] is None:
        return False
    if 'zip_code' not in content or content ['zip_code'] is None:
        return False
    if 'inspection_score' not in content or content['inspection_score'] is None:
        return False
    return True

# Decode the JWT supplied in the Authorization header
@app.route('/decode', methods=['GET'])
def decode_jwt():
    payload = verify_jwt(request)
    return payload                  

# Generate a JWT from the Auth0 domain and return it
# Request: JSON body with 2 properties with "username" and "password"
#       of a user registered with this Auth0 domain
# Response: JSON with the JWT as the value of the property id_token

@app.route('/login', methods=['POST'])
def login_user():
    content = request.get_json()
    username = content["username"]
    password = content["password"]
    body = {'grant_type':'password','username':username,
            'password':password,
            'client_id':CLIENT_ID,
            'client_secret':CLIENT_SECRET
           }
    headers = { 'content-type': 'application/json' }
    url = 'https://' + DOMAIN + '/oauth/token'
    r = requests.post(url, json=body, headers=headers)
    return r.text, 200, {'Content-Type':'application/json'}

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
