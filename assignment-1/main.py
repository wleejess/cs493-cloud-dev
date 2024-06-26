""" 
Main Python file to render web pages using flask
""" 

import datetime

from flask import Flask, render_template, request
from google.cloud import datastore

app = Flask(__name__)
datastore_client = datastore.Client()

@app.route("/", methods=["GET", "POST"])
def root():
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            return render_template("result.html", name=name)
        else:
            return "Name not provided."

    return render_template("index.html")

if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)



