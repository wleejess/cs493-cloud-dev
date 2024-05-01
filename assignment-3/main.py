# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import logging
import os

from flask import Flask, request

import sqlalchemy

from connect_connector import connect_with_connector

LODGINGS = 'lodgings'
ERROR_NOT_FOUND = {'Error' : 'No lodging with this id exists'}

app = Flask(__name__)

logger = logging.getLogger()

# Sets up connection pool for the app
def init_connection_pool() -> sqlalchemy.engine.base.Engine:
    if os.environ.get('INSTANCE_CONNECTION_NAME'):
        return connect_with_connector()
        
    raise ValueError(
        'Missing database connection type. Please define INSTANCE_CONNECTION_NAME'
    )

# This global variable is declared with a value of `None`
db = None

# Initiates connection to database
def init_db():
    global db
    db = init_connection_pool()

# create 'lodgings' table in database if it does not already exist
def create_table(db: sqlalchemy.engine.base.Engine) -> None:
    with db.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                'CREATE TABLE IF NOT EXISTS lodgings '
                '(lodging_id SERIAL NOT NULL, '
                'name VARCHAR(30) NOT NULL, '
                'description VARCHAR(100) NOT NULL, '
                'price DECIMAL (6,2) NOT NULL, '
                'PRIMARY KEY (lodging_id) );'
            )
        )
        conn.commit()


@app.route('/')
def index():
    return 'Please navigate to /lodgings to use this API'

# Create a lodging
@app.route('/' + LODGINGS, methods=['POST'])
def post_lodgings():
    content = request.get_json()

    try:
        # Using a with statement ensures that the connection is always released
        # back into the pool at the end of statement (even if an error occurs)
        with db.connect() as conn:
            # Preparing a statement before hand can help protect against injections.
            stmt = sqlalchemy.text(
                'INSERT INTO lodgings(name, description, price) '
                ' VALUES (:name, :description, :price)'
            )
            # connection.execute() automatically starts a transaction
            conn.execute(stmt, parameters={'name': content['name'], 
                                        'description': content['description'], 
                                        'price': content['price']})
            # The function last_insert_id() returns the most recent value
            # generated for an `AUTO_INCREMENT` column when the INSERT 
            # statement is executed
            stmt2 = sqlalchemy.text('SELECT last_insert_id()')
            # scalar() returns the first column of the first row or None if there are no rows
            lodging_id = conn.execute(stmt2).scalar()
            # Remember to commit the transaction
            conn.commit()

    except Exception as e:
        logger.exception(e)
        return ({'Error': 'Unable to create lodging'}, 500)

    return ({'lodging_id': lodging_id,
             'name': content['name'], 
             'description': content['description'], 
             'price': content['price']}, 201)

# Get all lodgings
@app.route('/' + LODGINGS, methods=['GET'])
def get_lodgings():
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT lodging_id, name, price, description FROM lodgings'
            )
        
        lodgings = []
        rows = conn.execute(stmt)
        # Iterate through the result
        for row in rows:
            # Turn row into a dictionary
            lodging = row._asdict()
            lodging['price'] = float(lodging['price'])
            lodgings.append(lodging)

        return lodgings

# Get a lodging
@app.route('/' + LODGINGS + '/<int:id>', methods=['GET'])
def get_lodging(id):
    with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT lodging_id, name, price, description FROM lodgings WHERE lodging_id=:lodging_id'
            )
        # one_or_none returns at most one result or raise an exception.
        # returns None if the result has no rows.
        row = conn.execute(stmt, parameters={'lodging_id': id}).one_or_none()
        if row is None:
            return ERROR_NOT_FOUND, 404
        else:
            lodging = row._asdict()
            lodging['price'] = float(lodging['price'])
            return lodging

# Update a lodging
@app.route('/' + LODGINGS + '/<int:id>', methods=['PUT'])
def put_lodging(id):
     with db.connect() as conn:
        stmt = sqlalchemy.text(
                'SELECT lodging_id, name, price, description FROM lodgings WHERE lodging_id=:lodging_id'
            )
        row = conn.execute(stmt, parameters={'lodging_id': id}).one_or_none()
        if row is None:
            return ERROR_NOT_FOUND, 404
        else:
            content = request.get_json()
            stmt = sqlalchemy.text(
                'UPDATE lodgings '
                'SET name = :name, description = :description, price = :price '
                'WHERE lodging_id = :lodging_id'
            )
            conn.execute(stmt, parameters={'name': content['name'], 
                                    'description': content['description'], 
                                    'price': content['price'],
                                    'lodging_id': id})
            conn.commit()
            return {'lodging_id': id, 
                    'name':  content['name'],
                    'description': content['description'], 
                    'price': content['price']}

# Delete a lodging
@app.route('/' + LODGINGS + '/<int:id>', methods=['DELETE'])
def delete_lodging(id):
     with db.connect() as conn:
        stmt = sqlalchemy.text(
                'DELETE FROM lodgings WHERE lodging_id=:lodging_id'
            )
        
        result = conn.execute(stmt, parameters={'lodging_id': id})
        conn.commit()
        # result.rowcount value will be the number of rows deleted.
        # For our statement, the value be 0 or 1 because lodging_id is
        # the PRIMARY KEY
        if result.rowcount == 1:
            return ('', 204)
        else:
            return ERROR_NOT_FOUND, 404            
            

if __name__ == '__main__':
    init_db()
    create_table(db)
    app.run(host='0.0.0.0', port=8080, debug=True)
