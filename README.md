# cs493-cloud-dev
A series of assignments from my course at Oregon State University. In this course, I've had the opportunity to learn more about what goes into Cloud App Development, as well as get hands on experience in:
1. Designing and implementing RESTful APIs using appropriate HTTP methods to access API resources.
2. Evaluating different approaches to representing data in API requests and responses, and for alerting users of errors.
3. Employ secure mechanisms for authenticating users, and authorizing the use of specific endpoints.
4. Create a publicly available cloud API.
5. Use modern tools and techniques for storing API data, and to replicate and synchronize data to ensure data safety and consistency.

### testing with postman / newman
Postman (API client for creating, sharing, and testing APIs), and Newman (command-line collection runner for Postman) was used to test the RESTful APIs.
<img width="1256" alt="image" src="https://github.com/wleejess/cs493-cloud-dev/assets/29618012/c8946435-145a-4937-a76f-d17f855d9c64">

### assignments 1, 2, 3
These initial assignments cover setting up a basic application and **deploying it on Google App Engine using Python and Flask.** Assignments also cover the **design, implementation, and testing of REST APIs** deployed on the cloud. Assignment 2 uses **Google's Cloud Datastore** to store the entities, "Businesses" and "Reviews." Assignment 3 on the other hand, will use **MySQL**, and also implement links and pagination. Additionally, the app will be deployed using a Docker container on a virtual machine using Goolge Computer Engine, instead of Google App Engine.

### assignments 4 & 5
For Assignment 4, a simple client was implemented. A user is shown a 'Welcome' page with a link that sends a request to the **Google OAuth 2.0 endpoint.** From there, the program should handle everything from sending requests, receiving redirects + access codes + access tokens, sending POST requests, and displaying 'User Information' afterwards. Assignment 5 was the implementation of an application that **generates JWTs** and also contains REST APIs, in which some resources are protected and require valid JWTs for making requests. 

### assignment 6 (portfolio project)
In this final assignment / portfolio project, I implemented a complete RESTful API for an application called Tarpaulin (a lightweight course management tool that's an 'alternative' to Canvas'). There are (3) types of users: admin, instructor, and student. Depending on the resource requested, only users with certain roles will have access to the endpoints.

<img width="1130" alt="image" src="https://github.com/wleejess/cs493-cloud-dev/assets/29618012/bf0bba71-72e8-41f8-8145-70f5974c501b">

