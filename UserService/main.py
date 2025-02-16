from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os
import pika
import time
import json
from datetime import datetime, date

# Database configurations
db_user = os.getenv('POSTGRES_USER')
db_password = os.getenv('POSTGRES_PASSWORD')
db_host = os.getenv('POSTGRES_HOST')
db_port = os.getenv('POSTGRES_PORT')
db_name = os.getenv('POSTGRES_DB')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
print("Database URI:", app.config['SQLALCHEMY_DATABASE_URI'])

db = SQLAlchemy(app)

def connect_to_rabbitmq():
    while True:
        try:
            credentials = pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER'), os.getenv('RABBITMQ_DEFAULT_PASS'))
            connection = pika.BlockingConnection(pika.ConnectionParameters("rabbitmq", 5672, "/", credentials, heartbeat=60))
            channel = connection.channel()
            channel.queue_declare(queue='borrow_book', durable=True)
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print("Waiting for RabbitMQ to become available...")
            time.sleep(5)

# Initialize RabbitMQ connection and channel
connection, channel = connect_to_rabbitmq()

class User(db.Model):
    __tablename__ = 'users'

    studentid = db.Column(db.String(20), primary_key=True)
    firstname = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def to_dict(self):
        return {
            "studentid": self.studentid,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "email": self.email
        }
with app.app_context():
    db.create_all()


# CREATE users
@app.route('/users/add', methods=['POST'])
def create_user():
    data = request.json
    user = User(
        studentid=data['studentid'],
        firstname=data['firstname'],
        lastname=data['lastname'],
        email=data['email']
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


# READ all users
@app.route('/users/all', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200


# READ a single user by ID
@app.route('/users/<studentid>', methods=['GET'])
def get_user(studentid:str):
    user = User.query.get(studentid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200


# UPDATE a user by student_id
@app.route('/users/<studentid>', methods=['PUT'])
def update_user(studentid:str):
    user = User.query.get(studentid)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json
    if 'firstname' in data:
        user.firstname = data['firstname']
    if 'lastname' in data:
        user.lastname = data['lastname']
    if 'email' in data:
        # Check if new email already exists for another user
        if User.query.filter(User.email == data['email'], User.studentid != studentid).first():
            return jsonify({"error": "Email already exists"}), 400
        user.email = data['email']
    db.session.commit()
    return jsonify(user.to_dict()), 200


# DELETE a user by student_id
@app.route('/users/<studentid>', methods=['DELETE'])
def delete_user(studentid:str):
    user = User.query.get(studentid)
    if not user:
        return jsonify({"error": "User not found"}), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully"}), 200

@app.route('/users/borrow/request', methods=['POST'])
def borrow_book():
    global connection, channel

    data = request.get_json()

    # Define the required fields and their types
    required_fields = {'student_id': str, 'book_id': str, 'date_returned': str}

    # Validate that all required fields are present
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'error': f'Missing fields: {", ".join(missing_fields)}'}), 400

    # Validate the types of the fields
    for field, field_type in required_fields.items():
        if not isinstance(data.get(field), field_type):
            return jsonify({'error': f'Invalid type for {field}. Expected {field_type.__name__}'}), 400

    try:
        # Ensure the channel is open, if not, reconnect
        if not channel.is_open:
            print("Channel is closed. Reconnecting...")
            connection, channel = connect_to_rabbitmq()

        # Publish the message to RabbitMQ
        channel.basic_publish(
            exchange='',
            routing_key='borrow_book',
            body=json.dumps(data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make the message persistent
            )
        )
        print(f"Message published to queue: {data}")

    except Exception as e:
        print("Exception occurred:", e)
        traceback.print_exc()  # This will print the traceback to the logs
        return jsonify({"error": "An unexpected error occurred"}), 500

    return jsonify({"message": "Book borrow request successfully sent"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
