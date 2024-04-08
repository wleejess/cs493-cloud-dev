import datetime

from flask import Flask, render_template, request, url_for
from google.cloud import datastore

app = Flask(__name__)
datastore_client = datastore.Client()

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/business.html', methods=['POST', 'GET'])
def business():
    if request.method == 'POST':
        # add company
        if request.form.get("addBusiness"):
            # do something to add the business
            pass
        return redirect("/business.html")
    
    if request.method == 'GET':        
        # access datastore to get all businesses
        return render_template("business.html")
    
@app.route('/business/delete/<int:id>')
def delete_business(id):
    # datastore to delete a business
    return redirect("/business.html")

@app.route('/business/edit/<int:id>', methods=['POST', 'GET'])
def edit_business(id):
    if request.method == 'GET':
        # do something to get the business
        return render_template("edit_business.html", data=data)
    
    if request.method == 'POST':
        # edit business
        if request.form.get("updateBusiness"):
            # retrieve user form input
            pass
        return redirect("/business.html")

@app.route('/reviews.html', methods=['POST', 'GET'])
def reviews():
    if request.method == 'POST':
        # add company
        if request.form.get("addBusiness"):
            # do something to add the reviews
            pass
        return redirect("/reviews.html")
    
    if request.method == 'GET':        
        # access datastore to get all reviews
        return render_template("reviews.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)



