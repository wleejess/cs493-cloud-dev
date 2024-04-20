import datetime

from flask import Flask, render_template, request, url_for, redirect, jsonify
from google.cloud import datastore

app = Flask(__name__)
client = datastore.Client()

BUSINESSES = 'businesses'
REVIEWS = 'reviews'
ERROR_MISSING_ATTRIBUTE = {"Error": "The request body is missing at least one of the required attributes"}
ERROR_NO_REVIEW = {"Error": "No review with this review_id exists"}
ERROR_NO_BUSINESS = {"Error": "No business with this business_id exists"}
ERROR_DUPE = {"Error": "You have already submitted a review for this business. You can update your previous review, or delete it and submit a new review"}

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/index')
def home():
    return render_template("/index.html")

@app.route('/' + BUSINESSES, methods=['POST', 'GET'])
def businesses():
    if request.method == 'POST':
        content = request.get_json()

        if check_attributes(content):
            new_key = client.key(BUSINESSES)
            new_business = client.entity(key=new_key)
            new_business.update({
                'owner_id': content['owner_id'],
                'name': content['name'],
                'street_address': content['street_address'],
                'city': content['city'],
                'state': content['state'],
                'zip_code': content['zip_code']
            })
            client.put(new_business)
            new_business['id'] = new_business.key.id
            return (new_business, 201)
        else:
            return ERROR_MISSING_ATTRIBUTE, 400
    
    if request.method == 'GET':        
        query = client.query(kind=BUSINESSES)
        results = list(query.fetch())
        for r in results:
            r['id'] = r.key.id
        return results

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

@app.route('/' + BUSINESSES + '/<int:id>', methods=['GET'])
def get_business(id):
    business_key = client.key(BUSINESSES, id)
    business = client.get(key=business_key)
    if business is None:
        return ERROR_NO_BUSINESS, 404
    else:
        business['id'] = business.key.id
        return business

@app.route('/' + BUSINESSES + '/<int:id>', methods=['PUT'])
def put_business(id):
    content = request.get_json()
    business_key = client.key(BUSINESSES, id)
    business = client.get(key=business_key)
    if business is None:
        return ERROR_NO_BUSINESS, 404
    else:
        if check_attributes(content):
            business.update({
                'owner_id': content['owner_id'],
                'name': content['name'],
                'street_address': content['street_address'],
                'city': content['city'],
                'state': content['state'],
                'zip_code': content['zip_code']
            })
            client.put(business)
            business['id'] = business.key.id
            return business
        else:
            return ERROR_MISSING_ATTRIBUTE, 400
    
@app.route('/' + BUSINESSES + '/<int:id>', methods=['DELETE'])
def delete_business(id):
    business_key = client.key(BUSINESSES, id)
    business = client.get(key=business_key)
    if business is None:
        return ERROR_NO_BUSINESS, 404
    else:
        client.delete(business_key)
        return ('', 204)

@app.route('/owners/<owner_id>/' + BUSINESSES, methods=['GET'])
def get_owner_business(owner_id):
    query = client.query(kind=BUSINESSES)
    query_params = request.args

    if owner_id is not None:
        query.add_filter('owner_id', '=', int(owner_id))
    results = list(query.fetch())
    for r in results:
        r['id'] = r.key.id
    print(owner_id, results)
    return results

@app.route('/' + REVIEWS, methods=['POST'])
def reviews():
    if request.method == 'POST':
        content = request.get_json()

        if check_params(content):
            user_id = content.get('user_id')
            business_id = content.get('business_id')

            business_key = client.key(BUSINESSES, business_id)
            business = client.get(key=business_key)
            if business is None:
                return ERROR_NO_BUSINESS, 404

            existing_review_query = client.query(kind=REVIEWS)
            existing_review_query.add_filter('user_id', '=', user_id)
            existing_review_query.add_filter('business_id', '=', business_id)
            existing_reviews = list(existing_review_query.fetch())
            if existing_reviews:
                return ERROR_DUPE, 409

            new_key = client.key(REVIEWS)
            new_review = client.entity(key=new_key)

            if check_params(content) == "Yes Review":
                new_review.update({
                    'user_id': content['user_id'],
                    'business_id': content['business_id'],
                    'stars': content['stars'],
                    'review_text': content['review_text'],
                })
            elif check_params(content) == "No Review":
                new_review.update({
                    'user_id': content['user_id'],
                    'business_id': content['business_id'],
                    'stars': content['stars'],
                })
            client.put(new_review)
            new_review['id'] = new_review.key.id
            return (new_review, 201)
        else:
            return ERROR_MISSING_ATTRIBUTE, 400

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

@app.route('/' + REVIEWS + '/<int:id>', methods=['GET'])
def get_review(id):
    review_key = client.key(REVIEWS, id)
    review = client.get(key=review_key)
    
    if review is None:
        return ERROR_NO_REVIEW, 404

    business_key = client.key(BUSINESSES, review['business_id'])
    business = client.get(key=business_key)
    
    if business is None:
        return ERROR_NO_REVIEW, 404

    review['id'] = review.key.id
    return review

@app.route('/' + REVIEWS + '/<int:id>', methods=['PUT'])
def put_review(id):
    content = request.get_json()
    review_key = client.key(REVIEWS, id)
    review = client.get(key=review_key)
    if review is None:
        return ERROR_NO_REVIEW, 404
    else:
        if ('stars' in content) and ('review_text' in content):
            review.update({
                    'stars': content['stars'],
                    'review_text': content['review_text'],
                })
            client.put(review)
            review['id'] = review.key.id
            return review
        elif ('stars' in content):
            review.update({
                    'stars': content['stars'],
                })
            client.put(review)
            review['id'] = review.key.id
            return review
        else:
            return ERROR_MISSING_ATTRIBUTE, 400

@app.route('/' + REVIEWS + '/<int:id>', methods=['DELETE'])
def delete_review(id):
    review_key = client.key(REVIEWS, id)
    review = client.get(key=review_key)
    if review is None:
        return ERROR_NO_REVIEW, 404
    else:
        client.delete(review_key)
        return ('', 204)

@app.route('/users/<user_id>/' + REVIEWS, methods=['GET'])
def get_user_reviews(user_id):
    query = client.query(kind=REVIEWS)
    query_params = request.args

    if user_id is not None:
        query.add_filter('user_id', '=', int(user_id))
    results = list(query.fetch())
    for r in results:
        r['id'] = r.key.id
    return results

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)



