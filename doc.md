# Project Documentation

# Table of Contents

- [1. Introduction](#1-introduction)
- [2. System Architecture](#2-system-architecture)
  - [2.1. Overview](#21-overview)
  - [2.2. Architectural Diagram](#22-architectural-diagram)
- [3. Components](#3-components)
  - [3.1. API Gateway (NGINX)](#31-api-gateway-nginx)
  - [3.2. User Manager Microservice](#32-user-manager-microservice)
  - [3.3. Data Collector Microservice](#33-data-collector-microservice)
  - [3.4. Alert System Service](#34-alert-system-service)
  - [3.5. Alert Notifier System Service](#35-alert-notifier-system-service)
- [4. Implementation Choices](#4-implementation-choices)
  - [4.1. Coding Standards](#41-coding-standards)
- [5. Database Schema](#5-database-schema)
  - [5.1. User Manager DB](#51-user-manager-db)
  - [5.2. Data Collector DB](#52-data-collector-db)
- [6. Setup and Execution](#6-setup-and-execution)
  - [6.1. Prerequisites](#61-prerequisites)
  - [6.2. Configuration](#62-configuration)
  - [6.3. SSL Certificate Generation](#63-ssl-certificate-generation)
  - [6.4. Running the Application](#64-running-the-application)
  - [6.5. Testing with Postman](#65-testing-with-postman)
- [7. At-Most-Once Semantics (Idempotency)](#7-at-most-once-semantics-idempotency)
  - [7.1. Implementation Details](#71-implementation-details)
  - [7.2. How to Test with Postman](#72-how-to-test-with-postman)
    - [Scenario 1: Successful First Request](#scenario-1-successful-first-request)
    - [Scenario 2: Repeated Request (Same Key)](#scenario-2-repeated-request-same-key)
    - [Scenario 3: Creating a User That Already Exists (New Key)](#scenario-3-creating-a-user-that-already-exists-new-key)
    - [Scenario 4: Request Without Idempotency Key](#scenario-4-request-without-idempotency-key)
- [8. Asynchronous Notification Flow](#8-asynchronous-notification-flow)

## 1. Introduction

This document provides a detailed overview of a distributed systems project, which consists of a Dockerized, microservices-based application. The system is designed to manage user data, collect flight information from the OpenSky Network, and provide users with real-time, threshold-based alerts via Telegram.

The architecture is composed of four main microservices, an API Gateway, and a message broker:

*   **User Manager**: Responsible for handling user registration, deletion, and management of user data, including Telegram chat information.
*   **Data Collector**: Responsible for fetching flight data from the OpenSky Network based on user interests (including alert thresholds), storing it, and providing processed data through its API. It is also a Kafka producer.
*   **Alert System**: A Kafka consumer and producer that contains the business logic for checking if flight data crosses user-defined thresholds.
*   **Alert Notifier System**: A Kafka consumer that sends notifications to users via a Telegram Bot.

The project emphasizes a clean, resilient, and scalable architecture, separation of concerns, and robust inter-service communication utilizing patterns like asynchronous messaging, and Circuit Breaker.

## 2. System Architecture

### 2.1. Overview

The architecture follows a microservices pattern. An **NGINX API Gateway** serves as the single entry point for all external traffic, handling SSL termination and routing requests to the appropriate backend services.

The services themselves are decoupled via an **Apache Kafka** message broker, which orchestrates the asynchronous notification workflow, making the system more resilient and scalable. Internal cross-service communication for synchronous requests (like user validation) is handled efficiently via **gRPC**. Each microservice has its own dedicated PostgreSQL database, ensuring loose coupling and data isolation.

### 2.2. Architectural Diagram

![Architectural Diagram](architecture.png)

## 3. Components

### 3.1. API Gateway (NGINX)
*   **Purpose**: To act as a reverse proxy, providing a single, unified, and secure entry point for the entire system. It handles SSL/TLS termination, encrypting all external traffic.
*   **Routing**: Routes requests based on URL prefixes:
    *   `https://localhost/user-manager/*` is routed to the `user-manager` service.
    *   `https://localhost/data-collector/*` is routed to the `data-collector` service.

### 3.2. User Manager Microservice

*   **Purpose**: To manage user information, including creation, deletion, retrieval of user data, and Telegram notification details.

*   **API Endpoints** (accessed via `/user-manager/` prefix):
    *   `GET /ping`: A health check endpoint.
    *   `POST /users`: Creates a new user.
        *   **Request Body**: `{"email": "...", "first_name": "...", "last_name": "...", "tax_code": "...", "iban": "..."}`
        *   **Response**: `{"message": "User created successfully"}`
    *   `GET /users`: Retrieves a list of all users.
    *   `GET /users/<email>`: Retrieves a single user by email.
    *   `DELETE /users/<email>`: Deletes a user by email.
    *   `POST /users/telegram`: Associates a numeric Telegram Chat ID with a user's email.
        *   **Request Body**: `{"email": "...", "telegram_chat_id": "..."}`

*   **gRPC Service**:
    *   **Service**: `UserService`
    *   **Method**: `CheckUserExists(UserRequest) returns (UserResponse)`
        *   **Description**: Checks if a user with the given email exists in the database. Called by the `Data Collector`.

### 3.3. Data Collector Microservice

*   **Purpose**: To collect flight data based on user interests, store it, and provide endpoints for data retrieval and analysis. It runs a background job to periodically fetch data from the OpenSky Network.

*   **API Endpoints**:
    *   `GET /ping`: A health check endpoint.
    *   `POST /interests`: Adds a new airport interest for a user. Accepts optional `high_value` and `low_value` fields.
    *   `PUT /interests`: Updates `high_value` and `low_value` for an existing interest.
    *   `DELETE /interests`: Removes an airport interest for a user.
    *   `GET /interests/<email>`: Retrieves all airport interests for a user.
    *   `GET /flights/<airport_code>`: Retrieves flights for a specific airport.
    *   `GET /flights/average/<icao>`: Calculates the average number of flights per day for an airport.
    *   `GET /flights/last/<icao>`: Returns the most recent flight recorded for an airport.

*   **Circuit Breaker**: All calls to the OpenSky Network API are wrapped in a Circuit Breaker (using `pybreaker`). If the API fails 5 consecutive times, the circuit opens for 60 seconds to allow the external service to recover.

*   **Kafka Producer**: After fetching flight data, it produces a message to the `to-alert-system` Kafka topic for each relevant user interest.

*   **gRPC Service**:
    *   **Service**: `DataCollectorService`
    *   **Method**: `DeleteUserInterests(UserRequest) returns (DeleteInterestsResponse)`
        *   **Description**: Deletes all interests associated with a user's email. Called by the `User Manager`.

### 3.4. Alert System Service
*   **Architectural Role**: A lightweight, standalone stream processing service. It does not expose any APIs and its sole purpose is to apply business logic to the stream of data produced by the `data-collector`.
*   **Functionality**:
    *   Acts as a Kafka **consumer**, listening to the `to-alert-system` topic.
    *   For each message, it compares the `flight_count` with the user's `high_value` and `low_value`.
    *   If a threshold is crossed, it acts as a Kafka **producer**, sending a formatted alert message to the `to-notifier` topic.

### 3.5. Alert Notifier System Service
*   **Architectural Role**: A standalone service responsible for the final step of the notification pipeline: dispatching messages to the user.
*   **Functionality**:
    *   Acts as an asynchronous Kafka **consumer** (using `aiokafka`), listening to the `to-notifier` topic.
    *   Upon receiving an alert, it **connects directly to the `user-manager`'s PostgreSQL database** to retrieve the `telegram_chat_id` for the user's email.
    *   It uses the Telegram Bot API to send the final alert message to the user.
*   **Design Note**: For simplicity in this project, this service queries another service's database directly. In a stricter, more complex microservice architecture, this could be replaced by an API call to the `User Manager` to further decouple the services.


## 4. Implementation Choices

*   **Frameworks**: **Flask** is used for the `user-manager` and `data-collector` APIs. It was chosen as the web framework for its lightweight nature, simplicity, and extensive documentation. It provides the necessary tools to build RESTful APIs without imposing a rigid structure, which is well-suited for microservices development.
*   **API Gateway**: **NGINX** is used as a reverse proxy and SSL termination point.
*   **Message Broker**: **Apache Kafka** is used for asynchronous messaging.
*   **Resilience**: **PyBreaker** is used to implement the Circuit Breaker pattern.
*   **Async**: **AIOKafka** and **Asyncio** are used in the `alert-notifier-system` for efficient, non-blocking I/O.
*   **ORM**: **SQLAlchemy** is used as the Object-Relational Mapper (ORM). It offers a powerful and flexible way to interact with the relational database, abstracting away the SQL queries and allowing developers to work with Python objects. Its declarative base and session management are well-suited for the application's needs.
*   **Inter-service Communication**: **gRPC** was chosen for communication between the `User Manager` and `Data Collector`. Its use of Protocol Buffers allows for a clear, contract-first definition of services and messages, ensuring type safety and high performance, which are critical in a distributed environment.
*   **Containerization**: **Docker** and **Docker Compose** are used to containerize the application. This approach provides a consistent and reproducible environment for development, testing, and deployment. It simplifies dependency management and ensures that the application runs the same way on any machine.



### 4.1 Coding Standards

The Python code in this project adheres to the **PEP 8** style guide to ensure consistency and readability. All docstrings for modules, classes, and functions are written to comply with the **PEP 257** standard, providing clear and comprehensive documentation directly within the code.

## 5. Database Schema

### 5.1. User Manager DB

*   **`users` table**:
    *   `email` (String, Primary Key)
    *   `first_name` (String)
    *   `last_name` (String)
    *   `tax_code` (String, Optional, Unique)
    *   `iban` (String, Optional)
    *   `telegram_chat_id` (String, Optional, Unique)

*   **`idempotency_keys` table**:
    *   `key` (String, Primary Key) - The unique idempotency key provided by the client.
    *   `status` (String) - Current status of the request (`in-progress`, `completed`).
    *   `created_at` (DateTime) - Timestamp of when the key was created.
    *   `response_code` (Integer, Optional) - HTTP status code of the cached response.
    *   `response_body` (Text, Optional) - JSON body of the cached response.
    *   `user_email` (String) - Email of the user associated with the request (not a foreign key).

### 5.2. Data Collector DB

*   **`user_interests` table**:
    *   `id` (Integer, Primary Key)
    *   `user_email` (String)
    *   `airport_code` (String)
    *   `high_value` (Integer, Optional)
    *   `low_value` (Integer, Optional)
*   **`flight_data` table**:
    *   `id` (Integer, Primary Key)
    *   `icao24` (String)
    *   `first_seen` (DateTime)
    *   `est_departure_airport` (String, Optional)
    *   `last_seen` (DateTime)
    *   `est_arrival_airport` (String, Optional)
    *   `callsign` (String, Optional)
    *   `est_departure_airport_horiz_distance` (Integer, Optional)
    *   `est_departure_airport_vert_distance` (Integer, Optional)
    *   `est_arrival_airport_horiz_distance` (Integer, Optional)
    *   `est_arrival_airport_vert_distance` (Integer, Optional)
    *   `departure_airport_candidates_count` (Integer, Optional)
    *   `arrival_airport_candidates_count` (Integer, Optional)

## 6. Setup and Execution

### 6.1. Prerequisites

*   Docker
*   Docker Compose (v1 or v2)
*   OpenSSL (for generating SSL certificate)

### 6.2. Configuration

Modify the `.env` file in the project's root directory to add your secret credentials.

```
# OpenSky Network API Credentials
OPEN_SKY_CLIENT_ID=your_api_client_id
OPEN_SKY_CLIENT_SECRET=your_api_client_secret

# Telegram Bot Token (from BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
...
```

### 6.3. SSL Certificate Generation

For HTTPS to work locally, you need to generate a self-signed certificate. The private key and certificate files are ignored by Git and will not be shared. 

Run the following command from the project's root directory:
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx-selfsigned.key \
  -out nginx-selfsigned.crt \
  -subj "/C=IT/ST=Italy/L=CT/O=Uni/OU=Dev/CN=localhost"
```
This will create the necessary `.key` and `.crt` files in the **project root directory**. You will then need to **move** these files into the `nginx/ssl/` directory (i.e., `mv nginx-selfsigned.key nginx/ssl/` and `mv nginx-selfsigned.crt nginx/ssl/`). For collaborators, if you do not wish to generate them, you may need to obtain these files from the project owner.

### 6.4. Running the Application

You can run the entire application using Docker Compose.

**Using Docker Compose v1:**
```bash
sudo docker-compose up --build -d
```

**Using Docker Compose v2:**
```bash
sudo docker compose up --build -d
```

The services are accessible through the API Gateway at **`https://localhost`**. HTTP traffic on `http://localhost:8080` is automatically redirected to HTTPS.

**Note**: Since a self-signed certificate is used, you must accept the browser's security warning or use the `-k` flag with `curl`.

### 6.5. Testing with Postman

The repository includes a Postman collection file: `DSBD.postman_collection.json`. You can import this file into Postman to get a pre-configured set of requests for all the main API endpoints, making it easy to test the system's functionality. Remember to update the base URL to `https://localhost`.

## 7. At-Most-Once Semantics (Idempotency)

To ensure robustness and prevent duplicate data processing in case of network failures or client retries, the system implements an "at-most-once" delivery guarantee for all state-changing operations in the `User Manager` service (`POST /users` and `DELETE /users/<email>`).

### 7.1. Implementation Details

The idempotency logic is handled at the application layer using a combination of a request header and a dedicated database table.

1.  **Idempotency-Key Header**: The client must send a unique identifier for each state-changing request in an `Idempotency-Key` HTTP header.

2.  **`idempotency_keys` Table**: A table in the `user_manager_db` is used to store the status and result of each request. The table includes the idempotency key, the status of the request (`in-progress` or `completed`), and the response body and status code that were originally returned.

3.  **Execution Flow**:
    *   When a request with an `Idempotency-Key` arrives, the server first checks the `idempotency_keys` table.
    *   **If the key exists and its status is `completed`**, the server immediately returns the stored response without re-processing the request.
    *   **If the key exists and its status is `in-progress`**, it means a concurrent request with the same key is being processed. The server returns a `409 Conflict` error to prevent a race condition.
    *   **If the key does not exist**, the server creates a new entry in the table with the status `in-progress`, executes the business logic (e.g., creates the user), and then updates the entry with the status `completed` along with the final response body and code.

This mechanism ensures that an operation is performed at most once, even if the client sends the same request multiple times.

### 7.2. How to Test with Postman

Here is a detailed guide on how to test the idempotency implementation.

#### Initial Setup

1.  **`Content-Type` Header**: For `POST` requests, set the `Content-Type` header to `application/json`.
2.  **`Idempotency-Key` Header**: Add an `Idempotency-Key` header to your `POST /user-manager/users` and `DELETE /user-manager/users/<email>` requests.

#### Scenario 1: Successful First Request

1.  **Action**:
    *   Create a `POST /users` request to `https://localhost/user-manager/users`.
    *   In **Headers**, set `Idempotency-Key` to `{{$guid}}`. This Postman variable generates a new GUID for each request.
    *   In the **Body**, provide the user's JSON data.
    *   Send the request.
2.  **Expected Result**: A `201 Created` response. The user and the idempotency key are stored in the database.

#### Scenario 2: Repeated Request (Same Key)

1.  **Action**:
    *   Take the previous request. **Do not change the `Idempotency-Key`**. If you used `{{$guid}}`, copy the value that was actually sent and paste it as a static value or repeat the **scenario 1** forcing a key, for example: `3f9d2e1b-8c4a-4d6f-b1e2-5a7f8c2d9e4a`.
    *   Send the request again.
2.  **Expected Result**: An immediate `201 Created` response. The server returns the cached response, and no new user is created. You will not see a "duplicate key" error from the database in the service logs.

#### Scenario 3: Creating a User That Already Exists (New Key)

1.  **Action**:
    *   Create a `POST /users` request for a user that already exists.
    *   Use a **new** `Idempotency-Key` (e.g., use `{{$guid}}` again).
    *   Send the request.
2.  **Expected Result**: A `409 Conflict` response. The server attempts to create the user, the database reports a conflict, and this "conflict" result is then cached for the new idempotency key.

#### Scenario 4: Request Without Idempotency Key

1.  **Action**:
    *   Disable or remove the `Idempotency-Key` header from the request.
    *   Send it.
2.  **Expected Result**: A `400 Bad Request` with an error message indicating that the header is required.

## 8. Asynchronous Notification Flow

The notification system is designed following an event-driven architecture, orchestrated by Apache Kafka. This approach decouples the primary services from the notification logic, leading to a more resilient and scalable system. If a notification service fails, the events remain in Kafka, ready to be processed once the service recovers, preventing data loss.

The flow is divided into three main stages: data production, alert evaluation, and notification dispatch.

1.  **Data Production**: A user registers an interest in an airport with specific alert thresholds (e.g., `LICC`, `high_value: 2`) by sending a `POST` request to `/data-collector/interests`. When the `data-collector`'s background job fetches new data from the OpenSky Network, it acts as a Kafka producer. For each user interest associated with that airport, it produces a JSON message to the `to-alert-system` topic with the relevant details: `{"user_email": "...", "airport_code": "LICC", "flight_count": 10, "high_value": 2, "low_value": 1}`.

2.  **Alert Evaluation**: The `alert-system` service, acting as a Kafka consumer, listens for messages on the `to-alert-system` topic. Upon receiving a message, it executes its sole business logic: it compares the `flight_count` against the `high_value` and `low_value`. In our example, `10` is greater than `2`, so the condition is met.

3.  **Notification Trigger**: Since the condition is met, the `alert-system` acts as a producer and sends a new, more specific message to the `to-notifier` topic. This message confirms that an alert must be sent and contains the necessary information: `{"user_email": "...", "airport_code": "LICC", "condition": "The number of flights (10) exceeded the high threshold of 2."}`.

4.  **Notification Dispatch**: The `alert-notifier-system` service consumes this final message from the `to-notifier` topic. It then performs a query on the `user_manager`'s database to find the `telegram_chat_id` corresponding to the user's email.

5.  **Message Delivery**: Finally, using the retrieved Chat ID, the service connects to the Telegram Bot API and sends the formatted alert message directly to the user, completing the workflow.
