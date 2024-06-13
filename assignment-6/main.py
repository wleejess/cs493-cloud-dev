from flask import Flask, request, jsonify, render_template, send_file
from google.cloud import datastore, storage
import io

import requests
import json

from six.moves.urllib.request import urlopen
from jose import jwt
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

client = datastore.Client()

COURSES = "courses"
ENROLLMENT = "enrollment"
AVATAR = "avatar"
USERS = "users"
PHOTO_BUCKET='cmt_avatar_photos'

ERROR_400 = {"Error": "The request body is invalid"}
ERROR_401 = {"Error": "Unauthorized"}
ERROR_403 = {"Error": "You don't have permission on this resource"}
ERROR_404 = {"Error": "Not found"}
ERROR_409 = {"Error": "Enrollment data is invalid"}

CLIENT_ID = 'ErWMLzhj3siwyAKAtioj1bkrwu8IcJy9'
CLIENT_SECRET = 'XWuLVFHUu5nPNCKzCqlYGNhmzZixs_83GAfi_rdgEWQG2DTty7JzlTXJONvFlsfl'
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

# Decode the JWT supplied in the Authorization header
@app.route('/decode', methods=['GET'])
def decode_jwt():
    payload = verify_jwt(request)
    return payload                  

# Generate a JWT from the Auth0 domain and return it
# Request: JSON body with 2 properties with "username" and "password"
#       of a user registered with this Auth0 domain
# Response: JSON with the JWT as the value of the property id_token

@app.route('/')
def index():
    return render_template("index.html")

### User Endpoints
@app.route('/' + USERS + '/login', methods=['POST'])
def login_user():
    """
    Checks for a username and password and signs on using Auth0.
    """
    content = request.get_json()
    required = ["username", "password"]
    
    if not all(field in content for field in required):
        return ERROR_400, 400

    username = content["username"]
    password = content["password"]
    body = {'grant_type':'password','username':username,
            'password':password,
            'client_id':CLIENT_ID,
            'client_secret':CLIENT_SECRET,
           }
    headers = { 'content-type': 'application/json' }
    url = 'https://' + DOMAIN + '/oauth/token'
    r = requests.post(url, json=body, headers=headers)

    if r.status_code == 200:
        response_json = r.json()
        id_token = response_json.get('id_token')
        if id_token:
            return jsonify({'token': id_token}), 200
        else:
            return ERROR_403, 403
    else:
        return ERROR_401, 401

@app.route('/users', methods=['GET'])
def get_users():
    """
    Only users with the "Admin" role can access this. Returns an array with all users.
    """
    payload = verify_jwt(request)

    if payload is None:
        return ERROR_401, 401

    query = client.query(kind="users")
    query.add_filter("sub", "=", payload.get('sub'))
    results = list(query.fetch())

    for entity in results:
        role = entity.get('role')
        if role == 'admin':
            query = client.query(kind="users")
            results = list(query.fetch())
            users = []
            for r in results:
                user_data = {
                    "id": r.key.id,
                    "role": r['role'],
                    "sub": r['sub']
                }
                users.append(user_data)
            return users, 200
        return ERROR_403, 403

@app.route('/' + USERS + '/<int:id>', methods=['GET'])
def get_user(id):
    """
    Users with "admin" role can view details of any user. Otherwise, users can only view their own details.
    """
    payload = verify_jwt(request)

    if payload is None:
        return ERROR_401, 401

    role = jwt_role(payload)

    user_key = client.key('users', id)
    entity = client.get(user_key)

    if not entity:
        return ERROR_403, 403
    if role != 'admin' and jwt_id(payload) != entity.key.id:
        return ERROR_403, 403
    
    user_data = {
        "id": entity.key.id,
        "role": role,
        "sub": entity['sub']
    }

    storage_client = storage.Client()
    bucket = storage_client.get_bucket(PHOTO_BUCKET)
    filename = str(id) + '_avatar'
    blob = bucket.blob(filename)

    if blob.exists():
        user_data['avatar_url'] = request.url_root + USERS + '/' + str(id) + '/' + AVATAR
    
    if role == 'admin':
        return user_data, 200

    courses = user_courses(payload, id)
    user_data['courses'] = courses

    return user_data, 200

### Avatar Endpoints
@app.route('/' + USERS + '/<int:id>/' + AVATAR, methods=['POST'])
def upload_avatar(id):
    """
    Uploads the .png in the request as the avatar of the user's avatar. If an avatar already exists, the image is updated.
    File will be uploaded to Google Cloud Storage.
    Checks whether JWT is owned by user_id in path parameter.
    """
    if "file" not in request.files:
        return ERROR_400, 400

    payload = verify_jwt(request)

    if payload is None:
        return ERROR_401, 401

    if id != jwt_id(payload):
        return ERROR_403, 403
    
    if "tag" in request.form:
        tag = request.form['tag']
    
    # Following code is adapted from Exploration: Handling Files with Flask Part 1.
    file_obj = request.files['file']
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(PHOTO_BUCKET)

    filename = str(id) + '_avatar'
    blob = bucket.blob(filename)
    file_obj.seek(0)
    blob.upload_from_file(file_obj)

    self_link = request.url_root + USERS + '/' + str(id) + '/' + AVATAR

    return ({'avatar_url': self_link}, 200)

@app.route('/' + USERS + '/<int:id>/' + AVATAR, methods=['GET'])
def get_avatar(id):
    """
    Returns the file stored in Google Cloud Storage as the user's avatar.
    Checks whether JWT is owned by user_id in path parameter.
    """
    payload = verify_jwt(request)

    if payload is None:
        return ERROR_401, 401

    if id != jwt_id(payload):
        return ERROR_403, 403
    
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(PHOTO_BUCKET)

    filename = str(id) + '_avatar'
    blob = bucket.blob(filename)

    if not blob.exists():
        return ERROR_404, 404

    file_obj = io.BytesIO()
    blob.download_to_file(file_obj)
    file_obj.seek(0)

    user_avatar = send_file(file_obj, mimetype='image/x-png', download_name=filename)

    return user_avatar, 200

@app.route('/' + USERS + '/<int:id>/' + AVATAR, methods=['DELETE'])
def delete_avatar(id):
    """
    Deletes the file stored in Google Cloud as the user's avatar.
    Checks whether JWT is owned by user_id in path parameter.
    """
    payload = verify_jwt(request)

    if payload is None:
        return ERROR_401, 401

    if id != jwt_id(payload):
        return ERROR_403, 403

    storage_client = storage.Client()
    bucket = storage_client.get_bucket(PHOTO_BUCKET)

    filename = str(id) + '_avatar'
    blob = bucket.blob(filename)

    if not blob.exists():
        return ERROR_404, 404

    blob.delete()
    return '', 204
    
### Course Endpoints
@app.route('/' + COURSES, methods=['POST'])
def create_course():
    """
    Only users with the 'admin' role can create a course. 
    Instructor in request body must match an instructor within the database.
    Required fields: subject, number, title, term, instructor_id.
    """
    payload = verify_jwt(request)
    content = request.get_json()

    if payload is None:
        return ERROR_401, 401
    if jwt_role(payload) != 'admin':
        return ERROR_403, 403

    required_fields = ["subject", "number", "title", "term", "instructor_id"]
    if not all(field in content for field in required_fields):
        return ERROR_400, 400 

    if check_instructor(content['instructor_id']):
        new_course = datastore.entity.Entity(key=client.key(COURSES))
        new_course.update({
                'subject': content['subject'],
                'number': content['number'],
                'title': content['title'],
                'term': content['term'],
                'instructor_id': content['instructor_id']
        })
        client.put(new_course)
        new_course['id'] = new_course.key.id

        self_link = request.url_root + COURSES + '/' + str(new_course['id'])

        return ({"id": new_course['id'],
            "instructor_id": content['instructor_id'],
            "subject": content['subject'], 
            "number": content['number'], 
            "term": content['term'],
            "title": content['title'],
            "self": self_link}, 201)

    return ERROR_400, 400

@app.route('/' + COURSES, methods=['GET'])
def get_courses():
    """
    Returns paginated list of the courses (limit/offset based on paging with size of 3).
    List is sorted by "subject" property, and courses returned do not contain list of students enrolled.
    Optional query parameters: Offset, limit.
    Unprotected resource.
    """
    offset = request.args.get('offset', default=0, type=int)
    limit = request.args.get('limit', default=3, type=int)

    query = client.query(kind='courses')
    query.order = ['subject']
    query_iter = query.fetch(offset=offset, limit=limit)
    
    courses = []
    for entity in query_iter:
        self_link = request.url_root + COURSES + '/' + str(entity.key.id)

        course = {
            'id': entity.key.id,
            'instructor_id': entity.get('instructor_id'),
            'number': entity.get('number'),
            'subject': entity.get('subject'),
            'term': entity.get('term'),
            'title': entity.get('title'),
            'self': self_link
        }
        courses.append(course)

    next_offset = offset + limit
    next_url = None

    if len(courses) == limit:
        next_url = f"{request.url_root}courses?offset={next_offset}&limit={limit}"

    response = {
        'courses': courses,
        'next': next_url
    }

    return response, 200

@app.route('/' + COURSES + '/<int:id>', methods=['GET'])
def get_course(id):
    """
    Returns an existing course, does not include list of students enrolled in course.
    Unprotected resource.
    """

    course_key = client.key('courses', id)
    entity = client.get(course_key)

    if not entity:
        return ERROR_404, 404

    self_link = request.url_root + COURSES + '/' + str(entity.key.id)

    course_data = {
                "id": entity.key.id,
                "instructor_id": entity['instructor_id'],
                "number": entity['number'],
                "subject": entity['subject'],
                "term": entity['term'],
                "title": entity['title'],
                "self": self_link
            }
    return course_data, 200
    
@app.route('/' + COURSES + '/<int:id>', methods=['PATCH'])
def update_course(id):
    """
    Performs a partial update on the course.
    Only admins can update this course, optional parameters: subject, number, title, term, instructor_id.
    Note: Student enrollment cannot be modified through this endpoint.
    """
    payload = verify_jwt(request)
    content = request.get_json()

    course_key = client.key(COURSES, id)
    course = client.get(key=course_key)

    if payload is None:
        return ERROR_401, 401
    if jwt_role(payload) != 'admin':
        return ERROR_403, 403
    if course is None:
        return ERROR_400, 400

    optional_fields = ["subject", "number", "title", "term", "instructor_id"]
    update_data = {field: value for field, value in content.items() if field in optional_fields}

    if "instructor_id" in update_data and not check_instructor(update_data["instructor_id"]):
        return ERROR_400, 400

    for field, value in update_data.items():
        course[field] = value
    client.put(course)

    updated_course = get_course(id)

    return updated_course[0], 201

@app.route('/' + COURSES + '/<int:id>', methods=['DELETE'])
def delete_course(id):
    """
    Deletes a course, as well as the enrollment of all students that were enrolled in the course.
    The instructor teaching the course is no longer associated with the course.
    Only admins can delete courses.
    """
    payload = verify_jwt(request)

    course_key = client.key(COURSES, id)
    course = client.get(key=course_key)

    if payload is None:
        return ERROR_401, 401
    if jwt_role(payload) != 'admin' or course is None:
        return ERROR_403, 403
    
    client.delete(course_key)

    enrollment_query = client.query(kind=ENROLLMENT)
    enrollment_query.ancestor = course_key
    enrollments = list(enrollment_query.fetch())
    for enrollment in enrollments:
        client.delete(enrollment.key)

    return ('', 204)

### Enrollment Endpoints
@app.route('/' + COURSES + '/<int:id>/students', methods=['PATCH'])
def update_enrollment(id):
    """
    Enroll and/or disenroll students from a course.
    Only users with the admin role, or when the JWT is owned by the instructor of the course can access this endpoint.
    Requires (2) arrays: "add", and "remove". Arrays can be empty, or contain student IDs to enroll/disenroll.
    """
    payload = verify_jwt(request)
    content = request.get_json()

    course_key = client.key(COURSES, id)
    course = client.get(key=course_key)

    if payload is None:
        return ERROR_401, 401
    if course is None: 
        return ERROR_403, 403
    if jwt_role(payload) != 'admin' and jwt_id(payload) != course['instructor_id']:
        return ERROR_403, 403

    enrollments = valid_enrollments(content, payload)

    if not enrollments:
        return ERROR_409, 409
    
    add_list, remove_list = enrollments[0], enrollments[1]
    course_key = client.key(COURSES, id)

    for student_id in add_list:
        enrollment_key = client.key(ENROLLMENT, student_id, parent=course_key)
        existing_enrollment = client.get(enrollment_key)
        if existing_enrollment:
            continue
        new_enrollment = datastore.Entity(key=enrollment_key)
        new_enrollment.update({
            'course_id': id,
            'student_id': student_id
        })
        client.put(new_enrollment)

    for student_id in remove_list:
        enrollment_key = client.key(ENROLLMENT, student_id, parent=course_key)
        existing_enrollment = client.get(enrollment_key)
        if not existing_enrollment:
            continue
        client.delete(enrollment_key)
    
    return '', 200

@app.route('/' + COURSES + '/<int:id>/students', methods=['GET'])
def get_enrollment(id):
    """
    Gets the list of students enrolled in a course.
    Only users with the admin role, or when the JWT is owned by the instructor of this course can access this endpoint.
    """
    payload = verify_jwt(request)

    course_key = client.key(COURSES, id)
    course = client.get(key=course_key)

    if payload is None:
        return ERROR_401, 401
    if course is None:
        return ERROR_403, 403
    if jwt_role(payload) != 'admin' and jwt_id(payload) != course['instructor_id']:
        return ERROR_403, 403
    
    query = client.query(kind='enrollment')
    query.add_filter('course_id', '=', id)
    enrollments = query.fetch()

    results = []
    for enrollment in enrollments:
        student_id = enrollment['student_id']
        results.append(student_id)

    return jsonify(results), 200

### Helper Functions 
def jwt_role(payload):
    """
    Helper function to check what role this JWT bearer has.
    """
    query = client.query(kind="users")
    query.add_filter("sub", "=", payload.get('sub'))
    results = list(query.fetch())
    if not results:
        return None
    entity = results[0]
    role = entity.get('role')
    return role

def jwt_id(payload):
    """
    Helper function to get the ID of the JWT bearer.
    """
    query = client.query(kind="users")
    query.add_filter("sub", "=", payload.get('sub'))
    results = list(query.fetch())
    if not results:
        return None
    entity = results[0]
    return entity.key.id

def check_instructor(instructor_id):
    """
    Helper function to check whether instructor from request exists in database.
    Returns True if instructor matches an existing instructor, otherwise False.
    """
    instructor_key = client.key('users', instructor_id)
    entity = client.get(instructor_key)

    if not entity:
        return False
    if entity.get('role') == 'instructor':
        return True
    return False

def valid_enrollments(content, payload):
    """
    Helper function to check that enrollment data is valid based on:
    1) There is no common value between 'add' and 'remove' arrays.
    2) All values in the array 'add' and 'remove' correspond to the ID of a student.
    """
    add_list, remove_list = set(content.get('add', [])), set(content.get('remove', []))
    
    if add_list & remove_list:
        return False
    
    if add_list:
        for user_id in add_list:
            user_key = client.key('users', user_id)
            entity = client.get(user_key)
            if not entity:
                return False
            if entity['role'] != 'student':
                return False

    if remove_list:
        for user_id in remove_list:
            user_key = client.key('users', user_id)
            entity = client.get(user_key)
            if not entity:
                return False
            if entity['role'] != 'student':
                return False

    return add_list, remove_list

def user_courses(payload, id):
    """
    Helper function to get a list of courses.
    If id belongs to an instructor, shows courses they are teaching.
    If id belongs to a student, shows courses they are enrolled in.
    """
    courses = []
    if jwt_role(payload) == 'instructor':
        query = client.query(kind=COURSES)
        query.add_filter('instructor_id', '=', id)
        courses = list(query.fetch())
    elif jwt_role(payload) == 'student':
        query = client.query(kind=ENROLLMENT)
        query.add_filter('student_id', '=', id)
        courses = list(query.fetch())
    return courses

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
