from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os
import pika
import time
import json
import requests
from threading import Thread

# Database configuration
db_user = os.getenv('POSTGRES_USER')
db_password = os.getenv('POSTGRES_PASSWORD')
db_host = os.getenv('POSTGRES_HOST')
db_port = os.getenv('POSTGRES_PORT')
db_name = os.getenv('POSTGRES_DB')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the Borrow model to store borrow requests
class Borrow(db.Model):
    __tablename__ = 'borrow_requests'

    borrow_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), nullable=False)
    book_id = db.Column(db.String(20), nullable=False)
    date_borrowed = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            "borrow_id": self.borrow_id,
            "student_id": self.student_id,
            "book_id": self.book_id,
            "date_borrowed": self.date_borrowed
        }

# Connect to RabbitMQ
def connect_to_rabbitmq():
    while True:
        try:
            credentials = pika.PlainCredentials(os.getenv('RABBITMQ_DEFAULT_USER'), os.getenv('RABBITMQ_DEFAULT_PASS'))
            connection = pika.BlockingConnection(pika.ConnectionParameters("rabbitmq", 5672, "/", credentials))
            return connection
        except pika.exceptions.AMQPConnectionError:
            print("Waiting for RabbitMQ to become available...")
            time.sleep(5)

# Set up RabbitMQ and create the channel
def setup_rabbitmq_channel():
    connection = connect_to_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue='borrow_book', durable=True)
    return connection, channel

# Initialize global connection and channel
connection, channel = setup_rabbitmq_channel()

# Process the borrow requests
def process_borrow_request(ch, method, properties, body):
    data = json.loads(body)
    student_id = data.get('student_id')
    book_id = data.get('book_id')
    date_borrowed = data.get('date_returned')

    # Ensure the code below runs within the app context
    with app.app_context():
        # Check if the student exists by calling the UserService
        user_response = requests.get(f'http://userservice:5002/users/{student_id}')
        if user_response.status_code != 200:
            print(f"User {student_id} not found.")
            return

        # Check if the book exists by calling the BookService
        book_response = requests.get(f'http://bookservice:5006/books/{book_id}')
        if book_response.status_code != 200:
            print(f"Book {book_id} not found.")
            return

        # Check if the student already borrowed 5 books
        borrowed_books_count = Borrow.query.filter_by(student_id=student_id).count()
        if borrowed_books_count >= 5:
            print(f"Student {student_id} cannot borrow more than 5 books.")
            return

        # Save the borrow request to the database
        borrow_request = Borrow(
            student_id=student_id,
            book_id=book_id,
            date_borrowed=date_borrowed
        )
        db.session.add(borrow_request)
        db.session.commit()
        print(f"Borrow request successfully saved: {borrow_request.to_dict()}")

    # Acknowledge message
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Start consuming messages from the RabbitMQ queue
def consume_messages():
    global channel, connection
    while True:
        try:
            print("Starting message consumption...")
            channel.basic_consume(queue='borrow_book', on_message_callback=process_borrow_request)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print("Lost connection to RabbitMQ. Reconnecting...")
            connection, channel = setup_rabbitmq_channel()

@app.route('/borrow/all/<student_id>', methods=['GET'])
def get_borrowed_books(student_id):
    # Fetch all books borrowed by a given student
    borrow_requests = Borrow.query.filter_by(student_id=student_id).all()

    # If no borrow requests found, return an error response
    if not borrow_requests:
        return jsonify({"error": "This student has not borrowed any books."}), 404

    # Return the list of borrowed books
    return jsonify([borrow_request.to_dict() for borrow_request in borrow_requests]), 200

@app.route('/borrow/return/<student_id>/all', methods=['POST'])
def return_all_books(student_id):
    # Fetch all books currently borrowed by the student
    borrow_requests = Borrow.query.filter_by(student_id=student_id).all()

    # If no borrowed books found, return an error response
    if not borrow_requests:
        return jsonify({"error": "This student has no books to return."}), 404

    # Delete each borrow request from the database
    for borrow_request in borrow_requests:
        db.session.delete(borrow_request)

    # Commit the changes to the database
    db.session.commit()
    return jsonify({"message": "All books have been successfully returned and deleted from the database.."}), 200

@app.route('/borrow/return/<student_id>/<borrow_id>', methods=['POST'])
def return_single_book(student_id, borrow_id):
    # Find the specific borrow request by student_id and book_id
    borrow_request = Borrow.query.filter_by(student_id=student_id, borrow_id=borrow_id).first()

    # If no such borrow request found, return an error response
    if not borrow_request:
        return jsonify({"error": "No borrowed book found for this student with the specified borrow ID."}), 404

    # Delete the borrow request from the database
    db.session.delete(borrow_request)

    # Commit the change to the database
    db.session.commit()
    return jsonify({"message": "Book successfully returned and removed from the database.", "borrow_id": borrow_id}), 200

# Initialize the database (create tables) and start the Flask app
if __name__ == "__main__":
    with app.app_context():
        # Create tables in the database (if not already created)
        db.create_all()

    # Start a separate thread for consuming RabbitMQ messages
    thread = Thread(target=consume_messages)
    thread.daemon = True  # Ensure the thread exits when the main program exits
    thread.start()

    # Start the Flask app
    app.run(host="0.0.0.0", port=5004)
