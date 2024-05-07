from __future__ import annotations

import logging
import os

from flask import Flask, request

import sqlalchemy
from sqlalchemy.exc import OperationalError

from connect_connector import connect_with_connector

BUSINESSES = 'businesses'
REVIEWS = 'reviews'
ERROR_MISSING_ATTRIBUTE = ({"Error": "The request body is missing at "
                            "least one of the required attributes"})
ERROR_NO_REVIEW = {"Error": "No review with this review_id exists"}
ERROR_NO_BUSINESS = {"Error": "No business with this business_id exists"}
ERROR_NO_OWNER = {"Error": "No owner with this owner_id exists"}
ERROR_DUPE = ({"Error": "You have already submitted a review for this business. "
               "You can update your previous review, or delete it and submit a new review"})

app = Flask(__name__)

base_url = 'http://127.0.0.1:8080'

logger = logging.getLogger()

def init_connection_pool() -> sqlalchemy.engine.base.Engine:
    """
    Set up connection pool for the app.
    """
    if os.environ.get('INSTANCE_CONNECTION_NAME'):
        return connect_with_connector()

    raise ValueError(
        'Missing database connection type. Please define INSTANCE_CONNECTION_NAME'
    )

# This global variable is declared with a value of `None`
db = None

def init_db():
    """
    Initiates connection to database
    """
    global db
    db = init_connection_pool()

def drop_businesses_table(db: sqlalchemy.engine.base.Engine) -> None:
    """
    Drop 'businesses' table from the database, if it exists (to avoid data anomalies when running new tests)
    """
    try:
        with db.connect() as conn:
            conn.execute(
                sqlalchemy.text(
                    'DROP TABLE IF EXISTS businesses;'
                )
            )
            conn.commit()
            print("'businesses' table dropped successfully.")
    except OperationalError as e:
        print("Error dropping 'businesses' table:", e)

def drop_reviews_table(db: sqlalchemy.engine.base.Engine) -> None:
    """
    Drop 'reviews' table from the database, if it exists (to avoid data anomalies when running new tests)
    """
    try:
        with db.connect() as conn:
            conn.execute(
                sqlalchemy.text(
                    'DROP TABLE IF EXISTS reviews;'
                )
            )
            conn.commit()
            print("'reviews' table dropped successfully.")
    except OperationalError as e:
        print("Error dropping 'reviews' table:", e)

def create_businesses_table(db: sqlalchemy.engine.base.Engine) -> None:
    """
    Create 'businesses' table in database, if it does not already exist.
    """
    try:
        with db.connect() as conn:
            conn.execute(
                sqlalchemy.text(
                    'CREATE TABLE IF NOT EXISTS businesses ('
                    'business_id INT AUTO_INCREMENT,'
                    'owner_id INT NOT NULL,'
                    'name VARCHAR(50) NOT NULL,'
                    'street_address VARCHAR(100) NOT NULL,'
                    'city VARCHAR(50) NOT NULL,'
                    'state CHAR(2) NOT NULL,'
                    'zip_code CHAR(5) NOT NULL,'
                    'PRIMARY KEY (business_id));'
                )
            )
            conn.commit()
    except OperationalError as e:
        print("Error creating 'businesses' table:", e)

def create_reviews_table(db: sqlalchemy.engine.base.Engine) -> None:
    """
    Create 'review' table in database, if it does not already exist.
    """
    try:
        with db.connect() as conn:
            conn.execute(
                sqlalchemy.text(
                    'CREATE TABLE IF NOT EXISTS reviews ('
                    'review_id INT AUTO_INCREMENT,'
                    'user_id INT NOT NULL,'
                    'business_id INT NOT NULL,'
                    'stars INT NOT NULL,'
                    'review_text VARCHAR(1000),'
                    'PRIMARY KEY (review_id),'
                    'FOREIGN KEY (business_id) REFERENCES businesses(business_id) ON DELETE CASCADE);'
                )
            )
            conn.commit()
    except OperationalError as e:
        print("Error creating 'reviews' table:", e)

@app.route('/')
def index():
    """ Defines the index page. """
    return 'Please navigate to /businesses to use this API'

# Create a businesses
@app.route('/' + BUSINESSES, methods=['POST'])
def post_businesses():
    """
    Allows you to create a new business.
    Returns status 400 if missing any of the required attributes.
    Returns status 201 and inserts to MySQL database with business.
    """
    content = request.get_json()

    if check_attributes(content):
        try:
            # Using a with statement ensures that the connection is always released
            # back into the pool at the end of statement (even if an error occurs)
            with db.connect() as conn:
                # Preparing a statement before hand can help protect against injections.
                stmt = sqlalchemy.text(
                    'INSERT INTO businesses(owner_id, name, street_address, city, state, zip_code) '
                    ' VALUES (:owner_id, :name, :street_address, :city, :state, :zip_code)'
                )
                # connection.execute() automatically starts a transaction
                conn.execute(stmt, parameters={'owner_id': content['owner_id'],
                                            'name': content['name'], 
                                            'street_address': content['street_address'], 
                                            'city': content['city'],
                                            'state': content['state'],
                                            'zip_code': content['zip_code']})
                                            
                stmt2 = sqlalchemy.text('SELECT last_insert_id()')
                business_id = conn.execute(stmt2).scalar()
                conn.commit()

        except Exception as e:
            logger.exception(e)
            return ({'Error': 'Unable to create business'}, 500)

        self_link = base_url + '/businesses/' + str(business_id)

        return ({"id": business_id,
                "owner_id": content['owner_id'],
                "name": content['name'], 
                "street_address": content['street_address'], 
                "city": content['city'],
                "state": content['state'],
                "zip_code": content['zip_code'],
                "self": self_link}, 201)

    return ERROR_MISSING_ATTRIBUTE, 400

# Get all businesses
@app.route('/' + BUSINESSES, methods=['GET'])
def get_businesses():
    """
    Lists all businesses, takes two optional query parameters: offset, limit.
    """
    # Get the query parameters from the request
    offset = request.args.get('offset', default=0, type=int)
    limit = request.args.get('limit', default=3, type=int)

    with db.connect() as conn:
        stmt = sqlalchemy.text(
            'SELECT * FROM businesses '
            'LIMIT :limit OFFSET :offset'
        )

        businesses = []
        rows = conn.execute(stmt, {'limit': limit, 'offset': offset})

        # Iterate through the result
        for row in rows:
            row_dict = dict(row._asdict())
            self_link = base_url + '/businesses/' + str(row_dict['business_id'])

            business = {
                'id': row_dict['business_id'],
                'owner_id': row_dict['owner_id'],
                'name': row_dict['name'],
                'street_address': row_dict['street_address'],
                'city': row_dict['city'],
                'state': row_dict['state'],
                'zip_code': row_dict['zip_code'],
                'self': self_link 
            }
            businesses.append(business)

        # Calculate the next page URL
        next_offset = offset + limit
        next_url = None

        if len(businesses) == limit:
            next_url = base_url + '/businesses?offset=' + str(next_offset) + '&limit=' + str(limit)

        response = {
            'entries': businesses,
            'next': next_url
        }

        return response, 200

# Get a business
@app.route('/' + BUSINESSES + '/<int:id>', methods=['GET'])
def get_business(id):
    """
    Allows you to get an existing business.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT * FROM businesses WHERE business_id=:business_id'
            )
        # one_or_none returns at most one result or raise an exception.
        # returns None if the result has no rows.
        row = conn.execute(stmt, parameters={'business_id': id}).one_or_none()
        if row is None:
            return ERROR_NO_BUSINESS, 404
        else:
            business = row._asdict()
            self_link = base_url + '/businesses/' + str(id)

            return ({"id": int(business['business_id']),
                "owner_id": business['owner_id'],
                "name": business['name'], 
                "street_address": business['street_address'], 
                "city": business['city'],
                "state": business['state'],
                "zip_code": int(business['zip_code']),
                "self": self_link}, 200)

# Get all businesses for an owner
@app.route('/owners/<int:id>/' + BUSINESSES, methods=['GET'])
def get_owner_business(id):
    """
    Allows you to get all businesses for a given owner.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT * FROM businesses WHERE owner_id=:owner_id'
            )
        businesses = []
        rows = conn.execute(stmt, parameters={'owner_id': id}).fetchall()

        for row in rows:
            row_dict = dict(row._asdict())
            self_link = base_url + '/businesses/' + str(row_dict['business_id'])

            business = {
                'id': row_dict['business_id'],
                'owner_id': row_dict['owner_id'],
                'name': row_dict['name'],
                'street_address': row_dict['street_address'],
                'city': row_dict['city'],
                'state': row_dict['state'],
                'zip_code': row_dict['zip_code'],
                'self': self_link 
            }
            businesses.append(business)
        
        return businesses, 200

# Update a business
@app.route('/' + BUSINESSES + '/<int:id>', methods=['PUT'])
def put_business(id):
    """
    Allows you to edit an existing business. Returns status 404 if business doesn't exist.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT * FROM businesses WHERE business_id=:business_id'
            )
        row = conn.execute(stmt, parameters={'business_id': id}).one_or_none()
        if row is None:
            return ERROR_NO_BUSINESS, 404
        content = request.get_json()

        if check_attributes(content):
            stmt = sqlalchemy.text(
                'UPDATE businesses '
                'SET name = :name, street_address = :street_address, city = :city,'
                    'state = :state, zip_code = :zip_code '
                'WHERE business_id = :business_id'
            )
            conn.execute(stmt, parameters={'name': content['name'], 
                                    'street_address': content['street_address'], 
                                    'city': content['city'],
                                    'state': content['state'],
                                    'zip_code': content['zip_code'],
                                    'business_id': id})
            conn.commit()

            self_link = base_url + '/businesses/' + str(id)

            return ({'id': id,
                    'owner_id': content['owner_id'],
                    'name': content['name'], 
                    'street_address': content['street_address'], 
                    'city': content['city'],
                    'state': content['state'],
                    'zip_code': content['zip_code'],
                    'self': self_link}, 200)
        return ERROR_MISSING_ATTRIBUTE, 400

# Delete a business
@app.route('/' + BUSINESSES + '/<int:id>', methods=['DELETE'])
def delete_business(id):
    """
    Allows you to delete a business. Returns status 404 if business doesn't exist.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'DELETE FROM businesses WHERE business_id=:business_id'
            )

        result = conn.execute(stmt, parameters={'business_id': id})
        conn.commit()
        # result.rowcount value will be the number of rows deleted.
        # For our statement, the value be 0 or 1 because lodging_id is
        # the PRIMARY KEY
        if result.rowcount == 1:
            return ('', 204)
        else:
            return ERROR_NO_BUSINESS, 404

###########################
# Reviews
###########################
# Create a businesses
@app.route('/' + REVIEWS, methods=['POST'])
def post_reviews():
    """
    Allows you to create a new review.
    Returns status 400 if missing any of the required attributes.
    Returns status 201 and inserts to MySQL database with review.
    """
    content = request.get_json()

    if check_params(content):
        user_id = content.get('user_id')
        business_id = content.get('business_id')

        business_check = get_business(business_id)
        if business_check[1] == 404:
            return ERROR_NO_BUSINESS, 404
        
        if check_duplicate_review(user_id, business_id):
            return ERROR_DUPE, 409

        try:
            # Using a with statement ensures that the connection is always released
            # back into the pool at the end of statement (even if an error occurs)
            with db.connect() as conn:
                # Preparing a statement before hand can help protect against injections.

                if ('review_text' in content):
                    stmt = sqlalchemy.text(
                        'INSERT INTO reviews(user_id, business_id, stars, review_text) '
                        ' VALUES (:user_id, :business_id, :stars, :review_text)'
                    )
                    # connection.execute() automatically starts a transaction
                    conn.execute(stmt, parameters={'user_id': content['user_id'],
                                                'business_id': content['business_id'], 
                                                'stars': content['stars'], 
                                                'review_text': content['review_text']})
                else:
                    stmt = sqlalchemy.text(
                        'INSERT INTO reviews(user_id, business_id, stars) '
                        ' VALUES (:user_id, :business_id, :stars)'
                    )
                    # connection.execute() automatically starts a transaction
                    conn.execute(stmt, parameters={'user_id': content['user_id'],
                                'business_id': content['business_id'], 
                                'stars': content['stars']})

                stmt2 = sqlalchemy.text('SELECT last_insert_id()')
                review_id = conn.execute(stmt2).scalar()
                conn.commit()

        except Exception as e:
            logger.exception(e)
            return ({'Error': 'Unable to create review'}, 500)

        self_link = base_url + '/reviews/' + str(review_id)
        business_link = base_url + '/businesses/' + str(content['business_id'])

        if 'review_text' in content:
            return ({"id": review_id,
                    "user_id": content['user_id'],
                    "business": business_link, 
                    "stars": content['stars'], 
                    "review_text": content['review_text'],
                    "self": self_link}, 201)
        return ({"id": review_id,
            "user_id": content['user_id'],
            "business": business_link, 
            "stars": content['stars'], 
            "review_text": '',
            "self": self_link}, 201)

    return ERROR_MISSING_ATTRIBUTE, 400

# Get a review
@app.route('/' + REVIEWS + '/<int:id>', methods=['GET'])
def get_review(id):
    """
    Allows you to get an existing review.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT * FROM reviews WHERE review_id=:review_id'
            )
        # one_or_none returns at most one result or raise an exception.
        # returns None if the result has no rows.
        row = conn.execute(stmt, parameters={'review_id': id}).one_or_none()
        if row is None:
            return ERROR_NO_REVIEW, 404
        else:
            review = row._asdict()
            self_link = base_url + '/reviews/' + str(id)
            business_link = base_url + '/businesses/' + str(review['business_id'])

            return ({"id": int(review['review_id']),
                "user_id": review['user_id'],
                "business": business_link, 
                "stars": review['stars'], 
                "review_text": review['review_text'],
                "self": self_link}, 200)

# Update a reivew
@app.route('/' + REVIEWS + '/<int:id>', methods=['PUT'])
def put_review(id):
    """
    Allows you to edit an existing review. Returns status 404 if review doesn't exist.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT * FROM reviews WHERE review_id=:review_id'
            )
        row = conn.execute(stmt, parameters={'review_id': id}).one_or_none()
        if row is None:
            return ERROR_NO_REVIEW, 404
        content = request.get_json()

        if 'review_text' in content and 'stars' in content:
            stmt = sqlalchemy.text(
                'UPDATE reviews '
                'SET stars = :stars, review_text = :review_text '
                'WHERE review_id = :review_id'
            )
            conn.execute(stmt, parameters={'stars': content['stars'],
                                    'review_text': content['review_text'],
                                    'review_id': id})
            conn.commit()
        elif 'stars' in content:
            stmt = sqlalchemy.text(
                'UPDATE reviews '
                'SET stars = :stars '
                'WHERE review_id = :review_id'
            )
            conn.execute(stmt, parameters={'stars': content['stars'],
                                    'review_id': id})
            conn.commit()
        else:
            return ERROR_MISSING_ATTRIBUTE, 400
        return get_review(id)

# Delete a review
@app.route('/' + REVIEWS + '/<int:id>', methods=['DELETE'])
def delete_review(id):
    """
    Allows you to delete a review. Returns status 404 if review doesn't exist.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'DELETE FROM reviews WHERE review_id=:review_id'
            )

        result = conn.execute(stmt, parameters={'review_id': id})
        conn.commit()
        # result.rowcount value will be the number of rows deleted.
        # For our statement, the value be 0 or 1 because lodging_id is
        # the PRIMARY KEY
        if result.rowcount == 1:
            return ('', 204)
        else:
            return ERROR_NO_REVIEW, 404

@app.route('/users/<user_id>/' + REVIEWS, methods=['GET'])
def get_user_reviews(user_id):
    """
    Allows you to get all reviews for a given user.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT * FROM reviews WHERE user_id=:user_id'
            )
        reviews = []
        rows = conn.execute(stmt, parameters={'user_id': user_id}).fetchall()

        for row in rows:
            row_dict = dict(row._asdict())
            self_link = base_url + '/reviews/' + str(row_dict['review_id'])
            business_link = base_url + '/businesses/' + str(row_dict['business_id'])

            review = {
                "id": int(row_dict['review_id']),
                "user_id": row_dict['user_id'],
                "business": business_link, 
                "stars": row_dict['stars'], 
                "review_text": row_dict['review_text'],
                "self": self_link}
            reviews.append(review)
        return reviews, 200

###########################
# Helper Functions
###########################
def check_attributes(content):
    if 'owner_id' not in content or content['owner_id'] is None:
        return False
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
    return True

def check_params(content):
    if 'user_id' not in content or content['user_id'] is None:
        return False
    if 'business_id' not in content or content['business_id'] is None:
        return False
    if 'stars' not in content or content['stars'] is None:
        return False
    if 'review_text' not in content or content['review_text'] is None:
        return "No Review"
    return "Yes Review"

def check_duplicate_review(user_id, business_id):
    """
    Checks if there's a duplicate review by looking for user_id in reviews and business_id.
    Returns True if a duplicate review exists, False otherwise.
    """
    with db.connect() as conn:
        stmt = sqlalchemy.text(
            'SELECT * FROM reviews WHERE user_id = :user_id AND business_id = :business_id'
        )
        result = conn.execute(stmt, {'user_id': user_id, 'business_id': business_id}).fetchone()
        if result:
            return True
        return False

if __name__ == '__main__':
    init_db()
    drop_reviews_table(db)
    drop_businesses_table(db)
    create_businesses_table(db)
    create_reviews_table(db)
    app.run(host='0.0.0.0', port=8080, debug=True)
