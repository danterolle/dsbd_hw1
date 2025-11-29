import os
import threading
from concurrent import futures
from typing import Optional, Any

import grpc
from flask import Flask, request, jsonify
from sqlalchemy.exc import IntegrityError
from models import db, User


try:
    import service_pb2
    import service_pb2_grpc
except ImportError:
    service_pb2 = None
    service_pb2_grpc = None

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

DATA_COLLECTOR_GRPC_HOST: str = "data-collector:50052"

data_collector_grpc_channel = (
    grpc.insecure_channel(DATA_COLLECTOR_GRPC_HOST) if service_pb2_grpc else None
)
data_collector_grpc_stub = (
    service_pb2_grpc.DataCollectorServiceStub(data_collector_grpc_channel)
    if data_collector_grpc_channel
    else None
)

with app.app_context():
    db.create_all()


@app.route("/ping")
def ping():
    return jsonify({"message": "pong"}), 200


@app.route("/users", methods=["POST"])
def add_user():
    data: Optional[dict[str, Any]] = request.get_json()
    if not data or "email" not in data or "nome" not in data or "cognome" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    new_user = User(
        email=data["email"],
        nome=data["nome"],
        cognome=data["cognome"],
        codice_fiscale=data.get("codice_fiscale"),
        iban=data.get("iban"),
    )

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created successfully"}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "User already exists"}), 409


@app.route("/users/<string:email>", methods=["DELETE"])
def delete_user(email):
    user = db.session.get(User, email)
    if not user:
        return jsonify({"error": "User not found"}), 404

    db.session.delete(user)
    db.session.commit()

    if data_collector_grpc_stub:
        try:
            response = data_collector_grpc_stub.DeleteUserInterests(
                service_pb2.UserRequest(email=email)
            )
            if response.success:
                print(
                    f"Successfully deleted {response.deleted_count} interests for {email}"
                )
            else:
                print(f"Failed to delete interests for {email}")
        except grpc.RpcError as e:
            print(f"gRPC Error calling data-collector: {e}")

    return jsonify({"message": "User deleted successfully"}), 200


@app.route("/users/<string:email>", methods=["GET"])
def get_user(email: str):
    user: Optional[User] = db.session.get(User, email)
    if user:
        return jsonify(user.to_dict()), 200
    return jsonify({"error": "User not found"}), 404


@app.route("/users", methods=["GET"])
def get_all_users():
    users = db.session.query(User).all()
    return jsonify([user.to_dict() for user in users])


class UserService(service_pb2_grpc.UserServiceServicer if service_pb2_grpc else object):
    def CheckUserExists(self, request, context):
        with app.app_context():
            try:
                user = db.session.get(User, request.email)
                exists = user is not None
                return service_pb2.UserResponse(exists=exists)
            except Exception as e:
                print(f"Error checking user existence: {e}")
                return service_pb2.UserResponse(exists=False)


def serve_grpc():
    if not service_pb2_grpc:
        print("gRPC modules not found. Run protoc to generate them.")
        return

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port("[::]:50051")
    print("gRPC Server starting on port 50051...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    grpc_thread = threading.Thread(target=serve_grpc)
    grpc_thread.daemon = True
    grpc_thread.start()

    app.run(host="0.0.0.0", port=5000, debug=True)
