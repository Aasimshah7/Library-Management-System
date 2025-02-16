# Library Management System

## Overview
This project is a microservices-based **Library Management Application** designed for efficient book borrowing and management. It includes **UserService, BookService, and BorrowService**, with **RabbitMQ** handling asynchronous messaging. The application is containerized using **Docker** and deployed on **Kubernetes** for scalability and fault tolerance.

## Features
- **User Management:** Add, update, retrieve, and delete users.
- **Book Management:** Add, update, retrieve, and delete books.
- **Borrowing System:** Borrow and return books with validation.
- **Asynchronous Communication:** Uses RabbitMQ for handling borrow requests.
- **Containerization:** Services are built with Docker and managed using Kubernetes.

## Services
1. **UserService** – Handles user-related operations.
2. **BookService** – Manages book records.
3. **BorrowService** – Tracks borrowed books and returns.
4. **RabbitMQ** – Facilitates communication between services.

## Deployment
The application can be deployed using **Kubernetes**. All necessary service definitions are included in Kubernetes manifests.

### **Steps to Run Locally**
1. Clone the repository:
   ```sh
   git clone https://github.com/Aasimshah7/Library-Management-System.git
   cd Library-Management-System
   ```
2. Build and run services using Docker Compose:
   ```sh
   docker-compose up --build
   ```
3. Deploy to Kubernetes:
   ```sh
   kubectl apply -f .
   ```
4. Port forward the services:
   ```sh
   kubectl port-forward svc/userservice 5002:5002
   kubectl port-forward svc/bookservice 5006:5006
   kubectl port-forward svc/borrowservice 5004:5004
   ```

## API Endpoints
### **UserService**
- `POST /users/add` – Create a new user.
- `GET /users/{studentid}` – Retrieve a user by ID.
- `GET /users/all` – Get all users.
- `PUT /users/{studentid}` – Update user details.
- `DELETE /users/{studentid}` – Delete a user.

### **BookService**
- `POST /books/add` – Add a new book.
- `GET /books/{bookid}` – Retrieve a book by ID.
- `GET /books/all` – Get all books.
- `PUT /books/{bookid}` – Update book details.
- `DELETE /books/{bookid}` – Delete a book.

### **BorrowService**
- `POST /users/borrow/request` – Borrow a book.
- `GET /borrow/all/{student_id}` – View borrowed books.
- `POST /borrow/return/{student_id}/{borrow_id}` – Return a book.
- `POST /borrow/return/{student_id}/all` – Return all books.

## Technologies Used
- **Python, Flask** – API development
- **PostgreSQL** – Database
- **RabbitMQ** – Messaging system
- **Docker, Docker Compose** – Containerization
- **Kubernetes** – Deployment and scaling

