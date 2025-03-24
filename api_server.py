import os
import psutil
import subprocess
from flask_cors import CORS
from flask import Flask, jsonify, send_file, request
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, verify_jwt_in_request
from flask_swagger_ui import get_swaggerui_blueprint
from dotenv import load_dotenv
from utils import log_info

# Flask app initialization
app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()
app.config["MONGO_URI"] = os.getenv("MONGO_URI") + "test"
app.config["JWT_SECRET_KEY"] = os.urandom(24)

# dotenv variables
access_ip = os.getenv("access_ip", "127.0.0.1")
server_port = os.getenv("server_port", "5000")
username = os.getenv("admin", "admin")
password = os.getenv("password", "password123")

# Initialize PyMongo and JWT
mongo = PyMongo(app)
jwt = JWTManager(app)

# Custom token verification without Bearer prefix
def custom_token_verification():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"msg": "Missing Authorization Header"}), 401

    token = auth_header.strip()
    try:
        verify_jwt_in_request(lambda: token)
    except Exception as e:
        return jsonify({"msg": f"Invalid token: {str(e)}"}), 401

# Swagger configuration without Bearer prefix
swagger_config = {
    "swagger": "2.0",
    "info": {
        "title": "Game Scraping API",
        "description": "API for managing game scrapers and retrieving game details.",
        "version": "1.0.0"
    },
    "host": f"{access_ip}:{server_port}",
    "basePath": "/",
    "schemes": ["http"],
    "securityDefinitions": {
        "TokenAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "headers",
            "description": "Enter your token without the 'Bearer ' prefix"
        }
    },
    "security": [
        {
            "TokenAuth": []
        }
    ],
    "paths": {
        "/login": {
            "post": {
                "summary": "Login",
                "description": "Authenticate user and generate a JWT token.",
                "parameters": [
                    {
                        "name": "body",
                        "in": "body",
                        "required": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "username": {
                                    "type": "string",
                                    "example": "admin"
                                },
                                "password": {
                                    "type": "string",
                                    "example": "password123"
                                }
                            }
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Token generated successfully."
                    },
                    "401": {
                        "description": "Invalid credentials."
                    }
                }
            }
        },
        "/games": {
            "get": {
                "summary": "Get Games",
                "description": "Retrieve a paginated list of games from the database.",
                "parameters": [
                    {
                        "name": "page",
                        "in": "query",
                        "type": "integer",
                        "required": False,
                        "default": 1
                    },
                    {
                        "name": "per_page",
                        "in": "query",
                        "type": "integer",
                        "required": False,
                        "default": 10
                    },
                    {
                        "name": "service",
                        "in": "query",
                        "type": "string",
                        "enum": [
                            "steam",
                            "xbox",
                            "playstation",
                            "nintendo"
                        ]
                    },
                    {
                        "name": "region",
                        "in": "query",
                        "type": "string"
                    }
                ],
                "security": [
                    {
                        "TokenAuth": []
                    }
                ],
                "responses": {
                    "200": {
                        "description": "A paginated list of games.",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "games": {
                                    "type": "array",
                                    "items": {
                                        "type": "object"
                                    }
                                }
                            }
                        }
                    },
                    "401": {
                        "description": "Unauthorized."
                    }
                }
            }
        },
        "/scheduler/start": {
            "post": {
                "summary": "Start Scheduler",
                "description": "Start the game scraper scheduler process.",
                "security": [
                    {
                        "TokenAuth": []
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Scheduler started successfully."
                    },
                    "500": {
                        "description": "Error occurred while starting the scheduler."
                    }
                }
            }
        },
        "/scheduler/stop": {
            "post": {
                "summary": "Stop Scheduler",
                "description": "Stop the game scraper scheduler process.",
                "security": [
                    {
                        "TokenAuth": []
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Scheduler stopped successfully."
                    },
                    "404": {
                        "description": "Scheduler not running."
                    },
                    "500": {
                        "description": "Error occurred while stopping the scheduler."
                    }
                }
            }
        },
        "/scheduler/status": {
            "post": {
                "summary": "Scheduler Status",
                "description": "Check if the game scraper scheduler process is running.",
                "security": [
                    {
                        "TokenAuth": []
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Scheduler status retrieved successfully."
                    },
                    "500": {
                        "description": "Error occurred while checking the scheduler status."
                    }
                }
            }
        },
        "/games/count": {
            "get": {
                "summary": "Get Game Count",
                "description": "Retrieve the count of games for a specific service.",
                "parameters": [
                    {
                        "name": "service",
                        "in": "query",
                        "type": "string",
                        "enum": [
                            "steam",
                            "xbox",
                            "playstation",
                            "nintendo"
                        ],
                        "required": True
                    }
                ],
                "security": [
                    {
                        "TokenAuth": []
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Game count retrieved successfully."
                    },
                    "400": {
                        "description": "Invalid service."
                    }
                }
            }
        },
        "/logs": {
            "get": {
                "summary": "Fetch Logs",
                "description": "Retrieve the scraper logs file.",
                "security": [
                    {
                        "TokenAuth": []
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Logs retrieved successfully."
                    },
                    "500": {
                        "description": "Error occurred while fetching logs."
                    }
                }
            }
        }
    },
}

# The Swagger JSON will be publicly accessible, but other endpoints will require authentication
@app.route("/swagger.json")
def swagger_json():
    return jsonify(swagger_config)

# Swagger UI blueprint
SWAGGER_URL = '/swagger'
API_URL = '/swagger.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Game Scraping API"}
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Check if scheduler.py is running
def is_scheduler_running():
    for proc in psutil.process_iter(attrs=['cmdline']):
        try:
            if proc.info['cmdline'] and "scheduler.py" in proc.info['cmdline']:
                return True
        except (psutil.NoSuchProcess, KeyError):
            continue
    return False

# Routes
@app.route('/scheduler/status', methods=['POST'])
def check_scheduler_status():
    auth_result = custom_token_verification()
    if isinstance(auth_result, tuple):
        return auth_result
    if is_scheduler_running():
        return jsonify({"running": True}), 200
    else:
        return jsonify({"running": False}), 200

@app.route('/scheduler/start', methods=['POST'])
def start_scheduler():
    auth_result = custom_token_verification()
    if isinstance(auth_result, tuple):
        return auth_result
    if is_scheduler_running():
        return jsonify({"msg": "The scheduler is already running on the server."}), 400
    try:
        log_info("******************** Started Scheduler... ********************")
        subprocess.Popen(["python", "scheduler.py"])
        return jsonify({"msg": "Scheduler started"}), 200
    except Exception as e:
        return jsonify({"msg": f"Error starting scheduler: {e}"}), 500

@app.route('/scheduler/stop', methods=['POST'])
def stop_scheduler():
    auth_result = custom_token_verification()
    if isinstance(auth_result, tuple):
        return auth_result
    if not is_scheduler_running():
        return jsonify({"msg": "Nothing works in server now."}), 400
    try:
        scheduler_stopped = False
        for proc in psutil.process_iter(attrs=['pid', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and "scheduler.py" in cmdline:
                    # Kill the scheduler process
                    proc.terminate()
                    proc.wait(timeout=5)
                    scheduler_stopped = True
                    log_info("******************** Killed Scheduler ********************")
                    # Terminate child processes
                    try:
                        children = proc.children(recursive=True)
                        for child in children:
                            try:
                                child.terminate()
                                child.wait(timeout=5)
                            except psutil.NoSuchProcess:
                                pass
                            except Exception as e:
                                print(f"API_server/Stop scheduler : Error terminating child process {child.pid}: {e}")
                    except psutil.NoSuchProcess:
                        pass
                    except Exception as e:
                        print(f"API_server/Stop scheduler : Error retrieving child processes: {e}")
                    break
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                print(f"API_server/Stop scheduler : Error processing scheduler process {proc.pid}: {e}")

        if scheduler_stopped:
            return jsonify({"msg": "Scheduler and its subprocesses stopped"}), 200
        else:
            return jsonify({"msg": "Scheduler not running"}), 404
    except Exception as e:
        return jsonify({"msg": f"Error stopping scheduler: {str(e)}"}), 500

@app.route('/games/count', methods=['GET'])
def get_game_count():
    auth_result = custom_token_verification()
    if isinstance(auth_result, tuple):
        return auth_result
    service = request.args.get('service')

    if service == "steam":
        collection = mongo.db.steam_games
    elif service == "xbox":
        collection = mongo.db.xbox_games
    elif service == "playstation":
        collection = mongo.db.playstation_games
    elif service == "nintendo":
        collection = mongo.db.nintendo_games
    else:
        return jsonify({"msg": "Invalid service"}), 400
    
    count = collection.count_documents({})
    return jsonify({"count": count}), 200

@app.route('/logs', methods=['GET'])
def fetch_logs():
    auth_result = custom_token_verification()
    if isinstance(auth_result, tuple):
        return auth_result
    try:
        return send_file("scraper.log", mimetype="text/plain")
    except Exception as e:
        return jsonify({"msg": f"Error fetching logs: {e}"}), 500

@app.route('/login', methods=['POST'])
def login():
    uname = request.json.get("username")
    pwd = request.json.get("password")
    
    if uname == username and pwd == password:
        token = create_access_token(identity=uname)
        return jsonify(access_token=token), 200
    else:
        return jsonify({"msg": "Invalid credentials"}), 401
    
@app.route('/games', methods=['GET'])
def get_games():
    auth_result = custom_token_verification()
    if isinstance(auth_result, tuple):
        return auth_result
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    service = request.args.get('service')
    region = request.args.get('region')
    
    filters = {}
    if region:
        filters["prices." + region] = {"$ne": "Free or Not Available"}

    if service == "steam":
        collection = mongo.db.steam_games
    elif service == "xbox":
        collection = mongo.db.xbox_games
    elif service == "playstation":
        collection = mongo.db.playstation_games
    elif service == "nintendo":
        collection = mongo.db.nintendo_games
    else:
        collection = mongo.db.steam_games

    games = paginate(collection, page, per_page, filters)

    for game in games:
        if region in game['prices']:
            game['price'] = game['prices'].get(region, "Not Available")
            del game['prices']
    return jsonify({"games": games}), 200

# Helper function to paginate results
def paginate(collection, page, per_page, filters=None):
    query = {}
    if filters:
        query = filters
    results = list(collection.find(query, {"_id": 0}).skip((page - 1) * per_page).limit(per_page))
    return results

if __name__ == '__main__':
    app.run(host=access_ip, port=server_port, debug=False)